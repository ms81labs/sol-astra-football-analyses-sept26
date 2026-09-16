export type ReviewAction =
  | 'play_pause'
  | 'previous_candidate'
  | 'next_candidate'
  | 'previous_frame'
  | 'next_frame'
  | 'mark_in'
  | 'mark_out'
  | 'accept'
  | 'reject'
  | 'undo'
  | 'save_note';

const SHORTCUTS: Record<string, ReviewAction> = {
  ' ': 'play_pause',
  '[': 'previous_candidate',
  ']': 'next_candidate',
  ',': 'previous_frame',
  '.': 'next_frame',
  i: 'mark_in',
  o: 'mark_out',
  a: 'accept',
  r: 'reject',
  z: 'undo',
  Enter: 'save_note',
};

export function reviewShortcut(key: string): ReviewAction | null {
  return SHORTCUTS[key] ?? SHORTCUTS[key.toLowerCase()] ?? null;
}
