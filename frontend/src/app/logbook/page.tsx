"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Bot,
  Calendar,
  ClipboardList,
  Download,
  FileText,
  Loader2,
  MessageSquare,
  PenLine,
  Sparkles,
  Wrench,
} from "lucide-react";

const TYPE_STYLE: Record<string, string> = {
  alert: "bg-red-500/15 text-red-700",
  diagnosis: "bg-purple-500/15 text-purple-700",
  schedule: "bg-blue-500/15 text-blue-700",
  reminder: "bg-blue-500/15 text-blue-700",
  report: "bg-emerald-500/15 text-emerald-700",
  feedback: "bg-amber-500/15 text-amber-800",
  ai_analysis: "bg-indigo-500/15 text-indigo-700",
  observation: "bg-steel-100 text-steel-700",
  inspection: "bg-steel-100 text-steel-700",
  repair: "bg-steel-100 text-steel-700",
};

const TYPE_ICON: Record<string, typeof AlertTriangle> = {
  alert: AlertTriangle,
  diagnosis: Sparkles,
  schedule: Calendar,
  reminder: Calendar,
  report: FileText,
  feedback: MessageSquare,
  ai_analysis: Bot,
  observation: PenLine,
  inspection: ClipboardList,
  repair: Wrench,
};

function eventLabel(sourceEvent?: string) {
  if (!sourceEvent) return null;
  return sourceEvent.replace(".", " · ").replace("_", " ");
}

export default function LogbookPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [equipment, setEquipment] = useState<any[]>([]);
  const [form, setForm] = useState({ equipment_id: 1, entry_type: "observation", title: "", description: "" });
  const [filter, setFilter] = useState<number | "">("");
  const [typeFilter, setTypeFilter] = useState("");
  const [autoFilter, setAutoFilter] = useState<"" | "auto" | "manual">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  async function downloadReport(entry: any) {
    const reportId = entry.source_id;
    if (!reportId) return;
    setDownloadingId(entry.id);
    setError("");
    try {
      await api.downloadReportPdf(reportId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not download report PDF");
    } finally {
      setDownloadingId(null);
    }
  }

  const load = useCallback(() => {
    if (!getToken()) return;
    setLoading(true);
    setError("");
    const autoOnly = autoFilter === "auto" ? true : autoFilter === "manual" ? false : undefined;
    Promise.all([
      api.logbook(filter || undefined, { entryType: typeFilter || undefined, autoOnly }),
      api.logbookSummary(filter || undefined),
    ])
      .then(([rows, sum]) => {
        setEntries(rows);
        setSummary(sum);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load logbook");
        setEntries([]);
      })
      .finally(() => setLoading(false));
  }, [filter, typeFilter, autoFilter]);

  useEffect(() => {
    if (!getToken()) {
      router.push("/");
      return;
    }
    api.equipment().then((eq) => {
      setEquipment(eq);
      if (eq.length) setForm((f) => ({ ...f, equipment_id: eq[0].id }));
    }).catch(() => {});
    load();
  }, [router, load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.createLogbook(form);
      setForm((f) => ({ ...f, title: "", description: "" }));
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save entry");
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Maintenance Logbook"
        subtitle="Complete maintenance history — auto-generated from alerts, diagnosis, scheduling, reports, and feedback."
        action={<Link href="/diagnose" className="btn-secondary text-sm">Run Diagnosis</Link>}
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
          {error.includes("Session") || error.includes("offline") ? (
            <span> — <Link href="/" className="underline">Sign in again</Link></span>
          ) : null}
        </div>
      )}

      {summary && (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="stat-card">
            <p className="stat-label">Total entries</p>
            <p className="stat-value">{summary.total_entries}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Auto-generated</p>
            <p className="stat-value text-tata-blue">{summary.auto_generated}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Manual entries</p>
            <p className="stat-value">{summary.manual_entries}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">History coverage</p>
            <p className="stat-value">{summary.coverage_pct}%</p>
          </div>
        </div>
      )}

      <form onSubmit={submit} className="panel mb-6 grid gap-3 md:grid-cols-2">
        <div>
          <label className="stat-label">Equipment</label>
          <select
            className="input mt-1 w-full"
            value={form.equipment_id}
            onChange={(e) => setForm({ ...form, equipment_id: Number(e.target.value) })}
          >
            {equipment.map((eq) => (
              <option key={eq.id} value={eq.id}>{eq.equipment_code} — {eq.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="stat-label">Type</label>
          <select
            className="input mt-1 w-full"
            value={form.entry_type}
            onChange={(e) => setForm({ ...form, entry_type: e.target.value })}
          >
            <option value="observation">Observation</option>
            <option value="inspection">Inspection</option>
            <option value="repair">Repair</option>
            <option value="procurement">Procurement</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="stat-label">Title</label>
          <input className="input mt-1 w-full" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
        </div>
        <div className="md:col-span-2">
          <label className="stat-label">Description</label>
          <textarea
            className="input mt-1 w-full min-h-[80px]"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            required
          />
        </div>
        <button type="submit" className="btn-primary md:col-span-2 w-fit">Add Manual Entry</button>
      </form>

      <div className="mb-4 flex flex-wrap gap-2">
        <select className="input w-auto" value={filter} onChange={(e) => setFilter(e.target.value ? Number(e.target.value) : "")}>
          <option value="">All equipment</option>
          {equipment.map((eq) => (
            <option key={eq.id} value={eq.id}>{eq.equipment_code}</option>
          ))}
        </select>
        <select className="input w-auto" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">All event types</option>
          <option value="alert">Alerts</option>
          <option value="diagnosis">Diagnosis</option>
          <option value="schedule">Scheduled maintenance</option>
          <option value="report">Reports</option>
          <option value="feedback">Feedback</option>
          <option value="ai_analysis">AI analysis</option>
        </select>
        <select className="input w-auto" value={autoFilter} onChange={(e) => setAutoFilter(e.target.value as "" | "auto" | "manual")}>
          <option value="">Auto + manual</option>
          <option value="auto">Auto-generated only</option>
          <option value="manual">Manual only</option>
        </select>
      </div>

      {loading ? (
        <div className="card flex items-center gap-2 text-tata-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading logbook…
        </div>
      ) : entries.length === 0 ? (
        <div className="card">
          <p className="text-tata-muted">
            No logbook entries match your filters. Run <Link href="/diagnose" className="text-tata-blue underline">Diagnosis</Link>, open the{" "}
            <Link href="/scheduler" className="text-tata-blue underline">Scheduler</Link>, or generate a{" "}
            <Link href="/reports" className="text-tata-blue underline">Report</Link> — entries appear automatically.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => {
            const Icon = TYPE_ICON[entry.entry_type] || ClipboardList;
            const style = TYPE_STYLE[entry.entry_type] || TYPE_STYLE.observation;
            return (
              <div key={entry.id} className="panel">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className={`mt-0.5 rounded-lg p-2 ${style}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-semibold text-tata-ink">{entry.title}</p>
                      {entry.source_event && (
                        <p className="mt-0.5 text-xs uppercase tracking-wide text-tata-muted">{eventLabel(entry.source_event)}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className={`badge ${style}`}>{entry.entry_type}</span>
                    {entry.auto_generated ? (
                      <span className="text-[10px] font-medium uppercase tracking-wide text-tata-blue">Auto</span>
                    ) : (
                      <span className="text-[10px] font-medium uppercase tracking-wide text-steel-500">Manual</span>
                    )}
                  </div>
                </div>
                <p className="mt-3 text-sm text-tata-muted whitespace-pre-line line-clamp-4">{entry.description}</p>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-tata-muted">
                    {entry.equipment_code || `#${entry.equipment_id}`} · {entry.observed_by} · {new Date(entry.created_at).toLocaleString()}
                  </p>
                  {entry.entry_type === "report" && entry.source_id ? (
                    <button
                      type="button"
                      onClick={() => downloadReport(entry)}
                      disabled={downloadingId === entry.id}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-100 disabled:opacity-60"
                    >
                      {downloadingId === entry.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Download className="h-3.5 w-3.5" />
                      )}
                      {downloadingId === entry.id ? "Preparing…" : "Download PDF"}
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Shell>
  );
}
