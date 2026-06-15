"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { StatTile } from "@/components/ui/StatTile";
import { api, getApiUrl, getToken, riskColor } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { Activity, Gauge, Radio, Thermometer, Waves, Zap } from "lucide-react";

const TEMP_COLOR = "#e67e22";
const VIB_COLOR = "#c0392b";
const HEALTH_COLOR = "#2a9d8f";
const PRESS_COLOR = "#6366f1";

type Reading = {
  time: string;
  vibration: number;
  temperature: number;
  health: number;
  pressure: number;
  motor: number;
};

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return ts;
  }
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="min-w-[168px] rounded-xl border border-tata-border bg-white px-3 py-2.5 shadow-panel">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-tata-blue">{label}</p>
      {payload.map((p: any) => {
        const key = String(p.dataKey || "").toLowerCase();
        const unit = key.includes("temp") ? " °C" : key.includes("vib") ? " mm/s" : key.includes("health") ? "%" : key.includes("press") ? " bar" : key.includes("motor") ? " A" : "";
        return (
          <div key={p.dataKey} className="flex items-center justify-between gap-4 text-sm">
            <span className="flex items-center gap-2 text-tata-muted">
              <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
              {p.name}
            </span>
            <span className="font-semibold tabular-nums text-tata-ink">
              {p.value}
              {unit}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function MonitorPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [equipment, setEquipment] = useState<any[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [connected, setConnected] = useState(false);
  const [mode, setMode] = useState<"websocket" | "polling">("polling");
  const [readings, setReadings] = useState<Reading[]>([]);
  const [latest, setLatest] = useState<any>(null);
  const [streamError, setStreamError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [loadingEquipment, setLoadingEquipment] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsActiveRef = useRef(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    setLoadingEquipment(true);
    setLoadError("");
    api
      .equipment()
      .then((eq) => {
        setEquipment(eq);
        const param = searchParams.get("equipment");
        if (param && eq.length) {
          const byId = eq.find((e) => String(e.id) === param);
          const byCode = eq.find((e) => e.equipment_code === param);
          setSelected((byId ?? byCode ?? eq[0]).id);
        } else if (eq.length) {
          setSelected(eq[0].id);
        } else {
          setLoadError("No equipment in fleet — restart backend to seed demo data.");
        }
      })
      .catch((err: Error) => {
        setLoadError(err?.message || "Could not load equipment list.");
      })
      .finally(() => setLoadingEquipment(false));
  }, [router, searchParams]);

  const pushReading = useCallback((data: any) => {
    if (!data) return;
    setStreamError("");
    setLatest(data);
    setConnected(true);
    setReadings((prev) =>
      [
        ...prev,
        {
          time: formatTime(data.timestamp || new Date().toISOString()),
          vibration: Number(data.vibration?.toFixed?.(3) ?? data.vibration),
          temperature: Number(data.temperature?.toFixed?.(2) ?? data.temperature),
          health: Number(data.health_indicator?.toFixed?.(1) ?? data.health_indicator),
          pressure: Number(data.pressure?.toFixed?.(2) ?? data.pressure),
          motor: Number(data.motor_current?.toFixed?.(2) ?? data.motor_current),
        },
      ].slice(-80)
    );
  }, []);

  useEffect(() => {
    if (!selected || !getToken()) return;
    setReadings([]);
    setLatest(null);
    setConnected(false);
    setStreamError("");
    wsActiveRef.current = false;

    const token = getToken();
    const poll = () =>
      api
        .liveSnapshot(selected)
        .then((data) => {
          pushReading(data);
          if (!wsActiveRef.current) setMode("polling");
        })
        .catch((err: Error) => {
          setConnected(false);
          setStreamError(
            err?.message?.includes("offline")
              ? "Backend offline — run backend/scripts/start_backend.sh"
              : err?.message?.includes("401") || err?.message?.includes("Session")
                ? "Session expired — sign in again"
                : "Cannot reach live sensor stream — check backend on port 8000"
          );
        });

    poll();
    pollRef.current = setInterval(poll, 2000);
    wsRef.current?.close();

    const ws = new WebSocket(`${getApiUrl().replace(/^http/, "ws")}/ws/monitor/${selected}?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setMode("websocket");
    };
    ws.onclose = () => {
      wsActiveRef.current = false;
      setMode("polling");
      if (!pollRef.current) pollRef.current = setInterval(poll, 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (ev) => {
      wsActiveRef.current = true;
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      try {
        pushReading(JSON.parse(ev.data));
      } catch {
        /* ignore malformed frame */
      }
    };

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
      ws.close();
    };
  }, [selected, pushReading]);

  const selectedEq = equipment.find((e) => e.id === selected);
  const hasData = readings.length > 0;
  const health = latest?.health_indicator ?? 0;
  const healthAccent = health < 45 ? "red" : health < 65 ? "amber" : "green";

  return (
    <Shell>
      <PageHeader
        label="Operations"
        title="Live Condition Monitoring"
        subtitle={
          selectedEq
            ? `${selectedEq.equipment_code} · ${selectedEq.name} — NASA C-MAPSS FD001 sensor replay`
            : "Real-time C-MAPSS FD001 sensor replay with ML risk scoring"
        }
        action={
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 border px-3 py-2 text-[11px] font-semibold uppercase tracking-wider ${
                connected ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"
              }`}
            >
              <span className={`h-2 w-2 rounded-full ${connected ? "animate-pulse-live bg-emerald-500" : "bg-amber-400"}`} />
              {connected ? `Live · ${mode}` : "Connecting…"}
            </span>
            <select
              className="input min-w-[220px] w-auto"
              value={selected ?? ""}
              onChange={(e) => setSelected(Number(e.target.value))}
            >
              {equipment.map((eq) => (
                <option key={eq.id} value={eq.id}>
                  {eq.equipment_code} — {eq.name}
                </option>
              ))}
            </select>
          </div>
        }
      />

      {(loadError || (streamError && !hasData)) && (
        <div className="mb-6 border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {loadError || streamError}
          {!loadError && streamError?.includes("Session") && (
            <button type="button" className="ml-2 font-semibold underline" onClick={() => router.replace("/")}>
              Sign in
            </button>
          )}
        </div>
      )}

      {loadingEquipment && !loadError && (
        <p className="mb-6 text-sm text-tata-muted">Loading fleet equipment…</p>
      )}

      {latest && (
        <div className="stat-grid mb-8 grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <StatTile label="Cycle / RUL" value={`${latest.cycle ?? "—"} / ${latest.rul_hours?.toFixed?.(0) ?? "—"}h`} icon={Activity} accent="blue" />
          <StatTile label="Temperature" value={`${latest.temperature?.toFixed(1)}°C`} icon={Thermometer} accent="amber" />
          <StatTile label="Vibration" value={`${latest.vibration?.toFixed(2)} mm/s`} icon={Waves} accent="red" />
          <StatTile label="Pressure" value={`${latest.pressure?.toFixed(1)} bar`} icon={Gauge} accent="blue" />
          <StatTile label="Motor Current" value={`${latest.motor_current?.toFixed(1)} A`} icon={Zap} accent="blue" />
          <StatTile label="Health Index" value={`${latest.health_indicator?.toFixed?.(0)}%`} icon={Radio} accent={healthAccent as "green" | "amber" | "red"} hint={latest.ml?.risk_level ? `Risk: ${latest.ml.risk_level}` : undefined} />
        </div>
      )}

      <section className="panel-flush mb-8">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-tata-border bg-tata-blue px-5 py-4 text-white sm:px-6">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-white/65">Sensor trends</p>
            <h3 className="text-sm font-semibold">Temperature · Vibration · Health · Pressure</h3>
          </div>
          {latest && (
            <div className="flex flex-wrap gap-4 text-xs">
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#e67e22]" />
                <span className="text-white/80">{latest.temperature?.toFixed(1)}°C</span>
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#c0392b]" />
                <span className="text-white/80">{latest.vibration?.toFixed(2)} mm/s</span>
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#2a9d8f]" />
                <span className="text-white/80">{latest.health_indicator?.toFixed(0)}% health</span>
              </span>
            </div>
          )}
        </div>

        <div className="grid gap-px bg-tata-border lg:grid-cols-2">
          {/* Temp + Vibration */}
          <div className="bg-white p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h4 className="text-sm font-semibold text-tata-ink">Temperature & Vibration</h4>
                <p className="text-xs text-tata-muted">Dual-axis · dashed lines = alert thresholds</p>
              </div>
              <div className="flex gap-3 text-[10px] text-tata-muted">
                <span className="flex items-center gap-1"><span className="h-1.5 w-4 rounded bg-[#e67e22]" /> °C</span>
                <span className="flex items-center gap-1"><span className="h-1.5 w-4 rounded bg-[#c0392b]" /> mm/s</span>
              </div>
            </div>
            <div className="h-72">
              {!hasData ? (
                <p className="flex h-full items-center justify-center text-sm text-tata-muted">Waiting for stream…</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={readings} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                    <defs>
                      <linearGradient id="tempFillLight" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={TEMP_COLOR} stopOpacity={0.2} />
                        <stop offset="100%" stopColor={TEMP_COLOR} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(0,93,164,0.1)" strokeDasharray="4 4" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: "#5C6B82", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={48} />
                    <YAxis yAxisId="temp" domain={[60, 130]} tick={{ fill: TEMP_COLOR, fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}°`} width={40} />
                    <YAxis yAxisId="vib" orientation="right" domain={[0, 14]} tick={{ fill: VIB_COLOR, fontSize: 10 }} axisLine={false} tickLine={false} width={32} />
                    <ReferenceLine yAxisId="temp" y={92} stroke={TEMP_COLOR} strokeDasharray="4 4" strokeOpacity={0.45} />
                    <ReferenceLine yAxisId="vib" y={6} stroke={VIB_COLOR} strokeDasharray="4 4" strokeOpacity={0.45} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area yAxisId="temp" type="monotone" dataKey="temperature" name="Temperature" stroke={TEMP_COLOR} strokeWidth={2} fill="url(#tempFillLight)" dot={false} isAnimationActive={false} />
                    <Line yAxisId="vib" type="monotone" dataKey="vibration" name="Vibration" stroke={VIB_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Health + Pressure + Motor */}
          <div className="bg-white p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h4 className="text-sm font-semibold text-tata-ink">Health · Pressure · Motor</h4>
                <p className="text-xs text-tata-muted">Degradation index and process variables</p>
              </div>
              <div className="flex gap-3 text-[10px] text-tata-muted">
                <span className="flex items-center gap-1"><span className="h-1.5 w-4 rounded bg-[#2a9d8f]" /> Health</span>
                <span className="flex items-center gap-1"><span className="h-1.5 w-4 rounded bg-[#6366f1]" /> bar</span>
              </div>
            </div>
            <div className="h-72">
              {!hasData ? (
                <p className="flex h-full items-center justify-center text-sm text-tata-muted">Waiting for stream…</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={readings} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                    <defs>
                      <linearGradient id="healthFillLight" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={HEALTH_COLOR} stopOpacity={0.25} />
                        <stop offset="100%" stopColor={HEALTH_COLOR} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(0,93,164,0.1)" strokeDasharray="4 4" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: "#5C6B82", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={48} />
                    <YAxis yAxisId="health" domain={[0, 100]} tick={{ fill: HEALTH_COLOR, fontSize: 10 }} axisLine={false} tickLine={false} width={32} />
                    <YAxis yAxisId="press" orientation="right" domain={[90, 150]} tick={{ fill: PRESS_COLOR, fontSize: 10 }} axisLine={false} tickLine={false} width={36} />
                    <ReferenceLine yAxisId="health" y={55} stroke="#c0392b" strokeDasharray="4 4" strokeOpacity={0.4} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area yAxisId="health" type="monotone" dataKey="health" name="Health Index" stroke={HEALTH_COLOR} strokeWidth={2} fill="url(#healthFillLight)" dot={false} isAnimationActive={false} />
                    <Line yAxisId="press" type="monotone" dataKey="pressure" name="Pressure" stroke={PRESS_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line yAxisId="press" type="monotone" dataKey="motor" name="Motor Current" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="3 3" dot={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      </section>

      {latest?.ml && (
        <section className="panel-flush mb-8">
          <div className="border-b border-tata-border/80 bg-gradient-to-r from-tata-blue-pale/50 to-white px-5 py-4 sm:px-6">
            <h3 className="text-sm font-semibold text-tata-ink">Predictive Maintenance Output</h3>
            <p className="text-xs text-tata-muted">XGBoost RUL · Isolation Forest · live alert engine</p>
          </div>
          <div className="stat-grid grid grid-cols-2 gap-4 p-4 lg:grid-cols-4">
            {[
              { label: "Failure Probability", value: `${(latest.ml.failure_probability * 100).toFixed(1)}%`, accent: "border-l-amber-400" },
              { label: "Remaining Useful Life", value: `${latest.ml.remaining_useful_life_hours?.toFixed?.(0)} h`, accent: "border-l-tata-blue" },
              { label: "Risk Level", value: latest.ml.risk_level, badge: true, accent: "border-l-emerald-400" },
              { label: "Live Alert", value: latest.ml.alert_id ? `Ticket #${latest.ml.alert_id}` : "No new alert", accent: "border-l-red-400" },
            ].map(({ label, value, badge, accent }) => (
              <div key={label} className={`stat-card border-l-4 ${accent}`}>
                <p className="stat-label">{label}</p>
                {badge ? (
                  <span className={`badge mt-2 ${riskColor(value)}`}>{value}</span>
                ) : (
                  <p className="stat-value text-2xl">{value}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </Shell>
  );
}
