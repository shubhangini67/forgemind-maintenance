"use client";

import { IndianRupee, Package, Timer, TrendingUp } from "lucide-react";
import { RiskBadge } from "@/components/RiskBadge";

type Props = {
  spareStock?: number | null;
  leadTimeDays?: number | null;
  procurementRisk?: string | null;
  businessImpactInr?: number | null;
  rulDays?: number | null;
  rulHours?: number | null;
  riskEscalated?: boolean;
  escalationReason?: string | null;
  criticalSparePart?: string | null;
  riskLevel?: string | null;
  compact?: boolean;
};

function procColor(level?: string | null) {
  if (level === "critical") return "border-red-300 bg-red-50";
  if (level === "high") return "border-orange-300 bg-orange-50";
  if (level === "medium") return "border-amber-300 bg-amber-50";
  return "border-emerald-300 bg-emerald-50";
}

export function ProcureRiskPanel({
  spareStock,
  leadTimeDays,
  procurementRisk,
  businessImpactInr,
  rulDays,
  rulHours,
  riskEscalated,
  escalationReason,
  criticalSparePart,
  riskLevel,
  compact = false,
}: Props) {
  const rulLabel =
    rulHours != null && rulHours < 48
      ? `${Math.round(rulHours)}h`
      : rulDays != null
        ? `${rulDays.toFixed(1)}d`
        : "—";

  return (
    <div className={`rounded-xl border ${procColor(procurementRisk)} ${compact ? "p-3" : "p-4"}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-bold uppercase tracking-wider text-tata-ink/80">
          Procurement & business impact
        </p>
        <div className="flex items-center gap-2">
          {procurementRisk && (
            <span className="rounded-full border border-current px-2 py-0.5 text-[10px] font-semibold uppercase">
              Procurement {procurementRisk}
            </span>
          )}
          {riskLevel && <RiskBadge level={riskLevel} />}
        </div>
      </div>

      <div className={`grid gap-3 ${compact ? "grid-cols-2 sm:grid-cols-4" : "sm:grid-cols-2 lg:grid-cols-4"}`}>
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase text-tata-muted">
            <Package className="h-3.5 w-3.5" /> Stock
          </div>
          <p className={`text-lg font-bold ${spareStock === 0 ? "text-red-600" : "text-tata-ink"}`}>
            {spareStock ?? "—"}
          </p>
          {criticalSparePart && <p className="text-[10px] text-tata-muted">{criticalSparePart}</p>}
        </div>
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase text-tata-muted">
            <Timer className="h-3.5 w-3.5" /> Lead time
          </div>
          <p className="text-lg font-bold text-tata-ink">{leadTimeDays != null ? `${leadTimeDays}d` : "—"}</p>
        </div>
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase text-tata-muted">
            <TrendingUp className="h-3.5 w-3.5" /> RUL
          </div>
          <p className={`text-lg font-bold ${rulDays != null && leadTimeDays != null && rulDays < leadTimeDays ? "text-red-600" : "text-tata-ink"}`}>
            {rulLabel}
          </p>
        </div>
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase text-tata-muted">
            <IndianRupee className="h-3.5 w-3.5" /> Business impact
          </div>
          <p className="text-lg font-bold text-tata-ink">
            {businessImpactInr != null ? `₹${(businessImpactInr / 100000).toFixed(1)}L` : "—"}
          </p>
        </div>
      </div>

      {riskEscalated && escalationReason && (
        <p className="mt-3 rounded-lg border border-red-200 bg-white/70 px-3 py-2 text-xs text-red-700">
          <span className="font-semibold">Risk escalated:</span> {escalationReason}
        </p>
      )}
    </div>
  );
}
