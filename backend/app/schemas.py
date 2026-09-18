from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic.dataclasses import dataclass

from .domain_types import FiniteFloat


class HomographyPoint(BaseModel):
    x: FiniteFloat
    y: FiniteFloat


class MatchPeriod(BaseModel):
    name: str
    startSeconds: FiniteFloat
    endSeconds: FiniteFloat

    @model_validator(mode="after")
    def ordered(self):
        if self.startSeconds > self.endSeconds:
            raise ValueError("period start must not exceed end")
        return self


class SourceRights(BaseModel):
    processingScope: Literal["local_only", "local_plus_burst", "hosted"] = "local_only"
    cloudPermission: bool = False
    retentionClass: Literal["working", "review", "publication", "unknown"] = "unknown"
    audience: str | None = None


class MatchConfig(BaseModel):
    attackDirection: Literal["left_to_right", "right_to_left"] = "left_to_right"
    manualHomographyPoints: list[HomographyPoint] = Field(default_factory=list)
    myTeamCluster: int | None = None
    llmProvider: Literal["local", "cloud"] = "local"
    autoHomography: bool = False  # if True, skip manualHomographyPoints and try pitch_detector.py first
    cameraProfile: Literal[
        "stable_elevated_wide",
        "stitched_panoramic_view",
        "broadcast_cuts_zoom",
        "handheld_low_angle",
    ] = "stitched_panoramic_view"
    pitchLengthM: FiniteFloat | None = Field(default=None, gt=0)
    pitchWidthM: FiniteFloat | None = Field(default=None, gt=0)
    periods: list[MatchPeriod] = Field(default_factory=list)
    rights: SourceRights = Field(default_factory=SourceRights)
    homeTeam: str = ""
    awayTeam: str = ""
    calibrationCommitted: bool = False

    @model_validator(mode="after")
    def ordered_periods(self):
        previous_end: float | None = None
        for period in self.periods:
            if previous_end is not None and period.startSeconds < previous_end:
                raise ValueError("periods must be ordered and non-overlapping")
            previous_end = period.endSeconds
        return self


class BallData(BaseModel):
    x: FiniteFloat
    y: FiniteFloat
    confidence: FiniteFloat = 0.0


class BallEstimate(BaseModel):
    x: FiniteFloat
    y: FiniteFloat
    confidence: FiniteFloat = 0.0
    radius: FiniteFloat = 0.0


@dataclass(slots=True)
class PlayerData:
    id: int
    x: FiniteFloat
    y: FiniteFloat
    confidence: FiniteFloat = 0.0


class FrameData(BaseModel):
    frameId: int
    timestamp: FiniteFloat
    ball: BallData | None = None
    myTeam: list[PlayerData] = Field(default_factory=list)
    enemies: list[PlayerData] = Field(default_factory=list)
    unassignedPlayers: list[PlayerData] = Field(default_factory=list)
    possession: "BallOwnership | None" = None


class BallOwnership(BaseModel):
    frameId: int
    timestamp: float
    team: Literal["my_team", "enemy", "contested", "dead_ball", "unassigned"]
    trackId: int | None = None
    distance: float | None = None


class MatchStateFrame(BaseModel):
    frameId: int
    timestamp: float
    mode: Literal["controlled_possession", "loose_ball", "aerial_transit", "restart_or_out", "unknown"]
    controllingTeam: Literal["my_team", "enemy", "unassigned", "contested", "none"]
    controllingTrackId: int | None = None
    ballVisibility: Literal["visible", "inferred", "hidden"]
    ballEstimate: BallEstimate | None = None
    source: Literal["observed_ball", "inferred_ball", "player_conditioned", "restart_rule", "unknown"]
    confidence: float = 0.0
    reasonCodes: list[str] = Field(default_factory=list)


class MetricAvailabilityRecord(BaseModel):
    metric: str
    definitionVersion: str = "1"
    value: float | None = None
    availability: Literal["available", "experimental", "withheld", "unknown"] = "unknown"
    eligibleSeconds: float = 0.0
    requestedSeconds: float = 0.0
    evidenceIds: list[str] = Field(default_factory=list)
    reasonCodes: list[str] = Field(default_factory=list)
    reviewStatus: str = "unreviewed"
    unit: str | None = None
    denominator: str | None = None
    publishedLabel: str | None = None
    teamScope: Literal["my_team", "enemy"] | None = None
    deprecated: bool = False
    pitchDimensions: dict[str, float] | None = None

    def published_value(self) -> float | None:
        if self.availability not in {"available", "experimental"}:
            return None
        return self.value


class MatchSummary(BaseModel):
    possession: int | None
    myTeamDistance: int | None
    enemyDistance: int | None
    myTeamAvgPos: dict[str, float] | None = None
    enemyAvgPos: dict[str, float] | None = None
    myTeamTopSpeed: float | None
    enemyTopSpeed: float | None
    myTeamSprints: int | None
    enemySprints: int | None
    myTeamXg: float | None = None
    enemyXg: float | None = None
    myTeamDefensiveLineHeight: float | None = None
    enemyDefensiveLineHeight: float | None = None
    myTeamDefensiveTeamLength: float | None = None
    enemyDefensiveTeamLength: float | None = None
    myTeamPpda: float | None = None
    enemyPpda: float | None = None
    myTeamHighPressRegains: int | None = None
    enemyHighPressRegains: int | None = None
    myTeamCounterpressRecoverySeconds: float | None = None
    enemyCounterpressRecoverySeconds: float | None = None
    formation: str | None = None
    # Defensive context metrics
    myTeamBlockHeight: str | None = None
    enemyBlockHeight: str | None = None
    myTeamRegainZones: dict[str, int] | None = None
    enemyRegainZones: dict[str, int] | None = None
    myTeamTransitionExposure: float | None = None
    enemyTransitionExposure: float | None = None
    ballSignalStatus: str = "trusted"
    ballSignalMessage: str | None = None
    truthGateReasons: list[str] = Field(default_factory=list)
    metricAvailability: list[MetricAvailabilityRecord] = Field(default_factory=list)


class FormationSegment(BaseModel):
    formation: str
    startFrameId: int
    endFrameId: int
    startTimestamp: float
    endTimestamp: float


class ShotAnalytics(BaseModel):
    frameId: int
    timestamp: float
    team: Literal["my_team", "enemy"]
    playerId: int
    x: float
    y: float
    inBox: bool
    xg: float
    publishedLabel: str = "experimental_shot_quality"
    distanceToGoal: float
    angleDegrees: float


class DetectedEvent(BaseModel):
    eventId: str | None = None
    type: str
    frameId: int
    timestamp: float
    team: str | None = None
    fromTrackId: int | None = None
    toTrackId: int | None = None
    description: str
    reviewStatus: Literal["unreviewed", "accepted", "rejected"] = "unreviewed"
    heuristicName: str = "provisional_event_suggestion"
    evidenceVersion: str | None = None
    intervalStart: float | None = None
    intervalEnd: float | None = None


class ColorClusterSummary(BaseModel):
    clusterId: int
    rgbCentroid: list[float]
    trackIds: list[int]


class ColorClusterResult(BaseModel):
    trackToCluster: dict[int, int]
    clusters: list[ColorClusterSummary]


class MatchRecord(BaseModel):
    id: str
    name: str
    inputMode: str
    status: str
    originalFilename: str
    config: MatchConfig
    createdAt: datetime
    updatedAt: datetime
    requiresTeamSelection: bool = False
    teamClusters: list[ColorClusterSummary] = Field(default_factory=list)


class JobRecord(BaseModel):
    id: str
    matchId: str
    status: str
    progress: float
    message: str | None = None
    error: str | None = None
    remoteRunId: str | None = None
    logPath: str | None = None
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    durationSeconds: float | None = None
    createdAt: datetime
    updatedAt: datetime


class MatchFramesResponse(BaseModel):
    matchId: str
    frames: list[FrameData]
    nextCursor: str | None = None
    frameCount: int | None = None
    intervalEndpoint: str = "half_open"


class MatchAnalyticsResponse(BaseModel):
    matchId: str
    summary: MatchSummary
    ballAssignments: list[BallOwnership]
    formationTimeline: list[FormationSegment] = Field(default_factory=list)
    shots: list[ShotAnalytics] = Field(default_factory=list)


class MatchEventsResponse(BaseModel):
    matchId: str
    events: list[DetectedEvent]


# Review Bundle / Playlist schemas
class ReviewBundleItem(BaseModel):
    annotationId: str
    matchId: str
    frameStart: int
    frameEnd: int
    timestampStart: float
    timestampEnd: float
    label: str
    description: str = ""


class ReviewBundle(BaseModel):
    id: str
    name: str
    description: str = ""
    items: list[ReviewBundleItem] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class CreateBundleRequest(BaseModel):
    name: str
    description: str = ""
    items: list[ReviewBundleItem] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class UpdateBundleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    items: list[ReviewBundleItem] | None = None
    tags: list[str] | None = None


# Semantic Search / Tactical Theme Search schemas
class TacticalTheme(str):
    """Known tactical themes for filtering and searching."""
    HIGH_PRESS = "high_press"
    LOW_BLOCK = "low_block"
    MID_BLOCK = "mid_block"
    COUNTER_ATTACK = "counter_attack"
    POSSESSION_BASED = "possession_based"
    DIRECT_PLAY = "direct_play"
    WING_PLAY = "wing_play"
    THROUGH_BALLS = "through_balls"
    DEFENSIVE_TRANSITION = "defensive_transition"
    OFFENSIVE_TRANSITION = "offensive_transition"
    DEEP_DEFENSE = "deep_defense"
    AGGRESSIVE_PRESS = "aggressive_press"
    PASSIVE_PRESS = "passive_press"


class SearchQuery(BaseModel):
    """Natural language search query for tactical search."""
    query: str = Field(..., description="Natural language query (e.g., 'matches with high press and counter-attacks')")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum results to return")
    match_ids: list[str] | None = Field(default=None, description="Optional: restrict search to specific match IDs")
    tactical_themes: list[str] | None = Field(default=None, description="Optional: filter by tactical themes")


class MatchSearchResult(BaseModel):
    """A single match search result."""
    matchId: str
    matchName: str
    relevanceScore: float = Field(..., description="Relevance score 0-100")
    matchedThemes: list[str] = Field(default_factory=list, description="Tactical themes matched")
    summary: str = Field(default="", description="Brief summary explaining the match")
    summaryData: dict = Field(default_factory=dict, description="Match summary data")


class BundleSearchResult(BaseModel):
    """A single bundle search result."""
    bundleId: str
    bundleName: str
    relevanceScore: float = Field(..., description="Relevance score 0-100")
    matchedThemes: list[str] = Field(default_factory=list)
    itemCount: int = 0
    description: str = ""


class SemanticSearchResponse(BaseModel):
    """Response for semantic search queries."""
    query: str
    results: list[MatchSearchResult] = Field(default_factory=list)
    totalMatches: int = 0
    searchMetadata: dict = Field(default_factory=dict)


class BundleSearchResponse(BaseModel):
    """Response for bundle search queries."""
    query: str
    results: list[BundleSearchResult] = Field(default_factory=list)
    totalMatches: int = 0


class TacticalThemeSummary(BaseModel):
    """Summary of tactical themes for a match."""
    matchId: str
    detectedThemes: list[str] = Field(default_factory=list)
    themeDetails: dict[str, float] = Field(default_factory=dict, description="Theme strength scores")


FrameData.model_rebuild()


# ===== Annotation & Issue Schemas =====


class TacticalAnnotationRecord(BaseModel):
    """A persisted annotation on a match — note, arrow, circle, or tagged moment."""
    id: str
    matchId: str
    type: Literal["note", "arrow", "circle", "moment"]
    frameStart: int
    frameEnd: int
    timestampStart: float
    timestampEnd: float
    x: float | None = None
    y: float | None = None
    x2: float | None = None
    y2: float | None = None
    text: str | None = None
    label: str | None = None
    team: str | None = None
    playerIds: list[int] | None = None
    createdAt: str
    updatedAt: str


class CreateAnnotationRequest(BaseModel):
    """Request body for POST /api/matches/{match_id}/annotations."""
    type: Literal["note", "arrow", "circle", "moment"]
    frameStart: int
    frameEnd: int
    timestampStart: float
    timestampEnd: float
    x: float | None = None
    y: float | None = None
    x2: float | None = None
    y2: float | None = None
    text: str | None = None
    label: str | None = None
    team: str | None = None
    playerIds: list[int] | None = None


class MatchIssueRecord(BaseModel):
    """A logged issue / trust crop for a match."""
    id: str
    matchId: str
    bucket: str
    frameStart: int
    frameEnd: int
    timestampStart: float
    timestampEnd: float
    processingBackend: Literal["local", "remote", "unknown"] = "unknown"
    evidenceTarget: Literal["trust_eval", "product_bug", "both"] = "both"
    note: str
    createdAt: str
    updatedAt: str


class CreateIssueRequest(BaseModel):
    """Request body for POST /api/matches/{match_id}/issues."""
    frameStart: int
    frameEnd: int
    timestampStart: float
    timestampEnd: float
    bucket: str
    processingBackend: Literal["local", "remote", "unknown"] = "unknown"
    evidenceTarget: Literal["trust_eval", "product_bug", "both"] = "both"
    note: str


# ===== Dashboard =====


class DashboardSummary(BaseModel):
    """Aggregated totals and averages across all completed matches."""
    matchCount: int
    avgPossession: float | None
    avgMyTeamXg: float | None
    avgEnemyXg: float | None
    avgXgDiff: float | None
    avgMyTeamSprints: float | None
    avgEnemySprints: float | None
    mostUsedFormation: str | None


class SeasonTrendPoint(BaseModel):
    """Single data point in season trends."""
    matchId: str
    name: str
    date: str
    summary: "MatchSummary"


class DashboardComparison(BaseModel):
    """Side-by-side comparison delta between the last 2 matches."""
    latestMatchId: str
    latestMatchName: str
    previousMatchId: str
    previousMatchName: str
    possessionDelta: float | None
    xgDiffDelta: float | None
    myTeamSprintsDelta: float | None
    enemySprintsDelta: float | None


class DashboardResponse(BaseModel):
    """Response for GET /api/dashboard."""
    summary: DashboardSummary
    comparison: DashboardComparison | None = None
    opponentRollups: list = []
    playerTrendSnapshots: list = []
    trends: list[SeasonTrendPoint] = []


# ===== Trust Crops =====


class TrustCropSchema(BaseModel):
    """A frame window flagged as uncertain / worth human review."""
    frameStart: int
    frameEnd: int
    timestampStart: float
    timestampEnd: float
    score: float
    reasons: list[str]


class TrustCropsResponse(BaseModel):
    """Response for trust crop queue for a match."""
    matchId: str
    crops: list[TrustCropSchema]
    totalFrames: int
