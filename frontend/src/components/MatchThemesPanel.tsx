import { useEffect, useState } from 'react';

import { fetchMatchThemes } from '../utils/workbench';

interface MatchThemesPanelProps {
  matchId?: string;
}

export default function MatchThemesPanel({ matchId }: MatchThemesPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchThemes(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (Array.isArray(payload.detectedThemes)) {
          setNote('Stored tactical themes are heuristic search tags. Detected themes do not prove tactical weakness.');
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
    <section aria-label="Tactical themes" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Tactical themes</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
