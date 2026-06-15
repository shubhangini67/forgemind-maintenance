import { Suspense } from "react";

export default function EquipmentLayout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="p-8 text-tata-muted">Loading equipment…</div>}>{children}</Suspense>;
}
