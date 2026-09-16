import { useMemo } from 'react';
import type { FormationSegment, MatchBenchmarkSummary, MatchStats, PlayerProfile, ShotSummary } from '../types';
import type { MetricAvailability } from '../utils/workbench';
import MetricInspector from './MetricInspector';

interface StatsPanelProps {
    stats: MatchStats | null;
    benchmark?: MatchBenchmarkSummary | null;
    formationTimeline?: FormationSegment[];
    formationAvailability?: { availability: string; reasonCodes?: string[]; value?: string | null };
    shotSummary?: ShotSummary | null;
    playerProfiles?: PlayerProfile[];
    comparisonStats?: MatchStats | null;
    comparisonName?: string;
    metricAvailability?: MetricAvailability[];
}

function StatBar({ label, value, maxValue, color }: { label: string; value: number; maxValue: number; color: string }) {
    const pct = Math.min((value / maxValue) * 100, 100);
    return (
        <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 w-20 text-right shrink-0">{label}</span>
            <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
            </div>
            <span className="text-slate-300 font-mono w-16 text-right">{value}</span>
        </div>
    );
}

function ComparisonArrow({ current, previous }: { current: number; previous: number }) {
    if (current === previous) return <span className="text-slate-600">—</span>;
    const diff = current - previous;
    const isUp = diff > 0;
    return (
        <span className={`text-xs font-mono ${isUp ? 'text-emerald-400' : 'text-red-400'}`}>
            {isUp ? '▲' : '▼'} {Math.abs(diff)}
        </span>
    );
}

function FormationDiagram({ formation }: { formation: string | null }) {
    if (!formation || formation === '-') return <span className="text-slate-500">—</span>;

    const rows = formation.split('-').map(Number).filter(n => !isNaN(n));
    const totalRows = rows.length;

    return (
        <div className="flex flex-col items-center gap-1 mt-1">
            {rows.map((count, rowIdx) => (
                <div key={rowIdx} className="flex gap-1.5 justify-center">
                    {Array.from({ length: count }).map((_, dotIdx) => (
                        <div
                            key={dotIdx}
                            className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_4px_rgba(59,130,246,0.5)]"
                            style={{ opacity: 0.6 + (rowIdx / totalRows) * 0.4 }}
                        />
                    ))}
                </div>
            ))}
            {/* Goalkeeper */}
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-400 shadow-[0_0_4px_rgba(234,179,8,0.5)] mt-0.5" />
        </div>
    );
}

function ContributionPill({ team }: { team: 'my_team' | 'enemy' }) {
    return (
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${team === 'my_team' ? 'bg-blue-500/15 text-blue-300' : 'bg-red-500/15 text-red-300'}`}>
            {team === 'my_team' ? 'My Team' : 'Enemy'}
        </span>
    );
}

export default function StatsPanel({
    stats,
    benchmark = null,
    formationTimeline = [],
    formationAvailability,
    shotSummary,
    playerProfiles = [],
    comparisonStats,
    comparisonName,
    metricAvailability = [],
}: StatsPanelProps) {
    const [topCreator, topFinisher, topBallWinner] = useMemo(() => [
        [...playerProfiles]
            .filter((player) => player.xgCreated > 0 || player.throughBalls > 0)
            .sort((left, right) => right.xgCreated - left.xgCreated || right.throughBalls - left.throughBalls || left.playerId - right.playerId)[0],
        [...playerProfiles]
            .filter((player) => player.xgTaken > 0 || player.shots > 0)
            .sort((left, right) => right.xgTaken - left.xgTaken || right.shots - left.shots || left.playerId - right.playerId)[0],
        [...playerProfiles]
            .filter((player) => player.ballWins > 0)
            .sort((left, right) => right.ballWins - left.ballWins || right.interceptions - left.interceptions || left.playerId - right.playerId)[0],
    ], [playerProfiles]);
    if (!stats) return null;

    const isBallSignalUntrusted = stats.ballSignalStatus === 'untrusted';
    const isBenchmarkTruthGateFailed = benchmark ? !benchmark.fiveMinuteTruthReady : false;
    const showTacticalInterpretation = !isBallSignalUntrusted && !isBenchmarkTruthGateFailed;
    const maxDist = Math.max(stats.myTeamDistance ?? 0, stats.enemyDistance ?? 0, 1);
    const withheld = (record?: MetricAvailability) => record != null && record.availability !== 'available' && record.availability !== 'experimental';
    const physical = metricAvailability.find((metric) => metric.metric === 'my_team_distance_m');
    const speed = metricAvailability.find((metric) => metric.metric === 'my_team_top_speed_kmh');
    const sprints = metricAvailability.find((metric) => metric.metric === 'my_team_sprints');
    const physicalUnavailable = withheld(physical) || stats.myTeamDistance == null || stats.enemyDistance == null;
    const speedUnavailable = withheld(speed) || withheld(sprints) || physicalUnavailable || stats.myTeamTopSpeed == null || stats.enemyTopSpeed == null || stats.myTeamSprints == null || stats.enemySprints == null;
    const myPpda = metricAvailability.find((metric) => metric.metric === 'my_team_ppda');
    const enemyPpda = metricAvailability.find((metric) => metric.metric === 'enemy_ppda');
    const ppdaUnavailable = (record?: { availability: string } | undefined, value?: number | null) =>
      value == null || (record != null && record.availability !== 'available' && record.availability !== 'experimental');
    const formationWithheld = stats.formation == null
      || stats.formation === '-'
      || (formationAvailability != null
      && formationAvailability.availability !== 'available'
      && formationAvailability.availability !== 'experimental');

    return (
        <div className="w-full max-w-4xl mt-4 space-y-3">
            {stats.ballSignalStatus === 'untrusted' && (
                <div className="flex items-start gap-3 rounded-lg border border-amber-600/60 bg-amber-900/30 p-3">
                    <div>
                        <p className="text-sm font-semibold text-amber-300">Ball signal untrusted</p>
                        <p className="text-xs text-amber-400/80 mt-0.5">Possession, experimental shot quality, and event analytics may be unreliable. Report issues using "Report Issue".</p>
                        <p className="text-xs text-amber-300/80 mt-1">Tracking-safe distance and speed remain visible while tactical interpretation is paused.</p>
                    </div>
                </div>
            )}

            {benchmark && isBenchmarkTruthGateFailed && (
                <div className="flex items-start gap-3 rounded-lg border border-amber-600/60 bg-amber-900/30 p-3">
                    <div>
                        <p className="text-sm font-semibold text-amber-300">Review-only: truth gates not met</p>
                        <p className="text-xs text-amber-400/80 mt-0.5">
                            Ball coverage, controlled possession, or event richness is below the threshold for tactical interpretation.
                        </p>
                        {benchmark.truthGateReasons.length > 0 && (
                            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-amber-300/80">
                                {benchmark.truthGateReasons.slice(0, 4).map((reason) => (
                                    <li key={reason}>{reason}</li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>
            )}

            <div className={`grid gap-3 ${showTacticalInterpretation ? 'grid-cols-2 lg:grid-cols-4' : 'grid-cols-1 lg:grid-cols-2'}`}>
                <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
                    <h4 className="text-xs text-slate-400 mb-2 font-medium uppercase tracking-wide">Distance (m)</h4>
                    {physicalUnavailable ? (
                        <p className="text-xs text-slate-400">Unavailable</p>
                    ) : (
                    <div className="space-y-1.5">
                        <StatBar label="My Team" value={stats.myTeamDistance ?? 0} maxValue={maxDist} color="#3b82f6" />
                        <StatBar label="Enemy" value={stats.enemyDistance ?? 0} maxValue={maxDist} color="#ef4444" />
                    </div>
                    )}
                    {comparisonStats && !physicalUnavailable && stats.myTeamDistance != null && stats.enemyDistance != null && comparisonStats.myTeamDistance != null && comparisonStats.enemyDistance != null && (
                        <div className="mt-1 flex gap-4 justify-center text-xs">
                            <ComparisonArrow current={stats.myTeamDistance} previous={comparisonStats.myTeamDistance} />
                            <ComparisonArrow current={stats.enemyDistance} previous={comparisonStats.enemyDistance} />
                        </div>
                    )}
                    {physicalUnavailable && physical && (
                        <div className="mt-3">
                            <MetricInspector
                                metric={physical.metric}
                                unit={physical.unit || 'metres'}
                                denominator={physical.denominator || 'identity_continuous_eligible_seconds'}
                                definitionVersion={physical.definitionVersion}
                                eligibleDuration={physical.eligibleSeconds ?? 0}
                                exclusions={physical.reasonCodes}
                                value={physical.value}
                                availability={physical.availability}
                            />
                        </div>
                    )}
                </div>

                <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
                    <h4 className="text-xs text-slate-400 mb-2 font-medium uppercase tracking-wide">Speed & Sprints</h4>
                    {speedUnavailable ? (
                        <p className="text-xs text-slate-400">Unavailable</p>
                    ) : (
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                        <div>
                            <span className="text-slate-500">Top Speed</span>
                            <p className="text-blue-400 font-mono font-semibold">{stats.myTeamTopSpeed} km/h</p>
                        </div>
                        <div>
                            <span className="text-slate-500">Top Speed</span>
                            <p className="text-red-400 font-mono font-semibold">{stats.enemyTopSpeed} km/h</p>
                        </div>
                        <div>
                            <span className="text-slate-500">Sprints</span>
                            <p className="text-blue-400 font-mono font-semibold">{stats.myTeamSprints}</p>
                        </div>
                        <div>
                            <span className="text-slate-500">Sprints</span>
                            <p className="text-red-400 font-mono font-semibold">{stats.enemySprints}</p>
                        </div>
                    </div>
                    )}
                </div>

                {showTacticalInterpretation && (
                    <>
                        {/* Possession */}
                        {stats.possession !== null && <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
                            <h4 className="text-xs text-slate-400 mb-2 font-medium uppercase tracking-wide">Possession</h4>
                            <div className="flex items-center gap-2">
                                <div className="flex-1 h-3 bg-red-500/30 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-blue-500 rounded-full transition-all duration-500"
                                        style={{ width: `${stats.possession}%` }}
                                    />
                                </div>
                            </div>
                            <div className="flex justify-between mt-1 text-xs font-mono">
                                <span className="text-blue-400">{stats.possession}%</span>
                                <span className="text-red-400">{100 - stats.possession}%</span>
                            </div>
                            {comparisonStats && comparisonStats.possession !== null && (
                                <div className="mt-1 flex justify-center">
                                    <ComparisonArrow current={stats.possession} previous={comparisonStats.possession} />
                                </div>
                            )}
                        </div>}

                        {/* Formation */}
                        <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
                            <h4 className="text-xs text-slate-400 mb-1 font-medium uppercase tracking-wide">Formation</h4>
                            {formationWithheld ? (
                                <>
                                    <p className="text-xl font-bold text-slate-400 font-mono mb-1">Unavailable</p>
                                    {formationAvailability?.reasonCodes?.length ? (
                                        <p className="text-[11px] text-slate-500 font-mono">{formationAvailability.reasonCodes.join(', ')}</p>
                                    ) : null}
                                </>
                            ) : (
                                <>
                                    <p className="text-xl font-bold text-emerald-400 font-mono mb-1">{stats.formation}</p>
                                    <FormationDiagram formation={stats.formation} />
                                    {formationTimeline.length > 0 && (
                                        <div className="mt-3 space-y-1 border-t border-slate-700 pt-2">
                                            {formationTimeline.slice(-3).map((segment) => (
                                                <div key={`${segment.startFrameId}-${segment.endFrameId}-${segment.formation}`} className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                                                    <span>{segment.formation}</span>
                                                    <span>{segment.startTimestamp.toFixed(1)}s-{segment.endTimestamp.toFixed(1)}s</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </>
                )}
            </div>

            {showTacticalInterpretation && (
                <>
                    <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
                        <h4 className="text-xs text-slate-400 mb-3 font-medium uppercase tracking-wide">Defensive Shape</h4>
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                            <div className="rounded-lg border border-slate-700 bg-slate-900/70 p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-semibold text-blue-300">My Team</span>
                                    <span className="text-[11px] text-slate-500">Out of possession</span>
                                </div>
                                <div className="grid grid-cols-2 gap-3 text-xs">
                                    <div>
                                        <p className="text-slate-500">Line Height</p>
                                        <p className="text-emerald-400 font-mono font-semibold">{stats.myTeamDefensiveLineHeight == null ? 'Unavailable' : stats.myTeamDefensiveLineHeight}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-500">Team Length</p>
                                        <p className="text-slate-300 font-mono font-semibold">{stats.myTeamDefensiveTeamLength == null ? 'Unavailable' : stats.myTeamDefensiveTeamLength}</p>
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-lg border border-slate-700 bg-slate-900/70 p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-semibold text-red-300">Enemy</span>
                                    <span className="text-[11px] text-slate-500">Out of possession</span>
                                </div>
                                <div className="grid grid-cols-2 gap-3 text-xs">
                                    <div>
                                        <p className="text-slate-500">Line Height</p>
                                        <p className="text-emerald-400 font-mono font-semibold">{stats.enemyDefensiveLineHeight == null ? 'Unavailable' : stats.enemyDefensiveLineHeight}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-500">Team Length</p>
                                        <p className="text-slate-300 font-mono font-semibold">{stats.enemyDefensiveTeamLength == null ? 'Unavailable' : stats.enemyDefensiveTeamLength}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
                        <h4 className="text-xs text-slate-400 mb-3 font-medium uppercase tracking-wide">Pressing</h4>
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                            <div className="rounded-lg border border-slate-700 bg-slate-900/70 p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-semibold text-blue-300">My Team</span>
                                    <span className="text-[11px] text-slate-500">Lower PPDA = more aggressive</span>
                                </div>
                                <div className="grid grid-cols-3 gap-3 text-xs">
                                    <div>
                                        <p className="text-slate-500">PPDA</p>
                                        <p className="text-emerald-400 font-mono font-semibold">{ppdaUnavailable(myPpda, stats.myTeamPpda) ? 'Unavailable' : stats.myTeamPpda}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-500">High Regains</p>
                                        <p className="text-slate-300 font-mono font-semibold">{stats.myTeamHighPressRegains}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-500">Counterpress</p>
                                        <p className="text-slate-300 font-mono font-semibold">{stats.myTeamCounterpressRecoverySeconds == null ? 'Unavailable' : `${stats.myTeamCounterpressRecoverySeconds}s`}</p>
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-lg border border-slate-700 bg-slate-900/70 p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-semibold text-red-300">Enemy</span>
                                    <span className="text-[11px] text-slate-500">Lower PPDA = more aggressive</span>
                                </div>
                                <div className="grid grid-cols-3 gap-3 text-xs">
                                    <div>
                                        <p className="text-slate-500">PPDA</p>
                                        <p className="text-emerald-400 font-mono font-semibold">{ppdaUnavailable(enemyPpda, stats.enemyPpda) ? 'Unavailable' : stats.enemyPpda}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-500">High Regains</p>
                                        <p className="text-slate-300 font-mono font-semibold">{stats.enemyHighPressRegains}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-500">Counterpress</p>
                                        <p className="text-slate-300 font-mono font-semibold">{stats.enemyCounterpressRecoverySeconds == null ? 'Unavailable' : `${stats.enemyCounterpressRecoverySeconds}s`}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </>
            )}

            {/* Match comparison label */}
            {showTacticalInterpretation && comparisonStats && comparisonName && (
                <div className="text-xs text-slate-500 text-center">
                    Compared to: <span className="text-slate-400 font-mono">{comparisonName}</span>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {showTacticalInterpretation && shotSummary && (
                    <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
                        <h4 className="text-xs text-slate-400 mb-3 font-medium uppercase tracking-wide">Shot Summary</h4>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                            <div className="rounded-lg border border-slate-700 bg-slate-900/70 p-3">
                                <p className="text-xs text-slate-500 mb-1">My Team Shots</p>
                                <p className="text-2xl font-bold text-rose-300">{shotSummary?.myTeamShots ?? 0}</p>
                                <p className="text-xs text-slate-400">{shotSummary?.myTeamBoxShots ?? 0} in box</p>
                                <p className="text-xs text-emerald-400 mt-1">{shotSummary?.myTeamXg == null ? 'Unavailable' : `experimental shot quality ${shotSummary.myTeamXg.toFixed(2)}`}</p>
                            </div>
                            <div className="rounded-lg border border-slate-700 bg-slate-900/70 p-3">
                                <p className="text-xs text-slate-500 mb-1">Enemy Shots</p>
                                <p className="text-2xl font-bold text-rose-400">{shotSummary?.enemyShots ?? 0}</p>
                                <p className="text-xs text-slate-400">{shotSummary?.enemyBoxShots ?? 0} in box</p>
                                <p className="text-xs text-emerald-400 mt-1">{shotSummary?.enemyXg == null ? 'Unavailable' : `experimental shot quality ${shotSummary.enemyXg.toFixed(2)}`}</p>
                            </div>
                        </div>
                    </div>
                )}

                {showTacticalInterpretation && (
                    <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm">
                    <h4 className="text-xs text-slate-400 mb-3 font-medium uppercase tracking-wide">Player Profiles</h4>
                    {(topCreator || topFinisher || topBallWinner) && (
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
                            {topCreator && (
                                <div className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-500">Top Creator</p>
                                    <div className="mt-1 flex items-center gap-2">
                                        <span className="text-sm font-semibold text-slate-100 font-mono">#{topCreator.playerId}</span>
                                        <ContributionPill team={topCreator.team} />
                                    </div>
                                    <p className="mt-1 text-xs text-emerald-400">{topCreator.summaryLine}</p>
                                </div>
                            )}
                            {topFinisher && (
                                <div className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-500">Top Finisher</p>
                                    <div className="mt-1 flex items-center gap-2">
                                        <span className="text-sm font-semibold text-slate-100 font-mono">#{topFinisher.playerId}</span>
                                        <ContributionPill team={topFinisher.team} />
                                    </div>
                                    <p className="mt-1 text-xs text-rose-300">{topFinisher.summaryLine}</p>
                                </div>
                            )}
                            {topBallWinner && (
                                <div className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-500">Top Ball Winner</p>
                                    <div className="mt-1 flex items-center gap-2">
                                        <span className="text-sm font-semibold text-slate-100 font-mono">#{topBallWinner.playerId}</span>
                                        <ContributionPill team={topBallWinner.team} />
                                    </div>
                                    <p className="mt-1 text-xs text-cyan-300">{topBallWinner.summaryLine}</p>
                                </div>
                            )}
                        </div>
                    )}
                    <div className="space-y-2">
                        {playerProfiles.slice(0, 4).map((player) => (
                            <div key={`${player.team}-${player.playerId}`} className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-sm font-semibold text-slate-100 font-mono">#{player.playerId}</span>
                                    <ContributionPill team={player.team} />
                                    <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                                        {player.profileLabel}
                                    </span>
                                    <span className="ml-auto text-xs font-mono text-emerald-400">{player.impactScore} pts</span>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-xs text-slate-400">
                                    <span>{player.passes} passes, {player.crosses} crosses</span>
                                    <span>{player.throughBalls} through balls, {player.shots} shots</span>
                                    <span>{player.ballWins} ball wins, {player.interceptions} interceptions</span>
                                    <span>{player.xgCreated.toFixed(2)} experimental shot quality created, {player.xgTaken.toFixed(2)} experimental shot quality taken</span>
                                    <span>{player.involvements} involvements</span>
                                    <span>{player.physicalTotalsWithheld ? 'Physical totals withheld' : `${player.totalDistance} m, ${player.topSpeed} km/h`}</span>
                                </div>
                                <p className="text-[11px] text-slate-500 mt-1 font-mono">
                                    Avg position {player.avgX}, {player.avgY}
                                </p>
                                <p className="text-xs text-slate-300 mt-1">{player.summaryLine}</p>
                            </div>
                        ))}
                        {playerProfiles.length === 0 && (
                            <div className="rounded-lg border border-dashed border-slate-700 px-3 py-4 text-xs text-slate-500 text-center">
                                Waiting for derived player profiles.
                            </div>
                        )}
                    </div>
                    </div>
                )}
            </div>
        </div>
    );
}
