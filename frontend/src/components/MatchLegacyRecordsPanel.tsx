import { useEffect, useState } from 'react';

import { fetchMatchLegacyMigrate } from '../utils/workbench';

interface MatchLegacyRecordsPanelProps {
  matchId?: string;
}

export default function MatchLegacyRecordsPanel({ matchId }: MatchLegacyRecordsPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchLegacyMigrate(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.migrated?.possession_pct?.availability === 'unknown'
          && payload.rollback?.possession == null
          && payload.rewrotePastOutcomes === false
        ) {
          setNote('Legacy records migrate without inventing known possession. Rollback possession is null. rewrotePastOutcomes is false.');
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
    <section aria-label="Legacy records" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Legacy records</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
