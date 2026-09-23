import ModalDialog from './ModalDialog';
import { useEffect, useState } from 'react';
import { findNearestFrameIndex } from '../utils/videoSync';
import type { FrameData, TrustCrop, TrustCropsResponse } from '../types';
import { createMatchIssue, fetchTrustCrops } from '../utils/api';

interface TrustCropPanelProps {
    matchId: string;
    generationId?: string;
    frames: FrameData[];
    onClose: () => void;
    onSeekToCrop: (frame: number) => void;
}

const REASON_LABELS: Record<string, { label: string; color: string }> = {
    ball_teleport: { label: 'Ball teleport', color: 'bg-red-900/50 text-red-300 border border-red-700' },
    track_switches: { label: 'Track switches', color: 'bg-orange-900/50 text-orange-300 border border-orange-700' },
    team_flips: { label: 'Team flips', color: 'bg-amber-900/50 text-amber-300 border border-amber-700' },
    possession_gap: { label: 'Possession gap', color: 'bg-yellow-900/50 text-yellow-300 border border-yellow-700' },
};

function formatTimestamp(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function ScoreBar({ score }: { score: number }) {
    const maxScore = 20;
    const pct = Math.min((score / maxScore) * 100, 100);
    const color = pct > 75 ? 'bg-red-500' : pct > 40 ? 'bg-amber-500' : 'bg-yellow-500';
    return (
        <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-xs font-mono text-slate-400 w-8 text-right">{score.toFixed(1)}</span>
        </div>
    );
}

export default function TrustCropPanel({ matchId, generationId, frames, onClose, onSeekToCrop }: TrustCropPanelProps) {
    const [data, setData] = useState<TrustCropsResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<Error | null>(null);
    const [saveError, setSaveError] = useState<Error | null>(null);
    const [savedCropKeys, setSavedCropKeys] = useState<Set<string>>(() => new Set());
    const [savingCropKey, setSavingCropKey] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setData(null);
        setLoadError(null);
        setSaveError(null);
        setSavedCropKeys(new Set());
        setSavingCropKey(null);
        setIsLoading(true);
        fetchTrustCrops(matchId, 20, generationId)
            .then((result) => {
                if (!cancelled) {
                    setData(result);
                    setIsLoading(false);
                }
            })
            .catch((err: Error) => {
                if (!cancelled) {
                    setLoadError(err);
                    setIsLoading(false);
                }
            });
        return () => {
            cancelled = true;
        };
    }, [matchId, generationId]);

    const timestamps = frames.map(frame => frame.Timestamp);
    const crops: TrustCrop[] = data?.crops ?? [];
    const saveCropForTrainingSet = async (crop: TrustCrop) => {
        const cropKey = `${crop.frameStart}-${crop.frameEnd}`;
        setSavingCropKey(cropKey);
        setSaveError(null);
        try {
            await createMatchIssue(matchId, {
                bucket: 'tracking_failure',
                frameStart: findNearestFrameIndex(timestamps, crop.timestampStart),
                frameEnd: findNearestFrameIndex(timestamps, crop.timestampEnd),
                timestampStart: crop.timestampStart,
                timestampEnd: crop.timestampEnd,
                processingBackend: 'unknown',
                evidenceTarget: 'trust_eval',
                note: `Trust crop score ${crop.score.toFixed(1)}: ${crop.reasons.join(', ') || 'uncertain window'}`,
            });
            setSavedCropKeys((previous) => new Set(previous).add(cropKey));
        } catch (err) {
            setSaveError(err instanceof Error ? err : new Error('Failed to save trust crop.'));
        } finally {
            setSavingCropKey(null);
        }
    };

    return (
        <ModalDialog label="Trust Crop Queue" onClose={onClose}>
            <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col">
                <div className="flex items-center justify-between p-4 border-b border-slate-700 shrink-0">
                    <div className="flex items-center gap-3">
                        <h3 className="text-base font-semibold text-amber-400">Trust Crop Queue</h3>
                        {data && (
                            <span className="text-xs text-slate-400 bg-slate-900 px-2 py-0.5 rounded-full border border-slate-700">
                                {crops.length} uncertain windows
                            </span>
                        )}
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1 text-slate-400 hover:text-slate-200 transition"
                        aria-label="Close"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-4">
                    {isLoading && (
                        <div className="flex items-center justify-center py-12">
                            <div className="animate-spin h-6 w-6 border-2 border-amber-500 border-t-transparent rounded-full" />
                        </div>
                    )}

                    {loadError && (
                        <div className="text-red-400 text-sm p-3 bg-red-900/30 rounded-lg border border-red-800">
                            Failed to load trust crops: {loadError.message}
                        </div>
                    )}

                    {saveError && (
                        <div className="mb-3 text-red-400 text-sm p-3 bg-red-900/30 rounded-lg border border-red-800">
                            Failed to save trust crop: {saveError.message}
                        </div>
                    )}

                    {!isLoading && !loadError && (
                        <>
                            {!data?.ballTeleportGeometryAvailable && (
                                <p className="mb-3 rounded border border-amber-800 bg-amber-950/30 p-2 text-xs text-amber-300">
                                    Physical ball-teleport check unavailable ({data?.ballTeleportReasonCodes.join(', ') || 'geometry unavailable'}). Other review signals remain active.
                                </p>
                            )}
                            {crops.length === 0 ? (
                                <div className="text-slate-500 text-sm text-center py-8">
                                    <div className="mb-2">
                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 mx-auto text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                    </div>
                                    No uncertain windows detected — tracking looks clean.
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    <p className="text-xs text-slate-500 mb-4">
                                        Frame windows flagged by available heuristic scoring: track ID switches,
                                        team flip rate, possession gaps, and ball teleport distance when geometry is available. Higher score = more uncertain.
                                    </p>
                                    {crops.map((crop, idx) => (
                                        <CropRow
                                            key={`${crop.frameStart}-${crop.frameEnd}`}
                                            crop={crop}
                                            index={idx + 1}
                                            onSeek={(timestamp) => onSeekToCrop(findNearestFrameIndex(timestamps, timestamp))}
                                            onSave={saveCropForTrainingSet}
                                            isSaved={savedCropKeys.has(`${crop.frameStart}-${crop.frameEnd}`)}
                                            isSaving={savingCropKey === `${crop.frameStart}-${crop.frameEnd}`}
                                        />
                                    ))}
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </ModalDialog>
    );
}

function CropRow({
    crop,
    index,
    onSeek,
    onSave,
    isSaved,
    isSaving,
}: {
    crop: TrustCrop;
    index: number;
    onSeek: (frame: number) => void;
    onSave: (crop: TrustCrop) => void;
    isSaved: boolean;
    isSaving: boolean;
}) {
    const timeRange = `${formatTimestamp(crop.timestampStart)} – ${formatTimestamp(crop.timestampEnd)}`;
    const frameRange = crop.frameStart === crop.frameEnd
        ? `Frame ${crop.frameStart}`
        : `Frames ${crop.frameStart}–${crop.frameEnd}`;
    const timestampMid = (crop.timestampStart + crop.timestampEnd) / 2;

    return (
        <div className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 transition-colors">
            <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-500 w-4">#{index}</span>
                    <span className="text-sm font-semibold text-slate-200">{frameRange}</span>
                    <span className="text-xs text-slate-500">{timeRange}</span>
                </div>
                <button
                    type="button"
                    onClick={() => onSeek(timestampMid)}
                    className="text-xs text-slate-500 hover:text-amber-400 transition-colors shrink-0"
                >
                    Seek →
                </button>
            </div>

            <div className="mb-2">
                <ScoreBar score={crop.score} />
            </div>

            {crop.reasons.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    {crop.reasons.map((reason) => {
                        const info = REASON_LABELS[reason] ?? { label: reason, color: 'bg-slate-700 text-slate-300 border border-slate-600' };
                        return (
                            <span key={reason} className={`text-xs px-2 py-0.5 rounded-full font-medium ${info.color}`}>
                                {info.label}
                            </span>
                        );
                    })}
                </div>
            )}

            <div className="mt-3 flex items-center justify-between border-t border-slate-800 pt-2">
                <p className="text-[11px] text-slate-500">
                    Save metadata now; model training stays parked for the later detector lane.
                </p>
                <button
                    type="button"
                    onClick={() => onSave(crop)}
                    disabled={isSaved || isSaving}
                    className="rounded border border-amber-700/60 bg-amber-900/30 px-2 py-1 text-xs font-semibold text-amber-200 hover:bg-amber-900/50 disabled:opacity-50"
                >
                    {isSaved ? 'Saved for training set' : isSaving ? 'Saving...' : 'Save for training set'}
                </button>
            </div>
        </div>
    );
}
