import { useEffect, useState } from 'react';

import { postMatchTracklets } from '../utils/workbench';

interface MatchTrackletWritePanelProps {
  matchId?: string;
}

export default function MatchTrackletWritePanel({ matchId }: MatchTrackletWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchTracklets(matchId)
      .then((payload) => {
        if (cancelled) return;
        const silent = payload.chunk?.silentlyReconnected ?? payload.silentlyReconnected;
        if (payload.assignment?.forced === false && silent === false) {
          setNote('Posted tracklet writes do not force a roster identity. Client rosterId and reviewed flags are not sent. silentlyReconnected stays false.');
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
    <section aria-label="Unforced roster write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced roster write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
