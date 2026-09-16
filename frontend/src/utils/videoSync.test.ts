import { describe, expect, it } from 'vitest';

import { findNearestFrameIndex, shouldResyncVideo } from './videoSync';

describe('findNearestFrameIndex', () => {
  it('maps video time to the nearest frame timestamp', () => {
    expect(findNearestFrameIndex([0, 0.2, 0.4, 0.8], 0.37)).toBe(2);
    expect(findNearestFrameIndex([0, 0.2, 0.4, 0.8], 0.79)).toBe(3);
  });
});

describe('shouldResyncVideo', () => {
  it('only forces sync when drift exceeds the threshold', () => {
    expect(shouldResyncVideo(1.0, 1.04, 0.08)).toBe(false);
    expect(shouldResyncVideo(1.0, 1.15, 0.08)).toBe(true);
  });
});
