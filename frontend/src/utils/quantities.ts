export function splitScores({
    detectorScore,
    calibratedProbability,
    interval,
}: {
    detectorScore: number | null;
    calibratedProbability: number | null;
    interval: [number, number] | null;
}) {
    return {
        detectorScore,
        calibratedProbability,
        confidenceInterval: interval,
    };
}
