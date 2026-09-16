import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import WorkbenchPanel from './WorkbenchPanel';

afterEach(() => vi.unstubAllGlobals());

it('renders independently visible capability statuses from the dossier', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.endsWith('/api/workbench/dossier')) {
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
  }));

  render(<WorkbenchPanel onClose={() => undefined} matchId="m1" events={[]} />);

  expect(await screen.findByText('Manual review')).toBeTruthy();
  expect(screen.getByText('Usable')).toBeTruthy();
  expect(screen.getByText('Unavailable')).toBeTruthy();
  expect(screen.getByText(/Independent labels 0\/18 complete/)).toBeTruthy();

  await fireEvent.click(screen.getByRole('button', { name: 'Search evidence' }));
  expect(await screen.findByText(/Unanswerable/)).toBeTruthy();
});

it('recovers a pending playlist correction after a simulated crash', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/api/workbench/dossier')) {
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
    return new Response(JSON.stringify({ query: { unanswerable: true, reason: 'x', eventFamily: 'pass' }, results: [] }), { status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<WorkbenchPanel onClose={() => undefined} matchId="m1" events={[]} />);
  expect(await screen.findByText(/pending playlist edit/i)).toBeTruthy();
  await fireEvent.click(screen.getByRole('button', { name: /recover pending edit/i }));
  expect(await screen.findByText(/saved/i)).toBeTruthy();
});
