"use client";

import { CheckCircle2, Circle, Loader2 } from "lucide-react";

const DEFAULT_AGENT_ORDER = [
  "document_agent",
  "predictive_agent",
  "rca_agent",
  "spare_parts_agent",
  "planner_agent",
  "alert_agent",
  "report_agent",
  "synthesizer",
];

const LABELS: Record<string, string> = {
  supervisor: "Supervisor",
  document_agent: "Knowledge RAG",
  predictive_agent: "Predictive Engine",
  rca_agent: "Diagnostic Engine",
  spare_parts_agent: "Spares & Risk",
  planner_agent: "Planner Agent",
  alert_agent: "Alert Agent",
  report_agent: "Report Agent",
  synthesizer: "Advisor Agent",
};

function resolveAgentOrder(thoughts: any[]): string[] {
  const supervisor = thoughts.find((t) => t.agent === "supervisor");
  const plan = supervisor?.data?.agent_plan as string[] | undefined;
  if (plan?.length) {
    return ["supervisor", ...plan, "synthesizer"];
  }
  return ["supervisor", ...DEFAULT_AGENT_ORDER];
}

export function AgentRoutingViz({
  thoughts,
  loading,
}: {
  thoughts: any[];
  loading?: boolean;
}) {
  const agentOrder = resolveAgentOrder(thoughts);
  const done = new Set(thoughts.map((t) => t.agent));
  const activeAgent = loading
    ? agentOrder.find((a) => !done.has(a)) || "synthesizer"
    : null;

  return (
    <div className="flex flex-wrap items-center gap-1 text-[10px]">
      {agentOrder.map((agent, i) => {
        const complete = done.has(agent);
        const active = agent === activeAgent;
        return (
          <div key={agent} className="flex items-center gap-1">
            {i > 0 && <span className="text-steel-200">→</span>}
            <span
              className={`flex items-center gap-1 rounded-lg px-2 py-1 ${
                active
                  ? "agent-active bg-tata-blue-pale text-tata-blue"
                  : complete
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-steel-50 text-steel-400"
              }`}
            >
              {active ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : complete ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <Circle className="h-3 w-3" />
              )}
              {LABELS[agent]}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function AgentThoughtPanel({
  thoughts,
  loading,
  provider,
  vertical = false,
}: {
  thoughts: any[];
  loading?: boolean;
  provider?: string;
  vertical?: boolean;
}) {
  const agentOrder = resolveAgentOrder(thoughts);
  const done = new Set(thoughts.map((t) => t.agent));
  const activeAgent = loading ? agentOrder.find((a) => !done.has(a)) || "synthesizer" : null;

  return (
    <div className="card-dark flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-tata-ink">Agent Pipeline</h3>
        {provider && (
          <span className="rounded bg-tata-blue-pale px-2 py-0.5 text-[10px] font-medium text-tata-blue">
            {provider.toUpperCase()}
          </span>
        )}
      </div>

      {vertical ? (
        <div className="mb-3 space-y-1">
          {agentOrder.map((agent) => {
            const complete = done.has(agent);
            const active = agent === activeAgent;
            return (
              <div
                key={agent}
                className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-[10px] ${
                  active ? "bg-tata-blue-pale text-tata-blue" : complete ? "text-emerald-700" : "text-steel-400"
                }`}
              >
                {active ? <Loader2 className="h-3 w-3 animate-spin" /> : complete ? <CheckCircle2 className="h-3 w-3" /> : <Circle className="h-3 w-3" />}
                {LABELS[agent]}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mb-3">
          <AgentRoutingViz thoughts={thoughts} loading={loading} />
        </div>
      )}

      <div className="flex-1 overflow-y-auto rounded-xl border border-tata-border bg-tata-blue-pale/40 p-3 font-mono text-xs max-h-[480px]">
        {thoughts.length === 0 && !loading && (
          <p className="text-tata-muted">&gt; idle — submit a query to trace agent decisions</p>
        )}
        {loading && thoughts.length === 0 && (
          <p className="terminal-log animate-pulse">&gt; supervisor routing agents…</p>
        )}
        {thoughts.map((t, i) => (
          <div key={i} className="mb-3 border-b border-tata-border/60 pb-2 last:border-0">
            <p className="text-tata-blue">[{new Date().toLocaleTimeString()}] {t.label || t.agent}</p>
            <p className="mt-1 text-[#14b8a6]/90">{t.detail}</p>
          </div>
        ))}
        {loading && thoughts.length > 0 && (
          <p className="terminal-log animate-pulse">&gt; pipeline running…</p>
        )}
      </div>
    </div>
  );
}
