import Link from "next/link";
import { ArrowRight, Radio } from "lucide-react";
import { RiskBadge } from "@/components/RiskBadge";

export type EquipmentRow = {
  id: number;
  equipment_code: string;
  name: string;
  equipment_type?: string;
  location?: string;
  cmapss_unit?: number;
  health_score?: number;
  rul_hours?: number | null;
  failure_probability?: number | null;
  risk_level?: string;
  alerts?: number;
};

function healthTone(score: number) {
  if (score >= 70) return "text-emerald-700 bg-emerald-50 ring-emerald-200/60";
  if (score >= 40) return "text-amber-700 bg-amber-50 ring-amber-200/60";
  return "text-red-700 bg-red-50 ring-red-200/60";
}

function failPct(eq: EquipmentRow) {
  if (eq.failure_probability == null) return "—";
  const pct = eq.failure_probability <= 1 ? Math.round(eq.failure_probability * 100) : Math.round(eq.failure_probability);
  return `${pct}%`;
}

function StatPill({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className={`rounded-lg bg-gradient-to-br from-white to-tata-blue-pale/40 px-3 py-2 ring-1 ring-tata-border/70 ${className}`}>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-tata-muted">{label}</p>
      <p className="mt-0.5 text-sm font-bold tabular-nums text-tata-ink">{value}</p>
    </div>
  );
}

export function EquipmentFleetTable({ fleet }: { fleet: EquipmentRow[] }) {
  return (
    <div className="panel-flush overflow-hidden">
      <div className="border-b border-tata-border/80 bg-gradient-to-r from-tata-blue-pale/60 to-white px-5 py-3.5">
        <h2 className="text-sm font-semibold text-tata-ink">Fleet Registry</h2>
        <p className="text-xs text-tata-muted">Five C-MAPSS FD001 units mapped to plant equipment</p>
      </div>

      <div className="hidden border-b border-tata-border/60 bg-white/50 px-5 py-2.5 lg:grid lg:grid-cols-[minmax(220px,1.2fr)_minmax(280px,1fr)_140px] lg:gap-6">
        <span className="stat-label">Asset</span>
        <span className="stat-label">Status</span>
        <span className="stat-label text-right">Actions</span>
      </div>

      <div className="divide-y divide-tata-border/50">
        {fleet.map((eq, i) => {
          const health = Math.round(eq.health_score ?? 0);
          const codeTag = eq.equipment_code.split("-")[0];

          return (
            <div
              key={eq.id}
              className="grid gap-4 px-5 py-4 transition hover:bg-gradient-to-r hover:from-tata-blue-pale/40 hover:to-transparent lg:grid-cols-[minmax(220px,1.2fr)_minmax(280px,1fr)_140px] lg:items-center lg:gap-6 lg:py-5"
            >
              {/* Asset */}
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-tata-blue to-tata-blue-light text-[11px] font-bold text-white shadow-md ring-2 ring-white">
                  {codeTag}
                </div>
                <div className="min-w-0">
                  <p className="font-mono text-sm font-bold text-tata-ink">{eq.equipment_code}</p>
                  <p className="truncate text-sm font-medium text-tata-ink">{eq.name}</p>
                  <p className="truncate text-xs text-tata-muted">
                    {eq.location ?? "—"} · {eq.equipment_type?.replace(/_/g, " ") ?? "asset"}
                  </p>
                </div>
              </div>

              {/* Status metrics */}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2 lg:gap-2 xl:grid-cols-4">
                <StatPill
                  label="Health"
                  value={`${health}%`}
                  className={healthTone(health)}
                />
                <StatPill
                  label="RUL"
                  value={eq.rul_hours != null ? `${Math.round(eq.rul_hours)}h` : "—"}
                />
                <StatPill label="Unit" value={`U${eq.cmapss_unit ?? i + 1}`} />
                <StatPill label="Fail %" value={failPct(eq)} />
              </div>

              {/* Actions */}
              <div className="flex flex-col items-stretch gap-2 border-t border-tata-border/50 pt-3 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
                <p className="stat-label lg:hidden">Actions</p>
                <div className="flex items-center justify-between gap-2 lg:flex-col lg:items-stretch">
                  <div className="flex items-center gap-2">
                    <RiskBadge level={eq.risk_level} />
                    {(eq.alerts ?? 0) > 0 && (
                      <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-700 ring-1 ring-red-200/60">
                        {eq.alerts} alert{eq.alerts === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>
                  <Link
                    href={`/monitor?equipment=${eq.id}`}
                    className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-tata-blue to-tata-blue-light px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:brightness-110"
                  >
                    <Radio className="h-3.5 w-3.5" />
                    Monitor
                    <ArrowRight className="h-3.5 w-3.5 opacity-80" />
                  </Link>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
