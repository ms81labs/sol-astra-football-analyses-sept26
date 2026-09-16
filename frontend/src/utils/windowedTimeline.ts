import type { FrameData } from '../types';

export function windowedTimelineProps(matchData: FrameData[], currentFrame: number) {
  return {
    matchData: [] as FrameData[],
    frameCount: matchData.length,
    currentFrame,
    currentRecord: matchData[currentFrame] ?? null,
  };
}
