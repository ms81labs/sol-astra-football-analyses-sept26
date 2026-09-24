// ===== Data Types =====

export interface PlayerData {
    id: number;
    x: number;
    y: number;
    conf: number;
}

export interface EnemyData {
    enemy_id: number;
    x: number;
    y: number;
    conf: number;
}

export interface BallData {
    x: number;
    y: number;
    conf: number;
}

export interface FrameData {
    Frame_ID: number;
    Timestamp: number;
    Ball: BallData | null;
    My_Team: PlayerData[];
    Enemies: EnemyData[];
    unassignedPlayers?: PlayerData[];
    possession?: BallOwnership | null;
}

export interface RawRow {
    Frame_ID: number;
    Timestamp: number;
    Entity_Type: string;
    Track_ID: number;
    X: number;
    Y: number;
    Conf: number;
}

// ===== Event Types =====

export type EventType = 'goal' | 'foul' | 'corner' | 'counter' | 'offside' | 'pass' | 'progressive_pass' | 'cross' | 'shot' | 'tackle' | 'recovery' | 'turnover' | 'through_ball' | 'interception' | 'carry' | 'box_entry' | 'final_third_entry' | 'zone_advancement' | 'custom';

export interface EventTag {
    frame: number;
    timestamp: number;
    label: string;
    type: EventType;
    reviewStatus?: 'unreviewed' | 'accepted' | 'rejected';
    rejectionReason?: string;
    heuristicName?: string;
    evidenceVersion?: string;
    intervalStart?: number;
    intervalEnd?: number;
}

// ===== LLM Types =====

export interface LlmOffsideResponse {
    offside: boolean;
    offside_x: number;
    explanation: string;
}

export interface LlmSpacingResponse {
    width: number;
    too_wide: boolean;
    explanation: string;
}

export interface LlmErrorResponse {
    error: string;
}

export type LlmResponse = LlmOffsideResponse | LlmSpacingResponse | LlmErrorResponse | null;

// ===== Analytics Types =====

export interface SpeedData {
    speed: number;       // km/h
    isSprinting: boolean; // > 25 km/h
}

export interface MatchStats {
    possession: number | null;  // null when no controlled frames exist
    ballSignalStatus: string;
    ballSignalMessage: string | null;
    myTeamDistance: number | null;
    enemyDistance: number | null;
    myTeamAvgPos: { x: number; y: number } | null;
    enemyAvgPos: { x: number; y: number } | null;
    myTeamTopSpeed: number | null;
    enemyTopSpeed: number | null;
    myTeamSprints: number | null;
    enemySprints: number | null;
    myTeamXg: number | null;
    enemyXg: number | null;
    myTeamDefensiveLineHeight: number | null;
    enemyDefensiveLineHeight: number | null;
    myTeamDefensiveTeamLength: number | null;
    enemyDefensiveTeamLength: number | null;
    myTeamPpda: number | null;
    enemyPpda: number | null;
    myTeamHighPressRegains: number | null;
    enemyHighPressRegains: number | null;
    myTeamCounterpressRecoverySeconds: number | null;
    enemyCounterpressRecoverySeconds: number | null;
    formation: string | null;         // e.g. "4-4-2"
    metricAvailability?: Array<{
        metric: string;
        definitionVersion: string;
        value: number | null;
        availability: string;
        reasonCodes: string[];
        unit?: string | null;
        publishedLabel?: string | null;
        eligibleSeconds?: number;
        requestedSeconds?: number;
        evidenceIds?: string[];
        reviewStatus?: string;
        denominator?: string | null;
        teamScope?: 'my_team' | 'enemy' | null;
        deprecated?: boolean;
        pitchDimensions?: { lengthM: number; widthM: number } | null;
    }>;
}

export interface MatchBenchmarkSummary {
    matchId: string;
    jobId?: string | null;
    inputMode: string;
    matchStatus: string;
    jobStatus?: string | null;
    requiresTeamSelection: boolean;
    rawRowCount: number;
    frameCount: number;
    playerFrames: number;
    withBallFrames: number;
    withBallRatio: number;
    trackedPossessionFrames: number;
    trackedPossessionRatio: number;
    controlledPossessionFrames: number;
    controlledPossessionRatio: number;
    eventCount: number;
    eventTypes: Record<string, number>;
    eventFamilyCount: number;
    dominantEventShare: number;
    shotCount: number;
    ballSignalStatus?: string | null;
    ballTrackPathLength: number;
    ballTrackEdgeFrameShare: number;
    ballTrackShowsMeaningfulMotion: boolean;
    ballTrackViable: boolean;
    fiveMinuteTruthReady: boolean;
    fortyFiveMinuteTruthReady: boolean;
    truthGateReasons: string[];
    artifactPresence: Record<string, boolean>;
}

export interface FormationSegment {
    formation: string;
    startFrameId: number;
    endFrameId: number;
    startTimestamp: number;
    endTimestamp: number;
}

// ===== TacticalPitch Types =====

export interface BallOwnership {
    frameId: number;
    timestamp: number;
    team: 'my_team' | 'enemy' | 'contested' | 'dead_ball' | 'unassigned';
    trackId: number | null;
    distance?: number | null;
}

export interface TeamCluster {
    clusterId: number;
    rgbCentroid: number[];
    trackIds: number[];
}

export interface MatchRecord {
  generationId?: string | null;
  commandVersion?: number;
  includedCommandIds?: string[];
    id: string;
    name: string;
    inputMode: string;
    status: string;
    originalFilename: string;
    config?: UploadConfig;
    createdAt?: string;
    updatedAt?: string;
    requiresTeamSelection?: boolean;
    teamClusters?: TeamCluster[];
}

export interface ProcessingJob {
    id: string;
    matchId: string;
    status: string;
    progress: number;
    message?: string | null;
    error?: string | null;
    remoteRunId?: string | null;
    logPath?: string | null;
    startedAt?: string | null;
    completedAt?: string | null;
    durationSeconds?: number | null;
    createdAt?: string;
    updatedAt?: string;
}

export type CameraProfile =
    | 'stable_elevated_wide'
    | 'stitched_panoramic_view'
    | 'broadcast_cuts_zoom'
    | 'handheld_low_angle';

/** Declared import geometry, validated by the backend; never inferred from value ranges. */
export interface CoordinateConvention {
    schemaVersion?: 1;
    space: 'source_pixels' | 'pitch_normalized_0_100' | 'pitch_metres' | 'unknown';
    axes?: 'x_right_y_down';
    origin?: 'top_left';
    pitchLengthM?: number | null;
    pitchWidthM?: number | null;
    sourceWidth?: number | null;
    sourceHeight?: number | null;
    streamId?: string | null;
    sourceFromObservation?: [[number, number, number], [number, number, number], [number, number, number]] | null;
}

export interface UploadConfig {
    coordinateConvention?: CoordinateConvention | null;
    attackDirection?: 'left_to_right' | 'right_to_left';
    manualHomographyPoints?: Array<{ x: number; y: number }>;
    myTeamCluster?: number | null;
    llmProvider?: 'local' | 'cloud';
    autoHomography?: boolean;
    cameraProfile?: CameraProfile;
    pitchLengthM?: number | null;
    pitchWidthM?: number | null;
    periods?: Array<{ name: string; startSeconds: number; endSeconds: number }>;
    rights?: {
        processingScope: 'local_only' | 'local_plus_burst' | 'hosted';
        cloudPermission: boolean;
        retentionClass: 'working' | 'review' | 'publication' | 'unknown';
        audience?: string | null;
    };
    homeTeam?: string;
    awayTeam?: string;
    calibrationCommitted?: boolean;
}

export interface AnalyticsPayload {
    summary: MatchStats;
    ballAssignments: BallOwnership[];
    formationTimeline: FormationSegment[];
    shots: ShotMarker[];
    passingNetwork?: PassNetworkEdge[];
    shotSummary?: ShotSummary;
    playerProfiles?: PlayerProfile[];
}

export interface BackendEvent {
    eventId?: string | null;
    type: string;
    frameId: number;
    timestamp: number;
    team?: string | null;
    fromTrackId?: number | null;
    toTrackId?: number | null;
    description: string;
    reviewStatus?: 'unreviewed' | 'accepted' | 'rejected';
    heuristicName?: string;
    evidenceVersion?: string;
    intervalStart?: number;
    intervalEnd?: number;
    proposalModelId?: string | null;
    proposalModelVersion?: string | null;
    proposalEvidenceIds?: string[];
}

export interface PassNetworkEdge {
    fromId: number;
    toId: number;
    count: number;
}

export interface ShotMarker {
    frameId: number;
    timestamp: number;
    team: 'my_team' | 'enemy';
    playerId: number;
    x: number;
    y: number;
    inBox: boolean;
    xg: number;
    publishedLabel?: string;
    distanceToGoal?: number;
    angleDegrees?: number;
}

export interface ShotSummary {
    myTeamShots: number;
    enemyShots: number;
    myTeamBoxShots: number;
    enemyBoxShots: number;
    myTeamXg: number | null;
    enemyXg: number | null;
}

export interface PlayerContribution {
    team: 'my_team' | 'enemy';
    playerId: number;
    passes: number;
    crosses: number;
    throughBalls: number;
    shots: number;
    tacklesWon: number;
    recoveries: number;
    interceptions: number;
    ballWins: number;
    involvements: number;
    xgCreated: number | null;
    xgTaken: number | null;
    impactScore: number;
}

export interface PlayerProfile extends PlayerContribution {
    avgX: number | null;
    avgY: number | null;
    totalDistance: number | null;
    topSpeed: number | null;
    physicalTotalsWithheld?: boolean;
    profileLabel: string;
    summaryLine: string;
    jerseyNumber?: number | null;
}

export interface PitchAnnotations {
    offside_x?: number;
    offside?: boolean;
    explanation?: string;
    width?: number;
    too_wide?: boolean;
    error?: string;
}

// ===== Review Bundle Types =====

export interface ReviewBundleItem {
    generationId?: string;
    annotationId: string;
    matchId: string;
    frameStart: number;
    frameEnd: number;
    timestampStart: number;
    timestampEnd: number;
    label: string;
    description: string;
}

export interface ReviewBundle {
    id: string;
    name: string;
    description: string;
    items: ReviewBundleItem[];
    tags: string[];
    createdAt: string;
    updatedAt: string;
}

export interface CreateBundleInput {
    name: string;
    description?: string;
    items?: ReviewBundleItem[];
    tags?: string[];
}

export interface UpdateBundleInput {
    name?: string;
    description?: string;
    items?: ReviewBundleItem[];
    tags?: string[];
}

// ===== Review Range =====

export interface ReviewRange {
    startFrame: number;
    endFrame: number;
}

// ===== Match Issue Types =====

export type MatchIssueBucket =
  | 'upload_calibration_issue'
  | 'tracking_failure'
  | 'team_classification_issue'
  | 'ocr_issue'
  | 'event_layer_issue'
  | 'tactical_summary_issue'
  | 'ui_review_issue'
  | 'report_export_issue';

export type MatchIssueEvidenceTarget = 'trust_eval' | 'product_bug' | 'both';

export interface MatchIssue {
    id: string;
    matchId: string;
    bucket: MatchIssueBucket;
    frameStart: number;
    frameEnd: number;
    timestampStart: number;
    timestampEnd: number;
    processingBackend: 'local' | 'remote' | 'unknown';
    evidenceTarget: MatchIssueEvidenceTarget;
    note: string;
    createdAt: string;
    updatedAt: string;
}

// ===== Tactical Annotation Types =====

export interface TacticalAnnotation {
    id: string;
    matchId: string;
    type: 'note' | 'arrow' | 'circle' | 'moment';
    frameStart: number;
    frameEnd: number;
    timestampStart: number;
    timestampEnd: number;
    createdAt: string;
    updatedAt: string;
    x?: number | null;
    y?: number | null;
    x2?: number | null;
    y2?: number | null;
    text?: string | null;
    label?: string | null;
    team?: string | null;
    playerIds?: number[];
}

// ===== Runtime Capabilities =====

export interface RuntimeCapabilities {
    analysisProviders: Array<'local' | 'cloud'>;
    defaultAnalysisProvider: 'local' | 'cloud';
    processingBackend?: 'local' | 'remote';
    remoteProcessingAvailable?: boolean;
    pdfExportAvailable: boolean;
}

// ===== Dashboard / Season Trend Types =====

export interface SeasonTrendPoint {
    matchId: string;
    name: string;
    date: string;
    summary: MatchStats;
}

export interface DashboardSummary {
    matchCount: number;
    avgPossession: number | null;
    avgMyTeamXg: number | null;
    avgEnemyXg: number | null;
    avgXgDiff: number | null;
    avgMyTeamSprints: number | null;
    avgEnemySprints: number | null;
    mostUsedFormation: string | null;
}

export interface DashboardComparison {
    latestMatchId: string;
    latestMatchName: string;
    previousMatchId: string;
    previousMatchName: string;
    possessionDelta: number | null;
    xgDiffDelta: number | null;
    myTeamSprintsDelta: number | null;
    enemySprintsDelta: number | null;
}

export interface OpponentRollup {
    opponentName: string;
    matchCount: number;
    avgPossession: number;
    avgMyTeamXg: number;
    avgEnemyXg: number;
    avgEnemyXgConceded: number;
}

export interface PlayerTrendMatchEvidence {
    matchId: string;
    matchName: string;
    date: string;
    involvements: number;
    avgX: number;
    avgY: number;
    passes: number;
    ballWins: number;
    summaryLine: string;
}

export interface PlayerTrendSnapshot {
    team: 'my_team' | 'enemy';
    playerId: number;
    jerseyNumber?: number | null;
    profileLabel: string;
    latestSummaryLine: string;
    avgInvolvements: number;
    avgBallWins: number;
    recentMatches: PlayerTrendMatchEvidence[];
}

export interface SeasonTrendsResponse {
    trends: SeasonTrendPoint[];
}

export interface DashboardResponse {
    summary: DashboardSummary;
    comparison: DashboardComparison | null;
    opponentRollups: OpponentRollup[];
    playerTrendSnapshots: PlayerTrendSnapshot[];
    trends: SeasonTrendPoint[];
}

// ===== Trust Crop Types =====

export interface TrustCrop {
    frameStart: number;
    frameEnd: number;
    timestampStart: number;
    timestampEnd: number;
    score: number;
    reasons: string[];
}

export interface TrustCropsResponse {
    matchId: string;
    generationId: string | null;
    ballTeleportGeometryAvailable: boolean;
    ballTeleportReasonCodes: string[];
    crops: TrustCrop[];
    totalFrames: number;
}

// ===== Shared Coach/LLM Types =====

export interface FocusPlayer {
    trackId: number;
    team: string;
    label?: string;
    summary?: string;
}

export interface EventSummaryPlayer {
    trackId: number;
    team: string;
    involvements: number;
    actions?: Record<string, number>;
}

export interface ReportEvidenceRef {
    matchId: string;
    generationId: string;
    kind: 'event' | 'frame' | 'metric';
    localId: string;
}

export interface ScopedCoachReport {
  metrics?: Array<{ metric: string; value: number | null; unit?: string | null; availability: string; teamScope?: string | null; intervalStart?: number; intervalEnd?: number; evidence?: Array<string | ReportEvidenceRef>; eligibleSeconds?: number | null; requestedSeconds?: number | null; denominator?: string | null; reasonCodes?: string[] }>;
    schemaVersion?: string;
    matchId?: string;
    generationId?: string;
    reportId?: string;
    status?: 'current' | 'historical';
    grounding?: string;
    validationDisposition?: string;
    interpretation?: string;
    recommendations?: string[];
    metricClaims?: Array<{ metric: string; value: number; unit: string; availability: string; teamScope: string | null; intervalStart?: number; intervalEnd?: number; evidence?: Array<string | ReportEvidenceRef>; eligibleSeconds?: number | null; requestedSeconds?: number | null; denominator?: string | null; reasonCodes?: string[] }>;
    observations?: Array<{ text: string; grounding: 'referenced'; evidence: Array<string | ReportEvidenceRef> }>;
    reasonCodes?: string[];
}

export interface TacticalReport extends ScopedCoachReport {
    attacking?: string;
    defensive?: string;
    pressing?: string;
    key_player?: number;
    weaknesses?: string;
    rating?: number;
    summary?: string;
    evidence?: Array<string | ReportEvidenceRef>;
    event_summary?: {
        eventCounts?: Record<string, number>;
        topPlayers?: EventSummaryPlayer[];
    };
    player_focus?: {
        topCreator?: FocusPlayer;
        topFinisher?: FocusPlayer;
        topBallWinner?: FocusPlayer;
        otherKeyPlayers?: FocusPlayer[];
    };
}

export interface DrillSuggestion {
    name: string;
    objective: string;
    setup: string;
    duration: string;
}

export interface DrillResponse extends ScopedCoachReport {
    drills?: DrillSuggestion[];
    focus_area?: string;
    evidence?: Array<string | ReportEvidenceRef>;
    player_focus?: {
        topCreator?: FocusPlayer;
        topFinisher?: FocusPlayer;
        topBallWinner?: FocusPlayer;
        otherKeyPlayers?: FocusPlayer[];
    };
}
