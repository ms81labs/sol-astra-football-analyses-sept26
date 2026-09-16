import type { EventTag, EventType, FrameData, ReviewRange } from '../types';

interface TimelineProps {
    matchData: FrameData[];
    currentFrame: number;
    isPlaying: boolean;
    fps: number;
    events: EventTag[];
    reviewRange?: ReviewRange | null;
    onRangeChange?: (range: ReviewRange | null) => void;
    onSeek: (frame: number) => void;
    onTogglePlay: () => void;
}

interface EventTaggerProps {
    currentFrame: number;
    timestamp: number;
    onAddEvent: (event: EventTag) => void;
}

const EVENT_PRESETS: { type: EventType; label: string; emoji: string }[] = [
    { type: 'goal', label: 'Goal', emoji: '⚽' },
    { type: 'foul', label: 'Foul', emoji: '🟨' },
    { type: 'corner', label: 'Corner', emoji: '🚩' },
    { type: 'counter', label: 'Counter', emoji: '⚡' },
    { type: 'offside', label: 'Offside', emoji: '🏳️' },
];

const EVENT_COLORS: Record<EventType, string> = {
    goal: '#eab308',
    foul: '#f59e0b',
    corner: '#22c55e',
    counter: '#3b82f6',
    offside: '#ef4444',
    pass: '#14b8a6',
    progressive_pass: '#10b981',
    cross: '#06b6d4',
    shot: '#f43f5e',
    tackle: '#84cc16',
    recovery: '#8b5cf6',
    turnover: '#f97316',
    through_ball: '#0ea5e9',
    interception: '#ec4899',
    carry: '#f59e0b',
    box_entry: '#ef4444',
    final_third_entry: '#3b82f6',
    zone_advancement: '#22c55e',
    custom: '#a855f7',
};

function EventTagger({ currentFrame, timestamp, onAddEvent }: EventTaggerProps) {
    return (
        <div className="flex items-center gap-1.5 flex-wrap">
            {EVENT_PRESETS.map(({ type, label, emoji }) => (
                <button
                    key={type}
                    onClick={() => onAddEvent({ frame: currentFrame, timestamp, label, type })}
                    className="bg-slate-800 hover:bg-slate-700 px-2 py-1 rounded text-xs transition-colors border border-slate-700 flex items-center gap-1"
                    title={`Tag as ${label}`}
                >
                    {emoji} {label}
                </button>
            ))}
        </div>
    );
}

function normalizeRange(startFrame: number, endFrame: number): ReviewRange {
    return startFrame <= endFrame
        ? { startFrame, endFrame }
        : { startFrame: endFrame, endFrame: startFrame };
}

export default function Timeline({
    matchData,
    currentFrame,
    isPlaying,
    fps,
    events,
    reviewRange = null,
    onRangeChange,
    onSeek,
    onTogglePlay,
}: TimelineProps) {
    const maxFrame = matchData.length > 0 ? matchData.length - 1 : 0;
    const reviewStartFrame = reviewRange?.startFrame ?? currentFrame;
    const reviewEndFrame = reviewRange?.endFrame ?? currentFrame;
    const activeEventIndex = events.findIndex((event) => event.frame === currentFrame);

    return (
        <div className="w-full max-w-4xl mt-6 bg-slate-900 p-3 rounded-lg border border-slate-700 space-y-2">
            <div className="flex items-center space-x-4">
                <button
                    onClick={onTogglePlay}
                    disabled={matchData.length === 0}
                    aria-label={isPlaying ? 'Pause' : 'Play'}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white w-12 h-12 rounded-full flex items-center justify-center transition focus:outline-none disabled:opacity-50 shrink-0"
                >
                    {isPlaying ? '⏸' : '▶'}
                </button>

                <div className="flex-grow flex flex-col justify-center relative">
                    {/* Event markers */}
                    <div className="relative h-1 mb-1">
                        {events.map((evt, idx) => {
                            const pct = maxFrame > 0 ? (evt.frame / maxFrame) * 100 : 0;
                            return (
                                <button
                                    key={idx}
                                    onClick={() => onSeek(evt.frame)}
                                    aria-label={`${evt.label} at ${evt.timestamp} seconds`}
                                    className="absolute w-2.5 h-2.5 rounded-full -top-0.5 transform -translate-x-1/2 hover:scale-150 transition-transform z-10 border border-slate-900"
                                    style={{ left: `${pct}%`, backgroundColor: EVENT_COLORS[evt.type] }}
                                    title={`${evt.label} @ ${evt.timestamp}s`}
                                />
                            );
                        })}
                    </div>

                    <input
                        type="range"
                        min="0"
                        max={maxFrame}
                        value={currentFrame}
                        onChange={(e) => onSeek(Number(e.target.value))}
                        aria-label="Timeline scrubber"
                        className="w-full accent-emerald-500"
                        disabled={matchData.length === 0}
                    />
                    <div className="flex justify-between text-xs text-slate-400 mt-1 font-mono">
                        <span>Time: {matchData[currentFrame]?.Timestamp || '0.00'}s</span>
                        <span>Frame {currentFrame} / {maxFrame}</span>
                    </div>
                    {events.length > 0 && (
                        <select
                            aria-label="Jump to event"
                            value={activeEventIndex < 0 ? '' : String(activeEventIndex)}
                            onChange={(e) => {
                                const event = events[Number(e.target.value)];
                                if (event) onSeek(event.frame);
                            }}
                            className="mt-2 w-full bg-slate-800 text-slate-200 text-xs px-2 py-1 rounded border border-slate-700"
                        >
                            <option value="">Jump to event</option>
                            {events.map((event, index) => (
                                <option key={index} value={index}>{event.label} @ {event.timestamp}s</option>
                            ))}
                        </select>
                    )}
                </div>

                <div className="text-sm font-mono bg-slate-800 px-3 py-1 rounded border border-slate-700 shrink-0">
                    {fps} FPS
                </div>
            </div>

            <div className="flex items-center gap-2 flex-wrap text-xs">
                <span className="text-slate-500">Review range:</span>
                <span className="font-mono text-slate-300">
                    {reviewRange ? `${reviewStartFrame} - ${reviewEndFrame}` : 'not set'}
                </span>
                <button
                    type="button"
                    onClick={() => onRangeChange?.({ startFrame: currentFrame, endFrame: currentFrame })}
                    disabled={matchData.length === 0 || !onRangeChange}
                    className="px-2 py-1 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 transition-colors disabled:opacity-50"
                >
                    Set Range Start
                </button>
                <button
                    type="button"
                    onClick={() => onRangeChange?.(normalizeRange(reviewRange?.startFrame ?? currentFrame, currentFrame))}
                    disabled={matchData.length === 0 || !onRangeChange}
                    className="px-2 py-1 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 transition-colors disabled:opacity-50"
                >
                    Set Range End
                </button>
                <button
                    type="button"
                    onClick={() => onRangeChange?.(null)}
                    disabled={matchData.length === 0 || !onRangeChange}
                    className="px-2 py-1 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 transition-colors disabled:opacity-50"
                >
                    Clear Range
                </button>
            </div>

            {/* Event tagger row */}
            {matchData.length > 0 && (
                <div className="flex items-center gap-3 pt-2 border-t border-slate-800">
                    <span className="text-xs text-slate-500 shrink-0">Tag:</span>
                    <EventTagger
                        currentFrame={currentFrame}
                        timestamp={matchData[currentFrame]?.Timestamp || 0}
                        onAddEvent={(evt) => {
                            // This is handled via the parent's onAddEvent - we pass it through
                            // The parent (App) provides the actual handler
                            const event = new CustomEvent('add-event', { detail: evt });
                            window.dispatchEvent(event);
                        }}
                    />
                    {events.length > 0 && (
                        <span className="text-xs text-slate-600 ml-auto">{events.length} tag{events.length > 1 ? 's' : ''}</span>
                    )}
                </div>
            )}
        </div>
    );
}
