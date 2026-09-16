import { describe, expect, it } from 'vitest';

import { buildUploadConfig, createEmptyPointInputs } from './uploadConfig';

describe('buildUploadConfig', () => {
  it('returns local-first JSON upload config without requiring points', () => {
    const config = buildUploadConfig({
      isVideo: false,
      llmProvider: 'local',
      attackDirection: 'left_to_right',
      pointInputs: createEmptyPointInputs(),
    });

    expect(config.attackDirection).toBe('left_to_right');
    expect(config.llmProvider).toBe('local');
    expect(config.manualHomographyPoints).toEqual([]);
    expect(config.cameraProfile).toBe('stitched_panoramic_view');
  });

  it('requires four complete points for video uploads', () => {
    expect(() =>
      buildUploadConfig({
        isVideo: true,
        llmProvider: 'local',
        attackDirection: 'left_to_right',
        pointInputs: createEmptyPointInputs(),
      }),
    ).toThrow(/manual homography/i);
  });

  it('builds manual homography points for video uploads when all fields are present', () => {
    const config = buildUploadConfig({
      isVideo: true,
      llmProvider: 'cloud',
      attackDirection: 'right_to_left',
      pointInputs: [
        { x: '10', y: '20' },
        { x: '110', y: '20' },
        { x: '110', y: '220' },
        { x: '10', y: '220' },
      ],
    });

    expect(config.llmProvider).toBe('cloud');
    expect(config.attackDirection).toBe('right_to_left');
    expect(config.manualHomographyPoints).toEqual([
      { x: 10, y: 20 },
      { x: 110, y: 20 },
      { x: 110, y: 220 },
      { x: 10, y: 220 },
    ]);
  });

  it('includes camera profile, pitch dimensions, periods and local-only rights', () => {
    const config = buildUploadConfig({
      isVideo: false,
      llmProvider: 'local',
      attackDirection: 'left_to_right',
      pointInputs: createEmptyPointInputs(),
      pitchLengthM: 105,
      pitchWidthM: 68,
      periods: [{ name: 'first_half', startSeconds: 0, endSeconds: 2700 }],
      rights: { processingScope: 'local_only', cloudPermission: false, retentionClass: 'review' },
    });

    expect(config.pitchLengthM).toBe(105);
    expect(config.periods?.[0]?.name).toBe('first_half');
    expect(config.rights?.cloudPermission).toBe(false);
    expect(config.rights?.retentionClass).toBe('review');
  });
});
