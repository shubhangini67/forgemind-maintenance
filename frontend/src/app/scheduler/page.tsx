"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { api, getToken, riskColor } from "@/lib/api";
import { useRouter } from "next/navigation";
import { ProcureRiskPanel } from "@/components/ProcureRiskPanel";
import { DownloadPdfButton } from "@/components/DownloadPdfButton";
import { Bell, Calendar, Plus, ShieldAlert } from "lucide-react";

const URGENCY_STYLE: Record<string, string> = {
  critical: "border-red-500/40 bg-red-500/5",
  high: "border-orange-500/40 bg-orange-500/5",
  planned: "border-tata-border bg-white",
};

function defaultReminderTime() {
  const d = new Date();
  d.setHours(d.getHours() + 24);
  d.setMinutes(0, 0, 0);
  return d.toISOString().slice(0, 16);
}

export default function SchedulerPage() {
  const router = useRouter();
  const [plan, setPlan] = useState<any>(null);
  const [equipment, setEquipment] = useState<any[]>([]);
  const [reminders, setReminders] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [alertSummary, setAlertSummary] = useState<any>(null);
  const [form, setForm] = useState({ equipment_id: 1, title: "", reminder_at: defaultReminderTime(), notes: "" });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  function loadReminders() {
    api.schedulerReminders().then(setReminders).catch(() => {});
  }

  function loadAlerts() {
    api.alerts("open", 8).then(setAlerts).catch(() => {});
    api.alertsSummary().then(setAlertSummary).catch(() => {});
  }

  useEffect(() => {
    if (!getToken()) router.push("/");
    else {
      api.scheduler().then((data) => {
        setPlan(data);
        if (data?.logbook_entries_created > 0) {
          setMessage(`${data.logbook_entries_created} maintenance task(s) auto-logged to logbook.`);
        }
      }).catch(() => {});
      api.equipment().then((eq) => {
        setEquipment(eq);
        if (eq.length) setForm((f) => ({ ...f, equipment_id: eq[0].id }));
      });
      loadReminders();
      loadAlerts();
    }
  }, [router]);

  async function addReminder(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      await api.createSchedulerReminder({
        equipment_id: form.equipment_id,
        title: form.title,
        reminder_at: new Date(form.reminder_at).toISOString(),
        notes: form.notes,
      });
      setForm((f) => ({ ...f, title: "", notes: "", reminder_at: defaultReminderTime() }));
      setMessage("Reminder saved — also logged to maintenance logbook.");
      loadReminders();
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Failed to save reminder");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Maintenance Scheduler"
        subtitle="7-day optimized plan plus manual engineer reminders — all recorded in the logbook."
      />

      <div className="grid gap-6 xl:grid-cols-3">
        {/* Manual reminders */}
        <div className="space-y-4 xl:col-span-1">
          <form onSubmit={addReminder} className="panel">
            <h2 className="panel-title mb-1 flex items-center gap-2">
              <Bell className="h-5 w-5" /> Manual Reminder
            </h2>
            <p className="panel-desc mb-4">Schedule a maintenance reminder for your team</p>
            <div className="space-y-3">
              <div>
                <label className="stat-label">Equipment</label>
                <select
                  className="input mt-1"
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
              <div>
                <label className="stat-label">Reminder title</label>
                <input
                  className="input mt-1"
                  placeholder="e.g. Bearing inspection due"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="stat-label">Date & time</label>
                <input
                  type="datetime-local"
                  className="input mt-1"
                  value={form.reminder_at}
                  onChange={(e) => setForm({ ...form, reminder_at: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="stat-label">Notes (optional)</label>
                <textarea
                  className="input mt-1 min-h-[72px]"
                  placeholder="Spare parts needed, crew assignment…"
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
              </div>
              <button type="submit" className="btn-primary w-full" disabled={saving}>
                <Plus className="h-4 w-4" /> {saving ? "Saving…" : "Set Reminder"}
              </button>
            </div>
            {message && (
              <p className={`mt-3 text-xs ${message.includes("saved") ? "text-emerald-400" : "text-red-400"}`}>{message}</p>
            )}
          </form>

          <div className="panel">
            <h3 className="panel-title mb-3">Your Reminders</h3>
            {reminders.length === 0 ? (
              <p className="text-sm text-tata-muted">No manual reminders yet.</p>
            ) : (
              <ul className="space-y-2">
                {reminders.map((r) => (
                  <li key={r.id} className="rounded-lg border border-tata-blue/25 bg-tata-blue/5 p-3">
                    <p className="text-sm font-medium text-tata-ink">{r.title}</p>
                    <p className="mt-1 text-xs text-tata-blue">
                      {r.equipment_code} · {r.reminder_at ? new Date(r.reminder_at).toLocaleString() : "—"}
                    </p>
                    {r.notes && <p className="mt-1 text-xs text-tata-muted line-clamp-2">{r.notes}</p>}
                    <p className="mt-1 text-[10px] text-tata-muted">By {r.observed_by}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="panel">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="panel-title flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-red-400" /> Open Alerts
              </h3>
              {alertSummary && (
                <span className="text-xs text-tata-muted">{alertSummary.open} open</span>
              )}
            </div>
            {alerts.length === 0 ? (
              <p className="text-sm text-tata-muted">No open alerts.</p>
            ) : (
              <ul className="space-y-2">
                {alerts.map((a) => {
                  const code = equipment.find((e) => e.id === a.equipment_id)?.equipment_code;
                  return (
                    <li
                      key={a.id}
                      className={`rounded-lg border p-3 ${
                        a.level === "critical"
                          ? "border-red-500/25 bg-red-500/5"
                          : a.level === "high"
                            ? "border-orange-500/25 bg-orange-500/5"
                            : "border-tata-border bg-tata-blue-pale/50"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs font-medium text-tata-ink line-clamp-2">{a.title}</p>
                        <span className={`badge shrink-0 ${riskColor(a.level)}`}>{a.level}</span>
                      </div>
                      <p className="mt-1 text-[10px] text-tata-muted">
                        {code || `#${a.equipment_id}`} · {new Date(a.created_at).toLocaleString()}
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}
            <a href="/alerts" className="mt-3 inline-block text-xs text-tata-blue hover:underline">
              View all alerts →
            </a>
          </div>
        </div>

        {/* Auto-generated plan */}
        <div className="xl:col-span-2">
          {!plan ? (
            <p className="text-sm text-tata-muted">Loading schedule…</p>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm text-tata-muted">
                  <Calendar className="h-4 w-4" />
                  Horizon: {plan.horizon_days} days · {plan.tasks.length} auto-scheduled tasks
                </div>
                <DownloadPdfButton
                  reportType="maintenance_plan"
                  payload={{ tasks: plan.tasks }}
                  label="Download Plan PDF"
                />
              </div>

              {plan.tasks.some((t: any) => t.procurement_risk === "critical") && (
                <div className="mb-4">
                  <ProcureRiskPanel
                    {...(() => {
                      const t = plan.tasks.find((x: any) => x.procurement_risk === "critical") || plan.tasks[0];
                      return {
                        spareStock: t.spares_available,
                        leadTimeDays: t.lead_time_days,
                        procurementRisk: t.procurement_risk,
                        businessImpactInr: t.business_impact_inr,
                        rulDays: t.rul_days,
                        riskEscalated: t.risk_escalated,
                        escalationReason: t.escalation_reason,
                        criticalSparePart: t.critical_spare_part,
                        riskLevel: t.urgency,
                      };
                    })()}
                    compact
                  />
                </div>
              )}

              <div className="space-y-3">
                {plan.tasks.map((task: any, i: number) => {
                  const start = new Date(task.start);
                  const end = new Date(task.end);
                  return (
                    <div
                      key={task.id}
                      className={`panel border ${URGENCY_STYLE[task.urgency] || URGENCY_STYLE.planned}`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-tata-blue/15 text-xs font-bold text-tata-blue">
                              {i + 1}
                            </span>
                            <p className="font-semibold text-tata-ink">
                              {task.equipment_code} — {task.task}
                            </p>
                          </div>
                          <p className="mt-2 text-sm text-tata-muted">
                            {start.toLocaleDateString()}{" "}
                            {start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            {" → "}
                            {end.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            {" "}({task.duration_hours}h)
                          </p>
                          <p className="mt-1 text-xs text-tata-muted">
                            Health {task.health_score}% · Stock {task.spares_available} · Lead {task.lead_time_days}d
                            {task.procurement_risk && (
                              <span className={task.procurement_risk === "critical" ? " text-red-600 font-semibold" : ""}>
                                {" "}· Procurement {task.procurement_risk}
                              </span>
                            )}
                            {task.business_impact_inr != null && (
                              <span> · Impact ₹{(task.business_impact_inr / 100000).toFixed(1)}L</span>
                            )}
                          </p>
                          {task.escalation_reason && (
                            <p className="mt-1 text-[10px] text-red-600">{task.escalation_reason}</p>
                          )}
                        </div>
                        <span className={`badge ${riskColor(task.urgency === "planned" ? "low" : task.urgency)}`}>
                          {task.urgency}
                        </span>
                      </div>
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-tata-blue to-tata-blue-light"
                          style={{ width: `${Math.min(100, (task.duration_hours / 24) * 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </Shell>
  );
}
