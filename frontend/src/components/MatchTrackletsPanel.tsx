import { useEffect, useState } from 'react';

import { fetchMatchTracklets } from '../utils/workbench';

interface MatchTrackletsPanelProps {
  matchId?: string;
}

export default function MatchTrackletsPanel({ matchId }: MatchTrackletsPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchTracklets(matchId)
      .then((payload) => {
        if (cancelled) return;
        const kind = payload.assignment?.kind;
        const silent = payload.chunk?.silentlyReconnected ?? payload.silentlyReconnected;
        if (kind === 'tracklet' && silent === false && payload.assignment?.forced === false) {
          setNote('Stored assignment kind is tracklet, not match identity. Tracklets are not silently reconnected.');
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
    <section aria-label="Tracklets" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Tracklets</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
