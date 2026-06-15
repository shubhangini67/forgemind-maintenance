"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { PageHeader } from "@/components/PageHeader";
import { EquipmentFleetTable } from "@/components/ui/EquipmentFleetTable";
import { api, getToken } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";

function resolveEquipmentId(fleet: any[], param: string | null) {
  if (!param || !fleet.length) return null;
  const byId = fleet.find((eq) => String(eq.id) === param);
  if (byId) return byId.id;
  const byCode = fleet.find((eq) => eq.equipment_code === param);
  return byCode?.id ?? null;
}

export default function EquipmentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const filterParam = searchParams.get("id") ?? searchParams.get("equipment");
  const [fleet, setFleet] = useState<any[]>([]);
  const [dataset, setDataset] = useState<any>(null);

  useEffect(() => {
    if (!getToken()) router.push("/");
    else
      api
        .plantTwin()
        .then((t) => {
          setFleet(t.cmapss_fleet || t.assets || []);
          setDataset(t.dataset);
        })
        .catch(() => {});
  }, [router]);

  const filterId = resolveEquipmentId(fleet, filterParam);
  const visibleFleet = useMemo(
    () => (filterId != null ? fleet.filter((eq) => eq.id === filterId) : fleet),
    [fleet, filterId]
  );
  const focused = filterId != null ? fleet.find((eq) => eq.id === filterId) : null;

  return (
    <Shell>
      <PageHeader
        label="Overview"
        title={focused ? focused.equipment_code : "Equipment"}
        subtitle={
          focused
            ? `${focused.name} — C-MAPSS FD001 unit U${focused.cmapss_unit ?? "—"}`
            : dataset?.description ||
              "Five steel plant assets — each mapped to one NASA C-MAPSS FD001 turbofan unit."
        }
        action={
          focused ? (
            <Link href="/equipment" className="btn-secondary text-sm">
              View full fleet
            </Link>
          ) : undefined
        }
      />

      {!fleet.length ? (
        <p className="text-sm text-tata-muted">Loading equipment…</p>
      ) : filterParam && !focused ? (
        <p className="text-sm text-tata-muted">Equipment not found.</p>
      ) : (
        <EquipmentFleetTable fleet={visibleFleet} />
      )}
    </Shell>
  );
}
