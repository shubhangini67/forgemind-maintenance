"use client";

import { Download, Loader2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";

type PdfExportOptions = {
  reportType: string;
  equipmentId?: number;
  alertId?: number;
  title?: string;
  payload?: Record<string, unknown>;
  label?: string;
  className?: string;
  variant?: "primary" | "secondary";
};

export function DownloadPdfButton({
  reportType,
  equipmentId,
  alertId,
  title,
  payload,
  label = "Download PDF",
  className = "",
  variant = "secondary",
}: PdfExportOptions) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    setLoading(true);
    setError("");
    try {
      await api.downloadPdfExport({
        report_type: reportType,
        equipment_id: equipmentId,
        alert_id: alertId,
        title,
        payload,
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "PDF download failed");
    } finally {
      setLoading(false);
    }
  }

  const btnClass =
    variant === "primary"
      ? "btn-primary inline-flex items-center gap-2 text-sm"
      : "btn-secondary inline-flex items-center gap-2 text-sm";

  return (
    <div className={className}>
      <button type="button" onClick={download} disabled={loading} className={btnClass}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
        {loading ? "Preparing PDF…" : label}
      </button>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
