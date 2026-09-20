import { useState } from 'react';

import { searchWorkbenchEvents } from '../utils/workbench';

interface TypedSearchPanelProps {
  matchId?: string;
  generationId?: string;
  onSeek?: (timestamp: number) => void;
}

export default function TypedSearchPanel({ matchId, onSeek, generationId }: TypedSearchPanelProps) {
  const [query, setQuery] = useState('');
  const [message, setMessage] = useState<string | null>(null);

  async function runSearch() {
    if (!matchId) return;
    try {
      const result = await searchWorkbenchEvents(query, matchId, [], generationId);
      if (result.query.unanswerable) {
        setMessage(`Unanswerable: ${result.query.reason ?? 'unknown'}`);
        return;
      }
      if (result.results.length === 0) {
        setMessage('No evidence-linked intervals matched.');
        return;
      }
      setMessage(`${result.results.length} evidence-linked interval${result.results.length === 1 ? '' : 's'}.`);
      onSeek?.(result.results[0].timestamp);
    } catch (error) {
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
    </section>
  );
}
