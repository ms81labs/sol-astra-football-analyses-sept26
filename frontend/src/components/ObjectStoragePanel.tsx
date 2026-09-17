import { useEffect, useState } from 'react';

import { fetchObjectStorage } from '../utils/workbench';

export default function ObjectStoragePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchObjectStorage()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.enabled === false
          && payload.mandatoryDuckDb === false
          && payload.role === 'local_content_addressed'
        ) {
          setNote('Stored object storage stays local content-addressed. Hosted admission stays off. Mandatory DuckDB stays false.');
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
    <section aria-label="Stored object storage" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored object storage</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
