import type { LucideIcon } from "lucide-react";

const accentBorder = {
  blue: "border-l-tata-blue",
  amber: "border-l-amber-400",
  red: "border-l-red-400",
  green: "border-l-emerald-500",
};

export function StatTile({
  label,
  value,
  hint,
  icon: Icon,
  accent = "blue",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  accent?: "blue" | "amber" | "red" | "green";
  index?: number;
}) {
  return (
    <div className={`stat-card border-l-4 ${accentBorder[accent]}`}>
      <div className="flex items-start gap-4">
        {Icon && (
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-tata-blue/10 text-tata-blue">
            <Icon className="h-5 w-5" strokeWidth={1.5} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="stat-label">{label}</p>
          <p className="stat-value">{value}</p>
          {hint && (
            <p className="mt-2 text-[11px] font-medium text-tata-muted">{hint}</p>
          )}
        </div>
      </div>
    </div>
  );
}
