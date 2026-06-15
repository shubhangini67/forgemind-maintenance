import { riskColor } from "@/lib/api";

export function RiskBadge({ level }: { level?: string }) {
  if (!level) return null;
  return (
    <span className={`badge rounded-full ring-1 ring-inset ring-black/5 ${riskColor(level)}`}>{level}</span>
  );
}
