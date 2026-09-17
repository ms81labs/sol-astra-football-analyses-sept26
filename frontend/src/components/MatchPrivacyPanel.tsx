import { useEffect, useState } from 'react';

import { fetchMatchPrivacy } from '../utils/workbench';

interface MatchPrivacyPanelProps {
  matchId?: string;
}

export default function MatchPrivacyPanel({ matchId }: MatchPrivacyPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchPrivacy(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.localProcessingRequired === true
          && payload.cloudAllowed === false
          && payload.faceRecognition === false
        ) {
          setNote('Local processing required. Cloud is not allowed. Face recognition is not enabled.');
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
    <section aria-label="Match privacy" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Match privacy</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
