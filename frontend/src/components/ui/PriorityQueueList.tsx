import Link from "next/link";
import { Activity, ArrowRight } from "lucide-react";

type PriorityItem = {
  equipment_id: number;
  equipment_code: string;
  recommended_action?: string;
};

export function PriorityQueueList({ items }: { items: PriorityItem[] }) {
  return (
    <div className="panel-flush flex h-full flex-col overflow-hidden">
      <div className="border-b border-tata-border/80 bg-gradient-to-r from-tata-blue-pale/60 to-white px-5 py-3.5">
        <h2 className="text-sm font-semibold text-tata-ink">Needs Attention</h2>
        <p className="text-xs text-tata-muted">Top maintenance priorities</p>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-50 to-white ring-1 ring-emerald-200/60">
            <Activity className="h-7 w-7 text-emerald-600" />
          </div>
          <p className="mt-4 text-sm font-semibold text-tata-ink">All systems stable</p>
          <p className="mt-1 text-xs text-tata-muted">No urgent maintenance actions</p>
        </div>
      ) : (
        <ol className="flex-1 space-y-3 p-4">
          {items.map((p, i) => (
            <li key={p.equipment_id}>
              <Link
                href={`/priority?equipment=${p.equipment_id}`}
                className="surface surface-hover group flex gap-3 p-4"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-tata-blue to-tata-blue-light text-xs font-bold text-white shadow-sm">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-tata-ink group-hover:text-tata-blue">{p.equipment_code}</p>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-tata-muted">
                    {p.recommended_action}
                  </p>
                </div>
                <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-tata-muted transition group-hover:text-tata-blue" />
              </Link>
            </li>
          ))}
        </ol>
      )}

      <div className="border-t border-tata-border/60 bg-gradient-to-r from-white to-tata-blue-pale/30 px-5 py-3">
        <Link
          href="/priority"
          className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-tata-blue hover:underline"
        >
          Full priority list <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}
