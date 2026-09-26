import { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { fetchQueryProposalAvailability, requestQueryProposal, searchWorkbenchEvents,
  type SearchHit, type TypedSearchFilter } from '../utils/workbench';

const EVENT_TYPES = ['pass', 'progressive_pass', 'through_ball', 'cross', 'shot', 'goal', 'turnover',
  'recovery', 'tackle', 'interception', 'carry', 'box_entry', 'final_third_entry'];

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
  const [filterEvent, setFilterEvent] = useState('pass');
  const [filterTeam, setFilterTeam] = useState('');
  const [filterRegion, setFilterRegion] = useState('');
  const [filterReview, setFilterReview] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [results, setResults] = useState<SearchHit[]>([]);
  const [filterText, setFilterText] = useState<string | null>(null);
  const [resultScope, setResultScope] = useState<string | null>(null);
  const [modelAvailability, setModelAvailability] = useState<{ scope: string; available: boolean } | null>(null);
  const modelRequest = useRef<{ scope: string; question: string; id: string } | null>(null);
  const currentScope = JSON.stringify([matchId, generationId]);
  const showResult = resultScope === currentScope;
  useEffect(() => {
    if (!matchId || !generationId) return;
    let current = true;
    void fetchQueryProposalAvailability(matchId, generationId)
      .then((available) => { if (current) setModelAvailability({ scope: currentScope, available }); })
      .catch(() => { if (current) setModelAvailability({ scope: currentScope, available: false }); });
    return () => { current = false; };
  }, [matchId, generationId, currentScope]);

  async function runSearch(request: string | TypedSearchFilter, useModel = false) {
    if (!matchId) return;
    const operation = scopeVersion.current;
    setResultScope(currentScope);
    setResults([]);
    setFilterText(null);
    setMessage(null);
    try {
      let result;
      if (useModel && typeof request === 'string' && generationId) {
        const question = request.trim();
        if (!modelRequest.current || modelRequest.current.scope !== currentScope || modelRequest.current.question !== question) {
          modelRequest.current = { scope: currentScope, question,
            id: crypto.randomUUID?.() ?? Array.from(crypto.getRandomValues(new Uint8Array(16)),
              (byte) => byte.toString(16).padStart(2, '0')).join('') };
        }
        result = await requestQueryProposal(matchId, generationId, question, modelRequest.current.id);
      } else {
        result = await searchWorkbenchEvents(request, matchId, [], generationId);
      }
      if (operation !== scopeVersion.current) return;
      if (result.query.unanswerable) {
        setMessage(result.query.reason === 'unsupported_terms' && result.query.unsupportedTerms?.length
          ? `Unsupported terms: ${result.query.unsupportedTerms.join(', ')}. Refine the query.`
          : `Unanswerable: ${result.query.reason ?? 'unknown'}`);
        return;
      }
      const filter = result.query.interpreted;
      if (filter) {
        const parts = [filter.eventFamily,
          filter.team === 'my_team' ? 'our team' : filter.team === 'enemy' ? 'opponent' : null,
          filter.playerTrackId != null ? `player ${filter.playerTrackId}` : null,
          filter.reviewStatus,
          filter.pitchRegion?.replace('_', ' '),
          filter.period != null ? `period ${filter.period}` : null,
          filter.timeStartSeconds != null || filter.timeEndSeconds != null
            ? `${filter.timeStartSeconds ?? 'start'}–${filter.timeEndSeconds ?? 'end'}s` : null];
        setFilterText(parts.filter(Boolean).join(' · ') || null);
      }
      if (result.results.length === 0) {
        setMessage(result.coverageState === 'insufficient'
          ? result.unknownLocationCount
            ? `${result.unknownLocationCount} matching event${result.unknownLocationCount === 1 ? '' : 's'} ${result.unknownLocationCount === 1 ? 'has' : 'have'} no verified location.`
            : 'Event coverage unavailable for this match.'
          : 'No evidence-linked intervals matched.');
        return;
      }
      setMessage(`${result.results.length} evidence-linked interval${result.results.length === 1 ? '' : 's'}.` +
        (result.coverageState === 'partial' && result.unknownLocationCount
          ? ` ${result.unknownLocationCount} matching event${result.unknownLocationCount === 1 ? '' : 's'} ${result.unknownLocationCount === 1 ? 'has' : 'have'} no verified location.` : ''));
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
        onClick={() => void runSearch(query)}
        disabled={!matchId}
        className="px-3 py-1.5 rounded bg-emerald-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Search evidence
      </button>
      {modelAvailability?.scope === currentScope && modelAvailability.available && <button type="button"
        disabled={!query.trim() || !generationId || query.trim().length > 512}
        onClick={() => void runSearch(query, true)}
        className="ml-2 px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50">
        Ask model to search
      </button>}
      <div className="grid grid-cols-2 gap-2 text-xs text-slate-400">
        <label>Event type
          <select value={filterEvent} onChange={(event) => setFilterEvent(event.target.value)} className="block w-full rounded border border-slate-600 bg-slate-900 p-1 text-slate-200">
            {EVENT_TYPES.map((type) => <option key={type} value={type}>{type.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
        <label>Team filter
          <select value={filterTeam} onChange={(event) => setFilterTeam(event.target.value)} className="block w-full rounded border border-slate-600 bg-slate-900 p-1 text-slate-200">
            <option value="">Any team</option><option value="my_team">Our team</option><option value="enemy">Opponent</option>
          </select>
        </label>
        <label>Pitch third
          <select value={filterRegion} onChange={(event) => setFilterRegion(event.target.value)} className="block w-full rounded border border-slate-600 bg-slate-900 p-1 text-slate-200">
            <option value="">Any</option><option value="left_third">Left</option><option value="middle_third">Middle</option><option value="right_third">Right</option>
          </select>
        </label>
        <label>Review status
          <select value={filterReview} onChange={(event) => setFilterReview(event.target.value)} className="block w-full rounded border border-slate-600 bg-slate-900 p-1 text-slate-200">
            <option value="">Any</option><option value="accepted">Accepted</option><option value="unreviewed">Unreviewed</option>
          </select>
        </label>
      </div>
      <button type="button" disabled={!matchId || !generationId}
        onClick={() => void runSearch({ eventFamily: filterEvent,
          ...(filterTeam ? { team: filterTeam } : {}),
          ...(filterRegion ? { pitchRegion: filterRegion } : {}),
          ...(filterReview ? { reviewStatus: filterReview } : {}) })}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50">
        Apply filters
      </button>
      {showResult && message && <p className="text-xs text-slate-300">{message}</p>}
      {showResult && filterText && <p aria-label="Interpreted filter" className="text-xs text-slate-400">{filterText}</p>}
      {showResult && results.length > 0 && <ul className="space-y-1">{results.map((hit) => (
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
