import type { FrameData } from '../types';

export function windowedTimelineProps(matchData: FrameData[], currentFrame: number, frameCount = matchData.length) {
  return {
    matchData: [] as FrameData[],
    frameCount,
    currentFrame,
    currentRecord:
      matchData.find((frame) => frame.Frame_ID === currentFrame)
      ?? matchData[currentFrame]
      ?? null,
  };
}
