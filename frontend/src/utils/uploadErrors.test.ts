import { describe, expect, it } from 'vitest';

import { getUploadFailureGuidance } from './uploadErrors';

describe('getUploadFailureGuidance', () => {
  it('returns manual-calibration guidance for auto-homography misses', () => {
    expect(
      getUploadFailureGuidance(
        'Homography could not be detected automatically. Please provide manualHomographyPoints (4 corner coordinates) when uploading.',
      ),
    ).toContain('Turn off "Auto-detect pitch"');
  });

  it('returns null for unrelated errors', () => {
    expect(getUploadFailureGuidance('detector unavailable')).toBeNull();
  });
});
