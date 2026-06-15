"use client";

import type { RefObject } from "react";
import Link from "next/link";
import { ExternalLink, Send, Sparkles } from "lucide-react";

export type QuickPrompt = {
  label: string;
  query?: string;
  href?: string;
  variant?: "link" | "prompt";
};

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading?: boolean;
  placeholder?: string;
  inputRef?: RefObject<HTMLInputElement | null>;
  quickPrompts?: QuickPrompt[];
  onPrompt?: (query: string) => void;
  provider?: string;
  modeLabel?: string;
  followUps?: string[];
  onFollowUp?: (query: string) => void;
};

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  loading = false,
  placeholder = "Type your question…",
  inputRef,
  quickPrompts = [],
  onPrompt,
  provider,
  modeLabel,
  followUps = [],
  onFollowUp,
}: Props) {
  const shortcutQueries = new Set(
    quickPrompts.map((p) => (p.query || "").trim().toLowerCase()).filter(Boolean)
  );
  const uniqueFollowUps = followUps.filter(
    (fq) => !shortcutQueries.has(fq.trim().toLowerCase())
  );

  return (
    <div className="chat-composer shrink-0 border-t border-tata-border/60 bg-white shadow-[0_-4px_24px_-8px_rgba(0,93,164,0.12)]">
      {(quickPrompts.length > 0 || uniqueFollowUps.length > 0) && (
        <div className="border-b border-tata-border/40 px-4 py-2">
          <div className="mx-auto max-w-3xl">
            <div className="flex items-center gap-2 overflow-x-auto pb-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <span className="flex shrink-0 items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-tata-muted">
                <Sparkles className="h-3 w-3 text-tata-blue" />
                {uniqueFollowUps.length > 0 ? "Continue" : modeLabel ? modeLabel : "Quick"}
              </span>
              {uniqueFollowUps.length > 0
                ? uniqueFollowUps.map((fq) => (
                    <button
                      key={fq}
                      type="button"
                      onClick={() => onFollowUp?.(fq)}
                      disabled={loading}
                      className="chat-suggestion-chip shrink-0 whitespace-nowrap disabled:opacity-50"
                    >
                      {fq.slice(0, 48)}
                      {fq.length > 48 ? "…" : ""}
                    </button>
                  ))
                : quickPrompts.map((p) => {
                    if (p.href) {
                      return (
                        <Link
                          key={p.label}
                          href={p.href}
                          className="chat-link-chip inline-flex shrink-0 items-center gap-1 whitespace-nowrap"
                        >
                          {p.label}
                          <ExternalLink className="h-3 w-3 opacity-50" />
                        </Link>
                      );
                    }
                    return (
                      <button
                        key={p.label}
                        type="button"
                        onClick={() => p.query && onPrompt?.(p.query)}
                        disabled={loading}
                        className="chat-suggestion-chip shrink-0 whitespace-nowrap disabled:opacity-50"
                      >
                        {p.label}
                      </button>
                    );
                  })}
            </div>
          </div>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        className="p-4 pt-2"
      >
        <div className="mx-auto flex max-w-3xl flex-col gap-1.5">
          <div className="chat-input-shell flex gap-2 p-1.5">
            <input
              ref={inputRef}
              className="min-w-0 flex-1 border-0 bg-transparent px-3 py-3 text-sm text-tata-ink outline-none placeholder:text-tata-muted/60"
              placeholder={placeholder}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              disabled={loading}
            />
            <button
              type="submit"
              className="inline-flex shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-tata-blue to-[#0078d4] px-5 py-3 text-white shadow-md transition hover:shadow-lg disabled:opacity-50"
              disabled={loading || !value.trim()}
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
          {(() => {
            if (!provider || provider === "rule_based") return null;
            return (
              <p className="px-1 text-center text-[10px] text-tata-muted">
                ForgeMind · Agentic AI
              </p>
            );
          })()}
        </div>
      </form>
    </div>
  );
}
