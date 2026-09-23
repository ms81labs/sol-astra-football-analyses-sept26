import { useLayoutEffect, useRef, useState } from 'react';

import { searchWorkbenchEvents, type SearchHit } from '../utils/workbench';

interface TypedSearchPanelProps {
  matchId?: string;
  generationId?: string;
  onSeek?: (timestamp: number) => void;
  onSelectHit?: (hit: SearchHit) => void;
}

export default function TypedSearchPanel({ matchId, onSeek, onSelectHit, generationId }: TypedSearchPanelProps) {
  const scopeVersion = useRef(0);
  useLayoutEffect(() => { scopeVersion.current += 1; return () => { scopeVersion.current += 1; }; }, [matchId, generationId]);
  const [query, setQuery] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [results, setResults] = useState<SearchHit[]>([]);

  async function runSearch() {
    if (!matchId) return;
    const operation = scopeVersion.current;
    setResults([]);
    try {
      const result = await searchWorkbenchEvents(query, matchId, [], generationId);
      if (operation !== scopeVersion.current) return;
      if (result.query.unanswerable) {
        setMessage(`Unanswerable: ${result.query.reason ?? 'unknown'}`);
        return;
      }
      if (result.results.length === 0) {
        setMessage('No evidence-linked intervals matched.');
        return;
      }
      setMessage(`${result.results.length} evidence-linked interval${result.results.length === 1 ? '' : 's'}.`);
      setResults(result.results);
    } catch (error) {
      if (operation !== scopeVersion.current) return;
      setMessage(error instanceof Error ? error.message : 'Failed to run typed search');
    }
  }

  return (
    <section aria-label="Typed search" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Typed tactical search</h4>
      <p className="text-xs text-slate-500">Queries stored match events. Arbitrary SQL or code is refused.</p>
      <label className="block text-xs text-slate-400">
        Query
        <input value={query} onChange={(event) => setQuery(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <button
        type="button"
        onClick={() => void runSearch()}
        disabled={!matchId}
        className="px-3 py-1.5 rounded bg-emerald-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Search evidence
      </button>
      {message && <p className="text-xs text-slate-300">{message}</p>}
      {results.length > 0 && <ul className="space-y-1">{results.map((hit) => (
        <li key={hit.eventId}>
          <button type="button" className="text-left text-xs text-emerald-300 hover:underline"
            onClick={() => { onSelectHit?.(hit); onSeek?.(hit.intervalStart ?? hit.timestamp); }}>
            {hit.label ?? 'event'} · {hit.intervalStart ?? hit.timestamp}s to {hit.intervalEnd ?? hit.timestamp}s · {hit.reviewStatus ?? 'unreviewed'} · {hit.evidenceIds.length} evidence reference{hit.evidenceIds.length === 1 ? '' : 's'}
          </button>
        </li>
      ))}</ul>}
    </section>
  );
}
