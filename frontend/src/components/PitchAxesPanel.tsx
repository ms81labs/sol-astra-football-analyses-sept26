import { useEffect, useState } from 'react';

import { fetchPitchAxes } from '../utils/workbench';

export default function PitchAxesPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPitchAxes()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.x === 'longitudinal'
          && payload.y === 'lateral'
          && payload.origin === 'declared_calibration'
          && payload.legacyDisplay === 'transform_explicitly'
        ) {
          setNote('Stored pitch axes keep x longitudinal and y lateral. Declared calibration is the origin. Legacy display stays an explicit transform.');
        } else {
          setNote(null);
        }
      })
      .catch(() => {
        if (!cancelled) setNote(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!note) return null;
  return (
    <section aria-label="Stored pitch axes" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored pitch axes</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
