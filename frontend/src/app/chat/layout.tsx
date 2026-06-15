import { Suspense } from "react";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="p-8 text-steel-500">Loading wizard…</div>}>{children}</Suspense>;
}
