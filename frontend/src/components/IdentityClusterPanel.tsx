import { useEffect, useState } from 'react';

import { fetchIdentityCluster } from '../utils/workbench';

export default function IdentityClusterPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchIdentityCluster()
      .then((payload) => {
        if (cancelled) return;
        if (payload.suggestion === true && payload.semanticTeam == null) {
          setNote('Stored identity cluster GET keeps suggestion true. GET selectedSemantic is not sent. Cluster GET stays unlabeled.');
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
    <section aria-label="Stored identity cluster" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored identity cluster</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
