import { RiskBadge } from "./RiskBadge";
import { CmapssSensorBar } from "./CmapssSensorBar";
import { AlertTriangle, Clock, Target, Wrench } from "lucide-react";

export function AnalysisPanel({ data }: { data: any }) {
  if (!data) return null;

  const diag = data.diagnosis || {};
  const pred = data.prediction || {};
  const risk = data.risk_assessment || {};
  const plan = data.maintenance_plan || {};
  const proc = data.procurement || {};

  return (
    <div className="space-y-4">
      {data.sensor_snapshot?.temperature != null && (
        <CmapssSensorBar snapshot={data.sensor_snapshot} />
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-steel-100 bg-steel-50 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-steel-500">
            <AlertTriangle className="h-4 w-4" /> Risk
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <RiskBadge level={risk.risk_level || pred.risk_level} />
            {risk.urgency && (
              <span className="badge bg-accent-orange/10 text-accent-orange">Urgency: {risk.urgency}</span>
            )}
          </div>
        </div>
        <div className="rounded-xl border border-steel-100 bg-steel-50 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-steel-500">
            <Clock className="h-4 w-4" /> RUL Estimate
          </div>
          <p className="mt-2 text-xl font-bold">
            {pred.rul_hours != null ? `${Number(pred.rul_hours).toFixed(0)} hrs` : "—"}
          </p>
          {pred.failure_probability != null && (
            <p className="text-xs text-steel-500">
              Failure prob: {(pred.failure_probability * 100).toFixed(1)}%
            </p>
          )}
        </div>
        <div className="rounded-xl border border-steel-100 bg-steel-50 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-steel-500">
            <Target className="h-4 w-4" /> Confidence
          </div>
          <p className="mt-2 text-xl font-bold">
            {diag.confidence_score ? `${(diag.confidence_score * 100).toFixed(0)}%` : "—"}
          </p>
        </div>
      </div>

      {diag.probable_causes?.length > 0 && (
        <div>
          <p className="section-title mb-2">Probable Causes</p>
          <div className="space-y-2">
            {diag.probable_causes.map((c: any, i: number) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-steel-100 px-3 py-2 text-sm">
                <span>{c.cause}</span>
                <span className="font-mono text-steel-500">{((c.confidence || 0) * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {plan.immediate_actions?.length > 0 && (
        <div>
          <p className="section-title mb-2 flex items-center gap-1">
            <Wrench className="h-3 w-3" /> Immediate Actions
          </p>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-steel-700">
            {plan.immediate_actions.map((a: string, i: number) => (
              <li key={i}>{a}</li>
            ))}
          </ol>
        </div>
      )}

      {proc.recommendation && (
        <div className="rounded-xl border border-accent-orange/30 bg-accent-orange/5 p-3 text-sm">
          <p className="font-semibold text-accent-orange">Procurement</p>
          <p className="mt-1 text-steel-700">{proc.recommendation}</p>
        </div>
      )}

      {data.data_lineage?.length > 0 && (
        <div>
          <p className="section-title mb-2">Explainability / Data Lineage</p>
          <ul className="space-y-1 text-xs text-steel-500">
            {data.data_lineage.map((line: string, i: number) => (
              <li key={i}>• {line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
