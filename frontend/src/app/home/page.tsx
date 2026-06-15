"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { TataSectionTitle } from "@/components/TataBrand";
import { HealthBar } from "@/components/ui/HealthBar";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  BarChart3,
  Bell,
  Brain,
  Calendar,
  ChevronRight,
  LayoutDashboard,
  Radio,
  TrendingUp,
  Wrench,
} from "lucide-react";

type Tab = "operations" | "intelligence" | "records";

const TABS: { id: Tab; label: string }[] = [
  { id: "operations", label: "Operations" },
  { id: "intelligence", label: "AI & Diagnostics" },
  { id: "records", label: "Records" },
];

const MODULES: Record<Tab, { href: string; label: string; desc: string; tag: string }[]> = {
  operations: [
    { href: "/monitor", label: "Live Operations", desc: "Real-time C-MAPSS sensor stream across all five plant assets.", tag: "Live" },
    { href: "/dashboard", label: "Plant Dashboard", desc: "Fleet health overview, equipment status, and priority actions.", tag: "Overview" },
    { href: "/alerts", label: "Alert Center", desc: "Review threshold breaches, acknowledge, and close tickets.", tag: "Alerts" },
    { href: "/priority", label: "Priority Queue", desc: "Maintenance actions ranked by risk and remaining useful life.", tag: "Priority" },
    { href: "/scheduler", label: "Maintenance Schedule", desc: "Planned work orders and engineer reminders.", tag: "Schedule" },
    { href: "/equipment", label: "Equipment Registry", desc: "BF-001 through CN-005 — C-MAPSS FD001 mapped assets.", tag: "Assets" },
  ],
  intelligence: [
    { href: "/chat", label: "AI Assistant", desc: "Ask questions, diagnose faults, and query maintenance documentation.", tag: "AI" },
    { href: "/diagnose", label: "Fault Diagnosis", desc: "Structured diagnostic workflow with sensor context.", tag: "Diagnose" },
    { href: "/analytics", label: "Analytics & ROI", desc: "Degradation trends, health scores, and savings projections.", tag: "Analytics" },
    { href: "/simulate", label: "Decision Simulator", desc: "Compare delay vs act-now — failure probability, cost, cascade, and AI recommendation.", tag: "Simulate" },
  ],
  records: [
    { href: "/logbook", label: "Engineer Logbook", desc: "Automatic and manual maintenance event records.", tag: "Logbook" },
    { href: "/reports", label: "Reports", desc: "Generate PDF maintenance and health reports.", tag: "Reports" },
    { href: "/history", label: "Work History", desc: "Past interventions and completed maintenance tasks.", tag: "History" },
    { href: "/knowledge", label: "Documents", desc: "SOPs, manuals, and uploaded reference material.", tag: "Docs" },
    { href: "/spares", label: "Spares Inventory", desc: "Parts availability and stock levels.", tag: "Inventory" },
    { href: "/delays", label: "Delay Logs", desc: "Track and explain schedule deviations.", tag: "Delays" },
  ],
};

const FEATURED = [
  {
    href: "/monitor",
    label: "Live Monitor",
    sub: "Sensor stream · 5 assets",
    icon: Radio,
    image: "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=800&q=80",
  },
  {
    href: "/dashboard",
    label: "Plant Dashboard",
    sub: "Fleet health & status",
    icon: LayoutDashboard,
    image: "https://images.unsplash.com/photo-1581094794329-c8112a89af12?w=800&q=80",
  },
  {
    href: "/chat",
    label: "Ask AI",
    sub: "Diagnose · query docs",
    icon: Brain,
    image: "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800&q=80",
  },
];

export default function HomePage() {
  const router = useRouter();
  const [summary, setSummary] = useState<any>(null);
  const [fleet, setFleet] = useState<any[]>([]);
  const [tab, setTab] = useState<Tab>("operations");

  useEffect(() => {
    if (!getToken()) router.push("/");
    else {
      Promise.all([api.dashboard(), api.plantTwin()])
        .then(([dash, twin]) => {
          setSummary(dash);
          setFleet(twin.cmapss_fleet || twin.assets || []);
        })
        .catch(() => {});
    }
  }, [router]);

  const items = MODULES[tab];
  const openAlerts = summary?.open_alerts ?? 0;

  return (
    <Shell fullWidth>
      {/* Hero with industrial photography */}
      <section className="relative min-h-[420px] overflow-hidden text-white">
        <Image
          src="https://images.unsplash.com/photo-1581094794329-c8112a89af12?w=1920&q=80"
          alt=""
          fill
          priority
          className="object-cover"
          sizes="100vw"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/70 to-black/50" />
        <div className="absolute inset-0 bg-tata-blue/20 mix-blend-multiply" />

        <div className="relative mx-auto max-w-6xl px-6 py-16 sm:px-10 sm:py-20">
          <p className="animate-fade-up text-[11px] font-semibold uppercase tracking-[0.4em] text-white/55">
            Engineer Portal
          </p>
          <h1 className="animate-fade-up mt-4 text-4xl font-light tracking-wide sm:text-5xl lg:text-[3.25rem]">
            Maintenance Wizard
          </h1>
          <p className="animate-fade-up mt-4 max-w-lg text-sm leading-relaxed text-white/70 sm:text-base">
            Predictive maintenance for the steel plant — five C-MAPSS assets monitored with live sensors and AI diagnostics.
          </p>

          {openAlerts > 0 && (
            <Link
              href="/alerts"
              className="animate-fade-up mt-6 inline-flex items-center gap-2 border border-red-400/40 bg-red-950/50 px-4 py-2.5 text-sm text-red-100 backdrop-blur-sm transition hover:bg-red-950/70"
            >
              <Bell className="h-4 w-4" />
              {openAlerts} open alert{openAlerts !== 1 ? "s" : ""} need review
              <ChevronRight className="h-4 w-4" />
            </Link>
          )}

          <div className="mt-14 grid sm:grid-cols-3">
            <div className="hero-stat-col">
              <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-white/45">Fleet Status</p>
              <p className="mt-3 text-5xl font-extralight tabular-nums">5</p>
              <p className="mt-1 text-xs text-white/50">Active assets · C-MAPSS FD001</p>
            </div>
            <div className="hero-stat-col">
              <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-white/45">Open Alerts</p>
              <p className="mt-3 text-5xl font-extralight tabular-nums">{summary?.open_alerts ?? "—"}</p>
              <p className="mt-1 text-xs text-white/50">Threshold breaches</p>
            </div>
            <div className="hero-stat-col">
              <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-white/45">Average Health</p>
              <p className="mt-3 text-5xl font-extralight tabular-nums">
                {summary ? `${Math.round(summary.avg_health_score)}%` : "—"}
              </p>
              <p className="mt-1 text-xs text-white/50">Fleet-wide score</p>
            </div>
          </div>
        </div>
      </section>

      {/* Fleet health strip */}
      {fleet.length > 0 && (
        <section className="border-b border-tata-border bg-white">
          <div className="mx-auto max-w-6xl px-6 py-5 sm:px-10">
            <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.25em] text-tata-muted">Fleet snapshot</p>
            <div className="grid gap-4 sm:grid-cols-5">
              {fleet.map((a: any) => (
                <Link
                  key={a.id}
                  href={`/monitor?equipment=${a.id}`}
                  className="fleet-chip"
                >
                  <p className="text-xs font-semibold text-tata-ink">{a.equipment_code}</p>
                  <p className="mt-0.5 truncate text-[10px] text-tata-muted">{a.name}</p>
                  <HealthBar value={a.health_score ?? 0} className="mt-2" />
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Featured tiles with images */}
      <section className="bg-[#eef2f7]">
        <div className="mx-auto grid max-w-6xl gap-px bg-tata-border sm:grid-cols-3">
          {FEATURED.map(({ href, label, sub, icon: Icon, image }) => (
            <Link key={href} href={href} className="group relative flex min-h-[200px] flex-col justify-end overflow-hidden bg-[#1a2a3a]">
              <Image src={image} alt="" fill className="object-cover opacity-60 transition duration-500 group-hover:scale-105 group-hover:opacity-75" sizes="33vw" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />
              <div className="relative p-6">
                <Icon className="mb-3 h-7 w-7 text-tata-menu" strokeWidth={1.25} />
                <p className="text-lg font-medium text-white">{label}</p>
                <p className="mt-1 text-xs text-white/55">{sub}</p>
                <span className="mt-3 inline-flex items-center gap-1 text-[11px] uppercase tracking-wider text-tata-menu group-hover:text-white">
                  Open <ChevronRight className="h-3 w-3" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Module grid */}
      <section className="mx-auto max-w-6xl px-6 pb-20 sm:px-10">
        <TataSectionTitle>Maintenance Portal</TataSectionTitle>

        <div className="mb-10 flex flex-wrap justify-center gap-6 border-b border-tata-border sm:gap-10">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`relative pb-3.5 text-sm transition ${
                tab === id
                  ? "font-semibold text-tata-ink after:absolute after:bottom-0 after:left-0 after:h-[3px] after:w-full after:bg-tata-blue"
                  : "text-tata-muted hover:text-tata-ink"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(({ href, label, desc, tag }, i) => (
            <Link key={href} href={href} className="module-card group animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
              <div className="module-card-accent" />
              <div className="module-card-body">
                <div className="flex items-start justify-between gap-3">
                  <div className="module-icon-wrap transition group-hover:bg-tata-blue group-hover:text-white">
                    <ModuleIcon href={href} />
                  </div>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-tata-muted">{tag}</span>
                </div>
                <h3 className="mt-4 text-[15px] font-semibold leading-snug text-tata-ink group-hover:text-tata-blue">
                  {label}
                </h3>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-tata-muted">{desc}</p>
                <span className="mt-5 inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-tata-blue">
                  Enter module <ChevronRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </Shell>
  );
}

function ModuleIcon({ href }: { href: string }) {
  const props = { className: "h-5 w-5", strokeWidth: 1.5 };
  if (href.includes("monitor")) return <Radio {...props} />;
  if (href.includes("dashboard")) return <LayoutDashboard {...props} />;
  if (href.includes("chat")) return <Brain {...props} />;
  if (href.includes("alerts")) return <Bell {...props} />;
  if (href.includes("priority")) return <TrendingUp {...props} />;
  if (href.includes("scheduler")) return <Calendar {...props} />;
  if (href.includes("analytics")) return <BarChart3 {...props} />;
  if (href.includes("equipment")) return <Wrench {...props} />;
  return <ChevronRight {...props} />;
}
