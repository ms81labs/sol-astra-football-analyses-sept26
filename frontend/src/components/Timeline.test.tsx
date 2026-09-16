import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import Timeline from './Timeline';
import type { EventTag, FrameData } from '../types';

afterEach(cleanup);

it('seeks both densely spaced events by their distinct selector entries', () => {
  const frames: FrameData[] = Array.from({ length: 360 }, (_, frame) => ({
    Frame_ID: frame, Timestamp: frame / 5, Ball: null, My_Team: [], Enemies: [],
  }));
  const events: EventTag[] = [
    { frame: 18, timestamp: 3.6, label: 'Pass from #2 to #82', type: 'pass' },
    { frame: 20, timestamp: 4, label: 'Pass from #3 to #2', type: 'pass' },
  ];

  function Harness() {
    const [frame, setFrame] = useState(0);
    return <Timeline matchData={frames} currentFrame={frame} isPlaying={false} fps={5}
      events={events} onSeek={setFrame} onTogglePlay={() => {}} />;
  }

  render(<Harness />);
  expect(screen.getByRole('button', { name: 'Pass from #2 to #82 at 3.6 seconds' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Pass from #3 to #2 at 4 seconds' })).toBeTruthy();
  const selector = screen.getByLabelText('Jump to event');
  fireEvent.change(selector, { target: { value: '0' } });
  expect((screen.getByLabelText('Timeline scrubber') as HTMLInputElement).value).toBe('18');
  fireEvent.change(selector, { target: { value: '1' } });
  expect((screen.getByLabelText('Timeline scrubber') as HTMLInputElement).value).toBe('20');
});

it('labels heuristic detections as provisional and keeps analyst tags distinct', () => {
  const frames: FrameData[] = Array.from({ length: 20 }, (_, frame) => ({
    Frame_ID: frame, Timestamp: frame / 5, Ball: null, My_Team: [], Enemies: [],
  }));
  const events: EventTag[] = [
    { frame: 5, timestamp: 1, label: 'Pass from #2 to #82', type: 'pass', reviewStatus: 'unreviewed', heuristicName: 'provisional_event_suggestion' },
    { frame: 8, timestamp: 1.6, label: 'Goal', type: 'goal', reviewStatus: 'accepted' },
  ];

  render(<Timeline matchData={frames} currentFrame={0} isPlaying={false} fps={5}
    events={events} onSeek={() => {}} onTogglePlay={() => {}} />);
  expect(screen.getByRole('button', { name: 'Pass from #2 to #82 at 1 seconds (provisional)' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Goal at 1.6 seconds' })).toBeTruthy();
});

it('shades uncertain intervals without treating them as accepted events', () => {
  const frames: FrameData[] = Array.from({ length: 20 }, (_, frame) => ({
    Frame_ID: frame, Timestamp: frame / 5, Ball: null, My_Team: [], Enemies: [],
  }));
  render(
    <Timeline
      matchData={frames}
      currentFrame={0}
      isPlaying={false}
      fps={5}
      events={[]}
      uncertaintyRanges={[{ startFrame: 4, endFrame: 8, reason: 'identity switch' }]}
      onSeek={() => {}}
      onTogglePlay={() => {}}
    />,
  );
  expect(screen.getByLabelText(/uncertain interval/i)).toBeTruthy();
  expect(screen.getByText(/identity switch/i)).toBeTruthy();
});

it('scrubs a usable timeline without loading all frame records', () => {
  const current = { Frame_ID: 12, Timestamp: 2.4, Ball: null, My_Team: [], Enemies: [] };
  render(
    <Timeline
      matchData={[]}
      frameCount={27000}
      currentFrame={12}
      currentRecord={current}
      isPlaying={false}
      fps={5}
      events={[]}
      onSeek={() => {}}
      onTogglePlay={() => {}}
    />,
  );
  const scrubber = screen.getByLabelText('Timeline scrubber') as HTMLInputElement;
  expect(scrubber.max).toBe('26999');
  expect(scrubber.value).toBe('12');
  expect(screen.getByText(/Time: 2.40s|Time: 2.4s/)).toBeTruthy();
  expect(screen.getByText(/Frame 12 \/ 26999/)).toBeTruthy();
});

it('hides rejected events from accepted views while retaining the candidate', () => {
  const frames: FrameData[] = Array.from({ length: 20 }, (_, frame) => ({
    Frame_ID: frame, Timestamp: frame / 5, Ball: null, My_Team: [], Enemies: [],
  }));
  const events: EventTag[] = [
    { frame: 5, timestamp: 1, label: 'Pass', type: 'pass', reviewStatus: 'accepted' },
    { frame: 8, timestamp: 1.6, label: 'Shot', type: 'shot', reviewStatus: 'rejected', rejectionReason: 'ambiguous deflection' },
  ];
  render(
    <Timeline
      matchData={frames}
      currentFrame={0}
      isPlaying={false}
      fps={5}
      events={events}
      onSeek={() => {}}
      onTogglePlay={() => {}}
    />,
  );
  expect(screen.getByRole('button', { name: 'Pass at 1 seconds' })).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Shot at 1.6 seconds' })).toBeNull();
  expect(screen.getByText(/retained candidate/i)).toBeTruthy();
  expect(screen.getByText(/ambiguous deflection/i)).toBeTruthy();
});
