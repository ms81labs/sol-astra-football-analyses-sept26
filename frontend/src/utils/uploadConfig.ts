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
  pitchLengthM?: number | null;
  pitchWidthM?: number | null;
  periods?: UploadConfig['periods'];
  rights?: UploadConfig['rights'];
}

export function createEmptyPointInputs(): PointInput[] {
  return Array.from({ length: 4 }, () => ({ x: '', y: '' }));
}

function withSetupFields(
  config: UploadConfig,
  extras: Pick<BuildUploadConfigInput, 'pitchLengthM' | 'pitchWidthM' | 'periods' | 'rights' | 'cameraProfile'>,
): UploadConfig {
  return {
    ...config,
    cameraProfile: extras.cameraProfile ?? config.cameraProfile ?? 'stitched_panoramic_view',
    pitchLengthM: extras.pitchLengthM ?? null,
    pitchWidthM: extras.pitchWidthM ?? null,
    periods: extras.periods ?? [],
    rights: extras.rights ?? { processingScope: 'local_only', cloudPermission: false, retentionClass: 'unknown' },
  };
}

export function buildUploadConfig({
  isVideo,
  llmProvider,
  attackDirection,
  pointInputs,
  autoHomography = false,
  cameraProfile = 'stitched_panoramic_view',
  pitchLengthM = null,
  pitchWidthM = null,
  periods = [],
  rights,
}: BuildUploadConfigInput & { autoHomography?: boolean }): UploadConfig {
  const setup = { pitchLengthM, pitchWidthM, periods, rights, cameraProfile };
  if (!isVideo) {
    return withSetupFields({
      attackDirection,
      llmProvider,
      manualHomographyPoints: [],
      cameraProfile,
    }, setup);
  }

  // Auto-detect: let backend try pitch_detector.py first
  if (autoHomography) {
    return withSetupFields({
      attackDirection,
      llmProvider,
      manualHomographyPoints: [],
      autoHomography: true,
      cameraProfile,
    }, setup);
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

  return withSetupFields({
    attackDirection,
    llmProvider,
    manualHomographyPoints: points,
    cameraProfile,
  }, setup);
}
