import { useEffect, useState } from 'react';

import { postMatchLegacyMigrate } from '../utils/workbench';

interface MatchLegacyRecordsWritePanelProps {
  matchId?: string;
}

export default function MatchLegacyRecordsWritePanel({ matchId }: MatchLegacyRecordsWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchLegacyMigrate(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.migrated?.possession_pct?.availability === 'unknown'
          && payload.rollback?.possession == null
          && payload.rewrotePastOutcomes === false
        ) {
          setNote('Posted migrate ignores client knownPossessionInvented. Client possession is not sent. Rollback possession stays null.');
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
    <section aria-label="Uninvented possession write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Uninvented possession write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
