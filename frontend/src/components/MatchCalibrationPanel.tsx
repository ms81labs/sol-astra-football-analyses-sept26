import { useEffect, useState } from 'react';

import { fetchMatchCalibration } from '../utils/workbench';

interface MatchCalibrationPanelProps {
  matchId?: string;
}

export default function MatchCalibrationPanel({ matchId }: MatchCalibrationPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchCalibration(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.fromStoredPoints === true
          && payload.measured === false
          && payload.evaluation?.accepted !== true
        ) {
          setNote('Four homography points do not make calibration accepted. Stored GET calibration is unmeasured. fromStoredPoints is true.');
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
    <section aria-label="Stored calibration" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored calibration</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
