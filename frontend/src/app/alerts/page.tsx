"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { DownloadPdfButton } from "@/components/DownloadPdfButton";
import { api, getToken, riskColor } from "@/lib/api";
import { useRouter } from "next/navigation";
import { AlertTriangle, Bell, Calendar, ShieldAlert } from "lucide-react";

const LEVEL_BORDER: Record<string, string> = {
  critical: "border-red-500/30 bg-red-500/5",
  high: "border-orange-500/30 bg-orange-500/5",
  warning: "border-yellow-500/20 bg-yellow-500/5",
};

const WORKFLOW = [
  { step: "1. Alert fires", detail: "Live Monitor detects high temp, vibration, or low health from C-MAPSS sensors." },
  { step: "2. Ack", detail: "You have seen the alert and someone is looking at it. Status → acknowledged." },
  { step: "3. Fix on plant floor", detail: "Actual repair: inspection, part change, shutdown — done outside this app (Logbook / Schedule)." },
  { step: "4. Resolve", detail: "Close the alert ticket once work is done. It moves to Resolved history and is logged — sensors are not auto-fixed." },
];

function defaultReminderTime() {
  const d = new Date();
  d.setHours(d.getHours() + 24);
  d.setMinutes(0, 0, 0);
  return d.toISOString();
}

export default function AlertsPage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [equipment, setEquipment] = useState<any[]>([]);
  const [filter, setFilter] = useState<"open" | "all" | "resolved">("open");
  const [reminding, setReminding] = useState<number | null>(null);
  const [resolving, setResolving] = useState<any | null>(null);
  const [resolveNote, setResolveNote] = useState("");
  const [toast, setToast] = useState("");

  const eqMap = Object.fromEntries(equipment.map((e) => [e.id, e.equipment_code]));

  function load() {
    api.alerts(filter === "all" ? undefined : filter, 100).then(setAlerts).catch(() => {});
    api.alertsSummary().then(setSummary).catch(() => {});
  }

  useEffect(() => {
    if (!getToken()) router.push("/");
    else {
      load();
      api.equipment().then(setEquipment).catch(() => {});
    }
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, [router, filter]);

  async function ack(id: number) {
    await api.acknowledgeAlert(id);
    load();
  }

  async function resolve(alert: any) {
    const note = resolveNote.trim();
    setResolving(null);
    setResolveNote("");
    try {
      await api.resolveAlert(alert.id);
      if (note) {
        await api.createLogbook({
          equipment_id: alert.equipment_id,
          entry_type: "maintenance",
          title: `Resolution: ${alert.title.slice(0, 80)}`,
          description: note,
        });
      }
      setToast(
        `${eqMap[alert.equipment_id] || "Asset"}: alert closed and logged. Equipment is not auto-repaired — check Live Monitor for new readings.`
      );
      setTimeout(() => setToast(""), 6000);
      load();
    } catch (err: unknown) {
      setToast(err instanceof Error ? err.message : "Failed to resolve alert");
    }
  }

  async function remind(alert: any) {
    setReminding(alert.id);
    setToast("");
    try {
      await api.createSchedulerReminder({
        equipment_id: alert.equipment_id,
        title: `Follow-up: ${alert.title}`,
        reminder_at: defaultReminderTime(),
        notes: alert.message,
      });
      setToast(`Reminder set for ${eqMap[alert.equipment_id] || `Equipment #${alert.equipment_id}`}`);
      setTimeout(() => setToast(""), 4000);
    } catch (err: unknown) {
      setToast(err instanceof Error ? err.message : "Failed to set reminder");
    } finally {
      setReminding(null);
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Real-Time Alert Center"
        subtitle="Sensor thresholds from Live Monitor — use Ack when reviewing, Resolve when maintenance work is complete."
        action={
          <select className="input w-auto" value={filter} onChange={(e) => setFilter(e.target.value as any)}>
            <option value="open">Open & Acknowledged</option>
            <option value="all">All</option>
            <option value="resolved">Resolved</option>
          </select>
        }
      />

      {toast && (
        <div className="mb-4 rounded-lg border border-tata-blue/30 bg-tata-blue-pale px-4 py-3 text-sm text-tata-ink">
          {toast}
        </div>
      )}

      <section className="panel mb-6">
        <h2 className="panel-title mb-3">What do these buttons mean?</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {WORKFLOW.map(({ step, detail }) => (
            <div key={step} className="rounded-lg border border-tata-border bg-tata-blue-pale/40 p-3">
              <p className="text-xs font-semibold text-tata-blue">{step}</p>
              <p className="mt-1 text-xs leading-relaxed text-tata-muted">{detail}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-tata-muted">
          <strong className="font-medium text-tata-ink">Resolve does not fix the machine.</strong> It only closes this
          alert record. If sensors are still bad, Live Monitor may raise a new alert.
        </p>
      </section>

      {resolving && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-tata-ink/40 p-4">
          <div className="panel w-full max-w-md shadow-lg">
            <h3 className="panel-title text-base">Close alert ticket?</h3>
            <p className="mt-2 text-sm text-tata-muted">
              Confirm that maintenance action is complete for{" "}
              <strong className="text-tata-ink">{resolving.title}</strong>. This marks the alert resolved and writes to
              the logbook — it does not change sensor readings.
            </p>
            <label className="mt-4 block text-xs font-medium text-tata-muted">What was done? (optional)</label>
            <textarea
              className="input mt-1 min-h-[80px]"
              placeholder="e.g. Bearing replaced, vibration back to normal after 2h shutdown"
              value={resolveNote}
              onChange={(e) => setResolveNote(e.target.value)}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setResolving(null)}>
                Cancel
              </button>
              <button type="button" className="btn-primary" onClick={() => resolve(resolving)}>
                Mark resolved
              </button>
            </div>
          </div>
        </div>
      )}

      {summary && (
        <div className="mb-6 grid gap-4 md:grid-cols-4 stat-grid">
          {[
            { label: "Open Alerts", value: summary.open, icon: Bell, border: "border-l-tata-blue" },
            { label: "Critical", value: summary.critical, icon: ShieldAlert, border: "border-l-red-400" },
            { label: "High", value: summary.high, icon: AlertTriangle, border: "border-l-orange-400" },
            { label: "Warning", value: summary.warning, icon: AlertTriangle, border: "border-l-amber-400" },
          ].map(({ label, value, icon: Icon, border }) => (
            <div key={label} className={`stat-card flex items-center gap-4 border-l-4 ${border}`}>
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-tata-blue/10 text-tata-blue">
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <p className="stat-label">{label}</p>
                <p className="stat-value">{value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <section className="panel">
        <div className="panel-header mb-4">
          <div>
            <h2 className="panel-title">Active Alerts</h2>
            <p className="panel-desc">
              {filter === "open"
                ? "Open and acknowledged alerts requiring action"
                : filter === "resolved"
                  ? "Resolved alert history"
                  : "All alerts"}
            </p>
          </div>
          <Link href="/scheduler" className="btn-secondary text-xs">
            <Calendar className="h-3.5 w-3.5" /> Schedule
          </Link>
        </div>

        <div className="space-y-3">
          {alerts.length === 0 ? (
            <p className="text-sm text-tata-muted">
              No {filter} alerts. Open Live Monitor to stream C-MAPSS sensors — alerts auto-generate on threshold breach.
            </p>
          ) : (
            alerts.map((alert) => (
              <div
                key={alert.id}
                className={`rounded-lg border p-4 ${LEVEL_BORDER[alert.level] || "border-tata-border bg-tata-blue-pale/50"}`}
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-tata-ink">{alert.title}</p>
                    <p className="mt-1 text-sm text-tata-muted">{alert.message}</p>
                    <p className="mt-2 text-xs text-tata-muted">
                      {eqMap[alert.equipment_id] || `Equipment #${alert.equipment_id}`} · {alert.source} ·{" "}
                      {new Date(alert.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <span className={`badge ${riskColor(alert.level)}`}>{alert.level}</span>
                    <span className="text-xs capitalize text-tata-muted">{alert.status}</span>
                    <div className="flex flex-wrap justify-end gap-1">
                      {(alert.status === "open" || alert.status === "acknowledged") && (
                        <button
                          onClick={() => remind(alert)}
                          disabled={reminding === alert.id}
                          className="btn-secondary py-1 px-2 text-xs"
                        >
                          <Bell className="h-3 w-3" />
                          {reminding === alert.id ? "…" : "Remind"}
                        </button>
                      )}
                      {alert.status === "open" && (
                        <>
                          <button
                            onClick={() => ack(alert.id)}
                            className="btn-secondary py-1 px-2 text-xs"
                            title="I have seen this alert — assign for review"
                          >
                            Ack
                          </button>
                          <button
                            onClick={() => setResolving(alert)}
                            className="btn-primary py-1 px-2 text-xs"
                            title="Maintenance complete — close this alert ticket"
                          >
                            Resolve
                          </button>
                        </>
                      )}
                      {alert.status === "acknowledged" && (
                        <button
                          onClick={() => setResolving(alert)}
                          className="btn-primary py-1 px-2 text-xs"
                          title="Maintenance complete — close this alert ticket"
                        >
                          Resolve
                        </button>
                      )}
                      <DownloadPdfButton
                        reportType="alert"
                        alertId={alert.id}
                        equipmentId={alert.equipment_id}
                        payload={{
                          ...alert,
                          equipment_code: eqMap[alert.equipment_id],
                        }}
                        label="PDF"
                        className="[&_button]:py-1 [&_button]:px-2 [&_button]:text-xs"
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </Shell>
  );
}
