"use client";

export function HealthGauge({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const safe = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
  const getColor = (s: number) => {
    if (s >= 80) return { stroke: "#22c55e", text: "text-emerald-400", bg: "bg-emerald-500/10" };
    if (s >= 60) return { stroke: "#eab308", text: "text-yellow-400", bg: "bg-yellow-500/10" };
    if (s >= 35) return { stroke: "#f97316", text: "text-orange-400", bg: "bg-orange-500/10" };
    return { stroke: "#ef4444", text: "text-red-400", bg: "bg-red-500/10" };
  };

  const { stroke, text, bg } = getColor(safe);
  const sizes = { sm: 56, md: 72, lg: 100 };
  const dim = sizes[size];
  const r = dim / 2 - 7;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (safe / 100) * circumference;

  return (
    <div className={`relative flex items-center justify-center rounded-full ${bg}`} style={{ width: dim, height: dim }}>
      <svg width={dim} height={dim} className="absolute -rotate-90">
        <circle cx={dim / 2} cy={dim / 2} r={r} fill="none" stroke="#1f2937" strokeWidth={5} />
        <circle
          cx={dim / 2}
          cy={dim / 2}
          r={r}
          fill="none"
          stroke={stroke}
          strokeWidth={5}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span className={`relative font-bold ${text} ${size === "lg" ? "text-lg" : size === "md" ? "text-sm" : "text-xs"}`}>
        {Math.round(safe)}
      </span>
    </div>
  );
}
