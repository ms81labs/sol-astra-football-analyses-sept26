import { useEffect, useState } from 'react';

import { fetchLegacyGeometry } from '../utils/workbench';

export default function LegacyGeometryPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchLegacyGeometry()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.evaluation?.accepted === false
          && payload.evaluation.reasonCodes?.includes('CALIBRATION_UNAVAILABLE')
        ) {
          setNote('Stored legacy geometry keeps evaluation.accepted false. Four default corners do not invent calibration_accepted. CALIBRATION_UNAVAILABLE stays blocking.');
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
    <section aria-label="Stored legacy geometry" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored legacy geometry</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
