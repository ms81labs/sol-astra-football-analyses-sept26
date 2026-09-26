import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import EvidenceInspector from './EvidenceInspector';
import type { FrameData } from '../types';
import { splitScores } from '../utils/quantities';

afterEach(cleanup);

const frame: FrameData = {
  Frame_ID: 1,
  Timestamp: 0.2,
  Ball: { x: 50, y: 50, conf: 0.8 },
  My_Team: [],
  Enemies: [],
};

it('keeps observation source separate from review status', () => {
  render(
    <EvidenceInspector
      frame={frame}
      cameraProfile="stitched_panoramic_view"
      reviewStatus="unreviewed"
      modelHash="weights-v1"
      configVersion="evidence_v1"
      uncertainty="unmeasured"
    />,
  );
  expect(screen.getByText(/Observation source/)).toBeTruthy();
  expect(screen.getByText('observed')).toBeTruthy();
  expect(screen.getByText('unreviewed')).toBeTruthy();
  expect(screen.getByLabelText(/observation source icon/i)).toBeTruthy();
  expect(screen.getByLabelText(/review status icon/i)).toBeTruthy();
  expect(screen.getByText(/weights-v1/)).toBeTruthy();
  expect(screen.getByText(/evidence_v1/)).toBeTruthy();
  expect(screen.getByText(/does not convert an inferred location/)).toBeTruthy();
});

it('shows coordinate space and definition version from the evidence page', () => {
  render(
    <EvidenceInspector
      frame={frame}
      coordinateSpace="pitch"
      definitionVersion="1"
    />,
  );
  expect(screen.getByText(/coordinate space/i)).toBeTruthy();
  expect(screen.getByText('pitch')).toBeTruthy();
  expect(screen.getByText(/definition version/i)).toBeTruthy();
  expect(screen.getByText('1')).toBeTruthy();
});

it('shows the server provider request linked to a proposed event', () => {
  render(<EvidenceInspector frame={frame} proposal={{ modelId: 'visual-model', modelVersion: 'v1',
    evidenceIds: ['frame:1'], requestId: 'provider-request-1' }} />);
  expect(screen.getByText(/Provider request: provider-request-1/)).toBeTruthy();
});

it('cannot accept an older model proposal without a provider request', () => {
  const onProposalDecision = vi.fn();
  render(<EvidenceInspector frame={frame} proposal={{ modelId: 'visual-model', modelVersion: 'v1',
    evidenceIds: ['frame:1'] }} onProposalDecision={onProposalDecision} />);
  expect(screen.getByRole('button', { name: /accept proposed event/i })).toHaveProperty('disabled', true);
  expect(screen.getByRole('button', { name: /reject proposed event/i })).toHaveProperty('disabled', false);
  expect(screen.getByText(/provider receipt unavailable/i)).toBeTruthy();
});

it('keeps detector score, calibrated probability and confidence interval as distinct quantities', () => {
  render(
    <EvidenceInspector
      frame={frame}
      detectorScore={0.81}
      calibratedProbability={0.22}
      confidenceInterval={[0.1, 0.4]}
    />,
  );
  expect(screen.getByText(/detector score/i)).toBeTruthy();
  expect(screen.getByText('0.81')).toBeTruthy();
  expect(screen.getByText(/calibrated probability/i)).toBeTruthy();
  expect(screen.getByText('0.22')).toBeTruthy();
  expect(screen.getByText(/confidence interval/i)).toBeTruthy();
  expect(screen.queryByText(/confidence(?! interval)/i)).toBeNull();
});

it('does not copy an uncalibrated detector score into calibrated probability', () => {
  const scores = splitScores({
    detectorScore: 0.81,
    calibratedProbability: null,
    interval: null,
  });
  render(<EvidenceInspector frame={frame} {...scores} />);
  expect(screen.getByText(/detector score/i)).toBeTruthy();
  expect(screen.getByText('0.81')).toBeTruthy();
  expect(screen.queryByText(/calibrated probability/i)).toBeNull();
  expect(scores.calibratedProbability).toBeNull();
  expect(scores.detectorScore).toBe(0.81);
});
