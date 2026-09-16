import { useState } from 'react';

interface IncidentSample {
  time: number;
  attackerX: number;
  offsideLineX: number;
  indeterminate: boolean;
}

interface IncidentReviewProps {
  touchStart: number;
  touchEnd: number;
  samples: IncidentSample[];
}

export default function IncidentReview({ touchStart, touchEnd, samples }: IncidentReviewProps) {
  const [start, setStart] = useState(String(touchStart));
  const [end, setEnd] = useState(String(touchEnd));
  const indeterminate = samples.length === 0 || samples.some((sample) => sample.indeterminate);

  return (
    <section aria-label="Incident review" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-2">
      <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Incident review</h3>
      <p className="text-slate-400">Level 1 positional aid. Not a validated measurement.</p>
      <label className="block text-slate-400">
        Touch interval start
        <input
          type="number"
          step="0.01"
          value={start}
          onChange={(event) => setStart(event.target.value)}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-800 px-2 py-1 font-mono text-slate-200"
        />
      </label>
      <label className="block text-slate-400">
        Touch interval end
        <input
          type="number"
          step="0.01"
          value={end}
          onChange={(event) => setEnd(event.target.value)}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-800 px-2 py-1 font-mono text-slate-200"
        />
      </label>
      {samples.length === 0 && <p className="text-amber-200">Positional samples unavailable.</p>}
      {indeterminate && <p className="text-amber-200">Indeterminate across the chosen touch interval.</p>}
      <p>Video-language model confidence is not referee ground truth.</p>
      <p>Broadcast replays from different times are not simultaneous evidence.</p>
      <p>Elevated body parts through a ground-plane homography are not a precise offside line.</p>
      <p>An invisible player or ball cannot be repaired by a larger model.</p>
      <ul className="space-y-1 font-mono text-slate-500">
        {samples.map((sample) => (
          <li key={sample.time}>
            t={sample.time} attackerX={sample.attackerX} line={sample.offsideLineX}
          </li>
        ))}
      </ul>
    </section>
  );
}
