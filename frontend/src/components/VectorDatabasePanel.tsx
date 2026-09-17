import { useEffect, useState } from 'react';

import { fetchVectorDatabase } from '../utils/workbench';

export default function VectorDatabasePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchVectorDatabase()
      .then((payload) => {
        if (cancelled) return;
        if (payload.admitted === false && payload.embeddingsProveTacticalWeakness === false) {
          setNote('Stored vector database stays unadmitted. Embeddings are not proof of tactical weakness.');
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
    <section aria-label="Stored vector database" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored vector database</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
