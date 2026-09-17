import { useEffect, useState } from 'react';

import { postMatchShotQuality } from '../utils/workbench';

interface MatchShotQualityWritePanelProps {
  matchId?: string;
}

export default function MatchShotQualityWritePanel({ matchId }: MatchShotQualityWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchShotQuality(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.publishedLabel === 'experimental_shot_quality' && payload.calibratedXg === false) {
          setNote('Posted shot quality ignores client shots and goal. Client calibratedXg is not sent. publishedLabel stays experimental_shot_quality.');
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
    <section aria-label="Unpublished xG write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unpublished xG write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
