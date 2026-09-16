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
});
