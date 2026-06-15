"""Tata Steel PDF report templates — ReportLab."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TATA_BLUE = colors.HexColor("#005DAA")
TATA_GOLD = colors.HexColor("#B8860B")
MUTED = colors.HexColor("#5C6B82")

REPORT_LABELS = {
    "alert": "Alert Report",
    "priority": "Priority Report",
    "diagnosis": "Diagnosis Report",
    "maintenance_plan": "Maintenance Plan",
    "scenario": "Failure Scenario Report",
    "decision": "Maintenance Decision Report",
    "executive": "Executive Summary",
    "maintenance": "Maintenance Report",
    "abnormal": "Abnormal Alert Report",
}


def _p(text: str) -> str:
    return (text or "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_report_pdf(title: str, content: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )
    styles = getSampleStyleSheet()
    brand = ParagraphStyle("Brand", parent=styles["Normal"], fontSize=9, textColor=MUTED)
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=16, textColor=TATA_BLUE, spaceAfter=6)
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=10, textColor=MUTED, spaceAfter=10)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, textColor=TATA_BLUE, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#1a1a1a"))
    small = ParagraphStyle("Small", parent=body, fontSize=8, textColor=MUTED)

    meta = content.get("report_meta") or {}
    report_type = meta.get("report_type") or content.get("report_type") or "report"
    type_label = REPORT_LABELS.get(report_type, report_type.replace("_", " ").title())

    story: list = [
        Paragraph(_p("TATA STEEL · Maintenance Wizard"), brand),
        Paragraph(_p(title), title_style),
        Paragraph(_p(f"{type_label} · Generated {meta.get('generated_at', 'N/A')[:19]}"), subtitle),
    ]

    # Key metrics table
    metrics = _metrics_rows(content)
    if metrics:
        tbl = Table(metrics, colWidths=[4.5 * cm, 12 * cm])
        tbl.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), TATA_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#E8F2FA")),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(tbl)
        story.append(Spacer(1, 0.35 * cm))

    sections = [
        ("Asset", _fmt_asset(content.get("asset"))),
        ("Diagnosis / Summary", _fmt_diagnosis(content)),
        ("Remaining Useful Life (RUL)", _fmt_dict(content.get("rul"))),
        ("Risk Assessment", _fmt_dict(content.get("risk"))),
        ("Root Cause Analysis", _fmt_causes(content.get("root_cause"))),
        ("Citations & Knowledge Base", _fmt_citations(content.get("citations") or content.get("retrieved_documents"))),
        ("Maintenance Recommendations", _fmt_maintenance(content.get("maintenance_recommendation") or content.get("recommended_actions"))),
        ("Spare Parts Status", _fmt_spares(content.get("spare_status") or content.get("spares"))),
        ("Business Impact", _fmt_business(content.get("business_impact") or content.get("cost_impact"))),
        ("Executive Narrative", content.get("narrative") or (content.get("executive_summary") or {}).get("narrative")),
        ("Scenario Details", _fmt_scenario(content.get("scenario"))),
        ("Schedule Tasks", _fmt_schedule(content.get("schedule_tasks"))),
    ]

    for heading, text in sections:
        if not text or text.strip() in ("", "—"):
            continue
        story.append(Paragraph(_p(heading), h2))
        story.append(Paragraph(_p(str(text)).replace("\n", "<br/>"), body))
        story.append(Spacer(1, 0.15 * cm))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(_p("Confidential — Tata Steel internal maintenance decision support"), small))

    doc.build(story)
    return buf.getvalue()


def _metrics_rows(content: dict) -> list[list[str]]:
    asset = content.get("asset") or {}
    rul = content.get("rul") or {}
    risk = content.get("risk") or {}
    bi = content.get("business_impact") or content.get("cost_impact") or {}
    rows = [["Metric", "Value"]]
    if asset.get("code"):
        rows.append(["Asset", f"{asset.get('code')} — {asset.get('name', '')}"])
    scenario = content.get("scenario") or {}
    if scenario.get("delay_label"):
        rows.append(["Simulated delay", str(scenario["delay_label"])])
    elif scenario.get("delay_hours") is not None:
        rows.append(["Simulated delay", f"{scenario['delay_hours']} hours"])
    if rul.get("rul_hours") is not None:
        rows.append(["RUL", f"{rul.get('rul_hours')} hours"])
    elif rul.get("rul_days") is not None:
        rows.append(["RUL", f"{rul.get('rul_days')} days"])
    if risk.get("risk_level") or risk.get("alert_level"):
        rows.append(["Risk", str(risk.get("risk_level") or risk.get("alert_level"))])
    fp = risk.get("failure_probability") or rul.get("failure_probability")
    if fp is not None:
        rows.append(["Failure Probability", f"{float(fp) * 100:.0f}%" if float(fp) <= 1 else str(fp)])
    impact = bi.get("cost_impact_inr") or bi.get("estimated_impact_inr") or bi.get("total_estimated_savings_inr")
    if impact:
        rows.append(["Business Impact", f"₹{int(impact):,}"])
    return rows if len(rows) > 1 else []


def _fmt_asset(asset: dict | None) -> str:
    if not asset:
        return ""
    lines = [
        f"Code: {asset.get('code', '—')}",
        f"Name: {asset.get('name', '—')}",
        f"Location: {asset.get('location', '—')}",
    ]
    if asset.get("criticality"):
        lines.append(f"Criticality: {asset.get('criticality')}/5")
    return "\n".join(lines)


def _fmt_diagnosis(content: dict) -> str:
    d = content.get("diagnosis")
    if isinstance(d, str):
        return d
    if isinstance(d, dict):
        return d.get("summary") or str(d)
    return content.get("narrative") or ""


def _fmt_dict(d: dict | None) -> str:
    if not d:
        return ""
    return "\n".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in d.items() if v is not None and v != "")


def _fmt_causes(rc: dict | None) -> str:
    if not rc:
        return ""
    lines = []
    for c in rc.get("probable_causes") or []:
        if isinstance(c, dict):
            conf = c.get("confidence")
            conf_s = f" ({float(conf) * 100:.0f}%)" if conf is not None else ""
            lines.append(f"• {c.get('cause', c)}{conf_s}")
        else:
            lines.append(f"• {c}")
    if rc.get("root_cause_analysis"):
        lines.append(str(rc["root_cause_analysis"]))
    return "\n".join(lines)


def _fmt_citations(docs: list | None) -> str:
    if not docs:
        return ""
    lines = []
    for i, d in enumerate(docs[:6], 1):
        if isinstance(d, dict):
            lines.append(f"[{i}] {d.get('source', 'Document')} ({d.get('document_type', '')})")
            excerpt = (d.get("excerpt") or d.get("content") or "")[:280]
            if excerpt:
                lines.append(f"    {excerpt}")
        else:
            lines.append(f"[{i}] {d}")
    return "\n".join(lines)


def _fmt_maintenance(rec: dict | None) -> str:
    if not rec:
        return ""
    lines = []
    for key, label in (
        ("immediate_actions", "Immediate"),
        ("immediate", "Immediate"),
        ("short_term_actions", "Short-term"),
        ("short_term", "Short-term"),
        ("long_term_actions", "Long-term"),
        ("long_term", "Long-term"),
    ):
        for a in rec.get(key) or []:
            lines.append(f"• [{label}] {a}")
    if rec.get("monitoring_plan"):
        lines.append(f"Monitoring: {rec['monitoring_plan']}")
    if rec.get("ai_summary"):
        lines.append(rec["ai_summary"][:800])
    return "\n".join(lines)


def _fmt_spares(sp: dict | None) -> str:
    if not sp:
        return ""
    lines = []
    for k in ("status", "spare_stock", "quantity_available", "lead_time_days", "procurement_risk", "critical_spare_part", "critical_spares_available"):
        if sp.get(k) is not None:
            lines.append(f"{k.replace('_', ' ').title()}: {sp[k]}")
    for p in sp.get("parts") or sp.get("available") or []:
        if isinstance(p, dict):
            lines.append(f"• {p.get('part_number', p.get('name'))}: {p.get('quantity_available', '?')} in stock")
    if sp.get("procurement_notes"):
        for n in sp["procurement_notes"][:3]:
            lines.append(f"• {n}")
    return "\n".join(lines)


def _fmt_business(bi: dict | None) -> str:
    if not bi:
        return ""
    lines = []
    mapping = {
        "cost_impact_inr": "Cost impact (INR)",
        "estimated_impact_inr": "Estimated impact (INR)",
        "total_estimated_savings_inr": "Fleet savings (INR)",
        "total_avoided_loss_inr": "Avoided loss (INR)",
        "fleet_roi_pct": "Fleet ROI %",
        "downtime_hours": "Downtime (hours)",
        "production_loss_tons": "Production loss (tons)",
        "direct_cost_inr": "Direct cost (INR)",
        "cascade_cost_inr": "Cascade cost (INR)",
        "estimated_downtime_hours": "Est. downtime (hours)",
        "estimated_cost_inr": "Est. cost (INR)",
    }
    for k, label in mapping.items():
        if bi.get(k) is not None:
            v = bi[k]
            lines.append(f"{label}: {f'₹{int(v):,}' if 'inr' in k or 'cost' in k or 'savings' in k or 'loss' in k else v}")
    return "\n".join(lines)


def _fmt_scenario(sc: dict | None) -> str:
    if not sc:
        return ""
    lines = []
    if sc.get("scenario_label"):
        lines.append(f"Selected scenario: {sc['scenario_label']}")
    if sc.get("delay_label"):
        lines.append(f"Maintenance delay simulated: {sc['delay_label']}")
    elif sc.get("delay_hours") is not None:
        hours = int(sc["delay_hours"])
        if hours == 72:
            lines.append("Maintenance delay simulated: 3 days (72 hours)")
        elif hours == 168:
            lines.append("Maintenance delay simulated: 7 days (168 hours)")
        elif hours == 24:
            lines.append("Maintenance delay simulated: 24 hours (1 day)")
        elif hours % 24 == 0 and hours > 0:
            lines.append(f"Maintenance delay simulated: {hours // 24} days ({hours} hours)")
        else:
            lines.append(f"Maintenance delay simulated: {hours} hours")
    if sc.get("failure_mode"):
        mode = sc["failure_mode"]
        lines.append(f"Simulation mode: {mode.replace('_', ' ')}")
    for line in sc.get("comparison") or []:
        lines.append(line)
    for step in sc.get("contingency") or []:
        lines.append(f"• {step}")
    return "\n".join(lines)


def _fmt_schedule(tasks: list | None) -> str:
    if not tasks:
        return ""
    lines = []
    for t in tasks[:10]:
        lines.append(
            f"• {t.get('equipment_code', '?')}: {t.get('task', 'Task')} "
            f"[{t.get('urgency', 'planned')}] {str(t.get('start', ''))[:10]}"
        )
    return "\n".join(lines)
