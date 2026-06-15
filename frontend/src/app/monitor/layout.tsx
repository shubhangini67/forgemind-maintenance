import { Suspense } from "react";

export default function MonitorLayout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="p-8 text-tata-muted">Loading monitor…</div>}>{children}</Suspense>;
}
