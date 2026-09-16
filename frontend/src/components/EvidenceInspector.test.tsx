import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import EvidenceInspector from './EvidenceInspector';
import type { FrameData } from '../types';

const frame: FrameData = {
  Frame_ID: 1,
  Timestamp: 0.2,
  Ball: { x: 50, y: 50, conf: 0.8 },
  My_Team: [],
  Enemies: [],
};

it('keeps observation source separate from review status', () => {
  render(<EvidenceInspector frame={frame} cameraProfile="stitched_panoramic_view" reviewStatus="unreviewed" />);
  expect(screen.getByText(/Observation source/)).toBeTruthy();
  expect(screen.getByText('observed')).toBeTruthy();
  expect(screen.getByText('unreviewed')).toBeTruthy();
  expect(screen.getByText(/does not convert an inferred location/)).toBeTruthy();
});
