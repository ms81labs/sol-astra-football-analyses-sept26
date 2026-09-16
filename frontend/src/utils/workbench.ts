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
  return response.json() as Promise<{ items: Array<{ correctionId: string; kind: string; saveState: string }> }>;
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
  return response.json() as Promise<{ intervalLimited: boolean; totalsWithheld: boolean; reasonCodes: string[] }>;
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

export async function fetchCorrectionHistory(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/corrections`);
  if (!response.ok) {
    throw new Error(`Failed to load correction history: ${response.status}`);
  }
  return response.json() as Promise<{
    items: Array<{ correctionId: string; kind: string; saveState: string; undoOf?: string | null }>;
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
}

export async function fetchMatchEdits(matchId: string) {
  const response = await fetch(`/api/matches/${matchId}/edits`);
  if (!response.ok) {
    throw new Error(`Failed to load edit list: ${response.status}`);
  }
  return response.json() as Promise<EditListSnapshot>;
}
