import type { ReactNode } from "react";

export function PageHeader({
  title,
  subtitle,
  action,
  label,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  label?: string;
}) {
  return (
    <header className="page-header">
      <div className="surface overflow-hidden">
        <div className="h-1 bg-gradient-to-r from-tata-blue via-tata-blue-light to-tata-menu" />
        <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-5 sm:px-6 sm:py-6">
          <div className="min-w-0 flex-1">
            {label && (
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-tata-blue">{label}</p>
            )}
            <h1 className="text-2xl font-semibold tracking-tight text-tata-ink sm:text-[1.75rem]">{title}</h1>
            {subtitle && (
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-tata-muted">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex shrink-0 flex-wrap items-center gap-3">{action}</div>}
        </div>
      </div>
    </header>
  );
}
