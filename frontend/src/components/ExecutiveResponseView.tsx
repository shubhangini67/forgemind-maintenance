"use client";

import { useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Cpu,
  Factory,
  GitBranch,
  Layers,
  Package,
  Shield,
  TrendingUp,
} from "lucide-react";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { AgentOrchestrationPanel } from "@/components/AgentOrchestrationPanel";
import type { ExplainabilityBundle } from "@/components/ExplainabilityDashboard";
import type { AIReasoningPanelData } from "@/components/AIReasoningPanel";

function fmtInr(v: unknown) {
  const n = Number(v);
  if (Number.isNaN(n) || n === 0) return "—";
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(1)} Lakhs`;
  if (n >= 1_000) return `₹${Math.round(n / 1_000)}k`;
  return `₹${n.toLocaleString()}`;
}

function Collapsible({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: typeof Shield;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="overflow-hidden rounded-xl border border-tata-border/60 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-slate-50/80"
      >
        {open ? <ChevronUp className="h-4 w-4 text-tata-muted" /> : <ChevronDown className="h-4 w-4 text-tata-muted" />}
        <Icon className="h-4 w-4 text-tata-blue" />
        <span className="text-xs font-semibold text-tata-ink">{title}</span>
      </button>
      {open && <div className="border-t border-tata-border/40 px-3 py-3">{children}</div>}
    </section>
  );
}

function SectionHeader({ title, icon: Icon }: { title: string; icon: typeof Shield }) {
  return (
    <div className="mb-2 flex items-center gap-2 border-b border-tata-border/40 pb-2">
      <Icon className="h-4 w-4 text-tata-blue" />
      <p className="text-[10px] font-bold uppercase tracking-wider text-tata-ink">{title}</p>
    </div>
  );
}

function RoutingBadge({ data }: { data: ExplainabilityBundle }) {
  const log = data.routing_log;
  if (!log?.intent_label) return null;
  return (
    <p className="mb-2 text-[10px] text-tata-muted">
      {log.intent_label} · template: <span className="font-medium text-tata-blue">{log.response_template}</span>
      {log.agents_invoked?.length ? ` · ${log.agents_invoked.length} agent(s)` : " · synthesizer only"}
    </p>
  );
}

function AssetRankingView({ data }: { data: ExplainabilityBundle }) {
  const ranking = data.asset_ranking || data.intent_response || {};
  const rows = (ranking.ranked_assets as Record<string, unknown>[]) || [];
  const rec = ranking.recommendation as string | undefined;
  return (
    <section className="rounded-xl border border-tata-border/70 bg-white p-4 shadow-sm">
      <SectionHeader title="Asset Ranking by RUL" icon={TrendingUp} />
      <RoutingBadge data={data} />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-tata-border/60 text-[10px] uppercase text-tata-muted">
              <th className="py-1 pr-2">Rank</th>
              <th className="py-1 pr-2">Asset</th>
              <th className="py-1 pr-2">RUL</th>
              <th className="py-1 pr-2">Failure Prob</th>
              <th className="py-1 pr-2">Risk</th>
              <th className="py-1">Priority</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={String(r.rank)} className="border-b border-tata-border/30">
                <td className="py-1.5 pr-2 font-semibold">{String(r.rank)}</td>
                <td className="py-1.5 pr-2 font-medium text-tata-ink">{String(r.equipment_code)}</td>
                <td className="py-1.5 pr-2">{String(r.rul_display ?? r.rul_hours)}</td>
                <td className="py-1.5 pr-2">{String(r.failure_probability_pct)}%</td>
                <td className="py-1.5 pr-2">{String(r.risk_level)}</td>
                <td className="py-1.5 font-bold text-tata-blue">{String(r.priority)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rec && (
        <div className="mt-3 rounded-lg bg-tata-blue-pale/50 p-3 text-xs text-tata-ink">
          <p className="font-semibold text-tata-blue">Maintenance Priority</p>
          <p className="mt-1">{rec}</p>
        </div>
      )}
    </section>
  );
}

function BusinessImpactView({ data }: { data: ExplainabilityBundle }) {
  const bi = data.business_impact_detail || data.intent_response || {};
  return (
    <section className="rounded-xl border border-tata-border/70 bg-white p-4 shadow-sm">
      <SectionHeader title="Business Impact Analysis" icon={Factory} />
      <RoutingBadge data={data} />
      <dl className="grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-[10px] text-tata-muted">Estimated Downtime</dt>
          <dd className="text-lg font-bold text-tata-ink">{bi.downtime_estimate_hours != null ? `${bi.downtime_estimate_hours}h` : "—"}</dd>
        </div>
        <div>
          <dt className="text-[10px] text-tata-muted">Production Loss</dt>
          <dd className="text-lg font-bold text-tata-ink">{bi.production_loss_tons != null ? `${bi.production_loss_tons} tons` : "—"}</dd>
        </div>
        <div>
          <dt className="text-[10px] text-tata-muted">Revenue / Cost Exposure</dt>
          <dd className="text-lg font-bold text-red-700">{fmtInr(bi.revenue_exposure_inr)}</dd>
        </div>
        <div>
          <dt className="text-[10px] text-tata-muted">Repair Cost</dt>
          <dd className="font-semibold text-tata-ink">{fmtInr(bi.repair_cost_inr)}</dd>
        </div>
        <div>
          <dt className="text-[10px] text-tata-muted">ROI of Preventive Maintenance</dt>
          <dd className="font-semibold text-emerald-700">
            {bi.preventive_roi_pct != null ? `${bi.preventive_roi_pct}%` : "—"} ({fmtInr(bi.potential_savings_inr)} savings)
          </dd>
        </div>
        <div>
          <dt className="text-[10px] text-tata-muted">Failure Probability (now)</dt>
          <dd className="font-semibold text-tata-ink">{bi.failure_probability_pct != null ? `${bi.failure_probability_pct}%` : "—"}</dd>
        </div>
      </dl>
    </section>
  );
}

function RootCauseView({ data }: { data: ExplainabilityBundle }) {
  const rca = data.root_cause_analysis || data.intent_response || {};
  const path = (rca.failure_path as string[]) || data.root_cause_chain?.failure_path || [];
  const sensor = (rca.sensor_evidence as string[]) || [];
  const pattern = (rca.pattern_evidence as { label?: string; detail?: string }[]) || data.root_cause_chain?.evidence || [];
  return (
    <section className="rounded-xl border border-tata-border/70 bg-white p-4 shadow-sm">
      <SectionHeader title="Root Cause Analysis" icon={GitBranch} />
      <RoutingBadge data={data} />
      <p className="mb-2 text-sm font-semibold text-tata-ink">{String(rca.most_likely_cause || "—")}</p>
      <p className="mb-3 text-xs text-tata-muted">Failure probability: {String(rca.failure_probability_pct ?? "—")}%</p>
      {path.length > 0 && (
        <div className="mb-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-tata-ink">{path.join(" → ")}</div>
      )}
      {sensor.length > 0 && (
        <>
          <p className="mb-1 text-[10px] font-bold uppercase text-tata-muted">Sensor Evidence</p>
          <ul className="mb-3 list-inside list-disc text-xs text-tata-ink">
            {sensor.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </>
      )}
      {pattern.length > 0 && (
        <>
          <p className="mb-1 text-[10px] font-bold uppercase text-tata-muted">Historical Evidence</p>
          <ul className="list-inside list-disc text-xs text-tata-muted">
            {pattern.map((ev, i) => (
              <li key={i}>{ev.label}{ev.detail ? ` — ${ev.detail}` : ""}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function MaintenancePlanView({ data }: { data: ExplainabilityBundle }) {
  const plan = data.maintenance_plan_detail || data.intent_response || {};
  const blocks = [
    { label: "Immediate Actions", items: plan.immediate_actions as string[] },
    { label: "Next Shift Actions", items: plan.next_shift_actions as string[] },
    { label: "Long-Term Actions", items: plan.long_term_actions as string[] },
  ];
  return (
    <section className="rounded-xl border border-tata-border/70 bg-white p-4 shadow-sm">
      <SectionHeader title="Maintenance Plan" icon={ClipboardList} />
      <RoutingBadge data={data} />
      <div className="grid gap-3 sm:grid-cols-3">
        {blocks.map(({ label, items }) =>
          items?.length ? (
            <div key={label}>
              <p className="mb-1 text-[10px] font-bold uppercase text-tata-muted">{label}</p>
              <ul className="list-inside list-disc space-y-0.5 text-xs text-tata-ink">
                {items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null
        )}
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg bg-slate-50 p-2 text-xs">
          <p className="font-semibold text-tata-ink">Required Manpower</p>
          <p className="text-tata-muted">{String(plan.required_manpower || "—")}</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2 text-xs">
          <p className="font-semibold text-tata-ink">Required Spares</p>
          <ul className="mt-1 list-inside list-disc text-tata-muted">
            {((plan.required_spares as string[]) || []).map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function SopKnowledgeView({ data }: { data: ExplainabilityBundle }) {
  const sop = data.sop_knowledge || data.intent_response || {};
  const docs = (sop.documents as { source?: string; excerpt?: string; document_type?: string }[]) || data.knowledge_evidence?.items || [];
  const steps = (sop.procedure_steps as string[]) || [];
  const safety = (sop.safety_notes as string[]) || [];
  return (
    <section className="rounded-xl border border-tata-border/70 bg-white p-4 shadow-sm">
      <SectionHeader title="SOP & Manual References" icon={BookOpen} />
      <RoutingBadge data={data} />
      {docs.map((d, i) => (
        <div key={i} className="mb-2 rounded-lg border border-tata-border/50 bg-slate-50/80 p-2">
          <p className="text-xs font-semibold text-tata-blue">{d.source}</p>
          <p className="mt-1 line-clamp-4 text-[11px] text-tata-muted">{d.excerpt}</p>
        </div>
      ))}
      {steps.length > 0 && (
        <>
          <p className="mb-1 mt-2 text-[10px] font-bold uppercase text-tata-muted">Procedure Steps</p>
          <ul className="list-inside list-decimal text-xs text-tata-ink">
            {steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </>
      )}
      {safety.length > 0 && (
        <>
          <p className="mb-1 mt-2 text-[10px] font-bold uppercase text-amber-700">Safety Notes</p>
          <ul className="list-inside list-disc text-xs text-amber-900">
            {safety.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function CriticalSparesView({ data }: { data: ExplainabilityBundle }) {
  const inv = data.critical_spares || data.intent_response || {};
  const spares = (inv.critical_spares as Record<string, unknown>[]) || [];
  return (
    <section className="rounded-xl border border-tata-border/70 bg-white p-4 shadow-sm">
      <SectionHeader title="Critical Spare Parts" icon={Package} />
      <RoutingBadge data={data} />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b text-[10px] uppercase text-tata-muted">
              <th className="py-1 pr-2">Part</th>
              <th className="py-1 pr-2">Stock</th>
              <th className="py-1 pr-2">Lead</th>
              <th className="py-1">Status</th>
            </tr>
          </thead>
          <tbody>
            {spares.map((s, i) => (
              <tr key={i} className="border-b border-tata-border/30">
                <td className="py-1.5 pr-2 font-medium">{String(s.part_number)} {String(s.name || "").slice(0, 20)}</td>
                <td className="py-1.5 pr-2">{String(s.quantity_available)}</td>
                <td className="py-1.5 pr-2">{String(s.lead_time_days)}d</td>
                <td className="py-1.5 font-bold text-red-700">{String(s.criticality)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {inv.recommendation != null && (
        <p className="mt-3 text-xs text-tata-ink">{String(inv.recommendation)}</p>
      )}
    </section>
  );
}

function FailureSimulationView({ data, content }: { data: ExplainabilityBundle; content?: string }) {
  const sim = (data.scenario_simulation || data.failure_simulation?.scenario_simulation || {}) as Record<string, unknown>;
  const failSim = data.failure_simulation as Record<string, unknown> | undefined;
  const rec = failSim?.recommended_action ?? sim.recommended_action;
  const tableMd =
    content && content.includes("| Scenario |")
      ? content.split("\n").slice(content.split("\n").findIndex((l) => l.includes("| Scenario |"))).join("\n").split("\n\n###")[0]
      : null;

  return (
    <section className="space-y-3">
      <div className="rounded-xl border border-tata-border/70 bg-white p-4 shadow-sm">
        <SectionHeader title="Failure Scenario Simulation" icon={Layers} />
        <RoutingBadge data={data} />
        {tableMd ? (
          <MarkdownRenderer content={tableMd} />
        ) : (
          <div className="space-y-1 text-xs">
            {(sim.projections as { label?: string; rul_hours?: number; failure_probability_pct?: number }[])?.map((p) => (
              <p key={p.label}>
                <strong>{p.label}</strong> — RUL {p.rul_hours}h · {p.failure_probability_pct}% failure
              </p>
            ))}
          </div>
        )}
        {rec != null && rec !== "" && (
          <div className="mt-3 rounded-lg bg-amber-50 p-3 text-xs font-medium text-amber-900">
            Recommended intervention: {String(rec)}
          </div>
        )}
      </div>
    </section>
  );
}

type Props = {
  explainability?: ExplainabilityBundle | null;
  reasoningPanel?: AIReasoningPanelData | null;
  content?: string;
  compact?: boolean;
};

export function ExecutiveResponseView({ explainability, reasoningPanel, content, compact = false }: Props) {
  const data = explainability || {};
  const template = data.response_template || "root_cause_analysis";
  const hasChatContent = Boolean(content && content.trim().length > 30);

  const primary = (() => {
    switch (template) {
      case "asset_ranking":
        return <AssetRankingView data={data} />;
      case "business_impact":
        return <BusinessImpactView data={data} />;
      case "root_cause_analysis":
        return <RootCauseView data={data} />;
      case "maintenance_plan":
        return <MaintenancePlanView data={data} />;
      case "sop_knowledge":
        return <SopKnowledgeView data={data} />;
      case "critical_spares":
        return <CriticalSparesView data={data} />;
      case "failure_simulation":
        return <FailureSimulationView data={data} content={content} />;
      default:
        if (content) return <MarkdownRenderer content={content} />;
        return <RootCauseView data={data} />;
    }
  })();

  if (!data.response_template && !content && !data.intent_response) {
    if (content) return <MarkdownRenderer content={content} />;
    return null;
  }

  return (
    <div className={`space-y-3 ${compact ? "text-xs" : "text-sm"}`}>
      {hasChatContent && (
        <div className="prose-chat">
          <MarkdownRenderer content={content!} />
        </div>
      )}

      {hasChatContent ? (
        <Collapsible title="Technical analysis & evidence" icon={GitBranch} defaultOpen={false}>
          {primary}
        </Collapsible>
      ) : (
        primary
      )}

      {data.root_cause_chain?.failure_path && template !== "root_cause_analysis" && !hasChatContent && (
        <Collapsible title="Root Cause Analysis" icon={GitBranch}>
          <div className="text-xs">{data.root_cause_chain.failure_path.join(" → ")}</div>
        </Collapsible>
      )}

      {data.knowledge_evidence?.items?.length && template !== "sop_knowledge" ? (
        <Collapsible title="SOP & Manual References" icon={BookOpen}>
          {data.knowledge_evidence.items.map((item, i) => (
            <div key={i} className="mb-2 text-xs">
              <p className="font-semibold text-tata-blue">{item.source}</p>
              <p className="text-tata-muted">{item.excerpt}</p>
            </div>
          ))}
        </Collapsible>
      ) : null}

      {reasoningPanel?.steps?.length ? (
        <Collapsible title="Agent Execution Trace" icon={Cpu}>
          <AgentOrchestrationPanel panel={reasoningPanel} compact={compact} embedMode />
        </Collapsible>
      ) : null}
    </div>
  );
}
