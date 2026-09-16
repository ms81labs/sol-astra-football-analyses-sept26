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
