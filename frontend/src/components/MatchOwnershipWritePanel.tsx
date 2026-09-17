import { useEffect, useState } from 'react';

import { postMatchOwnership } from '../utils/workbench';

interface MatchOwnershipWritePanelProps {
  matchId?: string;
}

export default function MatchOwnershipWritePanel({ matchId }: MatchOwnershipWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchOwnership(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (payload.mode === 'unknown' && reasons.includes('NEAREST_PLAYER_INSUFFICIENT')) {
          setNote('Posted ownership ignores client nearestTeam, calibrated, and ballVisible. Mode stays unknown. NEAREST_PLAYER_INSUFFICIENT remains.');
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
    <section aria-label="Posted nearest-player write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Posted nearest-player write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
