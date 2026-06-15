"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Circle,
  Cpu,
  FileText,
  Factory,
  Loader2,
  Network,
  Package,
  Sparkles,
  Stethoscope,
  TrendingUp,
} from "lucide-react";

export type ReasoningDocument = {
  source: string;
  document_type: string;
  excerpt: string;
  score: number;
};

export type ReasoningStep = {
  step: number;
  agent: string;
  label: string;
  phase: string;
  status: string;
  timestamp: string;
  confidence: number | null;
  summary: string;
  output: Record<string, unknown>;
  citations: { source: string; document_type: string; excerpt: string; score: number }[];
  documents: ReasoningDocument[];
};

export type AIReasoningPanelData = {
  query_intent?: string | null;
  routing_mode?: string | null;
  agent_plan?: string[];
  agent_trace?: string[];
  steps: ReasoningStep[];
  total_steps?: number;
  citations?: { source: string; document_type: string; excerpt: string; score: number }[];
  llm_provider?: string | null;
  structured_summary?: Record<string, unknown>;
};

const AGENT_ICONS: Record<string, typeof Brain> = {
  supervisor: Network,
  document_agent: BookOpen,
  predictive_agent: TrendingUp,
  rca_agent: Stethoscope,
  inventory_agent: Package,
  risk_agent: AlertTriangle,
  production_impact_agent: Factory,
  spare_parts_agent: AlertTriangle,
  planner_agent: Cpu,
  alert_agent: AlertTriangle,
  report_agent: FileText,
  synthesizer: Sparkles,
};

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return "—";
  }
}

function confidenceLabel(c: number | null | undefined) {
  if (c == null) return null;
  const pct = Math.round(c * 100);
  return `${pct}%`;
}

function ConfidenceBar({ value }: { value: number | null | undefined }) {
  if (value == null) return null;
  const pct = Math.min(100, Math.max(0, Math.round(value * 100)));
  return (
    <div className="mt-2">
      <div className="mb-1 flex justify-between text-[10px] text-tata-muted">
        <span>Confidence</span>
        <span className="font-mono font-semibold text-tata-blue">{pct}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-tata-border/50">
        <div
          className="h-full rounded-full bg-gradient-to-r from-tata-blue to-emerald-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function StepOutput({ step }: { step: ReasoningStep }) {
  const [open, setOpen] = useState(false);
  const hasOutput = step.output && Object.keys(step.output).length > 0;
  if (!hasOutput && step.documents.length === 0 && step.citations.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-[10px] font-medium text-tata-blue hover:underline"
      >
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        Agent output &amp; evidence
      </button>
      {open && (
        <div className="mt-2 space-y-2 rounded-lg border border-tata-border/60 bg-white/80 p-2.5 text-[11px]">
          {step.documents.length > 0 && (
            <div>
              <p className="mb-1 font-semibold text-tata-ink">Retrieved documents</p>
              {step.documents.map((d, i) => (
                <div key={i} className="mb-1 rounded bg-tata-blue-pale/50 px-2 py-1">
                  <span className="font-medium text-tata-blue">{d.source}</span>
                  <span className="text-tata-muted"> · score {d.score.toFixed(2)}</span>
                  {d.excerpt ? <p className="mt-0.5 text-tata-muted">{d.excerpt.slice(0, 120)}…</p> : null}
                </div>
              ))}
            </div>
          )}
          {step.citations.length > 0 && (
            <div>
              <p className="mb-1 font-semibold text-tata-ink">Citations</p>
              {step.citations.map((c, i) => (
                <p key={i} className="mb-1 text-tata-muted">
                  <span className="text-tata-blue">{c.source}</span> ({c.score.toFixed(2)}) — {c.excerpt.slice(0, 100)}…
                </p>
              ))}
            </div>
          )}
          {hasOutput && (
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] text-tata-muted">
              {JSON.stringify(step.output, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function AIReasoningPanel({
  panel,
  loading,
  provider,
  defaultExpanded = true,
}: {
  panel: AIReasoningPanelData | null;
  loading?: boolean;
  provider?: string;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const steps = panel?.steps ?? [];
  const doneAgents = new Set(steps.map((s) => s.agent));
  const planned = panel?.agent_plan ?? [];

  const pipelineOrder = useMemo(() => {
    if (planned.length) return ["supervisor", ...planned, "synthesizer"];
    return steps.map((s) => s.agent);
  }, [planned, steps]);

  const activeAgent = loading
    ? pipelineOrder.find((a) => !doneAgents.has(a) && a !== "inventory_agent") || "synthesizer"
    : null;

  const llm = provider || panel?.llm_provider;

  return (
    <div className="reasoning-panel overflow-hidden rounded-2xl border border-tata-blue/20 bg-gradient-to-br from-slate-950 via-slate-900 to-tata-blue/30 text-white shadow-lg">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 border-b border-white/10 px-4 py-3 text-left sm:px-5"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-tata-blue/30 ring-1 ring-white/20">
            <Brain className="h-5 w-5 text-sky-300" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-sky-300/90">Agentic AI</p>
            <h3 className="text-sm font-semibold text-white">AI Reasoning Panel</h3>
            <p className="text-[11px] text-white/55">
              {loading
                ? "LangGraph agents collaborating…"
                : `${steps.length} step${steps.length === 1 ? "" : "s"} · ${panel?.routing_mode?.replace(/_/g, " ") || "dynamic routing"}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {llm && (
            <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-medium uppercase text-white/80">
              {llm}
            </span>
          )}
          {expanded ? <ChevronUp className="h-4 w-4 text-white/60" /> : <ChevronDown className="h-4 w-4 text-white/60" />}
        </div>
      </button>

      {expanded && (
        <div className="px-4 py-4 sm:px-5">
          {/* Pipeline ribbon */}
          <div className="mb-4 flex flex-wrap items-center gap-1">
            {pipelineOrder.map((agent, i) => {
              const step = steps.find((s) => s.agent === agent);
              const complete = !!step || doneAgents.has(agent);
              const active = agent === activeAgent;
              const label = step?.label || agent.replace(/_/g, " ");
              return (
                <div key={`${agent}-${i}`} className="flex items-center gap-1">
                  {i > 0 && <span className="text-white/25">→</span>}
                  <span
                    className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] ${
                      active
                        ? "bg-sky-500/30 text-sky-100 ring-1 ring-sky-400/50"
                        : complete
                          ? "bg-emerald-500/20 text-emerald-200"
                          : "bg-white/5 text-white/40"
                    }`}
                  >
                    {active ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : complete ? (
                      <CheckCircle2 className="h-3 w-3" />
                    ) : (
                      <Circle className="h-3 w-3" />
                    )}
                    {label}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Step timeline */}
          <div className="max-h-[520px] space-y-3 overflow-y-auto pr-1">
            {loading && steps.length === 0 && (
              <p className="animate-pulse font-mono text-xs text-sky-300/80">&gt; Supervisor routing agents…</p>
            )}
            {steps.map((step) => {
              const Icon = AGENT_ICONS[step.agent] || Brain;
              return (
                <div
                  key={`${step.step}-${step.agent}`}
                  className="relative rounded-xl border border-white/10 bg-black/25 p-3 backdrop-blur-sm"
                >
                  <div className="flex gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-sky-300">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-[10px] font-bold uppercase tracking-wider text-sky-300/80">
                            Step {step.step} · {step.phase}
                          </p>
                          <p className="text-sm font-semibold text-white">[{step.label}]</p>
                        </div>
                        <span className="shrink-0 font-mono text-[10px] text-white/45">{formatTime(step.timestamp)}</span>
                      </div>
                      <p className="mt-1.5 text-xs leading-relaxed text-white/75">{step.summary}</p>
                      <ConfidenceBar value={step.confidence} />
                      <StepOutput step={step} />
                    </div>
                  </div>
                </div>
              );
            })}
            {loading && steps.length > 0 && (
              <p className="animate-pulse font-mono text-xs text-emerald-300/80">&gt; pipeline running…</p>
            )}
          </div>

          {/* Global citations */}
          {(panel?.citations?.length ?? 0) > 0 && (
            <div className="mt-4 border-t border-white/10 pt-3">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-white/50">Knowledge base citations</p>
              <div className="space-y-1">
                {panel!.citations!.slice(0, 4).map((c, i) => (
                  <p key={i} className="text-[11px] text-white/65">
                    <span className="font-medium text-sky-300">{c.source}</span>
                    <span className="text-white/40"> ({c.score.toFixed(2)})</span> — {c.excerpt.slice(0, 90)}…
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Build a minimal panel from legacy agent_thoughts when reasoning_panel is absent. */
export function reasoningFromThoughts(
  thoughts: any[],
  citations: any[] = [],
  provider?: string
): AIReasoningPanelData | null {
  if (!thoughts?.length) return null;
  return {
    steps: thoughts.map((t, i) => ({
      step: i + 1,
      agent: t.agent,
      label: t.label || t.agent,
      phase: t.phase || "Processing",
      status: t.status || "complete",
      timestamp: t.timestamp || new Date().toISOString(),
      confidence: t.confidence ?? null,
      summary: t.detail || "",
      output: t.data || {},
      citations: i === 0 || t.agent === "synthesizer" ? citations : [],
      documents: (t.data?.matches || []).map((m: any) => ({
        source: m.source,
        document_type: m.type || "document",
        excerpt: "",
        score: m.score || 0,
      })),
    })),
    citations,
    llm_provider: provider,
    total_steps: thoughts.length,
  };
}
