import { describe, expect, it } from 'vitest';

import {
  computeHeatmap,
  heatmapAvailability,
  speedAvailability,
  playerPhysicalTotalsAvailability,
  physicalMetricAvailability,
  buildPassingNetwork,
  buildPlayerProfiles,
  buildPlayerContributions,
  summarizeShots,
  resolvePassingNetworkEdgesForFrame,
} from './analytics';

describe('buildPassingNetwork', () => {
  it('aggregates only pass events into weighted network edges', () => {
    const edges = buildPassingNetwork([
      { type: 'pass', frameId: 1, timestamp: 0.2, team: 'my_team', fromTrackId: 7, toTrackId: 11, description: 'Pass' },
      { type: 'pass', frameId: 3, timestamp: 0.6, team: 'my_team', fromTrackId: 7, toTrackId: 11, description: 'Pass' },
      { type: 'pass', frameId: 5, timestamp: 1.0, team: 'my_team', fromTrackId: 11, toTrackId: 19, description: 'Pass' },
      { type: 'turnover', frameId: 6, timestamp: 1.2, team: 'enemy', fromTrackId: 11, toTrackId: 18, description: 'Turnover' },
    ]);

    expect(edges).toEqual([
      { fromId: 7, toId: 11, count: 2 },
      { fromId: 11, toId: 19, count: 1 },
    ]);
  });

  it('excludes enemy passes from the home-team network', () => {
    const homePass = { type: 'pass', frameId: 1, timestamp: 0.2, team: 'my_team', fromTrackId: 7, toTrackId: 11, description: 'Pass' };
    const enemyPass = { type: 'pass', frameId: 2, timestamp: 0.4, team: 'enemy', fromTrackId: 7, toTrackId: 11, description: 'Pass' };

    expect(buildPassingNetwork([homePass, enemyPass])).toEqual([
      { fromId: 7, toId: 11, count: 1 },
    ]);
  });

  it('returns no network for enemy-only passes', () => {
    const enemyPass = { type: 'pass', frameId: 2, timestamp: 0.4, team: 'enemy', fromTrackId: 7, toTrackId: 11, description: 'Pass' };

    expect(buildPassingNetwork([enemyPass])).toEqual([]);
  });
});

describe('resolvePassingNetworkEdgesForFrame', () => {
  it('keeps only edges whose players are present in the current frame', () => {
    const visibleEdges = resolvePassingNetworkEdgesForFrame(
      {
        Frame_ID: 10,
        Timestamp: 2.0,
        Ball: { x: 50, y: 50, conf: 0.9 },
        My_Team: [
          { id: 7, x: 20, y: 30, conf: 0.9 },
          { id: 11, x: 42, y: 35, conf: 0.9 },
        ],
        Enemies: [],
      },
      [
        { fromId: 7, toId: 11, count: 3 },
        { fromId: 11, toId: 19, count: 1 },
      ],
    );

    expect(visibleEdges).toEqual([
      {
        fromId: 7,
        toId: 11,
        count: 3,
        from: { x: 20, y: 30 },
        to: { x: 42, y: 35 },
      },
    ]);
  });
});

describe('summarizeShots xg totals', () => {
  it('does not invent experimental shot quality when there are no shots', () => {
    expect(summarizeShots([])).toEqual({
      myTeamShots: 0,
      enemyShots: 0,
      myTeamBoxShots: 0,
      enemyBoxShots: 0,
      myTeamXg: null,
      enemyXg: null,
    });
  });

  it('sums shot quality values by team when xg is available', () => {
    expect(
      summarizeShots([
        { frameId: 2, timestamp: 0.4, team: 'my_team', playerId: 9, x: 91, y: 50, inBox: true, xg: 0.42 },
        { frameId: 8, timestamp: 1.6, team: 'enemy', playerId: 4, x: 13, y: 48, inBox: true, xg: 0.11 },
      ]),
    ).toEqual({
      myTeamShots: 1,
      enemyShots: 1,
      myTeamBoxShots: 1,
      enemyBoxShots: 1,
      myTeamXg: 0.42,
      enemyXg: 0.11,
    });
  });
});

describe('buildPlayerContributions', () => {
  it('aggregates event output into ranked player contributions', () => {
    const contributions = buildPlayerContributions([
      { type: 'pass', frameId: 1, timestamp: 0.2, team: 'my_team', fromTrackId: 7, toTrackId: 11, description: 'Pass' },
      { type: 'pass', frameId: 2, timestamp: 0.4, team: 'my_team', fromTrackId: 11, toTrackId: 9, description: 'Pass' },
      { type: 'cross', frameId: 2, timestamp: 0.4, team: 'my_team', fromTrackId: 11, toTrackId: 9, description: 'Cross' },
      { type: 'shot', frameId: 3, timestamp: 0.6, team: 'my_team', fromTrackId: 9, description: 'Shot' },
      { type: 'tackle', frameId: 4, timestamp: 0.8, team: 'enemy', fromTrackId: 7, toTrackId: 18, description: 'Tackle' },
      { type: 'recovery', frameId: 5, timestamp: 1.0, team: 'enemy', toTrackId: 18, description: 'Recovery' },
    ]);

    expect(contributions).toEqual([
      expect.objectContaining({
        team: 'enemy',
        playerId: 18,
        passes: 0,
        crosses: 0,
        throughBalls: 0,
        shots: 0,
        tacklesWon: 1,
        recoveries: 1,
        interceptions: 0,
        ballWins: 2,
        involvements: 2,
        impactScore: 4,
      }),
      expect.objectContaining({
        team: 'my_team',
        playerId: 9,
        shots: 1,
        xgTaken: 0,
        xgCreated: 0,
        impactScore: 3,
      }),
      expect.objectContaining({
        team: 'my_team',
        playerId: 11,
        crosses: 1,
        impactScore: 2,
      }),
      expect.objectContaining({
        team: 'my_team',
        playerId: 7,
        passes: 1,
        impactScore: 1,
      }),
    ]);
  });
});

describe('buildPlayerProfiles', () => {
  it('combines event impact with movement metrics into ranked player profiles', () => {
    const profiles = buildPlayerProfiles(
      [
        {
          Frame_ID: 0,
          Timestamp: 0,
          Ball: { x: 50, y: 50, conf: 0.9 },
          My_Team: [{ id: 7, x: 20, y: 30, conf: 0.9 }],
          Enemies: [{ enemy_id: 18, x: 70, y: 40, conf: 0.9 }],
        },
        {
          Frame_ID: 1,
          Timestamp: 0.5,
          Ball: { x: 55, y: 50, conf: 0.9 },
          My_Team: [{ id: 7, x: 25, y: 30, conf: 0.9 }],
          Enemies: [{ enemy_id: 18, x: 68, y: 40, conf: 0.9 }],
        },
        {
          Frame_ID: 2,
          Timestamp: 1.0,
          Ball: { x: 58, y: 52, conf: 0.9 },
          My_Team: [{ id: 7, x: 30, y: 32, conf: 0.9 }],
          Enemies: [{ enemy_id: 18, x: 66, y: 42, conf: 0.9 }],
        },
      ],
      [
        { type: 'pass', frameId: 1, timestamp: 0.5, team: 'my_team', fromTrackId: 7, toTrackId: 11, description: 'Pass' },
        { type: 'shot', frameId: 2, timestamp: 1.0, team: 'my_team', fromTrackId: 7, description: 'Shot' },
        { type: 'tackle', frameId: 2, timestamp: 1.0, team: 'enemy', fromTrackId: 7, toTrackId: 18, description: 'Tackle' },
        { type: 'recovery', frameId: 2, timestamp: 1.0, team: 'enemy', toTrackId: 18, description: 'Recovery' },
      ],
      [],
      true,
    );

    expect(profiles).toEqual([
      expect.objectContaining({
        team: 'my_team',
        playerId: 7,
        passes: 1,
        crosses: 0,
        throughBalls: 0,
        shots: 1,
        tacklesWon: 0,
        recoveries: 0,
        interceptions: 0,
        ballWins: 0,
        xgTaken: 0,
        xgCreated: 0,
        impactScore: 4,
        avgX: 25,
        avgY: 30.7,
        totalDistance: 10.7,
        topSpeed: 39,
        profileLabel: 'Shot Threat',
        summaryLine: '1 shot, 0.00 experimental shot quality',
      }),
      expect.objectContaining({
        team: 'enemy',
        playerId: 18,
        passes: 0,
        crosses: 0,
        throughBalls: 0,
        shots: 0,
        tacklesWon: 1,
        recoveries: 1,
        interceptions: 0,
        ballWins: 2,
        xgTaken: 0,
        xgCreated: 0,
        impactScore: 4,
        avgX: 68,
        avgY: 40.7,
        totalDistance: 4.6,
        topSpeed: 18,
        profileLabel: 'Ball Winner',
        summaryLine: '2 ball wins, 0 interceptions',
      }),
    ]);
  });

  it('builds richer player profiles from event output and shot quality', () => {
    const profiles = buildPlayerProfiles(
      [
        {
          Frame_ID: 0,
          Timestamp: 0,
          Ball: { x: 48, y: 50, conf: 0.9 },
          My_Team: [
            { id: 7, x: 30, y: 40, conf: 0.9 },
            { id: 9, x: 82, y: 49, conf: 0.9 },
          ],
          Enemies: [{ enemy_id: 18, x: 58, y: 44, conf: 0.9 }],
        },
        {
          Frame_ID: 1,
          Timestamp: 0.5,
          Ball: { x: 82, y: 49, conf: 0.9 },
          My_Team: [
            { id: 7, x: 33, y: 40, conf: 0.9 },
            { id: 9, x: 84, y: 49, conf: 0.9 },
          ],
          Enemies: [{ enemy_id: 18, x: 56, y: 44, conf: 0.9 }],
        },
      ],
      [
        { type: 'through_ball', frameId: 1, timestamp: 0.5, team: 'my_team', fromTrackId: 7, toTrackId: 9, description: 'Through ball played' },
        { type: 'shot', frameId: 1, timestamp: 0.5, team: 'my_team', fromTrackId: 9, description: 'Shot attempted' },
        { type: 'interception', frameId: 1, timestamp: 0.5, team: 'enemy', toTrackId: 18, description: 'Interception won' },
      ],
      [
        { frameId: 1, timestamp: 0.5, team: 'my_team', playerId: 9, x: 84, y: 49, inBox: true, xg: 0.38 },
      ],
      true,
    );

    expect(profiles).toEqual([
      expect.objectContaining({
        team: 'my_team',
        playerId: 7,
        throughBalls: 1,
        interceptions: 0,
        ballWins: 0,
        xgCreated: 0.38,
        xgTaken: 0,
        profileLabel: 'Primary Creator',
        summaryLine: '1 through ball, 0.38 experimental shot quality created',
      }),
      expect.objectContaining({
        team: 'my_team',
        playerId: 9,
        shots: 1,
        xgTaken: 0.38,
        profileLabel: 'Shot Threat',
        summaryLine: '1 shot, 0.38 experimental shot quality',
      }),
      expect.objectContaining({
        team: 'enemy',
        playerId: 18,
        interceptions: 1,
        ballWins: 1,
        profileLabel: 'Ball Winner',
        summaryLine: '1 ball win, 1 interception',
      }),
    ]);
  });

  it('prefers xg and role signals when sorting tied impact profiles', () => {
    const profiles = buildPlayerProfiles(
      [],
      [
        { type: 'pass', frameId: 1, timestamp: 0.2, team: 'my_team', fromTrackId: 7, toTrackId: 11, description: 'Pass' },
        { type: 'shot', frameId: 2, timestamp: 0.4, team: 'my_team', fromTrackId: 11, description: 'Shot' },
      ],
      [
        { frameId: 2, timestamp: 0.4, team: 'my_team', playerId: 11, x: 90, y: 50, inBox: true, xg: 0.42 },
      ],
      true,
    );

    expect(profiles[0]).toEqual(
      expect.objectContaining({
        playerId: 11,
        profileLabel: 'Shot Threat',
      }),
    );
  });

  it('withholds player-profile physical totals until identity continuity is validated', () => {
    const frames = [
      {
        Frame_ID: 0,
        Timestamp: 0,
        Ball: { x: 50, y: 50, conf: 0.9 },
        My_Team: [{ id: 7, x: 20, y: 30, conf: 0.9 }],
        Enemies: [],
      },
      {
        Frame_ID: 1,
        Timestamp: 0.5,
        Ball: { x: 55, y: 50, conf: 0.9 },
        My_Team: [{ id: 7, x: 25, y: 30, conf: 0.9 }],
        Enemies: [],
      },
    ];
    const events = [
      { type: 'pass', frameId: 1, timestamp: 0.5, team: 'my_team', fromTrackId: 7, toTrackId: 11, description: 'Pass' },
    ];

    const withheld = buildPlayerProfiles(frames, events);
    expect(withheld).toEqual([
      expect.objectContaining({
        playerId: 7,
        totalDistance: null,
        topSpeed: null,
        physicalTotalsWithheld: true,
      }),
    ]);
    expect(withheld[0].totalDistance).toBeNull();
    expect(withheld[0].topSpeed).toBeNull();

    const continuous = buildPlayerProfiles(frames, events, [], true);
    expect(continuous[0].physicalTotalsWithheld).toBe(false);
    expect(continuous[0].totalDistance).toBeGreaterThan(0);
    expect(continuous[0].topSpeed).toBeGreaterThan(0);
  });

  it('does not invent a midfield average when a player has no position samples', () => {
    const profiles = buildPlayerProfiles(
      [],
      [{ type: 'pass', frameId: 1, timestamp: 0.5, team: 'my_team', fromTrackId: 7, toTrackId: 11, description: 'Pass' }],
    );
    expect(profiles).toEqual([
      expect.objectContaining({
        playerId: 7,
        avgX: null,
        avgY: null,
        totalDistance: null,
        topSpeed: null,
      }),
    ]);
  });
});


describe('computeHeatmap boundaries', () => {
  it('clamps finite off-pitch samples and ignores non-finite positions', () => {
    const grid = computeHeatmap([{
      Frame_ID: 100, Timestamp: 0, Ball: null, Enemies: [],
      My_Team: [-0.1, 100.1, NaN, Infinity].map((x, id) => ({ id, x, y: x, conf: 1 })),
    }], 'my_team', 2, 2);
    expect(grid).toEqual([[1, 0], [0, 1]]);
  });

  it('withholds a whole-match heatmap until identity continuity is validated', () => {
    const withheld = heatmapAvailability(false);
    expect(withheld.wholeMatch).toBe(false);
    expect(withheld.intervalLimited).toBe(true);
    expect(withheld.withheld).toBe(true);
    const continuous = heatmapAvailability(true);
    expect(continuous.wholeMatch).toBe(true);
    expect(continuous.withheld).toBe(false);
  });

  it('withholds derived speeds until identity continuity is validated', () => {
    const withheld = speedAvailability(false);
    expect(withheld.withheld).toBe(true);
    expect(withheld.intervalLimited).toBe(true);
    const continuous = speedAvailability(true);
    expect(continuous.withheld).toBe(false);
  });

  it('withholds player physical totals until identity continuity is validated', () => {
    const withheld = playerPhysicalTotalsAvailability(false);
    expect(withheld.withheld).toBe(true);
    expect(withheld.wholeMatch).toBe(false);
    const continuous = playerPhysicalTotalsAvailability(true);
    expect(continuous.withheld).toBe(false);
    expect(continuous.wholeMatch).toBe(true);
  });

  it('emits withheld availability for every physical family metric until identity is continuous', () => {
    const withheld = physicalMetricAvailability(false);
    expect(withheld.map((item) => item.metric)).toEqual([
      'my_team_distance_m',
      'enemy_distance_m',
      'my_team_top_speed_kmh',
      'enemy_top_speed_kmh',
      'my_team_sprints',
      'enemy_sprints',
    ]);
    expect(withheld.every((item) => item.availability === 'withheld')).toBe(true);
    expect(withheld.every((item) => item.reasonCodes.includes('IDENTITY_DISCONTINUITY'))).toBe(true);
    expect(withheld.every((item) => item.value === null)).toBe(true);
    const continuous = physicalMetricAvailability(true);
    expect(continuous.every((item) => item.availability === 'available')).toBe(true);
    expect(continuous.every((item) => item.reasonCodes.length === 0)).toBe(true);
  });
});
