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

export interface ReviewShortcutEvent {
  frame: number;
  timestamp: number;
  label: string;
  type: string;
  reviewStatus?: 'unreviewed' | 'accepted' | 'rejected';
  rejectionReason?: string;
}

export interface ReviewShortcutState {
  isPlaying: boolean;
  currentFrame: number;
  frameCount: number;
  events: ReviewShortcutEvent[];
  reviewRange: { startFrame: number; endFrame: number } | null;
}

function clampFrame(frame: number, frameCount: number): number {
  if (frameCount <= 0) return 0;
  return Math.max(0, Math.min(frameCount - 1, frame));
}

function currentEventIndex(state: ReviewShortcutState): number {
  const exact = state.events.findIndex((event) => event.frame === state.currentFrame);
  if (exact >= 0) return exact;
  let nearest = -1;
  let best = Number.POSITIVE_INFINITY;
  state.events.forEach((event, index) => {
    const delta = Math.abs(event.frame - state.currentFrame);
    if (delta < best) {
      best = delta;
      nearest = index;
    }
  });
  return nearest;
}

export function applyReviewShortcut(action: ReviewAction, state: ReviewShortcutState): ReviewShortcutState {
  if (action === 'save_note') return state;
  const events = state.events.map((event) => ({ ...event }));
  const { isPlaying, currentFrame, reviewRange } = state;

  if (action === 'play_pause') {
    return { ...state, events, isPlaying: !isPlaying };
  }
  if (action === 'next_frame') {
    return { ...state, events, isPlaying: false, currentFrame: clampFrame(currentFrame + 1, state.frameCount) };
  }
  if (action === 'previous_frame') {
    return { ...state, events, isPlaying: false, currentFrame: clampFrame(currentFrame - 1, state.frameCount) };
  }
  if (action === 'next_candidate' || action === 'previous_candidate') {
    if (events.length === 0) return { ...state, events, isPlaying: false };
    const resolved =
      action === 'next_candidate'
        ? events.find((event) => event.frame > currentFrame) ?? events[events.length - 1]
        : [...events].reverse().find((event) => event.frame < currentFrame) ?? events[0];
    return { ...state, events, isPlaying: false, currentFrame: resolved.frame };
  }
  if (action === 'mark_in') {
    const end = reviewRange?.endFrame ?? currentFrame;
    return { ...state, events, reviewRange: { startFrame: Math.min(currentFrame, end), endFrame: Math.max(currentFrame, end) } };
  }
  if (action === 'mark_out') {
    const start = reviewRange?.startFrame ?? currentFrame;
    return { ...state, events, reviewRange: { startFrame: Math.min(start, currentFrame), endFrame: Math.max(start, currentFrame) } };
  }
  if (action === 'accept' || action === 'reject') {
    const index = currentEventIndex({ ...state, events });
    if (index >= 0) {
      events[index] = {
        ...events[index],
        reviewStatus: action === 'accept' ? 'accepted' : 'rejected',
        rejectionReason: action === 'reject' ? 'analyst_rejected' : undefined,
      };
    }
    return { ...state, events };
  }
  if (action === 'undo') {
    const index = currentEventIndex({ ...state, events });
    if (index >= 0) {
      events[index] = { ...events[index], reviewStatus: 'unreviewed', rejectionReason: undefined };
    }
    return { ...state, events };
  }
  return { ...state, events, isPlaying, currentFrame, reviewRange };
}
