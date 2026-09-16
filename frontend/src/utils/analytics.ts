import type {
    BackendEvent,
    FrameData,
    PassNetworkEdge,
    PlayerContribution,
    PlayerProfile,
    ShotMarker,
    ShotSummary,
    SpeedData,
} from '../types';

// Standard pitch dimensions in meters
const PITCH_LENGTH_M = 105;
const PITCH_WIDTH_M = 68;

/**
 * Compute a heat map density grid from all frames for a given team.
 * Returns a 2D array [cols][rows] with values normalized 0–1.
 */
export function computeHeatmap(
    frames: FrameData[],
    team: 'my_team' | 'enemy',
    gridCols = 20,
    gridRows = 13
): number[][] {
    const grid: number[][] = Array.from({ length: gridCols }, () => Array(gridRows).fill(0));
    let maxCount = 0;

    for (const frame of frames) {
        const players = team === 'my_team' ? frame.My_Team : frame.Enemies;
        for (const p of players) {
            if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) continue;
            const col = Math.max(0, Math.min(Math.floor((p.x / 100) * gridCols), gridCols - 1));
            const row = Math.max(0, Math.min(Math.floor((p.y / 100) * gridRows), gridRows - 1));
            grid[col][row]++;
            if (grid[col][row] > maxCount) maxCount = grid[col][row];
        }
    }

    // Normalize to 0–1
    if (maxCount > 0) {
        for (let c = 0; c < gridCols; c++) {
            for (let r = 0; r < gridRows; r++) {
                grid[c][r] /= maxCount;
            }
        }
    }

    return grid;
}

export function heatmapAvailability(identityContinuous: boolean) {
    return physicalTotalsAvailability(identityContinuous);
}

export function speedAvailability(identityContinuous: boolean) {
    return physicalTotalsAvailability(identityContinuous);
}

export function playerPhysicalTotalsAvailability(identityContinuous: boolean) {
    return physicalTotalsAvailability(identityContinuous);
}

function physicalTotalsAvailability(identityContinuous: boolean) {
    return {
        wholeMatch: identityContinuous,
        intervalLimited: !identityContinuous,
        withheld: !identityContinuous,
    };
}

/**
 * Compute speed (km/h) for each player between consecutive frames.
 * Returns a Map of trackId → SpeedData[] indexed by frame.
 */
export function computeSpeedsForFrame(
    frames: FrameData[],
    frameIdx: number
): Map<number, SpeedData> {
    const result = new Map<number, SpeedData>();
    if (frameIdx <= 0 || frameIdx >= frames.length) return result;

    const prev = frames[frameIdx - 1];
    const curr = frames[frameIdx];
    const dt = curr.Timestamp - prev.Timestamp;
    if (dt <= 0) return result;

    // Match My_Team players by ID
    for (const cp of curr.My_Team) {
        const pp = prev.My_Team.find(p => p.id === cp.id);
        if (!pp) continue;
        const dx = (cp.x - pp.x) / 100 * PITCH_LENGTH_M;
        const dy = (cp.y - pp.y) / 100 * PITCH_WIDTH_M;
        const distM = Math.sqrt(dx * dx + dy * dy);
        const speedKmh = (distM / dt) * 3.6;
        result.set(cp.id, { speed: Math.round(speedKmh * 10) / 10, isSprinting: speedKmh > 25 });
    }

    // Match Enemies by ID
    for (const ce of curr.Enemies) {
        const pe = prev.Enemies.find(p => p.enemy_id === ce.enemy_id);
        if (!pe) continue;
        const dx = (ce.x - pe.x) / 100 * PITCH_LENGTH_M;
        const dy = (ce.y - pe.y) / 100 * PITCH_WIDTH_M;
        const distM = Math.sqrt(dx * dx + dy * dy);
        const speedKmh = (distM / dt) * 3.6;
        result.set(-ce.enemy_id, { speed: Math.round(speedKmh * 10) / 10, isSprinting: speedKmh > 25 });
    }

    return result;
}



export function buildPassingNetwork(events: BackendEvent[]): PassNetworkEdge[] {
    const edgeCounts = new Map<string, PassNetworkEdge>();

    for (const event of events) {
        if (event.type !== 'pass' || event.team !== 'my_team' || event.fromTrackId == null || event.toTrackId == null) {
            continue;
        }

        const key = `${event.fromTrackId}:${event.toTrackId}`;
        const existing = edgeCounts.get(key);
        if (existing) {
            existing.count += 1;
            continue;
        }

        edgeCounts.set(key, {
            fromId: event.fromTrackId,
            toId: event.toTrackId,
            count: 1,
        });
    }

    return Array.from(edgeCounts.values()).sort((left, right) => {
        if (right.count !== left.count) return right.count - left.count;
        if (left.fromId !== right.fromId) return left.fromId - right.fromId;
        return left.toId - right.toId;
    });
}

export function resolvePassingNetworkEdgesForFrame(
    frame: FrameData | null,
    edges: PassNetworkEdge[]
): Array<PassNetworkEdge & { from: { x: number; y: number }; to: { x: number; y: number } }> {
    if (!frame) return [];

    const playerPositions = new Map(frame.My_Team.map((player) => [player.id, { x: player.x, y: player.y }]));
    return edges.flatMap((edge) => {
        const from = playerPositions.get(edge.fromId);
        const to = playerPositions.get(edge.toId);
        if (!from || !to) return [];
        return [{ ...edge, from, to }];
    });
}

export function summarizeShots(markers: ShotMarker[]): ShotSummary {
    return markers.reduce<ShotSummary>((summary, marker) => {
        if (marker.team === 'my_team') {
            summary.myTeamShots += 1;
            summary.myTeamBoxShots += Number(marker.inBox);
            summary.myTeamXg = Math.round((summary.myTeamXg + (marker.xg ?? 0)) * 100) / 100;
        } else {
            summary.enemyShots += 1;
            summary.enemyBoxShots += Number(marker.inBox);
            summary.enemyXg = Math.round((summary.enemyXg + (marker.xg ?? 0)) * 100) / 100;
        }
        return summary;
    }, {
        myTeamShots: 0,
        enemyShots: 0,
        myTeamBoxShots: 0,
        enemyBoxShots: 0,
        myTeamXg: 0,
        enemyXg: 0,
    });
}

const CREATOR_EVENT_TYPES = new Set(['pass', 'cross', 'through_ball']);
const CREATION_FRAME_WINDOW = 12;

function roundTwo(value: number): number {
    return Math.round(value * 100) / 100;
}

function formatCount(count: number, singular: string, plural = `${singular}s`): string {
    return `${count} ${count === 1 ? singular : plural}`;
}

function selectProfileLabel(player: PlayerContribution): string {
    if (player.xgCreated >= 0.15 || player.throughBalls > 0) return 'Primary Creator';
    if (player.xgTaken >= 0.15 || player.shots > 0) return 'Shot Threat';
    if (player.ballWins > 0) return 'Ball Winner';
    if (player.crosses > 0) return 'Wide Threat';
    if (player.passes >= 3) return 'Connector';
    return 'Support Option';
}

function buildSummaryLine(player: PlayerContribution, profileLabel: string): string {
    if (profileLabel === 'Primary Creator') {
        return `${formatCount(player.throughBalls, 'through ball')}, ${player.xgCreated.toFixed(2)} xG created`;
    }
    if (profileLabel === 'Shot Threat') {
        return `${formatCount(player.shots, 'shot')}, ${player.xgTaken.toFixed(2)} xG taken`;
    }
    if (profileLabel === 'Ball Winner') {
        return `${formatCount(player.ballWins, 'ball win')}, ${formatCount(player.interceptions, 'interception')}`;
    }
    if (profileLabel === 'Wide Threat') {
        return `${formatCount(player.crosses, 'cross')}, ${player.involvements} involvements`;
    }
    return `${formatCount(player.passes, 'pass')}, ${player.involvements} involvements`;
}

export function buildPlayerContributions(events: BackendEvent[], shotMarkers: ShotMarker[] = []): PlayerContribution[] {
    const crossKeys = new Set(
        events
            .filter((event) => event.type === 'cross' && event.team && event.fromTrackId != null)
            .map((event) => `${event.frameId}:${event.team}:${event.fromTrackId}:${event.toTrackId ?? 'none'}`)
    );
    const contributions = new Map<string, PlayerContribution>();

    function ensureContribution(team: 'my_team' | 'enemy', playerId: number): PlayerContribution {
        const key = `${team}:${playerId}`;
        const existing = contributions.get(key);
        if (existing) return existing;

        const created: PlayerContribution = {
            team,
            playerId,
            passes: 0,
            crosses: 0,
            throughBalls: 0,
            shots: 0,
            tacklesWon: 0,
            recoveries: 0,
            interceptions: 0,
            ballWins: 0,
            involvements: 0,
            xgCreated: 0,
            xgTaken: 0,
            impactScore: 0,
        };
        contributions.set(key, created);
        return created;
    }

    for (const event of events) {
        if (event.team !== 'my_team' && event.team !== 'enemy') continue;

        if (event.type === 'pass' && event.fromTrackId != null) {
            const crossKey = `${event.frameId}:${event.team}:${event.fromTrackId}:${event.toTrackId ?? 'none'}`;
            if (crossKeys.has(crossKey)) continue;
            ensureContribution(event.team, event.fromTrackId).passes += 1;
        } else if (event.type === 'cross' && event.fromTrackId != null) {
            ensureContribution(event.team, event.fromTrackId).crosses += 1;
        } else if (event.type === 'through_ball' && event.fromTrackId != null) {
            ensureContribution(event.team, event.fromTrackId).throughBalls += 1;
        } else if (event.type === 'shot' && event.fromTrackId != null) {
            ensureContribution(event.team, event.fromTrackId).shots += 1;
        } else if (event.type === 'tackle' && event.toTrackId != null) {
            ensureContribution(event.team, event.toTrackId).tacklesWon += 1;
        } else if (event.type === 'recovery' && event.toTrackId != null) {
            ensureContribution(event.team, event.toTrackId).recoveries += 1;
        } else if (event.type === 'interception' && event.toTrackId != null) {
            ensureContribution(event.team, event.toTrackId).interceptions += 1;
        }
    }

    for (const marker of shotMarkers) {
        const contribution = ensureContribution(marker.team, marker.playerId);
        contribution.xgTaken = roundTwo(contribution.xgTaken + marker.xg);
    }

    const creatorEvents = events
        .filter((event) =>
            (event.team === 'my_team' || event.team === 'enemy') &&
            event.fromTrackId != null &&
            CREATOR_EVENT_TYPES.has(event.type)
        )
        .sort((left, right) => {
            if (left.frameId !== right.frameId) return left.frameId - right.frameId;
            return left.timestamp - right.timestamp;
        });

    for (const marker of shotMarkers) {
        const creator = [...creatorEvents]
            .reverse()
            .find((event) => {
                if (event.team !== marker.team) return false;
                if (event.frameId > marker.frameId) return false;
                if ((marker.frameId - event.frameId) > CREATION_FRAME_WINDOW) return false;
                if (event.frameId === marker.frameId && event.timestamp > marker.timestamp) return false;
                return true;
            });

        if (!creator || creator.fromTrackId == null || creator.fromTrackId === marker.playerId) continue;
        const contribution = ensureContribution(marker.team, creator.fromTrackId);
        contribution.xgCreated = roundTwo(contribution.xgCreated + marker.xg);
    }

    return Array.from(contributions.values())
        .map((entry) => {
            const ballWins = entry.tacklesWon + entry.recoveries + entry.interceptions;
            const involvements =
                entry.passes +
                entry.crosses +
                entry.throughBalls +
                entry.shots +
                entry.tacklesWon +
                entry.recoveries +
                entry.interceptions;

            return {
                ...entry,
                ballWins,
                involvements,
                xgCreated: roundTwo(entry.xgCreated),
                xgTaken: roundTwo(entry.xgTaken),
                impactScore:
                    entry.passes +
                    (entry.crosses * 2) +
                    (entry.throughBalls * 3) +
                    (entry.shots * 3) +
                    (entry.tacklesWon * 2) +
                    (entry.recoveries * 2) +
                    (entry.interceptions * 2) +
                    Math.round((entry.xgTaken + entry.xgCreated) * 10),
            };
        })
        .filter((entry) => entry.impactScore > 0)
        .sort((left, right) => {
            if (right.impactScore !== left.impactScore) return right.impactScore - left.impactScore;
            const rightXg = right.xgTaken + right.xgCreated;
            const leftXg = left.xgTaken + left.xgCreated;
            if (rightXg !== leftXg) return rightXg - leftXg;
            if (right.throughBalls !== left.throughBalls) return right.throughBalls - left.throughBalls;
            if (right.shots !== left.shots) return right.shots - left.shots;
            if (right.crosses !== left.crosses) return right.crosses - left.crosses;
            if (right.passes !== left.passes) return right.passes - left.passes;
            if (left.team !== right.team) return left.team.localeCompare(right.team);
            return left.playerId - right.playerId;
        });
}

export function buildPlayerProfiles(
    frames: FrameData[],
    events: BackendEvent[],
    shotMarkers: ShotMarker[] = [],
    identityContinuous = false,
): PlayerProfile[] {
    const contributions = buildPlayerContributions(events, shotMarkers);
    type PlayerMovementMetric = {
        sumX: number;
        sumY: number;
        count: number;
        totalDistance: number;
        topSpeed: number;
        lastX?: number;
        lastY?: number;
        lastTimestamp?: number;
    };

    const metrics = new Map<string, PlayerMovementMetric>();

    function ensureMetric(key: string): PlayerMovementMetric {
        const existing = metrics.get(key);
        if (existing) return existing;
        const created: PlayerMovementMetric = { sumX: 0, sumY: 0, count: 0, totalDistance: 0, topSpeed: 0 };
        metrics.set(key, created);
        return created;
    }

    for (const frame of frames) {
        for (const player of frame.My_Team) {
            const key = `my_team:${player.id}`;
            const metric = ensureMetric(key);
            metric.sumX += player.x;
            metric.sumY += player.y;
            metric.count += 1;
            if (identityContinuous && metric.lastX !== undefined && metric.lastY !== undefined && metric.lastTimestamp !== undefined) {
                const dt = frame.Timestamp - metric.lastTimestamp;
                if (dt > 0) {
                    const dx = (player.x - metric.lastX) / 100 * PITCH_LENGTH_M;
                    const dy = (player.y - metric.lastY) / 100 * PITCH_WIDTH_M;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    metric.totalDistance += distance;
                    metric.topSpeed = Math.max(metric.topSpeed, (distance / dt) * 3.6);
                }
            }
            metric.lastX = player.x;
            metric.lastY = player.y;
            metric.lastTimestamp = frame.Timestamp;
        }

        for (const player of frame.Enemies) {
            const key = `enemy:${player.enemy_id}`;
            const metric = ensureMetric(key);
            metric.sumX += player.x;
            metric.sumY += player.y;
            metric.count += 1;
            if (identityContinuous && metric.lastX !== undefined && metric.lastY !== undefined && metric.lastTimestamp !== undefined) {
                const dt = frame.Timestamp - metric.lastTimestamp;
                if (dt > 0) {
                    const dx = (player.x - metric.lastX) / 100 * PITCH_LENGTH_M;
                    const dy = (player.y - metric.lastY) / 100 * PITCH_WIDTH_M;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    metric.totalDistance += distance;
                    metric.topSpeed = Math.max(metric.topSpeed, (distance / dt) * 3.6);
                }
            }
            metric.lastX = player.x;
            metric.lastY = player.y;
            metric.lastTimestamp = frame.Timestamp;
        }
    }

    return contributions
        .map((contribution) => {
            const metric = metrics.get(`${contribution.team}:${contribution.playerId}`);
            const profileLabel = selectProfileLabel(contribution);
            return {
                ...contribution,
                avgX: metric && metric.count > 0 ? Math.round((metric.sumX / metric.count) * 10) / 10 : 50,
                avgY: metric && metric.count > 0 ? Math.round((metric.sumY / metric.count) * 10) / 10 : 50,
                totalDistance: identityContinuous ? Math.round((metric?.totalDistance ?? 0) * 10) / 10 : 0,
                topSpeed: identityContinuous ? Math.round((metric?.topSpeed ?? 0) * 10) / 10 : 0,
                physicalTotalsWithheld: !identityContinuous,
                profileLabel,
                summaryLine: buildSummaryLine(contribution, profileLabel),
            };
        })
        .sort((left, right) => {
            if (right.impactScore !== left.impactScore) return right.impactScore - left.impactScore;
            const rightXg = right.xgTaken + right.xgCreated;
            const leftXg = left.xgTaken + left.xgCreated;
            if (rightXg !== leftXg) return rightXg - leftXg;
            if (right.totalDistance !== left.totalDistance) return right.totalDistance - left.totalDistance;
            if (right.topSpeed !== left.topSpeed) return right.topSpeed - left.topSpeed;
            if (left.team !== right.team) return left.team.localeCompare(right.team);
            return left.playerId - right.playerId;
        });
}
