"use client";

import Link from "next/link";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import {
  Activity,
  ArrowDown,
  BookOpen,
  Bot,
  Brain,
  ClipboardList,
  Database,
  FileText,
  Layers,
  MessageSquare,
  Package,
  Radar,
  Shield,
  Sparkles,
  Target,
  Terminal,
  Wrench,
} from "lucide-react";

const DATA_SOURCES = [
  {
    name: "NASA C-MAPSS",
    icon: Activity,
    description: "FD001 turbofan degradation cycles — temperature, vibration, pressure, and health indicators replayed as live plant sensors.",
    feeds: "Live Monitor, ML training, RUL, anomaly scores, alerts",
    badge: "real" as const,
  },
  {
    name: "Maintenance Logs",
    icon: ClipboardList,
    description: "Work history, completed interventions, and auto-generated logbook entries from alerts, diagnoses, and schedules.",
    feeds: "Logbook, History, RCA context, operational memory",
    badge: "mixed" as const,
  },
  {
    name: "SOPs",
    icon: BookOpen,
    description: "Standard operating procedures (e.g. rolling-mill motor inspection) chunked and embedded for semantic retrieval.",
    feeds: "Qdrant RAG, Diagnose citations, Chat answers",
    badge: "real" as const,
  },
  {
    name: "Manuals",
    icon: FileText,
    description: "Equipment manuals uploaded to the Documents library — indexed on ingest for hybrid vector + keyword search.",
    feeds: "Knowledge page, RAG agent, report citations",
    badge: "real" as const,
  },
  {
    name: "Failure Reports",
    icon: Shield,
    description: "Historical failure analyses and incident records used to ground root-cause reasoning.",
    feeds: "Diagnostic Engine, Documents RAG, Priority context",
    badge: "mixed" as const,
  },
  {
    name: "Inventory",
    icon: Package,
    description: "Spare parts stock levels, reorder thresholds, lead times, and unit costs for procurement-aware planning.",
    feeds: "Spares page, Spares & Risk agent, Failure Simulator",
    badge: "demo" as const,
  },
  {
    name: "Feedback",
    icon: MessageSquare,
    description: "Engineer 👍/👎 ratings on diagnoses, chat, and reports — stored in DB and used to adjust future recommendations.",
    feeds: "Feedback scoring, RCA deprioritization, Analytics widget",
    badge: "live" as const,
  },
];

const PIPELINE = [
  { step: "Sensor Data", detail: "C-MAPSS FD001 replay over WebSocket — 5 assets mapped to BF-001 … CN-005", icon: Radar },
  { step: "Isolation Forest", detail: "Unsupervised anomaly detection on multi-sensor vectors; triggers alert engine", icon: Target },
  { step: "XGBoost", detail: "Remaining Useful Life (RUL) regression and failure probability from degradation features", icon: Brain },
  { step: "LangGraph", detail: "Supervisor-led multi-agent orchestration with intent-based dynamic routing", icon: Layers },
  { step: "Qdrant RAG", detail: "Hybrid retrieval over manuals, SOPs, and failure reports with BGE embeddings + reranking", icon: Database },
  { step: "Planner", detail: "Time-bound maintenance actions from RUL, risk, spares availability, and SOP constraints", icon: Wrench },
  { step: "Reports", detail: "Structured PDF exports — diagnosis, priority, alerts, scenarios, executive summary", icon: FileText },
];

const AGENTS = [
  {
    name: "Supervisor Agent",
    tag: "Orchestrator",
    role: "Classifies user intent and selects which specialist agents to run — avoids unnecessary LLM calls.",
    outputs: "Dynamic agent plan, execution trace",
  },
  {
    name: "Knowledge RAG",
    tag: "Retrieval",
    role: "Queries Qdrant for relevant manual, SOP, and failure-report chunks with citation metadata.",
    outputs: "Retrieved passages, source citations",
  },
  {
    name: "Predictive Engine",
    tag: "ML",
    role: "Runs Isolation Forest anomaly check and XGBoost RUL on the latest sensor snapshot.",
    outputs: "RUL hours, failure probability, anomaly flag",
  },
  {
    name: "Diagnostic Engine",
    tag: "RCA",
    role: "Correlates sensor patterns, failure history, delay logs, and RAG context into ranked probable causes.",
    outputs: "Root cause list, confidence scores",
  },
  {
    name: "Spares & Risk",
    tag: "Operations",
    role: "Checks inventory against required parts, computes composite risk (criticality × RUL × spares gap).",
    outputs: "Risk level, procurement flags, spare status",
  },
  {
    name: "Planner Agent",
    tag: "Planning",
    role: "Generates immediate, short-term, and long-term maintenance actions aligned with plant constraints.",
    outputs: "Maintenance plan, monitoring schedule",
  },
  {
    name: "Alert Agent",
    tag: "Escalation",
    role: "Recommends alert severity, escalation path, and supervisor notification when thresholds are breached.",
    outputs: "Alert recommendation, urgency rationale",
  },
  {
    name: "Report Agent",
    tag: "Reporting",
    role: "Assembles structured report sections for supervisors — metrics, diagnosis, plan, and business impact.",
    outputs: "Report JSON, executive narrative blocks",
  },
  {
    name: "Scenario Agent",
    tag: "Simulation",
    role: "Models failure cascades across asset dependencies — downtime, production loss, contingency plans.",
    outputs: "Cascade map, financial impact, contingency steps",
  },
  {
    name: "Advisor Agent",
    tag: "Synthesizer",
    role: "Final LLM synthesis (Groq / Gemini) grounded in all agent outputs — never hallucinates beyond evidence.",
    outputs: "Natural-language answer, citations, follow-ups",
  },
];

const DATA_TRUTH = [
  {
    title: "Real NASA data",
    color: "border-emerald-500 bg-emerald-50",
    badge: "Authentic",
    badgeClass: "bg-emerald-100 text-emerald-800",
    items: [
      "NASA C-MAPSS FD001 turbofan degradation dataset — publicly available benchmark data",
      "Sensor cycles (temperature, vibration, pressure, motor current) streamed as live readings",
      "XGBoost RUL and Isolation Forest models trained on C-MAPSS-derived feature vectors",
      "Health scores and failure probabilities calibrated to FD001 degradation signatures",
    ],
  },
  {
    title: "Synthetic operational data",
    color: "border-amber-500 bg-amber-50",
    badge: "Representative demo",
    badgeClass: "bg-amber-100 text-amber-900",
    items: [
      "Five steel-plant assets (BF-001 … CN-005) mapped 1:1 to C-MAPSS engine units for storytelling",
      "Spares inventory, lead times, and procurement records — seeded for demo workflows",
      "Delay logs, some failure history, and alert tickets — illustrative plant operations",
      "Business impact / ROI figures — modelled from asset criticality, not live ERP integration",
      "No connection to Tata Steel production SCADA, MES, or SAP in this demo environment",
    ],
  },
  {
    title: "RAG documents",
    color: "border-tata-blue bg-tata-blue-pale/30",
    badge: "Real indexed files",
    badgeClass: "bg-tata-blue/10 text-tata-blue",
    items: [
      "Equipment manuals and maintenance SOPs uploaded as real PDF/text files",
      "Chunked, embedded (BGE-small), and stored in Qdrant — same pipeline as production RAG",
      "New uploads via Documents page are indexed immediately and searchable by AI",
      "Citations in Diagnose, Chat, and Reports link back to the exact source document",
    ],
  },
];

const RUN_STEPS = [
  {
    title: "Prerequisites",
    items: ["Python 3.11+", "Node.js 18+", "npm 9+"],
    note: "First startup takes 1–3 minutes while the database is seeded and ML models train on NASA C-MAPSS FD001.",
  },
  {
    title: "Start backend",
    code: `cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.local .env
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`,
    note: "Verify at http://localhost:8000/health — expect \"status\": \"healthy\". API docs: /docs",
  },
  {
    title: "Start frontend (new terminal)",
    code: `cd frontend
npm install
npm run dev`,
    note: "Open http://localhost:3000 in your browser.",
  },
  {
    title: "Log in",
    items: [
      "Engineer — engineer@steelplant.com / demo1234",
      "Supervisor — supervisor@steelplant.com / demo1234",
      "Admin — admin@steelplant.com / demo1234",
    ],
  },
];

const REVIEW_FLOW = [
  { step: "Dashboard", detail: "Fleet KPIs, health gauges, priority assets" },
  { step: "Live Monitor", detail: "Select an asset; watch C-MAPSS sensor replay and live charts" },
  { step: "Alerts", detail: "Confirm alerts when thresholds are breached" },
  { step: "Ask AI", detail: "Try: \"What is the RUL for the highest-risk asset?\"" },
  { step: "Diagnose", detail: "Root-cause analysis, citations, AI Reasoning Panel" },
  { step: "Decision Simulator", detail: "Compare delay vs. repair scenarios" },
  { step: "Reports", detail: "Generate and download a PDF report" },
  { step: "Logbook", detail: "Auto entries from alerts, diagnoses, and schedules" },
];

const RUN_TIPS = [
  { issue: "Connection refused on port 3000", fix: "Start the frontend with npm run dev" },
  { issue: "Login fails / network error", fix: "Ensure backend is running on port 8000; check /health" },
  { issue: "Slow first load", fix: "Normal — DB seed and ML bootstrap on first boot" },
  { issue: "Generic chat answers", fix: "Add GROQ_API_KEY or GEMINI_API_KEY to backend/.env and restart" },
];

function SourceBadge({ type }: { type: "real" | "demo" | "mixed" | "live" }) {
  const styles = {
    real: "bg-emerald-100 text-emerald-800",
    demo: "bg-amber-100 text-amber-900",
    mixed: "bg-blue-100 text-blue-800",
    live: "bg-purple-100 text-purple-800",
  };
  const labels = { real: "Real dataset", demo: "Demo seed", mixed: "Auto + demo", live: "Session data" };
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${styles[type]}`}>{labels[type]}</span>;
}

export default function HowItWorksPage() {
  return (
    <Shell>
      <PageHeader
        label="Solution architecture"
        title="How This System Works"
        subtitle="End-to-end transparency for judges — data provenance, ML pipeline, multi-agent flow, and what is real versus representative demo data."
        action={
          <Link href="/credits" className="btn-secondary text-sm">
            Requirements checklist
          </Link>
        }
      />

      {/* Trust banner */}
      <div className="panel mb-6 border-l-4 border-l-tata-blue">
        <div className="flex items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-tata-blue/10 text-tata-blue">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-semibold text-tata-ink">Built for auditability</h2>
            <p className="mt-1 text-sm leading-relaxed text-tata-muted">
              Every AI recommendation traces back to sensor evidence, retrieved documents, or agent reasoning steps.
              Open <strong className="font-medium text-tata-ink">Diagnose</strong> or <strong className="font-medium text-tata-ink">Ask AI</strong> to see
              the live agent trace, citations, and confidence scores — not a black box.
            </p>
          </div>
        </div>
      </div>

      {/* 1. Data Sources */}
      <section className="mb-8">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-tata-blue text-xs font-bold text-white">1</span>
          <h2 className="text-lg font-semibold text-tata-ink">Data Sources</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {DATA_SOURCES.map(({ name, icon: Icon, description, feeds, badge }) => (
            <div key={name} className="panel flex flex-col">
              <div className="mb-3 flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-tata-blue" />
                  <p className="font-semibold text-tata-ink">{name}</p>
                </div>
                <SourceBadge type={badge} />
              </div>
              <p className="flex-1 text-sm leading-relaxed text-tata-muted">{description}</p>
              <p className="mt-3 border-t border-tata-border pt-3 text-[11px] text-tata-muted">
                <span className="font-semibold uppercase tracking-wide text-tata-ink/70">Feeds → </span>
                {feeds}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* 2. AI Pipeline */}
      <section className="mb-8">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-tata-blue text-xs font-bold text-white">2</span>
          <h2 className="text-lg font-semibold text-tata-ink">AI Pipeline</h2>
        </div>
        <div className="panel">
          <p className="mb-5 text-sm text-tata-muted">
            Sensor ingest through ML inference, agent orchestration, knowledge retrieval, planning, and report generation.
          </p>
          <div className="mx-auto max-w-md">
            {PIPELINE.map(({ step, detail, icon: Icon }, i) => (
              <div key={step}>
                <div className="flex items-start gap-4 rounded-xl border border-tata-border bg-white p-4 shadow-sm">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-tata-blue to-tata-blue-light text-white">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-semibold text-tata-ink">{step}</p>
                    <p className="mt-1 text-xs leading-relaxed text-tata-muted">{detail}</p>
                  </div>
                </div>
                {i < PIPELINE.length - 1 && (
                  <div className="flex justify-center py-1 text-tata-blue/50">
                    <ArrowDown className="h-5 w-5" />
                  </div>
                )}
              </div>
            ))}
          </div>
          <p className="mt-5 rounded-lg bg-tata-blue-pale/40 px-4 py-3 text-xs leading-relaxed text-tata-muted">
            <Bot className="mr-1 inline h-3.5 w-3.5 text-tata-blue" />
            LangGraph coordinates specialist agents inside the pipeline. RAG, Diagnostic, Spares, Planner, Alert, Report,
            and Scenario agents run in dependency order; the Advisor synthesizes the final grounded response.
          </p>
        </div>
      </section>

      {/* 3. Agent Flow */}
      <section className="mb-8">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-tata-blue text-xs font-bold text-white">3</span>
          <h2 className="text-lg font-semibold text-tata-ink">Agent Flow</h2>
        </div>
        <p className="mb-4 text-sm text-tata-muted">
          Ten LangGraph agents — each with a single responsibility. The Supervisor selects a subset per query intent
          (diagnosis, fleet overview, spares, scenario simulation, etc.).
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {AGENTS.map((a, i) => (
            <div key={a.name} className="panel">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-tata-blue">
                  {i === 0 ? "Entry point" : `Step ${i}`} · {a.tag}
                </span>
                <span className="rounded bg-steel-100 px-1.5 py-0.5 font-mono text-[10px] text-steel-600">
                  {a.name.replace(/ Agent$/, "").replace(/ /g, "_").toLowerCase()}
                </span>
              </div>
              <p className="font-semibold text-tata-ink">{a.name}</p>
              <p className="mt-1.5 text-sm leading-relaxed text-tata-muted">{a.role}</p>
              <p className="mt-2 text-[11px] text-tata-muted">
                <span className="font-semibold text-tata-ink/60">Outputs: </span>
                {a.outputs}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* 4. Real vs Demo Data */}
      <section className="mb-8">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-tata-blue text-xs font-bold text-white">4</span>
          <h2 className="text-lg font-semibold text-tata-ink">Real vs Demo Data</h2>
        </div>
        <p className="mb-4 text-sm text-tata-muted">
          We label data provenance explicitly so judges can distinguish authentic ML inputs from representative plant context.
        </p>
        <div className="grid gap-4 lg:grid-cols-3">
          {DATA_TRUTH.map(({ title, color, badge, badgeClass, items }) => (
            <div key={title} className={`rounded-xl border-l-4 p-5 ${color}`}>
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="font-semibold text-tata-ink">{title}</h3>
                <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${badgeClass}`}>
                  {badge}
                </span>
              </div>
              <ul className="space-y-2 text-sm leading-relaxed text-tata-ink/80">
                {items.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-40" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* 5. Instructions to Run */}
      <section className="mb-8">
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-tata-blue text-xs font-bold text-white">5</span>
          <h2 className="text-lg font-semibold text-tata-ink">Instructions to Run</h2>
        </div>
        <p className="mb-4 text-sm text-tata-muted">
          Steps for reviewers and judges to clone, run, and test the prototype locally.
        </p>

        <div className="grid gap-4 lg:grid-cols-2">
          {RUN_STEPS.map(({ title, code, items, note }) => (
            <div key={title} className="panel">
              <div className="mb-3 flex items-center gap-2">
                <Terminal className="h-4 w-4 text-tata-blue" />
                <h3 className="font-semibold text-tata-ink">{title}</h3>
              </div>
              {code ? (
                <pre className="overflow-x-auto rounded-lg bg-steel-900 px-4 py-3 text-xs leading-relaxed text-steel-100">
                  <code>{code}</code>
                </pre>
              ) : (
                <ul className="space-y-1.5 text-sm text-tata-muted">
                  {items?.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-tata-blue/60" />
                      {item}
                    </li>
                  ))}
                </ul>
              )}
              {note && <p className="mt-3 text-xs leading-relaxed text-tata-muted">{note}</p>}
            </div>
          ))}
        </div>

        <div className="mt-4 panel">
          <h3 className="mb-3 font-semibold text-tata-ink">Recommended review flow (~5 min)</h3>
          <ol className="space-y-2">
            {REVIEW_FLOW.map(({ step, detail }, i) => (
              <li key={step} className="flex gap-3 text-sm">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-tata-blue/10 text-xs font-bold text-tata-blue">
                  {i + 1}
                </span>
                <span>
                  <strong className="font-medium text-tata-ink">{step}</strong>
                  <span className="text-tata-muted"> — {detail}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {RUN_TIPS.map(({ issue, fix }) => (
            <div key={issue} className="rounded-lg border border-tata-border bg-white px-4 py-3 text-sm">
              <p className="font-medium text-tata-ink">{issue}</p>
              <p className="mt-1 text-tata-muted">{fix}</p>
            </div>
          ))}
        </div>

        <p className="mt-4 rounded-lg bg-tata-blue-pale/40 px-4 py-3 text-xs leading-relaxed text-tata-muted">
          <strong className="font-medium text-tata-ink">Optional — smarter AI:</strong> add{" "}
          <code className="rounded bg-white px-1 py-0.5 text-[11px]">GROQ_API_KEY</code> or{" "}
          <code className="rounded bg-white px-1 py-0.5 text-[11px]">GEMINI_API_KEY</code> to{" "}
          <code className="rounded bg-white px-1 py-0.5 text-[11px]">backend/.env</code>, set{" "}
          <code className="rounded bg-white px-1 py-0.5 text-[11px]">LLM_PROVIDER</code>, and restart the backend.
          Without keys, ML + rule-based responses still work.
        </p>
      </section>

      {/* CTA */}
      <section className="panel">
        <h2 className="panel-title mb-2">Verify it yourself</h2>
        <p className="mb-4 text-sm text-tata-muted">
          Each module below exposes the pipeline live — sensor charts, agent traces, citations, and PDF exports.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/monitor" className="btn-primary">Live Monitor</Link>
          <Link href="/diagnose" className="btn-secondary">Run Diagnosis</Link>
          <Link href="/chat" className="btn-secondary">Ask AI</Link>
          <Link href="/simulate" className="btn-secondary">Failure Simulator</Link>
          <Link href="/knowledge" className="btn-secondary">Documents (RAG)</Link>
        </div>
      </section>
    </Shell>
  );
}
