"""Build structured AI Reasoning Panel from LangGraph execution state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas import AIReasoningPanel, Citation, ReasoningDocument, ReasoningStep

JUDGE_LABELS: dict[str, str] = {
    "supervisor": "Supervisor Agent",
    "document_agent": "Knowledge Agent",
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

AGENT_PHASES: dict[str, str] = {
    "supervisor": "Agent orchestration",
    "document_agent": "Documents retrieved",
    "predictive_agent": "RUL prediction",
    "rca_agent": "Root cause analysis",
    "inventory_agent": "Spare availability",
    "risk_agent": "Risk classification",
    "production_impact_agent": "Business impact analysis",
    "spare_parts_agent": "Spare availability",
    "planner_agent": "Maintenance recommendation",
    "alert_agent": "Alert escalation",
    "report_agent": "Report generation",
    "scenario_agent": "Cascade impact analysis",
    "synthesizer": "Supervisor synthesis",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_confidence(agent: str, data: dict[str, Any]) -> float | None:
    if not data:
        return None
    if agent == "document_agent":
        matches = data.get("matches") or []
        return float(matches[0]["score"]) if matches else None
    if agent == "predictive_agent":
        pred = data.get("prediction") or {}
        mc = pred.get("model_confidence")
        if mc is not None:
            return float(mc)
        fp = pred.get("failure_probability")
        return float(fp) if fp is not None else None
    if agent == "rca_agent":
        diag = data.get("diagnosis") or {}
        cs = diag.get("confidence_score")
        return float(cs) if cs is not None else None
    if agent == "inventory_agent":
        inv = data.get("inventory") or {}
        pr = str(inv.get("procurement_risk", "medium")).lower()
        return {"low": 0.4, "medium": 0.6, "high": 0.78, "critical": 0.92}.get(pr, 0.55)
    if agent == "risk_agent":
        risk = data.get("risk_assessment") or {}
        rl = risk.get("risk_level")
        mapping = {"low": 0.35, "medium": 0.55, "high": 0.75, "critical": 0.92}
        if isinstance(rl, str):
            return mapping.get(rl.lower())
        return None
    if agent == "production_impact_agent":
        pi = data.get("production_impact") or {}
        return float(pi.get("prevention_factor_pct", 70)) / 100 if pi else None
    if agent == "spare_parts_agent":
        risk = data.get("risk") or {}
        rl = risk.get("risk_level")
        mapping = {"low": 0.35, "medium": 0.55, "high": 0.75, "critical": 0.92}
        if isinstance(rl, str):
            return mapping.get(rl.lower())
        return None
    if agent == "alert_agent":
        alert = data.get("should_alert")
        return 0.9 if alert else 0.4
    if agent == "synthesizer":
        prov = data.get("provider")
        return 0.85 if prov and prov not in ("rule_based", "unknown") else 0.6
    return None


def _docs_from_matches(data: dict[str, Any]) -> list[ReasoningDocument]:
    docs: list[ReasoningDocument] = []
    for m in (data.get("matches") or [])[:5]:
        docs.append(
            ReasoningDocument(
                source=str(m.get("source", "Unknown")),
                document_type=str(m.get("type", "document")),
                excerpt="",
                score=float(m.get("score", 0)),
            )
        )
    return docs


def _citations_from_list(raw: list[dict[str, Any]] | None) -> list[Citation]:
    if not raw:
        return []
    out: list[Citation] = []
    for c in raw[:6]:
        out.append(
            Citation(
                source=str(c.get("source", "")),
                document_type=str(c.get("document_type", "")),
                excerpt=str(c.get("excerpt", ""))[:400],
                score=float(c.get("score", 0)),
            )
        )
    return out


def _expand_spare_step(thought: dict[str, Any], step_no: int) -> list[ReasoningStep]:
    """Split Spares & Risk into Risk + Inventory steps for judge visibility."""
    data = thought.get("data") or {}
    risk = data.get("risk") or {}
    spares = data.get("spares") or []
    ts = thought.get("timestamp") or _now_iso()
    steps: list[ReasoningStep] = []

    risk_level = risk.get("risk_level", "medium")
    if hasattr(risk_level, "value"):
        risk_level = risk_level.value
    steps.append(
        ReasoningStep(
            step=step_no,
            agent="spare_parts_agent",
            label="Risk Agent",
            phase="Risk classification",
            status=thought.get("status", "complete"),
            timestamp=ts,
            confidence=_extract_confidence("spare_parts_agent", data),
            summary=f"Composite risk level: {risk_level}. Score factors include failure probability, criticality, and downtime cost.",
            output={"risk_assessment": risk},
            citations=[],
            documents=[],
        )
    )
    inv_summary = (
        f"{len(spares)} spare line(s) checked — "
        + (f"{spares[0].get('part_number')} ({spares[0].get('quantity_available', 0)} in stock)" if spares else "no mapped parts")
    )
    steps.append(
        ReasoningStep(
            step=step_no + 1,
            agent="inventory_agent",
            label="Inventory Agent",
            phase="Spare availability",
            status=thought.get("status", "complete"),
            timestamp=ts,
            confidence=0.95 if spares else 0.5,
            summary=inv_summary,
            output={"spares": spares[:5], "procurement_notes": risk.get("procurement_notes", [])},
            citations=[],
            documents=[],
        )
    )
    return steps


def build_reasoning_panel(
    *,
    agent_thoughts: list[dict[str, Any]] | None,
    agent_trace: list[str] | None = None,
    citations: list[dict[str, Any]] | None = None,
    query_intent: str | None = None,
    llm_provider: str | None = None,
    structured_output: dict[str, Any] | None = None,
) -> AIReasoningPanel:
    thoughts = agent_thoughts or []
    steps: list[ReasoningStep] = []
    step_no = 1
    global_citations = _citations_from_list(citations)

    supervisor = next((t for t in thoughts if t.get("agent") == "supervisor"), None)
    agent_plan: list[str] = []
    routing_mode = "intent_rules"
    if supervisor:
        sup_data = supervisor.get("data") or {}
        agent_plan = list(sup_data.get("agent_plan") or [])
        routing_mode = str(sup_data.get("routing_mode") or routing_mode)

    for thought in thoughts:
        agent = str(thought.get("agent", "unknown"))
        if agent == "spare_parts_agent":
            expanded = _expand_spare_step(thought, step_no)
            steps.extend(expanded)
            step_no += len(expanded)
            continue

        data = thought.get("data") or {}
        phase = thought.get("phase") or AGENT_PHASES.get(agent, "Processing")
        label = JUDGE_LABELS.get(agent, thought.get("label") or agent)
        conf = thought.get("confidence")
        if conf is None:
            conf = _extract_confidence(agent, data)

        step_citations = global_citations if agent in ("document_agent", "synthesizer") else []
        documents = _docs_from_matches(data) if agent == "document_agent" else []

        if agent == "document_agent" and global_citations and not documents:
            documents = [
                ReasoningDocument(
                    source=c.source,
                    document_type=c.document_type,
                    excerpt=c.excerpt[:200],
                    score=c.score,
                )
                for c in global_citations[:4]
            ]

        steps.append(
            ReasoningStep(
                step=step_no,
                agent=agent,
                label=label,
                phase=phase,
                status=str(thought.get("status", "complete")),
                timestamp=thought.get("timestamp") or _now_iso(),
                confidence=float(conf) if conf is not None else None,
                summary=str(thought.get("detail") or ""),
                output=data,
                citations=step_citations,
                documents=documents,
            )
        )
        step_no += 1

    return AIReasoningPanel(
        query_intent=query_intent,
        routing_mode=routing_mode,
        agent_plan=agent_plan,
        agent_trace=agent_trace or [],
        steps=steps,
        total_steps=len(steps),
        citations=global_citations,
        llm_provider=llm_provider,
        structured_summary={
            "diagnosis_confidence": (structured_output or {}).get("diagnosis", {}).get("confidence_score"),
            "risk_level": (structured_output or {}).get("risk_assessment", {}).get("risk_level"),
            "rul_hours": (structured_output or {}).get("prediction", {}).get("remaining_useful_life_hours"),
        },
    )
