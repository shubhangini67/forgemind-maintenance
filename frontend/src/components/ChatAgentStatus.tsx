"use client";

import { CheckCircle2, Loader2, Sparkles } from "lucide-react";

const STEPS = [
  "Reading sensors",
  "Predicting health",
  "Diagnosing causes",
  "Planning actions",
  "Writing answer",
];

export function ChatAgentStatus({ loading }: { loading?: boolean }) {
  if (!loading) return null;

  return (
    <div className="mx-auto mb-3 w-full max-w-3xl rounded-xl border border-tata-border/70 bg-white px-4 py-3 shadow-sm">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-tata-ink">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-tata-blue" />
        ForgeMind is reasoning…
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {STEPS.map((step, i) => (
          <div key={step} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-[10px] text-tata-muted">→</span>}
            <span className="inline-flex items-center gap-1 rounded-full bg-tata-blue-pale/60 px-2 py-0.5 text-[10px] font-medium text-tata-blue">
              {i < STEPS.length - 1 ? (
                <CheckCircle2 className="h-3 w-3 opacity-40" />
              ) : (
                <Loader2 className="h-3 w-3 animate-spin" />
              )}
              {step}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChatThinkingBubble() {
  return (
    <div className="flex w-full justify-start">
      <div className="chat-bubble-assistant flex items-center gap-2 px-4 py-3 text-sm text-tata-muted">
        <Sparkles className="h-4 w-4 shrink-0 text-tata-blue" />
        <span className="flex gap-1">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-tata-blue [animation-delay:-0.2s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-tata-blue [animation-delay:-0.1s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-tata-blue" />
        </span>
        <span>ForgeMind is thinking…</span>
      </div>
    </div>
  );
}
