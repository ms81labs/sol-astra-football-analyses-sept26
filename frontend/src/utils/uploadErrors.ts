export function getUploadFailureGuidance(errorMessage: string | null): string | null {
  if (!errorMessage) {
    return null;
  }

  if (
    errorMessage.includes('Homography could not be detected automatically')
    || errorMessage.includes('manualHomographyPoints')
  ) {
    return 'Turn off "Auto-detect pitch", enter the four pitch corners in the calibration strip above, then upload the video again.';
  }

  return null;
}
