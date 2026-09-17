import { useEffect, useState } from 'react';

import { postMatchEventPartition } from '../utils/workbench';

interface MatchEventPartitionWritePanelProps {
  matchId?: string;
}

export default function MatchEventPartitionWritePanel({ matchId }: MatchEventPartitionWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchEventPartition(matchId)
      .then((payload) => {
        if (cancelled) return;
        const blob = JSON.stringify(payload);
        if (payload.rejectedRemovedFromAcceptedViews === true && !blob.includes('forged-accepted')) {
          setNote('Posted event partition ignores client events. Client forged-accepted is not sent. rejectedRemovedFromAcceptedViews stays true.');
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
    <section aria-label="Uninjected candidate write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Uninjected candidate write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
