"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Brain, ChevronRight, ExternalLink, MessageSquarePlus, X } from "lucide-react";
import { ChatMessageList, ChatMessageItem } from "@/components/ChatMessageList";
import { reasoningFromThoughts } from "@/components/AIReasoningPanel";
import { ChatComposer } from "@/components/ChatComposer";
import { EquipmentScopeSelector } from "@/components/EquipmentScopeSelector";
import { getContextualPrompts } from "@/lib/chatPrompts";
import { api, getToken } from "@/lib/api";

const STORAGE_KEY = "spmw_widget_conversation_id";

type Message = ChatMessageItem;

const SECTION_CONTEXT: Record<string, { label: string; prompts: { label: string; query: string }[] }> = {
  home: {
    label: "Portal Home",
    prompts: [
      { label: "Fleet overview", query: "Give me a quick overview of all 5 plant assets and their current health" },
      { label: "Today's priorities", query: "What maintenance actions should I focus on today?" },
    ],
  },
  monitor: {
    label: "Live Monitor",
    prompts: [
      { label: "Explain readings", query: "Explain the current sensor readings for this asset — temperature, vibration, and health trend" },
      { label: "Threshold check", query: "Are any sensor values approaching alert thresholds on this asset?" },
    ],
  },
  dashboard: {
    label: "Dashboard",
    prompts: [
      { label: "Fleet summary", query: "Summarize current fleet health across all 5 C-MAPSS assets" },
      { label: "Needs attention", query: "Which assets need immediate maintenance attention and why?" },
    ],
  },
  alerts: {
    label: "Alerts",
    prompts: [
      { label: "Triage alerts", query: "Help me triage open alerts — which should I handle first and why?" },
      { label: "Root cause", query: "What are likely root causes for the current open alerts on this asset?" },
    ],
  },
  priority: {
    label: "Priority Queue",
    prompts: [
      { label: "Explain ranking", query: "Explain why the top priority assets are ranked highest" },
      { label: "Action plan", query: "Suggest a maintenance action plan for the top 3 priority items" },
    ],
  },
  scheduler: {
    label: "Schedule",
    prompts: [
      { label: "Optimize schedule", query: "Review the maintenance schedule and suggest optimizations" },
      { label: "Spares check", query: "Do we have spares available for upcoming scheduled work?" },
    ],
  },
  equipment: {
    label: "Equipment",
    prompts: [
      { label: "Asset details", query: "Summarize health, RUL, and risk for this equipment" },
      { label: "Maintenance history", query: "What maintenance should be planned next for this asset?" },
    ],
  },
  diagnose: {
    label: "Diagnose",
    prompts: [
      { label: "Fault analysis", query: "Help diagnose likely fault causes based on current sensor degradation" },
      { label: "Inspection steps", query: "What inspection steps should I follow for this equipment?" },
    ],
  },
  analytics: {
    label: "Analytics",
    prompts: [
      { label: "ROI summary", query: "Summarize downtime reduction and ROI from predictive maintenance" },
      { label: "Degradation trends", query: "Explain degradation trends across the fleet" },
    ],
  },
  simulate: {
    label: "Simulator",
    prompts: [
      { label: "Delay 7 days", query: "What happens if maintenance is delayed by 7 days?" },
      { label: "Vibration +20%", query: "What if vibration increases by 20%?" },
      { label: "Spare shortage", query: "What if spare parts are unavailable?" },
    ],
  },
  logbook: {
    label: "Logbook",
    prompts: [
      { label: "Recent events", query: "Summarize recent maintenance events in the logbook" },
      { label: "Log entry help", query: "Help me draft a logbook entry for a maintenance intervention" },
    ],
  },
  reports: {
    label: "Reports",
    prompts: [
      { label: "Report summary", query: "What should I include in a maintenance health report for management?" },
      { label: "Key metrics", query: "List the key KPIs to highlight in this week's maintenance report" },
    ],
  },
  spares: {
    label: "Inventory",
    prompts: [
      { label: "Stock risks", query: "Which spare parts are at risk of stockout for critical equipment?" },
      { label: "Reorder advice", query: "What spares should we reorder based on current fleet health?" },
    ],
  },
  knowledge: {
    label: "Documents",
    prompts: [
      { label: "Find SOP", query: "Find the relevant SOP and inspection procedure for this equipment" },
      { label: "Manual lookup", query: "Search maintenance manuals for bearing vibration troubleshooting" },
    ],
  },
  history: {
    label: "History",
    prompts: [
      { label: "Past interventions", query: "Summarize past maintenance interventions for this asset" },
      { label: "Repeat failures", query: "Are there patterns of repeat failures I should watch for?" },
    ],
  },
  delays: {
    label: "Delays",
    prompts: [
      { label: "Delay analysis", query: "Analyze recent schedule delays and suggest preventive actions" },
      { label: "Explain deviation", query: "Help explain a maintenance schedule deviation to operations" },
    ],
  },
};

const DEFAULT_CONTEXT = {
  label: "Maintenance",
  prompts: [
    { label: "Fleet status", query: "What is the current status of the C-MAPSS fleet?" },
    { label: "Find SOP", query: "Find relevant SOP and inspection steps for this equipment" },
  ],
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  hideFab?: boolean;
};

export function AiChatWidget({ open, onOpenChange, hideFab = false }: Props) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [equipment, setEquipment] = useState<any[]>([]);
  const [equipmentId, setEquipmentId] = useState<number | undefined>();
  const [conversationId, setConversationId] = useState<number | undefined>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [lastAssistantIdx, setLastAssistantIdx] = useState<number | null>(null);
  const [provider, setProvider] = useState("");

  const sectionKey = pathname.split("/").filter(Boolean)[0] || "home";
  const context = SECTION_CONTEXT[sectionKey] ?? DEFAULT_CONTEXT;
  const urlEquipment = searchParams.get("equipment") ?? searchParams.get("id");

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !getToken() || !open) return;
    api.equipment().then((eq) => setEquipment(eq)).catch(() => {});
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      const id = Number(stored);
      if (!Number.isNaN(id)) {
        api
          .chatConversation(id)
          .then((detail) => {
            setConversationId(detail.id);
            if (detail.equipment_id) setEquipmentId(detail.equipment_id);
            setMessages(
              detail.messages.map((m: any) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                follow_ups: m.follow_ups,
                reasoning_panel: m.reasoning_panel,
                explainability: m.explainability,
                chat_style: m.chat_style,
              }))
            );
          })
          .catch(() => sessionStorage.removeItem(STORAGE_KEY));
      }
    }
  }, [mounted, open]);

  useEffect(() => {
    if (!equipment.length) return;
    if (urlEquipment) {
      const byId = equipment.find((e) => String(e.id) === urlEquipment);
      const byCode = equipment.find((e) => e.equipment_code === urlEquipment);
      setEquipmentId((byId ?? byCode)?.id);
    }
  }, [urlEquipment, equipment]);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [open, messages, loading]);

  useEffect(() => {
    setLastAssistantIdx(
      messages.length ? messages.map((m) => m.role).lastIndexOf("assistant") : null
    );
  }, [messages]);

  async function sendFeedback(positive: boolean) {
    if (!conversationId) {
      throw new Error("No saved conversation yet");
    }
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
    await api.feedback({
      conversation_id: conversationId,
      equipment_id: equipmentId,
      query: lastUser?.content,
      recommendation: lastAssistant?.content?.slice(0, 4000),
      source_type: "chat",
      rating: positive ? 5 : 2,
      correction: positive ? undefined : "Engineer marked chat response as not helpful",
      approved: positive,
    });
  }

  async function sendMessage(
    text: string,
    opts?: { branchFromMessageId?: number; replaceFromIndex?: number }
  ) {
    if (!text.trim() || loading) return;
    const userMsg = text.trim();
    setInput("");

    if (opts?.replaceFromIndex != null) {
      setMessages((m) => m.slice(0, opts.replaceFromIndex));
    } else {
      setMessages((m) => [...m, { role: "user", content: userMsg }]);
    }

    setLoading(true);
    try {
      let branchId = opts?.branchFromMessageId;
      if (opts?.replaceFromIndex != null && !branchId && conversationId) {
        try {
          const detail = await api.chatConversation(conversationId);
          branchId = detail.messages[opts.replaceFromIndex]?.id;
        } catch {
          /* fall through */
        }
      }

      const res = await api.chat(
        userMsg,
        conversationId,
        equipmentId,
        context.label,
        branchId
      );
      setConversationId(res.conversation_id);
      sessionStorage.setItem(STORAGE_KEY, String(res.conversation_id));
      const isConv = res.structured_output?.chat_style === "conversational";
      const assistantMsg = {
        id: res.assistant_message_id,
        role: "assistant" as const,
        content: res.message,
        follow_ups: res.follow_up_suggestions,
        llm_provider: res.llm_provider,
        chat_style: isConv ? ("conversational" as const) : ("maintenance" as const),
        reasoning_panel: isConv
          ? undefined
          : res.reasoning_panel || reasoningFromThoughts(res.agent_thoughts, res.citations, res.llm_provider),
        explainability: isConv ? undefined : res.structured_output?.explainability,
      };
      if (opts?.replaceFromIndex != null) {
        setMessages((m) => [
          ...m,
          { id: res.user_message_id, role: "user", content: userMsg },
          assistantMsg,
        ]);
      } else {
        setMessages((m) => {
          const next = [...m];
          if (res.user_message_id) {
            for (let j = next.length - 1; j >= 0; j--) {
              if (next[j].role === "user" && next[j].content === userMsg) {
                next[j] = { ...next[j], id: res.user_message_id };
                break;
              }
            }
          }
          next.push(assistantMsg);
          return next;
        });
      }
      setProvider(res.llm_provider || "");
    } catch (e: unknown) {
      const msg =
        e instanceof Error && e.name === "AbortError"
          ? "Request timed out — try a shorter question."
          : e instanceof Error
            ? e.message
            : "Unknown error";
      setMessages((m) => [...m, { role: "assistant", content: `Request failed: ${msg.slice(0, 200)}` }]);
    } finally {
      setLoading(false);
    }
  }

  function startNewChat() {
    setConversationId(undefined);
    setMessages([]);
    setProvider("");
    sessionStorage.removeItem(STORAGE_KEY);
  }

  if (!mounted || pathname === "/" || pathname === "/chat" || !getToken()) return null;

  if (!open && hideFab) return null;

  const selected = equipment.find((e) => e.id === equipmentId);
  const widgetPrompts = getContextualPrompts(equipmentId, selected?.equipment_code);
  const modeLabel = equipmentId ? selected?.equipment_code ?? "Asset" : "Plant";
  const chatHref = conversationId
    ? `/chat?equipment=${equipmentId ?? ""}&conversation=${conversationId}`
    : equipmentId
      ? `/chat?equipment=${equipmentId}`
      : "/chat";

  return (
    <>
      {!open && !hideFab && (
        <button
          type="button"
          onClick={() => onOpenChange(true)}
          className="ai-fab group"
          aria-label="Open ForgeMind agentic AI assistant"
        >
          <span className="ai-fab-icon">
            <Brain className="h-5 w-5" strokeWidth={1.75} />
            <span className="ai-fab-pulse" />
          </span>
          <span className="flex flex-col items-start leading-none">
            <span className="text-[15px] font-semibold tracking-tight">ForgeMind</span>
            <span className="mt-0.5 text-[9px] font-medium uppercase tracking-[0.18em] text-white/70">
              Agentic AI
            </span>
          </span>
          <ChevronRight className="ai-fab-chevron h-4 w-4 shrink-0 text-white/70" strokeWidth={2} />
        </button>
      )}

      {open && (
        <div className="fixed bottom-6 right-6 z-[45] flex h-[min(85vh,640px)] w-[min(100vw-2rem,420px)] flex-col overflow-hidden rounded-xl border border-tata-border/90 bg-gradient-to-br from-white to-tata-blue-pale/70 shadow-panel">
          <div className="relative bg-gradient-to-r from-tata-blue to-tata-blue-light px-4 py-3.5 text-white">
            <div className="absolute inset-x-0 top-0 h-0.5 bg-tata-menu/50" />
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/15 backdrop-blur-sm">
                  <Brain className="h-4 w-4" strokeWidth={1.75} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold">ForgeMind</p>
                  <p className="truncate text-[10px] text-white/75">
                    Agentic AI · {context.label}
                  </p>
                </div>
              </div>
            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={startNewChat}
                className="rounded p-1.5 text-white/80 transition hover:bg-white/10 hover:text-white"
                title="New chat"
              >
                <MessageSquarePlus className="h-4 w-4" />
              </button>
              <Link
                href={chatHref}
                className="rounded p-1.5 text-white/80 transition hover:bg-white/10 hover:text-white"
                title="Open full chat"
              >
                <ExternalLink className="h-4 w-4" />
              </Link>
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="rounded p-1.5 text-white/80 transition hover:bg-white/10 hover:text-white"
                aria-label="Close assistant"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            </div>
          </div>

          <div className="border-b border-tata-border/80 bg-gradient-to-r from-tata-blue-pale/40 to-white px-3 py-2.5">
            <EquipmentScopeSelector
              equipment={equipment}
              equipmentId={equipmentId}
              onChange={setEquipmentId}
              compact
            />
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-gradient-to-b from-tata-blue-pale/20 to-white">
            <div className="flex-1 overflow-y-auto overscroll-contain px-3 py-3">
              <div className="mx-auto w-full max-w-3xl py-2">
              {messages.length === 0 && (
                <div className="px-2 py-4 text-center">
                  <p className="text-sm font-semibold text-tata-ink">
                    {equipmentId ? `${selected?.equipment_code} chat` : "Plant chat"}
                  </p>
                  <p className="mt-1 text-xs text-tata-muted">Shortcuts sit right above the input</p>
                </div>
              )}

              {messages.length > 0 && (
                <ChatMessageList
                  messages={messages}
                  loading={loading}
                  compact
                  lastAssistantIdx={lastAssistantIdx}
                  onSend={sendMessage}
                  onFeedback={sendFeedback}
                  showFeedback
                />
              )}
              {loading && (
                <p className="flex items-center justify-center gap-2 py-2 text-[10px] text-tata-blue">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-tata-blue" />
                  Agents working…
                </p>
              )}
              <div ref={bottomRef} />
              </div>
            </div>

            <ChatComposer
              inputRef={inputRef}
              value={input}
              onChange={setInput}
              onSubmit={() => sendMessage(input)}
              loading={loading}
              placeholder={selected ? `Ask about ${selected.equipment_code}…` : "Plant chat…"}
              quickPrompts={widgetPrompts.slice(0, 5)}
              onPrompt={sendMessage}
              modeLabel={modeLabel}
              followUps={
                lastAssistantIdx != null && messages[lastAssistantIdx]?.follow_ups?.length
                  ? messages[lastAssistantIdx].follow_ups
                  : undefined
              }
              onFollowUp={sendMessage}
              provider={provider}
            />
          </div>
        </div>
      )}
    </>
  );
}
