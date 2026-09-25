import { describe, expect, it } from 'vitest';
import { commandState, canUndo, mergeReceipt, nextTimestamp, type CommandReceipt } from './commandLifecycle';
import { ApiError, parseJson } from './request';
import { playlistClipsFromCorrections } from './playlist';
import { computeSpeedsForFrame, buildPlayerProfiles } from './analytics';

const applied: CommandReceipt = { correctionId: 'one', commandId: 'command-one', kind: 'playlist_item',
  saveState: 'saved', applyState: 'applied', appliedGeneration: 'g1', version: 1,
  payload: { timestampStart: 0, timestampEnd: 1, notes: 'Approved', sourceEndFrameExclusive: 5 } };

describe('C02 application contracts', () => {
  it.each([
    [{ saveState: 'saved' }, 'recorded'],
    [{ applyState: 'received' }, 'recorded'], [{ applyState: 'committed' }, 'recorded'],
    [{ applyState: 'applying' }, 'applying'], [{ applyState: 'failed' }, 'failed'],
    [{ applyState: 'applied', appliedGeneration: null }, 'unavailable'],
    [{ saveState: 'conflicted' }, 'conflicted'],
  ] as const)('does not confuse durable save with applied output (%j)', (patch, expected) => {
    expect(commandState({ correctionId: 'x', saveState: 'saved', ...patch })).toBe(expected);
  });
  it('requires a committed generation to confirm application', () => expect(commandState(applied)).toBe('applied'));
  it('does not undo recorded commands or undo-of-undo', () => {
    expect(canUndo({ ...applied, applyState: 'committed' }, [])).toBe(false);
    expect(canUndo({ ...applied, kind: 'undo', undoOf: 'prior' }, [])).toBe(false);
    expect(canUndo(applied, [applied, { ...applied, correctionId: 'undo', undoOf: 'one' }])).toBe(false);
    expect(canUndo(applied, [applied])).toBe(true);
  });
  it('keeps an applied receipt when an older pending fetch resolves late', () => {
    expect(mergeReceipt([applied], { ...applied, applyState: 'received', saveState: 'pending' })).toEqual([applied]);
  });
  it('selects playlist commands from the selected generation, not a newer log', () => {
    const newer = { ...applied, correctionId: 'two', commandId: 'command-two', appliedGeneration: 'g2' };
    expect(playlistClipsFromCorrections([applied, newer], ['command-one'])).toHaveLength(1);
    expect(playlistClipsFromCorrections([applied, newer], [])).toEqual([]);
    expect(playlistClipsFromCorrections([{ ...applied, applyState: 'committed' }], ['command-one'])).toEqual([]);
    const pendingUndo = { ...newer, kind: 'undo', undoOf: 'one', applyState: 'received' as const };
    expect(playlistClipsFromCorrections([applied, pendingUndo], ['command-one', 'command-two'])).toHaveLength(1);
  });
  it('restores a saved playlist title with its source interval', () => {
    expect(playlistClipsFromCorrections([{ ...applied, payload: { ...applied.payload, title: 'Pressing cue' } }], ['command-one'], 'g1'))
      .toMatchObject([{ generationId: 'g1', title: 'Pressing cue', start: 0, end: 1, notes: 'Approved' }]);
  });
  it.each([0, 0.2, 1, -1, 100000])('uses the smallest representable half-open endpoint after %s', (time) => {
    const end = nextTimestamp(time);
    expect(end).toBeGreaterThan(time);
    expect(end - time).toBeLessThanOrEqual(Math.max(Number.MIN_VALUE, Math.abs(time) * Number.EPSILON));
  });
  it.each([
    { detail: { code: 'STALE_GENERATION', message: 'Refresh first' } },
    { error: 'STALE_GENERATION' },
  ])('preserves stable conflict status and code from HTTP errors', async (payload) => {
    await expect(parseJson(new Response(JSON.stringify(payload), { status: 409 })))
      .rejects.toMatchObject({ status: 409, code: 'STALE_GENERATION' });
  });
  it('preserves a non-JSON server error rather than asserting saved', async () => {
    await expect(parseJson(new Response('not json', { status: 503 }))).rejects.toBeInstanceOf(ApiError);
  });
  it('uses accepted pitch dimensions, not fixed 105x68 metres', () => {
    const frames = [0, 1].map((i) => ({ Frame_ID: 100 + i, Timestamp: i,
      Ball: null, My_Team: [{ id: 7, x: 12 + i, y: 30, conf: 1 }], Enemies: [] }));
    const dimensions = { pitchLengthM: 100, pitchWidthM: 60 };
    expect(computeSpeedsForFrame(frames, 1, dimensions).get(7)?.speed).toBe(3.6);
    const events = [{ type: 'pass' as const, frameId: 100, timestamp: 0, team: 'my_team' as const,
      fromTrackId: 7, toTrackId: 8, description: 'Synthetic pass' }];
    expect(buildPlayerProfiles(frames, events, [], true, dimensions).find((p) => p.playerId === 7)?.totalDistance).toBe(1);
    expect(buildPlayerProfiles(frames, events, [], false, dimensions).find((p) => p.playerId === 7)?.totalDistance).toBeNull();
    expect(computeSpeedsForFrame(frames, 1, { ...dimensions, pitchLengthM: NaN }).size).toBe(0);
  });
});
