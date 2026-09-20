import { useState } from 'react';
import type { BackendEvent, PlayerProfile } from '../types';

interface PlayerDetailPanelProps {
    player: Partial<PlayerProfile>;
    events: BackendEvent[];
    identityContinuous?: boolean;
    onSplitIdentity?: () => void;
    onJoinIdentity?: (rightTrackId: string) => void;
    onValidateIdentity?: () => void;
}

type PlayerDetailSelection = PlayerDetailPanelProps['player'];

function formatTeam(team: PlayerProfile['team']) {
    return team === 'my_team' ? 'My Team' : 'Enemy';
}

function formatMetric(value: number | undefined) {
    return value ?? '—';
}

function isPlayerEvent(event: BackendEvent, player: PlayerDetailSelection) {
    if (event.team !== (player.team ?? 'my_team')) return false;
    if (player.playerId == null) return false;
    return event.fromTrackId === player.playerId || event.toTrackId === player.playerId;
}

export default function PlayerDetailPanel({ player, events, identityContinuous = false, onSplitIdentity, onJoinIdentity, onValidateIdentity }: PlayerDetailPanelProps) {
    const [joinTrackId, setJoinTrackId] = useState('');
    const recentEvents = events
        .filter((event) => isPlayerEvent(event, player))
        .sort((left, right) => {
            if (right.frameId !== left.frameId) return right.frameId - left.frameId;
            return right.timestamp - left.timestamp;
        })
        .slice(0, 4);
    const metric = (value: number | undefined) => (identityContinuous ? formatMetric(value) : '—');

    return (
        <aside className="w-full max-w-sm rounded-2xl border border-slate-700 bg-slate-900/90 p-4 shadow-lg shadow-slate-950/40">
            <div className="space-y-1 border-b border-slate-700 pb-3">
                <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-slate-50 font-mono">
                        {player.jerseyNumber != null ? `#${player.jerseyNumber}` : `Track ${player.playerId ?? '?'}`}
                    </h3>
                    {player.jerseyNumber != null && (
                        <span className="text-xs text-slate-500 font-mono">T{player.playerId ?? '?'}</span>
                    )}
                    <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300">
                        {formatTeam(player.team ?? 'my_team')}
                    </span>
                </div>
                <p className="text-sm font-medium text-emerald-300">{player.profileLabel?.trim() || 'Selected player'}</p>
                <p className="text-sm text-slate-300">{player.summaryLine?.trim() || 'No profile summary available.'}</p>
                {!identityContinuous && (
                    <p className="text-xs text-amber-200">Interval-limited observations. Totals withheld until identity continuity is validated.</p>
                )}
                {onValidateIdentity && !identityContinuous && (
                    <button
                        type="button"
                        onClick={onValidateIdentity}
                        className="mt-2 rounded border border-emerald-600/40 bg-emerald-900/20 px-2 py-1 text-[11px] font-semibold text-emerald-100 hover:bg-emerald-900/40"
                    >
                        Approve visible track interval
                    </button>
                )}
                {onSplitIdentity && (
                    <button
                        type="button"
                        onClick={onSplitIdentity}
                        className="mt-2 rounded border border-amber-600/40 bg-amber-900/20 px-2 py-1 text-[11px] font-semibold text-amber-100 hover:bg-amber-900/40"
                    >
                        Split identity
                    </button>
                )}
                {onJoinIdentity && (
                    <div className="mt-2 flex items-center gap-2">
                        <label className="flex min-w-0 flex-1 items-center gap-2 text-[11px] text-slate-400">
                            Join from track
                            <input
                                type="text"
                                inputMode="numeric"
                                value={joinTrackId}
                                onChange={(event) => setJoinTrackId(event.target.value)}
                                className="w-16 rounded border border-slate-600 bg-slate-800 px-1.5 py-1 font-mono text-[11px] text-slate-100"
                            />
                        </label>
                        <button
                            type="button"
                            onClick={() => {
                                const rightTrackId = joinTrackId.trim();
                                if (!rightTrackId || rightTrackId === String(player.playerId ?? '')) return;
                                onJoinIdentity(rightTrackId);
                            }}
                            className="rounded border border-amber-600/40 bg-amber-900/20 px-2 py-1 text-[11px] font-semibold text-amber-100 hover:bg-amber-900/40"
                        >
                            Join identity
                        </button>
                    </div>
                )}
            </div>

            <div className="grid grid-cols-2 gap-2 py-3 text-xs">
                <div className="rounded-lg bg-slate-800/80 px-3 py-2">
                    <div className="text-slate-500">Passes</div>
                    <div className="font-mono text-slate-100">{metric(player.passes)}</div>
                </div>
                <div className="rounded-lg bg-slate-800/80 px-3 py-2">
                    <div className="text-slate-500">Crosses</div>
                    <div className="font-mono text-slate-100">{metric(player.crosses)}</div>
                </div>
                <div className="rounded-lg bg-slate-800/80 px-3 py-2">
                    <div className="text-slate-500">Through Balls</div>
                    <div className="font-mono text-slate-100">{metric(player.throughBalls)}</div>
                </div>
                <div className="rounded-lg bg-slate-800/80 px-3 py-2">
                    <div className="text-slate-500">Shots</div>
                    <div className="font-mono text-slate-100">{metric(player.shots)}</div>
                </div>
                <div className="rounded-lg bg-slate-800/80 px-3 py-2">
                    <div className="text-slate-500">Ball Wins</div>
                    <div className="font-mono text-slate-100">{metric(player.ballWins)}</div>
                </div>
                <div className="rounded-lg bg-slate-800/80 px-3 py-2">
                    <div className="text-slate-500">Impact</div>
                    <div className="font-mono text-slate-100">
                        {identityContinuous ? (
                            <>
                                {player.impactScore ?? '—'}{player.impactScore !== undefined ? ' pts' : ''}
                            </>
                        ) : '—'}
                    </div>
                </div>
            </div>

            <div className="space-y-2 border-t border-slate-700 pt-3">
                <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Recent Events</h4>
                    <span className="text-[11px] text-slate-500">{recentEvents.length} filtered</span>
                </div>
                {recentEvents.length === 0 ? (
                    <p className="rounded-lg border border-dashed border-slate-700 px-3 py-3 text-xs text-slate-500">
                        No recent events for this player.
                    </p>
                ) : (
                    <ul className="space-y-2">
                        {recentEvents.map((event) => (
                            <li key={`${event.frameId}-${event.timestamp}-${event.type}`} className="rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2">
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-medium text-slate-100">{event.description}</span>
                                    <span className="text-[10px] font-mono text-slate-500">F{event.frameId}</span>
                                </div>
                                <div className="mt-1 text-[11px] text-slate-500 font-mono">
                                    {event.type} · {event.timestamp.toFixed(1)}s
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </aside>
    );
}
