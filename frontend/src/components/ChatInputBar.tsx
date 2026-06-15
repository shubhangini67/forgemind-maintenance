"use client";

import type { RefObject } from "react";
import { Send } from "lucide-react";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading?: boolean;
  placeholder?: string;
  inputRef?: RefObject<HTMLInputElement | null>;
};

export function ChatInputBar({
  value,
  onChange,
  onSubmit,
  loading = false,
  placeholder = "Type your question…",
  inputRef,
}: Props) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="border-t border-tata-border/80 bg-gradient-to-r from-white via-white to-tata-blue-pale/40 p-4"
    >
      <div className="flex gap-2 rounded-xl bg-white p-1.5 shadow-sm ring-1 ring-tata-border/80">
        <input
          ref={inputRef}
          className="min-w-0 flex-1 border-0 bg-transparent px-3 py-2 text-sm text-tata-ink outline-none placeholder:text-tata-muted/70"
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={loading}
        />
        <button
          type="submit"
          className="inline-flex shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-tata-blue to-tata-blue-light px-4 py-2 text-white shadow-sm transition hover:from-tata-blue-dark hover:to-tata-blue disabled:opacity-50"
          disabled={loading || !value.trim()}
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </form>
  );
}
