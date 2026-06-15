import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { HealthBar } from "@/components/ui/HealthBar";
import { RiskBadge } from "@/components/RiskBadge";

type FleetAsset = {
  id: number;
  equipment_code: string;
  name: string;
  cmapss_unit?: number;
  health_score?: number;
  rul_hours?: number;
  risk_level?: string;
};

const GRID =
  "grid grid-cols-[minmax(140px,1.4fr)_minmax(56px,0.5fr)_minmax(120px,1fr)_minmax(64px,0.5fr)_minmax(88px,0.6fr)_40px] items-center gap-3";

export function FleetStatusList({ fleet }: { fleet: FleetAsset[] }) {
  return (
    <div className="panel-flush overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-tata-border/80 bg-gradient-to-r from-tata-blue-pale/60 to-white px-5 py-3.5">
        <div>
          <h2 className="text-sm font-semibold text-tata-ink">Equipment Status</h2>
          <p className="text-xs text-tata-muted">C-MAPSS unit mapped to each plant asset</p>
        </div>
        <Link
          href="/equipment"
          className="shrink-0 text-[11px] font-semibold uppercase tracking-wider text-tata-blue transition hover:underline"
        >
          View all →
        </Link>
      </div>

      <div className={`${GRID} border-b border-tata-border/60 bg-white/50 px-5 py-2.5 max-md:hidden`}>
        {["Asset", "Unit", "Health", "RUL", "Risk", ""].map((h) => (
          <span key={h || "action"} className="stat-label">
            {h}
          </span>
        ))}
      </div>

      <div className="divide-y divide-tata-border/50">
        {fleet.map((a) => (
          <Link
            key={a.id}
            href={`/monitor?equipment=${a.id}`}
            className={`group ${GRID} px-5 py-4 transition hover:bg-gradient-to-r hover:from-tata-blue-pale/50 hover:to-transparent max-md:grid-cols-1 max-md:gap-3 max-md:border-b max-md:border-tata-border/40 max-md:py-5`}
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-tata-blue to-tata-blue-light text-[10px] font-bold text-white shadow-sm">
                {a.equipment_code.split("-")[0]}
              </div>
              <div className="min-w-0">
                <p className="truncate font-semibold text-tata-ink group-hover:text-tata-blue">{a.equipment_code}</p>
                <p className="truncate text-xs text-tata-muted">{a.name}</p>
              </div>
            </div>

            <span className="font-mono text-xs font-semibold text-tata-blue max-md:text-left">
              <span className="mr-2 text-tata-muted md:hidden">Unit</span>U{a.cmapss_unit ?? "—"}
            </span>

            <div className="max-md:w-full">
              <span className="mb-1 block text-tata-muted md:hidden stat-label">Health</span>
              <HealthBar value={a.health_score ?? 0} />
            </div>

            <span className="text-sm font-semibold tabular-nums text-tata-ink">
              <span className="mr-2 text-tata-muted md:hidden stat-label">RUL</span>
              {a.rul_hours != null ? `${Math.round(a.rul_hours)}h` : "—"}
            </span>

            <div>
              <span className="mb-1 block md:hidden stat-label">Risk</span>
              <RiskBadge level={a.risk_level} />
            </div>

            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-tata-blue/5 text-tata-muted transition group-hover:bg-tata-blue group-hover:text-white max-md:hidden">
              <ArrowRight className="h-4 w-4" />
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
