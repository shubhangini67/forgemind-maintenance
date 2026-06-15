"use client";

import { useEffect, useState } from "react";

function healthUrl(): string {
  if (typeof window === "undefined") return "http://localhost:8000/health";
  const env = process.env.NEXT_PUBLIC_API_URL;
  if (env) return env.replace(/\/api\/v1\/?$/, "") + "/health";
  return `http://${window.location.hostname}:8000/health`;
}

export function BackendStatus({ variant = "default" }: { variant?: "default" | "sidebar" }) {
  const [ok, setOk] = useState<boolean | null>(null);
  const [starting, setStarting] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    async function check() {
      attempts += 1;
      try {
        const r = await fetch(healthUrl(), { signal: AbortSignal.timeout(12000) });
        if (cancelled) return;
        setOk(r.ok);
        setStarting(false);
      } catch {
        if (cancelled) return;
        // First ~90s after page load: backend may still be bootstrapping
        if (attempts <= 8) {
          setOk(null);
          setStarting(true);
        } else {
          setOk(false);
          setStarting(false);
        }
      }
    }

    check();
    const id = setInterval(check, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const sidebar = variant === "sidebar";

  if (ok === null) {
    return (
      <span className={`badge ${sidebar ? "bg-white/10 text-tata-muted" : "bg-steel-100 text-steel-400"}`}>
        {starting ? "Starting…" : "…"}
      </span>
    );
  }

  return (
    <span
      className={`badge ${
        ok
          ? sidebar
            ? "bg-emerald-400/20 text-emerald-100"
            : "bg-emerald-50 text-emerald-700"
          : sidebar
            ? "bg-red-400/20 text-red-100"
            : "bg-red-50 text-red-700"
      }`}
      title={ok ? "Backend connected" : "Run backend/scripts/start_backend.sh"}
    >
      <span
        className={`mr-1 inline-block h-1.5 w-1.5 rounded-full ${ok ? "animate-pulse-live bg-emerald-400" : "bg-red-500"}`}
      />
      {ok ? "API OK" : "API DOWN"}
    </span>
  );
}
