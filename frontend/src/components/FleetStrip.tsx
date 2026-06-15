"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api, getToken } from "@/lib/api";

const UNIT_COLORS = ["#e8a317", "#3b82f6", "#a855f7", "#14b8a6", "#f97316"];

export function FleetStrip() {
  const pathname = usePathname();
  const [fleet, setFleet] = useState<any[]>([]);

  useEffect(() => {
    if (!getToken()) return;
    api.plantTwin().then((t) => setFleet(t.cmapss_fleet || t.assets || [])).catch(() => {});
    const id = setInterval(() => {
      api.plantTwin().then((t) => setFleet(t.cmapss_fleet || t.assets || [])).catch(() => {});
    }, 45000);
    return () => clearInterval(id);
  }, [pathname]);

  if (!fleet.length) return null;

  return (
    <div className="border-t border-tata-border/60 bg-[#0a0e16]/80 px-4 py-1.5 lg:px-6">
      <div className="flex items-center gap-2 overflow-x-auto">
        <span className="shrink-0 text-[9px] font-bold uppercase tracking-widest text-steel-300">FD001</span>
        {fleet.map((a, i) => {
          const color = UNIT_COLORS[i % UNIT_COLORS.length];
          const active = pathname.includes(String(a.id));
          return (
            <Link
              key={a.id}
              href={`/monitor?equipment=${a.id}`}
              className={`flex shrink-0 items-center gap-2 rounded-md border px-2.5 py-1 text-[11px] transition ${
                active ? "border-[rgba(232,163,23,0.4)] bg-[rgba(232,163,23,0.08)]" : "border-transparent hover:bg-white/[0.04]"
              }`}
            >
              <span className="font-mono font-bold" style={{ color }}>
                U{a.cmapss_unit ?? i + 1}
              </span>
              <span className="text-tata-ink/70">{a.equipment_code}</span>
              <span
                className={`rounded px-1 font-mono text-[10px] ${
                  a.status === "critical"
                    ? "bg-red-500/20 text-red-400"
                    : a.status === "degraded"
                    ? "bg-orange-500/20 text-orange-400"
                    : "bg-emerald-500/15 text-emerald-400"
                }`}
              >
                {Math.round(a.health_score)}%
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
