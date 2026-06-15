"use client";

import { History, MessageSquarePlus, PanelLeftClose, PanelLeftOpen } from "lucide-react";

type ConversationSummary = {
  id: number;
  title: string | null;
  preview: string | null;
};

type Props = {
  conversations: ConversationSummary[];
  conversationId?: number;
  loading: boolean;
  open: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  onSelectConversation: (id: number) => void;
};

export function ChatHistoryPanel({
  conversations,
  conversationId,
  loading,
  open,
  onToggle,
  onNewChat,
  onSelectConversation,
}: Props) {
  if (!open) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="fixed left-4 top-[calc(var(--shell-header,0px)+5.5rem)] z-20 flex items-center gap-1.5 rounded-full border border-tata-border/80 bg-white px-3 py-1.5 text-xs font-medium text-tata-ink shadow-sm transition hover:border-tata-blue/30 lg:left-[calc(16rem+1rem)]"
        title="Show chat history"
      >
        <PanelLeftOpen className="h-3.5 w-3.5" />
        History
      </button>
    );
  }

  return (
    <aside className="flex h-full w-[240px] shrink-0 flex-col border-r border-tata-border/80 bg-slate-50/80">
      <div className="flex items-center justify-between gap-2 border-b border-tata-border/80 px-3 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-tata-ink">
          <History className="h-4 w-4 text-tata-blue" />
          History
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onNewChat}
            className="rounded-lg p-1.5 text-tata-muted transition hover:bg-white hover:text-tata-blue"
            title="New chat"
          >
            <MessageSquarePlus className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onToggle}
            className="rounded-lg p-1.5 text-tata-muted transition hover:bg-white hover:text-tata-ink"
            title="Hide history"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {conversations.length === 0 ? (
          <p className="px-2 py-4 text-xs text-tata-muted">No saved chats yet.</p>
        ) : (
          conversations.map((c) => (
            <button
              key={c.id}
              type="button"
              disabled={loading}
              onClick={() => onSelectConversation(c.id)}
              className={`w-full rounded-lg px-3 py-2 text-left text-xs transition disabled:opacity-50 ${
                conversationId === c.id
                  ? "bg-white font-semibold text-tata-ink shadow-sm ring-1 ring-tata-blue/20"
                  : "text-tata-ink/80 hover:bg-white/80"
              }`}
            >
              <p className="truncate">{c.title || c.preview || `Chat #${c.id}`}</p>
              {c.preview && c.title && (
                <p className="mt-0.5 truncate text-[10px] font-normal text-tata-muted">{c.preview}</p>
              )}
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
