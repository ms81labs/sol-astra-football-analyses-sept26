import { useEffect, useState } from 'react';

import MetricInspector from './MetricInspector';
import ModalDialog from './ModalDialog';
import OperationsView from './OperationsView';
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
  fetchAssistance,
  fetchAnalystWorkflow,
  fetchCapacity,
  fetchCorrectionHistory,
  fetchExperiment,
  fetchGpuTiming,
  fetchIncidentReview,
  fetchJobCost,
  fetchJobView,
  fetchLabelProducts,
  fetchLandmarkPreview,
  fetchMatchClock,
  fetchMatchEdits,
  fetchMatchProxy,
  fetchMatchSetup,
  fetchMetricInspect,
  fetchNative,
  fetchNativeMemory,
  fetchObjectStorage,
  fetchPendingCorrections,
  fetchPitchAxes,
  fetchPlayerObservations,
  fetchPreemptible,
  fetchQualityTimeline,
  fetchRecovery,
  fetchRepository,
  fetchSecurity,
  fetchShadowMetric,
  fetchSupportBundle,
  fetchTrainingDrills,
  fetchTrainingPools,
  fetchWorkerEnvironment,
  fetchPerceptionScore,
  fetchPseudoLabel,
  fetchInterruptedUpload,
  fetchCalibrationHoldout,
  fetchEventScore,
  fetchDeploymentChoice,
  fetchEvaluationProtocol,
  fetchGpuDefaultFlag,
  fetchFourRates,
  fetchDecodeFrames,
  fetchChallengers,
  fetchHeatmap,
  fetchAssembleReport,
  fetchStalePermissions,
  fetchProviders,
  fetchRightsEvaluate,
  fetchTelestration,
  fetchReleaseDossier,
  fetchWorkbenchDossier,
  fetchWorkbenchFlags,
  recoverMatchCorrection,
  requestAccessDeletion,
  searchMatchLibrary,
  searchWorkbenchEvents,
  undoMatchCorrection,
  type AnalystWorkflowSnapshot,
  type CapacitySnapshot,
  type EditListSnapshot,
  type ExperimentReceiptSnapshot,
  type GpuTimingSnapshot,
  type LabelProductsSnapshot,
  type LandmarkPreview,
  type MatchSetup,
  type MetricInspect,
  type NativeMemorySnapshot,
  type NativeSnapshot,
  type ObjectStorageSnapshot,
  type PitchAxes,
  type PreemptibleSnapshot,
  type ProxyAssetsSnapshot,
  type QualityTimelinePayload,
  type RecoverySnapshot,
  type RepositorySnapshot,
  type SecuritySnapshot,
  type ShadowMetricSnapshot,
  type SupportBundleSnapshot,
  type TrainingPoolsSnapshot,
  type WorkerEnvironmentSnapshot,
  type PerceptionScoreSnapshot,
  type PseudoLabelSnapshot,
  type InterruptedUploadSnapshot,
  type CalibrationHoldoutSnapshot,
  type EventScoreSnapshot,
  type DeploymentChoiceSnapshot,
  type EvaluationProtocolSnapshot,
  type FeatureEnabledSnapshot,
  type FourRatesSnapshot,
  type DecodeFramesSnapshot,
  type ChallengerAdaptersSnapshot,
  type HeatmapSnapshot,
  type AssembleReportSnapshot,
  type StalePermissionsSnapshot,
  type ProviderRosterSnapshot,
  type RightsEvaluateSnapshot,
  type TelestrationSnapshot,
  type ReleaseDossierSnapshot,
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
  const [setup, setSetup] = useState<MatchSetup | null>(null);
  const [metricInspect, setMetricInspect] = useState<MetricInspect | null>(null);
  const [drills, setDrills] = useState<Array<{ name: string; coachReviewed?: boolean }>>([]);
  const [jobView, setJobView] = useState<{
    status?: string;
    durablePhase?: string | null;
    costReserved?: number;
    costActual?: number;
    cleanupResult?: string;
    cancelRequested?: boolean;
  } | null>(null);
  const [clock, setClock] = useState<{ presentationTimeSeconds: number; matchClockSeconds: number } | null>(null);
  const [incident, setIncident] = useState<{
    touchStart: number;
    touchEnd: number;
    samples: Array<{ time: number; attackerX: number; offsideLineX: number; indeterminate: boolean }>;
  } | null>(null);
  const [history, setHistory] = useState<Array<{ correctionId: string; kind: string; saveState: string; undoOf?: string | null }>>([]);
  const [recovery, setRecovery] = useState<RecoverySnapshot | null>(null);
  const [landmarkPreview, setLandmarkPreview] = useState<LandmarkPreview | null>(null);
  const [qualityItems, setQualityItems] = useState<QualityTimelinePayload['items']>([]);
  const [providersEnabled, setProvidersEnabled] = useState(false);
  const [security, setSecurity] = useState<SecuritySnapshot | null>(null);
  const [native, setNative] = useState<NativeSnapshot | null>(null);
  const [axes, setAxes] = useState<PitchAxes | null>(null);
  const [gpuTiming, setGpuTiming] = useState<GpuTimingSnapshot | null>(null);
  const [nativeMemory, setNativeMemory] = useState<NativeMemorySnapshot | null>(null);
  const [capacity, setCapacity] = useState<CapacitySnapshot | null>(null);
  const [repository, setRepository] = useState<RepositorySnapshot | null>(null);
  const [supportBundle, setSupportBundle] = useState<SupportBundleSnapshot | null>(null);
  const [objectStorage, setObjectStorage] = useState<ObjectStorageSnapshot | null>(null);
  const [experiment, setExperiment] = useState<ExperimentReceiptSnapshot | null>(null);
  const [preemptible, setPreemptible] = useState<PreemptibleSnapshot | null>(null);
  const [labelProducts, setLabelProducts] = useState<LabelProductsSnapshot | null>(null);
  const [proxyAssets, setProxyAssets] = useState<ProxyAssetsSnapshot | null>(null);
  const [editList, setEditList] = useState<EditListSnapshot | null>(null);
  const [workflow, setWorkflow] = useState<AnalystWorkflowSnapshot | null>(null);
  const [shadowMetric, setShadowMetric] = useState<ShadowMetricSnapshot | null>(null);
  const [trainingPools, setTrainingPools] = useState<TrainingPoolsSnapshot | null>(null);
  const [workerEnvironment, setWorkerEnvironment] = useState<WorkerEnvironmentSnapshot | null>(null);
  const [perceptionScore, setPerceptionScore] = useState<PerceptionScoreSnapshot | null>(null);
  const [pseudoLabel, setPseudoLabel] = useState<PseudoLabelSnapshot | null>(null);
  const [interruptedUpload, setInterruptedUpload] = useState<InterruptedUploadSnapshot | null>(null);
  const [calibrationHoldout, setCalibrationHoldout] = useState<CalibrationHoldoutSnapshot | null>(null);
  const [eventScore, setEventScore] = useState<EventScoreSnapshot | null>(null);
  const [deploymentChoice, setDeploymentChoice] = useState<DeploymentChoiceSnapshot | null>(null);
  const [evaluationProtocol, setEvaluationProtocol] = useState<EvaluationProtocolSnapshot | null>(null);
  const [gpuDefaultFlag, setGpuDefaultFlag] = useState<FeatureEnabledSnapshot | null>(null);
  const [fourRates, setFourRates] = useState<FourRatesSnapshot | null>(null);
  const [decodeFrames, setDecodeFrames] = useState<DecodeFramesSnapshot | null>(null);
  const [challengers, setChallengers] = useState<ChallengerAdaptersSnapshot | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapSnapshot | null>(null);
  const [assembleReport, setAssembleReport] = useState<AssembleReportSnapshot | null>(null);
  const [stalePermissions, setStalePermissions] = useState<StalePermissionsSnapshot | null>(null);
  const [providers, setProviders] = useState<ProviderRosterSnapshot | null>(null);
  const [rightsEvaluate, setRightsEvaluate] = useState<RightsEvaluateSnapshot | null>(null);
  const [telestration, setTelestration] = useState<TelestrationSnapshot | null>(null);
  const [releaseDossier, setReleaseDossier] = useState<ReleaseDossierSnapshot | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchWorkbenchDossier()
      .then((payload) => {
        if (!cancelled) setDossier(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load capability matrix');
      });
    fetchRecovery()
      .then((payload) => {
        if (!cancelled && payload.deletion) setRecovery(payload);
      })
      .catch(() => {
        if (!cancelled) setRecovery(null);
      });
    fetchAssistance()
      .then((payload) => {
        if (!cancelled) setProvidersEnabled(Boolean(payload.providersEnabled));
      })
      .catch(() => {
        if (!cancelled) setProvidersEnabled(false);
      });
    fetchSecurity()
      .then((payload) => {
        if (!cancelled && payload.modelOutput) setSecurity(payload);
      })
      .catch(() => {
        if (!cancelled) setSecurity(null);
      });
    fetchNative()
      .then((payload) => {
        if (!cancelled && typeof payload.approved === 'boolean') setNative(payload);
      })
      .catch(() => {
        if (!cancelled) setNative(null);
      });
    fetchPitchAxes()
      .then((payload) => {
        if (!cancelled && payload.x === 'longitudinal') setAxes(payload);
      })
      .catch(() => {
        if (!cancelled) setAxes(null);
      });
    fetchGpuTiming()
      .then((payload) => {
        if (!cancelled && payload.admitted === false) setGpuTiming(payload);
      })
      .catch(() => {
        if (!cancelled) setGpuTiming(null);
      });
    fetchNativeMemory()
      .then((payload) => {
        if (!cancelled && payload.completeRuntimeMemory === false) setNativeMemory(payload);
      })
      .catch(() => {
        if (!cancelled) setNativeMemory(null);
      });
    fetchCapacity()
      .then((payload) => {
        if (!cancelled && payload.billableCurrentSource === false) setCapacity(payload);
      })
      .catch(() => {
        if (!cancelled) setCapacity(null);
      });
    fetchRepository()
      .then((payload) => {
        if (!cancelled && payload.httpMayRunGpu === false) setRepository(payload);
      })
      .catch(() => {
        if (!cancelled) setRepository(null);
      });
    fetchSupportBundle()
      .then((payload) => {
        if (!cancelled && payload.released === false) setSupportBundle(payload);
      })
      .catch(() => {
        if (!cancelled) setSupportBundle(null);
      });
    fetchObjectStorage()
      .then((payload) => {
        if (!cancelled && payload.enabled === false) setObjectStorage(payload);
      })
      .catch(() => {
        if (!cancelled) setObjectStorage(null);
      });
    fetchExperiment('B2')
      .then((payload) => {
        if (!cancelled && payload.promoted === false) setExperiment(payload);
      })
      .catch(() => {
        if (!cancelled) setExperiment(null);
      });
    fetchPreemptible()
      .then((payload) => {
        if (!cancelled && payload.allowed === false) setPreemptible(payload);
      })
      .catch(() => {
        if (!cancelled) setPreemptible(null);
      });
    fetchLabelProducts()
      .then((payload) => {
        if (!cancelled && payload.cvat?.sameProductAsCorrections === false) setLabelProducts(payload);
      })
      .catch(() => {
        if (!cancelled) setLabelProducts(null);
      });
    fetchAnalystWorkflow()
      .then((payload) => {
        if (!cancelled && payload.measured === false) setWorkflow(payload);
      })
      .catch(() => {
        if (!cancelled) setWorkflow(null);
      });
    fetchShadowMetric('experimental_shot_quality')
      .then((payload) => {
        if (!cancelled && payload.shadowed === true) setShadowMetric(payload);
      })
      .catch(() => {
        if (!cancelled) setShadowMetric(null);
      });
    fetchTrainingPools()
      .then((payload) => {
        if (!cancelled && payload.pools?.includes('locked_evaluation')) setTrainingPools(payload);
      })
      .catch(() => {
        if (!cancelled) setTrainingPools(null);
      });
    fetchWorkerEnvironment()
      .then((payload) => {
        if (!cancelled && payload.NAMESPACE === 'production') setWorkerEnvironment(payload);
      })
      .catch(() => {
        if (!cancelled) setWorkerEnvironment(null);
      });
    fetchPerceptionScore()
      .then((payload) => {
        if (!cancelled && payload.labelsIndependent === false) setPerceptionScore(payload);
      })
      .catch(() => {
        if (!cancelled) setPerceptionScore(null);
      });
    fetchPseudoLabel()
      .then((payload) => {
        if (!cancelled && payload.independentGroundTruth === false) setPseudoLabel(payload);
      })
      .catch(() => {
        if (!cancelled) setPseudoLabel(null);
      });
    fetchInterruptedUpload()
      .then((payload) => {
        if (!cancelled && payload.accepted === false) setInterruptedUpload(payload);
      })
      .catch(() => {
        if (!cancelled) setInterruptedUpload(null);
      });
    fetchCalibrationHoldout()
      .then((payload) => {
        if (!cancelled && payload.accepted === false) setCalibrationHoldout(payload);
      })
      .catch(() => {
        if (!cancelled) setCalibrationHoldout(null);
      });
    fetchEventScore()
      .then((payload) => {
        if (!cancelled && payload.labelsIndependent === false) setEventScore(payload);
      })
      .catch(() => {
        if (!cancelled) setEventScore(null);
      });
    fetchDeploymentChoice()
      .then((payload) => {
        if (!cancelled && payload.alwaysOnGpuCommitted === false) setDeploymentChoice(payload);
      })
      .catch(() => {
        if (!cancelled) setDeploymentChoice(null);
      });
    fetchEvaluationProtocol()
      .then((payload) => {
        if (!cancelled && payload.accepted === false) setEvaluationProtocol(payload);
      })
      .catch(() => {
        if (!cancelled) setEvaluationProtocol(null);
      });
    fetchGpuDefaultFlag()
      .then((payload) => {
        if (!cancelled && payload.enabled === false) setGpuDefaultFlag(payload);
      })
      .catch(() => {
        if (!cancelled) setGpuDefaultFlag(null);
      });
    fetchFourRates()
      .then((payload) => {
        if (!cancelled && payload.exportFpsEqualsInferenceFps === false) setFourRates(payload);
      })
      .catch(() => {
        if (!cancelled) setFourRates(null);
      });
    fetchDecodeFrames()
      .then((payload) => {
        if (!cancelled && payload.backend === 'fixture' && payload.pyavDefault === false) setDecodeFrames(payload);
      })
      .catch(() => {
        if (!cancelled) setDecodeFrames(null);
      });
    fetchChallengers()
      .then((payload) => {
        if (!cancelled && payload.kloppy?.enabled === false) setChallengers(payload);
      })
      .catch(() => {
        if (!cancelled) setChallengers(null);
      });
    fetchHeatmap()
      .then((payload) => {
        if (!cancelled && payload.withheld === true) setHeatmap(payload);
      })
      .catch(() => {
        if (!cancelled) setHeatmap(null);
      });
    fetchAssembleReport()
      .then((payload) => {
        if (!cancelled && payload.factualCheck?.accepted === false) setAssembleReport(payload);
      })
      .catch(() => {
        if (!cancelled) setAssembleReport(null);
      });
    fetchStalePermissions()
      .then((payload) => {
        if (!cancelled && payload.admitted === false) setStalePermissions(payload);
      })
      .catch(() => {
        if (!cancelled) setStalePermissions(null);
      });
    fetchProviders()
      .then((payload) => {
        if (!cancelled && payload.roster?.default === 'disabled') setProviders(payload);
      })
      .catch(() => {
        if (!cancelled) setProviders(null);
      });
    fetchRightsEvaluate()
      .then((payload) => {
        if (!cancelled && payload.allowed === false) setRightsEvaluate(payload);
      })
      .catch(() => {
        if (!cancelled) setRightsEvaluate(null);
      });
    fetchTelestration()
      .then((payload) => {
        if (!cancelled && payload.blenderEnabled === false) setTelestration(payload);
      })
      .catch(() => {
        if (!cancelled) setTelestration(null);
      });
    fetchReleaseDossier()
      .then((payload) => {
        if (!cancelled && payload.deploymentBoundary === 'loopback') setReleaseDossier(payload);
      })
      .catch(() => {
        if (!cancelled) setReleaseDossier(null);
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
    fetchCorrectionHistory(matchId)
      .then((payload) => {
        if (!cancelled && Array.isArray(payload.items)) setHistory(payload.items);
      })
      .catch(() => {
        if (!cancelled) setHistory([]);
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
    fetchJobView(jobId)
      .then((payload) => {
        if (!cancelled && (typeof payload.status === 'string' || typeof payload.durablePhase === 'string')) {
          setJobView(payload);
        }
      })
      .catch(() => {
        if (!cancelled) setJobView(null);
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
    fetchMatchSetup(matchId)
      .then((payload) => {
        if (!cancelled && typeof payload.cameraProfile === 'string') setSetup(payload);
      })
      .catch(() => {
        if (!cancelled) setSetup(null);
      });
    fetchMatchProxy(matchId)
      .then((payload) => {
        if (!cancelled && payload.replacesOriginal === false) setProxyAssets(payload);
      })
      .catch(() => {
        if (!cancelled) setProxyAssets(null);
      });
    fetchMatchEdits(matchId)
      .then((payload) => {
        if (!cancelled && payload.reencodeFullMatch === false) setEditList(payload);
      })
      .catch(() => {
        if (!cancelled) setEditList(null);
      });
    fetchMetricInspect('my_team_distance_m', matchId)
      .then((payload) => {
        if (!cancelled && payload.metric) setMetricInspect(payload);
      })
      .catch(() => {
        if (!cancelled) setMetricInspect(null);
      });
    fetchMatchClock(matchId)
      .then((payload) => {
        if (!cancelled && typeof payload.presentationTimeSeconds === 'number') setClock(payload);
      })
      .catch(() => {
        if (!cancelled) setClock(null);
      });
    fetchIncidentReview(matchId)
      .then((payload) => {
        if (!cancelled && payload.decision == null && Array.isArray(payload.samples)) {
          const interval = payload.touchInterval;
          setIncident({
            touchStart: interval?.[0] ?? payload.samples[0]?.time ?? 0,
            touchEnd: interval?.[1] ?? payload.samples[payload.samples.length - 1]?.time ?? 0.12,
            samples: payload.samples,
          });
        }
      })
      .catch(() => {
        if (!cancelled) setIncident(null);
      });
    fetchLandmarkPreview(matchId)
      .then((payload) => {
        if (!cancelled && payload.committed === false) setLandmarkPreview(payload);
      })
      .catch(() => {
        if (!cancelled) {
          setLandmarkPreview({
            residualP95M: null,
            accepted: false,
            committed: false,
            measured: false,
          });
        }
      });
    fetchQualityTimeline(matchId)
      .then((payload) => {
        if (!cancelled && Array.isArray(payload.items)) setQualityItems(payload.items);
      })
      .catch(() => {
        if (!cancelled) setQualityItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  useEffect(() => {
    let cancelled = false;
    fetchTrainingDrills()
      .then((payload) => {
        if (!cancelled && Array.isArray(payload.items)) setDrills(payload.items);
      })
      .catch(() => {
        if (!cancelled) setDrills([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
    try {
      const historyPayload = await fetchCorrectionHistory(matchId);
      if (Array.isArray(historyPayload.items)) setHistory(historyPayload.items);
    } catch {
      /* fail-closed: keep local history */
    }
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
    const result = await searchMatchLibrary(libraryQuery);
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
                controllerRecorded={Boolean(recovery?.deletion.available)}
                unresolvedIncidents={recovery?.unresolvedIncidents.items ?? []}
                recoveryObjectivesDefined={Boolean(recovery?.recoveryObjectives.defined)}
                onRequestDeletion={() => {
                  void requestAccessDeletion().catch(() => undefined);
                }}
              />
              <SecurityBoundary
                modelTrusted={security?.modelOutput?.trusted}
                hostedEncryptionProven={security?.encryption?.hostedEncryptionProven}
                signedJobAccessAdmitted={security?.signedJobAccess?.admitted}
              />
              <ReleaseGate publicExposureAllowed={security?.publicExposure?.publicExposureAllowed} />
              <NativePackaging
                approved={native?.approved}
                rpcFleetEnabled={native?.rpcFleet?.enabled}
                universallyPortable={native?.pinned?.universallyPortable}
                completeRuntimeMemory={nativeMemory?.completeRuntimeMemory}
              />
              {axes && (
                <p className="text-xs text-slate-400">Pitch x is {axes.x}; y is {axes.y}. Legacy display must transform explicitly.</p>
              )}
              {gpuTiming?.admitted === false && (
                <p className="text-xs text-slate-400">GPU timing uses completed work, not submission.</p>
              )}
              {capacity?.billableCurrentSource === false && (
                <p className="text-xs text-slate-400">Historical two-half duration is not current billable capacity.</p>
              )}
              {repository?.httpMayRunGpu === false && (
                <p className="text-xs text-slate-400">HTTP control plane may not run GPU work.</p>
              )}
              {supportBundle?.released === false && (
                <p className="text-xs text-slate-400">Support bundle requires consent.</p>
              )}
              {objectStorage?.enabled === false && (
                <p className="text-xs text-slate-400">Hosted object storage is unadmitted. DuckDB is not mandatory.</p>
              )}
              {experiment?.promoted === false && (
                <p className="text-xs text-slate-400">Hardware experiment receipts stay unpromoted.</p>
              )}
              {preemptible?.allowed === false && (
                <p className="text-xs text-slate-400">Preemptible workers are not allowed without checkpoints.</p>
              )}
              {labelProducts?.cvat?.sameProductAsCorrections === false && (
                <p className="text-xs text-slate-400">Independent labels are not the same product as in-app corrections.</p>
              )}
              {proxyAssets?.replacesOriginal === false && (
                <p className="text-xs text-slate-400">Derived proxies retain the original source.</p>
              )}
              {editList?.reencodeFullMatch === false && (
                <p className="text-xs text-slate-400">Edit lists render on demand instead of re-encoding the match.</p>
              )}
              {workflow?.measured === false && (
                <p className="text-xs text-slate-400">Analyst workflow measures remain unmeasured.</p>
              )}
              {shadowMetric?.shadowed === true && (
                <p className="text-xs text-slate-400">Experimental shot quality stays shadowed off defaults.</p>
              )}
              {trainingPools?.pools?.includes('locked_evaluation') && (
                <p className="text-xs text-slate-400">Locked evaluation labels cannot enter training.</p>
              )}
              {workerEnvironment?.NAMESPACE === 'production' && (
                <p className="text-xs text-slate-400">Host credentials stay out of the worker environment.</p>
              )}
              {perceptionScore?.labelsIndependent === false && (
                <p className="text-xs text-slate-400">Independent labels remain incomplete for perception scoring.</p>
              )}
              {pseudoLabel?.independentGroundTruth === false && (
                <p className="text-xs text-slate-400">Pseudo-labels are not independent ground truth.</p>
              )}
              {interruptedUpload?.accepted === false && (
                <p className="text-xs text-slate-400">Interrupted uploads are quarantined, not accepted.</p>
              )}
              {calibrationHoldout?.accepted === false && (
                <p className="text-xs text-slate-400">Calibration holdout labels remain unavailable.</p>
              )}
              {eventScore?.labelsIndependent === false && (
                <p className="text-xs text-slate-400">Event scoring does not treat labels as independent.</p>
              )}
              {deploymentChoice?.alwaysOnGpuCommitted === false && (
                <p className="text-xs text-slate-400">Deployment does not commit always-on GPU.</p>
              )}
              {evaluationProtocol?.accepted === false && (
                <p className="text-xs text-slate-400">Frozen evaluation protocol remains incomplete.</p>
              )}
              {gpuDefaultFlag?.enabled === false && (
                <p className="text-xs text-slate-400">GPU default flag stays off.</p>
              )}
              {fourRates?.exportFpsEqualsInferenceFps === false && (
                <p className="text-xs text-slate-400">Export fps is not inference fps.</p>
              )}
              {decodeFrames?.backend === 'fixture' && decodeFrames.pyavDefault === false && (
                <p className="text-xs text-slate-400">Production decode stays on the fixture FrameSource; PyAV and TorchCodec stay challengers.</p>
              )}
              {challengers?.kloppy?.enabled === false && (
                <p className="text-xs text-slate-400">Kloppy, Roboflow, and MCBYTE stay unadmitted challengers.</p>
              )}
              {heatmap?.withheld === true && (
                <p className="text-xs text-slate-400">Heatmaps stay interval-limited without identity continuity.</p>
              )}
              {assembleReport?.factualCheck?.accepted === false && (
                <p className="text-xs text-slate-400">Report assembly rejects fabricated evidence.</p>
              )}
              {stalePermissions?.admitted === false && (
                <p className="text-xs text-slate-400">Stale permissions are not admitted.</p>
              )}
              {providers?.roster?.default === 'disabled' && (
                <p className="text-xs text-slate-400">Language providers stay disabled by default.</p>
              )}
              {rightsEvaluate?.allowed === false && (
                <p className="text-xs text-slate-400">Uncertain commercial permission blocks the use.</p>
              )}
              {telestration?.blenderEnabled === false && (
                <p className="text-xs text-slate-400">Telestration stays 2D before 3D.</p>
              )}
              {releaseDossier?.nativeCode === 'gated_inert' && (
                <p className="text-xs text-slate-400">Release dossier keeps native code gated and loopback-only.</p>
              )}
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
                  phase={jobView?.durablePhase ?? jobView?.status ?? 'submitted'}
                  estimatedCost={jobCost?.reservedTotal ?? jobView?.costReserved ?? 0}
                  actualCost={jobView?.costActual ?? 0}
                  retries={0}
                  cleanupResult={jobView?.cleanupResult ?? 'unknown'}
                  cancelRequested={Boolean(jobView?.cancelRequested)}
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
                cameraProfile={setup?.cameraProfile ?? dossier.baseline.declaredCameraProfile}
                pitchLengthM={setup?.pitchLengthM != null ? String(setup.pitchLengthM) : ''}
                automationAdmitted={setup?.automationAdmitted ?? false}
                manualTaggingPermitted={setup?.manualTaggingPermitted ?? true}
                cannotMeasure={setup?.cannotMeasure ?? ['physical_metrics']}
                landmarkPreview={
                  landmarkPreview ?? {
                    residualP95M: null,
                    accepted: false,
                    committed: false,
                    measured: false,
                  }
                }
              />
              <ClockReadout
                presentationTimeSeconds={clock?.presentationTimeSeconds ?? 0}
                matchClockSeconds={clock?.matchClockSeconds ?? 0}
              />
              <AiUnavailableBanner providersEnabled={providersEnabled} />
              <ChangeHistory
                items={history}
                onUndo={(correctionId) => {
                  if (!matchId) return;
                  void undoMatchCorrection(matchId, correctionId).then((saved) => {
                    setHistory((previous) => [
                      ...previous,
                      {
                        correctionId: saved.correctionId,
                        kind: 'undo',
                        saveState: 'saved',
                        undoOf: saved.undoOf,
                      },
                    ]);
                  });
                }}
              />
              <IncidentReview
                touchStart={incident?.touchStart ?? 0}
                touchEnd={incident?.touchEnd ?? 0.12}
                samples={
                  incident?.samples ?? [
                    { time: 0, attackerX: 0, offsideLineX: 0, indeterminate: true },
                    { time: 0.12, attackerX: 0, offsideLineX: 0, indeterminate: true },
                  ]
                }
              />
              {flags?.experimental_ui ? (
                <QualityTimeline items={qualityItems} />
              ) : null}
              <TrainingSuggestions
                observations={[{ id: 'o1', label: 'near-side recovery' }]}
                drills={drills.length ? drills : [{ name: 'near-side recovery 2v2', coachReviewed: true }]}
              />
              <MetricInspector
                metric={metricInspect?.metric ?? 'my_team_distance_m'}
                unit={metricInspect?.unit ?? 'metres'}
                denominator={metricInspect?.denominator ?? 'identity_continuous_eligible_seconds'}
                definitionVersion={metricInspect?.definitionVersion ?? '1'}
                eligibleDuration={metricInspect?.eligibleDuration ?? 0}
                exclusions={metricInspect?.exclusions ?? ['IDENTITY_DISCONTINUITY']}
                value={metricInspect?.publishedValue ?? null}
                availability={metricInspect?.rendered === 'unavailable' ? 'unknown' : 'available'}
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
