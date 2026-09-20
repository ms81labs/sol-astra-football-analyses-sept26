import { assertGeneration, parseJson, readGeneration, generationUrl, ApiError } from './request';
import type { CommandReceipt } from './commandLifecycle';
import { findNearestFrameIndex } from './videoSync';
import type {
  AnalyticsPayload,
  BackendEvent,
  CreateBundleInput,
  DashboardResponse,
  EventTag,
  EventType,
  FrameData,
  MatchIssue,
  MatchRecord,
  MatchBenchmarkSummary,
  MatchStats,
  ProcessingJob,
  ReviewBundle,
  TacticalAnnotation,
  TrustCropsResponse,
  UpdateBundleInput,
  UploadConfig,
} from '../types';

interface CreateMatchUploadInput {
  name: string;
  inputMode: 'tracking_json' | 'video';
  file: File;
  config?: UploadConfig;
  signal?: AbortSignal;
}

interface CreateMatchUploadResponse {
  matchId: string;
  jobId: string;
  status: string;
}

export interface EvidenceRecord {
  evidenceId: string;
  schemaVersion: string;
  observationSource: string;
  reviewStatus: string;
  intervalStart: number;
  intervalEnd: number;
  payload: Record<string, unknown>;
}

export interface EvidencePage {
  generationId?: string | null;
  matchId?: string | null;
  items: EvidenceRecord[];
  nextCursor: string | null;
  intervalEndpoint: string;
  coordinateSpace: string;
  definitionVersion: string;
}

export interface MatchWorkspace {
  generationId?: string | null;
  detail: MatchRecord;
  frames: FrameData[];
  analytics: AnalyticsPayload;
  events: BackendEvent[];
  benchmark: MatchBenchmarkSummary | null;
  frameCount: number;
  nextCursor: string | null;
  evidence: EvidencePage | null;
}

export const WORKSPACE_FRAME_LIMIT = 240;

export async function fetchMatchFrames(
  matchId: string,
  options: { afterFrame?: number; cursor?: string; limit?: number; signal?: AbortSignal; generationId?: string } = {},
): Promise<{ frames: FrameData[]; frameCount: number; nextCursor: string | null; generationId?: string | null }> {
  const params = new URLSearchParams();
  if (options.afterFrame != null) params.set('afterFrame', String(options.afterFrame));
  if (options.cursor) params.set('cursor', options.cursor);
  params.set('limit', String(options.limit ?? WORKSPACE_FRAME_LIMIT));
  if (options.generationId) params.set('generationId', options.generationId);
  const response = await fetch(`/api/matches/${matchId}/frames?${params.toString()}`, { signal: options.signal });
  const payload = await parseJson<{
    matchId: string;
    frames: Array<Record<string, unknown>>;
    nextCursor?: string | null;
    frameCount?: number;
    generationId?: string | null;
  }>(response);
  assertGeneration(payload, options.generationId);
  const frames = payload.frames.map(mapFrame);
  return {
    frames,
    generationId: payload.generationId,
    frameCount: payload.frameCount ?? frames.length,
    nextCursor: payload.nextCursor ?? null,
  };
}

export async function fetchMatchEvidence(
  matchId: string,
  options: {
    intervalStart?: number;
    intervalEnd?: number;
    cursor?: string;
    limit?: number;
    signal?: AbortSignal;
    generationId?: string;
  } = {},
): Promise<EvidencePage> {
  const params = new URLSearchParams();
  if (options.intervalStart != null) params.set('intervalStart', String(options.intervalStart));
  if (options.intervalEnd != null) params.set('intervalEnd', String(options.intervalEnd));
  if (options.cursor) params.set('cursor', options.cursor);
  params.set('limit', String(options.limit ?? 100));
  if (options.generationId) params.set('generationId', options.generationId);
  const response = await fetch(`/api/matches/${matchId}/evidence?${params.toString()}`, { signal: options.signal });
  if (response.status === 404 && !options.generationId) {
    return {
      matchId,
      items: [],
      nextCursor: null,
      intervalEndpoint: 'half_open',
      coordinateSpace: 'pitch',
      definitionVersion: '1',
    };
  }
  const page = await parseJson<EvidencePage>(response);
  assertGeneration(page, options.generationId);
  return page;
}

function mapFrame(frame: Record<string, unknown>): FrameData {
  return {
    Frame_ID: Number(frame.frameId),
    Timestamp: Number(frame.timestamp),
    Ball: frame.ball
      ? {
          x: Number((frame.ball as Record<string, unknown>).x),
          y: Number((frame.ball as Record<string, unknown>).y),
          conf: Number((frame.ball as Record<string, unknown>).confidence ?? 0),
        }
      : null,
    My_Team: ((frame.myTeam as Array<Record<string, unknown>> | undefined) ?? []).map((player) => ({
      id: Number(player.id),
      x: Number(player.x),
      y: Number(player.y),
      conf: Number(player.confidence ?? 0),
    })),
    Enemies: ((frame.enemies as Array<Record<string, unknown>> | undefined) ?? []).map((player) => ({
      enemy_id: Number(player.id),
      x: Number(player.x),
      y: Number(player.y),
      conf: Number(player.confidence ?? 0),
    })),
    unassignedPlayers: ((frame.unassignedPlayers as Array<Record<string, unknown>> | undefined) ?? []).map((player) => ({
      id: Number(player.id),
      x: Number(player.x),
      y: Number(player.y),
      conf: Number(player.confidence ?? 0),
    })),
    possession: frame.possession
      ? {
          frameId: Number((frame.possession as Record<string, unknown>).frameId),
          timestamp: Number((frame.possession as Record<string, unknown>).timestamp),
          team: ((frame.possession as Record<string, unknown>).team as FrameData['possession'] extends infer T
            ? T extends { team: infer Team }
              ? Team
              : never
            : never) ?? 'unassigned',
          trackId: ((frame.possession as Record<string, unknown>).trackId as number | null) ?? null,
          distance: Number((frame.possession as Record<string, unknown>).distance ?? 0),
        }
      : null,
  };
}

export async function createMatchUpload({
  name,
  inputMode,
  file,
  config = {},
  signal,
}: CreateMatchUploadInput): Promise<CreateMatchUploadResponse> {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('inputMode', inputMode);
  formData.append('config', JSON.stringify(config));
  formData.append('file', file);

  const response = await fetch('/api/matches', {
    method: 'POST',
    body: formData,
    signal,
  });

  return parseJson<CreateMatchUploadResponse>(response);
}

async function fetchJob(jobId: string, signal?: AbortSignal): Promise<ProcessingJob> {
  const response = await fetch(`/api/jobs/${jobId}`, { signal });
  return parseJson<ProcessingJob>(response);
}

export function buildMatchVideoUrl(matchId: string): string {
  return `/api/matches/${matchId}/video`;
}

export function buildMatchReportExportUrl(matchId: string, generationId?: string | null): string {
  return generationUrl(`/api/matches/${matchId}/report/html`, generationId);
}

export async function fetchMatches(): Promise<MatchRecord[]> {
  const response = await fetch('/api/matches');
  return parseJson<MatchRecord[]>(response);
}

async function fetchMatchBenchmark(matchId: string, signal?: AbortSignal, generationId?: string): Promise<MatchBenchmarkSummary | null> {
  const response = await fetch(`/api/matches/${matchId}/benchmark`, { signal });
  if (response.status === 404) return null;
  const result = await parseJson<MatchBenchmarkSummary & { generationId?: string }>(response);
  // Flat diagnostic summaries without a proven source snapshot are not current
  // analytical panes. C05 owns a richer benchmark/provenance migration.
  return generationId && result.generationId !== generationId ? null : result;
}

export async function updateMatchConfig(matchId: string, payload: Record<string, unknown>): Promise<MatchRecord & { correction?: CommandReceipt; generationId?: string | null }> {
  const response = await fetch(`/api/matches/${matchId}/config`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return parseJson<MatchRecord & { correction?: CommandReceipt; generationId?: string | null }>(response);
}

export async function fetchMatchWorkspace(matchId: string, signal?: AbortSignal, requestedGeneration?: string): Promise<MatchWorkspace> {
  // Resolve once before parallel reads. No silent retry against a newer generation.
  const detail = await readGeneration<MatchRecord>(`/api/matches/${matchId}`, requestedGeneration, signal);
  const generationId = detail.generationId;
  if (!generationId) throw new ApiError('Analysis has not published a snapshot yet.', 409, 'GENERATION_NOT_READY');
  const [framesPayload, analyticsPayload, eventsPayload, benchmark, evidence] = await Promise.all([
    fetchMatchFrames(matchId, { limit: WORKSPACE_FRAME_LIMIT, signal, generationId }),
    readGeneration<{
      matchId: string; summary: MatchStats; ballAssignments: AnalyticsPayload['ballAssignments'];
      formationTimeline?: AnalyticsPayload['formationTimeline']; shots?: AnalyticsPayload['shots'];
    }>(`/api/matches/${matchId}/analytics`, generationId, signal),
    readGeneration<{ matchId: string; events: BackendEvent[] }>(`/api/matches/${matchId}/events`, generationId, signal),
    fetchMatchBenchmark(matchId, signal, generationId),
    fetchMatchEvidence(matchId, { limit: 100, signal, generationId }),
  ]);
  return {
    detail, generationId,
    frames: framesPayload.frames, frameCount: framesPayload.frameCount, nextCursor: framesPayload.nextCursor,
    analytics: { summary: analyticsPayload.summary, ballAssignments: analyticsPayload.ballAssignments,
      formationTimeline: analyticsPayload.formationTimeline ?? [], shots: analyticsPayload.shots ?? [] },
    events: eventsPayload.events, benchmark, evidence,
  };
}

export async function fetchMatchEvents(matchId: string, signal?: AbortSignal, generationId?: string): Promise<BackendEvent[]> {
  const payload = await readGeneration<{ matchId: string; events: BackendEvent[] }>(`/api/matches/${matchId}/events`, generationId, signal);
  return payload.events;
}

export function mapBackendEventsToTags(events: BackendEvent[], frames: FrameData[]): EventTag[] {
  const supportedEventTypes = new Set<EventType>(['pass', 'cross', 'shot', 'tackle', 'recovery', 'turnover', 'through_ball', 'interception']);
  const timestamps = frames.map((frame) => frame.Timestamp);
  return events.map((event) => ({
    frame: Number.isFinite(event.frameId) ? event.frameId : findNearestFrameIndex(timestamps, event.timestamp),
    timestamp: event.timestamp,
    label: event.description,
    type: supportedEventTypes.has(event.type as EventType) ? (event.type as EventType) : 'custom',
    reviewStatus: event.reviewStatus ?? 'unreviewed',
    heuristicName: event.heuristicName ?? 'provisional_event_suggestion',
  }));
}

function waitForJobDelay(signal: AbortSignal, durationMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new Error('Job polling was cancelled.'));
      return;
    }

    const timer = window.setTimeout(() => finish(resolve), durationMs);
    const onAbort = () => finish(() => reject(new Error('Job polling was cancelled.')));
    signal.addEventListener('abort', onAbort, { once: true });

    function finish(callback: () => void) {
      window.clearTimeout(timer);
      signal.removeEventListener('abort', onAbort);
      callback();
    }
  });
}

export async function waitForJobCompletion(
  jobId: string,
  intervalMs = 2_000,
  maxDurationMs = 60 * 60 * 1000,  // 60 minutes — CPU video processing is slow
  signal?: AbortSignal,
  onUpdate?: (job: ProcessingJob) => void,
): Promise<ProcessingJob> {
  const deadline = Date.now() + maxDurationMs;
  if (signal?.aborted) throw new Error('Job polling was cancelled.');

  const controller = new AbortController();
  const cancel = () => controller.abort();
  let timedOut = false;
  signal?.addEventListener('abort', cancel, { once: true });
  const deadlineTimer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, Math.max(0, deadline - Date.now()));

  try {
    while (true) {
      if (controller.signal.aborted) throw new Error('Job polling was cancelled.');
      if (Date.now() >= deadline) {
        timedOut = true;
        controller.abort();
        throw new Error('Timed out waiting for job to complete.');
      }

      const job = await fetchJob(jobId, controller.signal);
      if (controller.signal.aborted) throw new Error('Job polling was cancelled.');
      if (Date.now() >= deadline) {
        timedOut = true;
        controller.abort();
        throw new Error('Timed out waiting for job to complete.');
      }

      onUpdate?.(job);
      if (job.status === 'completed') {
        return job;
      }
      if (job.status === 'failed') {
        throw new Error(job.error || job.message || 'Processing job failed.');
      }
      await waitForJobDelay(controller.signal, Math.min(intervalMs, deadline - Date.now()));
    }
  } catch (error) {
    if (signal?.aborted) throw new Error('Job polling was cancelled.');
    if (timedOut || Date.now() >= deadline) throw new Error('Timed out waiting for job to complete.');
    throw error;
  } finally {
    window.clearTimeout(deadlineTimer);
    signal?.removeEventListener('abort', cancel);
  }
}

export async function runMatchAnalysis(
  matchId: string,
  analysisType: string,
  provider: 'local' | 'cloud',
  currentFrameIndex: number,
  generationId?: string,
): Promise<Record<string, unknown>> {
  const response = await fetch(`/api/matches/${matchId}/analysis/${analysisType}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ provider, currentFrameIndex, generationId }),
  });
  return parseJson<Record<string, unknown>>(response);
}

// ===== Review Bundle API =====

export async function fetchBundles(tags?: string[]): Promise<ReviewBundle[]> {
  const url = tags?.length ? `/api/bundles?tags=${encodeURIComponent(tags.join(','))}` : '/api/bundles';
  const response = await fetch(url);
  return parseJson<ReviewBundle[]>(response);
}

export async function fetchBundle(bundleId: string): Promise<ReviewBundle> {
  const response = await fetch(`/api/bundles/${bundleId}`);
  return parseJson<ReviewBundle>(response);
}

export async function createBundle(input: CreateBundleInput): Promise<ReviewBundle> {
  const response = await fetch('/api/bundles', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  });
  return parseJson<ReviewBundle>(response);
}

export async function updateBundle(bundleId: string, input: UpdateBundleInput): Promise<ReviewBundle> {
  const response = await fetch(`/api/bundles/${bundleId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  });
  return parseJson<ReviewBundle>(response);
}

export async function deleteBundle(bundleId: string): Promise<void> {
  const response = await fetch(`/api/bundles/${bundleId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete bundle: ${response.status}`);
  }
}

// ===== Dashboard =====

export async function fetchDashboardData(): Promise<DashboardResponse> {
  const response = await fetch('/api/aggregate/dashboard');
  if (!response.ok) {
    throw new Error(`Failed to load dashboard data: ${response.status}`);
  }
  return parseJson<DashboardResponse>(response);
}

// ===== Match Annotations =====

export async function fetchMatchAnnotations(matchId: string): Promise<TacticalAnnotation[]> {
  const response = await fetch(`/api/matches/${matchId}/annotations`);
  if (response.status === 404) return [];
  const payload = await parseJson<{ matchId: string; annotations: TacticalAnnotation[] }>(response);
  return payload.annotations;
}

export async function createMatchAnnotation(
  matchId: string,
  payload: Omit<TacticalAnnotation, 'id' | 'matchId' | 'createdAt' | 'updatedAt'>,
): Promise<TacticalAnnotation> {
  const response = await fetch(`/api/matches/${matchId}/annotations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseJson<TacticalAnnotation>(response);
}

export async function deleteMatchAnnotation(matchId: string, annotationId: string): Promise<void> {
  const response = await fetch(`/api/matches/${matchId}/annotations/${annotationId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete annotation: ${response.status}`);
  }
}

// ===== Trust Crops =====

export async function fetchTrustCrops(matchId: string, limit = 20): Promise<TrustCropsResponse> {
    const response = await fetch(`/api/matches/${matchId}/trust-crops?limit=${encodeURIComponent(String(limit))}`);
    if (!response.ok) {
        throw new Error(`Failed to load trust crops: ${response.status}`);
    }
    return parseJson<TrustCropsResponse>(response);
}

// ===== Match Issues =====

export async function fetchMatchIssues(matchId: string): Promise<MatchIssue[]> {
  const response = await fetch(`/api/matches/${matchId}/issues`);
  if (response.status === 404) return [];
  const payload = await parseJson<{ matchId: string; issues: MatchIssue[] }>(response);
  return payload.issues;
}

export async function createMatchIssue(
  matchId: string,
  payload: Omit<MatchIssue, 'id' | 'matchId' | 'createdAt' | 'updatedAt'>,
): Promise<MatchIssue> {
  const response = await fetch(`/api/matches/${matchId}/issues`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseJson<MatchIssue>(response);
}

export async function deleteMatchIssue(matchId: string, issueId: string): Promise<void> {
  const response = await fetch(`/api/matches/${matchId}/issues/${issueId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete match issue: ${response.status}`);
  }
}

export async function fetchGenerationReports(matchId: string, generationId: string, signal?: AbortSignal) {
  return readGeneration<import('./reportLifecycle').ReportView>(`/api/matches/${matchId}/reports`, generationId, signal);
}
