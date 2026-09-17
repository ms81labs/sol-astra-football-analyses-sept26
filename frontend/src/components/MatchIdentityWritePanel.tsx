import { useEffect, useState } from 'react';

import { postMatchIdentity } from '../utils/workbench';

interface MatchIdentityWritePanelProps {
  matchId?: string;
}

export default function MatchIdentityWritePanel({ matchId }: MatchIdentityWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchIdentity(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.identityContinuous === false && payload.silentlyReconnected === false) {
          setNote('Posted identity ignores client identityContinuous true. identityContinuous stays false. silentlyReconnected stays false.');
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
    <section aria-label="Posted continuity denial" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Posted continuity denial</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
