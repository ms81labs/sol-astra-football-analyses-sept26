import { describe, expect, it } from 'vitest';

import { getNextCalibrationPointIndex, projectPreviewClickToSource } from './calibrationPoints';

describe('calibrationPoints', () => {
  it('returns the first empty calibration slot in corner order', () => {
    expect(
      getNextCalibrationPointIndex([
        { x: '', y: '' },
        { x: '', y: '' },
        { x: '', y: '' },
        { x: '', y: '' },
      ]),
    ).toBe(0);

    expect(
      getNextCalibrationPointIndex([
        { x: '10', y: '20' },
        { x: '', y: '' },
        { x: '', y: '' },
        { x: '', y: '' },
      ]),
    ).toBe(1);
  });

  it('returns null when all calibration slots are filled', () => {
    expect(
      getNextCalibrationPointIndex([
        { x: '10', y: '20' },
        { x: '110', y: '20' },
        { x: '110', y: '220' },
        { x: '10', y: '220' },
      ]),
    ).toBeNull();
  });

  it('maps a preview click back into source-frame pixel coordinates', () => {
    expect(
      projectPreviewClickToSource({
        clickX: 110,
        clickY: 70,
        rectLeft: 10,
        rectTop: 20,
        rectWidth: 200,
        rectHeight: 100,
        sourceWidth: 1920,
        sourceHeight: 1080,
      }),
    ).toEqual({ x: 960, y: 540 });
  });
});
