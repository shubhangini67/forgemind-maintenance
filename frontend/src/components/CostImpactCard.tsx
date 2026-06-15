"use client";

import { IndianRupee, Shield, TrendingDown, TrendingUp, Wrench } from "lucide-react";

type Props = {
  asset: {
    equipment_code: string;
    name?: string;
    downtime_cost_inr?: number;
    maintenance_cost_inr?: number;
    avoided_loss_inr?: number;
    estimated_savings_inr?: number;
    roi_pct?: number;
    downtime_cost_per_day_inr?: number;
    expected_downtime_hours?: number;
  };
  compact?: boolean;
};

function fmtLakhs(n: number | undefined) {
  if (n == null) return "—";
  return `₹${(n / 100_000).toFixed(1)}L`;
}

export function CostImpactCard({ asset, compact = false }: Props) {
  const items = [
    { label: "Downtime cost", value: fmtLakhs(asset.downtime_cost_inr), icon: TrendingDown, color: "text-red-600" },
    { label: "Maintenance cost", value: fmtLakhs(asset.maintenance_cost_inr), icon: Wrench, color: "text-amber-700" },
    { label: "Avoided loss", value: fmtLakhs(asset.avoided_loss_inr), icon: Shield, color: "text-tata-blue" },
    { label: "Est. savings", value: fmtLakhs(asset.estimated_savings_inr), icon: TrendingUp, color: "text-emerald-600" },
    { label: "ROI", value: asset.roi_pct != null ? `${asset.roi_pct}%` : "—", icon: IndianRupee, color: "text-tata-ink" },
  ];

  return (
    <div className={`rounded-xl border border-tata-border bg-white ${compact ? "p-3" : "p-4"}`}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-tata-muted">Cost impact</p>
          <p className="font-semibold text-tata-ink">{asset.equipment_code}</p>
          {asset.name && !compact && <p className="text-xs text-tata-muted">{asset.name}</p>}
        </div>
        {asset.downtime_cost_per_day_inr != null && (
          <p className="text-right text-[10px] text-tata-muted">
            ₹{(asset.downtime_cost_per_day_inr / 1000).toFixed(0)}K/day
            {asset.expected_downtime_hours != null && ` · ${asset.expected_downtime_hours}h exposure`}
          </p>
        )}
      </div>
      <div className={`grid gap-2 ${compact ? "grid-cols-2 sm:grid-cols-5" : "grid-cols-2 sm:grid-cols-5"}`}>
        {items.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-lg border border-tata-border/60 bg-tata-blue-pale/20 px-2 py-2">
            <div className="mb-1 flex items-center gap-1">
              <Icon className={`h-3 w-3 ${color}`} />
              <span className="text-[9px] font-semibold uppercase text-tata-muted">{label}</span>
            </div>
            <p className={`text-sm font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
