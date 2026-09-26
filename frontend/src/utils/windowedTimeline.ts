import type { FrameData } from '../types';

export function windowedTimelineProps(matchData: FrameData[], currentFrame: number, frameCount = matchData.length, lastFrameId?: number | null) {
  return {
    matchData: [] as FrameData[],
    frameCount: Math.max(frameCount, (lastFrameId ?? -1) + 1),
    currentFrame,
    currentRecord:
      matchData.find((frame) => frame.Frame_ID === currentFrame)
      ?? matchData[currentFrame]
      ?? null,
  };
}
