export interface CapabilityEntry {
  id: string;
  label: string;
  status: string;
  evidenceClass: string;
  evidenceLink: string;
  notes: string;
  independentlyVisible: boolean;
}

export interface WorkbenchDossier {
  baseline: {
    selectedCommit: string;
    declaredCameraProfile: string;
    declaredWorkflow: string;
    unresolvedGates: string[];
    permittedNextActions: string[];
    forbiddenActions: string[];
    capabilities: CapabilityEntry[];
    evidenceClasses: Record<string, string>;
  };
  release: {
    deploymentBoundary: string;
    gNetworkRequiredForNonLocal: boolean;
    nativeCode: string;
  };
  evaluation: {
    accepted: boolean;
    completeTasks: number;
    requiredTasks: number;
    reasonCodes: string[];
  };
  gpu: {
    available: boolean;
    canPromoteDefault: boolean;
    reasonCodes: string[];
  };
  native: {
    approved: boolean;
    reasonCodes: string[];
  };
}

export interface MetricAvailability {
  metric: string;
  definitionVersion: string;
  value: number | null;
  availability: string;
  reasonCodes: string[];
  unit?: string | null;
  denominator?: string | null;
  eligibleSeconds?: number;
}

export interface WorkbenchFlags {
  experimental_shot_quality: boolean;
  gpu_default: boolean;
  native_code: boolean;
  experimental_ui: boolean;
  embeddings_search: boolean;
}

export interface JobCostSummary {
  reservedTotal: number;
  actualTotal: number;
  p50Reserved: number;
}

export async function fetchWorkbenchDossier(): Promise<WorkbenchDossier> {
  const response = await fetch('/api/dossier');
  if (!response.ok) {
    throw new Error(`Failed to load workbench dossier: ${response.status}`);
  }
  return response.json() as Promise<WorkbenchDossier>;
}

export async function searchWorkbenchEvents(query: string, matchId: string, events: Array<Record<string, unknown>> = []) {
  void events;
  const response = await fetch(`/api/matches/${matchId}/queries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    throw new Error(`Failed to run typed search: ${response.status}`);
  }
  return response.json() as Promise<{
    query: { unanswerable: boolean; reason: string | null; eventFamily: string };
    results: Array<{ eventId: string; timestamp: number; evidenceIds: string[] }>;
  }>;
}

export async function submitMatchCorrection(
  matchId: string,
  body: { kind: string; payload?: Record<string, unknown>; expectedVersion?: number; author?: string },
) {
  const response = await fetch(`/api/matches/${matchId}/corrections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Failed to save correction: ${response.status}`);
  }
  return response.json() as Promise<{ correctionId: string; saveState: string; version?: number }>;
}

export async function fetchPendingCorrections(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/corrections?state=pending`);
  if (!response.ok) {
    throw new Error(`Failed to load pending corrections: ${response.status}`);
  }
  return response.json() as Promise<{ items: Array<{ correctionId: string; kind: string; saveState: string; payload?: Record<string, unknown> | null }> }>;
}

export async function recoverMatchCorrection(matchId: string, correctionId: string) {
  const response = await fetch(`/api/matches/${matchId}/corrections/${correctionId}/recover`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to recover correction: ${response.status}`);
  }
  return response.json() as Promise<{ correctionId: string; saveState: string }>;
}

export async function undoMatchCorrection(matchId: string, correctionId: string) {
  const response = await fetch(`/api/matches/${matchId}/corrections/${correctionId}/undo`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to undo correction: ${response.status}`);
  }
  return response.json() as Promise<{ correctionId: string; undoOf: string }>;
}

export async function exportPlaylistInterval(timestampStart: number, timestampEnd: number, sourceFps: number) {
  const response = await fetch('/api/playlists/export-interval', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ timestampStart, timestampEnd, sourceFps }),
  });
  if (!response.ok) {
    throw new Error(`Failed to export playlist interval: ${response.status}`);
  }
  return response.json() as Promise<{ sourceStartSeconds: number; sourceEndSeconds: number; sourceEndFrameExclusive: number }>;
}

export async function fetchWorkbenchFlags() {
  const response = await fetch('/api/flags');
  if (!response.ok) {
    throw new Error(`Failed to load feature flags: ${response.status}`);
  }
  return response.json() as Promise<WorkbenchFlags>;
}

export async function fetchJobCost(jobId: string) {
  const response = await fetch(`/api/jobs/${jobId}/cost`);
  if (!response.ok) {
    throw new Error(`Failed to load job cost: ${response.status}`);
  }
  return response.json() as Promise<JobCostSummary>;
}

export async function searchMatchLibrary(query: string) {
  const response = await fetch('/api/library/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    throw new Error(`Failed to search match library: ${response.status}`);
  }
  return response.json() as Promise<{ results: Array<{ id: string; title?: string }> }>;
}

export async function fetchPlayerObservations(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/players`);
  if (!response.ok) {
    throw new Error(`Failed to load player observations: ${response.status}`);
  }
  return response.json() as Promise<{ intervalLimited: boolean; totalsWithheld: boolean; reasonCodes: string[]; rows?: Array<{ trackId?: string }> }>;
}

export async function postPlayerObservations(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/players`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post player observations: ${response.status}`);
  }
  return response.json() as Promise<{ intervalLimited: boolean; totalsWithheld: boolean; reasonCodes: string[]; rows?: Array<{ trackId?: string }> }>;
}

export interface MatchSetup {
  cameraProfile: string;
  automationAdmitted: boolean;
  manualTaggingPermitted: boolean;
  cannotMeasure: string[];
  certified: boolean;
  pitchLengthM: number | null;
}

export interface MetricInspect {
  metric: string;
  unit: string | null;
  denominator: string | null;
  definitionVersion: string;
  eligibleDuration: number;
  exclusions: string[];
  rendered: string;
  publishedValue: number | null;
}

export async function fetchMatchSetup(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/setup`);
  if (!response.ok) {
    throw new Error(`Failed to load match setup: ${response.status}`);
  }
  return response.json() as Promise<MatchSetup>;
}

export async function fetchMetricInspect(metric: string, matchId?: string) {
  const url = matchId ? `/api/matches/${matchId}/metrics/inspect/${metric}` : `/api/metrics/inspect/${metric}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to inspect metric: ${response.status}`);
  }
  return response.json() as Promise<MetricInspect>;
}

export async function fetchMatchMetrics(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/metrics`);
  if (!response.ok) {
    throw new Error(`Failed to load match metrics: ${response.status}`);
  }
  return response.json() as Promise<{ metrics: MetricAvailability[] }>;
}

export async function postMatchMetrics(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/metrics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match metrics: ${response.status}`);
  }
  return response.json() as Promise<{ metrics: MetricAvailability[] }>;
}

export async function fetchTrainingDrills() {
  const response = await fetch('/api/training/drills');
  if (!response.ok) {
    throw new Error(`Failed to load training drills: ${response.status}`);
  }
  return response.json() as Promise<{ items: Array<{ name: string; coachReviewed?: boolean }>; prescribesMedicalLoad: boolean; diagnosesFatigueOrInjury: boolean }>;
}

export async function fetchJobView(jobId: string) {
  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(`Failed to load job: ${response.status}`);
  }
  return response.json() as Promise<{
    status?: string;
    durablePhase?: string | null;
    costReserved?: number;
    costActual?: number;
    cleanupResult?: string;
    cancelRequested?: boolean;
  }>;
}

export async function fetchMatchClock(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/clock`);
  if (!response.ok) {
    throw new Error(`Failed to load match clock: ${response.status}`);
  }
  return response.json() as Promise<{
    presentationTimeSeconds: number;
    matchClockSeconds: number;
    frameAccurateOverlay: boolean;
    explicitMapping?: boolean;
    sourceClockRecorded?: boolean;
  }>;
}

export async function fetchIncidentReview(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/incidents/review`);
  if (!response.ok) {
    throw new Error(`Failed to load incident review: ${response.status}`);
  }
  return response.json() as Promise<{
    level: number;
    decision: string | null;
    validatedMeasurement: boolean;
    touchInterval?: [number, number];
    samples: Array<{ time: number; attackerX: number; offsideLineX: number; indeterminate: boolean }>;
  }>;
}

export async function postIncidentReview(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/incidents/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post incident review: ${response.status}`);
  }
  return response.json() as Promise<{
    level: number;
    decision: string | null;
    validatedMeasurement: boolean;
  }>;
}

export interface MatchEventPartition {
  acceptedViews?: Array<Record<string, unknown>>;
  retainedCandidates?: Array<Record<string, unknown>>;
  rejectedRemovedFromAcceptedViews: boolean;
}

export async function fetchMatchEventPartition(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/events/partition`);
  if (!response.ok) {
    throw new Error(`Failed to load match event partition: ${response.status}`);
  }
  return response.json() as Promise<MatchEventPartition>;
}

export async function postMatchEventPartition(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/events/partition`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match event partition: ${response.status}`);
  }
  return response.json() as Promise<MatchEventPartition>;
}

export interface MatchIdentity {
  reset?: boolean;
  silentlyReconnected: boolean;
  cutCount?: number;
  identityContinuous: boolean;
  reasonCodes?: string[];
}

export async function fetchMatchIdentity(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/identity`);
  if (!response.ok) {
    throw new Error(`Failed to load match identity: ${response.status}`);
  }
  return response.json() as Promise<MatchIdentity>;
}

export async function postMatchIdentity(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/identity`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match identity: ${response.status}`);
  }
  return response.json() as Promise<MatchIdentity>;
}

export interface MatchAttackDirection {
  direction: string | null;
  fromStoredConfig: boolean;
  team?: string;
  period?: number;
}

export async function fetchMatchAttackDirection(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/attack-direction`);
  if (!response.ok) {
    throw new Error(`Failed to load match attack direction: ${response.status}`);
  }
  return response.json() as Promise<MatchAttackDirection>;
}

export async function postMatchAttackDirection(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/attack-direction`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match attack direction: ${response.status}`);
  }
  return response.json() as Promise<MatchAttackDirection>;
}

export interface MatchLegacyMigrate {
  migrated?: { possession_pct?: { availability?: string } };
  rollback?: { possession?: number | null; myTeamDistance?: number | null };
  rewrotePastOutcomes: boolean;
}

export async function fetchMatchLegacyMigrate(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/records/migrate`);
  if (!response.ok) {
    throw new Error(`Failed to load match legacy records: ${response.status}`);
  }
  return response.json() as Promise<MatchLegacyMigrate>;
}

export async function postMatchLegacyMigrate(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/records/migrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match legacy records: ${response.status}`);
  }
  return response.json() as Promise<MatchLegacyMigrate>;
}

export interface MatchExportBundle {
  schemaVersion: string;
  provenance?: { storageArtifactsAreSourceOfTruth?: boolean; llmGenerated?: boolean };
  exports?: {
    matchJson?: string;
    framesCsv?: string;
    eventsCsv?: string;
    metricsCsv?: string;
  };
}

export async function fetchMatchExport(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/export/match.json`);
  if (!response.ok) {
    throw new Error(`Failed to load match export: ${response.status}`);
  }
  return response.json() as Promise<MatchExportBundle>;
}

export interface MatchThemes {
  matchId?: string;
  detectedThemes: string[];
  themeDetails?: Record<string, number>;
}

export async function fetchMatchThemes(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/themes`);
  if (!response.ok) {
    throw new Error(`Failed to load match themes: ${response.status}`);
  }
  return response.json() as Promise<MatchThemes>;
}

export interface MatchAssistanceFallback {
  route: string;
  reasonCodes?: string[];
  reviewOperational: boolean;
  output?: { kind?: string };
}

export async function fetchMatchAssistanceFallback(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/assistance/fallback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to load match assistance fallback: ${response.status}`);
  }
  return response.json() as Promise<MatchAssistanceFallback>;
}

export interface MatchCalibration {
  fromStoredPoints: boolean;
  measured: boolean;
  evaluation?: { accepted?: boolean };
  residualP95M?: number | null;
}

export async function fetchMatchCalibration(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/calibration`);
  if (!response.ok) {
    throw new Error(`Failed to load match calibration: ${response.status}`);
  }
  return response.json() as Promise<MatchCalibration>;
}

export async function fetchCorrectionHistory(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/corrections`);
  if (!response.ok) {
    throw new Error(`Failed to load correction history: ${response.status}`);
  }
  return response.json() as Promise<{
    items: Array<{
      correctionId: string;
      kind: string;
      saveState: string;
      undoOf?: string | null;
      author?: string;
      payload?: Record<string, unknown> | null;
    }>;
  }>;
}

export interface RecoverySnapshot {
  deletion: { available: boolean; executed: boolean; trackIdsDoNotAnonymise: boolean; reasonCodes: string[] };
  unresolvedIncidents: {
    items: Array<{ id: string; title: string }>;
    operatorVisible: boolean;
    enterpriseUptimePromised: boolean;
  };
  recoveryObjectives: { defined: boolean; enterpriseUptimePromised: boolean; reasonCodes: string[] };
  stalePermissions: { stale: boolean; admitted: boolean; reasonCodes: string[] };
}

export async function fetchRecovery() {
  const response = await fetch('/api/recovery');
  if (!response.ok) {
    throw new Error(`Failed to load recovery state: ${response.status}`);
  }
  return response.json() as Promise<RecoverySnapshot>;
}

export async function requestAccessDeletion() {
  const response = await fetch('/api/access/deletion', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requested: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to request deletion: ${response.status}`);
  }
  return response.json() as Promise<{ executed: boolean; available: boolean; reasonCodes: string[] }>;
}

export interface LandmarkPreview {
  residualP95M: number | null;
  accepted: boolean;
  committed: boolean;
  measured?: boolean;
  visionRerun?: boolean;
  preview?: boolean;
  reasonCodes?: string[];
}

export async function fetchLandmarkPreview(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/setup/preview`);
  if (!response.ok) {
    throw new Error(`Failed to load landmark preview: ${response.status}`);
  }
  return response.json() as Promise<LandmarkPreview>;
}

export interface QualityTimelinePayload {
  reviewFirst: boolean;
  accepted: boolean;
  measured: boolean;
  items: Array<{ id: string; label: string; impact: string; accepted?: boolean }>;
}

export async function fetchQualityTimeline(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/quality`);
  if (!response.ok) {
    throw new Error(`Failed to load quality timeline: ${response.status}`);
  }
  return response.json() as Promise<QualityTimelinePayload>;
}

export interface AssistanceSnapshot {
  providersEnabled: boolean;
  reviewOperational: boolean;
  metricsOperational: boolean;
  templateReportOperational: boolean;
  route: string;
}

export async function fetchAssistance() {
  const response = await fetch('/api/assistance');
  if (!response.ok) {
    throw new Error(`Failed to load assistance state: ${response.status}`);
  }
  return response.json() as Promise<AssistanceSnapshot>;
}

export interface SecuritySnapshot {
  modelOutput?: { trusted?: boolean };
  publicExposure?: { admitted?: boolean; publicExposureAllowed?: boolean };
  encryption?: { hostedEncryptionProven?: boolean };
  signedJobAccess?: { admitted?: boolean };
  secretsAdmitted?: boolean;
}

export async function fetchSecurity() {
  const response = await fetch('/api/security');
  if (!response.ok) {
    throw new Error(`Failed to load security boundary: ${response.status}`);
  }
  return response.json() as Promise<SecuritySnapshot>;
}

export interface NativeSnapshot {
  approved?: boolean;
  rpcFleet?: { enabled?: boolean };
  pinned?: { universallyPortable?: boolean; admitted?: boolean };
  customNative?: { approved?: boolean };
}

export async function fetchNative() {
  const response = await fetch('/api/native');
  if (!response.ok) {
    throw new Error(`Failed to load native packaging: ${response.status}`);
  }
  return response.json() as Promise<NativeSnapshot>;
}

export interface PitchAxes {
  x: string;
  y: string;
  origin: string;
  legacyDisplay: string;
}

export async function fetchPitchAxes() {
  const response = await fetch('/api/quantities/axes');
  if (!response.ok) {
    throw new Error(`Failed to load pitch axes: ${response.status}`);
  }
  return response.json() as Promise<PitchAxes>;
}

export interface FormationAvailability {
  availability: string;
  reasonCodes?: string[];
  value?: string | null;
}

export async function fetchMatchFormation(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/formation`);
  if (!response.ok) {
    throw new Error(`Failed to load formation availability: ${response.status}`);
  }
  return response.json() as Promise<FormationAvailability>;
}

export async function postMatchFormation(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/formation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post formation availability: ${response.status}`);
  }
  return response.json() as Promise<FormationAvailability>;
}

export interface GpuTimingSnapshot {
  admitted?: boolean;
  usesSubmissionAsCompletedWork?: boolean;
  completedMs?: number | null;
  reasonCodes?: string[];
}

export async function fetchGpuTiming() {
  const response = await fetch('/api/timing/gpu');
  if (!response.ok) {
    throw new Error(`Failed to load GPU timing: ${response.status}`);
  }
  return response.json() as Promise<GpuTimingSnapshot>;
}

export interface NativeMemorySnapshot {
  completeRuntimeMemory?: boolean;
  admitted?: boolean;
  reasonCodes?: string[];
}

export async function fetchNativeMemory() {
  const response = await fetch('/api/native/memory');
  if (!response.ok) {
    throw new Error(`Failed to load native memory policy: ${response.status}`);
  }
  return response.json() as Promise<NativeMemorySnapshot>;
}

export interface CapacitySnapshot {
  seconds?: number;
  billableCurrentSource?: boolean;
  exportFpsEqualsInferenceFps?: boolean;
}

export async function fetchCapacity() {
  const response = await fetch('/api/capacity');
  if (!response.ok) {
    throw new Error(`Failed to load capacity: ${response.status}`);
  }
  return response.json() as Promise<CapacitySnapshot>;
}

export interface RepositorySnapshot {
  httpMayRunGpu?: boolean;
  vectorBrokerRequired?: boolean;
  replacesStorageModule?: boolean;
}

export async function fetchRepository() {
  const response = await fetch('/api/repository');
  if (!response.ok) {
    throw new Error(`Failed to load repository policy: ${response.status}`);
  }
  return response.json() as Promise<RepositorySnapshot>;
}

export interface SupportBundleSnapshot {
  released?: boolean;
  reasonCodes?: string[];
}

export async function fetchSupportBundle() {
  const response = await fetch('/api/support/bundle');
  if (!response.ok) {
    throw new Error(`Failed to load support bundle policy: ${response.status}`);
  }
  return response.json() as Promise<SupportBundleSnapshot>;
}

export interface ObjectStorageSnapshot {
  enabled?: boolean;
  mandatoryDuckDb?: boolean;
  role?: string;
}

export async function fetchObjectStorage() {
  const response = await fetch('/api/storage/object');
  if (!response.ok) {
    throw new Error(`Failed to load object storage policy: ${response.status}`);
  }
  return response.json() as Promise<ObjectStorageSnapshot>;
}

export interface ExperimentReceiptSnapshot {
  experiment?: string;
  promoted?: boolean;
  hardwareVerified?: boolean;
  reasonCodes?: string[];
}

export async function fetchExperiment(experiment: string) {
  const response = await fetch(`/api/experiments/${experiment}`);
  if (!response.ok) {
    throw new Error(`Failed to load experiment receipt: ${response.status}`);
  }
  return response.json() as Promise<ExperimentReceiptSnapshot>;
}

export interface PreemptibleSnapshot {
  allowed?: boolean;
}

export async function fetchPreemptible() {
  const response = await fetch('/api/preemptible');
  if (!response.ok) {
    throw new Error(`Failed to load preemptible policy: ${response.status}`);
  }
  return response.json() as Promise<PreemptibleSnapshot>;
}

export interface LabelProductsSnapshot {
  cvat?: { sameProductAsCorrections?: boolean };
  in_app_corrections?: { role?: string };
}

export async function fetchLabelProducts() {
  const response = await fetch('/api/roster/labels');
  if (!response.ok) {
    throw new Error(`Failed to load label products: ${response.status}`);
  }
  return response.json() as Promise<LabelProductsSnapshot>;
}

export interface ProxyAssetsSnapshot {
  replacesOriginal?: boolean;
  originalRetained?: boolean;
  assets?: {
    proxy?: { kind?: string; height?: number; streamCopy?: boolean };
    thumbnails?: { kind?: string; count?: number };
    waveform?: { kind?: string };
  };
  ptsMap?: Array<{
    originalPts?: number;
    proxyPts?: number;
    originalSeconds?: number;
    proxySeconds?: number;
  }>;
  frameExactExport?: { validatedDecodeReencode?: boolean; keyframeSeekIsExact?: boolean };
}

export async function fetchMatchProxy(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/media/proxy`);
  if (!response.ok) {
    throw new Error(`Failed to load proxy assets: ${response.status}`);
  }
  return response.json() as Promise<ProxyAssetsSnapshot>;
}

export interface EditListSnapshot {
  reencodeFullMatch?: boolean;
  renderOnDemand?: boolean;
  intervals?: Array<[number, number] | { start: number; end: number }>;
}

export async function fetchMatchEdits(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/edits`);
  if (!response.ok) {
    throw new Error(`Failed to load edit list: ${response.status}`);
  }
  return response.json() as Promise<EditListSnapshot>;
}

export interface MatchEditRender {
  interval?: [number, number] | { start: number; end: number };
  reencodedFullMatch: boolean;
  sourceSha256?: string;
}

export async function renderMatchEdit(matchId: string, start: number, end: number) {
  const response = await fetch(`/api/matches/${matchId}/edits/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start, end }),
  });
  if (!response.ok) {
    throw new Error(`Failed to render match edit: ${response.status}`);
  }
  return response.json() as Promise<MatchEditRender>;
}

export interface MatchWriteAlongside {
  digest: string;
  previousDigest: string;
  mutatedHistorical: boolean;
  namespace?: string;
}

export async function writeMatchAlongside(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/artifacts/alongside`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to write alongside artifacts: ${response.status}`);
  }
  return response.json() as Promise<MatchWriteAlongside>;
}

export interface MatchReportRecompute {
  visionInvoked: boolean;
  reused?: boolean;
  admitted?: boolean;
  imageSpaceDetectionsReused?: boolean;
}

export async function recomputeMatchReport(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/recompute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to recompute match report: ${response.status}`);
  }
  return response.json() as Promise<MatchReportRecompute>;
}

export interface MatchRecoveryImport {
  accepted: boolean;
  reasonCodes?: string[];
}

export async function importMatchRecovery(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/recovery/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to import match recovery artifact: ${response.status}`);
  }
  return response.json() as Promise<MatchRecoveryImport>;
}

export interface MatchAssistanceReport {
  factualCheck?: { accepted?: boolean; reasonCodes?: string[] };
}

export async function postMatchAssistanceReport(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/assistance/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to assemble match assistance report: ${response.status}`);
  }
  return response.json() as Promise<MatchAssistanceReport>;
}

export interface MatchPackageSnapshot {
  analyst?: {
    playlist?: unknown[];
    events?: unknown[];
    metrics?: unknown[];
    coverage?: { unknownMetrics?: unknown[] };
    limitations?: string[];
  };
  operator?: {
    manifest?: { schema?: string; sourceSnapshot?: string };
    secretsAdmitted?: boolean;
    cleanupStatus?: string;
  };
}

export async function fetchMatchPackage(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/package`);
  if (!response.ok) {
    throw new Error(`Failed to load match package: ${response.status}`);
  }
  return response.json() as Promise<MatchPackageSnapshot>;
}

export async function postMatchPackage(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/package`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match package: ${response.status}`);
  }
  return response.json() as Promise<MatchPackageSnapshot>;
}

export interface MatchReportCoverage {
  coverageAware: boolean;
  representsWholeMatch: boolean;
}

export async function fetchMatchCoverage(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/reports/coverage`);
  if (!response.ok) {
    throw new Error(`Failed to load match coverage: ${response.status}`);
  }
  return response.json() as Promise<MatchReportCoverage>;
}

export interface MatchReportProvenance {
  accepted: boolean;
  reasonCodes?: string[];
  missingEvidenceIds?: string[];
}

export async function fetchMatchProvenance(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/reports/provenance`);
  if (!response.ok) {
    throw new Error(`Failed to load match provenance: ${response.status}`);
  }
  return response.json() as Promise<MatchReportProvenance>;
}

export async function postMatchProvenance(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/reports/provenance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match provenance: ${response.status}`);
  }
  return response.json() as Promise<MatchReportProvenance>;
}

export interface MatchShotQuality {
  publishedLabel: string;
  calibratedXg: boolean;
  items?: Array<{ publishedLabel?: string; availability?: string; reasonCodes?: string[] }>;
}

export async function fetchMatchShotQuality(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/shots/quality`);
  if (!response.ok) {
    throw new Error(`Failed to load match shot quality: ${response.status}`);
  }
  return response.json() as Promise<MatchShotQuality>;
}

export async function postMatchShotQuality(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/shots/quality`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match shot quality: ${response.status}`);
  }
  return response.json() as Promise<MatchShotQuality>;
}

export interface MatchShotFeatures {
  recorded: boolean;
  missing?: string[];
  imputedAsCalibrated: boolean;
}

export async function fetchMatchShotFeatures(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/shots/features`);
  if (!response.ok) {
    throw new Error(`Failed to load match shot features: ${response.status}`);
  }
  return response.json() as Promise<MatchShotFeatures>;
}

export async function postMatchShotFeatures(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/shots/features`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match shot features: ${response.status}`);
  }
  return response.json() as Promise<MatchShotFeatures>;
}

export interface MatchAuditTrail {
  undoable: boolean;
  rewrotePastOutcomes: boolean;
  items?: unknown[];
}

export async function fetchMatchHistory(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/history`);
  if (!response.ok) {
    throw new Error(`Failed to load match history: ${response.status}`);
  }
  return response.json() as Promise<MatchAuditTrail>;
}

export interface MatchPrivacyScreen {
  cloudAllowed: boolean;
  localProcessingRequired: boolean;
  faceRecognition: boolean;
  crossSeasonIdentity?: boolean;
}

export async function fetchMatchPrivacy(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/privacy`);
  if (!response.ok) {
    throw new Error(`Failed to load match privacy: ${response.status}`);
  }
  return response.json() as Promise<MatchPrivacyScreen>;
}

export interface MatchTracklets {
  assignment?: { kind?: string; forced?: boolean; rosterId?: string | null };
  chunk?: { silentlyReconnected?: boolean };
  silentlyReconnected?: boolean;
}

export async function fetchMatchTracklets(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/tracklets`);
  if (!response.ok) {
    throw new Error(`Failed to load match tracklets: ${response.status}`);
  }
  return response.json() as Promise<MatchTracklets>;
}

export async function postMatchTracklets(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/tracklets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match tracklets: ${response.status}`);
  }
  return response.json() as Promise<MatchTracklets>;
}

export interface MatchCacheIdentity {
  namespace: string;
  compatibleWithDevelopment: boolean;
}

export async function fetchMatchCache(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/cache`);
  if (!response.ok) {
    throw new Error(`Failed to load match cache identity: ${response.status}`);
  }
  return response.json() as Promise<MatchCacheIdentity>;
}

export async function postMatchCache(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/cache`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match cache identity: ${response.status}`);
  }
  return response.json() as Promise<MatchCacheIdentity>;
}

export interface MatchPromotionReceipt {
  completeMatchAccepted: boolean;
  stageBenchmarkIsCompleteMatchAcceptance?: boolean;
  outputQuality: string;
}

export async function fetchMatchPromotion(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/promotion`);
  if (!response.ok) {
    throw new Error(`Failed to load match promotion receipt: ${response.status}`);
  }
  return response.json() as Promise<MatchPromotionReceipt>;
}

export interface MatchOwnership {
  mode: string;
  reasonCodes?: string[];
}

export async function fetchMatchOwnership(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/ownership`);
  if (!response.ok) {
    throw new Error(`Failed to load match ownership: ${response.status}`);
  }
  return response.json() as Promise<MatchOwnership>;
}

export async function postMatchOwnership(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/ownership`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match ownership: ${response.status}`);
  }
  return response.json() as Promise<MatchOwnership>;
}

export interface MatchIncidentGeometry {
  decision: string | null;
  validatedMeasurement: boolean;
  reasonCodes?: string[];
  mostAdvancedTeammateX?: number | null;
  secondLastOpponentX?: number | null;
}

export async function fetchMatchIncidentGeometry(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/incidents/geometry`);
  if (!response.ok) {
    throw new Error(`Failed to load match incident geometry: ${response.status}`);
  }
  return response.json() as Promise<MatchIncidentGeometry>;
}

export async function postMatchIncidentGeometry(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/incidents/geometry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match incident geometry: ${response.status}`);
  }
  return response.json() as Promise<MatchIncidentGeometry>;
}

export interface MatchIncidentPackage {
  level: number;
  clips?: Array<Record<string, unknown>>;
  notes?: string[];
  decision: string | null;
  validatedMeasurement: boolean;
  reasonCodes?: string[];
}

export async function fetchMatchIncidentPackage(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/incidents/package`);
  if (!response.ok) {
    throw new Error(`Failed to load match incident package: ${response.status}`);
  }
  return response.json() as Promise<MatchIncidentPackage>;
}

export async function postMatchIncidentPackage(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/incidents/package`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to post match incident package: ${response.status}`);
  }
  return response.json() as Promise<MatchIncidentPackage>;
}

export interface AnalystWorkflowSnapshot {
  measured?: boolean;
  analystCompletedReviewedMatch?: boolean;
  reasonCodes?: string[];
}

export async function fetchAnalystWorkflow() {
  const response = await fetch('/api/evaluation/workflow');
  if (!response.ok) {
    throw new Error(`Failed to load analyst workflow measures: ${response.status}`);
  }
  return response.json() as Promise<AnalystWorkflowSnapshot>;
}

export interface ShadowMetricSnapshot {
  default?: boolean;
  shadowed?: boolean;
  published?: boolean;
}

export async function fetchShadowMetric(name: string) {
  const response = await fetch(`/api/flags/shadow/${name}`);
  if (!response.ok) {
    throw new Error(`Failed to load shadowed metric: ${response.status}`);
  }
  return response.json() as Promise<ShadowMetricSnapshot>;
}

export interface TrainingPoolsSnapshot {
  pools?: string[];
}

export async function fetchTrainingPools() {
  const response = await fetch('/api/training/pools');
  if (!response.ok) {
    throw new Error(`Failed to load training pools: ${response.status}`);
  }
  return response.json() as Promise<TrainingPoolsSnapshot>;
}

export interface WorkerEnvironmentSnapshot {
  NAMESPACE?: string;
  REQUEST_ID?: string;
}

export async function fetchWorkerEnvironment() {
  const response = await fetch('/api/worker/environment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hostSecret: 'must-not-leak' }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load worker environment: ${response.status}`);
  }
  return response.json() as Promise<WorkerEnvironmentSnapshot>;
}

export interface PerceptionScoreSnapshot {
  labelsIndependent?: boolean;
  notes?: string[];
}

export async function fetchPerceptionScore() {
  const response = await fetch('/api/perception/score', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ labelsIndependent: true, detections: [], labels: [] }),
  });
  if (!response.ok) {
    throw new Error(`Failed to score detections: ${response.status}`);
  }
  return response.json() as Promise<PerceptionScoreSnapshot>;
}

export interface PseudoLabelSnapshot {
  independentGroundTruth?: boolean;
  approved?: boolean;
}

export async function fetchPseudoLabel() {
  const response = await fetch('/api/training/pseudo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suggestion: 'player', approved: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load pseudo-label policy: ${response.status}`);
  }
  return response.json() as Promise<PseudoLabelSnapshot>;
}

export interface InterruptedUploadSnapshot {
  accepted?: boolean;
  quarantined?: boolean;
}

export async function fetchInterruptedUpload() {
  const response = await fetch('/api/upload/interrupt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ accepted: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load interrupted upload policy: ${response.status}`);
  }
  return response.json() as Promise<InterruptedUploadSnapshot>;
}

export interface CalibrationHoldoutSnapshot {
  accepted?: boolean;
  holdoutCount?: number;
  reasonCodes?: string[];
}

export async function fetchCalibrationHoldout() {
  const response = await fetch('/api/geometry/landmarks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ accepted: true, independentHoldout: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load calibration holdout: ${response.status}`);
  }
  return response.json() as Promise<CalibrationHoldoutSnapshot>;
}

export interface EventScoreSnapshot {
  labelsIndependent?: boolean;
  toleranceSeconds?: number;
}

export async function fetchEventScore() {
  const response = await fetch('/api/events/score', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ labelsIndependent: true, predictions: [], labels: [] }),
  });
  if (!response.ok) {
    throw new Error(`Failed to score events: ${response.status}`);
  }
  return response.json() as Promise<EventScoreSnapshot>;
}

export interface DeploymentChoiceSnapshot {
  selected?: string;
  alwaysOnGpuCommitted?: boolean;
}

export async function fetchDeploymentChoice() {
  const response = await fetch('/api/costs/deployment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alwaysOnGpuCommitted: true, privacyRequired: false }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load deployment choice: ${response.status}`);
  }
  return response.json() as Promise<DeploymentChoiceSnapshot>;
}

export interface EvaluationProtocolSnapshot {
  accepted?: boolean;
  completeTasks?: number;
  protocolVersion?: string;
  reasonCodes?: string[];
}

export async function fetchEvaluationProtocol() {
  const response = await fetch('/api/evaluation/protocol', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ accepted: true, completeTasks: 18 }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load evaluation protocol: ${response.status}`);
  }
  return response.json() as Promise<EvaluationProtocolSnapshot>;
}

export interface FeatureEnabledSnapshot {
  name?: string;
  enabled?: boolean;
}

export async function fetchGpuDefaultFlag() {
  const response = await fetch('/api/flags/gpu_default/enabled', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load GPU flag: ${response.status}`);
  }
  return response.json() as Promise<FeatureEnabledSnapshot>;
}

export interface FourRatesSnapshot {
  exportFpsEqualsInferenceFps?: boolean;
  notes?: string[];
}

export async function fetchFourRates() {
  const response = await fetch('/api/rates/four', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ exportFpsEqualsInferenceFps: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load four rates: ${response.status}`);
  }
  return response.json() as Promise<FourRatesSnapshot>;
}

export interface MatchRatesSnapshot {
  decodeCount?: number;
  detectorPrimaryCount?: number;
  detectorRecoveryCount?: number;
  trackerUpdateCount?: number;
  exportCount?: number;
  exportFpsEqualsInferenceFps?: boolean;
  decodeFpsEqualsExportFps?: boolean;
  notes?: string[];
}

export async function fetchMatchRates(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/rates`);
  if (!response.ok) {
    throw new Error(`Failed to load match rates: ${response.status}`);
  }
  return response.json() as Promise<MatchRatesSnapshot>;
}

export interface DecodeFramesSnapshot {
  backend?: string;
  defaultBackend?: string;
  pyavDefault?: boolean;
  torchcodecDefault?: boolean;
  device?: string;
  indexes?: number[];
}

export async function fetchDecodeFrames() {
  const response = await fetch('/api/decode/frames', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ backend: 'pyav', device: 'cuda', frames: [{ sourceFrameIndex: 99 }] }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load decode frames: ${response.status}`);
  }
  return response.json() as Promise<DecodeFramesSnapshot>;
}

export interface ChallengerAdaptersSnapshot {
  kloppy?: { enabled?: boolean; replacesInternalProvenance?: boolean };
  roboflow?: { enabled?: boolean; name?: string };
  mcbyte?: { enabled?: boolean; default?: boolean };
}

export async function fetchChallengers() {
  const response = await fetch('/api/challengers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kloppy: true, enabled: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load challengers: ${response.status}`);
  }
  return response.json() as Promise<ChallengerAdaptersSnapshot>;
}

export interface HeatmapSnapshot {
  identityContinuous?: boolean;
  wholeMatch?: boolean;
  intervalLimited?: boolean;
  withheld?: boolean;
  reasonCodes?: string[];
}

export async function fetchHeatmap(matchId?: string) {
  const response = await fetch(matchId ? `/api/matches/${matchId}/heatmap` : '/api/heatmap', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to load heatmap availability: ${response.status}`);
  }
  return response.json() as Promise<HeatmapSnapshot>;
}

export interface AssembleReportSnapshot {
  factualCheck?: { accepted?: boolean; reasonCodes?: string[] };
  publication?: {
    accepted?: boolean;
    requiresAnalyst?: boolean;
    wholeMatchFrequency?: boolean;
    frequencyRequiresDenominator?: boolean;
  };
}

export async function assembleMatchReport(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Failed to assemble match report: ${response.status}`);
  }
  return response.json() as Promise<AssembleReportSnapshot>;
}

export async function promoteMatchIdentity(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/identity/promote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewed: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to promote match identity: ${response.status}`);
  }
  return response.json() as Promise<{
    committed: boolean;
    preview: boolean;
    identityContinuous: boolean;
    silentlyReconnected: boolean;
    visionRerun: boolean;
    reasonCodes: string[];
    correction?: { correctionId?: string; kind?: string; saveState?: string };
  }>;
}

export async function repairMatchIdentity(
  matchId: string,
  body: { kind?: string; trackId?: string; atFrame?: number; leftTrackId?: string; rightTrackId?: string } = {},
) {
  const response = await fetch(`/api/matches/${matchId}/identity/repair`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Failed to repair match identity: ${response.status}`);
  }
  return response.json() as Promise<{
    committed: boolean;
    preview: boolean;
    identityContinuous: boolean;
    silentlyReconnected: boolean;
    visionRerun: boolean;
    reasonCodes: string[];
    correction?: { correctionId?: string; kind?: string; saveState?: string };
  }>;
}

export async function submitMatchCalibration(
  matchId: string,
  body: {
    landmarks: Array<{
      name?: string;
      imageX: number;
      imageY: number;
      pitchX: number;
      pitchY: number;
      independentHoldout: true;
    }>;
  },
) {
  const response = await fetch(`/api/matches/${matchId}/calibration`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Failed to measure match calibration holdout: ${response.status}`);
  }
  return response.json() as Promise<{
    evaluation?: { accepted?: boolean };
    measured?: boolean;
    residualP95M?: number | null;
    committed?: boolean;
    visionRerun?: boolean;
  }>;
}

export async function fetchMatchDerivedDistance(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/geometry/distance`);
  if (!response.ok) {
    throw new Error(`Failed to load derived distance: ${response.status}`);
  }
  return response.json() as Promise<{
    availability?: string;
    value?: number | null;
    uncertaintyM?: number;
    bridged?: boolean;
    reasonCodes?: string[];
  }>;
}

export async function fetchAssembleReport() {
  const response = await fetch('/api/reports/assemble', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ claimedEvidenceIds: ['forged'], knownEvidenceIds: ['forged'] }),
  });
  if (!response.ok) {
    throw new Error(`Failed to assemble report: ${response.status}`);
  }
  return response.json() as Promise<AssembleReportSnapshot>;
}

export interface StalePermissionsSnapshot {
  stale?: boolean;
  admitted?: boolean;
  reasonCodes?: string[];
}

export async function fetchStalePermissions() {
  const response = await fetch('/api/permissions/stale', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ admitted: true, permissionExpiresAt: 9999999999 }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load stale permissions: ${response.status}`);
  }
  return response.json() as Promise<StalePermissionsSnapshot>;
}

export interface ProviderRosterSnapshot {
  roster?: { default?: string };
  local?: { route?: string };
  cloud?: { route?: string };
}

export async function fetchProviders() {
  const response = await fetch('/api/providers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: true, default: 'cloud' }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load providers: ${response.status}`);
  }
  return response.json() as Promise<ProviderRosterSnapshot>;
}

export interface RightsEvaluateSnapshot {
  allowed?: boolean;
  cloudPermitted?: boolean;
  reasonCodes?: string[];
}

export async function fetchRightsEvaluate() {
  const response = await fetch('/api/rights/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ commercialPermission: 'granted', allowed: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to evaluate rights: ${response.status}`);
  }
  return response.json() as Promise<RightsEvaluateSnapshot>;
}

export interface TelestrationSnapshot {
  blenderEnabled?: boolean;
  pitchView?: string;
}

export async function fetchTelestration() {
  const response = await fetch('/api/telestration');
  if (!response.ok) {
    throw new Error(`Failed to load telestration: ${response.status}`);
  }
  return response.json() as Promise<TelestrationSnapshot>;
}

export interface ReleaseDossierSnapshot {
  deploymentBoundary?: string;
  nativeCode?: string;
}

export async function fetchReleaseDossier() {
  const response = await fetch('/api/dossier/release', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ loopbackOnly: false, nativeCode: 'approved' }),
  });
  if (!response.ok) {
    throw new Error(`Failed to load release dossier: ${response.status}`);
  }
  return response.json() as Promise<ReleaseDossierSnapshot>;
}
