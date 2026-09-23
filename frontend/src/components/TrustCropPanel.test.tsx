import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import TrustCropPanel from './TrustCropPanel';
import { createMatchIssue, fetchTrustCrops } from '../utils/api';

vi.mock('../utils/api', () => ({
  fetchTrustCrops: vi.fn(),
  createMatchIssue: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('TrustCropPanel', () => {
  it('keeps loaded crops visible and labels a save failure correctly', async () => {
    vi.mocked(fetchTrustCrops).mockResolvedValue({
      matchId: 'match-1',
      generationId: 'gen-1',
      ballTeleportGeometryAvailable: true,
      ballTeleportReasonCodes: [],
      totalFrames: 1,
      crops: [{
        frameStart: 0,
        frameEnd: 0,
        timestampStart: 0,
        timestampEnd: 0,
        score: 8,
        reasons: ['track_switches'],
      }],
    });
    vi.mocked(createMatchIssue).mockRejectedValue(new Error('Save unavailable.'));

    render(<TrustCropPanel
      frames={[{ Frame_ID: 0, Timestamp: 0, Ball: null, My_Team: [], Enemies: [] }]}
      matchId="match-1"
      generationId="gen-1"
      onClose={() => {}}
      onSeekToCrop={() => {}}
    />);
    fireEvent.click(await screen.findByRole('button', { name: /save for training set/i }));

    expect(await screen.findByText('Failed to save trust crop: Save unavailable.')).toBeTruthy();
    expect(screen.getByText('Track switches')).toBeTruthy();
  });

  it('saves an uncertain crop as trust-eval training metadata', async () => {
    vi.mocked(fetchTrustCrops).mockResolvedValue({
      matchId: 'match-1',
      generationId: 'gen-1',
      ballTeleportGeometryAvailable: true,
      ballTeleportReasonCodes: [],
      totalFrames: 100,
      crops: [
        {
          frameStart: 10,
          frameEnd: 20,
          timestampStart: 1.0,
          timestampEnd: 2.0,
          score: 8.5,
          reasons: ['ball_teleport', 'track_switches'],
        },
      ],
    });
    vi.mocked(createMatchIssue).mockResolvedValue({
      id: 'issue-1',
      matchId: 'match-1',
      bucket: 'tracking_failure',
      frameStart: 10,
      frameEnd: 20,
      timestampStart: 1.0,
      timestampEnd: 2.0,
      processingBackend: 'unknown',
      evidenceTarget: 'trust_eval',
      note: 'Trust crop score 8.5: ball_teleport, track_switches',
      createdAt: '2026-04-11T00:00:00Z',
      updatedAt: '2026-04-11T00:00:00Z',
    });

    render(<TrustCropPanel frames={Array.from({ length: 21 }, (_, index) => ({ Frame_ID: index, Timestamp: index / 10, Ball: null, My_Team: [], Enemies: [] }))} matchId="match-1" generationId="gen-1" onClose={() => {}} onSeekToCrop={() => {}} />);

    const saveButton = await screen.findByRole('button', { name: /save for training set/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(createMatchIssue).toHaveBeenCalledWith('match-1', {
        bucket: 'tracking_failure',
        frameStart: 10,
        frameEnd: 20,
        timestampStart: 1.0,
        timestampEnd: 2.0,
        processingBackend: 'unknown',
        evidenceTarget: 'trust_eval',
        note: 'Trust crop score 8.5: ball_teleport, track_switches',
      });
    });
    expect(await screen.findByText(/saved for training set/i)).toBeTruthy();
  });
});


it('seeks the crop timestamp midpoint and saves displayed frame bounds for sparse IDs', async () => {
  const frames = [100, 150, 200].map((Frame_ID, index) => ({ Frame_ID, Timestamp: index, Ball: null, My_Team: [], Enemies: [] }));
  vi.mocked(fetchTrustCrops).mockResolvedValue({ matchId: 'm', generationId: 'gen-1', ballTeleportGeometryAvailable: true, ballTeleportReasonCodes: [], totalFrames: 3, crops: [{ frameStart: 100, frameEnd: 200, timestampStart: 0, timestampEnd: 2, score: 8, reasons: [] }] });
  const seek = vi.fn();
  render(<TrustCropPanel matchId="m" generationId="gen-1" frames={frames} onClose={() => {}} onSeekToCrop={seek} />);
  fireEvent.click(await screen.findByRole('button', { name: /Seek/ }));
  expect(seek).toHaveBeenCalledWith(1);
  fireEvent.click(screen.getByRole('button', { name: /Save for training set/i }));
  await waitFor(() => expect(createMatchIssue).toHaveBeenLastCalledWith('m', expect.objectContaining({ frameStart: 0, frameEnd: 2 })));
});

it('requests the displayed generation and ignores its old response after a generation change', async () => {
  let resolveOld!: (value: Awaited<ReturnType<typeof fetchTrustCrops>>) => void;
  vi.mocked(fetchTrustCrops)
    .mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve; }))
    .mockResolvedValueOnce({
      matchId: 'm', generationId: 'gen-2', ballTeleportGeometryAvailable: true,
      ballTeleportReasonCodes: [], totalFrames: 1,
      crops: [{ frameStart: 2, frameEnd: 2, timestampStart: 2, timestampEnd: 2, score: 4, reasons: ['team_flips'] }],
    });
  const props = { matchId: 'm', frames: [{ Frame_ID: 2, Timestamp: 2, Ball: null, My_Team: [], Enemies: [] }], onClose: () => {}, onSeekToCrop: () => {} };
  const { rerender } = render(<TrustCropPanel {...props} generationId="gen-1" />);
  rerender(<TrustCropPanel {...props} generationId="gen-2" />);
  expect(await screen.findByText('Team flips')).toBeTruthy();
  resolveOld({ matchId: 'm', generationId: 'gen-1', ballTeleportGeometryAvailable: true,
    ballTeleportReasonCodes: [], totalFrames: 1,
    crops: [{ frameStart: 1, frameEnd: 1, timestampStart: 1, timestampEnd: 1, score: 9, reasons: ['track_switches'] }] });
  await waitFor(() => expect(screen.queryByText('Track switches')).toBeNull());
  expect(fetchTrustCrops).toHaveBeenNthCalledWith(1, 'm', 20, 'gen-1');
  expect(fetchTrustCrops).toHaveBeenNthCalledWith(2, 'm', 20, 'gen-2');
});

it('discloses unavailable physical geometry without hiding independent reasons', async () => {
  vi.mocked(fetchTrustCrops).mockResolvedValue({
    matchId: 'm', generationId: 'gen-1', ballTeleportGeometryAvailable: false,
    ballTeleportReasonCodes: ['CALIBRATION_UNAVAILABLE'], totalFrames: 1,
    crops: [{ frameStart: 0, frameEnd: 0, timestampStart: 0, timestampEnd: 0, score: 5, reasons: ['track_switches'] }],
  });
  render(<TrustCropPanel matchId="m" generationId="gen-1" frames={[]} onClose={() => {}} onSeekToCrop={() => {}} />);
  expect(await screen.findByText(/physical ball-teleport check unavailable/i)).toBeTruthy();
  expect(screen.getByText('Track switches')).toBeTruthy();
  expect(screen.getByText(/CALIBRATION_UNAVAILABLE/)).toBeTruthy();
});


it('does not carry saved crop state into a new generation', async () => {
  const crop = { frameStart: 10, frameEnd: 20, timestampStart: 1, timestampEnd: 2, score: 8, reasons: ['track_switches'] };
  vi.mocked(fetchTrustCrops)
    .mockResolvedValueOnce({ matchId: 'm', generationId: 'gen-1', ballTeleportGeometryAvailable: true, ballTeleportReasonCodes: [], totalFrames: 21, crops: [crop] })
    .mockResolvedValueOnce({ matchId: 'm', generationId: 'gen-2', ballTeleportGeometryAvailable: true, ballTeleportReasonCodes: [], totalFrames: 21, crops: [crop] });
  vi.mocked(createMatchIssue).mockResolvedValue({
    id: 'issue-1', matchId: 'm', bucket: 'tracking_failure', frameStart: 10, frameEnd: 20,
    timestampStart: 1, timestampEnd: 2, processingBackend: 'unknown', evidenceTarget: 'trust_eval',
    note: 'saved', createdAt: '2026-09-23T00:00:00Z', updatedAt: '2026-09-23T00:00:00Z',
  });
  const frames = Array.from({ length: 21 }, (_, index) => ({ Frame_ID: index, Timestamp: index / 10, Ball: null, My_Team: [], Enemies: [] }));
  const props = { matchId: 'm', frames, onClose: () => {}, onSeekToCrop: () => {} };
  const { rerender } = render(<TrustCropPanel {...props} generationId="gen-1" />);

  fireEvent.click(await screen.findByRole('button', { name: /save for training set/i }));
  expect(await screen.findByText(/saved for training set/i)).toBeTruthy();

  rerender(<TrustCropPanel {...props} generationId="gen-2" />);
  expect(await screen.findByRole('button', { name: /^save for training set$/i })).toBeTruthy();
});
