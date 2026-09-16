interface MetricInspectorProps {
  metric: string;
  unit: string;
  denominator: string;
  definitionVersion: string;
  eligibleDuration: number;
  exclusions: string[];
  value: number | null;
  availability: string;
}

export default function MetricInspector({
  metric,
  unit,
  denominator,
  definitionVersion,
  eligibleDuration,
  exclusions,
  value,
  availability,
}: MetricInspectorProps) {
  const unknown = availability !== 'available' || value === null;
  return (
    <section aria-label="Metric inspector" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-1">
      <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Metric inspector</h3>
      <p>Metric: <span className="font-mono text-emerald-300">{metric}</span></p>
      <p>Unit: <span className="font-mono">{unit}</span></p>
      <p>Denominator: <span className="font-mono">{denominator}</span></p>
      <p>Definition v{definitionVersion}</p>
      <p>Eligible duration: <span className="font-mono">{eligibleDuration}s</span></p>
      {exclusions.length > 0 && <p>Exclusions: {exclusions.join(', ')}</p>}
      <p>Value: <span className="font-semibold text-amber-200">{unknown ? 'Unavailable' : value}</span></p>
    </section>
  );
}
