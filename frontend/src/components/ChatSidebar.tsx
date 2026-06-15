"use client";

import { Brain, MessageSquarePlus, Sparkles } from "lucide-react";
import { EquipmentScopeSelector } from "@/components/EquipmentScopeSelector";

type ConversationSummary = {
  id: number;
  title: string | null;
  preview: string | null;
};

type Props = {
  conversations: ConversationSummary[];
  conversationId?: number;
  equipment: { id: number; equipment_code: string; name: string }[];
  equipmentId?: number;
  quickPrompts: { label: string; query: string }[];
  loading: boolean;
  onNewChat: () => void;
  onSelectConversation: (id: number) => void;
  onEquipmentChange: (id: number | undefined) => void;
  onPrompt: (query: string) => void;
};

export function ChatSidebar({
  conversations,
  conversationId,
  equipment,
  equipmentId,
  quickPrompts,
  loading,
  onNewChat,
  onSelectConversation,
  onEquipmentChange,
  onPrompt,
}: Props) {
  return (
    <aside className="flex flex-col gap-4 lg:sticky lg:top-24">
      <div className="panel-flush overflow-hidden">
        <div className="flex items-center justify-between gap-2 border-b border-tata-border/80 bg-gradient-to-r from-tata-blue-pale/60 to-white px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-tata-blue to-tata-blue-light text-white">
              <Brain className="h-4 w-4" />
            </div>
            <p className="text-sm font-semibold text-tata-ink">Chat history</p>
          </div>
          <button
            type="button"
            onClick={onNewChat}
            className="btn-secondary px-2.5 py-1.5 text-[10px]"
            title="New chat"
          >
            <MessageSquarePlus className="h-3.5 w-3.5" />
            New
          </button>
        </div>
        <div className="max-h-48 space-y-1.5 overflow-y-auto p-3">
          {conversations.length === 0 ? (
            <p className="px-1 py-2 text-xs text-tata-muted">No saved chats yet — start below.</p>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => onSelectConversation(c.id)}
                className={`w-full rounded-lg px-3 py-2 text-left text-xs transition ${
                  conversationId === c.id
                    ? "bg-gradient-to-r from-tata-blue/10 to-tata-blue-pale/80 ring-1 ring-tata-blue/25"
                    : "hover:bg-tata-blue-pale/40"
                }`}
              >
                <p className="truncate font-semibold text-tata-ink">
                  {c.title || c.preview || `Chat #${c.id}`}
                </p>
                {c.preview && (
                  <p className="mt-0.5 truncate text-[10px] text-tata-muted">{c.preview}</p>
                )}
              </button>
            ))
          )}
        </div>
      </div>

      <div className="panel-flush p-4 lg:hidden">
        <EquipmentScopeSelector
          equipment={equipment}
          equipmentId={equipmentId}
          onChange={onEquipmentChange}
        />
      </div>

      <div className="panel-flush overflow-hidden">
        <div className="border-b border-tata-border/80 bg-gradient-to-r from-tata-blue-pale/40 to-white px-4 py-3">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-tata-ink">
            <Sparkles className="h-4 w-4 text-tata-blue" />
            Quick prompts
          </p>
        </div>
        <div className="grid gap-2 p-3">
          {quickPrompts.map(({ label, query }) => (
            <button
              key={label}
              type="button"
              onClick={() => onPrompt(query)}
              disabled={loading}
              className="chat-prompt-chip w-full text-left disabled:opacity-50"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
