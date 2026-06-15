"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { ProcureRiskPanel } from "@/components/ProcureRiskPanel";
import { DownloadPdfButton } from "@/components/DownloadPdfButton";
import { HealthGauge } from "@/components/HealthGauge";
import { api, clearApiCache, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, RefreshCw, TrendingUp, Package } from "lucide-react";

const ACTION_COLORS: Record<string, string> = {
  "IMMEDIATE SHUTDOWN & REPAIR": "text-red-700 bg-red-50 border-red-200 hover:bg-red-100",
  "URGENT: Schedule within 24h": "text-orange-700 bg-orange-50 border-orange-200 hover:bg-orange-100",
  "PLAN: Schedule within 1 week": "text-amber-800 bg-amber-50 border-amber-200 hover:bg-amber-100",
  "MONITOR: Normal operations": "text-emerald-700 bg-emerald-50 border-emerald-200 hover:bg-emerald-100",
};

function reminderAt(action: string): string {
  const d = new Date();
  if (action.includes("IMMEDIATE")) d.setHours(d.getHours() + 1);
  else if (action.includes("URGENT")) d.setHours(d.getHours() + 24);
  else if (action.includes("PLAN")) d.setDate(d.getDate() + 7);
  else return "";
  d.setMinutes(0, 0, 0);
  return d.toISOString();
}

function formatRul(item: { rul_days?: number | null; rul_hours?: number | null }) {
  const hours = item.rul_hours;
  const days = item.rul_days;
  if (hours != null && hours < 48) {
    const h = Math.max(1, Math.round(hours));
    return { label: `${h}h`, tone: h < 72 ? "text-red-600" : "text-orange-600" };
  }
  if (days != null) {
    const d = Math.max(1, Math.round(days));
    return { label: `${d}d`, tone: d < 3 ? "text-red-600" : d < 7 ? "text-orange-600" : "text-emerald-600" };
  }
  return { label: "—", tone: "text-tata-muted" };
}

export default function PriorityPage() {
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    setError("");
    clearApiCache("priority");
    api
      .priority()
      .then(setItems)
      .catch((e: Error) => setError(e.message || "Could not load priority queue"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!getToken()) router.push("/");
    else load();
  }, [router]);

  async function handleAction(item: any) {
    const action = item.recommended_action;

    if (action.includes("MONITOR")) {
      router.push(`/monitor?equipment=${item.equipment_id}`);
      return;
    }

    setActingId(item.equipment_id);
    setToast("");
    setError("");
    try {
      const at = reminderAt(action);
      await api.createSchedulerReminder({
        equipment_id: item.equipment_id,
        title: `${action} — ${item.equipment_code}`,
        reminder_at: at,
        notes: `Priority score ${item.priority_score}. Health ${Math.round(item.health_score)}%. ${item.critical_alerts} critical alert(s).`,
      });
      await api.createLogbook({
        equipment_id: item.equipment_id,
        entry_type: "maintenance",
        title: action,
        description: `Work order dispatched for ${item.equipment_name} (${item.equipment_code}). Scheduled follow-up logged from priority queue.`,
      });
      setToast(`${item.equipment_code}: ${action} — reminder and logbook entry created.`);
      setTimeout(() => setToast(""), 5000);
      router.push(`/scheduler?equipment=${item.equipment_id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to dispatch action";
      setError(msg);
      setToast("");
    } finally {
      setActingId(null);
    }
  }

  const immediate = items.filter((i) => i.recommended_action.includes("IMMEDIATE")).length;
  const urgent = items.filter((i) => i.recommended_action.includes("URGENT")).length;
  const procurementCritical = items.filter((i) => i.procurement_risk === "critical").length;
  const topProcure = items.find((i) => i.procurement_risk === "critical");

  return (
    <Shell>
      <PageHeader
        title="Plant Maintenance Priority"
        subtitle="Bottleneck analysis — ranked by criticality, alerts, RUL, and spares availability"
        action={
          <button onClick={load} className="btn-secondary flex items-center gap-2 text-sm">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Recalculate
          </button>
        }
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {toast && (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {toast}
        </div>
      )}

      {procurementCritical > 0 && (
        <div className="card mb-6 flex items-center gap-4 border-orange-300 bg-orange-50">
          <Package className="h-8 w-8 shrink-0 text-orange-600" />
          <div>
            <p className="font-semibold text-orange-800">
              {procurementCritical} asset(s) — RUL shorter than spare lead time
            </p>
            <p className="text-sm text-tata-muted">
              Cannot procure parts before predicted failure — risk auto-escalated to CRITICAL
            </p>
          </div>
        </div>
      )}

      {immediate > 0 && (
        <div className="card mb-6 flex items-center gap-4 border-red-200 bg-red-50">
          <AlertTriangle className="h-8 w-8 shrink-0 text-red-600 animate-pulse" />
          <div>
            <p className="font-semibold text-red-700">{immediate} equipment require IMMEDIATE attention</p>
            <p className="text-sm text-tata-muted">Unplanned downtime risk is HIGH — dispatch maintenance crew now</p>
          </div>
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Immediate", value: immediate, color: "text-red-600" },
          { label: "Urgent (24h)", value: urgent, color: "text-orange-600" },
          { label: "Plan (1 week)", value: items.filter((i) => i.recommended_action.includes("PLAN")).length, color: "text-amber-700" },
          { label: "Monitor", value: items.filter((i) => i.recommended_action.includes("MONITOR")).length, color: "text-emerald-600" },
        ].map((s) => (
          <div key={s.label} className="card text-center">
            <p className={`text-3xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs text-tata-muted">{s.label}</p>
          </div>
        ))}
      </div>

      {topProcure && (
        <div className="mb-6">
          <ProcureRiskPanel
            spareStock={topProcure.spare_stock}
            leadTimeDays={topProcure.lead_time_days}
            procurementRisk={topProcure.procurement_risk}
            businessImpactInr={topProcure.business_impact_inr}
            rulDays={topProcure.rul_days}
            rulHours={topProcure.rul_hours}
            riskEscalated={topProcure.risk_escalated}
            escalationReason={topProcure.escalation_reason}
            criticalSparePart={topProcure.critical_spare_part}
            riskLevel={topProcure.risk_level}
          />
        </div>
      )}

      <div className="card overflow-hidden p-0">
        <div className="flex items-center gap-2 border-b border-tata-border px-5 py-3">
          <TrendingUp className="h-4 w-4 text-tata-blue" />
          <span className="text-sm font-semibold text-tata-ink">Priority Ranking</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-tata-border bg-tata-blue-pale text-left text-xs text-tata-muted">
                {["Rank", "Asset", "Area", "Health", "Stock", "Lead", "RUL", "Proc. risk", "Score", "Action"].map((h) => (
                  <th key={h} className="whitespace-nowrap px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="py-10 text-center text-tata-muted">Loading…</td></tr>
              ) : (
                items.slice(0, 15).map((item, idx) => {
                  const rul = formatRul(item);
                  const health = Number(item.health_score);
                  return (
                    <tr key={item.equipment_id} className="border-b border-tata-border/40 hover:bg-tata-blue-pale/30">
                      <td className="px-4 py-3">
                        <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                          idx === 0 ? "bg-red-500 text-white" : idx === 1 ? "bg-orange-500 text-white" : idx === 2 ? "bg-amber-400 text-tata-ink" : "bg-steel-100 text-tata-muted"
                        }`}>{idx + 1}</span>
                      </td>
                      <td className="px-4 py-3">
                        <Link href={`/monitor?equipment=${item.equipment_id}`} className="font-medium text-tata-ink hover:text-tata-blue">
                          {item.equipment_code}
                        </Link>
                        <p className="text-xs text-tata-muted">{item.equipment_name}</p>
                      </td>
                      <td className="px-4 py-3 text-xs text-tata-muted">{item.plant_area}</td>
                      <td className="px-4 py-3">
                        <HealthGauge score={Number.isFinite(health) ? health : 0} size="sm" />
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold">
                        <span className={item.spare_stock === 0 ? "text-red-600" : "text-tata-ink"}>
                          {item.spare_stock ?? "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-tata-muted">{item.lead_time_days ?? "—"}d</td>
                      <td className="px-4 py-3 text-xs font-bold">
                        <span className={rul.tone}>{rul.label}</span>
                      </td>
                      <td className="px-4 py-3 text-xs capitalize">
                        <span
                          className={
                            item.procurement_risk === "critical"
                              ? "font-semibold text-red-600"
                              : item.procurement_risk === "high"
                                ? "text-orange-600"
                                : "text-tata-muted"
                          }
                        >
                          {item.procurement_risk || "—"}
                        </span>
                        {item.risk_escalated && (
                          <p className="mt-0.5 text-[9px] text-red-500">escalated</p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-tata-muted">{item.priority_score}</td>
                      <td className="relative z-10 px-4 py-3">
                        <div className="flex flex-col gap-1.5">
                          <button
                            type="button"
                            onClick={() => handleAction(item)}
                            disabled={actingId === item.equipment_id}
                            className={`relative z-10 cursor-pointer whitespace-nowrap rounded-lg border px-2.5 py-1.5 text-[10px] font-semibold transition disabled:cursor-wait disabled:opacity-60 ${ACTION_COLORS[item.recommended_action] || "border-tata-border text-tata-ink hover:bg-tata-blue-pale"}`}
                          >
                            {actingId === item.equipment_id ? "Dispatching…" : item.recommended_action}
                          </button>
                          <DownloadPdfButton
                            reportType="priority"
                            equipmentId={item.equipment_id}
                            payload={item}
                            label="PDF"
                            className="[&_button]:w-full [&_button]:justify-center [&_button]:py-1 [&_button]:text-[10px]"
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
