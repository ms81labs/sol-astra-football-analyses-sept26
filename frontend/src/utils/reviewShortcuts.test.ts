import { expect, it } from 'vitest';

import { reviewShortcut } from '../utils/reviewShortcuts';

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
  expect(reviewShortcut('x')).toBeNull();
});
