import type { QuickPrompt } from "@/components/ChatComposer";

/** Plant-wide mode — navigation & fleet, no asset required */
export function getPlantPrompts(): QuickPrompt[] {
  return [
    { label: "👋 Say hi", query: "Hi" },
    { label: "📡 Live Monitor", href: "/monitor", variant: "link" },
    { label: "📊 Dashboard", href: "/dashboard", variant: "link" },
    { label: "🔍 Diagnose", href: "/diagnose", variant: "link" },
    { label: "📋 Priority queue", href: "/priority", variant: "link" },
    { label: "Fleet RUL ranking", query: "Rank all assets by remaining useful life" },
  ];
}

/** Asset-scoped mode — diagnostics & actions for one unit */
export function getAssetPrompts(equipmentCode: string, equipmentId?: number): QuickPrompt[] {
  const eq = equipmentId ? `?equipment=${equipmentId}` : `?equipment=${equipmentCode}`;
  return [
    { label: "Say hi", query: "Hi" },
    { label: "Live sensors", href: `/monitor${eq}`, variant: "link" },
    { label: "What's the RUL?", query: `What's the RUL on ${equipmentCode}?` },
    { label: "Root cause", query: `Analyze degradation on ${equipmentCode} — root cause and likely failure mode` },
    { label: "What should we do?", query: `What should we do for ${equipmentCode}?` },
    { label: "SOP section", query: `Show me the relevant SOP section for ${equipmentCode}` },
  ];
}

export function getContextualPrompts(
  equipmentId: number | undefined,
  equipmentCode: string | undefined
): QuickPrompt[] {
  if (equipmentId && equipmentCode) {
    return getAssetPrompts(equipmentCode, equipmentId);
  }
  return getPlantPrompts();
}
