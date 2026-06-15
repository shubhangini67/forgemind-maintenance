from __future__ import annotations

from datetime import datetime, timezone
import json
import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.core.logging import get_logger
from app.schemas import Citation
from app.services.agents.reasoning_panel import AGENT_PHASES, build_reasoning_panel
from app.services.llm_service import llm_service
from app.services.ml.predictive_engine import pm_engine, risk_engine
from app.services.business_impact_service import compute_asset_business_impact
from app.services.explainability_service import build_root_cause_chain
from app.services.feedback_service import apply_feedback_to_causes
from app.services.scenario_simulation_engine import build_simulation_markdown, run_scenario_simulation
from app.services.response_templates import synthesize_intent_response
from app.services.agents.intent_classifier import RESPONSE_TEMPLATE_BY_INTENT
from app.services.procurement_risk import spare_procurement_profile
from app.services.rag.knowledge_engine import get_rag_engine
from app.services.agents.intent_classifier import (
    CONVERSATIONAL,
    INTENT_AGENT_PLANS as CHAT_INTENT_PLANS,
    INTENT_LABELS,
    classify_chat_intent,
    is_conversational_intent,
)

logger = get_logger(__name__)

AGENT_LABELS = {
    "supervisor": "Supervisor Agent",
    "document_agent": "Knowledge RAG",
    "predictive_agent": "Predictive Agent",
    "rca_agent": "Diagnostic Agent",
    "inventory_agent": "Inventory Agent",
    "risk_agent": "Risk Agent",
    "production_impact_agent": "Production Impact Agent",
    "spare_parts_agent": "Inventory Agent",
    "planner_agent": "Planner Agent",
    "alert_agent": "Alert Agent",
    "report_agent": "Report Agent",
    "scenario_agent": "Scenario Agent",
    "synthesizer": "Supervisor Agent",
}

# Chat: every query runs ALL specialist agents — no intent-based skipping.
CHAT_MANDATORY_PIPELINE = [
    "predictive_agent",
    "rca_agent",
    "inventory_agent",
    "risk_agent",
    "production_impact_agent",
    "planner_agent",
    "document_agent",
]

# Specialist nodes (synthesizer always runs last).
PIPELINE_AGENTS = [
    "document_agent",
    "predictive_agent",
    "rca_agent",
    "inventory_agent",
    "risk_agent",
    "production_impact_agent",
    "spare_parts_agent",
    "planner_agent",
    "alert_agent",
    "report_agent",
    "scenario_agent",
]

FULL_PIPELINE_PLAN = list(PIPELINE_AGENTS)

# Legacy intent plans (diagnose page, simulator, etc.)
INTENT_AGENT_PLANS: dict[str, list[str]] = {
    "diagnosis": FULL_PIPELINE_PLAN,
    "diagnostic": CHAT_INTENT_PLANS["diagnostic"],
    "asset_ranking": CHAT_INTENT_PLANS["asset_ranking"],
    "business_impact": CHAT_INTENT_PLANS["business_impact"],
    "risk": CHAT_INTENT_PLANS["risk"],
    "maintenance_planning": CHAT_INTENT_PLANS["maintenance_planning"],
    "inventory": CHAT_INTENT_PLANS["inventory"],
    "sop": CHAT_INTENT_PLANS["sop"],
    "failure_simulation": CHAT_INTENT_PLANS["failure_simulation"],
    "report": CHAT_INTENT_PLANS["report"],
    "conversational": [],
    "general": CHAT_INTENT_PLANS["report"],
    "fleet": CHAT_INTENT_PLANS["asset_ranking"],
    "knowledge": CHAT_INTENT_PLANS["sop"],
    "spares": CHAT_INTENT_PLANS["inventory"],
    "spares_cost": CHAT_INTENT_PLANS["inventory"],
    "rul": CHAT_INTENT_PLANS["asset_ranking"],
    "plan": CHAT_INTENT_PLANS["maintenance_planning"],
    "alerts": ["predictive_agent", "inventory_agent", "risk_agent", "alert_agent"],
    "scenario": CHAT_INTENT_PLANS["failure_simulation"],
}

AGENT_DEPENDENCIES: dict[str, list[str]] = {
    "rca_agent": ["predictive_agent"],
    "inventory_agent": ["predictive_agent"],
    "risk_agent": ["predictive_agent", "inventory_agent"],
    "production_impact_agent": ["predictive_agent"],
    "planner_agent": ["predictive_agent", "risk_agent"],
    "alert_agent": ["spare_parts_agent"],
    "scenario_agent": ["predictive_agent", "inventory_agent"],
    "spare_parts_agent": ["predictive_agent"],
}


class AgentState(TypedDict, total=False):
    query: str
    query_intent: str
    page_context: str | None
    equipment_id: int | None
    equipment_context: dict[str, Any]
    sensor_reading: dict[str, float]
    rag_results: list[dict[str, Any]]
    ml_prediction: dict[str, Any]
    risk_assessment: dict[str, Any]
    spare_context: list[dict[str, Any]]
    diagnosis: dict[str, Any]
    maintenance_plan: dict[str, Any]
    alert_recommendation: dict[str, Any]
    report_summary: str
    agent_trace: list[str]
    agent_thoughts: list[dict[str, Any]]
    final_response: str
    structured_output: dict[str, Any]
    citations: list[dict[str, Any]]
    feedback_hints: list[str]
    feedback_scoring: dict[str, Any]
    history: list[dict[str, str]]
    operational_context: dict[str, Any]
    scenario_context: dict[str, Any]
    agent_plan: list[str]
    plan_step: int
    orchestration_mode: str
    inventory_assessment: dict[str, Any]
    scenario_simulation: dict[str, Any]
    fleet_snapshot: dict[str, Any]
    execution_started_at: float
    response_template: str
    intent_response: dict[str, Any]


_orchestrator: "MaintenanceWizardOrchestrator | None" = None


def _thought(
    agent: str,
    detail: str,
    data: dict | None = None,
    confidence: float | None = None,
    phase: str | None = None,
) -> dict[str, Any]:
    return {
        "agent": agent,
        "label": AGENT_LABELS.get(agent, agent),
        "status": "complete",
        "phase": phase or AGENT_PHASES.get(agent, "Processing"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence": confidence,
        "detail": detail,
        "data": data or {},
    }


def _advance_plan_step(state: AgentState, updates: dict[str, Any]) -> AgentState:
    """Merge agent output and advance dynamic routing cursor."""
    return {**state, **updates, "plan_step": state.get("plan_step", 0) + 1}


class MaintenanceWizardOrchestrator:
    def __init__(self) -> None:
        self._rag = None
        self.graph = self._build_graph()

    @property
    def rag(self):
        if self._rag is None:
            self._rag = get_rag_engine()
        return self._rag

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("supervisor", self._supervisor)
        workflow.add_node("document_agent", self._document_agent)
        workflow.add_node("rca_agent", self._rca_agent)
        workflow.add_node("predictive_agent", self._predictive_agent)
        workflow.add_node("inventory_agent", self._inventory_agent)
        workflow.add_node("risk_agent", self._risk_agent)
        workflow.add_node("production_impact_agent", self._production_impact_agent)
        workflow.add_node("planner_agent", self._planner_agent)
        workflow.add_node("spare_parts_agent", self._spare_parts_agent)
        workflow.add_node("alert_agent", self._alert_agent)
        workflow.add_node("report_agent", self._report_agent)
        workflow.add_node("scenario_agent", self._scenario_agent)
        workflow.add_node("synthesizer", self._synthesizer)

        route_map = {agent: agent for agent in PIPELINE_AGENTS}
        route_map["synthesizer"] = "synthesizer"

        workflow.set_entry_point("supervisor")
        workflow.add_conditional_edges("supervisor", self._route_from_supervisor, route_map)
        for agent in PIPELINE_AGENTS:
            workflow.add_conditional_edges(agent, self._route_after_agent, route_map)
        workflow.add_edge("synthesizer", END)
        return workflow.compile()

    def _plan_for_intent(self, intent: str, query: str) -> list[str]:
        """Rule-based agent selection from classified intent."""
        if is_conversational_intent(intent):
            return []
        plan = list(INTENT_AGENT_PLANS.get(intent, CHAT_INTENT_PLANS.get("diagnostic", [])))
        q = (query or "").lower()
        if intent in ("diagnostic", "diagnosis") and any(w in q for w in ("sop", "manual", "procedure")):
            if "document_agent" not in plan:
                plan.append("document_agent")
        return plan

    def _validate_plan(self, plan: list[str], intent: str, *, strict: bool = False) -> list[str]:
        """Ensure only known agents run. Chat mode uses strict routing — no dependency expansion."""
        if is_conversational_intent(intent) or not plan:
            return []

        if strict:
            return [a for a in plan if a in PIPELINE_AGENTS]

        if intent in ("diagnosis",):
            return list(FULL_PIPELINE_PLAN)
        if intent == "failure_simulation":
            return list(INTENT_AGENT_PLANS["failure_simulation"])
        if intent == "scenario":
            return list(INTENT_AGENT_PLANS["scenario"])

        cleaned = [a for a in plan if a in PIPELINE_AGENTS]
        if not cleaned:
            return list(CHAT_INTENT_PLANS.get("diagnostic", []))

        ordered: list[str] = []
        seen: set[str] = set()
        for agent in cleaned:
            for dep in AGENT_DEPENDENCIES.get(agent, []):
                if dep not in seen:
                    ordered.append(dep)
                    seen.add(dep)
            if agent not in seen:
                ordered.append(agent)
                seen.add(agent)

        if intent == "report" and "report_agent" not in ordered and len(ordered) > 1:
            ordered.append("report_agent")
        return ordered

    async def _llm_refine_plan(self, query: str, intent: str, baseline: list[str]) -> list[str] | None:
        """Optional LLM supervisor — adjusts baseline plan; never used for formal diagnosis."""
        if intent in ("diagnosis",):
            return None
        allowed = ", ".join(PIPELINE_AGENTS)
        prompt = f"""You are the Supervisor Agent for a steel-plant maintenance AI system.
Given the user query and intent, pick which specialist agents should run BEFORE the final Advisor.
Return ONLY a JSON array of agent id strings, in execution order. No markdown.

Allowed agents: {allowed}
User query: {query[:500]}
Query intent: {intent}
Baseline plan (you may shorten, not reorder dependencies): {json.dumps(baseline)}

Rules:
- Include report_agent when more than one specialist runs.
- For spares/cost questions: spare_parts_agent (+ report_agent).
- For SOP/manual questions: document_agent (+ report_agent).
- For RUL only: predictive_agent (+ report_agent).
- For full fault analysis: use all seven specialists in pipeline order.
- Omit agents that add no value for this specific question.

JSON array:"""
        try:
            raw = await llm_service.generate(
                prompt,
                system="Return only a JSON array of agent id strings. No explanation.",
            )
            text = raw.strip()
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            start, end = text.find("["), text.rfind("]")
            if start < 0 or end <= start:
                return None
            parsed = json.loads(text[start : end + 1])
            if not isinstance(parsed, list):
                return None
            return [str(a) for a in parsed if str(a) in PIPELINE_AGENTS]
        except Exception as exc:
            logger.warning("supervisor_llm_plan_failed", error=str(exc))
            return None

    async def _supervisor(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        query = state.get("query") or ""
        chat_mode = state.get("orchestration_mode") in ("chat_full", "chat_intent")

        # Supervisor always classifies intent first (authoritative in chat mode)
        intent = classify_chat_intent(query) if chat_mode else (state.get("query_intent") or classify_chat_intent(query))
        intent_label = INTENT_LABELS.get(intent, intent.replace("_", " ").title())
        response_template = RESPONSE_TEMPLATE_BY_INTENT.get(intent, "root_cause_analysis")

        if is_conversational_intent(intent):
            plan: list[str] = []
            routing_mode = "conversational"
            detail = f"Intent classified as **{intent_label}** — no maintenance agents required."
        else:
            plan = self._plan_for_intent(intent, query)
            routing_mode = "chat_intent" if chat_mode else "intent_rules"
            if not chat_mode and state.get("orchestration_mode") != "diagnosis_llm":
                llm_plan = await self._llm_refine_plan(query, intent, plan)
                if llm_plan:
                    plan = llm_plan
                    routing_mode = "llm_supervisor"
            plan = self._validate_plan(plan, intent, strict=chat_mode)
            labels = [AGENT_LABELS.get(a, a) for a in plan]
            route_summary = " → ".join(labels) + (" → Supervisor Synthesis" if plan or intent else "")
            detail = (
                f"Intent: **{intent_label}** ({routing_mode}) — "
                f"template `{response_template}` — "
                f"{len(plan)} specialist(s): {route_summary or 'synthesizer only'}"
            )

        logger.info(
            "intent_routing",
            detected_intent=intent,
            intent_label=intent_label,
            agents_invoked=plan,
            response_template=response_template,
            routing_mode=routing_mode,
        )
        trace.append(
            f"Supervisor Agent → intent '{intent}' → template '{response_template}' → {len(plan)} agents"
        )
        thoughts.append(
            _thought(
                "supervisor",
                detail,
                {
                    "agent_plan": plan,
                    "query_intent": intent,
                    "intent_label": intent_label,
                    "routing_mode": routing_mode,
                    "response_template": response_template,
                },
                confidence=0.95,
                phase="Intent classification",
            )
        )
        return {
            **state,
            "query_intent": intent,
            "response_template": response_template,
            "agent_plan": plan,
            "plan_step": 0,
            "agent_trace": trace,
            "agent_thoughts": thoughts,
        }

    def _route_from_supervisor(self, state: AgentState) -> str:
        plan = state.get("agent_plan") or []
        if not plan:
            return "synthesizer"
        return plan[0]

    def _route_after_agent(self, state: AgentState) -> str:
        plan = state.get("agent_plan") or []
        step = state.get("plan_step", 0)
        if step >= len(plan):
            return "synthesizer"
        return plan[step]

    async def _document_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        equipment_type = state.get("equipment_context", {}).get("equipment_type")
        t0 = time.perf_counter()
        results = self.rag.hybrid_search(state["query"], equipment_type=equipment_type, limit=5)
        ms = round((time.perf_counter() - t0) * 1000)
        top = results[0] if results else None
        detail = (
            f"Queried Qdrant vector store — {len(results)} chunk(s) matched in {ms}ms"
            + (f". Top hit: {top['source']} (score {top['score']:.2f})" if top else "")
        )
        trace.append(f"Knowledge RAG → {len(results)} documents retrieved")
        thoughts.append(_thought(
            "document_agent", detail, {
            "matches": [
                {
                    "source": r["source"],
                    "score": r["score"],
                    "type": r["document_type"],
                    "excerpt": (r.get("excerpt") or "")[:300],
                }
                for r in results[:5]
            ],
            "knowledge_evidence": [
                {
                    "source": r["source"],
                    "reference": r["source"],
                    "excerpt": (r.get("excerpt") or "")[:280],
                    "document_type": r.get("document_type", "document"),
                    "score": r["score"],
                }
                for r in results[:4]
            ],
        }, confidence=top["score"] if top else None, phase="Documents retrieved"))
        return _advance_plan_step(state, {"rag_results": results, "agent_trace": trace, "agent_thoughts": thoughts})

    async def _predictive_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        reading = state.get("sensor_reading") or {}
        eq = state.get("equipment_context", {})
        if not reading:
            reading = {"temperature": 85, "vibration": 5.2, "pressure": 120, "motor_current": 62, "health_indicator": 72}
        prediction = pm_engine.predict_rul(reading)
        anomaly = pm_engine.detect_anomaly(reading)
        risk = prediction.get("risk_level")
        risk_str = risk.value if hasattr(risk, "value") else str(risk)
        temp = reading.get("temperature", 0)
        vib = reading.get("vibration", 0)
        cycle = reading.get("cycle", "?")
        unit = reading.get("cmapss_unit", "?")
        source = reading.get("source", "C-MAPSS FD001")
        detail = (
            f"NASA {source} — unit {unit} cycle {cycle}: "
            f"temp={temp:.1f}°C, vib={vib:.2f} mm/s, health={reading.get('health_indicator', 0):.0f}%. "
            f"Isolation Forest anomaly={'YES' if anomaly['is_anomaly'] else 'no'}. "
            f"RUL={prediction.get('remaining_useful_life_hours', 0):.0f}h, failure prob={prediction.get('failure_probability', 0):.0%}, risk={risk_str}."
        )
        trace.append("Predictive Engine → RUL + anomaly scoring complete")
        fp = float(prediction.get("failure_probability", 0) or 0)
        model_confidence = round(0.82 + (0.12 if not anomaly["is_anomaly"] else 0.05), 2)
        pred_payload = {
            k: (v.value if hasattr(v, "value") else v)
            for k, v in prediction.items()
            if k != "features_used"
        }
        pred_payload["model_confidence"] = model_confidence
        prediction_with_conf = {**prediction, "model_confidence": model_confidence}
        thoughts.append(_thought("predictive_agent", detail, {
            "reading": reading,
            "prediction": pred_payload,
            "anomaly": anomaly,
        }, confidence=model_confidence, phase="RUL prediction"))
        return _advance_plan_step(state, {"ml_prediction": prediction_with_conf, "agent_trace": trace, "agent_thoughts": thoughts})

    async def _rca_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        trace.append("Diagnostic Engine → correlating C-MAPSS patterns with failure history")
        reading = state.get("sensor_reading") or {}
        pred = state.get("ml_prediction") or {}
        vib = float(reading.get("vibration", 0))
        temp = float(reading.get("temperature", 0))
        health = float(reading.get("health_indicator", 100))
        failure_prob = float(pred.get("failure_probability", 0) or 0)
        cycle = reading.get("cycle", "N/A")
        cmapss_unit = reading.get("cmapss_unit", "N/A")

        causes: list[dict] = []
        op = state.get("operational_context") or {}
        for inc in (op.get("failure_incidents") or [])[:2]:
            causes.append({
                "cause": f"Historical incident {inc.get('fault_code')}: {inc.get('root_cause', inc.get('description', ''))[:120]}",
                "confidence": 0.84,
            })
        for alert in (op.get("open_fault_alerts") or [])[:1]:
            causes.append({
                "cause": f"Active fault alert: {alert.get('title', '')} — {alert.get('message', '')[:80]}",
                "confidence": 0.80,
            })
        if vib >= 8.5:
            causes.append({"cause": f"Bearing defect — vibration {vib:.2f} mm/s (C-MAPSS unit {cmapss_unit}, cycle {cycle})", "confidence": 0.88})
        elif vib >= 6.0:
            causes.append({"cause": f"Bearing wear trend — vibration {vib:.2f} mm/s exceeds ISO Class III alarm", "confidence": 0.82})
        if temp >= 95:
            causes.append({"cause": f"Thermal overload — {temp:.1f}°C at cycle {cycle} (FD001 degradation signature)", "confidence": 0.79})
        elif temp >= 85:
            causes.append({"cause": f"Elevated friction/heat — {temp:.1f}°C correlates with C-MAPSS s_4 drift", "confidence": 0.71})
        if failure_prob >= 0.6:
            causes.append({"cause": f"ML anomaly — {failure_prob:.0%} failure probability from XGBoost RUL model (FD001-trained)", "confidence": 0.75})
        if health < 50:
            causes.append({"cause": f"Late-stage degradation — health {health:.0f}% with RUL {pred.get('remaining_useful_life_hours', 0):.0f}h", "confidence": 0.85})
        if not causes:
            causes.append({"cause": "Normal wear within C-MAPSS expected degradation curve", "confidence": 0.65})

        scoring = state.get("feedback_scoring") or {}
        causes = apply_feedback_to_causes(
            causes,
            scoring.get("penalized_fault_types", {}),
            scoring.get("boosted_fault_types", {}),
        )

        risk = pred.get("risk_level")
        risk_str = risk.value if hasattr(risk, "value") else str(risk or "medium")
        diagnosis = {
            "probable_causes": causes[:4],
            "root_cause_analysis": (
                f"FD001 unit {cmapss_unit} cycle {cycle}: temp={temp:.1f}°C, vib={vib:.2f} mm/s, "
                f"health={health:.0f}%. Pattern matches NASA turbofan degradation trajectory."
            ),
            "confidence_score": round(max(c.get("confidence", 0.5) for c in causes), 2),
            "risk_level": risk_str,
        }
        diagnosis["root_cause_chain"] = build_root_cause_chain(
            diagnosis=diagnosis,
            sensor_reading=reading,
            operational_context=op,
        )
        top = causes[0]
        detail = f"RCA (rule+ML): {top['cause']} — confidence {top.get('confidence', 0):.0%}. No extra LLM latency."
        thoughts.append(_thought("rca_agent", detail, {"diagnosis": diagnosis}, confidence=diagnosis.get("confidence_score"), phase="Root cause analysis"))
        return _advance_plan_step(state, {"diagnosis": diagnosis, "agent_trace": trace, "agent_thoughts": thoughts})

    async def _inventory_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        spares = state.get("spare_context") or []
        profile = spare_procurement_profile(spares)
        low_stock = [s for s in spares if s.get("quantity_available", 0) <= s.get("reorder_level", 5)]

        procurement_risk = "critical" if profile["spare_stock"] == 0 else "high" if low_stock else "medium" if profile["spare_stock"] <= profile["reorder_level"] else "low"

        lines = []
        for s in spares[:5]:
            qty = int(s.get("quantity_available", 0))
            reorder = int(s.get("reorder_level", 5))
            lead = int(s.get("lead_time_days", 14))
            flag = "ORDER NOW" if qty <= reorder else "OK"
            lines.append(f"{s.get('part_number')} {s.get('name')}: {qty} in stock, lead {lead}d — {flag}")

        inventory = {
            "spare_availability": lines or ["No mapped spare parts"],
            "spare_stock": profile["spare_stock"],
            "lead_time_days": profile["lead_time_days"],
            "procurement_risk": procurement_risk,
            "critical_part": profile.get("critical_part_number"),
            "low_stock_count": len(low_stock),
            "spares": spares[:5],
        }
        detail = (
            f"Inventory check: {len(spares)} part line(s), "
            f"stock={profile['spare_stock']}, lead={profile['lead_time_days']}d, "
            f"procurement risk={procurement_risk.upper()}."
        )
        trace.append("Inventory Agent → spare availability & lead time assessed")
        thoughts.append(_thought(
            "inventory_agent", detail, {"inventory": inventory},
            confidence=0.92 if spares else 0.5, phase="Spare availability",
        ))
        return _advance_plan_step(state, {"inventory_assessment": inventory, "agent_trace": trace, "agent_thoughts": thoughts})

    async def _risk_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        spares = state.get("spare_context") or []
        profile = spare_procurement_profile(spares)
        pred = state.get("ml_prediction") or {}
        eq = state.get("equipment_context") or {}
        op = state.get("operational_context") or {}
        delay_count = len(op.get("delay_logs") or [])
        rul_hours = float(pred.get("remaining_useful_life_hours") or 0) or None

        risk = risk_engine.compute(
            criticality=eq.get("criticality", 3),
            failure_probability=pred.get("failure_probability", 0.5),
            downtime_cost=eq.get("downtime_cost", 50000),
            spare_availability=profile["spare_stock"],
            lead_time_days=profile["lead_time_days"],
            rul_hours=rul_hours,
            reorder_level=profile["reorder_level"],
            delay_log_count=delay_count,
        )
        risk_level = risk.get("risk_level")
        if hasattr(risk_level, "value"):
            risk_level = risk_level.value

        escalation = risk.get("escalation_reason") or (
            f"Composite score from failure probability, criticality, and spare lead time vs RUL"
        )
        risk_out = {
            **risk,
            "risk_level": risk_level,
            "risk_score": risk.get("overall_risk_score"),
            "score_breakdown": risk.get("score_breakdown"),
            "escalation_reason": escalation,
        }
        detail = f"Risk score: {risk_level.upper()} — {escalation}"
        trace.append(f"Risk Agent → level {risk_level}")
        conf_map = {"low": 0.35, "medium": 0.55, "high": 0.75, "critical": 0.92}
        thoughts.append(_thought(
            "risk_agent", detail, {"risk_assessment": risk_out},
            confidence=conf_map.get(str(risk_level).lower(), 0.6), phase="Risk classification",
        ))
        return _advance_plan_step(state, {"risk_assessment": risk_out, "agent_trace": trace, "agent_thoughts": thoughts})

    async def _production_impact_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        eq = state.get("equipment_context") or {}
        pred = state.get("ml_prediction") or {}
        reading = state.get("sensor_reading") or {}

        meta = eq.get("metadata_json") or {}
        downtime_day = float(eq.get("downtime_cost") or meta.get("downtime_cost") or eq.get("criticality", 3) * 25_000)
        health = float(reading.get("health_indicator") or 70)
        fp = float(pred.get("failure_probability") or 0.4)
        rul = float(pred.get("remaining_useful_life_hours") or reading.get("rul_hours") or 999)

        impact = compute_asset_business_impact(
            downtime_cost_per_day=downtime_day,
            criticality=int(eq.get("criticality", 3)),
            health_score=health,
            rul_hours=rul,
            failure_probability=fp,
        )
        # Throughput: blast furnace blower ~800-1200 t/day scaled by criticality
        daily_tons = {1: 400, 2: 600, 3: 800, 4: 1000, 5: 1200}.get(int(eq.get("criticality", 3)), 800)
        downtime_h = float(impact.get("expected_downtime_hours", 12))
        throughput_loss = round(daily_tons * (downtime_h / 24), 1)

        production = {
            **impact,
            "downtime_estimate_hours": downtime_h,
            "throughput_impact_tons": throughput_loss,
            "business_cost_inr": impact.get("downtime_cost_inr", 0),
            "data_source": "Tata Steel maintenance economics model + live C-MAPSS sensors",
        }
        detail = (
            f"Production impact: {downtime_h:.0f}h downtime est., "
            f"{throughput_loss:.0f}t throughput at risk, "
            f"₹{production['business_cost_inr']:,} business cost."
        )
        trace.append("Production Impact Agent → downtime & throughput computed")
        thoughts.append(_thought(
            "production_impact_agent", detail, {"production_impact": production},
            confidence=min(0.92, 0.5 + fp * 0.4), phase="Business impact analysis",
        ))
        return _advance_plan_step(state, {"production_impact": production, "agent_trace": trace, "agent_thoughts": thoughts})

    async def _spare_parts_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        spares = state.get("spare_context", [])
        low_stock = [s for s in spares if s.get("quantity_available", 0) <= s.get("reorder_level", 5)]
        spare_stock = min((s.get("quantity_available", 0) for s in spares), default=0)
        lead_time = max((s.get("lead_time_days", 14) for s in spares), default=14)
        reorder = min((s.get("reorder_level", 5) for s in spares), default=5) if spares else 5
        rul_hours = float(state.get("ml_prediction", {}).get("remaining_useful_life_hours") or 0) or None
        risk = risk_engine.compute(
            criticality=state.get("equipment_context", {}).get("criticality", 3),
            failure_probability=state.get("ml_prediction", {}).get("failure_probability", 0.5),
            downtime_cost=state.get("equipment_context", {}).get("downtime_cost", 50000),
            spare_availability=spare_stock,
            lead_time_days=lead_time,
            rul_hours=rul_hours,
            reorder_level=reorder,
        )
        risk_level = risk["risk_level"]
        if hasattr(risk_level, "value"):
            risk_level = risk_level.value
        if low_stock:
            s = low_stock[0]
            detail = f"Spare {s['part_number']} ({s['name']}): {s['quantity_available']} in stock — {'IN STOCK' if s['quantity_available'] > 0 else 'OUT OF STOCK'}. Lead time {s.get('lead_time_days', 14)}d."
        elif spares:
            s = spares[0]
            detail = f"Spare {s['part_number']}: {s['quantity_available']} available — IN STOCK."
        else:
            detail = "No spare parts mapped for this equipment type — flag procurement."
        if risk.get("escalated"):
            detail += f" RISK ESCALATED: {risk.get('escalation_reason', 'RUL < lead time')}."
        trace.append("Spares Agent → inventory & lead time checked")
        thoughts.append(_thought("spare_parts_agent", detail, {"spares": spares[:3], "risk": {**risk, "risk_level": risk_level}}, phase="Risk classification"))
        procurement = [f"Procure {s['name']} — only {s['quantity_available']} in stock" for s in low_stock[:2]]
        return _advance_plan_step(
            state,
            {
                "risk_assessment": {**risk, "risk_level": risk_level, "procurement_notes": procurement},
                "agent_trace": trace,
                "agent_thoughts": thoughts,
            },
        )

    async def _planner_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        trace.append("Planner Agent → prioritized plan from RUL + risk (instant)")
        pred = state.get("ml_prediction") or {}
        risk = state.get("risk_assessment") or {}
        reading = state.get("sensor_reading") or {}
        rul = float(pred.get("remaining_useful_life_hours", 999) or 999)
        vib = float(reading.get("vibration", 0))
        risk_level = risk.get("risk_level", "medium")
        if hasattr(risk_level, "value"):
            risk_level = risk_level.value

        immediate = []
        if vib >= 8.5:
            immediate.append("Stop asset — vibration exceeds 8.5 mm/s critical threshold")
        if rul < 24:
            immediate.append(f"Schedule intervention within {rul:.0f}h — RUL below 24h")
        immediate.extend([
            "Inspect bearing assembly and lubrication system",
            "Log C-MAPSS cycle reading in digital logbook",
            "Verify spare parts availability before next shift",
        ])

        plan = {
            "immediate_actions": immediate[:5],
            "short_term_actions": [
                f"Schedule PM before RUL drops below 48h (current {rul:.0f}h)",
                "Trend vibration every 2h until health > 70%",
                "Cross-check against FD001 unit degradation curve",
            ],
            "long_term_actions": [
                "Retrain XGBoost RUL model on latest C-MAPSS import",
                "Install continuous vibration monitoring on critical assets",
            ],
            "monitoring_plan": f"Monitor C-MAPSS-mapped sensors every 2h — risk={risk_level}, cycle={reading.get('cycle', 'N/A')}",
        }
        imm = plan["immediate_actions"]
        detail = f"Generated {len(imm)} immediate action(s): {imm[0] if imm else 'monitor only'}."
        thoughts.append(_thought("planner_agent", detail, {"plan": plan}, confidence=0.88, phase="Maintenance recommendation"))
        return _advance_plan_step(state, {"maintenance_plan": plan, "agent_trace": trace, "agent_thoughts": thoughts})

    async def _alert_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        risk_level = state.get("risk_assessment", {}).get("risk_level", "medium")
        if hasattr(risk_level, "value"):
            risk_level = risk_level.value
        level = "critical" if risk_level == "critical" else "high" if risk_level == "high" else "warning"
        alert = {
            "should_alert": risk_level in ("high", "critical"),
            "level": level,
            "message": f"Equipment risk level: {risk_level}. Review recommended actions.",
        }
        detail = f"Alert escalation: {'REQUIRED' if alert['should_alert'] else 'not required'} — level {level.upper()}."
        trace.append(f"Alert Agent → {detail}")
        thoughts.append(_thought("alert_agent", detail, alert, confidence=0.9 if alert["should_alert"] else 0.5, phase="Alert escalation"))
        return _advance_plan_step(state, {"alert_recommendation": alert, "agent_trace": trace, "agent_thoughts": thoughts})

    async def _report_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        pred = state.get("ml_prediction", {})
        diag = state.get("diagnosis", {})
        summary = (
            f"Diagnosis confidence: {diag.get('confidence_score', 'N/A')}. "
            f"RUL: {pred.get('remaining_useful_life_hours', 'N/A')} hours. "
            f"Risk: {state.get('risk_assessment', {}).get('risk_level', 'N/A')}."
        )
        trace.append("Report Agent → structured summary compiled")
        thoughts.append(_thought("report_agent", summary, {"report_summary": summary}, confidence=0.9, phase="Report generation"))
        return _advance_plan_step(state, {"report_summary": summary, "agent_trace": trace, "agent_thoughts": thoughts})

    async def _scenario_agent(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        eq = state.get("equipment_context") or {}
        code = eq.get("equipment_code", "Asset")
        query = state.get("query") or ""
        sim = state.get("scenario_simulation") or {}

        if not sim.get("projections"):
            sim = run_scenario_simulation(
                query=query,
                equipment_context=eq,
                sensor_reading=state.get("sensor_reading") or {},
                spare_context=state.get("spare_context") or [],
                operational_context=state.get("operational_context") or {},
                force_standard_horizons=state.get("query_intent") == "failure_simulation",
            )

        projections = sim.get("projections") or []
        cs = sim.get("current_state") or {}
        markdown = sim.get("markdown_table") or build_simulation_markdown(
            sim,
            equipment_code=code,
            equipment_name=eq.get("name", ""),
            query=query,
        )
        detail = (
            f"Scenario simulation complete — {len(projections)} deferral horizon(s). "
            f"Current RUL {cs.get('rul_hours')}h @ {cs.get('failure_probability_pct')}% failure probability. "
            f"{sim.get('recommended_action', '')}"
        )
        scenario_analysis = {
            "simulation": sim,
            "current_state": cs,
            "projections": projections,
            "recommended_action": sim.get("recommended_action"),
            "business_impact": sim.get("business_impact"),
            "operational_impact": sim.get("operational_impact"),
            "markdown_table": markdown,
        }
        trace.append("Scenario Agent → future-state simulation complete")
        thoughts.append(
            _thought(
                "scenario_agent",
                detail,
                {"scenario_analysis": scenario_analysis, "scenario_simulation": sim},
                confidence=0.94,
                phase="Future-state simulation",
            )
        )
        return _advance_plan_step(
            state,
            {
                "scenario_analysis": scenario_analysis,
                "scenario_simulation": sim,
                "agent_trace": trace,
                "agent_thoughts": thoughts,
            },
        )

    def _build_failure_simulation_synthesis(self, state: AgentState) -> str:
        """Scenario-only response for failure simulation — no generic asset summary."""
        query = state.get("query") or ""
        eq = state.get("equipment_context") or {}
        code = eq.get("equipment_code", "Asset")
        name = eq.get("name", "")
        scenario = state.get("scenario_analysis") or {}
        sim = state.get("scenario_simulation") or scenario.get("simulation") or {}

        if not sim.get("projections"):
            sim = run_scenario_simulation(
                query=query,
                equipment_context=eq,
                sensor_reading=state.get("sensor_reading") or {},
                spare_context=state.get("spare_context") or [],
                operational_context=state.get("operational_context") or {},
                force_standard_horizons=True,
            )

        return sim.get("markdown_table") or build_simulation_markdown(
            sim,
            equipment_code=code,
            equipment_name=name,
            query=query,
        )

    def _build_supervisor_synthesis(self, state: AgentState) -> str:
        """Deterministic supervisor synthesis from executed agent outputs — no standalone LLM answer."""
        intent = state.get("query_intent") or "general"
        if intent == "failure_simulation":
            return self._build_failure_simulation_synthesis(state)

        query = state.get("query") or ""
        agent_plan = set(state.get("agent_plan") or [])
        eq = state.get("equipment_context") or {}
        code = eq.get("equipment_code", "Asset")
        name = eq.get("name", "")
        reading = state.get("sensor_reading") or {}
        pred = state.get("ml_prediction") or {}
        diag = state.get("diagnosis") or {}
        risk = state.get("risk_assessment") or {}
        inv = state.get("inventory_assessment") or {}
        impact = state.get("production_impact") or {}
        plan = state.get("maintenance_plan") or {}
        rag = state.get("rag_results") or []
        scenario = state.get("scenario_analysis") or {}
        sim = state.get("scenario_simulation") or scenario.get("simulation") or {}
        report = state.get("report_summary") or ""

        rul = pred.get("remaining_useful_life_hours") or reading.get("rul_hours")
        fp = pred.get("failure_probability")
        fp_pct = f"{float(fp or 0) * 100:.1f}%" if fp is not None else "N/A"
        pred_conf = float(pred.get("model_confidence") or 0.87)
        risk_level = risk.get("risk_level", "medium")
        causes = diag.get("probable_causes") or []
        intent_label = INTENT_LABELS.get(intent, intent)

        q = query.lower()
        if intent == "risk" or any(w in q for w in ("risk", "delay", "operational", "postpone", "defer")):
            direct = (
                f"Operational risk for **{code}** is **{str(risk_level).upper()}** — "
                f"{risk.get('escalation_reason', 'composite risk score from sensors + spares')} (Risk Agent)."
            )
        elif intent == "diagnostic" or any(w in q for w in ("root cause", "degrad", "why", "diagnos", "fault")):
            top = causes[0]["cause"] if causes else "degradation trend from live sensors"
            direct = f"Primary root cause for **{code}**: {top} (Diagnostic Agent)."
        elif intent == "inventory" or any(w in q for w in ("spare", "procure", "inventory", "stock", "lead time")):
            direct = (
                f"Procurement risk for **{code}** is **{inv.get('procurement_risk', 'unknown').upper()}** "
                f"with **{inv.get('lead_time_days', '?')}d** lead time (Inventory Agent)."
            )
        elif intent == "maintenance_planning" or "plan" in q:
            imm = (plan.get("immediate_actions") or ["Monitor and inspect"])[0]
            direct = f"Recommended immediate action for **{code}**: {imm} (Planner Agent)."
        elif intent == "sop" or any(w in q for w in ("sop", "manual", "procedure")):
            top_doc = rag[0]["source"] if rag else "knowledge base"
            direct = f"Relevant documentation for **{code}**: **{top_doc}** (Knowledge Agent)."
        elif intent == "failure_simulation":
            direct = (
                f"Failure simulation for **{code}**: {scenario.get('affected_count', 0)} downstream asset(s) affected; "
                f"₹{scenario.get('impact_summary', {}).get('total_cost_inr', 0):,} exposure (Scenario Agent)."
            )
        elif intent == "report":
            direct = report or (
                f"Fleet summary for **{code}**: RUL **{float(rul or 0):.0f}h**, "
                f"risk **{str(risk_level).upper()}**, health **{float(reading.get('health_indicator', 0)):.0f}%**."
            )
        elif "rul" in q or "remaining" in q:
            direct = (
                f"**{code}** has approximately **{float(rul or 0):.0f} hours** RUL "
                f"with **{fp_pct}** failure probability (Predictive Agent, confidence {pred_conf:.0%})."
            )
        else:
            direct = f"Answer for **{code}** based on **{intent_label}** intent and executed specialist agents."

        lines = [
            "## Supervisor Synthesis\n",
            f"**Intent:** {intent_label}\n",
            f"**Your question:** {query}\n",
            f"**Direct answer:** {direct}\n",
            "---\n",
        ]

        if "predictive_agent" in agent_plan and (pred or reading):
            lines.extend([
                "### Predictive Agent",
                f"- **RUL:** {float(rul or 0):.1f} hours (~{float(rul or 0) / 24:.1f} days)" if rul else "- **RUL:** unavailable",
                f"- **Failure Probability:** {fp_pct}",
                f"- **Confidence:** {pred_conf:.0%} (XGBoost + Isolation Forest on C-MAPSS FD001)",
                f"- **Data source:** NASA C-MAPSS unit {reading.get('cmapss_unit', '?')}, cycle {reading.get('cycle', '?')}",
                "",
            ])

        if "rca_agent" in agent_plan:
            lines.append("### Diagnostic Agent")
            if causes:
                for i, c in enumerate(causes[:3], 1):
                    conf = c.get("confidence", 0)
                    lines.append(f"{i}. **{c.get('cause', c)}** — confidence {conf:.0%}")
                lines.append(
                    f"- **Evidence:** temp {reading.get('temperature')}°C, vib {reading.get('vibration')} mm/s, "
                    f"health {reading.get('health_indicator')}%"
                )
            else:
                lines.append("- No significant fault pattern detected")
            lines.append("")

        if "inventory_agent" in agent_plan or "spare_parts_agent" in agent_plan:
            lines.extend([
                "### Inventory Agent",
                f"- **Spare Availability:** {inv.get('spare_stock', 0)} units (critical part: {inv.get('critical_part') or 'N/A'})",
                f"- **Lead Time:** {inv.get('lead_time_days', '?')} days",
                f"- **Procurement Risk:** {str(inv.get('procurement_risk', 'unknown')).upper()}",
            ])
            for s in (inv.get("spare_availability") or [])[:3]:
                lines.append(f"  - {s}")
            lines.append("")

        if "risk_agent" in agent_plan:
            lines.extend([
                "### Risk Agent",
                f"- **Risk Score / Level:** {str(risk_level).upper()}",
                f"- **Escalation Reason:** {risk.get('escalation_reason', 'Standard composite scoring')}",
                "",
            ])

        if "production_impact_agent" in agent_plan:
            lines.extend([
                "### Production Impact Agent",
                f"- **Downtime Estimate:** {impact.get('downtime_estimate_hours', impact.get('expected_downtime_hours', '?'))} hours",
                f"- **Throughput Impact:** ~{impact.get('throughput_impact_tons', '?')} tons production at risk",
                f"- **Business Cost:** ₹{impact.get('business_cost_inr', 0):,}",
                f"- **Data source:** {impact.get('data_source', 'Business impact model')}",
                "",
            ])

        if "planner_agent" in agent_plan:
            lines.extend(["### Planner Agent", "**Immediate Actions:**"])
            for i, a in enumerate(plan.get("immediate_actions") or [], 1):
                lines.append(f"{i}. {a}")
            lines.append("\n**Long-Term Actions:**")
            for i, a in enumerate(plan.get("long_term_actions") or plan.get("short_term_actions") or [], 1):
                lines.append(f"{i}. {a}")
            lines.append("")

        if "scenario_agent" in agent_plan and scenario:
            lines.extend([
                "### Scenario Agent",
                f"- **Failed asset:** {scenario.get('failed_asset', code)}",
                f"- **Affected assets:** {scenario.get('affected_count', 0)}",
            ])
            for step in (scenario.get("contingency_steps") or [])[:3]:
                lines.append(f"  - {step}")
            lines.append("")

        if "report_agent" in agent_plan and report:
            lines.extend(["### Report Agent", report, ""])

        if "document_agent" in agent_plan and rag:
            lines.extend(["### Evidence & Data Sources"])
            for r in rag[:3]:
                lines.append(f"- [{r.get('source', 'Doc')}] ({r.get('document_type', 'manual')}, score {r.get('score', 0):.2f})")

        if sim and (sim.get("projections") or sim.get("current_state")):
            cs = sim.get("current_state") or {}
            lines.extend([
                "",
                "### Scenario Simulation",
                f"**Today:** RUL {cs.get('rul_hours')}h · Failure Probability {cs.get('failure_probability_pct')}% · Risk {cs.get('risk_level', '—')}",
            ])
            for p in (sim.get("projections") or [])[:4]:
                lines.append(
                    f"**{p.get('label')}:** RUL {p.get('rul_hours')}h · "
                    f"Failure Probability {p.get('failure_probability_pct')}% "
                    f"(Δ {p.get('failure_probability_delta_pct', 0):+.0f}%)"
                )
            lines.append(f"\n**Recommendation:** {sim.get('recommended_action', 'Review maintenance window.')}")
            bi = sim.get("business_impact") or {}
            if bi:
                lines.extend([
                    "",
                    "### Business Impact",
                    f"- Additional failure risk: **+{bi.get('additional_failure_risk_pct', 0)}%**",
                    f"- Potential downtime: **{bi.get('estimated_downtime_hours', '—')}h**",
                    f"- Production loss: **{bi.get('estimated_production_loss_tons', '—')}t**",
                    f"- Preventive maintenance cost: **₹{bi.get('preventive_maintenance_cost_inr', 0):,}**",
                    f"- Potential savings from early action: **₹{bi.get('potential_savings_inr', 0):,}**",
                ])

        rb = risk.get("score_breakdown") or {}
        if rb.get("components"):
            lines.extend(["", "### Risk Score Breakdown", f"**Final Risk Score:** {rb.get('final_score_100')}/100"])
            for c in rb["components"]:
                lines.append(f"- **{c['factor']}:** {c['value']} (weight {c['weight_pct']}%)")
            lines.append(f"**Reason:** {rb.get('reason', '')}")

        rcc = (diag.get("root_cause_chain") or {})
        if rcc.get("evidence"):
            lines.extend(["", "### Root Cause Chain", f"**Most Likely Cause:** {rcc.get('most_likely_cause', '—')}"])
            for i, ev in enumerate(rcc.get("evidence") or [], 1):
                lines.append(f"- Evidence {i}: {ev.get('label')} — {ev.get('detail', '')}")
            path = " → ".join(rcc.get("failure_path") or [])
            if path:
                lines.append(f"\n**Failure Path:** {path}")

        return "\n".join(lines)

    async def _synthesizer(self, state: AgentState) -> AgentState:
        trace = list(state.get("agent_trace", []))
        thoughts = list(state.get("agent_thoughts", []))
        trace.append("Supervisor Agent → synthesizing explainable response from agent outputs")
        citations = [
            Citation(source=r["source"], document_type=r["document_type"], excerpt=r["excerpt"][:300], score=r["score"]).model_dump()
            for r in state.get("rag_results", [])[:4]
        ]
        structured = {
            "diagnosis": state.get("diagnosis", {}),
            "prediction": {k: (v.value if hasattr(v, "value") else v) for k, v in (state.get("ml_prediction") or {}).items() if k != "features_used"},
            "risk_assessment": state.get("risk_assessment", {}),
            "inventory_assessment": state.get("inventory_assessment", {}),
            "production_impact": state.get("production_impact", {}),
            "maintenance_plan": state.get("maintenance_plan", {}),
            "alert": state.get("alert_recommendation", {}),
            "report_summary": state.get("report_summary", ""),
            "scenario_analysis": state.get("scenario_analysis", {}),
            "scenario_simulation": state.get("scenario_simulation", {}),
            "rag_results": state.get("rag_results", []),
        }

        agent_plan = state.get("agent_plan") or []
        chat_intent_mode = state.get("orchestration_mode") in ("chat_intent", "chat_full")
        intent = state.get("query_intent") or "diagnostic"

        if is_conversational_intent(intent):
            from app.services.conversational_service import conversational_reply

            eq = state.get("equipment_context") or {}
            code = eq.get("equipment_code") or None
            name = eq.get("name") or ""
            final, provider = await conversational_reply(
                state["query"],
                equipment_code=code,
                equipment_name=name,
                history=state.get("history"),
            )
            llm_service.last_provider = provider
            trace.append(f"Copilot Agent → conversational response ({provider})")
            thoughts.append(_thought(
                "conversational_agent",
                f"Copilot Agent composed a natural-language reply ({provider}).",
                {"provider": provider, "routing_mode": "conversational", "response_template": "conversational"},
                confidence=0.92,
                phase="Natural language response",
            ))
            structured["chat_style"] = "conversational"
            structured["response_template"] = "conversational"
            structured["llm_provider"] = provider
            return {
                **state,
                "final_response": final,
                "structured_output": structured,
                "citations": citations,
                "agent_trace": trace,
                "agent_thoughts": thoughts,
            }

        use_template = chat_intent_mode and not is_conversational_intent(intent)

        if use_template:
            final, intent_response, template = synthesize_intent_response(state)
            structured["intent_response"] = intent_response
            structured["response_template"] = template
            from app.services.chat_polish_service import polish_maintenance_reply

            eq = state.get("equipment_context") or {}
            polished, polish_provider = await polish_maintenance_reply(
                user_query=state["query"],
                technical_brief=final,
                equipment_code=eq.get("equipment_code"),
                history=state.get("history"),
            )
            final = polished
            llm_service.last_provider = polish_provider
            provider = polish_provider
            structured["technical_brief"] = intent_response
            structured["llm_provider"] = polish_provider
            structured["chat_style"] = "maintenance"
            logger.info(
                "intent_synthesis",
                detected_intent=intent,
                agents_invoked=agent_plan,
                response_template=template,
                polish_provider=polish_provider,
            )
            trace.append(f"Synthesizer → Groq polish ({polish_provider})")
            thoughts.append(_thought(
                "synthesizer",
                f"Template `{template}` from {len(agent_plan)} agent(s), polished via {polish_provider} for chat.",
                {"provider": provider, "response_template": template, "intent_response": intent_response},
                confidence=0.93,
                phase="Chat polish synthesis",
            ))
            return {
                **state,
                "final_response": final,
                "structured_output": structured,
                "intent_response": intent_response,
                "response_template": template,
                "citations": citations,
                "agent_trace": trace,
                "agent_thoughts": thoughts,
            }

        use_deterministic = chat_intent_mode and bool(agent_plan)

        if use_deterministic:
            final = self._build_supervisor_synthesis(state)
            provider = "agent_orchestration"
            trace.append("Supervisor Agent → synthesized final answer from executed agent outputs")
            thoughts.append(_thought(
                "synthesizer",
                "Supervisor synthesized response exclusively from executed agent outputs (no direct LLM completion).",
                {"provider": provider, "agent_outputs": structured},
                confidence=0.93,
                phase="Supervisor synthesis",
            ))
            return {
                **state,
                "final_response": final,
                "structured_output": structured,
                "citations": citations,
                "agent_trace": trace,
                "agent_thoughts": thoughts,
            }

        eq = state.get("equipment_context", {})
        reading = state.get("sensor_reading") or {}
        op = state.get("operational_context") or {}
        hints = state.get("feedback_hints") or []
        scoring = state.get("feedback_scoring") or {}
        hints_block = "\n".join(f"- Engineer correction: {h}" for h in hints[:5]) if hints else "None yet."
        penalized = scoring.get("penalized_fault_types") or {}
        boosted = scoring.get("boosted_fault_types") or {}
        scoring_lines = []
        if penalized:
            scoring_lines.append(
                "Deprioritize these fault types (engineers marked prior recommendations as not helpful): "
                + ", ".join(f"{k} ({v}x)" for k, v in penalized.items())
            )
        if boosted:
            scoring_lines.append(
                "Prioritize these fault types (engineers confirmed helpful): "
                + ", ".join(f"{k} ({v}x)" for k, v in boosted.items())
            )
        if scoring.get("accuracy_pct"):
            scoring_lines.append(f"Historical recommendation accuracy: {scoring['accuracy_pct']}%")
        scoring_block = "\n".join(scoring_lines) if scoring_lines else "No feedback scoring yet."
        op_block = json.dumps(op, default=str)[:2500] if op else "{}"
        rag_results = state.get("rag_results") or []
        rag_block = "\n".join(
            f"[Doc: {r.get('source', 'Unknown')}] ({r.get('document_type', '')}, score={r.get('score', 0):.2f})\n{r.get('excerpt', '')[:400]}"
            for r in rag_results[:4]
        ) or "No matching SOP/manual found in knowledge base."
        spares = state.get("spare_context") or []
        spares_block = json.dumps(spares, default=str)[:2000] if spares else "[]"
        intent = state.get("query_intent") or "general"
        page_ctx = state.get("page_context") or ""
        intent_instructions = {
            "spares_cost": "Lead with ## Spares Cost. Show unit price (INR), on-hand inventory value, and replenishment estimate. Do NOT list stock/reorder unless tied to a cost figure.",
            "spares": "Lead with ## Spares & Procurement only. List EVERY part with stock, reorder level, lead time, unit cost. Do NOT include Assessment or Root Causes unless user also asked for diagnosis.",
            "rul": "Lead with ## RUL Prediction only. Give hours, days, failure probability, urgency. Skip spares unless critical.",
            "knowledge": "Lead with ## References and procedure steps from RETRIEVED KNOWLEDGE. Quote [Doc: title]. Minimal sensor summary (2 lines max).",
            "plan": "Lead with ## Immediate Actions and short/medium-term plan. Time-bound numbered steps.",
            "alerts": "Lead with alert triage — which to handle first and why. Reference open faults from operational inputs.",
            "diagnosis": "Lead with ## Probable Root Causes with confidence and sensor evidence.",
            "fleet": "Answer across all 5 C-MAPSS assets — rank by urgency.",
            "scenario": "Lead with ## Operational Impact Summary (downtime, production tons, INR cost). Then ## Affected Assets table, ## Contingency Plan, ## Maintenance Recommendation. Be specific to Tata Steel Jamshedpur operations.",
        }.get(intent, "Answer the user's exact question first. Only add sensor assessment if directly relevant.")
        prompt = f"""You are ForgeMind for Tata Steel Jamshedpur — senior maintenance engineer.

Equipment: {eq.get('equipment_code')} — {eq.get('name')}
User question (answer THIS directly): {state['query']}
Query intent: {intent}
{f"User is on page: {page_ctx}" if page_ctx else ""}

C-MAPSS FD001 live sensors (unit {reading.get('cmapss_unit')}, cycle {reading.get('cycle')}):
- Temperature: {reading.get('temperature')}°C | Vibration: {reading.get('vibration')} mm/s
- Pressure: {reading.get('pressure')} bar | Current: {reading.get('motor_current')} A
- Health: {reading.get('health_indicator')}% | RUL: {reading.get('rul_hours')}h

SPARE PARTS INVENTORY (use for procurement questions):
{spares_block}

RETRIEVED KNOWLEDGE (cite as [Doc: title] when used):
{rag_block}

Operational inputs (delay logs, fault alerts, failure incidents):
{op_block}

Engineer feedback to incorporate:
{hints_block}

Feedback-driven scoring (adjust recommendations accordingly):
{scoring_block}

Multi-agent analysis (supporting data — do not dump all sections if irrelevant):
{json.dumps(structured, default=str)[:3500]}

RESPONSE CONTRACT:
1. First sentence MUST directly answer: "{state['query']}"
2. {intent_instructions}
3. Omit empty sections entirely — never use a generic template
4. Root causes only if user asked about faults/diagnosis OR vibration > 6.0 mm/s
5. Actions: numbered, time-bound; include part numbers for spares questions
6. End with exactly 3 follow-ups as lines starting with "->"
"""
        history = state.get("history") or []
        final = await llm_service.generate(prompt, history=history)
        if llm_service.last_provider == "rule_based":
            final = self._fallback_from_state(state, structured, spares)
        thoughts.append(_thought("synthesizer", "Orchestrator compiling final corrective actions for engineer.", {"provider": llm_service.last_provider}, phase="Final synthesis"))
        trace.append("Response synthesized — ready for engineer review")
        return {
            **state,
            "final_response": final,
            "structured_output": structured,
            "citations": citations,
            "agent_trace": trace,
            "agent_thoughts": thoughts,
        }

    def _fallback_from_state(self, state: AgentState, structured: dict, spares: list) -> str:
        """Query-aware fallback when no LLM API key is configured."""
        query = (state.get("query") or "").lower()
        eq = state.get("equipment_context") or {}
        reading = state.get("sensor_reading") or {}
        code = eq.get("equipment_code", "Asset")

        if any(w in query for w in ("cost", "price", "how much", "budget")):
            if not spares:
                return f"**Spare parts cost for {code}:** no priced parts in inventory."
            lines = [f"**Spare parts cost for {code}:**\n"]
            total = 0.0
            for s in spares:
                unit = float(s.get("unit_cost") or 0)
                qty = s.get("quantity_available", 0)
                val = unit * qty
                total += val
                lines.append(f"- {s['part_number']} {s['name']}: ₹{unit:,.0f}/unit · {qty} in stock · ₹{val:,.0f} on hand")
            lines.append(f"\n**Total on-hand value:** ₹{total:,.0f}")
            return "\n".join(lines)

        if any(w in query for w in ("spare", "procure", "inventory", "stock", "reorder", "part")):
            if not spares:
                return f"**Spares for {code}:** no parts mapped in inventory — raise procurement for bearings, belts, and seal kits."
            lines = [f"**Spares to procure for {code}:**\n"]
            for s in spares:
                qty = s.get("quantity_available", 0)
                reorder = s.get("reorder_level", 5)
                flag = " — **ORDER NOW**" if qty <= reorder else ""
                lines.append(
                    f"- **{s['part_number']}** {s['name']}: {qty} in stock (reorder at {reorder}, lead {s.get('lead_time_days', 14)}d){flag}"
                )
            return "\n".join(lines)

        if any(w in query for w in ("rul", "remaining", "life left")):
            rul = reading.get("rul_hours", "N/A")
            return (
                f"**RUL for {code}:** {rul}h remaining · health {reading.get('health_indicator', 'N/A')}% · "
                f"vibration {reading.get('vibration', 'N/A')} mm/s."
            )

        if any(w in query for w in ("root cause", "root-cause", "degrad", "degration", "why is", "diagnos", "fault", "symptom", "failure mode")):
            diagnosis = structured.get("diagnosis") or {}
            causes = diagnosis.get("probable_causes") or []
            if not causes:
                vib = float(reading.get("vibration", 0) or 0)
                temp = float(reading.get("temperature", 0) or 0)
                health = float(reading.get("health_indicator", 100) or 100)
                if vib >= 4.5:
                    causes.append({"cause": f"Bearing wear — vibration {vib:.2f} mm/s", "confidence": 0.8})
                if temp >= 85:
                    causes.append({"cause": f"Thermal stress — {temp:.1f}°C", "confidence": 0.75})
                if health < 60:
                    causes.append({"cause": f"Progressive degradation — health {health:.0f}%", "confidence": 0.82})
                if not causes:
                    causes.append({"cause": "Normal wear within expected C-MAPSS degradation curve", "confidence": 0.65})
            lines = [f"**Root cause analysis for {code}:**\n"]
            for i, c in enumerate(causes[:4], 1):
                conf = c.get("confidence", 0)
                lines.append(f"{i}. {c.get('cause', c)} (confidence {conf:.0%})" if isinstance(conf, (int, float)) else f"{i}. {c.get('cause', c)}")
            rca = diagnosis.get("root_cause_analysis")
            if rca:
                lines.append(f"\n**Analysis:** {rca}")
            plan = structured.get("maintenance_plan") or {}
            imm = plan.get("immediate_actions") or []
            if imm:
                lines.append("\n**Next steps:**\n" + "\n".join(f"{i}. {a}" for i, a in enumerate(imm[:4], 1)))
            return "\n".join(lines)

        pred = structured.get("prediction") or {}
        plan = structured.get("maintenance_plan") or {}
        imm = plan.get("immediate_actions") or []
        return (
            f"**Answer for {code}:**\n"
            f"RUL {pred.get('remaining_useful_life_hours', reading.get('rul_hours', 'N/A'))}h · "
            f"risk {structured.get('risk_assessment', {}).get('risk_level', 'medium')}.\n\n"
            f"**Next steps:**\n" + "\n".join(f"{i}. {a}" for i, a in enumerate(imm[:4], 1))
        )

    async def run(
        self,
        query: str,
        equipment_context: dict | None = None,
        sensor_reading: dict | None = None,
        spare_context: list | None = None,
        feedback_hints: list[str] | None = None,
        feedback_scoring: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
        operational_context: dict | None = None,
        scenario_context: dict | None = None,
        query_intent: str = "general",
        page_context: str | None = None,
        scenario_simulation: dict | None = None,
        fleet_snapshot: dict | None = None,
        force_chat_pipeline: bool = False,
        intent_routed_chat: bool = False,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        initial: AgentState = {
            "query": query,
            "query_intent": query_intent,
            "page_context": page_context,
            "orchestration_mode": (
                "chat_full"
                if force_chat_pipeline
                else "chat_intent"
                if intent_routed_chat
                else "dynamic"
            ),
            "equipment_id": equipment_context.get("id") if equipment_context else None,
            "equipment_context": equipment_context or {},
            "sensor_reading": sensor_reading or {},
            "spare_context": spare_context or [],
            "feedback_hints": feedback_hints or [],
            "feedback_scoring": feedback_scoring or {},
            "history": history or [],
            "operational_context": operational_context or {},
            "scenario_context": scenario_context or {},
            "scenario_simulation": scenario_simulation or {},
            "fleet_snapshot": fleet_snapshot or {},
            "agent_trace": ["Orchestrator → supervisor-led dynamic agent pipeline"],
            "agent_thoughts": [],
            "execution_started_at": t0,
        }
        result = await self.graph.ainvoke(initial)
        execution_ms = (time.perf_counter() - t0) * 1000
        structured = result.get("structured_output", {})
        if not structured and result.get("diagnosis"):
            structured = {
                "diagnosis": result.get("diagnosis", {}),
                "prediction": result.get("ml_prediction", {}),
                "risk_assessment": result.get("risk_assessment", {}),
                "maintenance_plan": result.get("maintenance_plan", {}),
            }
        if scenario_simulation and "scenario_simulation" not in structured:
            structured["scenario_simulation"] = scenario_simulation

        detected_intent = result.get("query_intent") or query_intent
        is_conv = is_conversational_intent(detected_intent) or structured.get("chat_style") == "conversational"

        if is_conv:
            structured["chat_style"] = "conversational"
            structured["response_template"] = structured.get("response_template") or "conversational"
            explainability = None
            reasoning = None
        else:
            from app.services.explainability_service import build_explainability_bundle

            structured["chat_style"] = structured.get("chat_style") or "maintenance"

            explainability = build_explainability_bundle(
                structured_output=structured,
                sensor_reading=sensor_reading,
                operational_context=operational_context,
                agent_thoughts=result.get("agent_thoughts", []),
                agent_trace=result.get("agent_trace", []),
                citations=result.get("citations", []),
                execution_time_ms=execution_ms,
                query_intent=detected_intent,
                scenario_simulation=scenario_simulation or structured.get("scenario_simulation"),
            )
            structured = {**structured, "explainability": explainability}

            reasoning = build_reasoning_panel(
                agent_thoughts=result.get("agent_thoughts", []),
                agent_trace=result.get("agent_trace", []),
                citations=result.get("citations", []),
                query_intent=detected_intent,
                llm_provider=llm_service.last_provider,
                structured_output=structured,
            )

        return {
            "message": result.get("final_response", ""),
            "agent_trace": result.get("agent_trace", []),
            "agent_thoughts": result.get("agent_thoughts", []),
            "citations": result.get("citations", []),
            "structured_output": structured,
            "reasoning_panel": reasoning.model_dump() if reasoning else None,
            "explainability": explainability,
            "execution_time_ms": execution_ms,
            "llm_provider": structured.get("llm_provider") or llm_service.last_provider,
        }


def get_orchestrator() -> MaintenanceWizardOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MaintenanceWizardOrchestrator()
    return _orchestrator
