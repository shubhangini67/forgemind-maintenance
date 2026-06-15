import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowRight, Brain } from "lucide-react";

type Action = {
  href: string;
  label: string;
  desc: string;
  icon: LucideIcon;
};

export function AiLaunchStrip({
  primaryHref = "/chat",
  actions,
}: {
  primaryHref?: string;
  actions: Action[];
}) {
  return (
    <div className="panel-flush mb-8 overflow-hidden">
      <div className="grid lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Link
          href={primaryHref}
          className="group relative flex min-h-[148px] flex-col justify-between overflow-hidden bg-gradient-to-br from-tata-blue via-[#0068b8] to-tata-blue-light p-6 text-white transition hover:brightness-[1.03] sm:p-7"
        >
          <div className="pointer-events-none absolute -right-10 -top-12 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
          <div className="pointer-events-none absolute bottom-0 left-0 h-24 w-full bg-gradient-to-t from-black/10 to-transparent" />

          <div className="relative flex items-start gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/15 shadow-lg ring-1 ring-white/25 backdrop-blur-sm transition group-hover:scale-105">
              <Brain className="h-7 w-7" strokeWidth={1.5} />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/65">Agentic AI</p>
              <h3 className="mt-1 text-xl font-semibold tracking-tight sm:text-[1.35rem]">Ask ForgeMind</h3>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-white/85">
                Diagnose faults, estimate RUL, find SOPs, and plan maintenance — with live sensor context.
              </p>
            </div>
          </div>

          <span className="relative mt-5 inline-flex w-fit items-center gap-2 rounded-lg bg-white/15 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider ring-1 ring-white/20 transition group-hover:bg-white/25">
            Start conversation
            <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
          </span>
        </Link>

        <div className="grid divide-y divide-tata-border/70 sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-1 lg:divide-x-0 lg:divide-y">
          {actions.map(({ href, label, desc, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="group flex items-start gap-3 bg-gradient-to-br from-white to-tata-blue-pale/45 p-5 transition hover:from-tata-blue-pale/30 hover:to-tata-blue-pale/70"
            >
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-tata-blue/10 text-tata-blue ring-1 ring-tata-blue/10 transition group-hover:bg-tata-blue group-hover:text-white">
                <Icon className="h-5 w-5" strokeWidth={1.5} />
              </div>
              <div className="min-w-0">
                <p className="font-semibold text-tata-ink group-hover:text-tata-blue">{label}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-tata-muted">{desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
