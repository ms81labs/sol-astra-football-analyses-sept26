import { useEffect, useState } from 'react';

import { fetchVideoRoster } from '../utils/workbench';

export default function VideoRosterPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchVideoRoster()
      .then((payload) => {
        if (cancelled) return;
        if (payload.qwen3_5_4b?.promoted === false) {
          setNote('Stored video roster keeps qwen3_5_4b unpromoted. Video models stay off the production path.');
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
    <section aria-label="Stored video roster" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored video roster</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
