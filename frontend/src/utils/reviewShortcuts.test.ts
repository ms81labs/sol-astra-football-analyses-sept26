import { expect, it } from 'vitest';

import { applyReviewShortcut, reviewShortcut, type ReviewShortcutState } from '../utils/reviewShortcuts';

it('maps the declared review keys to undoable analyst actions', () => {
  expect(reviewShortcut(' ')).toBe('play_pause');
  expect(reviewShortcut('[')).toBe('previous_candidate');
  expect(reviewShortcut(']')).toBe('next_candidate');
  expect(reviewShortcut('i')).toBe('mark_in');
  expect(reviewShortcut('o')).toBe('mark_out');
  expect(reviewShortcut('a')).toBe('accept');
  expect(reviewShortcut('r')).toBe('reject');
  expect(reviewShortcut('z')).toBe('undo');
  expect(reviewShortcut('Enter')).toBe('save_note');
  expect(reviewShortcut(',')).toBe('previous_frame');
  expect(reviewShortcut('.')).toBe('next_frame');
  expect(reviewShortcut('x')).toBeNull();
});

it('applies play, candidate, frame, mark, accept, reject and undo without loading every frame', () => {
  const events = [
    { frame: 4, timestamp: 0.8, label: 'Pass', type: 'pass' as const, reviewStatus: 'unreviewed' as const },
    { frame: 10, timestamp: 2, label: 'Shot', type: 'shot' as const, reviewStatus: 'unreviewed' as const },
  ];
  let state: ReviewShortcutState = {
    isPlaying: false,
    currentFrame: 0,
    frameCount: 27000,
    events,
    reviewRange: null as { startFrame: number; endFrame: number } | null,
  };
  state = applyReviewShortcut('play_pause', state);
  expect(state.isPlaying).toBe(true);
  state = applyReviewShortcut('next_candidate', state);
  expect(state.currentFrame).toBe(4);
  expect(state.isPlaying).toBe(false);
  state = applyReviewShortcut('next_candidate', state);
  expect(state.currentFrame).toBe(10);
  state = applyReviewShortcut('previous_candidate', state);
  expect(state.currentFrame).toBe(4);
  state = applyReviewShortcut('next_frame', state);
  expect(state.currentFrame).toBe(5);
  state = applyReviewShortcut('previous_frame', state);
  expect(state.currentFrame).toBe(4);
  state = applyReviewShortcut('mark_in', state);
  state = applyReviewShortcut('next_candidate', state);
  state = applyReviewShortcut('mark_out', state);
  expect(state.reviewRange).toEqual({ startFrame: 4, endFrame: 10 });
  state = applyReviewShortcut('accept', state);
  expect(state.events[1].reviewStatus).toBe('accepted');
  state = applyReviewShortcut('previous_candidate', state);
  state = applyReviewShortcut('reject', state);
  expect(state.events[0].reviewStatus).toBe('rejected');
  expect(state.events[0].rejectionReason).toBe('analyst_rejected');
  state = applyReviewShortcut('undo', state);
  expect(state.events[0].reviewStatus).toBe('unreviewed');
});
