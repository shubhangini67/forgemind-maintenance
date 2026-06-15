"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { StatTile } from "@/components/ui/StatTile";
import { FleetStatusList } from "@/components/ui/FleetStatusList";
import { PriorityQueueList } from "@/components/ui/PriorityQueueList";
import { AiLaunchStrip } from "@/components/AiLaunchStrip";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Activity, AlertTriangle, ArrowRight, Radio, RefreshCw, Server, TrendingUp } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<any>(null);
  const [fleet, setFleet] = useState<any[]>([]);
  const [priority, setPriority] = useState<any[]>([]);
  const [error, setError] = useState("");

  function load() {
    Promise.all([api.dashboard(), api.plantTwin(), api.priority()])
      .then(([dash, twin, pri]) => {
        setSummary(dash);
        setFleet(twin.cmapss_fleet || twin.assets || []);
        setPriority(pri.slice(0, 3));
        setError("");
      })
      .catch((e) =>
        setError(e?.message?.includes("fetch") ? "Backend offline — run start_backend.sh" : e?.message)
      );
  }

  useEffect(() => {
    if (!getToken()) router.push("/");
    else {
      load();
      const id = setInterval(load, 60000);
      return () => clearInterval(id);
    }
  }, [router]);

  const openAlerts = summary?.open_alerts ?? 0;
  const avgHealth = summary ? Math.round(summary.avg_health_score) : null;

  return (
    <Shell>
      <PageHeader
        label="Dashboard"
        title="Plant Overview"
        subtitle="Five assets monitored via NASA C-MAPSS FD001 — live health, alerts, and maintenance priorities"
        action={
          <button onClick={load} className="btn-secondary text-sm">
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        }
      />

      {error && (
        <div className="mb-6 flex items-center gap-3 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {openAlerts > 0 && !error && (
        <Link
          href="/alerts"
          className="surface surface-hover mb-6 flex items-center justify-between border-l-4 border-l-amber-400 p-5"
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600" />
            <div>
              <p className="text-sm font-semibold text-amber-900">{openAlerts} open alert{openAlerts !== 1 ? "s" : ""}</p>
              <p className="text-xs text-amber-700/80">Review and acknowledge threshold breaches</p>
            </div>
          </div>
          <ArrowRight className="h-4 w-4 text-amber-600" />
        </Link>
      )}

      <div className="stat-grid mb-8 grid grid-cols-2 lg:grid-cols-4">
        <StatTile label="Assets" value={fleet.length || "—"} hint="C-MAPSS mapped" icon={Server} accent="blue" />
        <StatTile
          label="Avg Health"
          value={avgHealth != null ? `${avgHealth}%` : "—"}
          hint="Fleet-wide score"
          icon={Activity}
          accent={avgHealth != null && avgHealth < 50 ? "red" : avgHealth != null && avgHealth < 70 ? "amber" : "green"}
        />
        <StatTile
          label="Open Alerts"
          value={openAlerts}
          hint="Needs review"
          icon={AlertTriangle}
          accent={openAlerts > 0 ? "amber" : "green"}
        />
        <StatTile
          label="Warnings"
          value={(summary?.early_warnings || []).length}
          hint="Early indicators"
          icon={Radio}
          accent="blue"
        />
      </div>

      <AiLaunchStrip
        actions={[
          {
            href: "/monitor",
            label: "Live Sensors",
            desc: "Real-time C-MAPSS stream for all five assets",
            icon: Radio,
          },
          {
            href: "/priority",
            label: "Priority Queue",
            desc: "Ranked maintenance actions by risk and RUL",
            icon: TrendingUp,
          },
        ]}
      />

      <div className="grid items-start gap-6 lg:grid-cols-5">
        <section className="lg:col-span-3">
          {!fleet.length ? (
            <div className="panel text-sm text-tata-muted">Loading fleet data…</div>
          ) : (
            <FleetStatusList fleet={fleet} />
          )}
        </section>

        <section className="lg:col-span-2">
          <PriorityQueueList items={priority} />
        </section>
      </div>
    </Shell>
  );
}
