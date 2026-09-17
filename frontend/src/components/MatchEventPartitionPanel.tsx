import { useEffect, useState } from 'react';

import { fetchMatchEventPartition } from '../utils/workbench';

interface MatchEventPartitionPanelProps {
  matchId?: string;
}

export default function MatchEventPartitionPanel({ matchId }: MatchEventPartitionPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchEventPartition(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.rejectedRemovedFromAcceptedViews === true) {
          setNote('Stored event partition removes rejected candidates from accepted views. rejectedRemovedFromAcceptedViews is true.');
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
    <section aria-label="Event partition" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Event partition</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
