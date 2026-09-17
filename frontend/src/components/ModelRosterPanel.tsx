import { useEffect, useState } from 'react';

import { fetchModelRoster } from '../utils/workbench';

export default function ModelRosterPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchModelRoster()
      .then((payload) => {
        if (cancelled) return;
        const items = payload.items ?? [];
        if (items.length > 0 && items.every((item) => item.promoted === false)) {
          setNote('Stored model roster keeps every upgrade unpromoted. Leftover roster labels stay unused.');
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
    <section aria-label="Stored model roster" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored model roster</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
