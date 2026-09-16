export function findNearestFrameIndex(frameTimestamps: number[], videoTime: number): number {
  if (frameTimestamps.length === 0) return 0;
  if (frameTimestamps.length === 1) return 0;

  // Binary search for O(log n) performance
  let lo = 0;
  let hi = frameTimestamps.length - 1;

  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (frameTimestamps[mid] < videoTime) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }

  // Check if previous frame is closer
  if (lo > 0 && Math.abs(frameTimestamps[lo - 1] - videoTime) < Math.abs(frameTimestamps[lo] - videoTime)) {
    return lo - 1;
  }
  return lo;
}

export function shouldResyncVideo(targetTime: number, currentTime: number, threshold = 0.08): boolean {
  return Math.abs(targetTime - currentTime) > threshold;
}
