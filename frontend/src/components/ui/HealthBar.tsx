export function HealthBar({ value, className = "" }: { value: number; className?: string }) {
  const v = Math.max(0, Math.min(100, value));
  const color =
    v >= 70
      ? "from-emerald-400 to-emerald-500"
      : v >= 40
        ? "from-amber-400 to-amber-500"
        : "from-red-400 to-red-500";

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-tata-border/60 ring-1 ring-inset ring-black/[0.04]">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${color} transition-all duration-500`}
          style={{ width: `${v}%` }}
        />
      </div>
      <span className="w-9 shrink-0 text-right text-xs font-bold tabular-nums text-tata-ink">{Math.round(v)}%</span>
    </div>
  );
}
