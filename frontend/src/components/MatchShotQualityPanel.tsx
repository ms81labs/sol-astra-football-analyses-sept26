import { useEffect, useState } from 'react';

import { fetchMatchShotQuality } from '../utils/workbench';

interface MatchShotQualityPanelProps {
  matchId?: string;
}

export default function MatchShotQualityPanel({ matchId }: MatchShotQualityPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchShotQuality(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = (payload.items ?? []).flatMap((item) => item.reasonCodes ?? []);
        if (
          payload.publishedLabel === 'experimental_shot_quality'
          && payload.calibratedXg === false
          && reasons.includes('EXPERIMENTAL_NOT_CALIBRATED_XG')
        ) {
          setNote('Stored shot quality is experimental_shot_quality and is not calibrated xG. EXPERIMENTAL_NOT_CALIBRATED_XG.');
        } else if (
          payload.publishedLabel === 'experimental_shot_quality'
          && payload.calibratedXg === false
        ) {
          setNote('Stored shot quality is experimental_shot_quality and is not calibrated xG.');
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
    <section aria-label="Shot quality" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Shot quality</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
