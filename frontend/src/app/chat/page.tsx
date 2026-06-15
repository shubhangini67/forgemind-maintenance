"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { CmapssSensorBar } from "@/components/CmapssSensorBar";
import { ChatMessageList, ChatMessageItem } from "@/components/ChatMessageList";
import { ChatComposer } from "@/components/ChatComposer";
import { ChatHistoryPanel } from "@/components/ChatHistoryPanel";
import { ChatAgentStatus } from "@/components/ChatAgentStatus";
import { EquipmentScopeSelector } from "@/components/EquipmentScopeSelector";
import { getContextualPrompts } from "@/lib/chatPrompts";
import { api, getToken } from "@/lib/api";
import { Brain, Globe2, MessageCircle } from "lucide-react";

type ConversationSummary = {
  id: number;
  title: string | null;
  preview: string | null;
  updated_at: string;
  message_count: number;
};

export default function ChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [equipment, setEquipment] = useState<any[]>([]);
  const [equipmentId, setEquipmentId] = useState<number | undefined>();
  const [conversationId, setConversationId] = useState<number | undefined>();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sensorSnapshot, setSensorSnapshot] = useState<any>(null);
  const [provider, setProvider] = useState("");
  const [lastAssistantIdx, setLastAssistantIdx] = useState<number | null>(null);
  const [historyOpen, setHistoryOpen] = useState(true);

  const loadConversations = useCallback(() => {
    api.chatConversations().then(setConversations).catch(() => {});
  }, []);

  const loadConversation = useCallback(async (id: number) => {
    const detail = await api.chatConversation(id);
    setConversationId(detail.id);
    if (detail.equipment_id) setEquipmentId(detail.equipment_id);
    else setEquipmentId(undefined);
    setMessages(
      detail.messages.map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        follow_ups: m.follow_ups,
        reasoning_panel: m.reasoning_panel,
        explainability: m.explainability,
        chat_style: m.chat_style,
        llm_provider: m.llm_provider,
      }))
    );
  }, []);

  useEffect(() => {
    if (!getToken()) router.push("/");
    else {
      api.equipment().then((eq) => {
        setEquipment(eq);
        const eqParam = searchParams.get("equipment");
        if (eqParam) {
          const byId = eq.find((e: any) => String(e.id) === eqParam);
          const byCode = eq.find((e: any) => e.equipment_code === eqParam);
          setEquipmentId((byId ?? byCode)?.id);
        }
        const q = searchParams.get("q");
        if (q) setInput(q);
      });
      loadConversations();
      const convParam = searchParams.get("conversation");
      if (convParam) loadConversation(Number(convParam)).catch(() => {});
    }
  }, [router, searchParams, loadConversations, loadConversation]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, [messages, loading]);

  useEffect(() => {
    setLastAssistantIdx(
      messages.length ? messages.map((m) => m.role).lastIndexOf("assistant") : null
    );
  }, [messages]);

  function startNewChat() {
    setConversationId(undefined);
    setMessages([]);
    setSensorSnapshot(null);
    setProvider("");
  }

  async function sendFeedback(positive: boolean) {
    if (!conversationId) throw new Error("No saved conversation yet");
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

      const res = await api.chat(userMsg, conversationId, equipmentId, undefined, branchId);
      setConversationId(res.conversation_id);
      const isConv = res.structured_output?.chat_style === "conversational";
      const replyText = (res.message || "").trim();
      const assistantMsg: ChatMessageItem = {
        id: res.assistant_message_id,
        role: "assistant",
        content: replyText || "The agent pipeline returned an empty response. Please try again.",
        agent_type: res.agent_type,
        follow_ups: res.follow_up_suggestions,
        llm_provider: res.llm_provider,
        chat_style: isConv ? "conversational" : "maintenance",
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
      setSensorSnapshot(isConv || !equipmentId ? null : res.structured_output?.sensor_snapshot || null);
      setProvider(res.llm_provider || "");
      loadConversations();
    } catch (e: unknown) {
      const msg =
        e instanceof Error && e.name === "AbortError"
          ? "Request timed out — try a shorter question."
          : e instanceof Error
            ? e.message
            : "Unknown error";
      setMessages((m) => [...m, { role: "assistant", content: `**Request failed:** ${msg.slice(0, 300)}` }]);
    } finally {
      setLoading(false);
    }
  }

  const selected = equipment.find((e) => e.id === equipmentId);
  const isPlantMode = !equipmentId;
  const contextualPrompts = getContextualPrompts(equipmentId, selected?.equipment_code);
  const modeLabel = isPlantMode ? "Plant" : selected?.equipment_code ?? "Asset";

  const inputPlaceholder = isPlantMode
    ? "Ask about the plant, navigation, fleet…"
    : `Ask about ${selected?.equipment_code} — RUL, root cause, actions…`;

  return (
    <Shell>
      <div className="panel-flush flex h-[calc(100vh-6rem)] min-h-[480px] overflow-hidden rounded-2xl shadow-lg ring-1 ring-tata-border/40">
        {historyOpen && (
          <ChatHistoryPanel
            conversations={conversations}
            conversationId={conversationId}
            loading={loading}
            open={historyOpen}
            onToggle={() => setHistoryOpen(false)}
            onNewChat={startNewChat}
            onSelectConversation={loadConversation}
          />
        )}

        <div className="relative flex min-w-0 flex-1 flex-col">
          {!historyOpen && (
            <ChatHistoryPanel
              conversations={conversations}
              conversationId={conversationId}
              loading={loading}
              open={false}
              onToggle={() => setHistoryOpen(true)}
              onNewChat={startNewChat}
              onSelectConversation={loadConversation}
            />
          )}

          {/* Compact header: mode + asset selector in a single row */}
          <div className={`shrink-0 border-b px-4 py-2.5 ${isPlantMode ? "border-sky-100 bg-sky-50/60" : "border-amber-100 bg-amber-50/60"}`}>
            <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2.5">
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white shadow-sm ${isPlantMode ? "bg-gradient-to-br from-sky-500 to-tata-blue" : "bg-gradient-to-br from-amber-500 to-orange-600"}`}>
                  {isPlantMode ? <Globe2 className="h-5 w-5" /> : <Brain className="h-5 w-5" />}
                </div>
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-bold text-tata-ink">
                    {isPlantMode ? "Plant mode" : `${selected?.equipment_code} · ${selected?.name}`}
                  </h2>
                  <p className="truncate text-[11px] text-tata-muted">
                    {isPlantMode ? "Navigation & fleet questions" : "Full agent pipeline · sensors → causes → actions"}
                  </p>
                </div>
              </div>
              <div className="w-full sm:w-auto sm:min-w-[220px]">
                <EquipmentScopeSelector
                  equipment={equipment}
                  equipmentId={equipmentId}
                  onChange={setEquipmentId}
                  compact
                />
              </div>
            </div>
            {!isPlantMode && sensorSnapshot && (
              <div className="mx-auto mt-2 max-w-3xl border-t border-amber-200/40 pt-2">
                <CmapssSensorBar snapshot={sensorSnapshot} compact />
              </div>
            )}
          </div>

          {/* Message thread — gets all remaining vertical space */}
          <div
            ref={scrollRef}
            className={`min-h-0 flex-1 overflow-y-auto overscroll-contain scroll-smooth bg-white px-3 sm:px-5 ${
              messages.length === 0 ? "flex items-center justify-center" : ""
            }`}
          >
            <div className="mx-auto w-full max-w-3xl py-4">
              <ChatAgentStatus loading={loading} />
              {messages.length === 0 && !loading && (
                <div className="mx-auto max-w-md px-2">
                  <div className="chat-welcome-card text-center">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-tata-blue to-sky-400 text-white shadow-lg">
                      <MessageCircle className="h-7 w-7" />
                    </div>
                    <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.2em] text-tata-blue">
                      ForgeMind · Agentic AI
                    </p>
                    <p className="mt-1.5 text-lg font-bold text-tata-ink">
                      {isPlantMode ? "Plant chat ready" : `${selected?.equipment_code} ready`}
                    </p>
                    <p className="mt-2 text-sm leading-relaxed text-tata-muted">
                      {isPlantMode
                        ? "Say hi, tap a shortcut below, or ask about the fleet."
                        : "Tap a shortcut below — RUL, root cause, or what to do."}
                    </p>
                  </div>
                </div>
              )}

              {messages.length > 0 && (
                <ChatMessageList
                  messages={messages}
                  loading={loading}
                  lastAssistantIdx={lastAssistantIdx}
                  onSend={sendMessage}
                  onFeedback={sendFeedback}
                  showFeedback
                />
              )}
              <div ref={bottomRef} className="h-1" />
            </div>
          </div>

          <ChatComposer
            value={input}
            onChange={setInput}
            onSubmit={() => sendMessage(input)}
            loading={loading}
            placeholder={inputPlaceholder}
            quickPrompts={contextualPrompts}
            onPrompt={sendMessage}
            provider={provider}
            modeLabel={modeLabel}
            followUps={
              lastAssistantIdx != null && messages[lastAssistantIdx]?.follow_ups?.length
                ? messages[lastAssistantIdx].follow_ups
                : undefined
            }
            onFollowUp={sendMessage}
          />
        </div>
      </div>
    </Shell>
  );
}
