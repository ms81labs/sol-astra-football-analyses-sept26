import { useEffect, useState } from 'react';

import { fetchRepository } from '../utils/workbench';

export default function RepositoryPolicyPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRepository()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.httpMayRunGpu === false
          && payload.vectorBrokerRequired === false
          && payload.replacesStorageModule === false
        ) {
          setNote('Stored repository policy keeps HTTP off GPU work. Vector broker is not required. Storage module stays unreplaced.');
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
    <section aria-label="Stored repository policy" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored repository policy</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
