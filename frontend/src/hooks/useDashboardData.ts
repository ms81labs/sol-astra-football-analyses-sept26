import { useState, useEffect } from 'react';
import { fetchDashboardData } from '../utils/api';
import type { DashboardComparison, DashboardSummary, OpponentRollup, PlayerTrendSnapshot, SeasonTrendPoint } from '../types';

export function useDashboardData() {
    const [trends, setTrends] = useState<SeasonTrendPoint[]>([]);
    const [summary, setSummary] = useState<DashboardSummary | null>(null);
    const [comparison, setComparison] = useState<DashboardComparison | null>(null);
    const [opponentRollups, setOpponentRollups] = useState<OpponentRollup[]>([]);
    const [playerTrendSnapshots, setPlayerTrendSnapshots] = useState<PlayerTrendSnapshot[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    useEffect(() => {
        let mounted = true;

        async function loadData() {
            try {
                setIsLoading(true);
                const data = await fetchDashboardData();
                if (mounted) {
                    setSummary(data.summary);
                    setComparison(data.comparison);
                    setOpponentRollups(data.opponentRollups);
                    setPlayerTrendSnapshots(data.playerTrendSnapshots ?? []);
                    setTrends(data.trends);
                    setError(null);
                }
            } catch (err) {
                if (mounted) {
                    setError(err instanceof Error ? err : new Error('Unknown error loading dashboard data'));
                }
            } finally {
                if (mounted) {
                    setIsLoading(false);
                }
            }
        }

        loadData();

        return () => {
            mounted = false;
        };
    }, []);

    return { summary, comparison, opponentRollups, playerTrendSnapshots, trends, isLoading, error, setTrends };
}
