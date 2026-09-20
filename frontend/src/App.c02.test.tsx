/** C02 UI acceptance: real HTTP client + App, controlled immutable server snapshots.
 * Only visual pitch/graph children are replaced; command and loading logic is real.
 */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import App from './App';
import type TacticalPitch from './components/TacticalPitch';
import type StatsPanel from './components/StatsPanel';
import type { BackendEvent, MatchRecord, MatchStats } from './types';
import type { CommandReceipt } from './utils/commandLifecycle';

vi.mock('./components/TacticalPitch', () => ({ default: (p: ComponentProps<typeof TacticalPitch>) => <div>
  <output data-testid="pitch-frame">{p.frameData?.Frame_ID ?? 'none'}</output>
  <output data-testid="pitch-team">{p.frameData?.My_Team.map((x) => x.id).join(',')}</output>
  <output data-testid="pitch-speeds">{p.speedData ? JSON.stringify([...p.speedData.entries()]) : 'withheld'}</output>
</div> }));
vi.mock('./components/StatsPanel', () => ({ default: (p: ComponentProps<typeof StatsPanel>) => <div>
  <output data-testid="possession">{p.stats?.possession ?? 'unknown'}</output>
  <output data-testid="player-distances">{JSON.stringify(p.playerProfiles?.map((p) => p.totalDistance))}</output>
</div> }));

beforeEach(() => sessionStorage.setItem('ga_leftover_panels', 'off'));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });
const respond = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } });
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
const summary = { possession: 50, formation: null, myTeamDistance: null, enemyDistance: null,
  myTeamTopSpeed: null, enemyTopSpeed: null, myTeamSprints: null, enemySprints: null,
  myTeamXg: null, enemyXg: null, ballSignalStatus: 'trusted', ballSignalMessage: null } as MatchStats;
const event: BackendEvent = { type: 'pass', frameId: 2, timestamp: .4, team: 'my_team', fromTrackId: 7, toTrackId: 8,
  description: 'Known synthetic pass', reviewStatus: 'unreviewed' };
interface Snapshot { id: string; name: string; generationId: string; events: BackendEvent[]; possession: number; includedCommandIds: string[]; team: number; }

function fixture() {
  const snapshots: Record<string, Snapshot> = {
    G1: { id: 'a', name: 'Match A', generationId: 'G1', possession: 50, team: 7, events: [event], includedCommandIds: [] },
    G2: { id: 'a', name: 'Match A', generationId: 'G2', possession: 61, team: 8,
      events: [{ ...event, reviewStatus: 'accepted' }], includedCommandIds: ['edit-one'] },
    B1: { id: 'b', name: 'Match B', generationId: 'B1', possession: 40, team: 18, events: [], includedCommandIds: [] },
  };
  let current = 'G1';
  let history: CommandReceipt[] = [];
  let partial = false;
  let heatmap = { identityContinuous: false, geometryEligible: false, withheld: true, wholeMatch: false,
    intervalLimited: true, pitchDimensions: null as null | { pitchLengthM: number; pitchWidthM: number } };
  let intercept: (url: URL, init?: RequestInit) => Response | Promise<Response> | undefined = () => undefined;
  let onCommand: (body: Record<string, unknown>) => Response | Promise<Response> = () => respond({ correctionId: 'edit-one', saveState: 'saved' });
  function detail(s: Snapshot): MatchRecord { return { id: s.id, name: s.name, status: 'ready', inputMode: 'tracking_json', originalFilename: 'synthetic.json',
    generationId: s.generationId, includedCommandIds: s.includedCommandIds, config: { pitchLengthM: 100, pitchWidthM: 60 } }; }
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = new URL(String(input), 'http://localhost');
    const intercepted = intercept(url, init);
    if (intercepted) return intercepted;
    if (url.pathname === '/api/matches') return respond([detail(snapshots[current]), detail(snapshots.B1)]);
    const match = url.pathname.match(/^\/api\/matches\/(a|b)(.*)$/);
    if (!match) return respond({ error: 'NOT_AVAILABLE_IN_TEST' }, 404);
    const [mid, suffix] = match.slice(1);
    const gid = url.searchParams.get('generationId') ?? (mid === 'b' ? 'B1' : current);
    const s = snapshots[gid];
    if (!s || s.id !== mid) return respond({ error: 'GENERATION_RECOVERY_REQUIRED' }, 503);
    if (suffix === '/corrections' && init?.method === 'POST') return onCommand(JSON.parse(String(init.body)));
    if (suffix === '/corrections') return respond({ items: url.searchParams.get('state') === 'pending'
      ? history.filter((c) => c.applyState !== 'applied') : history });
    const envelope = (value: object) => respond({ matchId: mid, ...value, generationId: gid });
    if (!suffix) return respond(detail(s));
    if (suffix === '/frames') return envelope({ frames: [0, 1, 2, 3, 4].map((f) => ({ frameId: f, timestamp: f / 5,
      ball: null, myTeam: [{ id: s.team, x: 12 + f, y: 30, confidence: 1 }], enemies: [] })), frameCount: partial ? 1000 : 5, nextCursor: null });
    if (suffix === '/analytics') return envelope({ summary: { ...summary, possession: s.possession }, shots: [], formationTimeline: [], ballAssignments: [] });
    if (suffix === '/events') return envelope({ events: s.events });
    if (suffix === '/evidence') return envelope({ items: [], nextCursor: null, intervalEndpoint: 'half_open' });
    if (suffix === '/benchmark') return respond({ fiveMinuteTruthReady: true }); // Unbound optional diagnostic must not be current.
    if (suffix === '/metrics') return envelope({ metrics: [] });
    if (suffix === '/heatmap') return envelope(heatmap);
    if (suffix === '/quality') return envelope({ items: [], measured: false });
    if (suffix === '/formation') return envelope({ availability: 'withheld', value: null, reasonCodes: ['UNAVAILABLE'] });
    if (suffix === '/incidents/review') return envelope({ samples: [], decision: null });
    if (suffix === '/setup') return envelope({ certified: false, cameraProfile: 'stable_elevated_wide', pitchLengthM: 100,
      manualTaggingPermitted: true, cannotMeasure: [], periods: [{ name: '1', startSeconds: 0, endSeconds: 600 }] });
    if (suffix === '/setup/preview') return envelope({ accepted: false, committed: false, measured: false, residualP95M: null });
    if (suffix.startsWith('/metrics/inspect')) return envelope({ rendered: 'unavailable', publishedValue: null, metric: 'my_team_distance_m', exclusions: [] });
    if (suffix === '/reports/coverage') return envelope({ coverageAware: true, representsWholeMatch: false });
    if (suffix === '/annotations') return respond({ annotations: [] });
    if (suffix === '/issues') return respond({ issues: [] });
    return respond({ error: 'NOT_AVAILABLE_IN_TEST' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  const applied: CommandReceipt = { correctionId: 'edit-one', commandId: 'edit-one', kind: 'event_accept', saveState: 'saved',
    applyState: 'applied', appliedGeneration: 'G2', baseGeneration: 'G1', version: 1 };
  return { fetchMock, applied, snapshots,
    setHandler(fn: typeof onCommand) { onCommand = fn; }, setIntercept(fn: typeof intercept) { intercept = fn; },
    setHistory(value: CommandReceipt[]) { history = value; }, setPartial() { partial = true; },
    admitPhysical() { heatmap = { identityContinuous: true, geometryEligible: true, withheld: false, wholeMatch: true,
      intervalLimited: false, pitchDimensions: { pitchLengthM: 100, pitchWidthM: 60 } }; },
    publish() { current = 'G2'; history = [applied]; },
    frameGets() { return fetchMock.mock.calls.filter(([u]) => String(u).includes('/frames?')); },
    writes() { return fetchMock.mock.calls.filter(([u, init]) => String(u).endsWith('/corrections') && init?.method === 'POST'); },
  };
}
async function loaded() { render(<App />); await screen.findByText('Match A', { selector: 'header span' });
  await waitFor(() => expect(screen.getByTestId('analysis-generation').textContent).toContain('G1'));
  fireEvent.keyDown(window, { key: '.' }); fireEvent.keyDown(window, { key: '.' });
  await waitFor(() => expect(screen.getByTestId('pitch-frame').textContent).toBe('2')); }

describe('C02 application/snapshot UI', () => {
  it.each([
    ['received', /Edit recorded/], ['committed', /Edit recorded/], ['applying', /Applying edit/], ['failed', /Edit failed/],
  ] as const)('shows %s without displaying an applied effect', async (state, label) => {
    const f = fixture(); f.setHandler(() => respond({ correctionId: 'edit-one', kind: 'event_accept', saveState: 'saved', applyState: state, lastError: state === 'failed' ? 'Synthetic failure' : null }));
    await loaded(); fireEvent.keyDown(window, { key: 'a' });
    expect(await screen.findByText(label)).toBeTruthy();
    expect(screen.getByTestId('analysis-generation').textContent).toContain('G1');
    expect(screen.getByTestId('possession').textContent).toBe('50');
    expect(screen.getByTestId('pitch-frame').textContent).toBe('2');
    expect(f.frameGets()).toHaveLength(1);
    expect(screen.queryByText(/^Edit applied/)).toBeNull();
  });
  it('refreshes all analytical panes on the returned generation and preserves the playhead', async () => {
    const f = fixture(); f.setHandler((body) => {
      expect(body).toMatchObject({ baseGeneration: 'G1', commandId: expect.any(String), kind: 'event_accept' });
      expect(body.payload).not.toHaveProperty('events');
      f.publish(); return respond(f.applied);
    });
    await loaded(); fireEvent.keyDown(window, { key: 'a' });
    expect(await screen.findByText(/^Edit applied/)).toBeTruthy();
    expect(screen.getByTestId('analysis-generation').textContent).toContain('G2');
    expect(screen.getByTestId('possession').textContent).toBe('61');
    expect(screen.getByTestId('pitch-team').textContent).toBe('8');
    expect(screen.getByTestId('pitch-frame').textContent).toBe('2');
    for (const suffix of ['/frames?', '/events?', '/analytics?', '/evidence?']) {
      expect(f.fetchMock.mock.calls.some(([u]) => String(u).includes(suffix) && String(u).includes('generationId=G2'))).toBe(true);
    }
    expect(f.frameGets()).toHaveLength(2);
  });
  it('retains the old complete snapshot when one refreshed core pane has a different generation', async () => {
    const f = fixture(); f.setHandler(() => { f.publish(); return respond(f.applied); });
    f.setIntercept((url) => url.pathname.endsWith('/analytics') && url.searchParams.get('generationId') === 'G2'
      ? respond({ generationId: 'G1', summary: { ...summary, possession: 99 }, ballAssignments: [], shots: [] }) : undefined);
    await loaded(); fireEvent.keyDown(window, { key: 'a' });
    await screen.findByText(/Stale correction/);
    expect(screen.getByTestId('analysis-generation').textContent).toContain('G1');
    expect(screen.getByTestId('possession').textContent).toBe('50');
    expect(screen.getByTestId('pitch-team').textContent).toBe('7');
  });
  it('does not call a saved receipt applied when its generation is missing', async () => {
    const f = fixture(); f.setHandler(() => respond({ ...f.applied, appliedGeneration: null }));
    await loaded(); fireEvent.keyDown(window, { key: 'a' });
    await screen.findByText(/Application unconfirmed/);
    expect(f.frameGets()).toHaveLength(1);
  });
  it('does not automatically resubmit a conflicted or uncertain command under a fresh ID', async () => {
    const f = fixture(); f.setHandler(() => respond({ code: 'STALE_GENERATION', message: 'Changed elsewhere' }, 409));
    await loaded(); fireEvent.keyDown(window, { key: 'a' }); await screen.findByText(/Stale correction/);
    fireEvent.keyDown(window, { key: 'a' }); await act(async () => {});
    expect(f.writes()).toHaveLength(1);
    expect(f.frameGets()).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: /refresh current snapshot/i }));
    await waitFor(() => expect(f.frameGets()).toHaveLength(2));
    expect(screen.getByTestId('analysis-generation').textContent).toContain('G1');
  });
  it('ignores a late command response after another match selection has started', async () => {
    const f = fixture(); const pending = deferred<Response>(); f.setHandler(() => pending.promise);
    await loaded(); fireEvent.keyDown(window, { key: 'a' }); await waitFor(() => expect(f.writes()).toHaveLength(1));
    fireEvent.change(screen.getByLabelText('Active match'), { target: { value: 'b' } });
    await screen.findByText('Match B', { selector: 'header span' });
    await act(async () => pending.resolve(respond(f.applied)));
    expect(screen.getByTestId('analysis-generation').textContent).toContain('B1');
    expect(f.fetchMock.mock.calls.some(([u]) => String(u).includes('generationId=G2'))).toBe(false);
  });
  it('does not let a late old-generation physical pane enable newer withheld overlays', async () => {
    const f = fixture(); const pending = deferred<Response>();
    f.setIntercept((url) => url.pathname.endsWith('/heatmap') && url.searchParams.get('generationId') === 'G1' ? pending.promise : undefined);
    f.setHandler(() => { f.publish(); return respond(f.applied); });
    await loaded(); fireEvent.keyDown(window, { key: 'a' }); await screen.findByText(/^Edit applied/);
    await act(async () => pending.resolve(respond({ generationId: 'G1', identityContinuous: true, geometryEligible: true,
      withheld: false, wholeMatch: true, intervalLimited: false, pitchDimensions: { pitchLengthM: 100, pitchWidthM: 60 } })));
    expect(screen.getByTestId('pitch-speeds').textContent).toBe('withheld');
    expect(screen.getByTestId('analysis-generation').textContent).toContain('G2');
  });
  it('withholds whole-match player totals on a partial frame page even with approved identity', async () => {
    const f = fixture(); f.admitPhysical(); f.setPartial(); await loaded();
    await waitFor(() => expect(screen.getByTestId('pitch-speeds').textContent).not.toBe('withheld'));
    expect(screen.getByTestId('player-distances').textContent).toMatch(/null/);
    expect(screen.getByText(/Player physical totals withheld.*complete frame coverage/)).toBeTruthy();
  });
  it('ignores a newer log playlist effect not included in the displayed generation', async () => {
    const f = fixture(); f.setHistory([{ ...f.applied, kind: 'playlist_item', payload: { timestampStart: 12, timestampEnd: 14, notes: 'Future clip' } }]);
    await loaded(); await screen.findByText('edit-one');
    expect(screen.queryByText('Future clip')).toBeNull();
    expect(screen.getByTestId('analysis-generation').textContent).toContain('G1');
  });
});
