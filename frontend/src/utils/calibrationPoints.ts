import type { PointInput } from './uploadConfig';

export function getNextCalibrationPointIndex(pointInputs: PointInput[]): number | null {
  const nextIndex = pointInputs.findIndex((point) => point.x.trim() === '' || point.y.trim() === '');
  return nextIndex === -1 ? null : nextIndex;
}

export function projectPreviewClickToSource({
  clickX,
  clickY,
  rectLeft,
  rectTop,
  rectWidth,
  rectHeight,
  sourceWidth,
  sourceHeight,
}: {
  clickX: number;
  clickY: number;
  rectLeft: number;
  rectTop: number;
  rectWidth: number;
  rectHeight: number;
  sourceWidth: number;
  sourceHeight: number;
}): { x: number; y: number } {
  const relativeX = Math.min(Math.max(clickX - rectLeft, 0), rectWidth);
  const relativeY = Math.min(Math.max(clickY - rectTop, 0), rectHeight);

  return {
    x: Math.round((relativeX / rectWidth) * sourceWidth),
    y: Math.round((relativeY / rectHeight) * sourceHeight),
  };
}
