"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { CostImpactCard } from "@/components/CostImpactCard";
import { DownloadPdfButton } from "@/components/DownloadPdfButton";
import { RiskBadge } from "@/components/RiskBadge";
import { FeedbackStatsWidget } from "@/components/FeedbackStatsWidget";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { FileText, IndianRupee, TrendingUp, Download } from "lucide-react";

function healthBarColor(health: number) {
  if (health < 40) return "#ef4444";
  if (health < 60) return "#f97316";
  if (health < 75) return "#005DAA";
  return "#22c55e";
}

function healthRisk(health: number) {
  if (health < 45) return "critical";
  if (health < 65) return "high";
  if (health < 80) return "medium";
  return "low";
}

function fmtL(n: number) {
  return `₹${(n / 100_000).toFixed(1)}L`;
}

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [executive, setExecutive] = useState<any>(null);
  const [generating, setGenerating] = useState(false);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!getToken()) router.push("/");
    else {
      setLoadError("");
      api
        .analytics()
        .then(setData)
        .catch((err: unknown) => {
          setLoadError(err instanceof Error ? err.message : "Failed to load analytics");
        });
      api.executiveSummary().then(setExecutive).catch(() => {});
    }
  }, [router]);

  const bi = data?.business_impact;
  const fleet = bi?.fleet_summary;
  const critical = bi?.critical_assets || [];
  const downtimePrevented =
    data?.roi?.downtime_hours_prevented ??
    (fleet?.total_avoided_loss_inr != null
      ? Math.round((fleet.total_avoided_loss_inr / 45000) * 10) / 10
      : null);

  const savingsChart = (bi?.assets || []).map((a: any) => ({
    name: a.equipment_code,
    savings: Math.round(a.estimated_savings_inr / 100_000),
    roi: a.roi_pct,
  }));

  const chartData = (data?.equipment || []).map((e: any) => ({
    name: e.equipment_code,
    health: Math.max(1, e.health_score ?? 0),
    displayHealth: e.health_score ?? 0,
  }));

  async function generateExecutiveReport() {
    setGenerating(true);
    try {
      const res = await api.generateReport({ report_type: "executive", title: "Executive Business Impact Summary" });
      router.push("/reports");
    } catch {
      /* stay on page */
    } finally {
      setGenerating(false);
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Business Impact Analytics"
        subtitle="Downtime cost, maintenance investment, avoided loss, savings & ROI — for every critical asset."
      />

      {loadError && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {loadError}
        </div>
      )}

      {!data ? (
        <p className="text-sm text-tata-muted">{loadError ? "Analytics unavailable." : "Loading analytics…"}</p>
      ) : (
        <>
          {/* Savings Dashboard */}
          {fleet && (
            <div className="panel mb-6 border-l-4 border-l-emerald-500">
              <h2 className="panel-title mb-4 flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-emerald-600" /> Savings Dashboard
              </h2>
              <div className="stat-grid mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <div className="stat-card">
                  <p className="stat-label">Fleet ROI</p>
                  <p className="stat-value text-emerald-600">{fleet.fleet_roi_pct}%</p>
                </div>
                <div className="stat-card border-l-4 border-l-emerald-500">
                  <p className="stat-label">Est. savings</p>
                  <p className="stat-value">{fmtL(fleet.total_estimated_savings_inr)}</p>
                </div>
                <div className="stat-card">
                  <p className="stat-label">Avoided loss</p>
                  <p className="stat-value">{fmtL(fleet.total_avoided_loss_inr)}</p>
                </div>
                <div className="stat-card">
                  <p className="stat-label">Maintenance cost</p>
                  <p className="stat-value">{fmtL(fleet.total_maintenance_cost_inr)}</p>
                </div>
                <div className="stat-card border-l-4 border-l-red-400">
                  <p className="stat-label">Downtime exposure</p>
                  <p className="stat-value">{fmtL(fleet.total_downtime_cost_inr)}</p>
                </div>
              </div>
              {savingsChart.length > 0 && (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={savingsChart} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,93,170,0.12)" />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#5C6B82" }} />
                      <YAxis tick={{ fontSize: 11, fill: "#5C6B82" }} unit="L" />
                      <Tooltip
                        contentStyle={{ background: "#fff", border: "1px solid #D4E0ED", borderRadius: 8 }}
                        formatter={(v: number, name: string) =>
                          name === "savings" ? [`₹${v}L`, "Est. savings"] : [`${v}%`, "ROI"]
                        }
                      />
                      <Bar dataKey="savings" name="savings" fill="#005DAA" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <p className="mt-3 text-xs text-tata-muted">
                Formulas: avoided_loss = downtime_cost × failure_prob × prevention_factor × (criticality/5);
                savings = avoided_loss − maintenance_cost; ROI = savings / maintenance_cost × 100
              </p>
            </div>
          )}

          {/* Critical asset cost impact cards */}
          {critical.length > 0 && (
            <div className="mb-6">
              <h2 className="panel-title mb-4 flex items-center gap-2">
                <IndianRupee className="h-5 w-5" /> Cost Impact — Critical Assets ({critical.length})
              </h2>
              <div className="grid gap-4 lg:grid-cols-2">
                {critical.map((asset: any) => (
                  <CostImpactCard key={asset.equipment_code} asset={asset} />
                ))}
              </div>
            </div>
          )}

          {/* Executive Summary Report */}
          {executive && (
            <div className="panel mb-6">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="panel-title flex items-center gap-2">
                    <FileText className="h-5 w-5" /> Executive Summary Report
                  </h2>
                  <p className="mt-1 text-sm text-tata-muted">
                    Board-ready business value narrative for Tata Steel maintenance leadership
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <DownloadPdfButton reportType="executive" label="Download Executive PDF" variant="primary" />
                  <button
                    type="button"
                    onClick={generateExecutiveReport}
                    disabled={generating}
                    className="btn-secondary inline-flex items-center gap-2 text-sm"
                  >
                    <Download className="h-4 w-4" />
                    {generating ? "Saving to Reports…" : "Save to Reports"}
                  </button>
                </div>
              </div>
              <div className="rounded-xl border border-tata-border bg-gradient-to-br from-white to-tata-blue-pale/30 p-5 text-sm leading-relaxed text-tata-ink/90 whitespace-pre-wrap">
                {executive.narrative}
              </div>
              <Link href="/reports" className="mt-3 inline-block text-xs text-tata-blue hover:underline">
                View all reports →
              </Link>
            </div>
          )}

          <div className="panel mb-6">
            <h2 className="panel-title mb-4">Feedback-Driven Learning</h2>
            <FeedbackStatsWidget />
          </div>

          <div className="stat-grid mb-6 grid gap-4 md:grid-cols-4">
            <div className="stat-card">
              <p className="stat-label">Fleet Avg Health</p>
              <p className="stat-value">{data.avg_health ?? "—"}%</p>
            </div>
            <div className="stat-card border-l-4 border-l-red-400">
              <p className="stat-label">At-Risk Assets</p>
              <p className="stat-value">{data.at_risk_count ?? "—"}</p>
            </div>
            <div className="stat-card">
              <p className="stat-label">Critical Assets</p>
              <p className="stat-value">{fleet?.critical_asset_count ?? "—"}</p>
            </div>
            <div className="stat-card">
              <p className="stat-label">Downtime Prevented</p>
              <p className="stat-value">{downtimePrevented != null ? `${downtimePrevented}h` : "—"}</p>
            </div>
          </div>

          <div className="panel mb-6">
            <h2 className="panel-title mb-4">Equipment Degradation Leaderboard</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,93,170,0.12)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#5C6B82" }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#5C6B82" }} />
                  <Tooltip formatter={(v: number, _n: string, p: any) => [`${p.payload.displayHealth}%`, "Health"]} />
                  <Bar dataKey="health" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry: any) => (
                      <Cell key={entry.name} fill={healthBarColor(entry.displayHealth)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel overflow-x-auto">
            <h2 className="panel-title mb-4">Business Impact by Asset</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Health</th>
                  <th>Downtime cost</th>
                  <th>Maintenance</th>
                  <th>Avoided loss</th>
                  <th>Savings</th>
                  <th>ROI</th>
                </tr>
              </thead>
              <tbody>
                {(bi?.assets || []).map((a: any) => (
                  <tr key={a.equipment_code}>
                    <td>
                      <p className="font-medium">{a.equipment_code}</p>
                      <p className="text-xs text-tata-muted">{a.name}</p>
                    </td>
                    <td>
                      <RiskBadge level={healthRisk(a.health_score)} /> {a.health_score}%
                    </td>
                    <td>{fmtL(a.downtime_cost_inr)}</td>
                    <td>{fmtL(a.maintenance_cost_inr)}</td>
                    <td className="text-tata-blue">{fmtL(a.avoided_loss_inr)}</td>
                    <td className="font-semibold text-emerald-600">{fmtL(a.estimated_savings_inr)}</td>
                    <td className="font-bold">{a.roi_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Shell>
  );
}
