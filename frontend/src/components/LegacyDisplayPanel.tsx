import { useEffect, useState } from 'react';

import { fetchLegacyDisplay } from '../utils/workbench';

export default function LegacyDisplayPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchLegacyDisplay()
      .then((payload) => {
        if (cancelled) return;
        if (payload.transformedExplicitly === true && payload.legacyDisplay === 'transform_explicitly') {
          setNote('Stored legacy display transform stays explicit. Display coordinates are not pitch metres until transformed.');
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
    <section aria-label="Stored legacy display" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored legacy display</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
