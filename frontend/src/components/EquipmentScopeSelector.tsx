"use client";

import { ChevronDown, Factory, Globe2, Info } from "lucide-react";

type Equipment = { id: number; equipment_code: string; name: string };

type Props = {
  equipment: Equipment[];
  equipmentId?: number;
  onChange: (id: number | undefined) => void;
  className?: string;
  compact?: boolean;
};

export function EquipmentScopeSelector({
  equipment,
  equipmentId,
  onChange,
  className = "",
  compact = false,
}: Props) {
  const isPlantMode = !equipmentId;
  const selected = equipment.find((e) => e.id === equipmentId);

  if (compact) {
    return (
      <div className={`flex items-center gap-1.5 ${className}`}>
        <div className="flex items-center gap-0.5 rounded-lg bg-slate-100/90 p-0.5 ring-1 ring-tata-border/60">
          <button
            type="button"
            onClick={() => onChange(undefined)}
            className={`flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-semibold transition ${
              isPlantMode ? "bg-white text-tata-blue shadow-sm" : "text-tata-muted hover:text-tata-ink"
            }`}
          >
            <Globe2 className="h-3 w-3" />
            Plant
          </button>
          <button
            type="button"
            onClick={() => {
              if (!equipmentId && equipment[0]) onChange(equipment[0].id);
            }}
            className={`flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-semibold transition ${
              !isPlantMode ? "bg-white text-tata-blue shadow-sm" : "text-tata-muted hover:text-tata-ink"
            }`}
          >
            <Factory className="h-3 w-3" />
            Asset
          </button>
        </div>
        {!isPlantMode && (
          <div className="relative min-w-0 flex-1">
            <select
              className="input w-full appearance-none py-1.5 pl-2 pr-7 text-[11px] font-medium"
              value={equipmentId ?? ""}
              onChange={(e) => onChange(Number(e.target.value))}
            >
              {equipment.map((eq) => (
                <option key={eq.id} value={eq.id}>
                  {eq.equipment_code} — {eq.name}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-tata-muted" />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center gap-1 rounded-xl bg-slate-100/90 p-1 ring-1 ring-tata-border/60">
        <button
          type="button"
          onClick={() => onChange(undefined)}
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition ${
            isPlantMode
              ? "bg-white text-tata-blue shadow-sm ring-1 ring-tata-blue/20"
              : "text-tata-muted hover:text-tata-ink"
          }`}
        >
          <Globe2 className="h-3.5 w-3.5" />
          Plant mode
        </button>
        <button
          type="button"
          onClick={() => {
            if (!equipmentId && equipment[0]) onChange(equipment[0].id);
          }}
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition ${
            !isPlantMode
              ? "bg-white text-tata-blue shadow-sm ring-1 ring-tata-blue/20"
              : "text-tata-muted hover:text-tata-ink"
          }`}
        >
          <Factory className="h-3.5 w-3.5" />
          Asset mode
        </button>
      </div>

      {!isPlantMode && (
        <div className="relative">
          <select
            className="input w-full appearance-none py-2 pl-3 pr-8 text-xs font-medium"
            value={equipmentId ?? ""}
            onChange={(e) => onChange(Number(e.target.value))}
          >
            {equipment.map((eq) => (
              <option key={eq.id} value={eq.id}>
                {eq.equipment_code} — {eq.name}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-tata-muted" />
        </div>
      )}

      <div
        className={`flex gap-2 rounded-lg px-3 py-2 text-[11px] leading-snug ${
          isPlantMode ? "bg-sky-50 text-sky-900 ring-1 ring-sky-100" : "bg-amber-50 text-amber-950 ring-1 ring-amber-100"
        }`}
      >
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-70" />
        <p>
          {isPlantMode ? (
            <>
              <strong>Plant mode</strong> — chat about the whole site, open pages, fleet ranking. No single pump selected.
            </>
          ) : (
            <>
              <strong>Asset mode — {selected?.equipment_code}</strong> — agents use live sensors, RUL, root cause &amp; actions for this unit only.
            </>
          )}
        </p>
      </div>
    </div>
  );
}
