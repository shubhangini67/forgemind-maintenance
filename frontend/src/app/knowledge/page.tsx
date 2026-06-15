"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { api, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";
import { BookOpen, Upload } from "lucide-react";

const TYPE_COLORS: Record<string, string> = {
  manual: "border-tata-blue/40",
  sop: "border-blue-500/40",
  failure_report: "border-red-500/40",
  log: "border-white/20",
};

export default function KnowledgePage() {
  const router = useRouter();
  const [docs, setDocs] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("manual");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  function load() {
    api.documents().then(setDocs).catch((e) => setError(e.message));
  }

  useEffect(() => {
    if (!getToken()) router.push("/");
    else load();
  }, [router]);

  async function openDoc(id: number) {
    try {
      const content = await api.documentContent(id);
      setSelected(content);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load document");
    }
  }

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await api.uploadDocument(file, docType);
      setFile(null);
      load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Documents & SOPs"
        subtitle="Equipment manuals indexed in Qdrant for RAG — click any document to read."
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <form onSubmit={upload} className="panel">
          <h2 className="panel-title mb-4 flex items-center gap-2">
            <Upload className="h-5 w-5" /> Upload
          </h2>
          <div className="space-y-3">
            <select className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
              <option value="manual">Equipment Manual</option>
              <option value="sop">Maintenance SOP</option>
              <option value="failure_report">Failure Report</option>
              <option value="log">Operational Log</option>
            </select>
            <input type="file" accept=".txt,.md,.pdf" className="input" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <button type="submit" className="btn-primary w-full" disabled={!file || uploading}>
              {uploading ? "Indexing…" : "Upload & Index"}
            </button>
          </div>
        </form>

        <div className="panel lg:col-span-2">
          <h2 className="panel-title mb-4 flex items-center gap-2">
            <BookOpen className="h-5 w-5" /> Indexed Knowledge
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {docs.length === 0 ? (
              <p className="text-sm text-tata-muted sm:col-span-2">No documents indexed yet.</p>
            ) : (
              docs.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => openDoc(d.id)}
                  className={`rounded-xl border bg-white p-4 text-left transition hover:bg-white/[0.04] ${TYPE_COLORS[d.document_type] || "border-tata-border"}`}
                >
                  <p className="font-medium text-tata-ink">{d.title}</p>
                  <p className="mt-1 text-xs uppercase tracking-wide text-tata-muted">{d.document_type}</p>
                  <span className={`mt-2 inline-block badge ${d.indexed ? "bg-emerald-500/15 text-emerald-400" : "bg-yellow-500/15 text-yellow-400"}`}>
                    {d.indexed ? "Indexed" : "Pending"}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {selected && (
        <div className="panel mt-6">
          <div className="panel-header">
            <h2 className="text-lg font-semibold text-tata-ink">{selected.title}</h2>
            <button type="button" className="btn-ghost text-xs" onClick={() => setSelected(null)}>Close</button>
          </div>
          <div className="max-h-96 overflow-y-auto rounded-lg border border-tata-border bg-white p-5 text-sm leading-relaxed text-tata-ink/90 whitespace-pre-wrap">
            {selected.content}
          </div>
          {selected.chunks?.length > 0 && (
            <div className="mt-4">
              <p className="panel-title mb-2">RAG Chunks</p>
              {selected.chunks.map((c: any, i: number) => (
                <div key={i} className="mb-2 rounded-lg border border-tata-blue/20 bg-tata-blue/5 p-3 text-xs text-tata-muted">
                  <span className="text-tata-blue">Chunk {i + 1}</span> · score {c.score?.toFixed?.(2)} · {c.excerpt?.slice(0, 200)}…
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
