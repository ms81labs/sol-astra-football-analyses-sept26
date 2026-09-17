/* eslint-disable react-refresh/only-export-components */
import ModalDialog from './components/ModalDialog';
import { useState, useEffect, useCallback, useLayoutEffect, useMemo, useRef } from 'react';


import AnnotationList from './components/AnnotationList';
import DrawingToolbar from './components/DrawingToolbar';
import ReviewToolbar from './components/ReviewToolbar';
import TacticalPitch from './components/TacticalPitch';
import CoachInsights from './components/CoachInsights';
import DashboardPanel from './components/DashboardPanel';
import EvidenceInspector from './components/EvidenceInspector';
import IncidentReview from './components/IncidentReview';
import ChangeHistory from './components/ChangeHistory';
import AiUnavailableBanner from './components/AiUnavailableBanner';
import LoopbackBanner from './components/LoopbackBanner';
import RecoveryPanel from './components/RecoveryPanel';
import SecurityBoundary from './components/SecurityBoundary';
import ReleaseGate from './components/ReleaseGate';
import NativePackaging from './components/NativePackaging';
import QualityTimeline from './components/QualityTimeline';
import WorkbenchPanel from './components/WorkbenchPanel';
import DemoMatchIssuePanel from './components/DemoMatchIssuePanel';
import MatchVideoPanel from './components/MatchVideoPanel';
import PlaylistBuilder from './components/PlaylistBuilder';
import MatchPackagePanel from './components/MatchPackagePanel';
import FourRatesPanel from './components/FourRatesPanel';
import LoadedMatchSetupPanel from './components/LoadedMatchSetupPanel';
import MatchMetricInspectorPanel from './components/MatchMetricInspectorPanel';
import MatchCoveragePanel from './components/MatchCoveragePanel';
import AnalystWorkflowPanel from './components/AnalystWorkflowPanel';
import EvaluationProtocolPanel from './components/EvaluationProtocolPanel';
import EvaluationPrerequisitesPanel from './components/EvaluationPrerequisitesPanel';
import EvaluationMeasuresPanel from './components/EvaluationMeasuresPanel';
import EvaluationHotaPanel from './components/EvaluationHotaPanel';
import CollaborationLockPanel from './components/CollaborationLockPanel';
import MediaStridePanel from './components/MediaStridePanel';
import CreditAllocationPanel from './components/CreditAllocationPanel';
import HeldOutQuestionsPanel from './components/HeldOutQuestionsPanel';
import GroundContactPanel from './components/GroundContactPanel';
import XtPlanPanel from './components/XtPlanPanel';
import RightsRegisterPanel from './components/RightsRegisterPanel';
import ModelRosterPanel from './components/ModelRosterPanel';
import RiskRegisterPanel from './components/RiskRegisterPanel';
import MilestoneProgressPanel from './components/MilestoneProgressPanel';
import NetworkFailureMetricPanel from './components/NetworkFailureMetricPanel';
import MetadataTargetsPanel from './components/MetadataTargetsPanel';
import ArchitectureDecisionsPanel from './components/ArchitectureDecisionsPanel';
import ResidencyClaimPanel from './components/ResidencyClaimPanel';
import DistributedBrokerPanel from './components/DistributedBrokerPanel';
import VectorDatabasePanel from './components/VectorDatabasePanel';
import HostedDeploymentPanel from './components/HostedDeploymentPanel';
import HandheldAdmissionPanel from './components/HandheldAdmissionPanel';
import ResearchLanePanel from './components/ResearchLanePanel';
import ScaleScenarioPanel from './components/ScaleScenarioPanel';
import MediaAdmitWritePanel from './components/MediaAdmitWritePanel';
import CostEstimateWritePanel from './components/CostEstimateWritePanel';
import RollbackWritePanel from './components/RollbackWritePanel';
import TrainingDrillsPanel from './components/TrainingDrillsPanel';
import RepositoryPolicyPanel from './components/RepositoryPolicyPanel';
import SupportBundlePanel from './components/SupportBundlePanel';
import ObjectStoragePanel from './components/ObjectStoragePanel';
import PreemptiblePolicyPanel from './components/PreemptiblePolicyPanel';
import PitchAxesPanel from './components/PitchAxesPanel';
import GpuTimingPanel from './components/GpuTimingPanel';
import ExperimentReceiptPanel from './components/ExperimentReceiptPanel';
import RecoveryDiskPanel from './components/RecoveryDiskPanel';
import ExperimentB5Panel from './components/ExperimentB5Panel';
import RecoveryRestorePanel from './components/RecoveryRestorePanel';
import VideoRosterPanel from './components/VideoRosterPanel';
import FrontierRosterPanel from './components/FrontierRosterPanel';
import PromotionGatePanel from './components/PromotionGatePanel';
import QualityGateWritePanel from './components/QualityGateWritePanel';
import JsonRepairWritePanel from './components/JsonRepairWritePanel';
import AssistancePolicyWritePanel from './components/AssistancePolicyWritePanel';
import WorkerEnvironmentWritePanel from './components/WorkerEnvironmentWritePanel';
import PerceptionScoreWritePanel from './components/PerceptionScoreWritePanel';
import InterruptedUploadWritePanel from './components/InterruptedUploadWritePanel';
import PseudoLabelWritePanel from './components/PseudoLabelWritePanel';
import EventScoreWritePanel from './components/EventScoreWritePanel';
import DeploymentChoiceWritePanel from './components/DeploymentChoiceWritePanel';
import TrainingPromoteWritePanel from './components/TrainingPromoteWritePanel';
import TrainingLedgerWritePanel from './components/TrainingLedgerWritePanel';
import CacheRecomputeWritePanel from './components/CacheRecomputeWritePanel';
import CleanupCompleteWritePanel from './components/CleanupCompleteWritePanel';
import TrainingCycleWritePanel from './components/TrainingCycleWritePanel';
import ExperimentPauseWritePanel from './components/ExperimentPauseWritePanel';
import DecodeFirstWritePanel from './components/DecodeFirstWritePanel';
import DetectorWritePanel from './components/DetectorWritePanel';
import TrackerWritePanel from './components/TrackerWritePanel';
import EventProposeWritePanel from './components/EventProposeWritePanel';
import DecodeExportWritePanel from './components/DecodeExportWritePanel';
import DecodeProbeWritePanel from './components/DecodeProbeWritePanel';
import DecodePixelsWritePanel from './components/DecodePixelsWritePanel';
import DecodeCropWritePanel from './components/DecodeCropWritePanel';
import DecodeCutsWritePanel from './components/DecodeCutsWritePanel';
import DecodeGridWritePanel from './components/DecodeGridWritePanel';
import DecodeWrapWritePanel from './components/DecodeWrapWritePanel';
import DecodeFallbackWritePanel from './components/DecodeFallbackWritePanel';
import DecodeSampleWritePanel from './components/DecodeSampleWritePanel';
import DecodePtsWritePanel from './components/DecodePtsWritePanel';
import DecodeIntervalWritePanel from './components/DecodeIntervalWritePanel';
import PerceptionPreprocessWritePanel from './components/PerceptionPreprocessWritePanel';
import PerceptionStratumWritePanel from './components/PerceptionStratumWritePanel';
import PerceptionBallStatesWritePanel from './components/PerceptionBallStatesWritePanel';
import IdentityPreviewWritePanel from './components/IdentityPreviewWritePanel';
import StageTimingPanel from './components/StageTimingPanel';
import GpuProbePanel from './components/GpuProbePanel';
import IndependentReviewerPanel from './components/IndependentReviewerPanel';
import WorkedMatchFlowPanel from './components/WorkedMatchFlowPanel';
import DecodeMemoryPanel from './components/DecodeMemoryPanel';
import IdentityPolicyPanel from './components/IdentityPolicyPanel';
import TrainingPoolsPanel from './components/TrainingPoolsPanel';
import ShadowMetricPanel from './components/ShadowMetricPanel';
import LegacyDisplayPanel from './components/LegacyDisplayPanel';
import MetricDictionaryPanel from './components/MetricDictionaryPanel';
import LicenceRegisterPanel from './components/LicenceRegisterPanel';
import TelestrationPanel from './components/TelestrationPanel';
import DatasetRightsPanel from './components/DatasetRightsPanel';
import MetricRoundTripPanel from './components/MetricRoundTripPanel';
import IncidentResponsePanel from './components/IncidentResponsePanel';
import ProviderRosterPanel from './components/ProviderRosterPanel';
import StalePermissionGatePanel from './components/StalePermissionGatePanel';
import SignedObjectAccessPanel from './components/SignedObjectAccessPanel';
import LegacyGeometryPanel from './components/LegacyGeometryPanel';
import SplitScoresPanel from './components/SplitScoresPanel';
import ReleaseDossierPanel from './components/ReleaseDossierPanel';
import TrainingSamplingPanel from './components/TrainingSamplingPanel';
import DependencyRegisterPanel from './components/DependencyRegisterPanel';
import ChallengerAdaptersPanel from './components/ChallengerAdaptersPanel';
import FeatureFlagsPanel from './components/FeatureFlagsPanel';
import CapabilityRosterPanel from './components/CapabilityRosterPanel';
import DecodeChallengersPanel from './components/DecodeChallengersPanel';
import DecodeFramesPanel from './components/DecodeFramesPanel';
import GpuDefaultEnabledPanel from './components/GpuDefaultEnabledPanel';
import LocalOnlyDeploymentPanel from './components/LocalOnlyDeploymentPanel';
import FinishLineReportPanel from './components/FinishLineReportPanel';
import AcceptanceReportPanel from './components/AcceptanceReportPanel';
import OperatorHandoffPanel from './components/OperatorHandoffPanel';
import ReleaseReadoutPanel from './components/ReleaseReadoutPanel';
import PostReleaseMonitoringPanel from './components/PostReleaseMonitoringPanel';
import DetectorEvaluationReportPanel from './components/DetectorEvaluationReportPanel';
import PromotionReviewReportPanel from './components/PromotionReviewReportPanel';
import PromotedRuntimeMonitoringPanel from './components/PromotedRuntimeMonitoringPanel';
import OperatorDashboardPanel from './components/OperatorDashboardPanel';
import RealVideoScaleoutReportPanel from './components/RealVideoScaleoutReportPanel';
import BoundedNextSampleReportPanel from './components/BoundedNextSampleReportPanel';
import MatchProvenancePanel from './components/MatchProvenancePanel';
import MatchShotQualityPanel from './components/MatchShotQualityPanel';
import MatchShotFeaturesPanel from './components/MatchShotFeaturesPanel';
import MatchPlayerObservationsPanel from './components/MatchPlayerObservationsPanel';
import MatchEventPartitionPanel from './components/MatchEventPartitionPanel';
import MatchIdentityPanel from './components/MatchIdentityPanel';
import MatchAttackDirectionPanel from './components/MatchAttackDirectionPanel';
import MatchLegacyRecordsPanel from './components/MatchLegacyRecordsPanel';
import MatchExportPanel from './components/MatchExportPanel';
import MatchThemesPanel from './components/MatchThemesPanel';
import MatchAssistanceFallbackPanel from './components/MatchAssistanceFallbackPanel';
import MatchCalibrationPanel from './components/MatchCalibrationPanel';
import MatchWriteAlongsidePanel from './components/MatchWriteAlongsidePanel';
import MatchReportRecomputePanel from './components/MatchReportRecomputePanel';
import MatchRecoveryImportPanel from './components/MatchRecoveryImportPanel';
import MatchAssistanceReportPanel from './components/MatchAssistanceReportPanel';
import MatchTrackletWritePanel from './components/MatchTrackletWritePanel';
import MatchShotFeatureWritePanel from './components/MatchShotFeatureWritePanel';
import MatchIncidentReviewWritePanel from './components/MatchIncidentReviewWritePanel';
import MatchCacheWritePanel from './components/MatchCacheWritePanel';
import MatchOwnershipWritePanel from './components/MatchOwnershipWritePanel';
import MatchPackageWritePanel from './components/MatchPackageWritePanel';
import MatchMetricsWritePanel from './components/MatchMetricsWritePanel';
import MatchFormationWritePanel from './components/MatchFormationWritePanel';
import MatchIdentityWritePanel from './components/MatchIdentityWritePanel';
import MatchPlayerWritePanel from './components/MatchPlayerWritePanel';
import MatchIncidentGeometryWritePanel from './components/MatchIncidentGeometryWritePanel';
import MatchIncidentPackageWritePanel from './components/MatchIncidentPackageWritePanel';
import MatchEventPartitionWritePanel from './components/MatchEventPartitionWritePanel';
import MatchLegacyRecordsWritePanel from './components/MatchLegacyRecordsWritePanel';
import MatchAttackDirectionWritePanel from './components/MatchAttackDirectionWritePanel';
import MatchProvenanceWritePanel from './components/MatchProvenanceWritePanel';
import MatchShotQualityWritePanel from './components/MatchShotQualityWritePanel';
import AnalystWorkflowWritePanel from './components/AnalystWorkflowWritePanel';
import EvaluationPrerequisitesWritePanel from './components/EvaluationPrerequisitesWritePanel';
import MatchJobWritePanel from './components/MatchJobWritePanel';
import MatchAuditTrailPanel from './components/MatchAuditTrailPanel';
import MatchPrivacyPanel from './components/MatchPrivacyPanel';
import MatchTrackletsPanel from './components/MatchTrackletsPanel';
import MatchCachePanel from './components/MatchCachePanel';
import MatchPromotionPanel from './components/MatchPromotionPanel';
import MatchOwnershipPanel from './components/MatchOwnershipPanel';
import MatchIncidentGeometryPanel from './components/MatchIncidentGeometryPanel';
import MatchIncidentPackagePanel from './components/MatchIncidentPackagePanel';
import ProxyAssetsPanel from './components/ProxyAssetsPanel';
import HoldoutCalibrationPanel from './components/HoldoutCalibrationPanel';
import TypedSearchPanel from './components/TypedSearchPanel';
import PlayerDetailPanel from './components/PlayerDetailPanel';
import StatsPanel from './components/StatsPanel';
import TeamSelectionBanner from './components/TeamSelectionBanner';
import Timeline from './components/Timeline';
import TrustCropPanel from './components/TrustCropPanel';
import UploadCalibrationPanel from './components/UploadCalibrationPanel';
import { useCoachAnalysis } from './hooks/useCoachAnalysis';
import { useReviewSurface } from './features/review/useReviewSurface';
import type { BackendEvent, CameraProfile, EventTag, FormationSegment, FrameData, MatchBenchmarkSummary, MatchRecord, MatchStats, ProcessingJob, RuntimeCapabilities, ShotMarker } from './types';
import { buildPassingNetwork, buildPlayerProfiles, computeHeatmap, physicalMetricAvailability, playerPhysicalTotalsAvailability, speedAvailability, computeSpeedsForFrame, summarizeShots } from './utils/analytics';
import {
  buildMatchVideoUrl,
  createMatchUpload,
  fetchMatches,
  fetchMatchEvents,
  fetchMatchFrames,
  fetchMatchWorkspace,
  mapBackendEventsToTags,
  runMatchAnalysis,
  updateMatchConfig,
  waitForJobCompletion,
} from './utils/api';
import { buildUploadConfig, createEmptyPointInputs } from './utils/uploadConfig';
import { getUploadFailureGuidance } from './utils/uploadErrors';
import { findNearestFrameIndex } from './utils/videoSync';
import { playlistClipsFromCorrections } from './utils/playlist';
import { applyReviewShortcut, type ReviewAction } from './utils/reviewShortcuts';
import { fetchAssistance, fetchCorrectionHistory, fetchHeatmap, fetchIncidentReview, fetchMatchFormation, fetchMatchMetrics, fetchNative, fetchNativeMemory, fetchPendingCorrections, fetchQualityTimeline, fetchRecovery, fetchSecurity, fetchWorkbenchDossier, promoteMatchIdentity, recoverMatchCorrection, repairMatchIdentity, requestAccessDeletion, submitMatchCorrection, undoMatchCorrection, type FormationAvailability, type MetricAvailability } from './utils/workbench';
import { windowedTimelineProps } from './utils/windowedTimeline';
import { splitScores } from './utils/quantities';

interface MatchEntry {
  id: string;
  name: string;
  detail: MatchRecord;
  data: FrameData[];
  frameCount: number;
  stats: MatchStats;
  benchmark: MatchBenchmarkSummary | null;
  formationTimeline: FormationSegment[];
  shotAnalytics: ShotMarker[];
  backendEvents: BackendEvent[];
  baseEvents: EventTag[];
  evidence: Awaited<ReturnType<typeof fetchMatchWorkspace>>['evidence'];
}

export function formatJobStatus(job: ProcessingJob): string {
  return `${job.message || 'Processing match'} (${Math.round(job.progress * 100)}%)`;
}

function emptyStats(): MatchStats {
  return {
    possession: null,
    ballSignalStatus: 'trusted',
    ballSignalMessage: null,
    myTeamDistance: null,
    enemyDistance: null,
    myTeamAvgPos: null,
    enemyAvgPos: null,
    myTeamTopSpeed: null,
    enemyTopSpeed: null,
    myTeamSprints: null,
    enemySprints: null,
    myTeamXg: null,
    enemyXg: null,
    myTeamDefensiveLineHeight: null,
    enemyDefensiveLineHeight: null,
    myTeamDefensiveTeamLength: null,
    enemyDefensiveTeamLength: null,
    myTeamPpda: null,
    enemyPpda: null,
    myTeamHighPressRegains: null,
    enemyHighPressRegains: null,
    myTeamCounterpressRecoverySeconds: null,
    enemyCounterpressRecoverySeconds: null,
    formation: null,
  };
}

function workspaceToEntry(workspace: Awaited<ReturnType<typeof fetchMatchWorkspace>>): MatchEntry {
  return {
    id: workspace.detail.id,
    name: workspace.detail.name,
    detail: workspace.detail,
    data: workspace.frames,
    frameCount: workspace.frameCount ?? workspace.frames.length,
    stats: workspace.analytics.summary,
    benchmark: workspace.benchmark,
    formationTimeline: workspace.analytics.formationTimeline,
    shotAnalytics: workspace.analytics.shots,
    backendEvents: workspace.events,
    baseEvents: mapBackendEventsToTags(workspace.events, workspace.frames),
    evidence: workspace.evidence,
  };
}

const LOCAL_RUNTIME_CAPABILITIES: RuntimeCapabilities = {
  analysisProviders: ['local'],
  defaultAnalysisProvider: 'local',
  pdfExportAvailable: false,
};

interface AppProps {
  runtimeCapabilities?: RuntimeCapabilities;
}

function App({ runtimeCapabilities = LOCAL_RUNTIME_CAPABILITIES }: AppProps = {}) {
  const [matches, setMatches] = useState<MatchRecord[]>([]);
  const [activeMatch, setActiveMatch] = useState<MatchEntry | null>(null);
  const [comparisonMatch, setComparisonMatch] = useState<MatchEntry | null>(null);

  const [currentFrame, setCurrentFrame] = useState(0);
  const [seekVersion, setSeekVersion] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [fps] = useState(5);

  // A.5 — Coach analysis hook: owns llmThinking, llmResponse, llmProvider, tacticalReport, drillResponse, activeTab
  const coach = useCoachAnalysis({
    runtimeCapabilities,
    runMatchAnalysis,
    currentFrame,
  });
  const resetCoachAnalysis = coach.resetAnalysis;

  const [showZones, setShowZones] = useState(false);
  const [showNetwork, setShowNetwork] = useState(false);
  const [showShots, setShowShots] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [heatmapAvail, setHeatmapAvail] = useState({ wholeMatch: false, intervalLimited: true, withheld: true });
  const [speedAvail, setSpeedAvail] = useState({ wholeMatch: false, intervalLimited: true, withheld: true });
  const [playerTotalsAvail, setPlayerTotalsAvail] = useState({ wholeMatch: false, intervalLimited: true, withheld: true });
  const [identityContinuous, setIdentityContinuous] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState<import('./types').PlayerProfile | null>(null);
  const [showIssuePanel, setShowIssuePanel] = useState(false);
  const [showDashboard, setShowDashboard] = useState(false);
  const [showWorkbench, setShowWorkbench] = useState(false);
  const [showTrustCrop, setShowTrustCrop] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [comparisonLoadError, setComparisonLoadError] = useState<string | null>(null);
  const [events, setEvents] = useState<EventTag[]>([]);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const uploadAbortControllerRef = useRef<AbortController | null>(null);
  const activeWorkspaceRequestRef = useRef(0);
  const comparisonWorkspaceRequestRef = useRef(0);
  const activeMatchIdRef = useRef<string | null>(null);
  const activeFrameTimestampsRef = useRef<number[]>([]);
  const loadingOperationRef = useRef(0);
  const [uploadAttackDirection, setUploadAttackDirection] = useState<'left_to_right' | 'right_to_left'>('left_to_right');
  const [uploadCameraProfile, setUploadCameraProfile] = useState<CameraProfile>('stitched_panoramic_view');
  const [uploadPitchLengthM, setUploadPitchLengthM] = useState('');
  const [uploadPitchWidthM, setUploadPitchWidthM] = useState('');
  const [uploadPeriodOneEnd, setUploadPeriodOneEnd] = useState('');
  const [uploadCloudPermission, setUploadCloudPermission] = useState(false);
  const [uploadRetentionClass, setUploadRetentionClass] = useState<'working' | 'review' | 'publication' | 'unknown'>('unknown');
  const [uploadPointInputs, setUploadPointInputs] = useState(createEmptyPointInputs);
  const [uploadAutoHomography, setUploadAutoHomography] = useState(true);
  const [uploadVideoFile, setUploadVideoFile] = useState<File | null>(null);
  const [uploadVideoPreviewUrl, setUploadVideoPreviewUrl] = useState<string | null>(null);
  const [teamSelectionSaving, setTeamSelectionSaving] = useState(false);

  const beginLoadingOperation = useCallback(() => {
    const operationId = ++loadingOperationRef.current;
    setIsLoading(true);
    return operationId;
  }, []);

  const finishLoadingOperation = useCallback((operationId: number) => {
    if (loadingOperationRef.current === operationId) setIsLoading(false);
  }, []);

  useLayoutEffect(() => {
    activeMatchIdRef.current = activeMatch?.id ?? null;
  }, [activeMatch?.id]);
  useEffect(() => {
    if (!activeMatch?.id) {
      setStoredIncident(null);
      setQualityItems([]);
      setFormationAvailability(null);
      setHeatmapAvail({ wholeMatch: false, intervalLimited: true, withheld: true });
      setSpeedAvail({ wholeMatch: false, intervalLimited: true, withheld: true });
      setPlayerTotalsAvail({ wholeMatch: false, intervalLimited: true, withheld: true });
      setIdentityContinuous(false);
      setPendingCorrection(null);
      setCorrectionHistory([]);
      correctionHistoryRef.current = [];
      setStoredMetrics([]);
      return;
    }
    let cancelled = false;
    fetchIncidentReview(activeMatch.id)
      .then((payload) => {
        if (cancelled || payload.decision != null || !Array.isArray(payload.samples)) return;
        const interval = payload.touchInterval;
        setStoredIncident({
          touchStart: interval?.[0] ?? payload.samples[0]?.time ?? 0,
          touchEnd: interval?.[1] ?? payload.samples[payload.samples.length - 1]?.time ?? 0.12,
          samples: payload.samples,
        });
      })
      .catch(() => {
        if (!cancelled) setStoredIncident(null);
      });
    fetchQualityTimeline(activeMatch.id)
      .then((payload) => {
        if (cancelled || !Array.isArray(payload.items)) return;
        setQualityItems(payload.items);
      })
      .catch(() => {
        if (!cancelled) setQualityItems([]);
      });
    fetchMatchFormation(activeMatch.id)
      .then((payload) => {
        if (cancelled || typeof payload.availability !== 'string') return;
        setFormationAvailability(payload);
      })
      .catch(() => {
        if (!cancelled) setFormationAvailability(null);
      });
    fetchHeatmap(activeMatch.id)
      .then((payload) => {
        if (cancelled) return;
        const identity = payload.identityContinuous === true;
        setIdentityContinuous(identity);
        setHeatmapAvail({
          wholeMatch: payload.wholeMatch === true,
          intervalLimited: payload.intervalLimited !== false,
          withheld: payload.withheld !== false,
        });
        setSpeedAvail(speedAvailability(identity));
        setPlayerTotalsAvail(playerPhysicalTotalsAvailability(identity));
      })
      .catch(() => {
        if (!cancelled) {
          setIdentityContinuous(false);
          setHeatmapAvail({ wholeMatch: false, intervalLimited: true, withheld: true });
          setSpeedAvail({ wholeMatch: false, intervalLimited: true, withheld: true });
          setPlayerTotalsAvail({ wholeMatch: false, intervalLimited: true, withheld: true });
        }
      });
    fetchPendingCorrections(activeMatch.id)
      .then((payload) => {
        if (cancelled) return;
        const pending = payload.items.find((item) => item.saveState === 'pending') ?? payload.items[0] ?? null;
        setPendingCorrection(pending);
        if (pending) {
          setCorrectionSaveState('pending');
        }
      })
      .catch(() => {
        if (!cancelled) setPendingCorrection(null);
      });
    fetchCorrectionHistory(activeMatch.id)
      .then((payload) => {
        if (cancelled || !Array.isArray(payload.items)) return;
        const items = payload.items.map((item) => ({
          correctionId: item.correctionId,
          kind: item.kind,
          saveState: item.saveState,
          undoOf: item.undoOf ?? null,
          author: item.author,
          payload: item.payload ?? undefined,
        }));
        setCorrectionHistory(items);
        correctionHistoryRef.current = items;
      })
      .catch(() => undefined);
    fetchMatchMetrics(activeMatch.id)
      .then((payload) => {
        if (cancelled || !Array.isArray(payload.metrics)) return;
        setStoredMetrics(payload.metrics);
      })
      .catch(() => {
        if (!cancelled) setStoredMetrics([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeMatch?.id]);
  useEffect(() => {
    let cancelled = false;
    fetchRecovery()
      .then((payload) => {
        if (cancelled || !payload.deletion) return;
        setRecovery({
          controllerRecorded: Boolean(payload.deletion.available),
          unresolvedIncidents: payload.unresolvedIncidents.items ?? [],
          recoveryObjectivesDefined: Boolean(payload.recoveryObjectives.defined),
        });
      })
      .catch(() => {
        if (!cancelled) {
          setRecovery({ controllerRecorded: false, unresolvedIncidents: [], recoveryObjectivesDefined: false });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);
  useEffect(() => {
    let cancelled = false;
    fetchWorkbenchDossier()
      .then((payload) => {
        if (!cancelled && payload.release?.deploymentBoundary) {
          setDeploymentBoundary(payload.release.deploymentBoundary);
        }
      })
      .catch(() => {
        if (!cancelled) setDeploymentBoundary('loopback');
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
        if (cancelled || !payload.modelOutput) return;
        setSecurity({
          modelTrusted: payload.modelOutput.trusted,
          hostedEncryptionProven: payload.encryption?.hostedEncryptionProven,
          signedJobAccessAdmitted: payload.signedJobAccess?.admitted,
          publicExposureAllowed: payload.publicExposure?.publicExposureAllowed,
        });
      })
      .catch(() => {
        if (!cancelled) setSecurity(null);
      });
    fetchNative()
      .then((payload) => {
        if (cancelled || typeof payload.approved !== 'boolean') return;
        setNative((current) => ({
          ...current,
          approved: payload.approved,
          rpcFleetEnabled: payload.rpcFleet?.enabled,
          universallyPortable: payload.pinned?.universallyPortable,
        }));
      })
      .catch(() => {
        if (!cancelled) setNative(null);
      });
    fetchNativeMemory()
      .then((payload) => {
        if (cancelled || payload.completeRuntimeMemory !== false) return;
        setNative((current) => ({
          ...current,
          completeRuntimeMemory: payload.completeRuntimeMemory,
        }));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  const matchData = useMemo(() => activeMatch?.data || [], [activeMatch]);
  const totalFrameCount = activeMatch?.frameCount ?? matchData.length;
  const timelineWindow = useMemo(
    () => windowedTimelineProps(matchData, currentFrame, totalFrameCount),
    [matchData, currentFrame, totalFrameCount],
  );
  const [correctionSaveState, setCorrectionSaveState] = useState<'saved' | 'pending' | 'conflicted' | 'unavailable' | null>(null);
  const [correctionHistory, setCorrectionHistory] = useState<Array<{ correctionId: string; kind: string; saveState: string; undoOf?: string | null; author?: string; payload?: Record<string, unknown> }>>([]);
  const [pendingCorrection, setPendingCorrection] = useState<{ correctionId: string; kind: string; saveState: string; payload?: Record<string, unknown> | null } | null>(null);
  const [storedIncident, setStoredIncident] = useState<{
    touchStart: number;
    touchEnd: number;
    samples: Array<{ time: number; attackerX: number; offsideLineX: number; indeterminate: boolean }>;
  } | null>(null);
  const [storedMetrics, setStoredMetrics] = useState<MetricAvailability[]>([]);
  const [recovery, setRecovery] = useState<{
    controllerRecorded: boolean;
    unresolvedIncidents: Array<{ id: string; title: string }>;
    recoveryObjectivesDefined: boolean;
  }>({ controllerRecorded: false, unresolvedIncidents: [], recoveryObjectivesDefined: false });
  const [deploymentBoundary, setDeploymentBoundary] = useState('loopback');
  const [providersEnabled, setProvidersEnabled] = useState(false);
  const [qualityItems, setQualityItems] = useState<Array<{ id: string; label: string; impact: string }>>([]);
  const [formationAvailability, setFormationAvailability] = useState<FormationAvailability | null>(null);
  const [security, setSecurity] = useState<{
    modelTrusted?: boolean;
    hostedEncryptionProven?: boolean;
    signedJobAccessAdmitted?: boolean;
    publicExposureAllowed?: boolean;
  } | null>(null);
  const [native, setNative] = useState<{
    approved?: boolean;
    rpcFleetEnabled?: boolean;
    universallyPortable?: boolean;
    completeRuntimeMemory?: boolean;
  } | null>(null);
  const correctionVersionRef = useRef(0);
  const correctionHistoryRef = useRef(correctionHistory);
  correctionHistoryRef.current = correctionHistory;
  const matchStats = activeMatch?.stats || null;
  const matchBenchmark = activeMatch?.benchmark || null;
  const requiresTeamSelection = activeMatch?.detail.requiresTeamSelection ?? false;
  const isBallSignalUntrusted = matchStats?.ballSignalStatus === 'untrusted';
  const isBenchmarkTruthGateFailed = matchBenchmark ? !matchBenchmark.fiveMinuteTruthReady : false;
  const truthGateReasons = matchBenchmark?.truthGateReasons ?? [];
  const isTacticalInterpretationPaused = requiresTeamSelection || isBallSignalUntrusted || isBenchmarkTruthGateFailed;
  const tacticalPauseMessage = requiresTeamSelection
    ? 'Tactical interpretation is paused until a team cluster is chosen.'
    : isBallSignalUntrusted
      ? 'Ball signal is untrusted, so tactical interpretation is paused.'
      : isBenchmarkTruthGateFailed
        ? 'Benchmark truth gates failed, so this match is review-only until coverage improves.'
        : null;
  const comparisonStats = comparisonMatch?.stats ?? null;
  const comparisonName = comparisonMatch?.name ?? null;
  const isVideoMatch = activeMatch?.detail.inputMode === 'video';
  const frameTimestamps = useMemo(() => matchData.map((frame) => frame.Timestamp), [matchData]);
  const currentFrameRecord = matchData.find((frame) => frame.Frame_ID === currentFrame) ?? matchData[currentFrame] ?? null;
  const currentTimestamp = currentFrameRecord?.Timestamp ?? 0;
  const currentEvent = events.find((event) => event.frame === currentFrame) ?? events.find((event) => Math.abs(event.timestamp - currentTimestamp) < 0.2) ?? null;
  const incidentTouchStart = storedIncident?.touchStart ?? currentEvent?.intervalStart ?? currentTimestamp;
  const incidentTouchEnd = storedIncident?.touchEnd ?? currentEvent?.intervalEnd ?? Number((currentTimestamp + 0.12).toFixed(2));
  const incidentSamples = storedIncident?.samples ?? [];
  const matchVideoUrl = activeMatch ? buildMatchVideoUrl(activeMatch.id) : '';
  const uploadFailureGuidance = getUploadFailureGuidance(loadError);
  const canRetryUpload =
    !uploadAutoHomography &&
    uploadVideoFile !== null &&
    uploadPointInputs.every((point) => point.x.trim() !== '' && point.y.trim() !== '');

  // A.4 — Review surface hook: manages annotations, issues, review range, pitch placement
  const review = useReviewSurface({
    activeMatchId: activeMatch?.id ?? null,
    currentFrame,
    matchData,
    pausePlayback: () => setIsPlaying(false),
    clearResponse: coach.clearResponse,
    onSeekFrame: (frame) => {
      setCurrentFrame(frame);
      setSeekVersion(version => version + 1);
      coach.clearResponse();
    },
    setLoadError,
  });

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isPlaying && totalFrameCount > 0 && !isVideoMatch) {
      interval = setInterval(() => {
        setCurrentFrame((prev) => {
          if (prev >= totalFrameCount - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1000 / fps);
    }
    return () => clearInterval(interval);
  }, [fps, isPlaying, isVideoMatch, totalFrameCount]);

  useEffect(() => {
    if (!activeMatch) return;
    const loaded = matchData.some((frame) => frame.Frame_ID === currentFrame);
    if (loaded || totalFrameCount <= matchData.length) return;
    const matchId = activeMatch.id;
    let cancelled = false;
    void fetchMatchFrames(matchId, { afterFrame: currentFrame }).then((page) => {
      if (cancelled) return;
      setActiveMatch((previous) => (
        previous && previous.id === matchId
          ? { ...previous, data: page.frames, frameCount: page.frameCount || previous.frameCount }
          : previous
      ));
    }).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [activeMatch, currentFrame, matchData, totalFrameCount]);

  useEffect(() => {
    return () => {
      if (uploadVideoPreviewUrl) {
        URL.revokeObjectURL(uploadVideoPreviewUrl);
      }
    };
  }, [uploadVideoPreviewUrl]);

  useEffect(() => () => uploadAbortControllerRef.current?.abort(), []);

  const handleAddEvent = useCallback((event: EventTag) => {
    const nearestIndex = findNearestFrameIndex(activeFrameTimestampsRef.current, event.timestamp);
    const mappedFrame = Number.isFinite(event.frame)
      ? event.frame
      : (matchData[nearestIndex]?.Frame_ID ?? nearestIndex);
    setEvents((prev) => [...prev, { ...event, frame: mappedFrame }]);
  }, [matchData]);

  // Bridge CustomEvent('add-event') from Timeline.tsx to App state
  useEffect(() => {
    const handler = (e: Event) => {
      handleAddEvent((e as CustomEvent<EventTag>).detail);
    };
    window.addEventListener('add-event', handler);
    return () => window.removeEventListener('add-event', handler);
  }, [handleAddEvent]);

  const heatmapData = useMemo(() => {
    if (matchData.length === 0 || heatmapAvail.withheld) return null;
    return computeHeatmap(matchData, 'my_team');
  }, [heatmapAvail.withheld, matchData]);

  const passingNetwork = useMemo(() => {
    if (!activeMatch) return [];
    return buildPassingNetwork(activeMatch.backendEvents);
  }, [activeMatch]);

  const shotMarkers = useMemo(() => {
    return activeMatch?.shotAnalytics ?? [];
  }, [activeMatch]);

  const shotSummary = useMemo(() => summarizeShots(shotMarkers), [shotMarkers]);

  const playerProfiles = useMemo(() => {
    if (!activeMatch) return [];
    return buildPlayerProfiles(activeMatch.data, activeMatch.backendEvents, shotMarkers, identityContinuous);
  }, [activeMatch, identityContinuous, shotMarkers]);

  const speedData = useMemo(() => {
    if (matchData.length === 0 || speedAvail.withheld) return null;
    return computeSpeedsForFrame(matchData, currentFrame);
  }, [currentFrame, matchData, speedAvail.withheld]);

  const togglePlay = useCallback(() => setIsPlaying((playing) => !playing), []);

  const handleSeek = useCallback((frame: number) => {
    const last = Math.max(totalFrameCount, 1) - 1;
    setCurrentFrame(Math.max(0, Math.min(last, Math.trunc(frame))));
    setSeekVersion(version => version + 1);
    coach.clearResponse();
  }, [coach, totalFrameCount]);

  const applyStoredMatchEvents = useCallback(async (matchId: string, frames: FrameData[]) => {
    const storedEvents = await fetchMatchEvents(matchId);
    const tags = mapBackendEventsToTags(storedEvents, frames);
    setActiveMatch((previous) => {
      if (!previous || previous.id !== matchId) {
        return previous;
      }
      return {
        ...previous,
        backendEvents: storedEvents,
        baseEvents: tags,
      };
    });
    setEvents(tags);
  }, []);

  const handleReviewShortcut = useCallback((action: ReviewAction) => {
    const next = applyReviewShortcut(action, {
      isPlaying,
      currentFrame,
      frameCount: Math.max(totalFrameCount, 1),
      events,
      reviewRange: review.reviewRange,
    });
    if (next.isPlaying !== isPlaying) {
      setIsPlaying(next.isPlaying);
    }
    if (next.currentFrame !== currentFrame) {
      handleSeek(next.currentFrame);
    }
    const rangeChanged =
      next.reviewRange?.startFrame !== review.reviewRange?.startFrame ||
      next.reviewRange?.endFrame !== review.reviewRange?.endFrame;
    if (rangeChanged) {
      review.setReviewRange(next.reviewRange);
    }
    setEvents(next.events as EventTag[]);
    if ((action === 'accept' || action === 'reject') && activeMatch) {
      const matchId = activeMatch.id;
      const frames = activeMatch.data;
      const kind = action === 'accept' ? 'event_accept' : 'event_reject';
      const expectedVersion = correctionVersionRef.current;
      const reviewed = next.events.find((event) => event.frame === next.currentFrame) ?? next.events.find((event) => event.reviewStatus === (kind === 'event_accept' ? 'accepted' : 'rejected'));
      setCorrectionSaveState('pending');
      void submitMatchCorrection(matchId, {
        kind,
        payload: { frame: next.currentFrame, type: reviewed?.type },
        expectedVersion,
      })
        .then(async (saved) => {
          setCorrectionSaveState(saved.saveState as 'saved' | 'pending' | 'conflicted' | 'unavailable');
          if (saved.saveState === 'saved' && typeof saved.version === 'number') {
            correctionVersionRef.current = saved.version;
          }
          if (saved.correctionId) {
            setCorrectionHistory((previous) => {
              const next = [
                ...previous,
                { correctionId: saved.correctionId, kind, saveState: saved.saveState, undoOf: null },
              ];
              correctionHistoryRef.current = next;
              return next;
            });
          }
          if (saved.saveState !== 'saved') {
            return;
          }
          await applyStoredMatchEvents(matchId, frames);
        })
        .catch(() => {
          setCorrectionSaveState('unavailable');
        });
      return;
    }
    if (action === 'undo' && activeMatch) {
      const history = correctionHistoryRef.current;
      const undoneIds = new Set(
        history
          .map((item) => item.undoOf)
          .filter((undoOf): undoOf is string => typeof undoOf === 'string' && undoOf.length > 0),
      );
      const target = [...history].reverse().find((item) => (
        (item.kind === 'event_accept' || item.kind === 'event_reject')
        && item.saveState === 'saved'
        && !undoneIds.has(item.correctionId)
      ));
      if (!target) {
        return;
      }
      const matchId = activeMatch.id;
      const frames = activeMatch.data;
      setCorrectionSaveState('pending');
      void undoMatchCorrection(matchId, target.correctionId)
        .then(async (saved) => {
          setCorrectionSaveState('saved');
          setCorrectionHistory((previous) => {
            const next = [
              ...previous,
              {
                correctionId: saved.correctionId,
                kind: target.kind,
                saveState: 'saved',
                undoOf: saved.undoOf,
              },
            ];
            correctionHistoryRef.current = next;
            return next;
          });
          await applyStoredMatchEvents(matchId, frames);
        })
        .catch(() => {
          setCorrectionSaveState('unavailable');
        });
    }
  }, [activeMatch, applyStoredMatchEvents, currentFrame, events, handleSeek, isPlaying, totalFrameCount, review]);

  const handleDrawingAnnotation = useCallback(
    (x: number, y: number, x2?: number, y2?: number) => {
      if (!review.reviewMode || !activeMatch) return;
      if (review.reviewMode === 'circle') {
        void review.handlePitchPointSelect({ x, y });
      } else if (review.reviewMode === 'arrow') {
        if (review.pitchAnnotationPlacementMode === 'arrow-start') {
          void review.handlePitchPointSelect({ x, y });
        } else if (review.pitchAnnotationPlacementMode === 'arrow-end' && x2 !== undefined && y2 !== undefined) {
          void review.handlePitchPointSelect({ x: x2, y: y2 });
        }
      }
    },
    [activeMatch, review],
  );

  const loadWorkspaceIntoState = useCallback(
    async (
      matchId: string,
      { prepend = false, force = false }: { prepend?: boolean; force?: boolean } = {},
      signal?: AbortSignal,
    ) => {
      if (!force && activeMatchIdRef.current === matchId) return true;

      const requestId = ++activeWorkspaceRequestRef.current;
      const loadingOperationId = beginLoadingOperation();
      setLoadError(null);
      try {
        const workspace = await fetchMatchWorkspace(matchId, signal);
        if (signal?.aborted || activeWorkspaceRequestRef.current !== requestId) return false;
        const entry = workspaceToEntry(workspace);
        activeFrameTimestampsRef.current = entry.data.map(frame => frame.Timestamp);

        setMatches((previous) => {
          if (previous.some((match) => match.id === entry.id)) {
            return previous.map((match) => (match.id === entry.id ? entry.detail : match));
          }
          return prepend ? [entry.detail, ...previous] : [...previous, entry.detail];
        });
        setActiveMatch(entry);
        comparisonWorkspaceRequestRef.current += 1;
        setComparisonMatch(null);
        setComparisonLoadError(null);
        setCurrentFrame(entry.data[0]?.Frame_ID ?? 0);
        setIsPlaying(false);
        setSelectedPlayer(null);
        setEvents(entry.baseEvents);
        resetCoachAnalysis();
        setLoadError(null);
        return true;
      } catch (err) {
        if (signal?.aborted || activeWorkspaceRequestRef.current !== requestId) return false;
        setLoadError(err instanceof Error ? err.message : 'Failed to load the selected match.');
        throw err;
      } finally {
        finishLoadingOperation(loadingOperationId);
      }
    },
    [beginLoadingOperation, finishLoadingOperation, resetCoachAnalysis],
  );

  const handleRecoverPendingCorrection = useCallback(() => {
    if (!activeMatch || !pendingCorrection) return;
    const matchId = activeMatch.id;
    const frames = activeMatch.data;
    const pending = pendingCorrection;
    setCorrectionSaveState('pending');
    void recoverMatchCorrection(matchId, pending.correctionId)
      .then(async (saved) => {
        setPendingCorrection(null);
        setCorrectionSaveState(saved.saveState === 'saved' ? 'saved' : 'pending');
        setCorrectionHistory((previous) => {
          const next = [
            ...previous,
            {
              correctionId: saved.correctionId,
              kind: pending.kind,
              saveState: saved.saveState,
              undoOf: null,
              payload: pending.payload ?? undefined,
            },
          ];
          correctionHistoryRef.current = next;
          return next;
        });
        if (pending.kind === 'event_accept' || pending.kind === 'event_reject') {
          await applyStoredMatchEvents(matchId, frames);
          return;
        }
        if (pending.kind === 'playlist_item') {
          return;
        }
        await loadWorkspaceIntoState(matchId, { prepend: true, force: true });
      })
      .catch(() => {
        setCorrectionSaveState('unavailable');
      });
  }, [activeMatch, applyStoredMatchEvents, loadWorkspaceIntoState, pendingCorrection]);

  useEffect(() => {
    const controller = new AbortController();

    async function init() {
      const loadingOperationId = beginLoadingOperation();
      setLoadError(null);
      try {
        const listedMatches = await fetchMatches();
        if (controller.signal.aborted) return;
        const readyMatches = listedMatches.filter((match) => match.status === 'ready');
        setMatches(readyMatches);

        if (readyMatches.length === 0) {
          setActiveMatch(null);
          comparisonWorkspaceRequestRef.current += 1;
          setComparisonMatch(null);
          setComparisonLoadError(null);
          setEvents([]);
          return;
        }

        await loadWorkspaceIntoState(readyMatches[0].id, {}, controller.signal);
      } catch (err) {
        if (controller.signal.aborted) return;
        console.error('Could not load matches from the backend.', err);
        setLoadError(err instanceof Error ? err.message : 'Failed to load matches from the backend.');
      } finally {
        finishLoadingOperation(loadingOperationId);
      }
    }

    void init();
    return () => controller.abort();
  }, [beginLoadingOperation, finishLoadingOperation, loadWorkspaceIntoState]);

  const executeUpload = useCallback(
    async (file: File) => {
      const isJson = file.name.endsWith('.json');
      const isVideo = /\.(mp4|mov|m4v|avi)$/i.test(file.name);

      if (!isJson && !isVideo) {
        setLoadError('Please upload a tracking JSON file or a video file.');
        return;
      }

      let uploadConfig;
      try {
        uploadConfig = buildUploadConfig({
          isVideo,
          llmProvider: coach.llmProvider,
          attackDirection: uploadAttackDirection,
          cameraProfile: uploadCameraProfile,
          pointInputs: uploadPointInputs,
          autoHomography: uploadAutoHomography,
          pitchLengthM: uploadPitchLengthM.trim() === '' ? null : Number(uploadPitchLengthM),
          pitchWidthM: uploadPitchWidthM.trim() === '' ? null : Number(uploadPitchWidthM),
          periods: uploadPeriodOneEnd.trim() === '' ? [] : [
            { name: 'first_half', startSeconds: 0, endSeconds: Number(uploadPeriodOneEnd) },
          ],
          rights: {
            processingScope: 'local_only',
            cloudPermission: uploadCloudPermission,
            retentionClass: uploadRetentionClass,
          },
        });
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : 'Video uploads require calibration points.');
        return;
      }

      uploadAbortControllerRef.current?.abort();
      const controller = new AbortController();
      uploadAbortControllerRef.current = controller;
      const activeRequestId = activeWorkspaceRequestRef.current;
      const loadingOperationId = beginLoadingOperation();
      setJobStatus('Uploading match...');
      setLoadError(null);

      try {
        const upload = await createMatchUpload({
          name: file.name.replace(/\.[^.]+$/, ''),
          inputMode: isJson ? 'tracking_json' : 'video',
          file,
          config: uploadConfig,
          signal: controller.signal,
        });

        if (controller.signal.aborted) return;
        setJobStatus('Processing match...');
        await waitForJobCompletion(upload.jobId, undefined, undefined, controller.signal, (job) => {
          setJobStatus(formatJobStatus(job));
        });
        if (controller.signal.aborted || activeWorkspaceRequestRef.current !== activeRequestId) return;
        setJobStatus('Loading tactical workspace...');
        await loadWorkspaceIntoState(upload.matchId, { prepend: true, force: true }, controller.signal);
        if (controller.signal.aborted) return;
      } catch (err) {
        if (controller.signal.aborted) return;
        console.error(err);
        setLoadError(err instanceof Error ? err.message : 'Failed to upload and process match.');
      } finally {
        if (!controller.signal.aborted) {
          setJobStatus(null);
        }
        finishLoadingOperation(loadingOperationId);
        controller.abort();
        if (uploadAbortControllerRef.current === controller) {
          uploadAbortControllerRef.current = null;
        }
      }
    },
    [beginLoadingOperation, coach.llmProvider, finishLoadingOperation, loadWorkspaceIntoState, uploadAttackDirection, uploadCameraProfile, uploadPointInputs, uploadAutoHomography, uploadPitchLengthM, uploadPitchWidthM, uploadPeriodOneEnd, uploadCloudPermission, uploadRetentionClass],
  );

  const handleFileUpload = useCallback(
    async (file: File) => {
      const isJson = file.name.endsWith('.json');
      const isVideo = /\.(mp4|mov|m4v|avi)$/i.test(file.name);

      if (!isJson && !isVideo) {
        setLoadError('Please upload a tracking JSON file or a video file.');
        return;
      }

      setUploadVideoFile(isVideo ? file : null);
      setUploadVideoPreviewUrl((previousUrl) => {
        if (previousUrl) {
          URL.revokeObjectURL(previousUrl);
        }
        return isVideo ? URL.createObjectURL(file) : null;
      });

      await executeUpload(file);
    },
    [executeUpload],
  );

  const handleRetryUpload = useCallback(() => {
    if (!uploadVideoFile || !canRetryUpload) {
      return;
    }
    void executeUpload(uploadVideoFile);
  }, [canRetryUpload, executeUpload, uploadVideoFile]);

  const updateUploadPoint = useCallback((index: number, axis: 'x' | 'y', value: string) => {
    setUploadPointInputs((prev) =>
      prev.map((point, pointIndex) => (pointIndex === index ? { ...point, [axis]: value } : point)),
    );
  }, []);

  const resetUploadPoints = useCallback(() => {
    setUploadPointInputs(createEmptyPointInputs());
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const file = event.dataTransfer.files[0];
      if (file) void handleFileUpload(file);
    },
    [handleFileUpload],
  );

  const handleFileInput = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) void handleFileUpload(file);
      event.target.value = '';
    },
    [handleFileUpload],
  );

  const handleMatchSelection = useCallback(
    (matchId: string) => {
      void loadWorkspaceIntoState(matchId).catch(() => undefined);
    },
    [loadWorkspaceIntoState],
  );

  const handleComparisonSelection = useCallback((matchId: string | null) => {
    if (!matchId) {
      comparisonWorkspaceRequestRef.current += 1;
      setComparisonMatch(null);
      setComparisonLoadError(null);
      return;
    }
    if (comparisonMatch?.id === matchId) return;

    const requestId = ++comparisonWorkspaceRequestRef.current;
    setComparisonLoadError(null);
    void fetchMatchWorkspace(matchId)
      .then((workspace) => {
        if (comparisonWorkspaceRequestRef.current !== requestId) return;
        setComparisonMatch(workspaceToEntry(workspace));
      })
      .catch((err) => {
        if (comparisonWorkspaceRequestRef.current !== requestId) return;
        setComparisonLoadError(err instanceof Error ? err.message : 'Failed to load the comparison match.');
      });
  }, [comparisonMatch?.id]);

  const handleTeamClusterSelection = useCallback(
    async (clusterId: number) => {
      if (!activeMatch) return;

      const matchId = activeMatch.id;
      const activeRequestId = activeWorkspaceRequestRef.current;
      const loadingOperationId = beginLoadingOperation();
      setTeamSelectionSaving(true);
      setJobStatus('Relabeling teams...');
      setLoadError(null);
      try {
        await updateMatchConfig(matchId, { myTeamCluster: clusterId });
        if (activeWorkspaceRequestRef.current !== activeRequestId || activeMatchIdRef.current !== matchId) return;
        await loadWorkspaceIntoState(matchId, { prepend: true, force: true });
      } catch (err) {
        console.error(err);
        if (activeWorkspaceRequestRef.current === activeRequestId) {
          setLoadError(err instanceof Error ? err.message : 'Failed to apply team selection.');
        }
      } finally {
        setJobStatus(null);
        finishLoadingOperation(loadingOperationId);
        setTeamSelectionSaving(false);
      }
    },
    [activeMatch, beginLoadingOperation, finishLoadingOperation, loadWorkspaceIntoState],
  );

  const handleClipSaved = useCallback((clip: { start: number; end: number; notes: string; sourceEndFrameExclusive: number }) => {
    if (!activeMatch?.id) return Promise.resolve();
    const matchId = activeMatch.id;
    const expectedVersion = correctionVersionRef.current;
    setCorrectionSaveState('pending');
    return submitMatchCorrection(matchId, {
      kind: 'playlist_item',
      payload: {
        timestampStart: clip.start,
        timestampEnd: clip.end,
        sourceEndFrameExclusive: clip.sourceEndFrameExclusive,
        notes: clip.notes,
      },
      expectedVersion,
    })
      .then((saved) => {
        setCorrectionSaveState(saved.saveState as 'saved' | 'pending' | 'conflicted' | 'unavailable');
        if (saved.saveState === 'saved' && typeof saved.version === 'number') {
          correctionVersionRef.current = saved.version;
        }
        if (saved.correctionId) {
          setCorrectionHistory((previous) => {
            const next = [
              ...previous,
              {
                correctionId: saved.correctionId,
                kind: 'playlist_item',
                saveState: saved.saveState,
                undoOf: null,
                author: 'analyst',
                payload: {
                  timestampStart: clip.start,
                  timestampEnd: clip.end,
                  sourceEndFrameExclusive: clip.sourceEndFrameExclusive,
                  notes: clip.notes,
                },
              },
            ];
            correctionHistoryRef.current = next;
            return next;
          });
        }
      })
      .catch(() => {
        setCorrectionSaveState('unavailable');
      });
  }, [activeMatch?.id]);

  const handleSwapTeams = useCallback(() => {
    if (!activeMatch?.id || requiresTeamSelection) return;
    const matchId = activeMatch.id;
    const expectedVersion = correctionVersionRef.current;
    setCorrectionSaveState('pending');
    void submitMatchCorrection(matchId, {
      kind: 'team_mapping',
      payload: { swap: true },
      expectedVersion,
    })
      .then(async (saved) => {
        setCorrectionSaveState(saved.saveState as 'saved' | 'pending' | 'conflicted' | 'unavailable');
        if (saved.saveState === 'saved' && typeof saved.version === 'number') {
          correctionVersionRef.current = saved.version;
        }
        if (saved.correctionId) {
          setCorrectionHistory((previous) => [
            ...previous,
            { correctionId: saved.correctionId, kind: 'team_mapping', saveState: saved.saveState, undoOf: null },
          ]);
        }
        if (saved.saveState === 'saved') {
          await loadWorkspaceIntoState(matchId, { prepend: true, force: true });
        }
      })
      .catch(() => {
        setCorrectionSaveState('unavailable');
      });
  }, [activeMatch?.id, loadWorkspaceIntoState, requiresTeamSelection]);

  const handleVideoTimeChange = useCallback(
    (time: number) => {
      if (frameTimestamps.length === 0) return;
      const index = findNearestFrameIndex(frameTimestamps, time);
      setCurrentFrame(matchData[index]?.Frame_ID ?? index);
    },
    [frameTimestamps, matchData],
  );

  return (
    <div className="min-h-screen bg-slate-900 text-slate-200 p-6 font-sans">
      <header className="mb-6 flex justify-between items-center gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-emerald-400">Guerilla Analytics</h1>
          <p className="text-slate-400 text-sm">Local-First Tactical Panel</p>
        </div>
        <div className="flex items-center space-x-3 flex-wrap justify-end">
          {matches.length > 1 && (
            <select
              aria-label="Active match"
              value={activeMatch?.id ?? ''}
              onChange={(event) => handleMatchSelection(event.target.value)}
              className="bg-slate-800 text-slate-200 text-xs px-3 py-2 rounded border border-slate-700 font-mono"
            >
              {matches.map((match) => (
                <option key={match.id} value={match.id}>
                  {match.name}
                </option>
              ))}
            </select>
          )}
          {matches.length > 1 && (
            <select
              aria-label="Comparison match"
              value={comparisonMatch?.id ?? ''}
              onChange={(event) => handleComparisonSelection(event.target.value || null)}
              className="bg-slate-800 text-slate-200 text-xs px-3 py-2 rounded border border-slate-700 font-mono"
            >
              <option value="">Compare to...</option>
              {matches.map(
                (match) =>
                  match.id !== activeMatch?.id && (
                    <option key={match.id} value={match.id}>
                      {match.name}
                    </option>
                  ),
              )}
            </select>
          )}
          {activeMatch && (
            <span className="text-xs text-slate-500 font-mono bg-slate-800 px-3 py-1 rounded border border-slate-700">
              {activeMatch.name}
            </span>
          )}
          <label className="focus-within:ring-2 focus-within:ring-emerald-300 bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded text-sm transition-colors border border-emerald-500 shadow-sm flex items-center gap-2 cursor-pointer text-white font-semibold">
            Load Match
            <input type="file" accept=".json,video/*" onChange={handleFileInput} className="sr-only" disabled={isLoading || jobStatus !== null} />
          </label>
        </div>
      </header>

      <UploadCalibrationPanel
        autoHomography={uploadAutoHomography}
        loadedVideoConfig={isVideoMatch ? activeMatch?.detail.config ?? null : undefined}
        attackDirection={uploadAttackDirection}
        cameraProfile={uploadCameraProfile}
        pointInputs={uploadPointInputs}
        previewUrl={uploadVideoPreviewUrl}
        canRetryUpload={canRetryUpload}
        isRetryingUpload={jobStatus !== null}
        uploadFailureGuidance={uploadFailureGuidance}
        onAutoHomographyChange={setUploadAutoHomography}
        onAttackDirectionChange={setUploadAttackDirection}
        onCameraProfileChange={setUploadCameraProfile}
        onPointChange={updateUploadPoint}
        onResetPoints={resetUploadPoints}
        onRetryUpload={handleRetryUpload}
        pitchLengthM={uploadPitchLengthM}
        pitchWidthM={uploadPitchWidthM}
        periodOneEnd={uploadPeriodOneEnd}
        cloudPermission={uploadCloudPermission}
        retentionClass={uploadRetentionClass}
        onPitchLengthChange={setUploadPitchLengthM}
        onPitchWidthChange={setUploadPitchWidthM}
        onPeriodOneEndChange={setUploadPeriodOneEnd}
        onCloudPermissionChange={setUploadCloudPermission}
        onRetentionClassChange={setUploadRetentionClass}
      />

      {activeMatch && loadError && (
        <div role="alert" className="mb-4 rounded border border-red-800 bg-red-900/30 px-3 py-2 text-sm text-red-300">
          {loadError}
        </div>
      )}
      {comparisonLoadError && (
        <div role="alert" className="mb-4 rounded border border-red-800 bg-red-900/30 px-3 py-2 text-sm text-red-300">
          Comparison unavailable: {comparisonLoadError}
        </div>
      )}

      {activeMatch?.detail.requiresTeamSelection && (
        <TeamSelectionBanner
          clusters={activeMatch.detail.teamClusters || []}
          isSubmitting={teamSelectionSaving}
          onSelectCluster={(clusterId) => void handleTeamClusterSelection(clusterId)}
        />
      )}

      <main className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 bg-slate-800 p-4 rounded-xl shadow-lg border border-slate-700 flex flex-col items-center">
          <div
            className={`w-full ${isVideoMatch && matchData.length > 0 ? 'max-w-6xl' : 'max-w-4xl'} aspect-[1.5] bg-green-800 rounded-lg overflow-hidden border-2 border-slate-600 relative shrink-0 flex items-center justify-center`}
          >
            {isLoading && (!activeMatch || jobStatus !== null) ? (
              <div className="w-full h-full flex flex-col items-center justify-center bg-slate-900 z-10">
                <div className="text-4xl mb-4 animate-bounce">⚽</div>
                <p className="text-slate-400 text-sm">{jobStatus || 'Loading tactical workspace...'}</p>
              </div>
            ) : loadError && !activeMatch ? (
              <div className="w-full h-full flex flex-col items-center justify-center bg-slate-900 border-2 border-dashed border-red-900/50 p-10 text-center z-10">
                <div className="text-4xl mb-4">⚠️</div>
                <h2 className="text-xl font-bold text-red-400 mb-2">Backend Not Ready</h2>
                <p className="text-slate-400 text-sm max-w-md">{loadError}</p>
                {uploadFailureGuidance && (
                  <p className="mt-3 max-w-md rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                    {uploadFailureGuidance}
                  </p>
                )}
              </div>
            ) : matchData.length === 0 ? (
              <div
                className="w-full h-full flex flex-col items-center justify-center bg-slate-900 border-2 border-dashed border-slate-700 hover:border-emerald-600/50 p-10 text-center z-10 transition-colors"
                onDragOver={(event) => {
                  event.preventDefault();
                  event.currentTarget.classList.add('border-emerald-400');
                }}
                onDragLeave={(event) => {
                  event.currentTarget.classList.remove('border-emerald-400');
                }}
                onDrop={(event) => {
                  event.currentTarget.classList.remove('border-emerald-400');
                  handleDrop(event);
                }}
              >
                <div className="text-5xl mb-6">⚽</div>
                <h2 className="text-2xl font-bold text-slate-200 mb-4">Upload a Match</h2>
                <p className="text-slate-400 max-w-md mb-8">
                  Import existing tracking JSON now, or send video through the backend pipeline once calibration points are available.
                </p>
                <label className="focus-within:ring-2 focus-within:ring-emerald-300 bg-emerald-600 hover:bg-emerald-500 px-6 py-3 rounded-lg text-sm transition-colors border border-emerald-500 shadow-lg cursor-pointer text-white font-semibold mb-8 flex items-center gap-2">
                  Upload JSON or Video
                  <input type="file" accept=".json,video/*" onChange={handleFileInput} className="sr-only" disabled={isLoading || jobStatus !== null} />
                </label>
                <p className="text-slate-600 text-xs mb-6">Drag & drop works too. Tracking JSON imports are the fastest path for tranche 1 verification, while video uploads use the calibration strip above.</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left w-full max-w-3xl px-4">
                  <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                    <div className="w-7 h-7 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold mb-2 text-sm">1</div>
                    <h3 className="font-semibold text-slate-200 mb-1 text-sm">Upload Source</h3>
                    <p className="text-xs text-slate-400">Tracking JSON is ready today. Video jobs depend on manual homography inputs.</p>
                  </div>
                  <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                    <div className="w-7 h-7 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold mb-2 text-sm">2</div>
                    <h3 className="font-semibold text-slate-200 mb-1 text-sm">Process Locally</h3>
                    <p className="text-xs text-slate-400">The backend stores match state, analytics, and derived events in SQLite plus local artifacts.</p>
                  </div>
                  <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                    <div className="w-7 h-7 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold mb-2 text-sm">3</div>
                    <h3 className="font-semibold text-slate-200 mb-1 text-sm">Review Tactically</h3>
                    <p className="text-xs text-slate-400">Playback, overlays, event markers, and tactical analysis all come from the persisted API workspace.</p>
                  </div>
                </div>
              </div>
            ) : isVideoMatch ? (
              <div className="grid h-full w-full grid-cols-1 gap-4 bg-slate-900 p-4 xl:grid-cols-[1.2fr_1fr]">
                <MatchVideoPanel
                  key={matchVideoUrl}
                  videoUrl={matchVideoUrl}
                  currentTimestamp={currentTimestamp}
                  isPlaying={isPlaying}
                  seekVersion={seekVersion}
                  onPlayingChange={setIsPlaying}
                  onVideoTimeChange={handleVideoTimeChange}
                />
                <div className="overflow-hidden rounded-lg border border-slate-700 bg-green-800">
                  <TacticalPitch
                    frameData={currentFrameRecord}
                    annotations={coach.llmResponse}
                    showZones={showZones}
                    showNetwork={showNetwork}
                    showShots={showShots}
                    showHeatmap={showHeatmap}
                    heatmapData={heatmapData}
                    passNetwork={passingNetwork}
                    shotMarkers={shotMarkers}
                    speedData={speedData}
                    playerProfiles={playerProfiles}
                    onPlayerClick={setSelectedPlayer}
                    drawingMode={review.reviewMode}
                    pitchAnnotationPlacementMode={review.pitchAnnotationPlacementMode}
                    savedAnnotations={review.annotations}
                    onAnnotationCreate={handleDrawingAnnotation}
                  />
                </div>
              </div>
            ) : (
              <TacticalPitch
                frameData={currentFrameRecord}
                annotations={coach.llmResponse}
                showZones={showZones}
                showNetwork={showNetwork}
                showShots={showShots}
                showHeatmap={showHeatmap}
                heatmapData={heatmapData}
                passNetwork={passingNetwork}
                shotMarkers={shotMarkers}
                speedData={speedData}
                playerProfiles={playerProfiles}
                onPlayerClick={setSelectedPlayer}
                drawingMode={review.reviewMode}
                pitchAnnotationPlacementMode={review.pitchAnnotationPlacementMode}
                savedAnnotations={review.annotations}
                onAnnotationCreate={handleDrawingAnnotation}
              />
            )}
          </div>

          {selectedPlayer && (
            <div className="fixed right-4 top-20 z-50 w-80 max-w-xs">
              <PlayerDetailPanel
                player={selectedPlayer}
                events={activeMatch?.backendEvents ?? []}
                identityContinuous={identityContinuous}
                onSplitIdentity={() => {
                  if (!activeMatch?.id || selectedPlayer.playerId == null) return;
                  const matchId = activeMatch.id;
                  setCorrectionSaveState('pending');
                  void repairMatchIdentity(matchId, {
                    kind: 'track_split',
                    trackId: String(selectedPlayer.playerId),
                    atFrame: currentFrame,
                  })
                    .then(async (payload) => {
                      setCorrectionSaveState(payload.correction?.saveState === 'saved' ? 'saved' : 'pending');
                      if (payload.correction?.correctionId) {
                        setCorrectionHistory((previous) => [
                          ...previous,
                          {
                            correctionId: payload.correction?.correctionId ?? '',
                            kind: payload.correction?.kind ?? 'track_split',
                            saveState: payload.correction?.saveState ?? 'pending',
                            undoOf: null,
                          },
                        ]);
                      }
                      setIdentityContinuous(false);
                      if (payload.correction?.saveState === 'saved') {
                        await loadWorkspaceIntoState(matchId, { prepend: true, force: true });
                      }
                      const heatmap = await fetchHeatmap(matchId);
                      const identity = heatmap.identityContinuous === true;
                      setIdentityContinuous(identity);
                      setHeatmapAvail({
                        wholeMatch: heatmap.wholeMatch === true,
                        intervalLimited: heatmap.intervalLimited !== false,
                        withheld: heatmap.withheld !== false,
                      });
                      setSpeedAvail(speedAvailability(identity));
                      setPlayerTotalsAvail(playerPhysicalTotalsAvailability(identity));
                    })
                    .catch(() => {
                      setCorrectionSaveState('unavailable');
                    });
                }}
                onJoinIdentity={(rightTrackId) => {
                  if (!activeMatch?.id || selectedPlayer.playerId == null) return;
                  const matchId = activeMatch.id;
                  setCorrectionSaveState('pending');
                  void repairMatchIdentity(matchId, {
                    kind: 'track_join',
                    leftTrackId: String(selectedPlayer.playerId),
                    rightTrackId,
                  })
                    .then(async (payload) => {
                      setCorrectionSaveState(payload.correction?.saveState === 'saved' ? 'saved' : 'pending');
                      if (payload.correction?.correctionId) {
                        setCorrectionHistory((previous) => [
                          ...previous,
                          {
                            correctionId: payload.correction?.correctionId ?? '',
                            kind: payload.correction?.kind ?? 'track_join',
                            saveState: payload.correction?.saveState ?? 'pending',
                            undoOf: null,
                          },
                        ]);
                      }
                      setIdentityContinuous(false);
                      if (payload.correction?.saveState === 'saved') {
                        await loadWorkspaceIntoState(matchId, { prepend: true, force: true });
                      }
                      const heatmap = await fetchHeatmap(matchId);
                      const identity = heatmap.identityContinuous === true;
                      setIdentityContinuous(identity);
                      setHeatmapAvail({
                        wholeMatch: heatmap.wholeMatch === true,
                        intervalLimited: heatmap.intervalLimited !== false,
                        withheld: heatmap.withheld !== false,
                      });
                      setSpeedAvail(speedAvailability(identity));
                      setPlayerTotalsAvail(playerPhysicalTotalsAvailability(identity));
                    })
                    .catch(() => {
                      setCorrectionSaveState('unavailable');
                    });
                }}
                onValidateIdentity={() => {
                  if (!activeMatch?.id) return;
                  const matchId = activeMatch.id;
                  setCorrectionSaveState('pending');
                  void promoteMatchIdentity(matchId)
                    .then(async (payload) => {
                      setCorrectionSaveState(payload.correction?.saveState === 'saved' ? 'saved' : 'pending');
                      if (payload.correction?.correctionId) {
                        setCorrectionHistory((previous) => [
                          ...previous,
                          {
                            correctionId: payload.correction?.correctionId ?? '',
                            kind: payload.correction?.kind ?? 'identity_validate',
                            saveState: payload.correction?.saveState ?? 'pending',
                            undoOf: null,
                          },
                        ]);
                      }
                      const heatmap = await fetchHeatmap(matchId);
                      const identity = heatmap.identityContinuous === true;
                      setIdentityContinuous(identity);
                      setHeatmapAvail({
                        wholeMatch: heatmap.wholeMatch === true,
                        intervalLimited: heatmap.intervalLimited !== false,
                        withheld: heatmap.withheld !== false,
                      });
                      setSpeedAvail(speedAvailability(identity));
                      setPlayerTotalsAvail(playerPhysicalTotalsAvailability(identity));
                    })
                    .catch(() => {
                      setCorrectionSaveState('unavailable');
                    });
                }}
              />
              <button
                type="button"
                onClick={() => setSelectedPlayer(null)}
                className="mt-2 w-full rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-800 transition-colors"
              >
                Close
              </button>
            </div>
          )}

          <Timeline
            matchData={timelineWindow.matchData}
            currentFrame={timelineWindow.currentFrame}
            currentRecord={timelineWindow.currentRecord}
            frameCount={timelineWindow.frameCount}
            isPlaying={isPlaying}
            fps={fps}
            events={events}
            reviewRange={review.reviewRange}
            onRangeChange={review.setReviewRange}
            onSeek={handleSeek}
            onTogglePlay={togglePlay}
          />

          {matchData.length > 0 && (
            <div className="w-full max-w-4xl mt-4 flex justify-between items-center text-sm flex-wrap gap-2">
              <div className="flex space-x-4 bg-slate-900 px-3 py-2 rounded-lg border border-slate-700">
                <div className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
                  <span className="text-slate-400 text-xs">My Team</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span>
                  <span className="text-slate-400 text-xs">Enemy</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-yellow-400"></span>
                  <span className="text-slate-400 text-xs">Ball</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-orange-500"></span>
                  <span className="text-slate-400 text-xs">Sprint</span>
                </div>
              </div>

              <div className="flex space-x-2">
                {[
                  { key: 'heatmap', label: 'Heat Map', active: showHeatmap, toggle: () => setShowHeatmap(!showHeatmap), activeStyle: 'bg-orange-600/20 border-orange-500 text-orange-400' },
                  { key: 'zones', label: 'Zones', active: showZones, toggle: () => setShowZones(!showZones), activeStyle: 'bg-emerald-600/20 border-emerald-500 text-emerald-400' },
                  { key: 'network', label: 'Pass Net', active: showNetwork, toggle: () => setShowNetwork(!showNetwork), activeStyle: 'bg-blue-600/20 border-blue-500 text-blue-400' },
                  { key: 'shots', label: 'Shot Map', active: showShots, toggle: () => setShowShots(!showShots), activeStyle: 'bg-rose-600/20 border-rose-500 text-rose-300' },
                ].map((button) => (
                  <button
                    key={button.key}
                    onClick={button.toggle}
                    aria-pressed={button.active}
                    className={`px-3 py-1.5 rounded border text-xs font-semibold transition-colors ${
                      button.active ? button.activeStyle : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-500'
                    }`}
                  >
                    {button.label}
                  </button>
                ))}
                {heatmapAvail.withheld && (
                  <span className="text-[11px] text-amber-200">Whole-match heatmap withheld until identity continuity.</span>
                )}
                {speedAvail.withheld && (
                  <span className="text-[11px] text-amber-200">Derived speeds withheld until identity continuity.</span>
                )}
                {playerTotalsAvail.withheld && (
                  <span className="text-[11px] text-amber-200">Player physical totals withheld until identity continuity.</span>
                )}
                <button
                  type="button"
                  onClick={() => setShowDashboard(true)}
                  className="px-3 py-1.5 rounded border border-emerald-600/30 bg-emerald-900/20 text-emerald-300 text-xs font-semibold hover:bg-emerald-900/40 transition-colors"
                >
                  Dashboard
                </button>
                <button
                  type="button"
                  onClick={() => setShowWorkbench(true)}
                  className="px-3 py-1.5 rounded border border-sky-600/30 bg-sky-900/20 text-sky-300 text-xs font-semibold hover:bg-sky-900/40 transition-colors"
                >
                  Capabilities
                </button>
                <button
                  type="button"
                  onClick={() => setShowTrustCrop(true)}
                  className="px-3 py-1.5 rounded border border-amber-600/30 bg-amber-900/20 text-amber-300 text-xs font-semibold hover:bg-amber-900/40 transition-colors"
                >
                  Trust Crops
                </button>
                <button
                  type="button"
                  onClick={() => setShowIssuePanel(true)}
                  className="px-3 py-1.5 rounded border border-amber-600/30 bg-amber-900/20 text-amber-300 text-xs font-semibold hover:bg-amber-900/40 transition-colors"
                >
                  Report Issue
                </button>
                {!requiresTeamSelection && (
                  <button
                    type="button"
                    onClick={handleSwapTeams}
                    className="px-3 py-1.5 rounded border border-sky-600/30 bg-sky-900/20 text-sky-300 text-xs font-semibold hover:bg-sky-900/40 transition-colors"
                  >
                    Swap teams
                  </button>
                )}
              </div>
            </div>
          )}

          {matchData.length > 0 && (
            <StatsPanel
              stats={matchStats || emptyStats()}
              benchmark={matchBenchmark}
              formationTimeline={activeMatch?.formationTimeline ?? []}
              formationAvailability={formationAvailability ?? undefined}
              shotSummary={shotSummary}
              playerProfiles={playerProfiles}
              comparisonStats={comparisonStats}
              comparisonName={comparisonName ?? undefined}
              metricAvailability={
                storedMetrics.length
                  ? storedMetrics
                  : (matchStats as MatchStats | null)?.metricAvailability?.length
                    ? matchStats?.metricAvailability
                    : activeMatch?.detail.requiresTeamSelection || matchBenchmark?.fiveMinuteTruthReady === false
                      ? physicalMetricAvailability(identityContinuous)
                      : []
              }
            />
          )}
        </div>

        <div className="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-4 flex flex-col" style={{ maxHeight: '85vh' }}>
          <h2 className="text-lg font-semibold mb-3 text-emerald-400 border-b border-slate-700 pb-2">Tactical Brain</h2>

          {isTacticalInterpretationPaused && (
            <div className="mb-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
              <p>{tacticalPauseMessage}</p>
              {truthGateReasons.length > 0 && (
                <ul className="mt-2 list-disc space-y-1 pl-4">
                  {truthGateReasons.slice(0, 3).map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* A.4 — Annotation toolbar and list wired to useReviewSurface */}
          <div className="mb-3 shrink-0">
            <ReviewToolbar
              onCreateNote={review.handleCreateNote}
              onCreateTaggedMoment={review.handleCreateTaggedMoment}
              onShortcut={handleReviewShortcut}
              saveState={correctionSaveState}
            />
            {pendingCorrection && (
              <div className="mt-2 rounded-lg border border-amber-700/50 bg-amber-950/30 p-3 space-y-2">
                <p className="text-xs text-amber-200">Pending correction ({pendingCorrection.kind})</p>
                <button
                  type="button"
                  onClick={handleRecoverPendingCorrection}
                  className="px-3 py-1.5 rounded bg-amber-700 text-xs font-semibold text-white"
                >
                  Recover pending correction
                </button>
              </div>
            )}
          </div>
          <div className="mb-3 shrink-0">
            <ChangeHistory
              items={correctionHistory}
              onUndo={(correctionId) => {
                if (!activeMatch?.id) return;
                const matchId = activeMatch.id;
                const frames = activeMatch.data;
                const original = correctionHistory.find((item) => item.correctionId === correctionId)
                  ?? correctionHistoryRef.current.find((item) => item.correctionId === correctionId);
                void undoMatchCorrection(matchId, correctionId).then(async (saved) => {
                  setCorrectionHistory((previous) => {
                    const next = [
                      ...previous,
                      {
                        correctionId: saved.correctionId,
                        kind: original?.kind ?? 'undo',
                        saveState: 'saved',
                        undoOf: saved.undoOf,
                        author: original?.author,
                      },
                    ];
                    correctionHistoryRef.current = next;
                    return next;
                  });
                  if (original?.kind === 'event_accept' || original?.kind === 'event_reject') {
                    await applyStoredMatchEvents(matchId, frames);
                    return;
                  }
                  if (original?.kind === 'playlist_item') {
                    return;
                  }
                  await loadWorkspaceIntoState(matchId, { prepend: true, force: true });
                  const heatmap = await fetchHeatmap(matchId);
                  const identity = heatmap.identityContinuous === true;
                  setIdentityContinuous(identity);
                  setHeatmapAvail({
                    wholeMatch: heatmap.wholeMatch === true,
                    intervalLimited: heatmap.intervalLimited !== false,
                    withheld: heatmap.withheld !== false,
                  });
                  setSpeedAvail(speedAvailability(identity));
                  setPlayerTotalsAvail(playerPhysicalTotalsAvailability(identity));
                }).catch(() => {
                  setCorrectionSaveState('unavailable');
                });
              }}
            />
          </div>
          <div className="mb-3 shrink-0">
            <AiUnavailableBanner providersEnabled={providersEnabled} />
          </div>
          <div className="mb-3 shrink-0">
            <LoopbackBanner deploymentBoundary={deploymentBoundary} />
          </div>
          <div className="mb-3 shrink-0">
            <RecoveryPanel
              controllerRecorded={recovery.controllerRecorded}
              unresolvedIncidents={recovery.unresolvedIncidents}
              recoveryObjectivesDefined={recovery.recoveryObjectivesDefined}
              onRequestDeletion={() => {
                void requestAccessDeletion().catch(() => undefined);
              }}
            />
          </div>
          <div className="mb-3 shrink-0">
            <SecurityBoundary
              modelTrusted={security?.modelTrusted}
              hostedEncryptionProven={security?.hostedEncryptionProven}
              signedJobAccessAdmitted={security?.signedJobAccessAdmitted}
            />
          </div>
          <div className="mb-3 shrink-0">
            <ReleaseGate publicExposureAllowed={security?.publicExposureAllowed} />
          </div>
          <div className="mb-3 shrink-0">
            <NativePackaging
              approved={native?.approved}
              rpcFleetEnabled={native?.rpcFleetEnabled}
              universallyPortable={native?.universallyPortable}
              completeRuntimeMemory={native?.completeRuntimeMemory}
            />
          </div>
          <div className="mb-3 shrink-0">
            <DrawingToolbar
              activeMode={review.reviewMode}
              onArrow={review.startArrowPlacement}
              onCircle={review.startCirclePlacement}
              onCancel={review.cancelPlacement}
            />
          </div>

          <div className="mb-3 shrink-0">
            <EvidenceInspector
              matchId={activeMatch?.id}
              frame={currentFrameRecord}
              cameraProfile={activeMatch?.detail.config?.cameraProfile ?? uploadCameraProfile}
              reviewStatus={currentEvent?.reviewStatus ?? 'unreviewed'}
              configVersion={activeMatch?.evidence?.items[0]?.schemaVersion ?? 'evidence_v1'}
              coordinateSpace={activeMatch?.evidence?.coordinateSpace}
              definitionVersion={activeMatch?.evidence?.definitionVersion}
              {...splitScores({
                detectorScore: currentFrameRecord?.Ball?.conf ?? null,
                calibratedProbability: null,
                interval: null,
              })}
            />
          </div>
          <div className="mb-3 shrink-0">
            <IncidentReview
              touchStart={incidentTouchStart}
              touchEnd={incidentTouchEnd}
              samples={incidentSamples}
            />
          </div>
          <div className="mb-3 shrink-0">
            <QualityTimeline items={qualityItems} />
          </div>
          <div className="mb-3 shrink-0">
            <PlaylistBuilder
              matchId={activeMatch?.id}
              reviewRange={review.reviewRange}
              frames={matchData}
              sourceFps={fps}
              storedClips={playlistClipsFromCorrections(correctionHistory)}
              onClipSaved={handleClipSaved}
              onOpenInterval={(timestamp) => {
                setIsPlaying(false);
                const index = findNearestFrameIndex(matchData.map((frame) => frame.Timestamp), timestamp);
                if (index >= 0) handleSeek(matchData[index]?.Frame_ID ?? index);
              }}
            />
          </div>
          <div className="mb-3 shrink-0">
            <MatchPackagePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <FourRatesPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <LoadedMatchSetupPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchMetricInspectorPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchCoveragePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <AnalystWorkflowPanel />
          </div>
          <div className="mb-3 shrink-0">
            <EvaluationProtocolPanel />
          </div>
          <div className="mb-3 shrink-0">
            <EvaluationPrerequisitesPanel />
          </div>
          <div className="mb-3 shrink-0">
            <EvaluationMeasuresPanel />
          </div>
          <div className="mb-3 shrink-0">
            <EvaluationHotaPanel />
          </div>
          <div className="mb-3 shrink-0">
            <CollaborationLockPanel />
          </div>
          <div className="mb-3 shrink-0">
            <MediaStridePanel />
          </div>
          <div className="mb-3 shrink-0">
            <CreditAllocationPanel />
          </div>
          <div className="mb-3 shrink-0">
            <HeldOutQuestionsPanel />
          </div>
          <div className="mb-3 shrink-0">
            <GroundContactPanel />
          </div>
          <div className="mb-3 shrink-0">
            <XtPlanPanel />
          </div>
          <div className="mb-3 shrink-0">
            <RightsRegisterPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ModelRosterPanel />
          </div>
          <div className="mb-3 shrink-0">
            <RiskRegisterPanel />
          </div>
          <div className="mb-3 shrink-0">
            <MilestoneProgressPanel />
          </div>
          <div className="mb-3 shrink-0">
            <NetworkFailureMetricPanel />
          </div>
          <div className="mb-3 shrink-0">
            <MetadataTargetsPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ArchitectureDecisionsPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ResidencyClaimPanel />
          </div>
          <div className="mb-3 shrink-0">
            <DistributedBrokerPanel />
          </div>
          <div className="mb-3 shrink-0">
            <VectorDatabasePanel />
          </div>
          <div className="mb-3 shrink-0">
            <HostedDeploymentPanel />
          </div>
          <div className="mb-3 shrink-0">
            <HandheldAdmissionPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ResearchLanePanel />
          </div>
          <div className="mb-3 shrink-0">
            <ScaleScenarioPanel />
          </div>
          <div className="mb-3 shrink-0">
            <MediaAdmitWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <CostEstimateWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <RollbackWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <TrainingDrillsPanel />
          </div>
          <div className="mb-3 shrink-0">
            <RepositoryPolicyPanel />
          </div>
          <div className="mb-3 shrink-0">
            <SupportBundlePanel />
          </div>
          <div className="mb-3 shrink-0">
            <ObjectStoragePanel />
          </div>
          <div className="mb-3 shrink-0">
            <PreemptiblePolicyPanel />
          </div>
          <div className="mb-3 shrink-0">
            <PitchAxesPanel />
          </div>
          <div className="mb-3 shrink-0">
            <GpuTimingPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ExperimentReceiptPanel />
          </div>
          <div className="mb-3 shrink-0">
            <RecoveryDiskPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ExperimentB5Panel />
          </div>
          <div className="mb-3 shrink-0">
            <RecoveryRestorePanel />
          </div>
          <div className="mb-3 shrink-0">
            <VideoRosterPanel />
          </div>
          <div className="mb-3 shrink-0">
            <FrontierRosterPanel />
          </div>
          <div className="mb-3 shrink-0">
            <PromotionGatePanel />
          </div>
          <div className="mb-3 shrink-0">
            <QualityGateWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <JsonRepairWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <AssistancePolicyWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <WorkerEnvironmentWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <PerceptionScoreWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <InterruptedUploadWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <PseudoLabelWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <EventScoreWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DeploymentChoiceWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <TrainingPromoteWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <TrainingLedgerWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <CacheRecomputeWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <CleanupCompleteWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <TrainingCycleWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <ExperimentPauseWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeFirstWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DetectorWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <TrackerWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <EventProposeWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeExportWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeProbeWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodePixelsWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeCropWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeCutsWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeGridWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeWrapWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeFallbackWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeSampleWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodePtsWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeIntervalWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <PerceptionPreprocessWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <PerceptionStratumWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <PerceptionBallStatesWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <IdentityPreviewWritePanel />
          </div>
          <div className="mb-3 shrink-0">
            <StageTimingPanel />
          </div>
          <div className="mb-3 shrink-0">
            <GpuProbePanel />
          </div>
          <div className="mb-3 shrink-0">
            <IndependentReviewerPanel />
          </div>
          <div className="mb-3 shrink-0">
            <WorkedMatchFlowPanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeMemoryPanel />
          </div>
          <div className="mb-3 shrink-0">
            <IdentityPolicyPanel />
          </div>
          <div className="mb-3 shrink-0">
            <TrainingPoolsPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ShadowMetricPanel />
          </div>
          <div className="mb-3 shrink-0">
            <LegacyDisplayPanel />
          </div>
          <div className="mb-3 shrink-0">
            <MetricDictionaryPanel />
          </div>
          <div className="mb-3 shrink-0">
            <LicenceRegisterPanel />
          </div>
          <div className="mb-3 shrink-0">
            <TelestrationPanel />
          </div>
          <div className="mb-3 shrink-0">
            <DatasetRightsPanel />
          </div>
          <div className="mb-3 shrink-0">
            <MetricRoundTripPanel />
          </div>
          <div className="mb-3 shrink-0">
            <IncidentResponsePanel />
          </div>
          <div className="mb-3 shrink-0">
            <ProviderRosterPanel />
          </div>
          <div className="mb-3 shrink-0">
            <StalePermissionGatePanel />
          </div>
          <div className="mb-3 shrink-0">
            <SignedObjectAccessPanel />
          </div>
          <div className="mb-3 shrink-0">
            <LegacyGeometryPanel />
          </div>
          <div className="mb-3 shrink-0">
            <SplitScoresPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ReleaseDossierPanel />
          </div>
          <div className="mb-3 shrink-0">
            <TrainingSamplingPanel />
          </div>
          <div className="mb-3 shrink-0">
            <DependencyRegisterPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ChallengerAdaptersPanel />
          </div>
          <div className="mb-3 shrink-0">
            <FeatureFlagsPanel />
          </div>
          <div className="mb-3 shrink-0">
            <CapabilityRosterPanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeChallengersPanel />
          </div>
          <div className="mb-3 shrink-0">
            <DecodeFramesPanel />
          </div>
          <div className="mb-3 shrink-0">
            <GpuDefaultEnabledPanel />
          </div>
          <div className="mb-3 shrink-0">
            <LocalOnlyDeploymentPanel />
          </div>
          <div className="mb-3 shrink-0">
            <FinishLineReportPanel />
          </div>
          <div className="mb-3 shrink-0">
            <AcceptanceReportPanel />
          </div>
          <div className="mb-3 shrink-0">
            <OperatorHandoffPanel />
          </div>
          <div className="mb-3 shrink-0">
            <ReleaseReadoutPanel />
          </div>
          <div className="mb-3 shrink-0">
            <PostReleaseMonitoringPanel />
          </div>
          <div className="mb-3 shrink-0">
            <DetectorEvaluationReportPanel />
          </div>
          <div className="mb-3 shrink-0">
            <PromotionReviewReportPanel />
          </div>
          <div className="mb-3 shrink-0">
            <PromotedRuntimeMonitoringPanel />
          </div>
          <div className="mb-3 shrink-0">
            <OperatorDashboardPanel />
          </div>
          <div className="mb-3 shrink-0">
            <RealVideoScaleoutReportPanel />
          </div>
          <div className="mb-3 shrink-0">
            <BoundedNextSampleReportPanel />
          </div>
          <div className="mb-3 shrink-0">
            <MatchProvenancePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchShotQualityPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchShotFeaturesPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchPlayerObservationsPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchEventPartitionPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchIdentityPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchAttackDirectionPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchLegacyRecordsPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchExportPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchThemesPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchAssistanceFallbackPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchCalibrationPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchWriteAlongsidePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchReportRecomputePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchRecoveryImportPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchAssistanceReportPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchTrackletWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchShotFeatureWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchIncidentReviewWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchCacheWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchOwnershipWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchPackageWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchMetricsWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchFormationWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchIdentityWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchPlayerWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchIncidentGeometryWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchIncidentPackageWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchEventPartitionWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchLegacyRecordsWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchAttackDirectionWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchProvenanceWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchShotQualityWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <AnalystWorkflowWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <EvaluationPrerequisitesWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchJobWritePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchAuditTrailPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchPrivacyPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchTrackletsPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchCachePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchPromotionPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchOwnershipPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchIncidentGeometryPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <MatchIncidentPackagePanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <ProxyAssetsPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <HoldoutCalibrationPanel matchId={activeMatch?.id} />
          </div>
          <div className="mb-3 shrink-0">
            <TypedSearchPanel
              matchId={activeMatch?.id}
              onSeek={(timestamp) => {
                setIsPlaying(false);
                const index = findNearestFrameIndex(matchData.map((frame) => frame.Timestamp), timestamp);
                if (index >= 0) handleSeek(matchData[index]?.Frame_ID ?? index);
              }}
            />
          </div>
          <div className="mb-3 flex-1 overflow-y-auto">
            <AnnotationList
              annotations={review.annotations}
              onSeekToAnnotation={review.handleSeekToAnnotation}
              onDeleteAnnotation={review.handleDeleteAnnotation}
            />
          </div>

          <div className="border-t border-slate-700 pt-3 mt-2"></div>

          {matchData.length === 0 ? (
            <div className="text-center text-slate-500 mt-10 p-4 border border-dashed border-slate-700 rounded-lg">
              <p>Waiting for processed match data...</p>
            </div>
          ) : (
            <div className="flex flex-col flex-1 overflow-hidden">
              <div className="flex bg-slate-900 rounded p-0.5 border border-slate-700 mb-3 shrink-0">
                <button
                  onClick={() => coach.selectLlmProvider('local')}
                  className={`flex-1 text-xs py-1.5 rounded transition font-medium ${coach.llmProvider === 'local' ? 'bg-slate-700 text-emerald-400' : 'text-slate-400'}`}
                >
                  Local
                </button>
                <button
                  disabled={!coach.supportsCloudProvider}
                  onClick={() => coach.selectLlmProvider('cloud')}
                  className={`flex-1 text-xs py-1.5 rounded transition font-medium ${coach.llmProvider === 'cloud' ? 'bg-slate-700 text-blue-400' : 'text-slate-400'}`}
                >
                  Cloud
                </button>
              </div>

              <div className="flex bg-slate-900 rounded p-0.5 border border-slate-700 mb-3 shrink-0">
                {(['analysis', 'report', 'drills'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => coach.setActiveTab(tab)}
                    className={`flex-1 text-xs py-1.5 rounded transition font-medium capitalize ${coach.activeTab === tab ? 'bg-slate-700 text-emerald-400' : 'text-slate-400'}`}
                  >
                    {tab === 'analysis' ? 'Analysis' : tab === 'report' ? 'Report' : 'Drills'}
                  </button>
                ))}
              </div>

              <div className="border-t border-slate-700 pt-3 mb-3 shrink-0"></div>

              <div className="flex-1 overflow-y-auto space-y-3 text-sm">
                {coach.activeTab === 'analysis' && (
                  <>
                    <div className="p-3 bg-slate-900 rounded border border-slate-700">
                      <h3 className="text-emerald-500 font-medium mb-1 text-xs">Offside Check</h3>
                      <p className="text-xs text-slate-400 mb-2">Ask the backend analysis engine to inspect the current frame.</p>
                      <button
                        disabled={coach.llmThinking || isPlaying || isTacticalInterpretationPaused}
                        onClick={() => coach.runScenario({ matchId: activeMatch?.id ?? null, currentFrame, scenario: 'offside' })}
                        className="w-full py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded text-xs font-semibold transition"
                      >
                        Run Check
                      </button>
                    </div>

                    <div className="p-3 bg-slate-900 rounded border border-slate-700">
                      <h3 className="text-emerald-500 font-medium mb-1 text-xs">Defense Spacing</h3>
                      <p className="text-xs text-slate-400 mb-2">Analyze horizontal spacing from the persisted frame data.</p>
                      <button
                        disabled={coach.llmThinking || isPlaying || isTacticalInterpretationPaused}
                        onClick={() => coach.runScenario({ matchId: activeMatch?.id ?? null, currentFrame, scenario: 'spacing' })}
                        className="w-full py-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded text-xs font-semibold transition"
                      >
                        Analyze Lines
                      </button>
                    </div>

                    <div className="pt-3 border-t border-slate-700">
                      <p className="text-xs text-slate-400 mb-1">Output:</p>
                      <div className="p-2 bg-slate-900 rounded border border-slate-700 font-mono text-xs text-emerald-400 min-h-[60px] whitespace-pre-wrap">
                        {isTacticalInterpretationPaused
                          ? tacticalPauseMessage
                          : coach.llmThinking
                            ? 'Thinking...'
                            : coach.llmResponse
                              ? JSON.stringify(coach.llmResponse, null, 2)
                              : 'Ready.'}
                      </div>
                    </div>
                  </>
                )}

                {!isTacticalInterpretationPaused && (coach.activeTab === 'report' || coach.activeTab === 'drills') && (
                <CoachInsights
                  activeTab={coach.activeTab === 'report' ? 'report' : 'drills'}
                  llmThinking={coach.llmThinking}
                  matchId={activeMatch?.id ?? null}
                  currentFrame={currentFrame}
                  events={events}
                  tacticalReport={coach.tacticalReport}
                  drillResponse={coach.drillResponse}
                  ballSignalStatus={matchStats?.ballSignalStatus ?? null}
                  onSwitchMatch={loadWorkspaceIntoState}
                  onGenerateReport={() => coach.runScenario({ matchId: activeMatch?.id ?? null, currentFrame, scenario: 'tactical_report' })}
                  onGenerateDrills={() => coach.runScenario({ matchId: activeMatch?.id ?? null, currentFrame, scenario: 'drills' })}
                />
              )}
                {isTacticalInterpretationPaused && coach.activeTab !== 'analysis' && (
                  <div className="rounded-lg border border-slate-700 bg-slate-900/70 p-3 text-xs text-slate-400">
                    Tactical interpretation is paused while the match is waiting on truth prerequisites.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* A.3/A.4 — Issue modal overlay */}
      {showIssuePanel && (
        <ModalDialog label="Match issues" onClose={() => setShowIssuePanel(false)}>
          <div className="w-full max-w-2xl">
            <DemoMatchIssuePanel
              issues={review.issues}
              currentFrame={currentFrame}
              currentTimestamp={currentTimestamp}
              reviewRange={review.reviewRange}
              processingBackend="unknown"
              onCreateIssue={review.handleCreateIssue}
              onSeekToIssue={review.handleSeekToIssue}
              onDeleteIssue={review.handleDeleteIssue}
            />
            <button
              type="button"
              onClick={() => setShowIssuePanel(false)}
              className="mt-3 w-full rounded border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-400 hover:bg-slate-800 transition-colors"
            >
              Close
            </button>
          </div>
        </ModalDialog>
      )}

      {showDashboard && (
        <DashboardPanel
          onClose={() => setShowDashboard(false)}
          onSelectMatch={(matchId) => {
            setShowDashboard(false);
            void loadWorkspaceIntoState(matchId).catch(() => undefined);
          }}
        />
      )}

      {showWorkbench && (
        <WorkbenchPanel
          onClose={() => setShowWorkbench(false)}
          matchId={activeMatch?.id}
          events={(activeMatch?.backendEvents ?? []).map((event) => ({
            id: `${event.type}-${event.timestamp}`,
            type: event.type,
            timestamp: event.timestamp,
            team: event.team,
          }))}
          onSeek={(timestamp) => {
            setShowWorkbench(false);
            setIsPlaying(false);
            const index = findNearestFrameIndex(matchData.map((frame) => frame.Timestamp), timestamp);
            if (index >= 0) handleSeek(matchData[index]?.Frame_ID ?? index);
          }}
        />
      )}

      {showTrustCrop && activeMatch && (
        <>
          <TrustCropPanel
            matchId={activeMatch.id}
            frames={matchData}
            onClose={() => setShowTrustCrop(false)}
            onSeekToCrop={(frame) => {
              setShowTrustCrop(false);
              setIsPlaying(false);
              handleSeek(frame);
            }}
          />
        </>
      )}
    </div>
  );
}
export default App;
