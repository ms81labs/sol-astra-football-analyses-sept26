interface QualityItem {
  id: string;
  label: string;
  impact: string;
}

const IMPACT_RANK: Record<string, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

interface QualityTimelineProps {
  items: QualityItem[];
}

export default function QualityTimeline({ items }: QualityTimelineProps) {
  const ordered = [...items].sort(
    (left, right) => (IMPACT_RANK[left.impact] ?? 9) - (IMPACT_RANK[right.impact] ?? 9),
  );
  return (
    <section aria-label="Quality timeline" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-2">
      <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Quality timeline</h3>
      <p className="text-amber-200">Review first. High-impact uncertainty is not accepted.</p>
      <ul className="space-y-1">
        {ordered.map((item) => (
          <li
            key={item.id}
            aria-label={item.impact === 'high' ? 'high-impact uncertainty' : `${item.impact} uncertainty`}
            className={
              item.impact === 'high'
                ? 'flex items-center justify-between gap-2 rounded bg-amber-900/40 px-1.5 py-0.5'
                : 'flex items-center justify-between gap-2'
            }
          >
            <span>{item.label}</span>
            <span className="font-mono text-slate-500">{item.impact}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
