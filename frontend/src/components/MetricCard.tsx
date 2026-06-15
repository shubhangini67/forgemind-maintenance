import { LucideIcon } from "lucide-react";

export function MetricCard({
  label,
  value,
  sub,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon?: LucideIcon;
  accent?: "red" | "green" | "orange" | "default";
}) {
  const accentClass =
    accent === "red"
      ? "border-red-500/30 bg-red-500/5"
      : accent === "green"
        ? "border-emerald-500/30 bg-emerald-500/5"
        : accent === "orange"
          ? "border-orange-500/30 bg-orange-500/5"
          : "border-tata-border bg-white/5";

  const iconColor =
    accent === "red" ? "text-red-400" : accent === "green" ? "text-emerald-400" : accent === "orange" ? "text-orange-400" : "text-blue-400";

  return (
    <div className={`card ${accentClass}`}>
      <div className="flex items-start justify-between">
        <p className="section-title">{label}</p>
        {Icon && <Icon className={`h-5 w-5 ${iconColor}`} />}
      </div>
      <p className="mt-2 text-3xl font-bold tracking-tight text-white">{value}</p>
      {sub && <p className="mt-1 text-xs text-tata-muted">{sub}</p>}
    </div>
  );
}
