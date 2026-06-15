"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Clock, Plus } from "lucide-react";

export default function DelaysPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<any[]>([]);
  const [equipment, setEquipment] = useState<any[]>([]);
  const [form, setForm] = useState({
    equipment_id: 1,
    delay_hours: 1,
    fault_code: "",
    reason: "",
    severity: "medium",
  });

  function load() {
    api.delayLogs().then(setEntries).catch(() => {});
  }

  useEffect(() => {
    if (!getToken()) router.push("/");
    else {
      api.equipment().then((eq) => {
        setEquipment(eq);
        if (eq.length) setForm((f) => ({ ...f, equipment_id: eq[0].id }));
      });
      load();
    }
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await api.createDelayLog(form);
    setForm((f) => ({ ...f, reason: "", fault_code: "" }));
    load();
  }

  return (
    <Shell>
      <header className="mb-6">
        <p className="section-title text-tata-blue/80">Operational Inputs</p>
        <h1 className="text-xl font-black text-tata-ink">Production Delay Logs</h1>
        <p className="text-sm text-tata-muted">
          Equipment delay records with fault codes — used in priority scoring and AI diagnosis context.
        </p>
      </header>

      <form onSubmit={submit} className="card mb-6 grid gap-3 md:grid-cols-2">
        <div>
          <label className="text-xs text-tata-muted">Equipment</label>
          <select
            className="input mt-1"
            value={form.equipment_id}
            onChange={(e) => setForm({ ...form, equipment_id: Number(e.target.value) })}
          >
            {equipment.map((eq) => (
              <option key={eq.id} value={eq.id}>{eq.equipment_code} — {eq.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-tata-muted">Delay (hours)</label>
          <input
            type="number"
            step="0.25"
            className="input mt-1"
            value={form.delay_hours}
            onChange={(e) => setForm({ ...form, delay_hours: Number(e.target.value) })}
          />
        </div>
        <div>
          <label className="text-xs text-tata-muted">Fault code</label>
          <input
            className="input mt-1"
            placeholder="E-2041"
            value={form.fault_code}
            onChange={(e) => setForm({ ...form, fault_code: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs text-tata-muted">Severity</label>
          <select
            className="input mt-1"
            value={form.severity}
            onChange={(e) => setForm({ ...form, severity: e.target.value })}
          >
            <option value="warning">Warning</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="text-xs text-tata-muted">Reason / description</label>
          <textarea
            className="input mt-1 min-h-[70px]"
            required
            value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })}
          />
        </div>
        <button type="submit" className="btn-primary w-fit md:col-span-2">
          <Plus className="h-4 w-4" /> Log delay
        </button>
      </form>

      <div className="space-y-3">
        {entries.length === 0 ? (
          <div className="card text-tata-muted">No delay logs — run backend bootstrap or add above.</div>
        ) : (
          entries.map((d) => (
            <div key={d.id} className="card flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-tata-ink">
                  {equipment.find((e) => e.id === d.equipment_id)?.equipment_code || `#${d.equipment_id}`}
                  {d.fault_code && <span className="ml-2 font-mono text-tata-blue">{d.fault_code}</span>}
                </p>
                <p className="mt-1 text-sm text-tata-muted">{d.reason}</p>
              </div>
              <div className="text-right text-xs">
                <p className="flex items-center gap-1 font-bold text-tata-ink">
                  <Clock className="h-3.5 w-3.5" /> {d.delay_hours}h downtime
                </p>
                <p className="mt-1 text-tata-muted">{d.severity} · {new Date(d.created_at).toLocaleString()}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </Shell>
  );
}
