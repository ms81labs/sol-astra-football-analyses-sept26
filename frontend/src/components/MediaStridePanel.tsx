import { useEffect, useState } from 'react';

import { fetchMediaStride } from '../utils/workbench';

export default function MediaStridePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMediaStride()
      .then((payload) => {
        if (cancelled) return;
        if (payload.addsVidStrideAlone === false && payload.targetFpsEqualsInferenceFps === false) {
          setNote('Stored media stride does not add vid_stride alone. Target fps is not inference fps.');
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
    <section aria-label="Stored media stride" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored media stride</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
