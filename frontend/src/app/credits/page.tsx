"use client";

import { Shell } from "@/components/Shell";
import { getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";

type Status = "ok" | "partial";

const REQUIREMENTS: { section: string; items: { req: string; impl: string; status: Status }[] }[] = [
  {
    section: "4.1 — Operational & failure inputs",
    items: [
      { req: "Equipment delay logs", impl: "Delays page; fed into priority ranking and AI context", status: "ok" },
      { req: "Fault / error messages", impl: "Alerts, fault codes, failure history records", status: "ok" },
      { req: "Failure analysis reports", impl: "Failure history + indexed bearing-failure report in Documents", status: "ok" },
      { req: "Incident / breakdown records", impl: "Diagnose form, History, Logbook auto-entries", status: "ok" },
    ],
  },
  {
    section: "4.2 — Condition monitoring",
    items: [
      { req: "Sensor data summaries", impl: "Live Monitor + Analytics — C-MAPSS FD001 replay (WebSocket)", status: "ok" },
      { req: "Abnormality / anomaly alerts", impl: "Isolation Forest + real-time alert engine", status: "ok" },
      { req: "Process condition indicators", impl: "Temp, vibration, pressure, motor current, health, RUL", status: "ok" },
    ],
  },
  {
    section: "4.3 — Knowledge & documentation",
    items: [
      { req: "Equipment manuals", impl: "Documents library + semantic search (RAG)", status: "ok" },
      { req: "Maintenance SOPs", impl: "Indexed SOPs (e.g. rolling-mill motor procedure)", status: "ok" },
      { req: "Historical maintenance records", impl: "History page; key records indexed for search", status: "ok" },
      { req: "Spare parts + lead time", impl: "Spares page — stock, lead time, unit cost, procurement", status: "ok" },
    ],
  },
  {
    section: "4.4 — User interaction",
    items: [
      { req: "Natural language queries", impl: "Ask AI chat (Groq / Gemini with rule-based fallback)", status: "ok" },
      { req: "Scenario troubleshooting prompts", impl: "Diagnose form, Simulate page, chat quick prompts", status: "ok" },
      { req: "Multi-turn follow-ups", impl: "Conversation history + suggested follow-up chips", status: "ok" },
    ],
  },
  {
    section: "5 — Expected outputs",
    items: [
      { req: "Probable fault diagnosis + RCA", impl: "Diagnose page + Diagnostic Engine in agent pipeline", status: "ok" },
      { req: "RUL prediction + early warning", impl: "XGBoost on C-MAPSS; shown on Diagnose, Monitor, Priority", status: "ok" },
      { req: "Risk level + urgency", impl: "Composite risk engine; badges on Diagnose, Alerts, Priority", status: "ok" },
      { req: "Plant-level prioritization", impl: "Priority page — criticality × RUL × delays × spares", status: "ok" },
      { req: "Maintenance plans (immediate / long-term)", impl: "Planner Agent; Diagnose + Reports + Scheduler", status: "ok" },
      { req: "Spare procurement strategy", impl: "Spares agent + procurement workflow + AI spares answers", status: "ok" },
      { req: "Structured reports + PDF", impl: "Reports page — maintenance, abnormal, diagnosis, executive", status: "ok" },
      { req: "Digital logbook entries", impl: "Logbook — manual + auto from alerts, AI, diagnoses", status: "ok" },
    ],
  },
  {
    section: "6 — Functional requirements",
    items: [
      { req: "LLM contextual reasoning", impl: "Groq / Gemini in Advisor + optional supervisor routing", status: "ok" },
      { req: "Knowledge integration (manuals, SOPs, logs)", impl: "Qdrant RAG + operational context loader", status: "ok" },
      { req: "Natural language + multi-turn", impl: "Chat with persisted conversations", status: "ok" },
      { req: "Explainable recommendations", impl: "Agent trace, citations, sensor evidence on Diagnose", status: "ok" },
      { req: "Abnormality detection + failure prediction", impl: "Isolation Forest + XGBoost RUL architecture", status: "ok" },
      { req: "Feedback-driven improvement", impl: "👍/👎 on Diagnose, Chat & Reports → DB + scoring influences RCA & synthesis", status: "ok" },
      { req: "Real-time alerting", impl: "WebSocket monitor + alert lifecycle + supervisor notifications", status: "ok" },
    ],
  },
  {
    section: "7 — Optional enhancements",
    items: [
      { req: "Conversational interface", impl: "Ask AI chat widget + dedicated Chat page", status: "ok" },
      { req: "Visualization dashboard", impl: "Dashboard, Monitor charts, Analytics ROI view", status: "ok" },
      { req: "Simulated IoT / monitoring", impl: "C-MAPSS live replay over WebSocket (not plant SCADA)", status: "partial" },
      { req: "Dynamic knowledge base", impl: "Document upload → immediate RAG indexing", status: "ok" },
      { req: "Automatic digital logbook", impl: "Auto entries from AI, alerts, reports, priority dispatch", status: "ok" },
      { req: "User-role-based alerts", impl: "Critical/high alerts notify supervisor/admin roles in-app", status: "partial" },
    ],
  },
  {
    section: "8 — Expected outcomes",
    items: [
      { req: "Faster diagnosis", impl: "Supervisor-led agent pipeline — one query, consolidated answer", status: "ok" },
      { req: "Proactive maintenance shift", impl: "RUL-driven priority queue + scheduler + simulate scenarios", status: "ok" },
      { req: "Steel plant applicability", impl: "Tata-themed UX; C-MAPSS stands in for IoT until CMMS integration", status: "partial" },
    ],
  },
];

const DATA_SOURCES = [
  { layer: "Sensors & RUL", detail: "NASA C-MAPSS train_FD001.txt replayed live — one engine unit per plant asset" },
  { layer: "ML models", detail: "XGBoost (RUL) and Isolation Forest (anomalies), trained on C-MAPSS cycles" },
  { layer: "Knowledge docs", detail: "Manuals, SOPs, failure reports under data/documents/, indexed for RAG" },
  { layer: "Operational records", detail: "Delay logs, maintenance history, spares, alerts, logbook — app database" },
  { layer: "Production note", detail: "At Tata, plant IoT/SCADA and CMMS would replace C-MAPSS replay and demo seed data" },
];

function StatusIcon({ status }: { status: Status }) {
  if (status === "ok") return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />;
  return <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />;
}

export default function CreditsPage() {
  const router = useRouter();
  useEffect(() => {
    if (!getToken()) router.push("/");
  }, [router]);

  const okCount = REQUIREMENTS.flatMap((b) => b.items).filter((i) => i.status === "ok").length;
  const total = REQUIREMENTS.flatMap((b) => b.items).length;

  return (
    <Shell>
      <header className="mb-8">
        <p className="section-title text-tata-blue/80">Requirements</p>
        <h1 className="text-2xl font-bold text-tata-ink">Problem statement alignment</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-tata-muted">
          Checklist against the Tata Steel Round 2 brief. Green = implemented end-to-end. Amber = implemented with demo
          limitations (honest for judges).
        </p>
        <p className="mt-2 text-sm font-medium text-tata-ink">
          {okCount} / {total} requirements fully met · {total - okCount} with documented demo constraints
        </p>
      </header>

      <div className="mb-8 grid gap-4 lg:grid-cols-2">
        {REQUIREMENTS.map((block) => (
          <section key={block.section} className="card">
            <h2 className="mb-3 text-sm font-bold text-tata-blue">{block.section}</h2>
            <ul className="space-y-3">
              {block.items.map((item) => (
                <li key={item.req} className="flex gap-2.5 text-xs">
                  <StatusIcon status={item.status} />
                  <div>
                    <p className="font-medium text-tata-ink/85">
                      {item.req}
                      {item.status === "partial" && (
                        <span className="ml-1.5 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-normal text-amber-700">
                          partial
                        </span>
                      )}
                    </p>
                    <p className="mt-0.5 leading-relaxed text-tata-muted">{item.impl}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <section className="card mb-6">
        <h2 className="mb-3 font-bold text-tata-ink">Where the data comes from</h2>
        <div className="space-y-2">
          {DATA_SOURCES.map((row) => (
            <div key={row.layer} className="flex flex-wrap gap-x-3 gap-y-1 border-b border-tata-border/60 pb-2 last:border-0">
              <span className="min-w-[140px] text-xs font-semibold text-tata-blue sm:min-w-[180px]">{row.layer}</span>
              <span className="text-xs leading-relaxed text-tata-muted">{row.detail}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2 className="mb-2 font-bold text-tata-ink">Tech stack</h2>
        <div className="flex flex-wrap gap-2">
          {["FastAPI", "LangGraph", "Supervisor Agent", "Groq", "Gemini", "XGBoost", "Isolation Forest", "C-MAPSS FD001", "Qdrant", "Next.js"].map(
            (t) => (
              <span key={t} className="rounded-md border border-tata-border bg-white/[0.04] px-2 py-1 text-[10px] text-tata-muted">
                {t}
              </span>
            )
          )}
        </div>
      </section>
    </Shell>
  );
}
