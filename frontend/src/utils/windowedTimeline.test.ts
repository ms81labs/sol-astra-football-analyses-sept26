import { expect, it } from 'vitest';

import { windowedTimelineProps } from './windowedTimeline';
import type { FrameData } from '../types';

it('does not pass every frame record into the timeline', () => {
  const matchData: FrameData[] = Array.from({ length: 27000 }, (_, frame) => ({
    Frame_ID: frame,
    Timestamp: frame / 5,
    Ball: null,
    My_Team: [],
    Enemies: [],
  }));
  const props = windowedTimelineProps(matchData, 12);
  expect(props.matchData).toEqual([]);
  expect(props.frameCount).toBe(27000);
  expect(props.currentFrame).toBe(12);
  expect(props.currentRecord?.Frame_ID).toBe(12);
  expect(props.currentRecord?.Timestamp).toBe(2.4);
});
