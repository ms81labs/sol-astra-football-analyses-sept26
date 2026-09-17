import { useEffect, useState } from 'react';

import { fetchDecodeChallengers } from '../utils/workbench';

export default function DecodeChallengersPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDecodeChallengers()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.pyav?.default === false
          && payload.torchcodec?.role === 'challenger'
          && payload.selected !== 'pyav'
        ) {
          setNote('Stored decode challengers keep pyav.default false. torchcodec stays a challenger. Production selected decode is not PyAV.');
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
    <section aria-label="Stored decode challengers" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored decode challengers</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
