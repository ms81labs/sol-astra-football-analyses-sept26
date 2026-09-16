import ModalDialog from './ModalDialog';
import { useDashboardData } from '../hooks/useDashboardData';

interface DashboardPanelProps {
    onClose: () => void;
    onSelectMatch?: (matchId: string) => void;
}

function DeltaBadge({ label, value }: { label: string; value: number | null }) {
    if (value === null) return <span className="text-slate-500 text-xs">{label}: Not measured</span>;
    if (value === 0) return <span className="text-slate-600 text-xs">{label}: —</span>;
    const isUp = value > 0;
    return (
        <span className={`text-xs font-mono ${isUp ? 'text-emerald-400' : 'text-red-400'}`}>
            {label}: {isUp ? '▲' : '▼'} {Math.abs(value)}{isUp ? '+' : ''}
        </span>
    );
}

function formatDate(dateStr: string) {
    const date = new Date(dateStr);
    if (Number.isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export default function DashboardPanel({ onClose, onSelectMatch }: DashboardPanelProps) {
    const { summary, comparison, trends, isLoading, error } = useDashboardData();

    return (
        <ModalDialog label="Season Dashboard" onClose={onClose}>
            <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl w-full max-w-3xl mx-4 max-h-[85vh] flex flex-col">
                <div className="flex items-center justify-between p-4 border-b border-slate-700 shrink-0">
                    <h3 className="text-base font-semibold text-emerald-400">Season Dashboard</h3>
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

                <div className="flex-1 overflow-y-auto p-4 space-y-6">
                    {isLoading && (
                        <div className="flex items-center justify-center py-8">
                            <div className="animate-spin h-6 w-6 border-2 border-emerald-500 border-t-transparent rounded-full" />
                        </div>
                    )}

                    {error && (
                        <div className="text-red-400 text-sm p-3 bg-red-900/30 rounded-lg border border-red-800">
                            Failed to load dashboard: {error.message}
                        </div>
                    )}

                    {!isLoading && !error && (
                        <>
                            {/* Summary Stats */}
                            <section>
                                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Season Summary</h4>
                                {summary && summary.matchCount === 0 ? (
                                    <div className="text-slate-500 text-sm">No completed matches yet.</div>
                                ) : summary ? (
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="bg-slate-900 rounded-lg p-3">
                                            <div className="text-slate-400 text-xs mb-1">Matches</div>
                                            <div className="text-2xl font-bold text-slate-100">{summary.matchCount}</div>
                                        </div>
                                        <div className="bg-slate-900 rounded-lg p-3">
                                            <div className="text-slate-400 text-xs mb-1">Avg Possession</div>
                                            <div className="text-2xl font-bold text-slate-100">{summary.avgPossession === null ? 'Not measured' : `${summary.avgPossession}%`}</div>
                                        </div>
                                        <div className="bg-slate-900 rounded-lg p-3">
                                            <div className="text-slate-400 text-xs mb-1">Experimental shot quality For / Against</div>
                                            <div className="text-lg font-bold">
                                                <span className="text-emerald-400">{summary.avgMyTeamXg.toFixed(2)}</span>
                                                <span className="text-slate-500 mx-1">/</span>
                                                <span className="text-red-400">{summary.avgEnemyXg.toFixed(2)}</span>
                                            </div>
                                        </div>
                                        <div className="bg-slate-900 rounded-lg p-3">
                                            <div className="text-slate-400 text-xs mb-1">Experimental shot quality Diff</div>
                                            <div className={`text-lg font-bold ${summary.avgXgDiff >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                {summary.avgXgDiff >= 0 ? '+' : ''}{summary.avgXgDiff.toFixed(2)}
                                            </div>
                                        </div>
                                        <div className="bg-slate-900 rounded-lg p-3">
                                            <div className="text-slate-400 text-xs mb-1">Sprints For / Against</div>
                                            {summary.avgMyTeamSprints == null || summary.avgEnemySprints == null ? (
                                                <div className="text-lg font-bold text-slate-400">Unavailable</div>
                                            ) : (
                                            <div className="text-lg font-bold">
                                                <span className="text-emerald-400">{summary.avgMyTeamSprints.toFixed(0)}</span>
                                                <span className="text-slate-500 mx-1">/</span>
                                                <span className="text-red-400">{summary.avgEnemySprints.toFixed(0)}</span>
                                            </div>
                                            )}
                                        </div>
                                        <div className="bg-slate-900 rounded-lg p-3">
                                            <div className="text-slate-400 text-xs mb-1">Top Formation</div>
                                            <div className="text-lg font-bold text-slate-100">{summary.mostUsedFormation}</div>
                                        </div>
                                    </div>
                                ) : null}
                            </section>

                            {/* Last Match Comparison */}
                            {comparison && (
                                <section>
                                    <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Last Match vs Previous</h4>
                                    <div className="bg-slate-900 rounded-lg p-4">
                                        <div className="flex items-center justify-between mb-3">
                                            <div className="text-sm text-slate-300">
                                                <span className="font-semibold text-emerald-400">{comparison.latestMatchName}</span>
                                                <span className="text-slate-600 mx-2">vs</span>
                                                <span className="text-slate-400">{comparison.previousMatchName}</span>
                                            </div>
                                        </div>
                                        <div className="flex flex-wrap gap-3 mb-3">
                                            <DeltaBadge label="Possession" value={comparison.possessionDelta} />
                                            <DeltaBadge label="Experimental shot quality" value={comparison.xgDiffDelta} />
                                            <DeltaBadge label="Sprints" value={comparison.myTeamSprintsDelta} />
                                        </div>
                                    </div>
                                </section>
                            )}

                            {/* Season Trends — possession timeline */}
                            {trends && trends.length > 0 && (
                                <section>
                                    <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Possession Trend</h4>
                                    <div className="bg-slate-900 rounded-lg p-4">
                                        <div className="flex items-end gap-1 h-20">
                                            {trends.slice(-12).map((t) => {
                                                const possession = t.summary?.possession;
                                                return (
                                                    <div
                                                        key={t.matchId}
                                                        className="flex-1 flex flex-col items-center gap-1 cursor-pointer group"
                                                        title={`${t.name}: ${possession == null ? 'Not measured' : `${possession}%`}`}
                                                        onClick={() => onSelectMatch?.(t.matchId)}
                                                    >
                                                        {possession == null ? (
                                                            <div className="text-xs text-slate-500">?</div>
                                                        ) : (
                                                            <>
                                                                <div className="w-full bg-emerald-500/80 rounded-t transition-all group-hover:bg-emerald-400" style={{ height: `${possession}%` }} />
                                                                <div className="w-full bg-red-500/80 rounded-b" style={{ height: `${100 - possession}%` }} />
                                                            </>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                        <div className="flex justify-between mt-2 text-xs text-slate-500">
                                            <span>{formatDate(trends[0]?.date ?? '')}</span>
                                            <span>{formatDate(trends[trends.length - 1]?.date ?? '')}</span>
                                        </div>
                                    </div>
                                </section>
                            )}

                            {/* Match list */}
                            {trends && trends.length > 0 && (
                                <section>
                                    <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">All Matches</h4>
                                    <div className="space-y-2">
                                        {trends.map((t) => (
                                            <div
                                                key={t.matchId}
                                                className="flex items-center justify-between bg-slate-900 rounded-lg px-3 py-2 cursor-pointer hover:bg-slate-700 transition"
                                                onClick={() => onSelectMatch?.(t.matchId)}
                                            >
                                                <div>
                                                    <div className="text-sm text-slate-200">{t.name}</div>
                                                    <div className="text-xs text-slate-500">{formatDate(t.date)}</div>
                                                </div>
                                                <div className="text-right">
                                                    <div className="text-sm font-mono text-slate-200">{t.summary?.possession == null ? 'Not measured' : `${t.summary.possession}%`}</div>
                                                    <div className="text-xs text-slate-500 font-mono">
                                                        experimental shot quality {t.summary?.myTeamXg?.toFixed(1) ?? '?'} / {t.summary?.enemyXg?.toFixed(1) ?? '?'}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </section>
                            )}
                        </>
                    )}
                </div>
            </div>
        </ModalDialog>
    );
}
