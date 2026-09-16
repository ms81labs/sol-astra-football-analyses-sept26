import { useEffect, useState } from 'react';

import ModalDialog from './ModalDialog';
import {
  fetchPendingCorrections,
  fetchWorkbenchDossier,
  recoverMatchCorrection,
  searchWorkbenchEvents,
  type WorkbenchDossier,
} from '../utils/workbench';

interface WorkbenchPanelProps {
  onClose: () => void;
  matchId?: string;
  events?: Array<Record<string, unknown>>;
  onSeek?: (timestamp: number) => void;
}

const STATUS_LABEL: Record<string, string> = {
  usable: 'Usable',
  review_only: 'Review only',
  experimental: 'Experimental',
  unavailable: 'Unavailable',
  blocked: 'Blocked',
  unproven: 'Unproven',
};

export default function WorkbenchPanel({ onClose, matchId, events = [], onSeek }: WorkbenchPanelProps) {
  const [dossier, setDossier] = useState<WorkbenchDossier | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('show our second-half turnovers followed by a shot within 10 seconds');
  const [searchMessage, setSearchMessage] = useState<string | null>(null);
  const [pendingCorrection, setPendingCorrection] = useState<{ correctionId: string; kind: string; saveState: string } | null>(null);
  const [recoveryMessage, setRecoveryMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchWorkbenchDossier()
      .then((payload) => {
        if (!cancelled) setDossier(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load capability matrix');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchPendingCorrections(matchId)
      .then((payload) => {
        if (!cancelled) setPendingCorrection(payload.items[0] ?? null);
      })
      .catch(() => {
        if (!cancelled) setPendingCorrection(null);
      });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  async function runSearch() {
    if (!matchId) {
      setSearchMessage('Load a match before running typed search.');
      return;
    }
    const result = await searchWorkbenchEvents(query, matchId, events);
    if (result.query.unanswerable) {
      setSearchMessage(`Unanswerable: ${result.query.reason ?? 'unknown'}`);
      return;
    }
    if (result.results.length === 0) {
      setSearchMessage('No evidence-linked intervals matched.');
      return;
    }
    setSearchMessage(`${result.results.length} evidence-linked interval(s).`);
    onSeek?.(result.results[0].timestamp);
  }

  async function recoverPending() {
    if (!matchId || !pendingCorrection) return;
    const saved = await recoverMatchCorrection(matchId, pendingCorrection.correctionId);
    setPendingCorrection(null);
    setRecoveryMessage(saved.saveState);
  }

  return (
    <ModalDialog label="Capability matrix" onClose={onClose}>
      <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl w-full max-w-3xl mx-4 max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-slate-700 shrink-0">
          <h3 className="text-base font-semibold text-emerald-400">Evidence-led workbench</h3>
          <button type="button" onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200" aria-label="Close">
            Close
          </button>
        </div>
        <div className="overflow-y-auto p-4 space-y-4 text-sm">
          {error && <p className="text-amber-300">{error}</p>}
          {dossier && (
            <>
              <p className="text-slate-300">
                Camera profile <span className="font-mono text-emerald-300">{dossier.baseline.declaredCameraProfile}</span>
                {' '}· boundary {dossier.release.deploymentBoundary}
                {' '}· native {dossier.native.approved ? 'approved' : 'gated'}
              </p>
              <div className="rounded-lg border border-slate-700 p-3">
                <h4 className="text-xs uppercase tracking-wide text-slate-500 mb-2">Capability matrix</h4>
                <ul className="space-y-2">
                  {dossier.baseline.capabilities.map((capability) => (
                    <li key={capability.id} className="flex flex-col gap-0.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-slate-200">{capability.label}</span>
                        <span className="text-xs font-semibold text-amber-200">{STATUS_LABEL[capability.status] ?? capability.status}</span>
                      </div>
                      <span className="text-xs text-slate-500">{capability.notes}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-slate-700 p-3">
                <h4 className="text-xs uppercase tracking-wide text-slate-500 mb-2">Evidence classes</h4>
                <p className="text-xs text-slate-400">Independent accuracy: unproven. Independent labels {dossier.evaluation.completeTasks}/{dossier.evaluation.requiredTasks} complete.</p>
                <p className="text-xs text-slate-500 mt-1">Observation source and review status are separate. An inferred ball can be reviewed and still remain inferred.</p>
              </div>
              <div className="rounded-lg border border-slate-700 p-3 space-y-2">
                <h4 className="text-xs uppercase tracking-wide text-slate-500">Typed tactical search</h4>
                <label className="block text-xs text-slate-400">
                  Query
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => void runSearch()}
                  className="px-3 py-1.5 rounded bg-emerald-700 text-xs font-semibold text-white"
                >
                  Search evidence
                </button>
                {searchMessage && <p className="text-xs text-slate-300">{searchMessage}</p>}
              </div>
              {pendingCorrection && (
                <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 p-3 space-y-2">
                  <p className="text-xs text-amber-200">Pending playlist edit ({pendingCorrection.kind})</p>
                  <button
                    type="button"
                    onClick={() => void recoverPending()}
                    className="px-3 py-1.5 rounded bg-amber-700 text-xs font-semibold text-white"
                  >
                    Recover pending edit
                  </button>
                </div>
              )}
              {recoveryMessage && <p className="text-xs text-emerald-300">{recoveryMessage}</p>}
            </>
          )}
        </div>
      </div>
    </ModalDialog>
  );
}
