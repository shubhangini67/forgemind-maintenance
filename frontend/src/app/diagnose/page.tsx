"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { AIReasoningPanel, reasoningFromThoughts, type AIReasoningPanelData } from "@/components/AIReasoningPanel";
import { FeedbackBar } from "@/components/FeedbackBar";
import { DownloadPdfButton } from "@/components/DownloadPdfButton";
import { ProcureRiskPanel } from "@/components/ProcureRiskPanel";
import { RiskBadge } from "@/components/RiskBadge";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Brain, Stethoscope } from "lucide-react";

function AiSummaryBody({ text }: { text: string }) {
  const lines = text.split("\n").filter((line) => line.trim());
  return (
    <div className="prose-chat space-y-2 text-sm leading-relaxed text-tata-ink/90">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={i} className="mt-4 text-sm font-semibold text-tata-blue first:mt-0">
              {trimmed.slice(3)}
            </h3>
          );
        }
        if (/^\d+\.\s/.test(trimmed)) {
          return (
            <p key={i} className="pl-1">
              {trimmed}
            </p>
          );
        }
        if (trimmed.startsWith("- ")) {
          return (
            <p key={i} className="pl-3 before:mr-2 before:content-['•']">
              {trimmed.slice(2)}
            </p>
          );
        }
        return <p key={i}>{trimmed}</p>;
      })}
    </div>
  );
}

export default function DiagnosePage() {
  const router = useRouter();
  const [equipment, setEquipment] = useState<any[]>([]);
  const [form, setForm] = useState({
    equipment_id: 2,
    symptoms: "",
    fault_codes: "",
    incident_description: "",
  });
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [reasoningPanel, setReasoningPanel] = useState<AIReasoningPanelData | null>(null);

  useEffect(() => {
    if (!getToken()) router.push("/");
    else
      api.equipment().then((eq) => {
        setEquipment(eq);
        if (eq.length) setForm((f) => ({ ...f, equipment_id: eq[0].id }));
      });
  }, [router]);

  useEffect(() => {
    if (result?.reasoning_panel || result?.agent_thoughts?.length) {
      setReasoningPanel(
        result.reasoning_panel ||
          reasoningFromThoughts(result.agent_thoughts, result.citations, result.llm_provider)
      );
    }
  }, [result]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    setReasoningPanel(null);
    try {
      const res = await api.diagnose({
        equipment_id: form.equipment_id,
        symptoms: form.symptoms,
        fault_codes: form.fault_codes.split(/[\s,]+/).filter(Boolean),
        incident_description: form.incident_description,
      });
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Diagnosis failed — check backend");
    } finally {
      setLoading(false);
    }
  }

  const aiText = result?.ai_summary || result?.root_cause_analysis || "";

  return (
    <Shell>
      <PageHeader
        title="Equipment Diagnosis"
        subtitle="Formal fault diagnosis with root cause analysis via the supervisor-led LangGraph agent pipeline."
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <div className="section-stack">
        <form onSubmit={submit} className="panel">
          <h2 className="panel-title mb-4 flex items-center gap-2">
            <Stethoscope className="h-5 w-5" /> Operational & Failure Inputs
          </h2>
          <div className="grid gap-4 lg:grid-cols-12 lg:items-end">
            <div className="lg:col-span-4">
              <label className="stat-label mb-1 block">Equipment</label>
              <select
                className="input"
                value={form.equipment_id}
                onChange={(e) => setForm({ ...form, equipment_id: Number(e.target.value) })}
              >
                {equipment.map((eq) => (
                  <option key={eq.id} value={eq.id}>
                    {eq.equipment_code} — {eq.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="lg:col-span-4">
              <label className="stat-label mb-1 block">Symptoms</label>
              <textarea
                className="input min-h-[72px] lg:min-h-[42px]"
                placeholder="Elevated vibration, overheating, unusual noise…"
                value={form.symptoms}
                onChange={(e) => setForm({ ...form, symptoms: e.target.value })}
                required
              />
            </div>
            <div className="lg:col-span-4">
              <label className="stat-label mb-1 block">Fault Codes</label>
              <input
                className="input"
                placeholder="E-2041, F-102 (comma separated)"
                value={form.fault_codes}
                onChange={(e) => setForm({ ...form, fault_codes: e.target.value })}
              />
            </div>
            <div className="lg:col-span-8">
              <label className="stat-label mb-1 block">Incident Description</label>
              <textarea
                className="input min-h-[72px] lg:min-h-[42px]"
                placeholder="Production delay, breakdown summary…"
                value={form.incident_description}
                onChange={(e) => setForm({ ...form, incident_description: e.target.value })}
              />
            </div>
            <div className="lg:col-span-4">
              <button type="submit" className="btn-primary w-full" disabled={loading}>
                {loading ? "Running agent diagnosis…" : "Run Diagnosis"}
              </button>
            </div>
          </div>
        </form>

        {!result && !loading ? (
          <div className="panel flex min-h-[240px] flex-col items-center justify-center gap-3 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-tata-blue to-tata-blue-light text-white shadow-md">
              <Brain className="h-7 w-7" />
            </div>
            <p className="text-sm font-medium text-tata-ink">Submit symptoms to generate a diagnosis</p>
            <p className="max-w-lg text-xs text-tata-muted">
              Results appear below in a balanced layout — assessment metrics, engineer summary, root causes, and maintenance actions.
            </p>
          </div>
        ) : loading ? (
          <div className="panel flex min-h-[240px] items-center justify-center">
            <p className="animate-pulse text-sm text-tata-muted">Analyzing sensors, SOPs, and fault patterns…</p>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-medium text-tata-ink">
                Diagnosis for{" "}
                <span className="font-semibold text-tata-blue">
                  {equipment.find((e) => e.id === result.equipment_id)?.equipment_code || "asset"}
                </span>
              </p>
              <DownloadPdfButton
                reportType="diagnosis"
                equipmentId={result.equipment_id}
                payload={result}
                label="Download Diagnosis PDF"
              />
            </div>

            {(result.remaining_useful_life_hours != null ||
              result.failure_probability != null ||
              result.spare_stock != null ||
              result.procurement_risk) && (
              <div className="panel">
                <h3 className="panel-title mb-4">Assessment Overview</h3>
                <div className="grid gap-4 xl:grid-cols-2">
                  {(result.remaining_useful_life_hours != null || result.failure_probability != null) && (
                    <div className="grid gap-3 sm:grid-cols-3">
                      {result.remaining_useful_life_hours != null && (
                        <div className="metric-tile rounded-lg">
                          <div>
                            <p className="stat-label">Remaining Useful Life</p>
                            <p className="mt-1 text-lg font-semibold text-tata-blue">
                              {Math.round(result.remaining_useful_life_hours)}h
                              <span className="ml-1 text-sm font-normal text-tata-muted">
                                (~{Math.round(result.remaining_useful_life_hours / 24)}d)
                              </span>
                            </p>
                          </div>
                        </div>
                      )}
                      {result.failure_probability != null && (
                        <div className="metric-tile rounded-lg">
                          <div>
                            <p className="stat-label">Failure Probability</p>
                            <p className="mt-1 text-lg font-semibold text-tata-ink">
                              {Math.round(result.failure_probability * 100)}%
                            </p>
                          </div>
                        </div>
                      )}
                      <div className="metric-tile rounded-lg">
                        <div>
                          <p className="stat-label">Risk Level</p>
                          <div className="mt-2">
                            <RiskBadge level={result.risk_level} />
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                  {(result.spare_stock != null || result.procurement_risk) && (
                    <ProcureRiskPanel
                      compact
                      spareStock={result.spare_stock}
                      leadTimeDays={result.lead_time_days}
                      procurementRisk={result.procurement_risk}
                      businessImpactInr={result.business_impact_inr}
                      rulDays={
                        result.remaining_useful_life_hours != null
                          ? result.remaining_useful_life_hours / 24
                          : null
                      }
                      rulHours={result.remaining_useful_life_hours}
                      riskEscalated={result.risk_escalated}
                      escalationReason={result.escalation_reason}
                      criticalSparePart={result.critical_spare_part}
                      riskLevel={result.risk_level}
                    />
                  )}
                </div>
                {result.monitoring_plan && (
                  <p className="mt-4 rounded-lg border border-tata-border/80 bg-tata-blue-pale/30 px-4 py-3 text-sm text-tata-muted">
                    {result.monitoring_plan}
                  </p>
                )}
              </div>
            )}

            <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
              <div className="space-y-6">
                <div className="panel-flush overflow-hidden">
                  <div className="flex items-start justify-between gap-3 border-b border-tata-border/80 bg-gradient-to-r from-tata-blue to-tata-blue-light px-5 py-4 text-white">
                    <div className="flex items-start gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/15 ring-1 ring-white/25">
                        <Brain className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/70">AI generated</p>
                        <h2 className="text-base font-semibold">Engineer Summary</h2>
                        <p className="mt-0.5 text-xs text-white/80">
                          Confidence {(result.confidence_score * 100).toFixed(0)}%
                          {result.llm_provider ? ` · ${result.llm_provider}` : ""}
                        </p>
                      </div>
                    </div>
                    <RiskBadge level={result.risk_level} />
                  </div>
                  <div className="bg-gradient-to-br from-white to-tata-blue-pale/40 px-5 py-4">
                    {aiText ? (
                      <AiSummaryBody text={aiText} />
                    ) : (
                      <p className="text-sm text-tata-muted">No AI summary returned.</p>
                    )}
                    {result.follow_up_suggestions?.length > 0 && (
                      <div className="mt-4 border-t border-tata-border/60 pt-4">
                        <p className="stat-label mb-2">Suggested follow-ups</p>
                        <div className="flex flex-wrap gap-2">
                          {result.follow_up_suggestions.map((q: string) => (
                            <Link
                              key={q}
                              href={`/chat?equipment=${result.equipment_id}&q=${encodeURIComponent(q)}`}
                              className="chat-prompt-chip !py-2 !text-[11px]"
                            >
                              {q}
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-tata-border/60 pt-4">
                      <FeedbackBar
                        onSubmit={async (positive) => {
                          await api.feedback({
                            equipment_id: result.equipment_id,
                            query: `${form.symptoms} ${form.fault_codes} ${form.incident_description}`.trim(),
                            recommendation: (result.ai_summary || result.root_cause_analysis || "").slice(0, 4000),
                            source_type: "diagnose",
                            fault_type: result.probable_causes?.[0]?.cause,
                            rating: positive ? 5 : 2,
                            correction: positive
                              ? undefined
                              : `Diagnosis not helpful for ${result.probable_causes?.[0]?.cause || "reported symptoms"}`,
                            approved: positive,
                          });
                        }}
                      />
                      <Link
                        href={`/chat?equipment=${result.equipment_id}`}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-tata-blue px-3 py-2 text-xs font-semibold text-white hover:brightness-110"
                      >
                        <Brain className="h-3.5 w-3.5" />
                        Continue in AI chat
                      </Link>
                    </div>
                  </div>
                </div>

                {result.root_cause_analysis && result.root_cause_analysis !== aiText.slice(0, 500) && (
                  <div className="panel">
                    <h3 className="panel-title mb-3">Sensor Evidence</h3>
                    <div className="rounded-lg border border-tata-border bg-white p-4 text-sm leading-relaxed text-tata-ink/90">
                      {result.root_cause_analysis}
                    </div>
                  </div>
                )}

                <div className="panel">
                  <h3 className="panel-title mb-3">Probable Causes</h3>
                  <div className="space-y-3">
                    {(result.probable_causes || []).length === 0 ? (
                      <p className="text-sm text-tata-muted">No causes identified.</p>
                    ) : (
                      (result.probable_causes || []).map((c: any, i: number) => {
                        const pct = Math.round((c.confidence || 0) * 100);
                        return (
                          <div key={i} className="rounded-lg border border-tata-border bg-white p-3">
                            <div className="flex items-start justify-between gap-3 text-sm">
                              <span className="text-tata-ink/90">{c.cause}</span>
                              <span className="shrink-0 font-mono text-xs font-semibold text-tata-blue">{pct}%</span>
                            </div>
                            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-tata-border/40">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-tata-blue to-tata-blue-light"
                                style={{ width: `${Math.min(100, pct)}%` }}
                              />
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                <div className="panel">
                  <h3 className="panel-title mb-3">Immediate Actions</h3>
                  <ol className="list-decimal space-y-2 pl-5 text-sm text-tata-ink/85">
                    {(result.immediate_actions || []).length === 0 ? (
                      <li className="list-none pl-0 text-tata-muted">No immediate actions listed.</li>
                    ) : (
                      (result.immediate_actions || []).map((a: string, i: number) => <li key={i}>{a}</li>)
                    )}
                  </ol>
                </div>

                {(result.short_term_actions?.length > 0 || result.long_term_actions?.length > 0) && (
                  <div className="panel">
                    <h3 className="panel-title mb-3">Maintenance Plan</h3>
                    {result.short_term_actions?.length > 0 && (
                      <>
                        <p className="stat-label mb-2">Short-term (1–7 days)</p>
                        <ol className="mb-4 list-decimal space-y-2 pl-5 text-sm text-tata-ink/85">
                          {result.short_term_actions.map((a: string, i: number) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ol>
                      </>
                    )}
                    {result.long_term_actions?.length > 0 && (
                      <>
                        <p className="stat-label mb-2">Long-term monitoring</p>
                        <ol className="list-decimal space-y-2 pl-5 text-sm text-tata-ink/85">
                          {result.long_term_actions.map((a: string, i: number) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ol>
                      </>
                    )}
                  </div>
                )}

                {result.citations?.length > 0 && (
                  <div className="panel">
                    <h3 className="panel-title mb-3">Traceability — Citations</h3>
                    {result.citations.map((c: any, i: number) => (
                      <div key={i} className="mb-2 rounded-lg border border-tata-blue/20 bg-tata-blue/5 p-3 text-xs last:mb-0">
                        <p className="font-semibold text-tata-blue">{c.source}</p>
                        <p className="mt-1 text-tata-muted">{c.excerpt?.slice(0, 160)}…</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {(reasoningPanel || loading) && (
              <div className="panel-flush overflow-hidden p-0">
                <AIReasoningPanel
                  panel={reasoningPanel}
                  loading={loading}
                  provider={result?.llm_provider}
                  defaultExpanded={false}
                />
              </div>
            )}
          </>
        )}
      </div>
    </Shell>
  );
}
