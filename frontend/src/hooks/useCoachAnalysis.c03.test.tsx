import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { RuntimeCapabilities } from '../types';
import type { ReportView } from '../utils/reportLifecycle';
import { ApiError } from '../utils/request';
import { useCoachAnalysis } from './useCoachAnalysis';

const capabilities: RuntimeCapabilities = { analysisProviders: ['local'], defaultAnalysisProvider: 'local', pdfExportAvailable: false };
const report = (generationId = 'N', matchId = 'm') => ({ schemaVersion: 'report_draft_v1', matchId, generationId,
  reportId: 'report1', status: 'current' as const, grounding: 'interpretive' as const, interpretation: 'Review spacing.' });
const view = (generationId = 'N', matchId = 'm'): ReportView => ({ matchId, generationId, status: 'current', reports: {
  tactical_report: { matchId, generationId, reportId: 'report1', status: 'current', validationDisposition: 'interpretive', payload: report(generationId, matchId) },
}, notices: [] });
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((r) => { resolve = r; }); return { promise, resolve }; }
afterEach(cleanup);

it('C03 dispatches once with the committed generation and accepts its matching report', async () => {
  const run = vi.fn().mockResolvedValue(report());
  const { result } = renderHook(() => useCoachAnalysis({ runtimeCapabilities: capabilities, activeMatchId: 'm', generationId: 'N', runMatchAnalysis: run }));
  await act(() => result.current.runScenario({ matchId: 'm', currentFrame: 0, scenario: 'tactical_report' }));
  expect(run).toHaveBeenCalledExactlyOnceWith('m', 'tactical_report', 'local', 0, 'N');
  expect(result.current.tacticalReport?.generationId).toBe('N');
  expect(result.current.activeTab).toBe('report');
});

it('C03 refuses generationless report submission without dispatch', async () => {
  const run = vi.fn();
  const { result } = renderHook(() => useCoachAnalysis({ runtimeCapabilities: capabilities, activeMatchId: 'm', runMatchAnalysis: run }));
  await act(() => result.current.runScenario({ matchId: 'm', currentFrame: 0, scenario: 'tactical_report' }));
  expect(run).not.toHaveBeenCalled();
  expect(result.current.tacticalReport).toBeNull();
  expect(result.current.reportNotice).toContain('Refresh');
});

it.each(['STALE_EVIDENCE_GENERATION', 'STALE_REPORT_POLICY'])('C03 exposes %s without automatically retrying', async (code) => {
  const run = vi.fn().mockRejectedValue(new ApiError('Snapshot changed', 409, code));
  const { result } = renderHook(() => useCoachAnalysis({ runtimeCapabilities: capabilities, activeMatchId: 'm', generationId: 'N', runMatchAnalysis: run }));
  await act(() => result.current.runScenario({ matchId: 'm', currentFrame: 0, scenario: 'tactical_report' }));
  expect(run).toHaveBeenCalledTimes(1);
  expect(result.current.tacticalReport).toBeNull();
  expect(result.current.reportNotice).toContain('no provider retry was sent automatically');
  expect(result.current.llmThinking).toBe(false);
});

it.each(['generation', 'match'])('C03 ignores a provider response after %s selection changed', async (change) => {
  const pending = deferred<unknown>(); const run = vi.fn(() => pending.promise);
  const { result, rerender } = renderHook(({ matchId, generationId }) => useCoachAnalysis({ runtimeCapabilities: capabilities,
    activeMatchId: matchId, generationId, runMatchAnalysis: run }), { initialProps: { matchId: 'm', generationId: 'N' } });
  let request!: Promise<void>;
  act(() => { request = result.current.runScenario({ matchId: 'm', currentFrame: 0, scenario: 'tactical_report' }); });
  rerender(change === 'match' ? { matchId: 'other', generationId: 'N' } : { matchId: 'm', generationId: 'N1' });
  await act(async () => { pending.resolve(report()); await request; });
  expect(result.current.tacticalReport).toBeNull();
  expect(result.current.llmThinking).toBe(false);
  expect(run).toHaveBeenCalledTimes(1);
});

it('C03 restores reports using a read-only generation-scoped request', async () => {
  const fetchReports = vi.fn().mockResolvedValue(view()); const run = vi.fn();
  const { result } = renderHook(() => useCoachAnalysis({ runtimeCapabilities: capabilities, activeMatchId: 'm', generationId: 'N', runMatchAnalysis: run, fetchReports }));
  await waitFor(() => expect(result.current.tacticalReport?.generationId).toBe('N'));
  expect(fetchReports).toHaveBeenCalledWith('m', 'N', expect.any(AbortSignal));
  expect(run).not.toHaveBeenCalled();
});

it('C03 rejects a mixed report group before changing either pane', async () => {
  const mixed = view(); mixed.reports.drills = { ...mixed.reports.tactical_report!, generationId: 'N1', payload: report('N1') };
  const { result } = renderHook(() => useCoachAnalysis({ runtimeCapabilities: capabilities, activeMatchId: 'm', generationId: 'N', runMatchAnalysis: vi.fn(), fetchReports: vi.fn().mockResolvedValue(mixed) }));
  await waitFor(() => expect(result.current.reportNotice).toContain('Refresh'));
  expect(result.current.tacticalReport).toBeNull(); expect(result.current.drillResponse).toBeNull();
});

it('C03 a delayed read cannot erase a newly generated report', async () => {
  const pending = deferred<ReportView>();
  const run = vi.fn().mockResolvedValue(report()); const fetchReports = vi.fn(() => pending.promise);
  const { result } = renderHook(() => useCoachAnalysis({ runtimeCapabilities: capabilities, activeMatchId: 'm', generationId: 'N', runMatchAnalysis: run, fetchReports }));
  await act(() => result.current.runScenario({ matchId: 'm', currentFrame: 0, scenario: 'tactical_report' }));
  await act(async () => pending.resolve({ ...view(), reports: {} }));
  expect(result.current.tacticalReport?.interpretation).toBe('Review spacing.');
});

it.each(['missing', 'historical'])('C03 displays the %s report state without dispatch', async (state) => {
  const response = view();
  if (state === 'missing') response.reports = {};
  else { response.status = 'historical'; response.reports.tactical_report!.status = 'historical'; }
  const run = vi.fn();
  const { result } = renderHook(() => useCoachAnalysis({ runtimeCapabilities: capabilities, activeMatchId: 'm', generationId: 'N', runMatchAnalysis: run, fetchReports: vi.fn().mockResolvedValue(response) }));
  await waitFor(() => expect(result.current.reportNotice).toContain(state === 'missing' ? 'Older reports' : 'Historical report'));
  expect(run).not.toHaveBeenCalled();
});

it('C03 never promotes an unbound legacy response into a current report', async () => {
  const { result } = renderHook(() => useCoachAnalysis({ runtimeCapabilities: capabilities, activeMatchId: 'm', generationId: 'N', runMatchAnalysis: vi.fn().mockResolvedValue({ summary: 'Old report', grounding: 'grounded' }) }));
  await act(() => result.current.runScenario({ matchId: 'm', currentFrame: 0, scenario: 'tactical_report' }));
  expect(result.current.tacticalReport).toBeNull();
  expect(result.current.reportNotice).toContain('Refresh');
});
