import { useEffect, useState } from 'react';

import { fetchIdentityPolicy } from '../utils/workbench';

export default function IdentityPolicyPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchIdentityPolicy()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.faceRecognition?.enabled === false
          && payload.crossSeasonIdentity?.enabled === false
          && payload.appearance?.everyDetection === false
        ) {
          setNote('Stored identity policy keeps face recognition off. Cross-season identity stays off. Appearance embeddings stay off every detection.');
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
    <section aria-label="Stored identity policy" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored identity policy</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
