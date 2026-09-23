import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FrameData } from '../../types';
import { useReviewSurface } from './useReviewSurface';

const api = vi.hoisted(() => ({
  createMatchAnnotation: vi.fn(),
  createMatchIssue: vi.fn(),
  deleteMatchAnnotation: vi.fn(),
  deleteMatchIssue: vi.fn(),
  fetchMatchAnnotations: vi.fn(),
  fetchMatchIssues: vi.fn(),
}));

vi.mock('../../utils/api', () => api);

beforeEach(() => {
  api.fetchMatchAnnotations.mockResolvedValue([]);
  api.fetchMatchIssues.mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

function renderReviewSurface(setLoadError: (message: string | null) => void) {
  return renderHook(() => useReviewSurface({
    activeMatchId: 'match-1',
    currentFrame: 0,
    matchData: [frame(12, 2.4)],
    pausePlayback: vi.fn(),
    clearResponse: vi.fn(),
    onSeekFrame: vi.fn(),
    setLoadError,
  }));
}

function frame(frameId: number, timestamp: number): FrameData {
  return {
    Frame_ID: frameId,
    Timestamp: timestamp,
    Ball: null,
    My_Team: [],
    Enemies: [],
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

describe('useReviewSurface', () => {
  it('clears a selected source range when the review generation changes', () => {
    const { result, rerender } = renderHook(({ generation }) => useReviewSurface({
      activeMatchId: 'match-1', activeGenerationId: generation,
      currentFrame: 0, matchData: [frame(0, 1), frame(1, 2)],
      pausePlayback: vi.fn(), clearResponse: vi.fn(), onSeekFrame: vi.fn(), setLoadError: vi.fn(),
    }), { initialProps: { generation: 'g1' } });
    act(() => result.current.setReviewRange({ startFrame: 0, endFrame: 1 }));
    expect(result.current.reviewRange).toEqual({ startFrame: 0, endFrame: 1 });
    rerender({ generation: 'g2' });
    expect(result.current.reviewRange).toBeNull();
  });

  it('surfaces an annotation load failure instead of presenting an empty review', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.fetchMatchAnnotations.mockRejectedValueOnce(new Error('Annotation history unavailable.'));
    const setLoadError = vi.fn();

    renderReviewSurface(setLoadError);

    await waitFor(() => {
      expect(setLoadError).toHaveBeenCalledWith('Annotation history unavailable.');
    });
  });

  it('surfaces an issue load failure instead of presenting an empty review', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    api.fetchMatchIssues.mockRejectedValueOnce(new Error('Issue history unavailable.'));
    const setLoadError = vi.fn();

    renderReviewSurface(setLoadError);

    await waitFor(() => {
      expect(setLoadError).toHaveBeenCalledWith('Issue history unavailable.');
    });
  });

  it('surfaces an annotation save error and clears it after a successful retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const setLoadError = vi.fn();
    api.createMatchAnnotation
      .mockRejectedValueOnce(new Error('Annotation service unavailable.'))
      .mockResolvedValueOnce({
        id: 'annotation-1',
        matchId: 'match-1',
        type: 'note',
        frameStart: 12,
        frameEnd: 12,
        timestampStart: 2.4,
        timestampEnd: 2.4,
        text: 'Hold shape',
        createdAt: '2026-09-10T00:00:00Z',
        updatedAt: '2026-09-10T00:00:00Z',
      });
    const { result } = renderReviewSurface(setLoadError);

    await act(async () => {
      await result.current.handleCreateNote('Hold shape');
    });

    expect(setLoadError).toHaveBeenLastCalledWith('Annotation service unavailable.');

    await act(async () => {
      await result.current.handleCreateNote('Hold shape');
    });

    expect(setLoadError).toHaveBeenLastCalledWith(null);
  });

  it('surfaces an issue save error and clears it after a successful retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const setLoadError = vi.fn();
    api.createMatchIssue
      .mockRejectedValueOnce(new Error('Issue service unavailable.'))
      .mockResolvedValueOnce({
        id: 'issue-1',
        matchId: 'match-1',
        bucket: 'tracking_failure',
        frameStart: 12,
        frameEnd: 12,
        timestampStart: 2.4,
        timestampEnd: 2.4,
        processingBackend: 'local',
        evidenceTarget: 'product_bug',
        note: 'Tracker lost the ball',
        createdAt: '2026-09-10T00:00:00Z',
        updatedAt: '2026-09-10T00:00:00Z',
      });
    const { result } = renderReviewSurface(setLoadError);

    await act(async () => {
      await result.current.handleCreateIssue({
        bucket: 'tracking_failure',
        processingBackend: 'local',
        evidenceTarget: 'product_bug',
        note: 'Tracker lost the ball',
      });
    });

    expect(setLoadError).toHaveBeenLastCalledWith('Issue service unavailable.');

    await act(async () => {
      await result.current.handleCreateIssue({
        bucket: 'tracking_failure',
        processingBackend: 'local',
        evidenceTarget: 'product_bug',
        note: 'Tracker lost the ball',
      });
    });

    expect(setLoadError).toHaveBeenLastCalledWith(null);
  });

  it('clears match-scoped review state and clamps a new match save to its frames', async () => {
    const matches = {
      a: [frame(0, 1), frame(1, 2), frame(2, 3), frame(3, 4), frame(4, 5)],
      b: [frame(0, 10), frame(1, 11)],
    };
    const { result, rerender } = renderHook(
      ({ activeMatchId, currentFrame, matchData }) => useReviewSurface({
        activeMatchId,
        currentFrame,
        matchData,
        pausePlayback: vi.fn(),
        clearResponse: vi.fn(),
        onSeekFrame: vi.fn(),
        setLoadError: vi.fn(),
      }),
      { initialProps: { activeMatchId: 'match-a', currentFrame: 4, matchData: matches.a } },
    );

    act(() => {
      result.current.setReviewRange({ startFrame: 4, endFrame: 2 });
      result.current.startArrowPlacement();
    });
    act(() => {
      void result.current.handlePitchPointSelect({ x: 12, y: 34 });
    });
    expect(result.current.pitchAnnotationPlacementMode).toBe('arrow-end');

    rerender({ activeMatchId: 'match-b', currentFrame: 9, matchData: matches.b });

    expect(result.current.reviewRange).toBeNull();
    expect(result.current.reviewMode).toBeNull();
    expect(result.current.pitchAnnotationPlacementMode).toBeNull();

    act(() => result.current.setReviewRange({ startFrame: 9, endFrame: -4 }));

    api.createMatchAnnotation.mockResolvedValue({
      id: 'annotation-b',
      matchId: 'match-b',
      type: 'note',
      frameStart: 0,
      frameEnd: 1,
      timestampStart: 10,
      timestampEnd: 11,
      text: 'New match note',
      createdAt: '2026-09-12T00:00:00Z',
      updatedAt: '2026-09-12T00:00:00Z',
    });
    await act(async () => {
      await result.current.handleCreateNote('New match note');
    });

    expect(api.createMatchAnnotation).toHaveBeenCalledWith('match-b', {
      type: 'note',
      frameStart: 0,
      frameEnd: 1,
      timestampStart: 10,
      timestampEnd: 11,
      text: 'New match note',
    });
  });

  it.each([
    { range: { startFrame: 2, endFrame: Infinity }, expected: [0, 2, 10, 12] },
    { range: { startFrame: Number.NaN, endFrame: 4 }, expected: [0, 4, 10, 14] },
    { range: { startFrame: -Infinity, endFrame: 3 }, expected: [0, 3, 10, 13] },
  ])('normalizes each non-finite range endpoint before ordering %#', async ({ range, expected }) => {
    const matchData = [frame(0, 10), frame(1, 11), frame(2, 12), frame(3, 13), frame(4, 14)];
    const { result } = renderHook(() => useReviewSurface({
      activeMatchId: 'match-1',
      currentFrame: 0,
      matchData,
      pausePlayback: vi.fn(),
      clearResponse: vi.fn(),
      onSeekFrame: vi.fn(),
      setLoadError: vi.fn(),
    }));

    act(() => result.current.setReviewRange(range));
    await act(async () => {
      await result.current.handleCreateNote('Normalized range');
    });

    expect(api.createMatchAnnotation).toHaveBeenCalledWith('match-1', expect.objectContaining({
      frameStart: expected[0],
      frameEnd: expected[1],
      timestampStart: expected[2],
      timestampEnd: expected[3],
    }));
  });

  it('does not submit review records when the active match has no frames', async () => {
    const { result } = renderHook(() => useReviewSurface({
      activeMatchId: 'empty-match',
      currentFrame: 0,
      matchData: [],
      pausePlayback: vi.fn(),
      clearResponse: vi.fn(),
      onSeekFrame: vi.fn(),
      setLoadError: vi.fn(),
    }));

    await act(async () => {
      await result.current.handleCreateNote('Note');
      await result.current.handleCreateTaggedMoment('Moment');
      await result.current.handleCreateIssue({
        bucket: 'tracking_failure',
        processingBackend: 'local',
        evidenceTarget: 'product_bug',
        note: 'Missing frames',
      });
      result.current.startCirclePlacement();
    });
    await act(async () => {
      await result.current.handlePitchPointSelect({ x: 10, y: 20 });
      result.current.startArrowPlacement();
    });
    act(() => {
      void result.current.handlePitchPointSelect({ x: 10, y: 20 });
    });
    await act(async () => {
      await result.current.handlePitchPointSelect({ x: 30, y: 40 });
    });

    expect(api.createMatchAnnotation).not.toHaveBeenCalled();
    expect(api.createMatchIssue).not.toHaveBeenCalled();
  });

  it('keeps the new match arrow gesture when an old match save completes late', async () => {
    const oldSave = deferred<Awaited<ReturnType<typeof api.createMatchAnnotation>>>();
    api.createMatchAnnotation.mockReturnValueOnce(oldSave.promise);
    const frames = [frame(0, 1)];
    const { result, rerender } = renderHook(
      ({ activeMatchId }) => useReviewSurface({
        activeMatchId,
        currentFrame: 0,
        matchData: frames,
        pausePlayback: vi.fn(),
        clearResponse: vi.fn(),
        onSeekFrame: vi.fn(),
        setLoadError: vi.fn(),
      }),
      { initialProps: { activeMatchId: 'match-a' } },
    );

    act(() => result.current.startCirclePlacement());
    let pendingSave!: Promise<void>;
    act(() => {
      pendingSave = result.current.handlePitchPointSelect({ x: 5, y: 6 });
    });

    rerender({ activeMatchId: 'match-b' });
    act(() => result.current.startArrowPlacement());
    act(() => {
      void result.current.handlePitchPointSelect({ x: 70, y: 80 });
    });
    expect(result.current.pitchAnnotationPlacementMode).toBe('arrow-end');

    await act(async () => {
      oldSave.resolve({
        id: 'old-circle',
        matchId: 'match-a',
        type: 'circle',
        frameStart: 0,
        frameEnd: 0,
        timestampStart: 1,
        timestampEnd: 1,
        x: 5,
        y: 6,
        createdAt: '2026-09-12T00:00:00Z',
        updatedAt: '2026-09-12T00:00:00Z',
      });
      await pendingSave;
    });

    expect(result.current.reviewMode).toBe('arrow');
    expect(result.current.pitchAnnotationPlacementMode).toBe('arrow-end');
  });
});


it('resolves saved issue and annotation timestamps against displayed frames', () => {
  const onSeekFrame = vi.fn();
  const { result } = renderHook(() => useReviewSurface({ activeMatchId: 'm', currentFrame: 0, matchData: [frame(100, 0), frame(200, 2)], pausePlayback: vi.fn(), clearResponse: vi.fn(), onSeekFrame, setLoadError: vi.fn() }));
  const timing = { frameStart: 100, frameEnd: 200, timestampStart: 0, timestampEnd: 2 };
  act(() => result.current.handleSeekToIssue({ ...timing, id: 'i', matchId: 'm', bucket: 'tracking_failure', processingBackend: 'unknown', evidenceTarget: 'trust_eval', note: '', createdAt: '', updatedAt: '' }));
  expect(onSeekFrame).toHaveBeenLastCalledWith(0);
  expect(result.current.reviewRange).toEqual({ startFrame: 0, endFrame: 1 });
  act(() => result.current.handleSeekToAnnotation({ ...timing, id: 'a', matchId: 'm', type: 'circle', createdAt: '', updatedAt: '' }));
  expect(onSeekFrame).toHaveBeenLastCalledWith(0);
  expect(result.current.reviewRange).toEqual({ startFrame: 0, endFrame: 1 });
});
