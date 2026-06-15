"use client";

import { useEffect, useState } from "react";
import { Pencil, Sparkles, X, Check } from "lucide-react";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { ChatThinkingBubble } from "@/components/ChatAgentStatus";
import type { ExplainabilityBundle } from "@/components/ExplainabilityDashboard";
import type { AIReasoningPanelData } from "@/components/AIReasoningPanel";

export type ChatMessageItem = {
  id?: number;
  role: string;
  content: string;
  agent_type?: string;
  follow_ups?: string[];
  reasoning_panel?: AIReasoningPanelData | null;
  explainability?: ExplainabilityBundle | null;
  chat_style?: "conversational" | "maintenance" | null;
  llm_provider?: string | null;
};

type Props = {
  messages: ChatMessageItem[];
  loading?: boolean;
  lastAssistantIdx?: number | null;
  compact?: boolean;
  onSend: (text: string, opts?: { branchFromMessageId?: number; replaceFromIndex?: number }) => void;
  onFeedback?: (positive: boolean) => void | Promise<void>;
  showFeedback?: boolean;
};

function AgentBadge({ style }: { style?: string | null; provider?: string | null }) {
  if (style === "conversational") return null;
  return (
    <div className="mb-2 flex items-center gap-1.5">
      <span className="inline-flex items-center gap-1 rounded-full bg-tata-blue-pale/70 px-2 py-0.5 text-[10px] font-semibold text-tata-blue">
        <Sparkles className="h-3 w-3" />
        ForgeMind · Agentic AI
      </span>
    </div>
  );
}

function displayContent(content: string): string {
  const text = (content || "").trim();
  if (text) return text;
  return "No response was generated. Please try again or start a new chat.";
}

export function ChatMessageList({
  messages,
  loading = false,
  lastAssistantIdx = null,
  compact = false,
  onSend,
  onFeedback,
  showFeedback = false,
}: Props) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [feedbackState, setFeedbackState] = useState<"idle" | "saving" | "done" | "error">("idle");
  const [feedbackChoice, setFeedbackChoice] = useState<boolean | null>(null);

  useEffect(() => {
    setFeedbackState("idle");
    setFeedbackChoice(null);
  }, [lastAssistantIdx]);

  async function handleFeedback(positive: boolean) {
    if (!onFeedback || feedbackState === "saving" || feedbackState === "done") return;
    setFeedbackState("saving");
    try {
      await Promise.resolve(onFeedback(positive));
      setFeedbackChoice(positive);
      setFeedbackState("done");
    } catch {
      setFeedbackState("error");
    }
  }

  function startEdit(index: number) {
    const msg = messages[index];
    if (msg.role !== "user" || loading) return;
    setEditingIndex(index);
    setEditDraft(msg.content);
  }

  function cancelEdit() {
    setEditingIndex(null);
    setEditDraft("");
  }

  function submitEdit(index: number) {
    const text = editDraft.trim();
    if (!text || loading) return;
    const msg = messages[index];
    onSend(text, {
      branchFromMessageId: msg.id,
      replaceFromIndex: index,
    });
    setEditingIndex(null);
    setEditDraft("");
  }

  return (
    <div className="chat-thread mx-auto flex w-full max-w-3xl flex-col gap-4 py-1">
      {messages.map((msg, i) => (
        <div
          key={msg.id ?? `msg-${i}`}
          className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`flex flex-col gap-1.5 ${
              msg.role === "user" ? "chat-row-user" : "chat-row-assistant"
            }`}
          >
            {editingIndex === i && msg.role === "user" ? (
              <div className="surface w-full rounded-xl p-4 ring-1 ring-tata-blue/20">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-tata-blue">
                  Edit question
                </p>
                <textarea
                  className="input min-h-[80px] w-full resize-y text-sm"
                  value={editDraft}
                  onChange={(e) => setEditDraft(e.target.value)}
                  disabled={loading}
                  autoFocus
                />
                <div className="mt-2 flex justify-end gap-2">
                  <button type="button" onClick={cancelEdit} className="btn-ghost px-2 py-1.5 text-xs" disabled={loading}>
                    <X className="mr-1 inline h-3 w-3" />
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={() => submitEdit(i)}
                    className="btn-primary px-2 py-1.5 text-xs"
                    disabled={loading || !editDraft.trim()}
                  >
                    <Check className="mr-1 inline h-3 w-3" />
                    Save & resubmit
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div
                  className={`relative leading-relaxed ${compact ? "text-xs" : "text-sm"} ${
                    msg.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"
                  }`}
                >
                  {msg.role === "assistant" && msg.chat_style !== "conversational" && (
                    <AgentBadge style={msg.chat_style} provider={msg.llm_provider} />
                  )}
                  {msg.role === "user" ? (
                    msg.content
                  ) : (
                    <MarkdownRenderer content={displayContent(msg.content)} className="prose-chat" />
                  )}
                  {msg.role === "user" && !loading && (
                    <button
                      type="button"
                      onClick={() => startEdit(i)}
                      className={`absolute -bottom-3 right-0 flex items-center gap-1 border border-tata-border bg-white px-2 py-0.5 text-[10px] font-medium text-tata-muted shadow-sm transition hover:border-tata-blue/40 hover:text-tata-blue ${
                        compact ? "-bottom-2.5 px-1.5 py-px text-[9px]" : ""
                      }`}
                      title="Edit & resubmit"
                    >
                      <Pencil className="h-3 w-3" />
                      Edit
                    </button>
                  )}
                </div>

                {showFeedback &&
                  msg.role === "assistant" &&
                  msg.chat_style !== "conversational" &&
                  msg.agent_type !== "system" &&
                  i === lastAssistantIdx &&
                  !loading &&
                  onFeedback && (
                    <div className="pl-1">
                      {feedbackState === "done" ? (
                        <p className="text-[10px] font-medium text-emerald-600">
                          {feedbackChoice ? "Thanks — marked as helpful." : "Thanks — we'll use this to improve answers."}
                        </p>
                      ) : feedbackState === "error" ? (
                        <p className="text-[10px] text-red-600">Could not save feedback — try again.</p>
                      ) : (
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => handleFeedback(true)}
                            disabled={feedbackState === "saving"}
                            className="rounded-full border border-emerald-500/30 px-2.5 py-0.5 text-[10px] text-emerald-600 transition hover:bg-emerald-50 disabled:opacity-50"
                          >
                            {feedbackState === "saving" ? "Saving…" : "Helpful"}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleFeedback(false)}
                            disabled={feedbackState === "saving"}
                            className="rounded-full border border-red-500/30 px-2.5 py-0.5 text-[10px] text-red-600 transition hover:bg-red-50 disabled:opacity-50"
                          >
                            {feedbackState === "saving" ? "Saving…" : "Not helpful"}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
              </>
            )}
          </div>
        </div>
      ))}
      {loading && <ChatThinkingBubble />}
    </div>
  );
}
