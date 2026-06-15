import type { ReactNode } from "react";

/** Tata Steel wordmark — bold TATA + light STEEL, matches corporate site typography */
export function TataSteelWordmark({ light = false }: { light?: boolean }) {
  const color = light ? "text-white" : "text-tata-blue";
  return (
    <div className={color}>
      <div className="flex items-baseline leading-none">
        <span className="text-[17px] font-black tracking-[0.14em]">TATA</span>
        <span className="ml-1 text-[17px] font-extralight tracking-[0.22em]">STEEL</span>
      </div>
      <p className="mt-1 text-[8px] font-normal tracking-[0.06em] opacity-75">#WeAlsoMakeTomorrow</p>
    </div>
  );
}

/** Circular TATA group emblem — top-right on corporate header */
export function TataEmblem({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" fill="none" className={className} aria-label="Tata">
      <circle cx="24" cy="24" r="22" stroke="currentColor" strokeWidth="1.5" />
      <text
        x="24"
        y="28"
        textAnchor="middle"
        fill="currentColor"
        style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em" }}
      >
        TATA
      </text>
    </svg>
  );
}

/** Centered section title with horizontal rules — Media page pattern */
export function TataSectionTitle({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center justify-center gap-5 py-10">
      <span className="h-px w-16 bg-tata-blue sm:w-24" />
      <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-tata-blue">{children}</h2>
      <span className="h-px w-16 bg-tata-blue sm:w-24" />
    </div>
  );
}
