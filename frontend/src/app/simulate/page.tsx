"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { AIReasoningPanel, type AIReasoningPanelData } from "@/components/AIReasoningPanel";
import { DownloadPdfButton } from "@/components/DownloadPdfButton";
import { RiskBadge } from "@/components/RiskBadge";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  Brain,
  CheckCircle2,
  Clock,
  Factory,
  GitCompare,
  IndianRupee,
  Package,
  Scale,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";

type DelayPreset = "24h" | "3d" | "7d" | "custom" | "immediate";

const DELAY_MAP: Record<Exclude<DelayPreset, "custom" | "immediate">, number> = {
  "24h": 24,
  "3d": 72,
  "7d": 168,
};

function fmtL(n: number | undefined) {
  if (n == null) return "—";
  if (n >= 100000) return `₹${(n / 100000).toFixed(2)}L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

function fmtTons(n: number | undefined) {
  if (n == null) return "—";
  return `${n.toLocaleString("en-IN")} Tons`;
}

function formatDelayLabel(result: any): string {
  if (!result) return "After delay";
  if (result.mode === "immediate_failure") return "After immediate failure";
  if (result.selected_delay_label) return `After ${result.selected_delay_label.toLowerCase()}`;
  const h = result.selected_delay_hours ?? result.selected_scenario?.delay_hours;
  if (h == null) return "After delay";
  if (h === 0) return "If maintained today";
  if (h === 24) return "After 24-hour delay";
  if (h === 72) return "After 3-day delay";
  if (h === 168) return "After 7-day delay";
  if (h % 24 === 0) return `After ${h / 24}-day delay`;
  return `After ${h}-hour delay`;
}

function scenarioBannerText(result: any): string {
  if (!result) return "";
  if (result.mode === "immediate_failure") return "Immediate failure simulation";
  return result.selected_delay_label || result.selected_scenario?.label || formatDelayLabel(result).replace(/^After /i, "");
}

export default function SimulatePage() {
  const router = useRouter();
  const [equipment, setEquipment] = useState<any[]>([]);
  const [equipmentId, setEquipmentId] = useState(1);
  const [delayPreset, setDelayPreset] = useState<DelayPreset>("3d");
  const [customHours, setCustomHours] = useState(120);
  const [result, setResult] = useState<any>(null);
  const [reasoningPanel, setReasoningPanel] = useState<AIReasoningPanelData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) router.push("/");
    else {
      api.equipment().then((eq) => {
        setEquipment(eq);
        if (eq[0]) setEquipmentId(eq[0].id);
      });
    }
  }, [router]);

  useEffect(() => {
    if (result?.reasoning_panel) setReasoningPanel(result.reasoning_panel);
  }, [result]);

  const selectedEq = equipment.find((e) => e.id === equipmentId);

  async function run() {
    setLoading(true);
    setError("");
    setResult(null);
    setReasoningPanel(null);
    try {
      const immediate = delayPreset === "immediate";
      const payload: Parameters<typeof api.simulateDecision>[0] = {
        equipment_id: equipmentId,
        mode: immediate ? "immediate_failure" : "delay",
        failure_mode: "bearing_failure",
      };
      if (!immediate) {
        if (delayPreset === "custom") {
          payload.custom_delay_hours = customHours;
        } else {
          payload.delay_hours = DELAY_MAP[delayPreset as keyof typeof DELAY_MAP];
        }
      }
      const res = await api.simulateDecision(payload);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  }

  const current = result?.current_state;
  const after = result?.after_delay || result?.selected_scenario;
  const fin = result?.financial_impact;
  const spares = result?.spare_availability;
  const rec = result?.recommendation;
  const afterDelayLabel = result ? formatDelayLabel(result) : "After delay";
  const scenarioLabel = result ? scenarioBannerText(result) : "";

  return (
    <Shell>
      <PageHeader
        label="Maintenance Decision Intelligence"
        title="AI Maintenance Decision Simulator"
        subtitle="Understand the consequences of maintenance decisions before you act — delay vs repair, failure cascade, cost, and AI-backed recommendations."
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <div className="grid gap-6 xl:grid-cols-12">
        {/* Controls */}
        <div className="space-y-4 xl:col-span-3">
          <div className="panel">
            <h2 className="panel-title mb-4 flex items-center gap-2">
              <Scale className="h-5 w-5 text-tata-blue" /> Decision Inputs
            </h2>
            <div className="space-y-4">
              <div>
                <label className="stat-label mb-1 block">Asset</label>
                <select className="input w-full" value={equipmentId} onChange={(e) => setEquipmentId(Number(e.target.value))}>
                  {equipment.map((eq) => (
                    <option key={eq.id} value={eq.id}>
                      {eq.equipment_code} — {eq.name}
                    </option>
                  ))}
                </select>
                {selectedEq && (
                  <p className="mt-1 text-xs text-tata-muted">
                    {selectedEq.location} · Criticality {selectedEq.criticality}/5
                  </p>
                )}
              </div>

              <div>
                <label className="stat-label mb-2 block">Delay duration</label>
                <div className="grid grid-cols-2 gap-2">
                  {(
                    [
                      ["24h", "24 Hours"],
                      ["3d", "3 Days"],
                      ["7d", "7 Days"],
                      ["custom", "Custom"],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setDelayPreset(id)}
                      className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                        delayPreset === id
                          ? "border-tata-blue bg-tata-blue text-white"
                          : "border-tata-border bg-white text-tata-ink hover:border-tata-blue/40"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {delayPreset === "custom" && (
                  <div className="mt-2">
                    <input
                      type="number"
                      min={1}
                      max={720}
                      className="input mt-1 w-full"
                      value={customHours}
                      onChange={(e) => setCustomHours(Number(e.target.value))}
                    />
                    <p className="mt-1 text-[10px] text-tata-muted">Custom delay in hours</p>
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => setDelayPreset("immediate")}
                className={`w-full rounded-lg border px-3 py-2.5 text-left text-sm font-semibold transition ${
                  delayPreset === "immediate"
                    ? "border-red-500 bg-red-50 text-red-700"
                    : "border-tata-border bg-white text-tata-ink hover:border-red-300"
                }`}
              >
                <Zap className="mb-1 inline h-4 w-4" /> Simulate Immediate Failure
              </button>

              <button onClick={run} className="btn-primary w-full py-3" disabled={loading}>
                {loading ? "Running decision intelligence…" : "Run Decision Simulation"}
              </button>
            </div>
          </div>

          <div className="panel border-l-4 border-l-tata-blue bg-tata-blue-pale/20">
            <p className="text-xs font-semibold uppercase tracking-wider text-tata-blue">Questions answered</p>
            <ul className="mt-2 space-y-1.5 text-xs text-tata-muted">
              <li>• What happens if we delay maintenance?</li>
              <li>• What happens if this asset fails?</li>
              <li>• What is the best maintenance decision?</li>
            </ul>
          </div>
        </div>

        {/* Results */}
        <div className="xl:col-span-9">
          {!result && !loading && (
            <div className="panel flex min-h-[420px] flex-col items-center justify-center bg-gradient-to-br from-white to-tata-blue-pale/20 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-tata-blue to-tata-blue-light text-white shadow-lg">
                <GitCompare className="h-8 w-8" />
              </div>
              <p className="text-xl font-semibold text-tata-ink">Maintenance Decision Intelligence</p>
              <p className="mt-2 max-w-lg text-sm leading-relaxed text-tata-muted">
                Select an asset and a delay scenario. The simulator projects failure probability, RUL erosion, risk
                escalation, downtime, production loss, financial exposure, spare constraints, and downstream cascade —
                then compares maintain-today vs delay options.
              </p>
            </div>
          )}

          {loading && (
            <div className="panel flex min-h-[420px] flex-col items-center justify-center gap-4">
              <div className="flex items-center gap-2 text-sm text-tata-blue">
                <span className="h-2 w-2 animate-pulse rounded-full bg-tata-blue" />
                Predictive Agent → Inventory Agent → Risk Engine → Planner → Advisor…
              </div>
              <p className="text-xs text-tata-muted">Computing delay scenarios and comparison matrix</p>
            </div>
          )}

          {result && (
            <div className="space-y-4">
              {/* Selected scenario context */}
              <div className="flex flex-wrap items-center gap-3 rounded-xl border border-tata-blue/25 bg-tata-blue-pale/40 px-4 py-3">
                <Clock className="h-5 w-5 shrink-0 text-tata-blue" />
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-tata-blue">Simulated scenario</p>
                  <p className="text-sm font-semibold text-tata-ink">{scenarioLabel}</p>
                  {result.selected_delay_hours != null && result.mode !== "immediate_failure" && (
                    <p className="text-xs text-tata-muted">
                      {result.selected_scenario?.label} · {result.selected_delay_hours} hours deferral
                    </p>
                  )}
                </div>
                <span className="rounded-full bg-tata-blue px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-white">
                  {result.mode === "immediate_failure" ? "Failure mode" : "Delay analysis"}
                </span>
              </div>

              {/* Hero recommendation */}
              <div className="panel-flush overflow-hidden">
                <div className="bg-gradient-to-r from-tata-blue via-[#006BB8] to-tata-blue-light px-5 py-5 text-white">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-white/70">
                        AI Recommendation · {rec?.confidence_pct}% confidence · {scenarioLabel}
                      </p>
                      <h2 className="mt-1 text-2xl font-bold">{rec?.action}</h2>
                      <p className="mt-2 max-w-2xl text-sm text-white/90">{rec?.reason}</p>
                    </div>
                    <DownloadPdfButton
                      reportType="decision"
                      equipmentId={result.equipment_id}
                      payload={result}
                      label="Download PDF"
                      variant="primary"
                    />
                  </div>
                </div>
              </div>

              {/* Current vs After */}
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-tata-muted">
                  Current state vs {afterDelayLabel.toLowerCase()}
                </p>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCompare
                  label="Failure Probability"
                  icon={Target}
                  current={`${current?.failure_probability_pct}%`}
                  after={`${after?.failure_probability_pct}%`}
                  afterLabel={afterDelayLabel}
                  warn={after?.failure_probability_pct > current?.failure_probability_pct}
                />
                <MetricCompare
                  label="Remaining Useful Life"
                  icon={Clock}
                  current={`${current?.rul_days} Days`}
                  after={`${after?.rul_days} Days`}
                  afterLabel={afterDelayLabel}
                  warn={after?.rul_days < current?.rul_days}
                />
                <MetricCompare
                  label="Risk Escalation"
                  icon={AlertTriangle}
                  current={current?.risk_level?.toUpperCase()}
                  after={after?.risk_escalation || after?.risk_level?.toUpperCase()}
                  afterLabel={afterDelayLabel}
                  warn
                />
                <MetricCompare
                  label="Expected Downtime"
                  icon={Factory}
                  current="—"
                  after={`${result.selected_scenario?.downtime_hours ?? 0} Hours`}
                  afterLabel={afterDelayLabel}
                  warn={(result.selected_scenario?.downtime_hours ?? 0) > 8}
                />
                </div>
              </div>

              {/* Financial + Production + Spares row */}
              <div className="stat-grid grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="stat-card border-l-4 border-l-orange-400">
                  <p className="stat-label">Production Impact</p>
                  <p className="stat-value">{fmtTons(result.selected_scenario?.production_loss_tons)}</p>
                </div>
                <div className="stat-card border-l-4 border-l-red-400">
                  <p className="stat-label">Downtime Cost</p>
                  <p className="stat-value">{fmtL(fin?.downtime_cost_inr)}</p>
                </div>
                <div className="stat-card border-l-4 border-l-amber-500">
                  <p className="stat-label">Maintenance Cost</p>
                  <p className="stat-value">{fmtL(fin?.maintenance_cost_inr)}</p>
                </div>
                <div className="stat-card border-l-4 border-l-emerald-500">
                  <p className="stat-label">Avoided Loss</p>
                  <p className="stat-value text-emerald-600">{fmtL(fin?.avoided_loss_inr)}</p>
                </div>
              </div>

              {/* Spares + Downstream */}
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="panel">
                  <h3 className="panel-title mb-3 flex items-center gap-2">
                    <Package className="h-5 w-5" /> Spare Availability
                  </h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div className="rounded-lg border border-tata-border bg-white p-3">
                      <p className="text-[10px] font-semibold uppercase text-tata-muted">Bearing Stock</p>
                      <p className={`text-2xl font-bold ${spares?.bearing_stock <= 0 ? "text-red-600" : "text-tata-ink"}`}>
                        {spares?.bearing_stock ?? 0}
                      </p>
                    </div>
                    <div className="rounded-lg border border-tata-border bg-white p-3">
                      <p className="text-[10px] font-semibold uppercase text-tata-muted">Lead Time</p>
                      <p className="text-2xl font-bold">{spares?.lead_time_days ?? "—"} Days</p>
                    </div>
                  </div>
                  <p className="mt-3 text-sm">
                    Procurement Risk:{" "}
                    <span className="font-bold uppercase text-red-600">{spares?.procurement_risk || "—"}</span>
                  </p>
                  {spares?.part_name && <p className="mt-1 text-xs text-tata-muted">{spares.part_name}</p>}
                </div>

                <div className="panel">
                  <h3 className="panel-title mb-3 flex items-center gap-2">
                    <ArrowRight className="h-5 w-5" /> Downstream Impact
                  </h3>
                  {result.downstream_impact?.affected_assets?.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {result.downstream_impact.affected_assets.map((code: string) => (
                        <span key={code} className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-semibold text-red-700">
                          {code}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-tata-muted">No downstream cascade for selected scenario — asset contained.</p>
                  )}
                  {result.inputs_snapshot && (
                    <p className="mt-3 text-xs text-tata-muted">
                      Priority #{result.inputs_snapshot.priority_rank ?? "—"} ·{" "}
                      {result.inputs_snapshot.open_alerts} open alerts · Isolation Forest{" "}
                      {result.inputs_snapshot.isolation_forest_anomaly ? "anomaly detected" : "normal"}
                    </p>
                  )}
                </div>
              </div>

              {/* Comparison mode */}
              <div className="panel">
                <h3 className="panel-title mb-4 flex items-center gap-2">
                  <GitCompare className="h-5 w-5" /> Decision Comparison Mode
                </h3>
                <div className="grid gap-4 lg:grid-cols-3">
                  {(result.comparison || []).map((s: any) => (
                    <ComparisonCard
                      key={s.id}
                      scenario={s}
                      isBest={s.is_best}
                      isSelected={s.id === result.selected_scenario_id}
                    />
                  ))}
                </div>
              </div>

              {/* AI Explanation chain */}
              <div className="panel border-l-4 border-l-indigo-500">
                <h3 className="panel-title mb-4 flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-indigo-600" /> Why This Recommendation?
                </h3>
                <div className="mx-auto max-w-lg">
                  {(result.reasoning_chain || []).map((step: any, i: number) => (
                    <div key={step.step}>
                      <div className="rounded-xl border border-tata-border bg-gradient-to-r from-white to-indigo-50/40 p-4">
                        <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">{step.step}</p>
                        <p className="mt-1 text-sm leading-relaxed text-tata-ink/90">{step.detail}</p>
                      </div>
                      {i < (result.reasoning_chain?.length || 0) - 1 && (
                        <div className="flex justify-center py-1 text-indigo-400">
                          <ArrowDown className="h-4 w-4" />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {(reasoningPanel || result.agent_trace?.length) && (
                <AIReasoningPanel
                  panel={reasoningPanel}
                  loading={false}
                  provider={result.llm_provider}
                  defaultExpanded={false}
                />
              )}

              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/chat?equipment=${equipmentId}&q=${encodeURIComponent(
                    `Explain the maintenance decision for ${result.equipment_code} — why ${rec?.action}?`
                  )}`}
                  className="btn-secondary inline-flex items-center gap-2"
                >
                  <Brain className="h-4 w-4" /> Ask AI to explain
                </Link>
                <Link href={`/diagnose?equipment=${equipmentId}`} className="btn-ghost inline-flex">
                  Run formal diagnosis
                </Link>
                <Link href="/priority" className="btn-ghost inline-flex">
                  View priority queue
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </Shell>
  );
}

function MetricCompare({
  label,
  icon: Icon,
  current,
  after,
  afterLabel = "After delay",
  warn,
}: {
  label: string;
  icon: typeof Target;
  current: string;
  after: string;
  afterLabel?: string;
  warn?: boolean;
}) {
  const shortAfter =
    afterLabel.length > 28 ? afterLabel.replace(/^After /i, "").slice(0, 24) + "…" : afterLabel.replace(/^After /i, "");
  return (
    <div className="panel">
      <div className="mb-2 flex items-center gap-2">
        <Icon className="h-4 w-4 text-tata-blue" />
        <p className="stat-label">{label}</p>
      </div>
      <div className="flex items-end justify-between gap-2">
        <div>
          <p className="text-[10px] uppercase text-tata-muted">Current</p>
          <p className="text-lg font-semibold text-tata-ink">{current}</p>
        </div>
        <ArrowRight className="h-4 w-4 shrink-0 text-tata-muted" />
        <div className="text-right">
          <p className="text-[10px] uppercase text-tata-muted" title={afterLabel}>
            {shortAfter || "After delay"}
          </p>
          <p className={`text-lg font-bold ${warn ? "text-red-600" : "text-tata-ink"}`}>{after}</p>
        </div>
      </div>
    </div>
  );
}

function ComparisonCard({
  scenario,
  isBest,
  isSelected,
}: {
  scenario: any;
  isBest?: boolean;
  isSelected?: boolean;
}) {
  return (
    <div
      className={`relative rounded-xl border p-4 ${
        isSelected
          ? "border-tata-blue bg-tata-blue-pale/40 ring-2 ring-tata-blue/35"
          : isBest
            ? "border-emerald-500 bg-emerald-50/50 ring-2 ring-emerald-500/30"
            : "border-tata-border bg-white"
      }`}
    >
      {isSelected && (
        <span className="absolute -top-2.5 left-3 inline-flex items-center gap-1 rounded-full bg-tata-blue px-2 py-0.5 text-[10px] font-bold uppercase text-white">
          Your selection
        </span>
      )}
      {isBest && (
        <span className="absolute -top-2.5 right-3 inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-bold uppercase text-white">
          <CheckCircle2 className="h-3 w-3" /> Best option
        </span>
      )}
      <p className="font-semibold text-tata-ink">{scenario.label}</p>
      <div className="mt-3 space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-tata-muted">Risk</span>
          <RiskBadge level={scenario.risk_level} />
        </div>
        <div className="flex justify-between">
          <span className="text-tata-muted">Failure prob</span>
          <span className="font-semibold">{scenario.failure_probability_pct}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-tata-muted">Downtime</span>
          <span className="font-semibold">{scenario.downtime_hours}h</span>
        </div>
        <div className="flex justify-between">
          <span className="text-tata-muted">Production</span>
          <span className="font-semibold">{scenario.production_loss_tons?.toLocaleString()} t</span>
        </div>
        <div className="flex justify-between border-t border-tata-border pt-2">
          <span className="text-tata-muted">Net exposure</span>
          <span className="font-bold text-tata-ink">{fmtL(scenario.net_exposure_inr)}</span>
        </div>
      </div>
    </div>
  );
}
