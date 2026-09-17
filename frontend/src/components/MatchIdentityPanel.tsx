import { useEffect, useState } from 'react';

import { fetchMatchIdentity } from '../utils/workbench';

interface MatchIdentityPanelProps {
  matchId?: string;
}

export default function MatchIdentityPanel({ matchId }: MatchIdentityPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchIdentity(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.identityContinuous === false
          && payload.silentlyReconnected === false
          && (payload.cutCount === 0 || payload.reset === false)
        ) {
          setNote('No camera cuts do not make identity continuous. Stored identityContinuous is false. Tracks are not silently reconnected.');
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
  }, [matchId]);

  if (!note) return null;
  return (
    <section aria-label="Stored identity" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored identity</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
