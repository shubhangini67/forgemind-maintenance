"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function HistoryPage() {
  const router = useRouter();
  const [equipment, setEquipment] = useState<any[]>([]);
  const [selected, setSelected] = useState(1);
  const [history, setHistory] = useState<any>({ maintenance: [], failures: [], logbook: [] });

  useEffect(() => {
    if (!getToken()) router.push("/");
    else api.equipment().then((eq) => {
      setEquipment(eq);
      if (eq.length) setSelected(eq[0].id);
    });
  }, [router]);

  useEffect(() => {
    if (selected) api.history(selected).then(setHistory).catch(() => {});
  }, [selected]);

  return (
    <Shell>
      <div className="mb-4 flex items-center gap-3">
        <h2 className="text-lg font-semibold">Maintenance History</h2>
        <select className="input w-auto" value={selected} onChange={(e) => setSelected(Number(e.target.value))}>
          {equipment.map((eq) => (
            <option key={eq.id} value={eq.id}>{eq.equipment_code} — {eq.name}</option>
          ))}
        </select>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <div className="card">
          <h3 className="mb-3 font-semibold">Maintenance Records</h3>
          {history.maintenance?.length ? history.maintenance.map((m: any) => (
            <div key={m.id} className="mb-3 border-b border-steel-100 pb-2 text-sm">
              <p className="font-medium">{m.type}</p>
              <p className="text-steel-600">{m.description}</p>
              <p className="text-xs text-steel-500">{new Date(m.performed_at).toLocaleDateString()} · {m.outcome}</p>
            </div>
          )) : <p className="text-steel-500 text-sm">No records</p>}
        </div>

        <div className="card">
          <h3 className="mb-3 font-semibold">Failure History</h3>
          {history.failures?.length ? history.failures.map((f: any) => (
            <div key={f.id} className="mb-3 border-b border-steel-100 pb-2 text-sm">
              <p className="font-medium">{f.failure_type} — {f.fault_code}</p>
              <p className="text-steel-600">{f.description}</p>
              <p className="text-xs text-steel-500">{new Date(f.occurred_at).toLocaleDateString()}</p>
            </div>
          )) : <p className="text-steel-500 text-sm">No failures logged</p>}
        </div>

        <div className="card">
          <h3 className="mb-3 font-semibold">Logbook Entries</h3>
          {history.logbook?.length ? history.logbook.map((l: any) => (
            <div key={l.id} className="mb-3 border-b border-steel-100 pb-2 text-sm">
              <p className="font-medium">{l.title}</p>
              <p className="text-steel-600">{l.description}</p>
              <p className="text-xs text-steel-500">{l.entry_type} · {new Date(l.created_at).toLocaleDateString()}</p>
            </div>
          )) : <p className="text-steel-500 text-sm">No logbook entries</p>}
        </div>
      </div>
    </Shell>
  );
}
