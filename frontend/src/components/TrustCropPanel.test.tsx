import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import TrustCropPanel from './TrustCropPanel';
import { createMatchIssue, fetchTrustCrops } from '../utils/api';

vi.mock('../utils/api', () => ({
  fetchTrustCrops: vi.fn(),
  createMatchIssue: vi.fn(),
}));

afterEach(cleanup);

describe('TrustCropPanel', () => {
  it('keeps loaded crops visible and labels a save failure correctly', async () => {
    vi.mocked(fetchTrustCrops).mockResolvedValue({
      matchId: 'match-1',
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

    render(<TrustCropPanel frames={Array.from({ length: 21 }, (_, index) => ({ Frame_ID: index, Timestamp: index / 10, Ball: null, My_Team: [], Enemies: [] }))} matchId="match-1" onClose={() => {}} onSeekToCrop={() => {}} />);

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
  vi.mocked(fetchTrustCrops).mockResolvedValue({ matchId: 'm', totalFrames: 3, crops: [{ frameStart: 100, frameEnd: 200, timestampStart: 0, timestampEnd: 2, score: 8, reasons: [] }] });
  const seek = vi.fn();
  render(<TrustCropPanel matchId="m" frames={frames} onClose={() => {}} onSeekToCrop={seek} />);
  fireEvent.click(await screen.findByRole('button', { name: /Seek/ }));
  expect(seek).toHaveBeenCalledWith(1);
  fireEvent.click(screen.getByRole('button', { name: /Save for training set/i }));
  await waitFor(() => expect(createMatchIssue).toHaveBeenLastCalledWith('m', expect.objectContaining({ frameStart: 0, frameEnd: 2 })));
});
