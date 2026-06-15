"use client";

import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Cpu,
  Factory,
  GitBranch,
  Layers,
  TrendingUp,
} from "lucide-react";

export type ExplainabilityBundle = {
  query_intent?: string;
  response_template?: string;
  routing_log?: {
    detected_intent?: string;
    intent_label?: string;
    response_template?: string;
    agents_invoked?: string[];
  };
  intent_response?: Record<string, unknown>;
  asset_ranking?: Record<string, unknown>;
  business_impact_detail?: Record<string, unknown>;
  root_cause_analysis?: Record<string, unknown>;
  maintenance_plan_detail?: Record<string, unknown>;
  sop_knowledge?: Record<string, unknown>;
  critical_spares?: Record<string, unknown>;
  failure_simulation?: Record<string, unknown>;
  decision_summary?: {
    risk_level?: string;
    rul?: string;
    rul_hours?: number;
    failure_probability_pct?: number;
    root_cause?: string;
    priority?: string;
    recommended_action?: string;
  };
  action_plan?: {
    immediate?: string[];
    next_shift?: string[];
    long_term?: string[];
  };
  executive_business_impact?: {
    downtime_avoided_hours?: number;
    production_protected_tons?: number;
    cost_exposure_inr?: number;
    potential_savings_inr?: number;
  };
  current_state?: {
    rul_hours?: number;
    failure_probability_pct?: number;
    health_score?: number;
    risk_level?: string;
    risk_score_100?: number;
    spare_stock?: number;
    lead_time_days?: number;
  };
  root_cause_chain?: {
    evidence?: { label: string; detail?: string; confidence_pct?: number }[];
    most_likely_cause?: string;
    failure_path?: string[];
  };
  risk_breakdown?: {
    final_score_100?: number;
    components?: { factor: string; value: string; weight_pct: number; contribution?: number }[];
    reason?: string;
  };
  knowledge_evidence?: {
    items?: { source: string; excerpt: string; reference?: string; score?: number }[];
    confidence_pct?: number;
  };
  scenario_simulation?: {
    current_state?: Record<string, unknown>;
    projections?: {
      label: string;
      rul_hours?: number;
      failure_probability_pct?: number;
      failure_probability_delta_pct?: number;
      risk_level?: string;
    }[];
    recommended_action?: string;
    business_impact?: Record<string, unknown>;
  };
  business_impact?: Record<string, unknown>;
  agent_trace?: {
    agents?: { agent: string; label: string; status: string }[];
    execution_time_s?: number;
    data_sources?: string[];
    intent_label?: string;
  };
};

function Card({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
}: {
  title: string;
  icon: typeof Activity;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="overflow-hidden rounded-xl border border-tata-border/70 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 border-b border-tata-border/50 bg-slate-50/80 px-3 py-2.5 text-left"
      >
        <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-tata-ink">
          <Icon className="h-4 w-4 text-tata-blue" />
          {title}
        </span>
        {open ? <ChevronUp className="h-4 w-4 text-tata-muted" /> : <ChevronDown className="h-4 w-4 text-tata-muted" />}
      </button>
      {open && <div className="px-3 py-3 text-xs leading-relaxed text-tata-muted">{children}</div>}
    </section>
  );
}

function fmtInr(v: unknown) {
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)} Lakhs`;
  return `₹${n.toLocaleString()}`;
}

export function ExplainabilityDashboard({ data }: { data: ExplainabilityBundle | null | undefined }) {
  if (!data) return null;

  const cs = data.current_state || {};
  const rcc = data.root_cause_chain || {};
  const rb = data.risk_breakdown || {};
  const ke = data.knowledge_evidence || {};
  const sim = data.scenario_simulation || {};
  const bi = data.business_impact || sim.business_impact || {};
  const trace = data.agent_trace || {};

  const hasContent =
    cs.rul_hours ||
    rcc.evidence?.length ||
    rb.components?.length ||
    ke.items?.length ||
    sim.projections?.length ||
    trace.agents?.length;

  if (!hasContent) return null;

  return (
    <div className="mb-3 space-y-2">
      <p className="text-[10px] font-bold uppercase tracking-wider text-tata-blue">Decision Support Analysis</p>

      <div className="grid gap-2 sm:grid-cols-2">
        {(cs.rul_hours != null || cs.failure_probability_pct != null) && (
          <Card title="Current State" icon={Activity}>
            <dl className="grid grid-cols-2 gap-2">
              <div>
                <dt className="text-[10px] font-semibold text-tata-muted">RUL</dt>
                <dd className="font-semibold text-tata-ink">{cs.rul_hours?.toLocaleString()} h</dd>
              </div>
              <div>
                <dt className="text-[10px] font-semibold text-tata-muted">Failure Probability</dt>
                <dd className="font-semibold text-tata-ink">{cs.failure_probability_pct}%</dd>
              </div>
              <div>
                <dt className="text-[10px] font-semibold text-tata-muted">Health</dt>
                <dd>{cs.health_score}%</dd>
              </div>
              <div>
                <dt className="text-[10px] font-semibold text-tata-muted">Risk</dt>
                <dd className="font-medium uppercase text-amber-700">{String(cs.risk_level || "—")}</dd>
              </div>
            </dl>
          </Card>
        )}

        {rcc.evidence && rcc.evidence.length > 0 && (
          <Card title="Root Cause Chain" icon={GitBranch}>
            <p className="mb-2 font-medium text-tata-ink">{rcc.most_likely_cause}</p>
            <ul className="mb-2 space-y-1">
              {rcc.evidence.map((ev, i) => (
                <li key={i}>
                  <span className="font-medium text-tata-ink">Evidence {i + 1}:</span> {ev.label}
                  {ev.confidence_pct ? ` (${ev.confidence_pct}%)` : ""}
                </li>
              ))}
            </ul>
            {rcc.failure_path && rcc.failure_path.length > 0 && (
              <div className="rounded-lg bg-slate-50 p-2 font-mono text-[10px] text-tata-ink">
                {rcc.failure_path.join(" → ")}
              </div>
            )}
          </Card>
        )}

        {rb.components && rb.components.length > 0 && (
          <Card title="Risk Score Breakdown" icon={AlertTriangle}>
            <p className="mb-2 text-lg font-bold text-tata-ink">{rb.final_score_100}/100</p>
            <ul className="space-y-1">
              {rb.components.map((c) => (
                <li key={c.factor} className="flex justify-between gap-2">
                  <span>
                    {c.factor}: <strong className="text-tata-ink">{c.value}</strong>
                  </span>
                  <span className="text-[10px]">weight {c.weight_pct}%</span>
                </li>
              ))}
            </ul>
            {rb.reason && <p className="mt-2 text-[11px] italic">Reason: {rb.reason}</p>}
          </Card>
        )}

        {ke.items && ke.items.length > 0 && (
          <Card title="Knowledge Evidence" icon={BookOpen} defaultOpen={false}>
            {ke.items.map((item, i) => (
              <div key={i} className="mb-2 rounded-lg bg-tata-blue-pale/40 p-2">
                <p className="font-semibold text-tata-blue">{item.source}</p>
                <p className="mt-0.5 line-clamp-3">{item.excerpt}</p>
                {item.score != null && <p className="mt-1 text-[10px]">Relevance {Math.round(item.score * 100)}%</p>}
              </div>
            ))}
            {ke.confidence_pct != null && (
              <p className="font-medium text-tata-ink">Confidence: {ke.confidence_pct}%</p>
            )}
          </Card>
        )}

        {sim.projections && sim.projections.length > 0 && (
          <Card title="Scenario Simulation" icon={TrendingUp}>
            <div className="space-y-2">
              {sim.projections.map((p) => (
                <div key={p.label} className="rounded-lg border border-tata-border/50 p-2">
                  <p className="font-semibold text-tata-ink">{p.label}</p>
                  <p>
                    RUL {p.rul_hours}h · Failure {p.failure_probability_pct}%
                    {p.failure_probability_delta_pct != null && (
                      <span className={p.failure_probability_delta_pct > 0 ? " text-red-600" : " text-emerald-600"}>
                        {" "}
                        (Δ {p.failure_probability_delta_pct > 0 ? "+" : ""}
                        {p.failure_probability_delta_pct}%)
                      </span>
                    )}
                  </p>
                </div>
              ))}
            </div>
            {sim.recommended_action && (
              <p className="mt-2 font-medium text-amber-800">{sim.recommended_action}</p>
            )}
          </Card>
        )}

        {(bi.estimated_downtime_hours != null || bi.additional_failure_risk_pct != null) && (
          <Card title="Business Impact" icon={Factory}>
            <dl className="space-y-1">
              {bi.additional_failure_risk_pct != null && (
                <div className="flex justify-between">
                  <dt>Additional failure risk</dt>
                  <dd className="font-semibold text-red-700">+{Number(bi.additional_failure_risk_pct)}%</dd>
                </div>
              )}
              {bi.estimated_downtime_hours != null && (
                <div className="flex justify-between">
                  <dt>Potential downtime</dt>
                  <dd>{String(bi.estimated_downtime_hours)}h</dd>
                </div>
              )}
              {bi.estimated_production_loss_tons != null && (
                <div className="flex justify-between">
                  <dt>Production loss</dt>
                  <dd>{String(bi.estimated_production_loss_tons)}t</dd>
                </div>
              )}
              {bi.preventive_maintenance_cost_inr != null && (
                <div className="flex justify-between">
                  <dt>Preventive maintenance</dt>
                  <dd>{fmtInr(bi.preventive_maintenance_cost_inr)}</dd>
                </div>
              )}
              {bi.potential_savings_inr != null && (
                <div className="flex justify-between border-t border-tata-border/40 pt-1">
                  <dt className="font-medium text-tata-ink">Potential savings</dt>
                  <dd className="font-bold text-emerald-700">{fmtInr(bi.potential_savings_inr)}</dd>
                </div>
              )}
            </dl>
          </Card>
        )}
      </div>

      {trace.agents && trace.agents.length > 0 && (
        <Card title="Agent Execution Trace" icon={Cpu} defaultOpen={false}>
          <ul className="mb-2 space-y-0.5">
            {trace.agents.map((a) => (
              <li key={a.agent} className="flex items-center gap-2 text-tata-ink">
                <span className="text-emerald-600">✓</span>
                {a.label}
              </li>
            ))}
          </ul>
          {trace.execution_time_s != null && (
            <p className="mb-2">Execution time: <strong>{trace.execution_time_s}s</strong></p>
          )}
          {trace.intent_label && <p className="mb-2">Intent: {trace.intent_label}</p>}
          {trace.data_sources && (
            <div>
              <p className="mb-1 font-semibold text-tata-ink">Data sources</p>
              <p>{trace.data_sources.join(" · ")}</p>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
