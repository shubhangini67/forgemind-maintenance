"use client";

import { useState } from "react";

type Props = {
  onSubmit: (positive: boolean) => void | Promise<void>;
  label?: string;
  compact?: boolean;
};

export function FeedbackBar({ onSubmit, label = "Was this recommendation helpful?", compact = false }: Props) {
  const [state, setState] = useState<"idle" | "saving" | "done" | "error">("idle");
  const [choice, setChoice] = useState<boolean | null>(null);

  async function handle(positive: boolean) {
    if (state === "saving" || state === "done") return;
    setState("saving");
    try {
      await Promise.resolve(onSubmit(positive));
      setChoice(positive);
      setState("done");
    } catch {
      setState("error");
    }
  }

  if (state === "done") {
    return (
      <p className={`font-medium text-emerald-600 ${compact ? "text-[10px]" : "text-xs"}`}>
        {choice
          ? "Thanks — marked as helpful. Feedback improves future recommendations."
          : "Thanks — we'll adjust future recommendations based on your feedback."}
      </p>
    );
  }

  if (state === "error") {
    return <p className={`text-red-600 ${compact ? "text-[10px]" : "text-xs"}`}>Could not save feedback — try again.</p>;
  }

  return (
    <div className={`flex flex-wrap items-center gap-2 ${compact ? "" : "mt-1"}`}>
      <span className={`text-tata-muted ${compact ? "text-[10px]" : "text-xs"}`}>{label}</span>
      <button
        type="button"
        onClick={() => handle(true)}
        disabled={state === "saving"}
        className={`rounded border border-emerald-500/30 bg-emerald-50/50 transition hover:bg-emerald-50 disabled:opacity-50 ${
          compact ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs"
        }`}
        title="Helpful"
      >
        {state === "saving" ? "…" : "👍 Helpful"}
      </button>
      <button
        type="button"
        onClick={() => handle(false)}
        disabled={state === "saving"}
        className={`rounded border border-red-500/30 bg-red-50/50 transition hover:bg-red-50 disabled:opacity-50 ${
          compact ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs"
        }`}
        title="Not Helpful"
      >
        {state === "saving" ? "…" : "👎 Not Helpful"}
      </button>
    </div>
  );
}
