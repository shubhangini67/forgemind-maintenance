export function getApiUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") return `http://${window.location.hostname}:8000/api/v1`;
  return "http://localhost:8000/api/v1";
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("spmw_token");
}

export function setToken(token: string) {
  localStorage.setItem("spmw_token", token);
}

export function clearToken() {
  localStorage.removeItem("spmw_token");
}

type CacheEntry = { data: unknown; expires: number };
const memCache = new Map<string, CacheEntry>();

function getCached<T>(key: string): T | undefined {
  const entry = memCache.get(key);
  if (entry && entry.expires > Date.now()) return entry.data as T;
  if (entry) memCache.delete(key);
  return undefined;
}

function setCached<T>(key: string, data: T, ttlMs = 30_000) {
  memCache.set(key, { data, expires: Date.now() + ttlMs });
}

export function clearApiCache(prefix?: string) {
  if (!prefix) {
    memCache.clear();
    return;
  }
  for (const key of memCache.keys()) {
    if (key.startsWith(prefix)) memCache.delete(key);
  }
}

export type PublicPlantStatus = {
  plant_assets: number;
  active_alerts: number;
  critical_assets: number;
  average_health: number;
  models_online: string[];
  live: boolean;
};

export async function fetchPublicPlantStatus(): Promise<PublicPlantStatus> {
  const base = getApiUrl().replace(/\/api\/v1$/, "");
  const res = await fetch(`${base}/api/v1/public/plant-status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Plant status unavailable");
  return res.json();
}

function cachedGet<T>(key: string, fetcher: () => Promise<T>, ttlMs = 30_000): Promise<T> {
  const hit = getCached<T>(key);
  if (hit !== undefined) return Promise.resolve(hit);
  return fetcher().then((data) => {
    setCached(key, data, ttlMs);
    return data;
  });
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  const res = await fetch(`${getApiUrl()}${path}`, { ...options, headers }).catch(() => {
    throw new Error("Backend offline — run backend/scripts/start_backend.sh on port 8000");
  });
  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/") {
      window.location.href = "/";
    }
    throw new Error("Session expired — please sign in again.");
  }
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

export const api = {
  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${getApiUrl()}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) throw new Error("Login failed");
    return res.json();
  },
  dashboard: () => cachedGet("dashboard", () => request<any>("/equipment/dashboard")),
  plantTwin: () => cachedGet("plant-twin", () => request<any>("/equipment/plant-twin")),
  priority: () => cachedGet("priority", () => request<any[]>("/equipment/priority")),
  equipment: () => cachedGet("equipment", () => request<any[]>("/equipment")),
  equipmentDetail: (id: number) => request<any>(`/equipment/${id}`),
  sensors: (id: number) => request<any[]>(`/equipment/${id}/sensors`),
  prediction: (id: number) => request<any>(`/equipment/${id}/predictions`),
  health: (id: number) => request<any>(`/equipment/${id}/health`),
  alerts: (status?: string, limit = 50) =>
    request<any[]>(`/alerts?${new URLSearchParams({ ...(status ? { status } : {}), limit: String(limit) })}`),
  alertsSummary: () => request<any>("/alerts/summary"),
  analytics: () => request<any>("/analytics/plant"),
  businessImpact: () => request<any>("/analytics/business-impact"),
  executiveSummary: () => request<any>("/analytics/executive-summary"),
  scheduler: () => request<any>("/scheduler/plan"),
  schedulerReminders: () => request<any[]>("/scheduler/reminders"),
  createSchedulerReminder: (payload: { equipment_id: number; title: string; reminder_at: string; notes?: string }) =>
    request<any>("/scheduler/reminders", { method: "POST", body: JSON.stringify(payload) }),
  acknowledgeAlert: (id: number) => request<any>(`/alerts/${id}/acknowledge`, { method: "PATCH" }),
  resolveAlert: (id: number) => request<any>(`/alerts/${id}/resolve`, { method: "PATCH" }),
  logbook: (equipmentId?: number, opts?: { entryType?: string; autoOnly?: boolean }) => {
    const params = new URLSearchParams();
    if (equipmentId) params.set("equipment_id", String(equipmentId));
    if (opts?.entryType) params.set("entry_type", opts.entryType);
    if (opts?.autoOnly === true) params.set("auto_only", "true");
    if (opts?.autoOnly === false) params.set("auto_only", "false");
    const q = params.toString();
    return request<any[]>(`/logbook${q ? `?${q}` : ""}`);
  },
  logbookSummary: (equipmentId?: number) =>
    request<any>(equipmentId ? `/logbook/summary?equipment_id=${equipmentId}` : "/logbook/summary"),
  logbookTimeline: (equipmentId: number) => request<any>(`/logbook/timeline/${equipmentId}`),
  createLogbook: (body: Record<string, unknown>) =>
    request<any>("/logbook", { method: "POST", body: JSON.stringify(body) }),
  history: (equipmentId: number) => request<any>(`/history/${equipmentId}`),
  sparesList: () => request<any[]>("/spares"),
  procurement: () => request<any[]>("/procurement"),
  createProcurement: (body: Record<string, unknown>) =>
    request<any>("/procurement", { method: "POST", body: JSON.stringify(body) }),
  approveProcurement: (id: number) => request<any>(`/procurement/${id}/approve`, { method: "PATCH" }),
  rejectProcurement: (id: number, reason: string) =>
    request<any>(`/procurement/${id}/reject`, { method: "PATCH", body: JSON.stringify({ reason }) }),
  liveSnapshot: (equipmentId: number) => request<any>(`/monitor/live/${equipmentId}`),
  chat: (
    message: string,
    conversationId?: number,
    equipmentId?: number,
    pageContext?: string,
    branchFromMessageId?: number
  ) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    return request<any>("/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        equipment_id: equipmentId,
        page_context: pageContext,
        branch_from_message_id: branchFromMessageId,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));
  },
  chatConversations: () => request<any[]>("/chat/conversations"),
  chatConversation: (id: number) => request<any>(`/chat/conversations/${id}`),
  diagnose: (payload: {
    equipment_id: number;
    symptoms: string;
    fault_codes?: string[];
    incident_description?: string;
  }) => request<any>("/diagnose", { method: "POST", body: JSON.stringify(payload) }),
  feedback: (payload: Record<string, unknown>) =>
    request<any>("/feedback", { method: "POST", body: JSON.stringify(payload) }),
  feedbackStats: () => request<any>("/feedback/stats"),
  delayLogs: () => request<any[]>("/delay-logs"),
  createDelayLog: (body: Record<string, unknown>) =>
    request<any>("/delay-logs", { method: "POST", body: JSON.stringify(body) }),
  documents: () => request<any[]>("/documents"),
  uploadDocument: async (file: File, documentType: string, equipmentType?: string) => {
    const form = new FormData();
    form.append("file", file);
    const token = getToken();
    const params = new URLSearchParams({ document_type: documentType });
    if (equipmentType) params.set("equipment_type", equipmentType);
    const res = await fetch(`${getApiUrl()}/documents/upload?${params}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  reports: () => request<any[]>("/reports"),
  getReport: (id: number) => request<any>(`/reports/${id}`),
  generateReport: (payload: Record<string, unknown>) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 180000);
    return request<any>("/reports/generate", {
      method: "POST",
      body: JSON.stringify(payload),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));
  },
  downloadReportPdf: async (id: number) => {
    const token = getToken();
    const res = await fetch(`${getApiUrl()}/reports/${id}/pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).catch(() => {
      throw new Error("Backend offline — start backend first");
    });
    if (!res.ok) throw new Error("PDF download failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  },
  downloadPdfExport: async (opts: {
    report_type: string;
    equipment_id?: number;
    alert_id?: number;
    title?: string;
    payload?: Record<string, unknown>;
  }) => {
    const token = getToken();
    const res = await fetch(`${getApiUrl()}/reports/pdf/export`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(opts),
    }).catch(() => {
      throw new Error("Backend offline — start backend first");
    });
    if (res.status === 401) {
      clearToken();
      if (typeof window !== "undefined") window.location.href = "/";
      throw new Error("Session expired — please sign in again.");
    }
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "PDF export failed");
    }
    const blob = await res.blob();
    const code = opts.payload?.equipment_code || opts.equipment_id || "report";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tata_${opts.report_type}_${code}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  },
  documentContent: (id: number) => request<any>(`/documents/${id}/content`),
  simulateDependencies: () => request<any>("/simulate/dependencies"),
  simulate: (payload: Record<string, unknown>) =>
    request<any>("/simulate", { method: "POST", body: JSON.stringify(payload) }),
  simulateDecision: (payload: {
    equipment_id: number;
    mode?: "delay" | "immediate_failure";
    delay_hours?: number;
    custom_delay_hours?: number;
    failure_mode?: string;
  }) => request<any>("/simulate/decision", { method: "POST", body: JSON.stringify(payload) }),
};

export function riskColor(level: string) {
  switch (level?.toLowerCase()) {
    case "critical":
      return "text-red-400 bg-red-500/15";
    case "high":
      return "text-orange-400 bg-orange-500/15";
    case "medium":
    case "warning":
      return "text-yellow-400 bg-yellow-500/15";
    default:
      return "text-emerald-400 bg-emerald-500/15";
  }
}
