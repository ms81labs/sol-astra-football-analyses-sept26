import { useEffect, useState } from 'react';

import { fetchMatchExport, type MatchExportBundle } from '../utils/workbench';

interface MatchExportPanelProps {
  matchId?: string;
}

export default function MatchExportPanel({ matchId }: MatchExportPanelProps) {
  const [bundle, setBundle] = useState<MatchExportBundle | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchExport(matchId)
      .then((payload) => {
        if (!cancelled) setBundle(payload);
      })
      .catch(() => {
        if (!cancelled) setBundle(null);
      });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  const exports = bundle?.exports;
  const ready = bundle?.schemaVersion === 'match_bundle_v1'
    && Boolean(exports?.framesCsv && exports.eventsCsv && exports.metricsCsv && exports.matchJson);
  if (!ready || !exports) return null;

  return (
    <section aria-label="Match export" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Match export</h4>
      <p className="text-xs text-slate-400">
        Stored match export is match_bundle_v1. Frames, events, metrics and match.json are source-linked downloads. This is not a whole-match certification.
      </p>
      <div className="flex flex-wrap gap-2 text-xs">
        <a className="text-emerald-400 underline" href={exports.framesCsv}>frames.csv</a>
        <a className="text-emerald-400 underline" href={exports.eventsCsv}>events.csv</a>
        <a className="text-emerald-400 underline" href={exports.metricsCsv}>metrics.csv</a>
        <a className="text-emerald-400 underline" href={exports.matchJson}>match.json</a>
      </div>
    </section>
  );
}
