"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ThumbsDown, ThumbsUp, TrendingUp } from "lucide-react";

type Stats = {
  feedback_events: number;
  recommendation_accuracy_pct: number;
  most_corrected_fault_type: string | null;
  helpful_count: number;
  not_helpful_count: number;
};

export function FeedbackStatsWidget({ compact = false }: { compact?: boolean }) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    api.feedbackStats().then(setStats).catch(() => {});
  }, []);

  if (!stats) {
    return <p className="text-sm text-tata-muted">Loading feedback metrics…</p>;
  }

  const cards = [
    {
      label: "Feedback Events",
      value: String(stats.feedback_events),
      sub: `${stats.helpful_count} helpful · ${stats.not_helpful_count} not helpful`,
      icon: ThumbsUp,
    },
    {
      label: "Recommendation Accuracy",
      value: `${stats.recommendation_accuracy_pct}%`,
      sub: "Based on engineer 👍/👎 ratings",
      icon: TrendingUp,
    },
    {
      label: "Most Corrected Fault Type",
      value: stats.most_corrected_fault_type || "—",
      sub: stats.most_corrected_fault_type
        ? "Deprioritized in future RCA"
        : "No negative feedback yet",
      icon: ThumbsDown,
    },
  ];

  return (
    <div className={`grid gap-3 ${compact ? "sm:grid-cols-3" : "sm:grid-cols-3"}`}>
      {cards.map(({ label, value, sub, icon: Icon }) => (
        <div key={label} className="stat-card">
          <div className="mb-2 flex items-center gap-2">
            <Icon className="h-4 w-4 text-tata-blue" />
            <p className="stat-label">{label}</p>
          </div>
          <p className={`font-bold text-tata-ink ${compact ? "text-lg" : "text-2xl"}`}>{value}</p>
          <p className="mt-1 text-xs text-tata-muted">{sub}</p>
        </div>
      ))}
    </div>
  );
}
