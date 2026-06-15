"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Cpu,
  Factory,
  Layers,
  Network,
  Package,
  Sparkles,
  Stethoscope,
  TrendingUp,
} from "lucide-react";
import type { AIReasoningPanelData, ReasoningStep } from "@/components/AIReasoningPanel";

const DISPLAY_ORDER = [
  "predictive_agent",
  "inventory_agent",
  "rca_agent",
  "risk_agent",
  "production_impact_agent",
  "scenario_agent",
  "planner_agent",
  "document_agent",
  "synthesizer",
] as const;

const AGENT_ICONS: Record<string, typeof TrendingUp> = {
  predictive_agent: TrendingUp,
  inventory_agent: Package,
  rca_agent: Stethoscope,
  risk_agent: AlertTriangle,
  production_impact_agent: Factory,
  scenario_agent: Layers,
  planner_agent: Cpu,
  document_agent: BookOpen,
  synthesizer: Sparkles,
  supervisor: Network,
};

type FieldRow = { label: string; value: string; highlight?: boolean };

function pct(v: unknown): string {
  const n = Number(v);
  if (Number.isNaN(n)) return String(v ?? "—");
  const pctVal = n <= 1 ? n * 100 : n;
  return `${Math.min(100, Math.round(pctVal))}%`;
}

function confidencePct(v: unknown): number | null {
  const n = Number(v);
  if (Number.isNaN(n)) return null;
  const pctVal = n <= 1 ? n * 100 : n;
  return Math.min(100, Math.round(pctVal));
}

function fmtNum(v: unknown, suffix = ""): string {
  const n = Number(v);
  if (Number.isNaN(n)) return String(v ?? "—");
  return `${n.toLocaleString()}${suffix}`;
}

function extractFields(step: ReasoningStep): FieldRow[] {
  const out = step.output || {};
  switch (step.agent) {
    case "predictive_agent": {
      const pred = (out.prediction as Record<string, unknown>) || {};
      const reading = (out.reading as Record<string, unknown>) || {};
      const src = reading.source ? String(reading.source) : "C-MAPSS FD001";
      const unit = reading.cmapss_unit ?? "?";
      const cycle = reading.cycle ?? "?";
      return [
        { label: "RUL", value: `${fmtNum(pred.remaining_useful_life_hours, " h")}`, highlight: true },
        { label: "Failure Probability", value: pct(pred.failure_probability) },
        { label: "Confidence", value: pct(pred.model_confidence ?? step.confidence) },
        { label: "Data Source", value: `${src} · unit ${unit} · cycle ${cycle}` },
      ];
    }
    case "inventory_agent": {
      const inv = (out.inventory as Record<string, unknown>) || {};
      const lines = (inv.spare_availability as string[]) || [];
      return [
        { label: "Spare Availability", value: `${inv.spare_stock ?? 0} units in stock`, highlight: true },
        { label: "Lead Time", value: `${inv.lead_time_days ?? "?"} days` },
        { label: "Procurement Risk", value: String(inv.procurement_risk ?? "unknown").toUpperCase(), highlight: true },
        ...(lines.slice(0, 2).map((l, i) => ({ label: i === 0 ? "Parts Checked" : "", value: l })) as FieldRow[]),
      ];
    }
    case "rca_agent": {
      const diag = (out.diagnosis as Record<string, unknown>) || {};
      const chain = (diag.root_cause_chain as Record<string, unknown>) || {};
      const causes = (diag.probable_causes as { cause?: string; confidence?: number }[]) || [];
      const evidence = (chain.evidence as { label?: string }[]) || [];
      const top = causes[0];
      return [
        { label: "Root Cause", value: String(chain.most_likely_cause || top?.cause || "No dominant fault pattern"), highlight: true },
        { label: "Confidence", value: pct(diag.confidence_score ?? step.confidence) },
        ...(evidence.slice(0, 2).map((e, i) => ({ label: `Evidence ${i + 1}`, value: String(e.label) })) as FieldRow[]),
      ];
    }
    case "scenario_agent": {
      const sa = (out.scenario_analysis as Record<string, unknown>) || {};
      const sim = (sa.simulation as Record<string, unknown>) || (out.scenario_simulation as Record<string, unknown>) || {};
      const projections = (sim.projections as { label?: string; failure_probability_pct?: number }[]) || [];
      return [
        { label: "Simulation", value: String(sim.recommended_action || sa.recommended_action || "Future-state projection"), highlight: true },
        ...projections.slice(0, 3).map((p, i) => ({
          label: i === 0 ? "Horizons" : "",
          value: `${p.label}: ${p.failure_probability_pct}% failure prob`,
        })),
      ];
    }
    case "risk_agent": {
      const risk = (out.risk_assessment as Record<string, unknown>) || {};
      const breakdown = (risk.score_breakdown as Record<string, unknown>) || {};
      const components = (breakdown.components as { factor: string; value: string; weight_pct: number }[]) || [];
      return [
        { label: "Risk Score / Level", value: `${breakdown.final_score_100 ?? "—"}/100 · ${String(risk.risk_level ?? "medium").toUpperCase()}`, highlight: true },
        { label: "Escalation Reason", value: String(risk.escalation_reason ?? step.summary) },
        ...components.slice(0, 2).map((c) => ({ label: c.factor, value: `${c.value} (w${c.weight_pct}%)` })),
      ];
    }
    case "production_impact_agent": {
      const pi = (out.production_impact as Record<string, unknown>) || {};
      return [
        { label: "Downtime Estimate", value: `${fmtNum(pi.downtime_estimate_hours ?? pi.expected_downtime_hours, " h")}`, highlight: true },
        { label: "Throughput Impact", value: `${fmtNum(pi.throughput_impact_tons, " t")} at risk` },
        { label: "Business Cost", value: `₹${fmtNum(pi.business_cost_inr ?? pi.downtime_cost_inr)}` },
        { label: "Data Source", value: String(pi.data_source ?? "Business impact model") },
      ];
    }
    case "planner_agent": {
      const plan = (out.plan as Record<string, unknown>) || (out.maintenance_plan as Record<string, unknown>) || {};
      const imm = (plan.immediate_actions as string[]) || [];
      const long = (plan.long_term_actions as string[]) || (plan.short_term_actions as string[]) || [];
      return [
        { label: "Immediate Action", value: imm[0] || "Monitor and inspect", highlight: true },
        { label: "Long-Term Action", value: long[0] || "Schedule preventive maintenance", highlight: true },
        ...(imm.slice(1, 3).map((a, i) => ({ label: `Also (immediate ${i + 2})`, value: a })) as FieldRow[]),
      ];
    }
    case "document_agent": {
      const docs = step.documents?.length ? step.documents : [];
      const matches = ((out.matches as { source?: string; score?: number }[]) || []).slice(0, 3);
      const src =
        docs.length > 0
          ? docs.map((d) => `${d.source} (${d.score.toFixed(2)})`).join(", ")
          : matches.map((m) => `${m.source} (${Number(m.score).toFixed(2)})`).join(", ");
      return [
        { label: "Documents Retrieved", value: src || "No matching SOP/manual", highlight: true },
        { label: "Evidence", value: step.summary },
      ];
    }
    case "synthesizer":
      return [
        { label: "Synthesis Mode", value: "Deterministic merge of all agent outputs", highlight: true },
        { label: "Reasoning", value: step.summary },
      ];
    default:
      return [{ label: "Output", value: step.summary }];
  }
}

function ConfidencePill({ value }: { value: number | null | undefined }) {
  const pctVal = value == null ? null : confidencePct(value);
  if (pctVal == null) return null;
  const tone =
    pctVal >= 80 ? "bg-emerald-100 text-emerald-800" : pctVal >= 60 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-700";
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${tone}`}>{pctVal}% confidence</span>
  );
}

const AGENT_PURPOSE: Record<string, string> = {
  predictive_agent: "Forecast RUL and failure probability from live sensors",
  rca_agent: "Diagnose root cause from degradation signatures",
  document_agent: "Retrieve SOPs, manuals, and failure reports",
  inventory_agent: "Assess spare availability and procurement risk",
  risk_agent: "Compute composite operational risk score",
  production_impact_agent: "Estimate downtime and production loss",
  scenario_agent: "Simulate future states under deferral scenarios",
  planner_agent: "Prioritize maintenance actions by urgency",
  synthesizer: "Merge specialist outputs into final recommendation",
};

function AgentCard({ step, embedMode }: { step: ReasoningStep; embedMode?: boolean }) {
  const [open, setOpen] = useState(false);
  const Icon = AGENT_ICONS[step.agent] || Network;
  const fields = extractFields(step);
  const purpose = AGENT_PURPOSE[step.agent] || step.phase;
  const hasEvidence =
    step.documents.length > 0 || step.citations.length > 0 || Object.keys(step.output || {}).length > 0;

  return (
    <article className={`rounded-lg border border-tata-border/60 bg-slate-50/50 ${embedMode ? "" : "shadow-sm ring-1 ring-black/[0.02]"}`}>
      <header className="flex items-start gap-2 px-3 py-2">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-tata-blue-pale text-tata-blue">
          <Icon className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-[11px] font-bold text-tata-ink">{step.label}</h4>
            <ConfidencePill value={step.confidence} />
          </div>
          <p className="text-[10px] text-tata-muted">{purpose}</p>
        </div>
      </header>
      <dl className="space-y-1.5 px-3 pb-2">
        {fields.slice(0, embedMode ? 2 : fields.length).map((f) =>
          f.label ? (
            <div key={`${f.label}-${f.value}`}>
              <dt className="text-[9px] font-semibold uppercase tracking-wide text-tata-muted">{f.label}</dt>
              <dd className={`text-[11px] leading-relaxed ${f.highlight ? "font-medium text-tata-ink" : "text-tata-muted"}`}>
                {f.value}
              </dd>
            </div>
          ) : null
        )}
      </dl>
      {hasEvidence && (
        <div className="border-t border-tata-border/40 px-3 py-1.5">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-1 text-[10px] font-medium text-tata-blue hover:underline"
          >
            {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            Reasoning trace
          </button>
          {open && (
            <div className="mt-1.5 space-y-1 text-[10px] text-tata-muted">
              {step.summary && <p className="italic">{step.summary}</p>}
              {step.documents.map((d, i) => (
                <p key={i}>
                  <span className="font-medium text-tata-blue">{d.source}</span> ({d.score.toFixed(2)})
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export function AgentOrchestrationPanel({
  panel,
  compact = false,
  embedMode = false,
}: {
  panel: AIReasoningPanelData | null | undefined;
  compact?: boolean;
  embedMode?: boolean;
}) {
  const orderedSteps = useMemo(() => {
    if (!panel?.steps?.length) return [];
    const byAgent = new Map(panel.steps.map((s) => [s.agent, s]));
    const ordered: ReasoningStep[] = [];
    for (const agent of DISPLAY_ORDER) {
      const step = byAgent.get(agent);
      if (step) ordered.push(step);
    }
    for (const step of panel.steps) {
      if (!DISPLAY_ORDER.includes(step.agent as (typeof DISPLAY_ORDER)[number]) && step.agent !== "supervisor") {
        ordered.push(step);
      }
    }
    return ordered;
  }, [panel]);

  if (!orderedSteps.length) return null;

  const specialistSteps = orderedSteps.filter((s) => s.agent !== "synthesizer");

  return (
    <div className={`space-y-2 ${compact ? "text-[11px]" : ""}`}>
      {!embedMode && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-tata-blue">Agent Orchestration</span>
          <span className="text-[10px] text-tata-muted">
            {specialistSteps.length} agents · {panel?.routing_mode?.replace(/_/g, " ") || "pipeline"}
          </span>
        </div>
      )}
      <div className={`grid gap-2 ${compact || embedMode ? "grid-cols-1" : "sm:grid-cols-2"}`}>
        {specialistSteps.map((step) => (
          <AgentCard key={`${step.step}-${step.agent}`} step={step} embedMode={embedMode} />
        ))}
      </div>
      {!embedMode && (panel?.citations?.length ?? 0) > 0 && (
        <div className="rounded-lg border border-tata-border/60 bg-tata-blue-pale/30 px-3 py-2">
          <p className="mb-1 text-[10px] font-bold uppercase text-tata-muted">Knowledge base evidence</p>
          {panel!.citations!.slice(0, 3).map((c, i) => (
            <p key={i} className="text-[11px] text-tata-muted">
              <span className="font-medium text-tata-blue">{c.source}</span> ({c.score.toFixed(2)}) — {c.excerpt.slice(0, 100)}…
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
