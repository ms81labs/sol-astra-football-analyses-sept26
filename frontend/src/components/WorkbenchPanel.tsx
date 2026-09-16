import { useEffect, useState } from 'react';

import MetricInspector from './MetricInspector';
import ModalDialog from './ModalDialog';
import OperationsView from './OperationsView';
import PlaylistBuilder from './PlaylistBuilder';
import ClockReadout from './ClockReadout';
import IncidentReview from './IncidentReview';
import ChangeHistory from './ChangeHistory';
import AiUnavailableBanner from './AiUnavailableBanner';
import LoopbackBanner from './LoopbackBanner';
import RecoveryPanel from './RecoveryPanel';
import SecurityBoundary from './SecurityBoundary';
import ReleaseGate from './ReleaseGate';
import NativePackaging from './NativePackaging';
import QualityTimeline from './QualityTimeline';
import SetupWizard from './SetupWizard';
import TrainingSuggestions from './TrainingSuggestions';
import {
  exportPlaylistInterval,
  fetchJobCost,
  fetchPendingCorrections,
  fetchPlayerObservations,
  fetchWorkbenchDossier,
  fetchWorkbenchFlags,
  recoverMatchCorrection,
  searchMatchLibrary,
  searchWorkbenchEvents,
  type WorkbenchDossier,
} from '../utils/workbench';

interface WorkbenchPanelProps {
  onClose: () => void;
  matchId?: string;
  jobId?: string;
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

export default function WorkbenchPanel({ onClose, matchId, jobId, events = [], onSeek }: WorkbenchPanelProps) {
  const [dossier, setDossier] = useState<WorkbenchDossier | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('show our second-half turnovers followed by a shot within 10 seconds');
  const [searchMessage, setSearchMessage] = useState<string | null>(null);
  const [pendingCorrection, setPendingCorrection] = useState<{ correctionId: string; kind: string; saveState: string } | null>(null);
  const [recoveryMessage, setRecoveryMessage] = useState<string | null>(null);
  const [playlistStart, setPlaylistStart] = useState('3');
  const [playlistEnd, setPlaylistEnd] = useState('5');
  const [playlistMessage, setPlaylistMessage] = useState<string | null>(null);
  const [flags, setFlags] = useState<{
    experimental_shot_quality?: boolean;
    experimental_ui?: boolean;
    embeddings_search?: boolean;
  } | null>(null);
  const [jobCost, setJobCost] = useState<{ reservedTotal: number } | null>(null);
  const [libraryQuery, setLibraryQuery] = useState('');
  const [libraryHits, setLibraryHits] = useState<Array<{ id: string; title?: string }>>([]);
  const [playersLimited, setPlayersLimited] = useState(false);

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

  useEffect(() => {
    let cancelled = false;
    fetchWorkbenchFlags()
      .then((payload) => {
        if (!cancelled) {
          setFlags(payload);
        }
      })
      .catch(() => {
        if (!cancelled) setFlags(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    fetchJobCost(jobId)
      .then((payload) => {
        if (!cancelled && typeof payload.reservedTotal === 'number') {
          setJobCost(payload);
        }
      })
      .catch(() => {
        if (!cancelled) setJobCost(null);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchPlayerObservations(matchId)
      .then((payload) => {
        if (!cancelled) setPlayersLimited(Boolean(payload.intervalLimited));
      })
      .catch(() => {
        if (!cancelled) setPlayersLimited(false);
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

  async function exportPlaylist() {
    const start = Number(playlistStart);
    const end = Number(playlistEnd);
    if (!Number.isFinite(start) || !Number.isFinite(end)) {
      setPlaylistMessage('Enter a numeric source interval.');
      return;
    }
    const interval = await exportPlaylistInterval(start, end, 25);
    setPlaylistMessage(`Source interval ${interval.sourceStartSeconds}s to ${interval.sourceEndSeconds}s (frame ${interval.sourceEndFrameExclusive} exclusive).`);
    onSeek?.(interval.sourceStartSeconds);
  }

  async function runLibrarySearch() {
    const result = await searchMatchLibrary(libraryQuery, [
      { id: 'm-lib', title: 'elevated training', cameraProfile: 'stable_elevated_wide' },
    ]);
    setLibraryHits(result.results);
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
              <LoopbackBanner deploymentBoundary={dossier.release.deploymentBoundary} />
              <RecoveryPanel
                controllerRecorded={false}
                unresolvedIncidents={[]}
                recoveryObjectivesDefined={false}
              />
              <SecurityBoundary />
              <ReleaseGate />
              <NativePackaging />
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
              <div className="rounded-lg border border-slate-700 p-3 space-y-2">
                <OperationsView
                  phase="running"
                  estimatedCost={jobCost?.reservedTotal ?? 0}
                  actualCost={0}
                  retries={0}
                  cleanupResult="unknown"
                />
                {flags && flags.experimental_shot_quality === false && (
                  <p className="text-xs text-slate-400">experimental shot quality: shadowed</p>
                )}
                {flags && flags.experimental_ui === false && (
                  <p className="text-xs text-slate-400">experimental UI: shadowed</p>
                )}
                {flags && flags.embeddings_search === false && (
                  <p className="text-xs text-slate-400">embeddings search: shadowed</p>
                )}
                {jobCost && <p className="text-xs text-slate-300">Live job cost reserved {jobCost.reservedTotal}</p>}
              </div>
              <div className="rounded-lg border border-slate-700 p-3 space-y-2">
                <h4 className="text-xs uppercase tracking-wide text-slate-500">Match library</h4>
                <label className="block text-xs text-slate-400">
                  Match library
                  <input
                    value={libraryQuery}
                    onChange={(event) => setLibraryQuery(event.target.value)}
                    className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
                  />
                </label>
                <button type="button" onClick={() => void runLibrarySearch()} className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white">
                  Search library
                </button>
                {libraryHits.map((hit) => (
                  <p key={hit.id} className="text-xs text-slate-300">{hit.title ?? hit.id}</p>
                ))}
                {playersLimited && <p className="text-xs text-amber-200">Interval-limited player observations. Totals withheld.</p>}
              </div>
              <SetupWizard
                cameraProfile={dossier.baseline.declaredCameraProfile}
                automationAdmitted={false}
                manualTaggingPermitted
                cannotMeasure={['physical_metrics']}
                landmarkPreview={{ residualP95M: 4.2, accepted: false, committed: false }}
              />
              <ClockReadout presentationTimeSeconds={0} matchClockSeconds={0} />
              <AiUnavailableBanner providersEnabled={false} />
              <ChangeHistory
                items={
                  pendingCorrection
                    ? [{ correctionId: pendingCorrection.correctionId, kind: pendingCorrection.kind, saveState: pendingCorrection.saveState }]
                    : []
                }
              />
              <IncidentReview
                touchStart={0}
                touchEnd={0.12}
                samples={[
                  { time: 0, attackerX: 0, offsideLineX: 0, indeterminate: true },
                  { time: 0.12, attackerX: 0, offsideLineX: 0, indeterminate: true },
                ]}
              />
              {flags?.experimental_ui ? (
                <QualityTimeline
                  items={[
                    { id: 'possession', label: 'ambiguous possession around a shot', impact: 'high' },
                    { id: 'team', label: 'incorrect team selection', impact: 'high' },
                    { id: 'far', label: 'far-side miss', impact: 'medium' },
                  ]}
                />
              ) : null}
              <TrainingSuggestions
                observations={[{ id: 'o1', label: 'near-side recovery' }]}
                drills={[{ name: 'near-side recovery 2v2', coachReviewed: true }]}
              />
              <MetricInspector
                metric="my_team_distance_m"
                unit="metres"
                denominator="identity_continuous_eligible_seconds"
                definitionVersion="1"
                eligibleDuration={0}
                exclusions={['IDENTITY_DISCONTINUITY']}
                value={null}
                availability="unknown"
              />
              <div className="rounded-lg border border-slate-700 p-3 space-y-2">
                <h4 className="text-xs uppercase tracking-wide text-slate-500">Playlist source interval</h4>
                <label className="block text-xs text-slate-400">
                  Start seconds
                  <input value={playlistStart} onChange={(event) => setPlaylistStart(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
                </label>
                <label className="block text-xs text-slate-400">
                  End seconds
                  <input value={playlistEnd} onChange={(event) => setPlaylistEnd(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
                </label>
                <button type="button" onClick={() => void exportPlaylist()} className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white">
                  Export source interval
                </button>
                {playlistMessage && <p className="text-xs text-slate-300">{playlistMessage}</p>}
              </div>
            </>
          )}
        </div>
      </div>
    </ModalDialog>
  );
}
