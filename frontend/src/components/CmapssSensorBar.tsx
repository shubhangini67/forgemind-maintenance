"use client";

import { Activity, Gauge, Thermometer, Waves, Zap } from "lucide-react";

function formatNum(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

function healthStatus(pct: number) {
  if (pct >= 65) return { label: "Healthy", className: "bg-emerald-50 text-emerald-700 ring-emerald-200" };
  if (pct >= 45) return { label: "Degrading", className: "bg-amber-50 text-amber-700 ring-amber-200" };
  return { label: "At risk", className: "bg-red-50 text-red-700 ring-red-200" };
}

export function CmapssSensorBar({
  snapshot,
  compact = false,
}: {
  snapshot: Record<string, any> | null | undefined;
  compact?: boolean;
}) {
  if (!snapshot || snapshot.temperature == null) return null;

  const health = Number(snapshot.health_indicator);
  const status = Number.isFinite(health) ? healthStatus(health) : null;

  const tiles = [
    { label: "Temperature", value: `${formatNum(snapshot.temperature, 1)}°C`, icon: Thermometer },
    { label: "Vibration", value: `${formatNum(snapshot.vibration, 2)} mm/s`, icon: Waves },
    { label: "Pressure", value: `${formatNum(snapshot.pressure, 1)} bar`, icon: Gauge },
    { label: "Motor current", value: `${formatNum(snapshot.motor_current, 1)} A`, icon: Zap },
  ];

  if (compact) {
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-tata-muted">
        <span className="inline-flex items-center gap-1 font-medium text-tata-ink">
          <Activity className="h-3 w-3 text-tata-blue" /> Live
        </span>
        {tiles.map(({ label, value }) => (
          <span key={label} className="tabular-nums">
            <span className="text-tata-muted/70">{label.split(" ")[0]}</span>{" "}
            <span className="font-semibold text-tata-ink">{value}</span>
          </span>
        ))}
        <span className="tabular-nums">
          <span className="text-tata-muted/70">RUL</span>{" "}
          <span className="font-semibold text-tata-ink">{formatNum(snapshot.rul_hours, 0)}h</span>
        </span>
        {status && (
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${status.className}`}>
            {status.label} · {formatNum(health, 0)}%
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="panel-flush mb-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-tata-border/80 bg-gradient-to-r from-tata-blue-pale/40 to-white px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-tata-blue" />
          <span className="text-xs font-semibold text-tata-ink">Live readings</span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-tata-muted">
          <span>Cycle {snapshot.cycle ?? "—"}</span>
          <span aria-hidden>·</span>
          <span>{formatNum(snapshot.rul_hours, 0)}h remaining</span>
          {status && (
            <>
              <span aria-hidden>·</span>
              <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${status.className}`}>
                {status.label} · {formatNum(health, 0)}%
              </span>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4">
        {tiles.map(({ label, value, icon: Icon }) => (
          <div key={label} className="metric-tile border-t border-tata-border/60 sm:border-l sm:border-t-0 first:sm:border-l-0">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-tata-blue/10 text-tata-blue">
              <Icon className="h-4 w-4" strokeWidth={1.75} />
            </div>
            <div className="min-w-0">
              <p className="stat-label">{label}</p>
              <p className="mt-0.5 truncate text-base font-semibold tabular-nums text-tata-ink">{value}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
