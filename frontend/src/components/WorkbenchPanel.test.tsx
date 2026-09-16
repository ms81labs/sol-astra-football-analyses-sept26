import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import WorkbenchPanel from './WorkbenchPanel';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('renders independently visible capability statuses from the dossier', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.endsWith('/api/dossier')) {
      return new Response(JSON.stringify({
        baseline: {
          selectedCommit: '5099e1f',
          declaredCameraProfile: 'stitched_panoramic_view',
          declaredWorkflow: 'manual_review_plus_declared_camera_setup',
          unresolvedGates: ['independent_labels_0_of_18'],
          permittedNextActions: [],
          forbiddenActions: [],
          capabilities: [
            { id: 'manual_review', label: 'Manual review', status: 'usable', evidenceClass: 'software_verification', evidenceLink: 'docs', notes: 'Tagging works without an LLM.', independentlyVisible: true },
            { id: 'physical_metrics', label: 'Physical metrics', status: 'unavailable', evidenceClass: 'independent_accuracy', evidenceLink: 'docs', notes: 'Withheld until identity continuity.', independentlyVisible: true },
          ],
          evidenceClasses: {},
        },
        release: { deploymentBoundary: 'loopback', gNetworkRequiredForNonLocal: true, nativeCode: 'gated_inert' },
        evaluation: { accepted: false, completeTasks: 0, requiredTasks: 18, reasonCodes: ['LABELS_INCOMPLETE'] },
        gpu: { available: false, canPromoteDefault: false, reasonCodes: ['HARDWARE_UNAVAILABLE'] },
        native: { approved: false, reasonCodes: ['NATIVE_GATE_CLOSED'] },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    return new Response(JSON.stringify({
      query: { unanswerable: true, reason: 'refused_code_execution', eventFamily: 'pass' },
      results: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<WorkbenchPanel onClose={() => undefined} matchId="m1" events={[]} />);

  expect(await screen.findByText('Manual review')).toBeTruthy();
  expect(screen.getByText('Usable')).toBeTruthy();
  expect(screen.getAllByText('Unavailable').length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText(/Independent labels 0\/18 complete/)).toBeTruthy();
  expect(screen.getByText(/cancellation is a request/i)).toBeTruthy();
  expect(screen.getByText(/native code remain gated/i)).toBeTruthy();

  await fireEvent.click(screen.getByRole('button', { name: 'Search evidence' }));
  expect(await screen.findByText(/Unanswerable/)).toBeTruthy();
  const queryCall = fetchMock.mock.calls.find(([url, init]) => String(url).includes('/api/matches/m1/queries') && init?.method === 'POST');
  expect(queryCall).toBeTruthy();
  expect(JSON.parse(String(queryCall?.[1]?.body))).toEqual({ query: 'show our second-half turnovers followed by a shot within 10 seconds' });
});

it('recovers a pending playlist correction after a simulated crash', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/api/dossier')) {
      return new Response(JSON.stringify({
        baseline: {
          selectedCommit: '5099e1f',
          declaredCameraProfile: 'stitched_panoramic_view',
          declaredWorkflow: 'manual_review_plus_declared_camera_setup',
          unresolvedGates: [],
          permittedNextActions: [],
          forbiddenActions: [],
          capabilities: [],
          evidenceClasses: {},
        },
        release: { deploymentBoundary: 'loopback', gNetworkRequiredForNonLocal: true, nativeCode: 'gated_inert' },
        evaluation: { accepted: false, completeTasks: 0, requiredTasks: 18, reasonCodes: ['LABELS_INCOMPLETE'] },
        gpu: { available: false, canPromoteDefault: false, reasonCodes: ['HARDWARE_UNAVAILABLE'] },
        native: { approved: false, reasonCodes: ['NATIVE_GATE_CLOSED'] },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    if (url.includes('/corrections') && url.includes('state=pending') && !init?.method) {
      return new Response(JSON.stringify({
        items: [{ correctionId: 'c-pending', kind: 'playlist_item', saveState: 'pending' }],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    if (url.endsWith('/corrections/c-pending/recover') && init?.method === 'POST') {
      return new Response(JSON.stringify({ correctionId: 'c-pending', saveState: 'saved' }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    if (url.endsWith('/api/playlists/export-interval') && init?.method === 'POST') {
      return new Response(JSON.stringify({
        sourceStartSeconds: 3,
        sourceEndSeconds: 5,
        sourceEndFrameExclusive: 125,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    return new Response(JSON.stringify({ query: { unanswerable: true, reason: 'x', eventFamily: 'pass' }, results: [] }), { status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<WorkbenchPanel onClose={() => undefined} matchId="m1" events={[]} />);
  expect(await screen.findByText(/pending playlist edit/i)).toBeTruthy();
  await fireEvent.click(screen.getByRole('button', { name: /recover pending edit/i }));
  expect(await screen.findByText(/saved/i)).toBeTruthy();
  await fireEvent.click(screen.getByRole('button', { name: /export source interval/i }));
  expect(await screen.findByText(/Source interval 3s to 5s/i)).toBeTruthy();
});

it('shows feature flags, live job cost, match library hits and interval-limited players', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/api/dossier')) {
      return new Response(JSON.stringify({
        baseline: {
          selectedCommit: '5099e1f',
          declaredCameraProfile: 'stitched_panoramic_view',
          declaredWorkflow: 'manual_review_plus_declared_camera_setup',
          unresolvedGates: [],
          permittedNextActions: [],
          forbiddenActions: [],
          capabilities: [],
          evidenceClasses: {},
        },
        release: { deploymentBoundary: 'loopback', gNetworkRequiredForNonLocal: true, nativeCode: 'gated_inert' },
        evaluation: { accepted: false, completeTasks: 0, requiredTasks: 18, reasonCodes: ['LABELS_INCOMPLETE'] },
        gpu: { available: false, canPromoteDefault: false, reasonCodes: ['HARDWARE_UNAVAILABLE'] },
        native: { approved: false, reasonCodes: ['NATIVE_GATE_CLOSED'] },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    if (url.endsWith('/api/flags')) {
      return new Response(JSON.stringify({ experimental_shot_quality: false, gpu_default: false, native_code: false }), { status: 200 });
    }
    if (url.endsWith('/api/jobs/live/cost')) {
      return new Response(JSON.stringify({ reservedTotal: 1.5, actualTotal: 0, p50Reserved: 1.5 }), { status: 200 });
    }
    if (url.endsWith('/api/library/search') && init?.method === 'POST') {
      return new Response(JSON.stringify({ results: [{ id: 'm-lib', title: 'elevated training' }] }), { status: 200 });
    }
    if (url.endsWith('/api/matches/m1/players')) {
      return new Response(JSON.stringify({ intervalLimited: true, totalsWithheld: true, reasonCodes: ['IDENTITY_DISCONTINUITY'] }), { status: 200 });
    }
    return new Response(JSON.stringify({ query: { unanswerable: true, reason: 'x', eventFamily: 'pass' }, results: [] }), { status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<WorkbenchPanel onClose={() => undefined} matchId="m1" jobId="live" events={[]} />);
  expect(await screen.findByText(/experimental shot quality: shadowed/i)).toBeTruthy();
  expect(await screen.findByText(/reserved 1.5/i)).toBeTruthy();
  await fireEvent.change(screen.getByLabelText(/match library/i), { target: { value: 'elevated' } });
  await fireEvent.click(screen.getByRole('button', { name: /search library/i }));
  expect(await screen.findByText(/elevated training/i)).toBeTruthy();
  expect(await screen.findByText(/interval-limited player observations/i)).toBeTruthy();
});

it('shows the quality timeline only when experimental UI is enabled', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.endsWith('/api/dossier')) {
      return new Response(JSON.stringify({
        baseline: {
          selectedCommit: '5099e1f',
          declaredCameraProfile: 'stitched_panoramic_view',
          declaredWorkflow: 'manual_review_plus_declared_camera_setup',
          unresolvedGates: [],
          permittedNextActions: [],
          forbiddenActions: [],
          capabilities: [],
          evidenceClasses: {},
        },
        release: { deploymentBoundary: 'loopback', gNetworkRequiredForNonLocal: true, nativeCode: 'gated_inert' },
        evaluation: { accepted: false, completeTasks: 0, requiredTasks: 18, reasonCodes: ['LABELS_INCOMPLETE'] },
        gpu: { available: false, canPromoteDefault: false, reasonCodes: ['HARDWARE_UNAVAILABLE'] },
        native: { approved: false, reasonCodes: ['NATIVE_GATE_CLOSED'] },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    if (url.endsWith('/api/flags')) {
      return new Response(JSON.stringify({
        experimental_shot_quality: false,
        gpu_default: false,
        native_code: false,
        experimental_ui: true,
        embeddings_search: false,
      }), { status: 200 });
    }
    return new Response(JSON.stringify({ query: { unanswerable: true, reason: 'x', eventFamily: 'pass' }, results: [] }), { status: 200 });
  }));

  render(<WorkbenchPanel onClose={() => undefined} matchId="m1" events={[]} />);
  expect(await screen.findByText(/review first/i)).toBeTruthy();
  expect(screen.getByText(/incorrect team selection/i)).toBeTruthy();
  expect(screen.getByText(/does not prescribe medical load/i)).toBeTruthy();
});

it('loads recovery and landmark preview from production routes and posts deletion', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/api/dossier')) {
      return new Response(JSON.stringify({
        baseline: {
          selectedCommit: '5099e1f',
          declaredCameraProfile: 'stitched_panoramic_view',
          declaredWorkflow: 'manual_review_plus_declared_camera_setup',
          unresolvedGates: [],
          permittedNextActions: [],
          forbiddenActions: [],
          capabilities: [],
          evidenceClasses: {},
        },
        release: { deploymentBoundary: 'loopback', gNetworkRequiredForNonLocal: true, nativeCode: 'gated_inert' },
        evaluation: { accepted: false, completeTasks: 0, requiredTasks: 18, reasonCodes: ['LABELS_INCOMPLETE'] },
        gpu: { available: false, canPromoteDefault: false, reasonCodes: ['HARDWARE_UNAVAILABLE'] },
        native: { approved: false, reasonCodes: ['NATIVE_GATE_CLOSED'] },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    if (url.endsWith('/api/recovery')) {
      return new Response(JSON.stringify({
        deletion: { available: false, executed: false, trackIdsDoNotAnonymise: true, reasonCodes: ['CONTROLLER_PROCESSOR_ROLES_REQUIRED'] },
        unresolvedIncidents: { items: [{ id: 'inc-op', title: 'cleanup unconfirmed' }], operatorVisible: true, enterpriseUptimePromised: false },
        recoveryObjectives: { defined: false, enterpriseUptimePromised: false, reasonCodes: ['RECOVERY_OBJECTIVES_UNMEASURED'] },
        stalePermissions: { stale: true, admitted: false, reasonCodes: ['PERMISSION_EXPIRY_UNRECORDED'] },
      }), { status: 200 });
    }
    if (url.endsWith('/api/access/deletion') && init?.method === 'POST') {
      return new Response(JSON.stringify({
        available: false,
        executed: false,
        trackIdsDoNotAnonymise: true,
        reasonCodes: ['CONTROLLER_PROCESSOR_ROLES_REQUIRED'],
      }), { status: 200 });
    }
    if (url.endsWith('/api/matches/m1/setup/preview')) {
      return new Response(JSON.stringify({
        preview: true,
        committed: false,
        accepted: false,
        visionRerun: false,
        residualP95M: null,
        measured: false,
        reasonCodes: ['LANDMARK_RESIDUAL_UNMEASURED'],
      }), { status: 200 });
    }
    if (url.endsWith('/api/native')) {
      return new Response(JSON.stringify({
        approved: false,
        reasonCodes: ['NATIVE_GATE_CLOSED'],
        pinned: { universallyPortable: false, admitted: false },
        rpcFleet: { enabled: false },
        customNative: { approved: false },
      }), { status: 200 });
    }
    if (url.endsWith('/api/security')) {
      return new Response(JSON.stringify({
        modelOutput: { trusted: false, admitted: false },
        publicExposure: { admitted: true, publicExposureAllowed: false },
        encryption: { hostedEncryptionProven: false },
        egress: { defaultDeny: true },
      }), { status: 200 });
    }
    return new Response(JSON.stringify({ query: { unanswerable: true, reason: 'x', eventFamily: 'pass' }, results: [] }), { status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<WorkbenchPanel onClose={() => undefined} matchId="m1" events={[]} />);
  expect(await screen.findByText(/cleanup unconfirmed/i)).toBeTruthy();
  expect(screen.getByText(/recovery objectives remain unmeasured/i)).toBeTruthy();
  expect(await screen.findByText(/landmark residual unmeasured/i)).toBeTruthy();
  await fireEvent.click(screen.getByRole('button', { name: /request deletion/i }));
  const deletionCall = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith('/api/access/deletion') && init?.method === 'POST');
  expect(deletionCall).toBeTruthy();
  expect(JSON.parse(String(deletionCall?.[1]?.body))).toEqual({ requested: true });
});

