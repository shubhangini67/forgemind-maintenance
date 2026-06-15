"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Brain } from "lucide-react";

function formatInr(n: number) {
  return `₹${n.toLocaleString("en-IN")}`;
}

export default function SparesPage() {
  const router = useRouter();
  const [spares, setSpares] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [equipment, setEquipment] = useState<any[]>([]);
  const [orderForm, setOrderForm] = useState({
    spare_part_id: 0,
    equipment_id: 1,
    quantity: 1,
    urgency: "normal",
    notes: "",
  });

  function load() {
    Promise.all([api.sparesList(), api.procurement()]).then(([s, o]) => {
      setSpares(s);
      setOrders(o);
      if (s.length && !orderForm.spare_part_id) setOrderForm((f) => ({ ...f, spare_part_id: s[0].id }));
    });
  }

  useEffect(() => {
    if (!getToken()) router.push("/");
    else {
      api.equipment().then((eq) => {
        setEquipment(eq);
        if (eq.length) setOrderForm((f) => ({ ...f, equipment_id: eq[0].id }));
      });
      load();
    }
  }, [router]);

  async function submitOrder(e: React.FormEvent) {
    e.preventDefault();
    await api.createProcurement(orderForm);
    load();
  }

  async function approve(id: number) {
    await api.approveProcurement(id);
    load();
  }

  async function reject(id: number) {
    await api.rejectProcurement(id, "Not approved at this time");
    load();
  }

  const lowStock = spares.filter((s) => s.quantity_available <= s.reorder_level);

  return (
    <Shell>
      <PageHeader
        title="Spare Parts & Procurement"
        subtitle="Inventory availability, lead times, and procurement workflow — also used by the Spares & Risk agent for AI recommendations."
        action={
          <Link href="/chat?q=What%20spare%20parts%20should%20we%20procure%3F" className="btn-secondary inline-flex items-center gap-2 text-sm">
            <Brain className="h-4 w-4" /> Ask AI for procurement
          </Link>
        }
      />

      {lowStock.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>{lowStock.length} part(s)</strong> at or below reorder level — review procurement urgency.
        </div>
      )}

      <div className="mb-6 grid gap-4 md:grid-cols-2">
        <div className="card">
          <h3 className="mb-3 font-semibold">Inventory</h3>
          <div className="max-h-80 space-y-2 overflow-y-auto">
            {spares.map((s) => {
              const low = s.quantity_available <= s.reorder_level;
              return (
                <div key={s.id} className={`flex justify-between border-b border-steel-100 py-2 text-sm ${low ? "bg-red-50/50 -mx-2 px-2 rounded" : ""}`}>
                  <div>
                    <p className="font-medium">{s.part_number} — {s.name}</p>
                    <p className="text-xs text-steel-500">{s.equipment_type}</p>
                  </div>
                  <div className="text-right">
                    <p className={low ? "font-bold text-red-600" : ""}>{s.quantity_available} in stock</p>
                    <p className="text-xs text-steel-500">Reorder at {s.reorder_level}</p>
                    <p className="text-xs text-steel-500">
                      Lead {s.lead_time_days ?? "—"}d · {s.unit_cost != null ? formatInr(s.unit_cost) : "—"}/unit
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <form onSubmit={submitOrder} className="card">
          <h3 className="mb-3 font-semibold">Request Spare Part</h3>
          <div className="space-y-3">
            <select className="input w-full" value={orderForm.spare_part_id} onChange={(e) => setOrderForm({ ...orderForm, spare_part_id: Number(e.target.value) })}>
              {spares.map((s) => (
                <option key={s.id} value={s.id}>{s.part_number} — {s.name}</option>
              ))}
            </select>
            <select className="input w-full" value={orderForm.equipment_id} onChange={(e) => setOrderForm({ ...orderForm, equipment_id: Number(e.target.value) })}>
              {equipment.map((eq) => (
                <option key={eq.id} value={eq.id}>{eq.equipment_code}</option>
              ))}
            </select>
            <input type="number" min={1} className="input w-full" value={orderForm.quantity} onChange={(e) => setOrderForm({ ...orderForm, quantity: Number(e.target.value) })} />
            <select className="input w-full" value={orderForm.urgency} onChange={(e) => setOrderForm({ ...orderForm, urgency: e.target.value })}>
              <option value="normal">Normal urgency</option>
              <option value="high">High — within 48h</option>
              <option value="critical">Critical — production stop risk</option>
            </select>
            <input className="input w-full" placeholder="Notes" value={orderForm.notes} onChange={(e) => setOrderForm({ ...orderForm, notes: e.target.value })} />
            <button type="submit" className="btn-primary">Submit Order</button>
          </div>
        </form>
      </div>

      <div className="card">
        <h3 className="mb-3 font-semibold">Orders — Approve / Reject</h3>
        <div className="space-y-3">
          {orders.length === 0 ? (
            <p className="text-steel-500">No procurement requests.</p>
          ) : (
            orders.map((o) => (
              <div key={o.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-steel-100 py-3">
                <div>
                  <p className="font-medium">{o.part_number} — {o.part_name}</p>
                  <p className="text-sm text-steel-600">Qty: {o.quantity} · Equipment #{o.equipment_id} · {o.urgency}</p>
                  <p className="text-xs text-steel-500">{new Date(o.requested_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`badge ${o.status === "pending" ? "text-yellow-700 bg-yellow-50" : o.status === "approved" ? "text-green-700 bg-green-50" : "text-red-600 bg-red-50"}`}>
                    {o.status}
                  </span>
                  {o.status === "pending" && (
                    <>
                      <button onClick={() => approve(o.id)} className="btn-primary text-sm py-1 px-3">Approve</button>
                      <button onClick={() => reject(o.id)} className="btn-secondary text-sm py-1 px-3">Reject</button>
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </Shell>
  );
}
