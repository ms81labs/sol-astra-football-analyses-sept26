import type { CameraProfile, UploadConfig } from '../types';

export interface PointInput {
  x: string;
  y: string;
}

interface BuildUploadConfigInput {
  isVideo: boolean;
  llmProvider: 'local' | 'cloud';
  attackDirection: 'left_to_right' | 'right_to_left';
  pointInputs: PointInput[];
  cameraProfile?: CameraProfile;
}

export function createEmptyPointInputs(): PointInput[] {
  return Array.from({ length: 4 }, () => ({ x: '', y: '' }));
}

export function buildUploadConfig({
  isVideo,
  llmProvider,
  attackDirection,
  pointInputs,
  autoHomography = false,
  cameraProfile = 'stitched_panoramic_view',
}: BuildUploadConfigInput & { autoHomography?: boolean }): UploadConfig {
  if (!isVideo) {
    return {
      attackDirection,
      llmProvider,
      manualHomographyPoints: [],
      cameraProfile,
    };
  }

  // Auto-detect: let backend try pitch_detector.py first
  if (autoHomography) {
    return {
      attackDirection,
      llmProvider,
      manualHomographyPoints: [],
      autoHomography: true,
      cameraProfile,
    };
  }

  // Manual: require all 4 points
  const points = pointInputs.map(({ x, y }) => {
    if (x.trim() === '' || y.trim() === '') {
      throw new Error('Video uploads require four manual homography points, or enable Auto-detect.');
    }
    const parsedX = Number(x);
    const parsedY = Number(y);
    if (!Number.isFinite(parsedX) || !Number.isFinite(parsedY)) {
      throw new Error('Video uploads require four manual homography points, or enable Auto-detect.');
    }
    return { x: parsedX, y: parsedY };
  });

  return {
    attackDirection,
    llmProvider,
    manualHomographyPoints: points,
    cameraProfile,
  };
}
