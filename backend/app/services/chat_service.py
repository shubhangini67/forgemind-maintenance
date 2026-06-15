from datetime import datetime, timezone
import json
import re

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Conversation, ConversationMessage
from app.services.feedback_service import load_feedback_influence
from app.schemas import ChatRequest, DiagnosisRequest, DiagnosisResponse
from app.services.operational_context import load_operational_context
from app.services.agents.orchestrator import get_orchestrator
from app.services.agents.intent_classifier import (
    FAILURE_SIMULATION,
    classify_chat_intent,
    is_conversational_intent,
)
from app.services.portal_navigation import is_navigation_query
from app.services.scenario_simulation_engine import parse_scenario_params, run_scenario_simulation
from app.services.agents.reasoning_panel import build_reasoning_panel
from app.services.equipment_service import get_equipment, get_plant_twin, list_spare_parts
from app.services.live_stream import peek_reading
from app.services.ml.predictive_engine import pm_engine
from app.services.llm_service import llm_service
from app.core.logging import get_logger
from app.services.procurement_risk import spare_procurement_profile
from app.services.ml.predictive_engine import get_pm_engine, risk_engine
from app.services.rag.knowledge_engine import get_rag_engine

logger = get_logger(__name__)


def _risk_str(value) -> str:
    s = str(value).replace("RiskLevel.", "").lower()
    return s if s in ("low", "medium", "high", "critical") else "medium"


def _urgency_from_ml(ml: dict) -> str:
    prob = ml.get("failure_probability") or 0
    rul = ml.get("remaining_useful_life_hours") or 999
    if prob > 0.85 or rul < 12:
        return "critical"
    if prob > 0.65 or rul < 48:
        return "high"
    if prob > 0.4 or rul < 120:
        return "medium"
    return "low"


def _extract_numbered_actions(text: str) -> list[str]:
    actions = re.findall(r"(?:^\d+\.\s+.+$)", text, re.MULTILINE)
    if actions:
        return [a.lstrip("0123456789. ").strip() for a in actions[:6]]
    return []


def _build_structured_output(
    ml_result: dict,
    equipment_context: dict,
    spare_context: list,
    citations_raw: list,
    response_text: str,
    orchestrator_output: dict | None = None,
) -> dict:
    risk = _risk_str(ml_result.get("risk_level", "medium"))
    urgency = _urgency_from_ml(ml_result)

    structured = {
        "diagnosis": {"probable_causes": [], "root_cause_summary": "", "confidence_score": 0.0},
        "prediction": {
            "rul_hours": ml_result.get("remaining_useful_life_hours"),
            "failure_probability": ml_result.get("failure_probability"),
            "degradation_score": ml_result.get("degradation_score"),
            "risk_level": risk,
            "explanation": ml_result.get("explanation"),
        },
        "risk_assessment": {"risk_level": risk, "urgency": urgency},
        "maintenance_plan": {
            "immediate_actions": [],
            "short_term_actions": [],
            "long_term_actions": [],
            "monitoring_plan": "Continue C-MAPSS sensor monitoring every 2 hours",
        },
        "procurement": {"spares": spare_context[:5], "recommendation": ""},
        "equipment": equipment_context,
        "sensor_snapshot": {},
        "citations_count": len(citations_raw),
        "data_lineage": [
            "4.2 Sensors: NASA C-MAPSS FD001 live replay (condition monitoring)",
            "4.3 Knowledge: RAG over manuals, SOPs, failure reports (Qdrant)",
            "4.3 History: maintenance records + logbook indexed in RAG",
            "4.1 Operations: delay logs, fault alerts, failure incidents (Postgres)",
            "4.4 Interaction: multi-turn NL chat with follow-up suggestions",
            "ML: Isolation Forest anomaly + XGBoost RUL (C-MAPSS-trained)",
            "Agents: Supervisor-led LangGraph orchestrator with dynamic routing",
        ],
    }

    if orchestrator_output:
        diag = orchestrator_output.get("diagnosis", {})
        plan = orchestrator_output.get("maintenance_plan", {})
        structured["diagnosis"] = {
            "probable_causes": diag.get("probable_causes", []),
            "root_cause_summary": diag.get("root_cause_analysis", ""),
            "confidence_score": diag.get("confidence_score", 0.75),
        }
        structured["maintenance_plan"] = {
            "immediate_actions": plan.get("immediate_actions", []),
            "short_term_actions": plan.get("short_term_actions", []),
            "long_term_actions": plan.get("long_term_actions", []),
            "monitoring_plan": plan.get("monitoring_plan", structured["maintenance_plan"]["monitoring_plan"]),
        }
        risk_assess = orchestrator_output.get("risk_assessment", {})
        if risk_assess:
            structured["risk_assessment"]["risk_level"] = _risk_str(risk_assess.get("risk_level", risk))
        proc_notes = risk_assess.get("procurement_notes", [])
        if proc_notes:
            structured["procurement"]["recommendation"] = proc_notes[0]
    else:
        structured["diagnosis"]["probable_causes"] = [
            {"cause": "Bearing degradation (C-MAPSS vibration pattern)", "confidence": 0.72},
        ] if risk in ("high", "critical") else [{"cause": "Normal wear within expected curve", "confidence": 0.65}]
        structured["diagnosis"]["root_cause_summary"] = ml_result.get("explanation", "")
        structured["diagnosis"]["confidence_score"] = round(1 - (ml_result.get("failure_probability") or 0.3), 2)
        structured["maintenance_plan"]["immediate_actions"] = _extract_numbered_actions(response_text) or [
            "Inspect bearing assembly and lubrication system",
            "Verify sensor readings against baseline",
        ]

    low_stock = [s for s in spare_context if s.get("quantity_available", 0) <= 3]
    if low_stock and not structured["procurement"]["recommendation"]:
        structured["procurement"]["recommendation"] = (
            f"Procure {low_stock[0]['part_number']} — only {low_stock[0]['quantity_available']} in stock"
        )
    return structured


async def get_or_create_conversation(
    db: AsyncSession, user_id: int, conversation_id: int | None, equipment_id: int | None
) -> Conversation:
    if conversation_id:
        result = await db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            if equipment_id and conv.equipment_id != equipment_id:
                conv.equipment_id = equipment_id
            return conv
    conv = Conversation(user_id=user_id, equipment_id=equipment_id, title="Maintenance Chat")
    db.add(conv)
    await db.flush()
    return conv


async def truncate_conversation_from_message(
    db: AsyncSession, user_id: int, conversation_id: int, message_id: int
) -> None:
    conv = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    if not conv.scalar_one_or_none():
        raise ValueError("Conversation not found")

    anchor = await db.get(ConversationMessage, message_id)
    if not anchor or anchor.conversation_id != conversation_id:
        raise ValueError("Message not found")

    result = await db.execute(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.created_at >= anchor.created_at,
        )
    )
    for msg in result.scalars().all():
        await db.delete(msg)
    await db.flush()


async def list_user_conversations(db: AsyncSession, user_id: int, limit: int = 30) -> list[dict]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
    )
    conversations = list(result.scalars().all())
    summaries: list[dict] = []
    for conv in conversations:
        msg_count = await db.scalar(
            select(func.count())
            .select_from(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
        )
        preview_row = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id, ConversationMessage.role == "user")
            .order_by(ConversationMessage.created_at)
            .limit(1)
        )
        preview_msg = preview_row.scalar_one_or_none()
        summaries.append({
            "id": conv.id,
            "title": conv.title,
            "equipment_id": conv.equipment_id,
            "updated_at": conv.updated_at,
            "message_count": int(msg_count or 0),
            "preview": (preview_msg.content[:120] if preview_msg else None),
        })
    return summaries


async def get_conversation_detail(db: AsyncSession, user_id: int, conversation_id: int) -> dict:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise ValueError("Conversation not found")

    msg_result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
    )
    messages = []
    for m in msg_result.scalars().all():
        meta = m.metadata_json or {}
        follow_ups = meta.get("follow_up_suggestions") or meta.get("follow_ups") or []
        reasoning_panel = meta.get("reasoning_panel")
        structured = meta.get("structured_output") or {}
        explainability = structured.get("explainability") or meta.get("explainability")
        chat_style = structured.get("chat_style") or meta.get("chat_style")
        if m.role == "assistant" and not follow_ups:
            follow_ups = _extract_follow_ups(m.content, query_intent="general")
        is_conv = chat_style == "conversational"
        messages.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at,
            "follow_ups": follow_ups[:3] if m.role == "assistant" else [],
            "reasoning_panel": None if is_conv else (reasoning_panel if m.role == "assistant" else None),
            "explainability": None if is_conv else (explainability if m.role == "assistant" else None),
            "chat_style": chat_style if m.role == "assistant" else None,
        })
    return {
        "id": conv.id,
        "equipment_id": conv.equipment_id,
        "title": conv.title,
        "messages": messages,
    }


async def _load_feedback_influence(db: AsyncSession, equipment_id: int | None) -> dict:
    return await load_feedback_influence(db, equipment_id)

async def _build_context(db: AsyncSession, equipment_id: int | None) -> tuple[dict, dict, list]:
    equipment_context = {}
    sensor_reading = {}
    if not equipment_id:
        return equipment_context, sensor_reading, []

    equipment = await get_equipment(db, equipment_id)
    if not equipment:
        return equipment_context, sensor_reading, []

    equipment_context = {
        "id": equipment.id,
        "equipment_code": equipment.equipment_code,
        "name": equipment.name,
        "equipment_type": equipment.equipment_type,
        "criticality": equipment.criticality,
        "location": equipment.location,
        "plant_sector": (equipment.metadata_json or {}).get("plant_sector", equipment.location),
        "downtime_cost": (equipment.metadata_json or {}).get("downtime_cost", equipment.criticality * 25000),
        "data_source": (equipment.metadata_json or {}).get("data_source", "unknown"),
        "cmapss_unit": (equipment.metadata_json or {}).get("cmapss_unit"),
    }

    from app.models import SensorData

    # Live NASA C-MAPSS FD001 replay — same stream as Live Monitor
    from app.services.live_stream import get_next_reading

    live = get_next_reading(equipment_id)
    sensor_reading = {
        "temperature": live["temperature"],
        "vibration": live["vibration"],
        "pressure": live["pressure"],
        "motor_current": live["motor_current"],
        "health_indicator": live["health_indicator"],
        "cycle": live.get("cycle"),
        "rul_hours": live.get("rul_hours"),
        "rul_cycles": live.get("rul_cycles"),
        "degradation_index": live.get("degradation_index"),
        "cmapss_unit": live.get("cmapss_unit"),
        "cmapss_sensors": live.get("cmapss_sensors", {}),
        "source": live.get("source", "NASA C-MAPSS FD001"),
        "dataset": live.get("dataset", "FD001"),
        "timestamp": live.get("timestamp"),
    }
    equipment_context["cmapss_unit"] = live.get("cmapss_unit") or equipment_context.get("cmapss_unit")
    # Read-only snapshot for chat — do not persist sensor rows on every message

    spares = await list_spare_parts(db)
    spare_context = [
        {
            "part_number": s.part_number,
            "name": s.name,
            "quantity_available": s.quantity_available,
            "lead_time_days": s.lead_time_days,
            "reorder_level": s.reorder_level,
            "unit_cost": float(s.unit_cost or 0),
        }
        for s in spares
        if s.equipment_type == equipment.equipment_type
    ]
    return equipment_context, sensor_reading, spare_context


async def _load_fleet_snapshot(db: AsyncSession) -> dict:
    """Fleet-wide asset + spare snapshot for ranking and inventory intents."""
    twin = await get_plant_twin(db)
    assets = []
    for a in twin.get("assets") or []:
        live = peek_reading(a["id"])
        live_pred = pm_engine.predict_rul({
            "temperature": live["temperature"],
            "vibration": live["vibration"],
            "pressure": live.get("pressure", 120),
            "motor_current": live.get("motor_current", 60),
            "health_indicator": live["health_indicator"],
        })
        assets.append({
            **a,
            "rul_hours": live_pred.get("remaining_useful_life_hours") or live.get("rul_hours") or a.get("rul_hours"),
            "failure_probability": live_pred.get("failure_probability") or a.get("failure_probability"),
            "health_score": live.get("health_indicator") or a.get("health_score"),
        })

    all_spares = await list_spare_parts(db)
    critical_spares = [
        {
            "part_number": s.part_number,
            "name": s.name,
            "quantity_available": s.quantity_available,
            "reorder_level": s.reorder_level,
            "lead_time_days": s.lead_time_days,
            "equipment_type": s.equipment_type,
        }
        for s in all_spares
    ]
    return {"assets": assets, "critical_spares": critical_spares, "summary": twin.get("summary")}


def _normalize_question(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip("?.! "))


def _questions_similar(a: str, b: str) -> bool:
    na, nb = _normalize_question(a), _normalize_question(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    tokens_a = set(na.split())
    tokens_b = set(nb.split())
    overlap = tokens_a & tokens_b
    return len(overlap) >= max(3, min(len(tokens_a), len(tokens_b)) * 0.7)


def _prior_user_questions(history: list[dict[str, str]], current: str = "") -> list[str]:
    asked = [_normalize_message(h["content"]) for h in history if h.get("role") == "user"]
    if current:
        asked.append(_normalize_message(current))
    return asked


def _parse_inline_follow_ups(text: str) -> list[str]:
    follow_ups: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("->") or stripped.startswith("→"):
            cleaned = stripped.lstrip("->→").strip()
            if len(cleaned) > 10:
                follow_ups.append(cleaned)
    return follow_ups


def _parse_follow_up_json(raw: str) -> list[str]:
    text = (raw or "").strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            chunk = part.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("["):
                text = chunk
                break
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if isinstance(item, str) and len(str(item).strip()) > 8]


def _filter_follow_ups(
    candidates: list[str],
    user_message: str,
    history: list[dict[str, str]],
) -> list[str]:
    asked = _prior_user_questions(history, user_message)
    filtered: list[str] = []
    for fu in candidates:
        if any(_questions_similar(fu, prev) for prev in asked):
            continue
        if any(_questions_similar(fu, existing) for existing in filtered):
            continue
        filtered.append(fu)
    return filtered


def _fallback_follow_ups_from_analysis(
    user_message: str,
    query_intent: str,
    equipment_context: dict,
    structured_output: dict,
    history: list[dict[str, str]],
) -> list[str]:
    """Derive next questions from analysis output when LLM suggestion is unavailable."""
    code = equipment_context.get("equipment_code", "this unit")
    pred = structured_output.get("prediction") or {}
    diagnosis = structured_output.get("diagnosis") or {}
    plan = structured_output.get("maintenance_plan") or {}
    risk = structured_output.get("risk_assessment") or {}
    asked = _prior_user_questions(history, user_message)

    candidates: list[str] = []
    causes = diagnosis.get("probable_causes") or []
    if causes and query_intent != "diagnosis":
        top = causes[0].get("cause", "") if isinstance(causes[0], dict) else str(causes[0])
        if top:
            candidates.append(f"How urgent is it to act on: {top[:80]}?")
    if pred.get("remaining_useful_life_hours") is not None and query_intent != "rul":
        candidates.append(f"If RUL is {float(pred['remaining_useful_life_hours']):.0f}h, when should we schedule the shutdown?")
    if plan.get("immediate_actions"):
        candidates.append(f"What is the fastest way to complete step 1 for {code}?")
    if risk.get("procurement_notes"):
        candidates.append(f"Which spare part order should we raise first for {code}?")
    if query_intent == "rul":
        candidates.extend([
            f"What sensor trend explains the RUL drop on {code}?",
            f"Which bearing or lubrication check should we run first on {code}?",
            f"What production impact if {code} fails before the next PM window?",
        ])
    elif query_intent == "diagnosis":
        candidates.extend([
            f"What inspection steps confirm this fault on {code}?",
            f"Which spare parts should be staged before we open {code}?",
            f"How many hours of safe operation remain on {code}?",
        ])
    else:
        candidates.extend([
            f"What should we inspect first on {code} based on this answer?",
            f"What is the operational risk if we delay action on {code}?",
            f"Which SOP applies to the next maintenance step for {code}?",
        ])

    return _filter_follow_ups(candidates, user_message, history)[:3]


async def _generate_agentic_follow_ups(
    *,
    user_message: str,
    assistant_response: str,
    query_intent: str,
    equipment_context: dict,
    sensor_reading: dict,
    history: list[dict[str, str]],
    structured_output: dict | None = None,
) -> list[str]:
    """LLM-generated follow-ups based on conversation — like ChatGPT suggested replies."""
    structured_output = structured_output or {}
    inline = _parse_inline_follow_ups(assistant_response)
    asked = _prior_user_questions(history, user_message)

    code = equipment_context.get("equipment_code", "Asset")
    name = equipment_context.get("name", "")
    sensor_bits = []
    if sensor_reading:
        for key, label in (
            ("temperature", "temp"),
            ("vibration", "vib"),
            ("health_indicator", "health"),
            ("rul_hours", "RUL"),
            ("cycle", "cycle"),
        ):
            val = sensor_reading.get(key)
            if val is not None:
                sensor_bits.append(f"{label}={val}")
    sensor_summary = ", ".join(sensor_bits) or "no live sensors"

    history_block = ""
    for msg in (history or [])[-6:]:
        role = "Engineer" if msg.get("role") == "user" else "Assistant"
        history_block += f"{role}: {msg.get('content', '')[:350]}\n"

    already_asked = "\n".join(f"- {q}" for q in asked[-8:]) or "- (none yet)"
    analysis_hint = json.dumps(
        {
            k: structured_output.get(k)
            for k in ("prediction", "diagnosis", "risk_assessment", "maintenance_plan")
            if structured_output.get(k)
        },
        default=str,
    )[:1200]

    prompt = f"""Suggest exactly 3 follow-up questions a Tata Steel maintenance engineer would ask NEXT in this chat.

Equipment: {code} — {name}
Live sensors: {sensor_summary}
Query intent: {query_intent}

Conversation so far:
{history_block}
Engineer (latest): {user_message}
Assistant (latest): {assistant_response[:1200]}

Analysis data (use for specificity):
{analysis_hint}

Questions already asked (do NOT repeat or rephrase):
{already_asked}

Rules:
1. Each question must logically continue THIS conversation — reference specific findings (RUL, vibration, root cause, spares, etc.)
2. Vary the angle: e.g. diagnosis → action → spares → schedule → business impact
3. 8–18 words each, natural engineer language
4. Do NOT repeat prior questions
5. Return ONLY a JSON array of 3 strings — no markdown, no explanation

Example: ["Should we schedule bearing inspection before the next shift?", "Which BRG part number matches this vibration signature?", "What downtime cost if we run 48 more hours?"]
"""
    try:
        raw = await llm_service.generate(
            prompt,
            system=(
                "You generate contextual chat follow-up questions for industrial maintenance engineers. "
                "Output must be a valid JSON array of exactly 3 strings."
            ),
            history=None,
        )
        llm_suggestions = _parse_follow_up_json(raw)
        merged = _filter_follow_ups(inline + llm_suggestions, user_message, history)
        if len(merged) >= 3:
            return merged[:3]
    except Exception as exc:
        logger.warning("agentic_follow_ups_failed", error=str(exc))

    merged = _filter_follow_ups(inline, user_message, history)
    if len(merged) >= 3:
        return merged[:3]

    fallback = _fallback_follow_ups_from_analysis(
        user_message, query_intent, equipment_context, structured_output, history
    )
    for item in fallback:
        if len(merged) >= 3:
            break
        if not any(_questions_similar(item, m) for m in merged):
            merged.append(item)
    return merged[:3]


def _extract_follow_ups(
    text: str,
    user_message: str = "",
    query_intent: str = "general",
    equipment_context: dict | None = None,
    history: list[dict[str, str]] | None = None,
    structured_output: dict | None = None,
) -> list[str]:
    """Sync fallback for reloading old messages without stored follow-ups."""
    history = history or []
    equipment_context = equipment_context or {}
    inline = _parse_inline_follow_ups(text)
    filtered = _filter_follow_ups(inline, user_message, history)
    if len(filtered) >= 3:
        return filtered[:3]
    fallback = _fallback_follow_ups_from_analysis(
        user_message, query_intent, equipment_context, structured_output or {}, history
    )
    for item in fallback:
        if len(filtered) >= 3:
            break
        if not any(_questions_similar(item, f) for f in filtered):
            filtered.append(item)
    return filtered[:3]


def _normalize_message(message: str) -> str:
    """Strip UI context prefixes so the model answers the actual question."""
    cleaned = re.sub(r"\[Context:[^\]]+\]\s*", "", message, flags=re.IGNORECASE).strip()
    return cleaned or message.strip()


def _classify_query_intent(message: str) -> str:
    """Classify into one of eight chat intents (delegates to intent_classifier)."""
    return classify_chat_intent(message)


def _format_inr(amount: float) -> str:
    return f"₹{amount:,.0f}"


def _spares_cost_focused_response(equipment_context: dict, spare_context: list) -> dict:
    code = equipment_context.get("equipment_code", "Asset")
    name = equipment_context.get("name", "")
    etype = equipment_context.get("equipment_type", "this equipment type")

    if not spare_context:
        message = (
            f"**Spare parts cost for {code}** ({name})\n\n"
            f"No spare parts with pricing are mapped to `{etype}` in inventory.\n"
            "Check **Inventory** module or raise a procurement request for a cost quote."
        )
    else:
        lines = [f"**Spare parts cost for {code}** ({name})\n"]
        total_inventory = 0.0
        for s in spare_context:
            unit = float(s.get("unit_cost") or 0)
            qty = int(s.get("quantity_available", 0))
            line_value = unit * qty
            total_inventory += line_value
            lines.append(
                f"- **{s['part_number']}** — {s['name']}: **{_format_inr(unit)}/unit** · "
                f"{qty} in stock · on-hand value **{_format_inr(line_value)}**"
            )
        lines.append(f"\n**Total inventory value (on hand):** {_format_inr(total_inventory)}")

        low_stock = [s for s in spare_context if s.get("quantity_available", 0) <= s.get("reorder_level", 5)]
        if low_stock:
            lines.append("\n**Estimated cost to replenish low-stock items:**")
            total_procure = 0.0
            for s in low_stock:
                qty = int(s.get("quantity_available", 0))
                reorder = int(s.get("reorder_level", 5))
                order_qty = max(reorder - qty + 2, 2)
                unit = float(s.get("unit_cost") or 0)
                line_cost = order_qty * unit
                total_procure += line_cost
                lines.append(
                    f"- {s['name']} ({s['part_number']}): {order_qty} units × {_format_inr(unit)} = **{_format_inr(line_cost)}**"
                )
            lines.append(f"\n**Total replenishment estimate:** {_format_inr(total_procure)}")
        else:
            lines.append("\nAll mapped spares are above reorder level — no urgent purchase cost right now.")

        message = "\n".join(lines)

    message += (
        "\n\n-> What spare parts should we procure?\n"
        "-> What is the RUL for this unit?\n"
        "-> Generate a maintenance plan for the next 7 days"
    )
    return {
        "message": message,
        "agent_trace": ["Spares Agent → direct cost answer (query-focused path)"],
        "agent_thoughts": [{
            "agent": "spare_parts_agent",
            "label": "Spares & Risk",
            "status": "complete",
            "detail": f"Answered spare-parts cost question for {code} from unit_cost in inventory.",
            "data": {"spares": spare_context[:5]},
        }],
        "citations": [],
        "structured_output": {"procurement": {"spares": spare_context[:5]}},
    }


def _spares_focused_response(
    equipment_context: dict,
    spare_context: list,
    sensor_reading: dict,
) -> dict:
    code = equipment_context.get("equipment_code", "Asset")
    name = equipment_context.get("name", "")
    etype = equipment_context.get("equipment_type", "this equipment type")

    if not spare_context:
        message = (
            f"**Spares to procure for {code}** ({name})\n\n"
            f"No spare parts are mapped to `{etype}` in inventory yet.\n\n"
            "**Recommended procurement:**\n"
            "1. Bearing assembly matched to equipment type\n"
            "2. Drive belt / coupling consumables\n"
            "3. Seal kit for lubrication system\n\n"
            "Raise a procurement ticket and map parts to this equipment type in Inventory."
        )
    else:
        lines = [f"**Spares to procure for {code}** ({name})\n"]
        procure: list[dict] = []
        for s in spare_context:
            qty = int(s.get("quantity_available", 0))
            reorder = int(s.get("reorder_level", 5))
            lead = int(s.get("lead_time_days", 14))
            unit = float(s.get("unit_cost") or 0)
            action = "**ORDER NOW**" if qty <= reorder else "OK"
            cost_bit = f" · {_format_inr(unit)}/unit" if unit else ""
            lines.append(
                f"- **{s['part_number']}** — {s['name']}: **{qty}** in stock (reorder at {reorder}) · "
                f"lead **{lead}d** · {action}{cost_bit}"
            )
            if qty <= reorder:
                procure.append(s)

        if procure:
            lines.append(f"\n**Priority orders ({len(procure)}):**")
            for i, s in enumerate(procure, 1):
                qty = int(s.get("quantity_available", 0))
                reorder = int(s.get("reorder_level", 5))
                order_qty = max(reorder - qty + 2, 2)
                lines.append(
                    f"{i}. **{s['name']}** ({s['part_number']}) — order **{order_qty}** units "
                    f"(only {qty} available, {s.get('lead_time_days', 14)}d lead time)"
                )
        else:
            lines.append("\nAll mapped spares are **above reorder level** — no urgent procurement required.")

        vib = sensor_reading.get("vibration")
        if vib and float(vib) >= 6.0:
            lines.append(
                f"\n*Sensor note: vibration {float(vib):.2f} mm/s — expedite bearing-related spares if a shutdown is planned.*"
            )
        message = "\n".join(lines)

    message += (
        "\n\n-> What is the RUL for this unit?\n"
        "-> Generate a maintenance plan for the next 7 days\n"
        "-> Find bearing replacement SOP"
    )
    return {
        "message": message,
        "agent_trace": ["Spares Agent → direct inventory answer (query-focused path)"],
        "agent_thoughts": [{
            "agent": "spare_parts_agent",
            "label": "Spares & Risk",
            "status": "complete",
            "detail": f"Answered spare-parts question for {code} from live inventory — skipped generic assessment template.",
            "data": {"spares": spare_context[:5]},
        }],
        "citations": [],
        "structured_output": {
            "risk_assessment": {"procurement_notes": [
                f"Procure {s['name']} — only {s['quantity_available']} in stock" for s in spare_context
                if s.get("quantity_available", 0) <= s.get("reorder_level", 5)
            ][:3]},
        },
    }


def _rul_focused_response(equipment_context: dict, sensor_reading: dict) -> dict:
    code = equipment_context.get("equipment_code", "Asset")
    unit = equipment_context.get("cmapss_unit") or sensor_reading.get("cmapss_unit", "—")
    cycle = sensor_reading.get("cycle", "—")
    rul = sensor_reading.get("rul_hours")
    health = sensor_reading.get("health_indicator")
    vib = sensor_reading.get("vibration")
    temp = sensor_reading.get("temperature")

    pm = get_pm_engine()
    pred = pm.predict_rul(sensor_reading) if sensor_reading else {}
    rul_h = rul if rul is not None else pred.get("remaining_useful_life_hours")
    fail_prob = pred.get("failure_probability")
    risk = pred.get("risk_level")
    risk_str = risk.value if hasattr(risk, "value") else str(risk or "medium")

    rul_txt = f"**{float(rul_h):.0f} hours** (~{float(rul_h) / 24:.1f} days)" if rul_h is not None else "**unavailable**"
    message = (
        f"**RUL for {code}** (C-MAPSS FD001 Unit {unit}, cycle {cycle})\n\n"
        f"Estimated remaining useful life: {rul_txt}\n"
        f"- Failure probability: **{float(fail_prob or 0) * 100:.1f}%**\n"
        f"- Risk level: **{risk_str}**\n"
        f"- Current health: **{float(health or 0):.1f}%** · vibration **{float(vib or 0):.2f} mm/s** · temp **{float(temp or 0):.1f}°C**\n\n"
    )
    if rul_h is not None and float(rul_h) < 48:
        message += "**Urgency:** Schedule intervention within 24–48h — RUL is critically low.\n"
    elif rul_h is not None and float(rul_h) < 120:
        message += "**Urgency:** Plan maintenance within the next week before RUL drops further.\n"
    else:
        message += "**Urgency:** Continue monitoring; schedule PM before RUL falls below 48h.\n"

    message += (
        "\n-> What spare parts should we procure?\n"
        "-> Analyze degradation root cause\n"
        "-> Generate a 7-day maintenance plan"
    )
    return {
        "message": message,
        "agent_trace": ["Predictive Engine → direct RUL answer (query-focused path)"],
        "agent_thoughts": [{
            "agent": "predictive_agent",
            "label": "Predictive Engine",
            "status": "complete",
            "detail": f"Answered RUL question for {code} from live C-MAPSS replay.",
            "data": {"prediction": pred},
        }],
        "citations": [],
        "structured_output": {"prediction": {
            k: (v.value if hasattr(v, "value") else v) for k, v in pred.items() if k != "features_used"
        }},
    }


def _diagnosis_focused_response(equipment_context: dict, sensor_reading: dict) -> dict:
    """Direct root-cause answer — avoids generic RUL fallback when LLM is unavailable."""
    code = equipment_context.get("equipment_code", "Asset")
    unit = equipment_context.get("cmapss_unit") or sensor_reading.get("cmapss_unit", "—")
    cycle = sensor_reading.get("cycle", "—")
    vib = float(sensor_reading.get("vibration", 0) or 0)
    temp = float(sensor_reading.get("temperature", 0) or 0)
    health = float(sensor_reading.get("health_indicator", 100) or 100)
    pressure = sensor_reading.get("pressure")
    current = sensor_reading.get("motor_current")

    pm = get_pm_engine()
    pred = pm.predict_rul(sensor_reading) if sensor_reading else {}
    failure_prob = float(pred.get("failure_probability", 0) or 0)
    rul_h = sensor_reading.get("rul_hours") or pred.get("remaining_useful_life_hours")
    risk = pred.get("risk_level")
    risk_str = risk.value if hasattr(risk, "value") else str(risk or "medium")

    causes: list[dict] = []
    if vib >= 8.5:
        causes.append({"cause": f"Bearing defect — vibration {vib:.2f} mm/s (C-MAPSS unit {unit}, cycle {cycle})", "confidence": 0.88})
    elif vib >= 4.5:
        causes.append({"cause": f"Bearing wear / misalignment — vibration {vib:.2f} mm/s trending above baseline", "confidence": 0.80})
    if temp >= 95:
        causes.append({"cause": f"Thermal overload — {temp:.1f}°C at cycle {cycle} (FD001 degradation signature)", "confidence": 0.79})
    elif temp >= 85:
        causes.append({"cause": f"Elevated friction/heat — {temp:.1f}°C correlates with C-MAPSS s_4 drift", "confidence": 0.71})
    if failure_prob >= 0.5:
        causes.append({"cause": f"ML degradation signal — {failure_prob:.0%} failure probability from XGBoost RUL model", "confidence": 0.75})
    if health < 60:
        causes.append({"cause": f"Progressive component wear — health {health:.0f}% with ~{float(rul_h or 0):.0f}h RUL remaining", "confidence": 0.82})
    if not causes:
        causes.append({"cause": "Normal wear within C-MAPSS expected degradation curve — continue trend monitoring", "confidence": 0.65})

    cause_lines = "\n".join(
        f"{i}. **{c['cause']}** (confidence {c['confidence']:.0%})"
        for i, c in enumerate(causes[:4], 1)
    )
    message = (
        f"**Root cause analysis for {code}** (C-MAPSS FD001 Unit {unit}, cycle {cycle})\n\n"
        f"**Probable root causes:**\n{cause_lines}\n\n"
        f"**Sensor evidence:** temp **{temp:.1f}°C** · vibration **{vib:.2f} mm/s** · "
        f"health **{health:.1f}%** · pressure **{float(pressure or 0):.1f} bar** · "
        f"current **{float(current or 0):.1f} A**\n\n"
        f"**Assessment:** Degradation pattern matches NASA turbofan wear trajectory — risk **{risk_str}**.\n\n"
        f"**Recommended next steps:**\n"
        f"1. Inspect bearing assembly and lubrication system\n"
        f"2. Log C-MAPSS cycle {cycle} reading in digital logbook\n"
        f"3. Verify spare parts availability before next shift\n\n"
        f"-> What is the RUL for this unit?\n"
        f"-> What spare parts should we procure?\n"
        f"-> Find bearing replacement SOP"
    )
    diagnosis = {
        "probable_causes": causes[:4],
        "root_cause_analysis": f"FD001 unit {unit} cycle {cycle}: sensor-driven RCA",
        "confidence_score": round(max(c.get("confidence", 0.5) for c in causes), 2),
        "risk_level": risk_str,
    }
    return {
        "message": message,
        "agent_trace": ["Diagnostic Engine → direct root-cause answer (query-focused path)"],
        "agent_thoughts": [{
            "agent": "rca_agent",
            "label": "Diagnostic Engine",
            "status": "complete",
            "detail": f"Answered root-cause question for {code} from live C-MAPSS sensors.",
            "data": {"diagnosis": diagnosis},
        }],
        "citations": [],
        "structured_output": {"diagnosis": diagnosis, "prediction": {
            k: (v.value if hasattr(v, "value") else v) for k, v in pred.items() if k != "features_used"
        }},
    }


def _route_focused_response(
    intent: str,
    equipment_context: dict,
    sensor_reading: dict,
    spare_context: list,
) -> dict | None:
    if intent == "spares_cost":
        return _spares_cost_focused_response(equipment_context, spare_context)
    if intent == "spares":
        return _spares_focused_response(equipment_context, spare_context, sensor_reading)
    if intent == "rul":
        return _rul_focused_response(equipment_context, sensor_reading)
    if intent == "diagnosis":
        return _diagnosis_focused_response(equipment_context, sensor_reading)
    return None


def _is_casual_message(message: str) -> bool:
    """True when query is conversational and should skip maintenance agents."""
    return is_conversational_intent(classify_chat_intent(message))


def _conversational_follow_ups(message: str, *, has_equipment: bool) -> list[str]:
    m = message.lower().strip()
    if _is_greeting_simple(m):
        if has_equipment:
            return ["What should we do?", "What's the RUL?", "Show root cause"]
        return ["Where is live monitor?", "Rank fleet by RUL", "Open dashboard"]
    if is_navigation_query(message):
        return ["Rank fleet by RUL", "Show priority queue"] if not has_equipment else ["What's the RUL?", "What should we do?"]
    if has_equipment:
        return ["What should we do?", "How urgent is this?", "Critical spares"]
    return ["Rank all assets by RUL", "Where is the logbook?", "Fleet health summary"]


def _is_greeting_simple(m: str) -> bool:
    return m in ("hi", "hello", "hey", "hii", "good morning", "good afternoon") or (
        len(m) <= 12 and any(m.startswith(w) for w in ("hi", "hey", "hello"))
    )


from app.core.logbook_events import LogbookEventSource, LogbookEventType
from app.services.logbook_service import emit_logbook_event


def _classify_agent_type(message: str) -> str:
    msg = message.lower()
    if any(w in msg for w in ["diagnos", "fault", "failure", "vibration", "root cause", "symptom"]):
        return "diagnostic"
    if any(w in msg for w in ["rul", "predict", "forecast", "degradation", "remaining"]):
        return "predictive"
    if any(w in msg for w in ["spare", "procure", "inventory", "stock", "reorder", "cost", "price"]):
        return "spares"
    if any(w in msg for w in ["sop", "manual", "procedure", "how to", "steps"]):
        return "knowledge"
    if any(w in msg for w in ["report", "summary", "brief"]):
        return "report"
    return "advisory"


async def process_chat(db: AsyncSession, user_id: int, request: ChatRequest) -> dict:
    if request.branch_from_message_id and request.conversation_id:
        await truncate_conversation_from_message(
            db, user_id, request.conversation_id, request.branch_from_message_id
        )

    conv = await get_or_create_conversation(db, user_id, request.conversation_id, request.equipment_id)

    hist_result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conv.id)
        .order_by(ConversationMessage.created_at)
        .limit(20)
    )
    history = [{"role": m.role, "content": m.content} for m in hist_result.scalars().all()]

    user_row = ConversationMessage(conversation_id=conv.id, role="user", content=request.message)
    db.add(user_row)
    await db.flush()

    if not conv.title or conv.title == "Maintenance Chat":
        user_count = await db.scalar(
            select(func.count())
            .select_from(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id, ConversationMessage.role == "user")
        )
        if user_count == 1:
            conv.title = request.message.strip()[:80]

    user_message = _normalize_message(request.message)
    query_intent = _classify_query_intent(user_message)

    # In asset mode, a selected unit means the engineer expects diagnostics.
    # Only keep casual chat for clear greetings / meta / navigation; otherwise run the pipeline.
    if request.equipment_id and is_conversational_intent(query_intent):
        from app.services.agents.intent_classifier import DIAGNOSTIC, _is_greeting, is_definition_query, normalize_message
        from app.services.meta_chat import is_meta_conversational
        from app.services.portal_navigation import is_navigation_query

        m_norm = normalize_message(user_message).lower()
        if not (
            _is_greeting(m_norm)
            or is_meta_conversational(user_message)
            or is_navigation_query(user_message)
            or is_definition_query(user_message)
        ):
            query_intent = DIAGNOSTIC

    page_note = f" (viewing {request.page_context})" if request.page_context else ""

    equipment_context, sensor_reading, spare_context = await _build_context(db, request.equipment_id)
    operational_context = await load_operational_context(db, request.equipment_id)
    feedback_influence = await _load_feedback_influence(db, request.equipment_id)

    ml_result: dict = {}

    scenario_sim = None
    is_failure_sim = query_intent == FAILURE_SIMULATION or bool(parse_scenario_params(user_message))
    if is_failure_sim:
        scenario_sim = run_scenario_simulation(
            query=user_message,
            equipment_context=equipment_context,
            sensor_reading=sensor_reading,
            spare_context=spare_context,
            operational_context=operational_context,
            force_standard_horizons=True,
        )
        query_intent = FAILURE_SIMULATION

    fleet_snapshot = await _load_fleet_snapshot(db)

    orch = await get_orchestrator().run(
        query=user_message,
        query_intent=query_intent,
        page_context=request.page_context,
        equipment_context=equipment_context,
        sensor_reading=sensor_reading,
        spare_context=spare_context,
        feedback_hints=feedback_influence.get("hints", []),
        feedback_scoring=feedback_influence,
        history=history,
        operational_context=operational_context,
        scenario_simulation=scenario_sim,
        fleet_snapshot=fleet_snapshot,
        intent_routed_chat=True,
    )

    is_conversational = (
        is_conversational_intent(query_intent)
        or orch.get("structured_output", {}).get("chat_style") == "conversational"
    )

    if not is_conversational and request.equipment_id:
        code = equipment_context.get("equipment_code", "Asset")
        await emit_logbook_event(
            db,
            event=LogbookEventType.AI_ANALYSIS,
            equipment_id=request.equipment_id,
            title=f"AI analysis — {code}",
            description=f"Query: {user_message[:500]}{page_note}\n\nSummary: {(orch.get('message') or '')[:800]}",
            observed_by="AI Maintenance Wizard",
            source=LogbookEventSource.CHAT,
            source_id=conv.id,
            metadata={"page_context": request.page_context, "query_intent": query_intent},
        )
    response_text = orch["message"]
    citations_raw = orch.get("citations") or []
    orchestrator_output = orch.get("structured_output", {})
    if orchestrator_output.get("prediction"):
        ml_result = orchestrator_output["prediction"]
    agent_trace = orch.get("agent_trace", [])
    agent_thoughts = orch.get("agent_thoughts", [])
    response_provider = orch.get("llm_provider") or llm_service.last_provider
    if is_conversational:
        reasoning_panel = None
        follow_ups = _conversational_follow_ups(user_message, has_equipment=bool(request.equipment_id))
        llm_service.last_provider = response_provider
    else:
        reasoning_panel = orch.get("reasoning_panel") or build_reasoning_panel(
            agent_thoughts=agent_thoughts,
            agent_trace=agent_trace,
            citations=citations_raw,
            query_intent=query_intent,
            llm_provider=llm_service.last_provider,
            structured_output=orchestrator_output,
        ).model_dump()
        follow_ups = await _generate_agentic_follow_ups(
            user_message=user_message,
            assistant_response=response_text,
            query_intent=query_intent,
            equipment_context=equipment_context,
            sensor_reading=sensor_reading,
            history=history,
            structured_output=orchestrator_output,
        )
        llm_service.last_provider = response_provider
    agent_type = _classify_agent_type(user_message)

    if is_conversational:
        structured_output = dict(orchestrator_output)
        structured_output["chat_style"] = "conversational"
    else:
        structured_output = _build_structured_output(
            ml_result, equipment_context, spare_context, citations_raw, response_text, orchestrator_output
        )
        if orchestrator_output.get("explainability"):
            structured_output["explainability"] = orchestrator_output["explainability"]
        structured_output["sensor_snapshot"] = sensor_reading
        structured_output["operational_context"] = operational_context

    db.add(
        ConversationMessage(
            conversation_id=conv.id,
            role="assistant",
            content=response_text,
            metadata_json={
                "agent_trace": agent_trace,
                "agent_thoughts": agent_thoughts,
                "reasoning_panel": reasoning_panel,
                "structured_output": structured_output,
                "llm_provider": llm_service.last_provider,
                "follow_up_suggestions": follow_ups,
                "chat_style": "conversational" if is_conversational else "maintenance",
            },
        )
    )
    await db.flush()

    assistant_row = await db.scalar(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conv.id, ConversationMessage.role == "assistant")
        .order_by(desc(ConversationMessage.created_at))
        .limit(1)
    )

    conv.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "conversation_id": conv.id,
        "message": response_text,
        "user_message_id": user_row.id,
        "assistant_message_id": assistant_row.id if assistant_row else None,
        "agent_trace": agent_trace,
        "agent_thoughts": agent_thoughts,
        "reasoning_panel": reasoning_panel,
        "llm_provider": response_provider,
        "agent_type": agent_type,
        "follow_up_suggestions": follow_ups,
        "citations": citations_raw,
        "structured_output": structured_output,
    }


async def run_diagnosis(db: AsyncSession, request: DiagnosisRequest) -> DiagnosisResponse:
    equipment = await get_equipment(db, request.equipment_id)
    if not equipment:
        raise ValueError("Equipment not found")

    _, sensor_reading, spare_context = await _build_context(db, request.equipment_id)
    query = f"{request.symptoms} {' '.join(request.fault_codes)} {request.incident_description or ''}"
    operational_context = await load_operational_context(db, request.equipment_id)
    feedback_influence = await _load_feedback_influence(db, request.equipment_id)
    result = await get_orchestrator().run(
        query=query,
        query_intent="diagnosis",
        page_context="Equipment Diagnosis",
        equipment_context={
            "id": equipment.id,
            "equipment_code": equipment.equipment_code,
            "name": equipment.name,
            "equipment_type": equipment.equipment_type,
            "criticality": equipment.criticality,
            "location": equipment.location,
            "downtime_cost": (equipment.metadata_json or {}).get("downtime_cost", 50000),
        },
        sensor_reading=sensor_reading,
        spare_context=spare_context,
        operational_context=operational_context,
        feedback_hints=feedback_influence.get("hints", []),
        feedback_scoring=feedback_influence,
    )
    structured = result["structured_output"]
    diagnosis = structured.get("diagnosis", {})
    risk = structured.get("risk_assessment", {}).get("risk_level", "medium")
    if hasattr(risk, "value"):
        risk = risk.value

    ai_summary = (result.get("message") or "").strip()
    follow_ups = [m.strip() for m in re.findall(r"^->\s*(.+)$", ai_summary, re.MULTILINE)][:3]
    if follow_ups:
        ai_summary = re.sub(r"\n->\s*.+$", "", ai_summary, flags=re.MULTILINE).strip()

    await emit_logbook_event(
        db,
        event=LogbookEventType.DIAGNOSIS_COMPLETED,
        equipment_id=equipment.id,
        title=f"Diagnosis — {equipment.equipment_code}",
        description=result["message"][:1500],
        observed_by="Diagnostic Agent",
        source=LogbookEventSource.DIAGNOSIS,
        metadata={"risk_level": risk, "query_intent": "diagnosis"},
    )

    plan = structured.get("maintenance_plan") or {}
    prediction = structured.get("prediction") or {}
    risk_assessment = structured.get("risk_assessment") or {}
    profile = spare_procurement_profile(spare_context)
    rul_h = prediction.get("remaining_useful_life_hours")
    if rul_h is None:
        rul_h = sensor_reading.get("rul_hours")
    proc_risk = risk_engine.compute(
        criticality=equipment.criticality,
        failure_probability=float(prediction.get("failure_probability") or 0.5),
        downtime_cost=float((equipment.metadata_json or {}).get("downtime_cost", 50000)),
        spare_availability=profile["spare_stock"],
        lead_time_days=profile["lead_time_days"],
        rul_hours=float(rul_h) if rul_h is not None else None,
        reorder_level=profile["reorder_level"],
    )
    final_risk = proc_risk["risk_level"]
    if hasattr(final_risk, "value"):
        final_risk = final_risk.value
    else:
        final_risk = str(final_risk)

    reasoning_panel = result.get("reasoning_panel") or build_reasoning_panel(
        agent_thoughts=result.get("agent_thoughts", []),
        agent_trace=result.get("agent_trace", []),
        citations=result["citations"],
        query_intent="diagnosis",
        llm_provider=llm_service.last_provider,
        structured_output=structured,
    ).model_dump()
    return DiagnosisResponse(
        equipment_id=equipment.id,
        equipment_code=equipment.equipment_code,
        probable_causes=diagnosis.get("probable_causes", []),
        root_cause_analysis=diagnosis.get("root_cause_analysis", ai_summary[:500]),
        ai_summary=ai_summary,
        confidence_score=float(diagnosis.get("confidence_score", 0.7)),
        risk_level=str(final_risk),
        remaining_useful_life_hours=prediction.get("remaining_useful_life_hours"),
        failure_probability=prediction.get("failure_probability"),
        immediate_actions=plan.get("immediate_actions", []),
        short_term_actions=plan.get("short_term_actions", []),
        long_term_actions=plan.get("long_term_actions", []),
        monitoring_plan=plan.get("monitoring_plan"),
        spare_stock=proc_risk["spare_stock"],
        lead_time_days=proc_risk["lead_time_days"],
        procurement_risk=proc_risk["procurement_risk"],
        business_impact_inr=proc_risk["business_impact_inr"],
        risk_escalated=proc_risk["escalated"],
        escalation_reason=proc_risk["escalation_reason"],
        critical_spare_part=profile["critical_part_number"],
        citations=result["citations"],
        agent_thoughts=result.get("agent_thoughts", []),
        agent_trace=result.get("agent_trace", []),
        reasoning_panel=reasoning_panel,
        follow_up_suggestions=follow_ups,
        llm_provider=llm_service.last_provider,
    )
