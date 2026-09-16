from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .provider_adapters import execute_cloud, execute_local
from .schemas import DetectedEvent, FormationSegment, FrameData, MatchSummary, ShotAnalytics

CREATOR_EVENT_TYPES = {"pass", "cross", "through_ball"}
CREATION_FRAME_WINDOW = 12


class _ProviderPayload(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)


class _FocusPlayer(_ProviderPayload):
    trackId: int
    team: Literal["my_team", "enemy"]
    label: str = ""
    summary: str = ""
    involvements: int = Field(default=0, ge=0)
    xgCreated: float | None = Field(default=None, ge=0)
    xgTaken: float | None = Field(default=None, ge=0)
    ballWins: int = Field(default=0, ge=0)
    actions: dict[str, int] = Field(default_factory=dict)


class _PlayerFocus(_ProviderPayload):
    topCreator: _FocusPlayer | None = None
    topFinisher: _FocusPlayer | None = None
    topBallWinner: _FocusPlayer | None = None
    otherKeyPlayers: list[_FocusPlayer] = Field(default_factory=list)


class _EventSummary(_ProviderPayload):
    eventCounts: dict[str, int] = Field(default_factory=dict)
    topPlayers: list[_FocusPlayer] = Field(default_factory=list)
    teamEventCounts: dict[str, dict[str, int]] = Field(default_factory=dict)
    shotCountsByTeam: dict[str, int] = Field(default_factory=dict)
    shotXgByTeam: dict[str, float] = Field(default_factory=dict)


class _TacticalReport(_ProviderPayload):
    attacking: str
    defensive: str
    pressing: str
    key_player: int
    weaknesses: str
    rating: float = Field(ge=0, le=10)
    summary: str
    evidence: list[str] = Field(default_factory=list)
    event_summary: _EventSummary = Field(default_factory=_EventSummary)
    player_focus: _PlayerFocus = Field(default_factory=_PlayerFocus)


class _Drill(_ProviderPayload):
    name: str
    objective: str
    setup: str
    duration: str


class _Drills(_ProviderPayload):
    drills: list[_Drill]
    focus_area: str
    evidence: list[str] = Field(default_factory=list)
    player_focus: _PlayerFocus = Field(default_factory=_PlayerFocus)


class _Offside(_ProviderPayload):
    offside: bool
    offside_x: float
    explanation: str


class _Spacing(_ProviderPayload):
    width: float
    too_wide: bool
    explanation: str


def _validate_provider_output(analysis_type: str, payload: object) -> dict:
    schema = {"tactical_report": _TacticalReport, "drills": _Drills, "offside": _Offside, "spacing": _Spacing}[analysis_type]
    return schema.model_validate(payload).model_dump(mode="json", exclude_unset=True)


def _sample_frames(frames: list[FrameData], sample_size: int = 10) -> list[dict]:
    if len(frames) <= sample_size:
        return [frame.model_dump(mode="json") for frame in frames]
    step = max(1, len(frames) // sample_size)
    return [frame.model_dump(mode="json") for frame in frames[::step]]


def _round_two(value: float) -> float:
    return round(value, 2)


def _format_count(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _build_event_summary(events: list[DetectedEvent], shots: list[ShotAnalytics] | None = None) -> dict:
    counts = Counter(event.type for event in events)
    team_counts: dict[str, Counter[str]] = {
        "my_team": Counter(),
        "enemy": Counter(),
    }
    player_map: dict[tuple[str, int], dict] = defaultdict(
        lambda: {"trackId": None, "team": None, "involvements": 0, "actions": Counter()}
    )

    for event in events:
        if event.team in team_counts:
            team_counts[event.team][event.type] += 1

        for track_id in (event.fromTrackId, event.toTrackId):
            if track_id is None or event.team not in team_counts:
                continue
            player = player_map[(event.team, track_id)]
            player["trackId"] = track_id
            player["team"] = event.team
            player["involvements"] += 1
            player["actions"][event.type] += 1

    top_players = [
        {
            "trackId": player["trackId"],
            "team": player["team"],
            "involvements": player["involvements"],
            "actions": dict(player["actions"]),
        }
        for player in sorted(
            player_map.values(),
            key=lambda item: (
                -item["involvements"],
                -item["actions"].get("shot", 0),
                -item["actions"].get("pass", 0),
                item["trackId"] or 0,
            ),
        )[:5]
    ]

    shot_xg_by_team: dict[str, float] = defaultdict(float)
    shot_count_by_team: Counter[str] = Counter()
    if shots:
        for shot in shots:
            shot_count_by_team[shot.team] += 1
            shot_xg_by_team[shot.team] += shot.xg

    return {
        "eventCounts": dict(sorted(counts.items())),
        "teamEventCounts": {
            team: dict(sorted(counter.items()))
            for team, counter in team_counts.items()
            if counter
        },
        "shotCountsByTeam": dict(sorted(shot_count_by_team.items())),
        "shotXgByTeam": {team: _round_two(value) for team, value in sorted(shot_xg_by_team.items())},
        "topPlayers": top_players,
    }


def _select_player_label(player: dict) -> str:
    created = player.get("xgCreated")
    taken = player.get("xgTaken")
    if (created is not None and created >= 0.15) or player["actions"].get("through_ball", 0) > 0:
        return "Primary Creator"
    if (taken is not None and taken >= 0.15) or player["actions"].get("shot", 0) > 0:
        return "Shot Threat"
    if player["ballWins"] > 0:
        return "Ball Winner"
    if player["actions"].get("cross", 0) > 0:
        return "Wide Threat"
    if player["actions"].get("pass", 0) >= 3:
        return "Connector"
    return "Support Option"


def _build_player_summary(player: dict, label: str) -> str:
    if label == "Primary Creator":
        quality = (
            "experimental shot quality unavailable"
            if player["xgCreated"] is None
            else f"{player['xgCreated']:.2f} experimental shot quality created"
        )
        return f"{_format_count(player['actions'].get('through_ball', 0), 'through ball')}, {quality}"
    if label == "Shot Threat":
        quality = (
            "experimental shot quality unavailable"
            if player["xgTaken"] is None
            else f"{player['xgTaken']:.2f} experimental shot quality"
        )
        return f"{_format_count(player['actions'].get('shot', 0), 'shot')}, {quality}"
    if label == "Ball Winner":
        return f"{_format_count(player['ballWins'], 'ball win')}, {_format_count(player['actions'].get('interception', 0), 'interception')}"
    if label == "Wide Threat":
        return f"{_format_count(player['actions'].get('cross', 0), 'cross')}, {player['involvements']} involvements"
    return f"{_format_count(player['actions'].get('pass', 0), 'pass')}, {player['involvements']} involvements"


def _build_player_focus(events: list[DetectedEvent] | None, shots: list[ShotAnalytics] | None) -> dict:
    if not events and not shots:
        return {}

    players: dict[tuple[str, int], dict] = defaultdict(
        lambda: {
            "trackId": None,
            "team": None,
            "involvements": 0,
            "actions": Counter(),
            "xgCreated": 0.0,
            "xgTaken": 0.0,
            "ballWins": 0,
        }
    )

    def ensure(team: str, track_id: int) -> dict:
        player = players[(team, track_id)]
        player["trackId"] = track_id
        player["team"] = team
        return player

    for event in events or []:
        if event.team not in {"my_team", "enemy"}:
            continue
        team = event.team
        if event.type in {"pass", "cross", "through_ball", "shot"} and event.fromTrackId is not None:
            player = ensure(team, event.fromTrackId)
            player["involvements"] += 1
            player["actions"][event.type] += 1
        elif event.type in {"tackle", "recovery", "interception", "turnover"} and event.toTrackId is not None:
            player = ensure(team, event.toTrackId)
            player["involvements"] += 1
            player["actions"][event.type] += 1
            if event.type in {"tackle", "recovery", "interception"}:
                player["ballWins"] += 1

    for shot in shots or []:
        player = ensure(shot.team, shot.playerId)
        player["xgTaken"] = _round_two(player["xgTaken"] + shot.xg)

    creator_events = sorted(
        [
            event
            for event in (events or [])
            if event.team in {"my_team", "enemy"} and event.fromTrackId is not None and event.type in CREATOR_EVENT_TYPES
        ],
        key=lambda event: (event.frameId, event.timestamp),
    )

    for shot in shots or []:
        creator = next(
            (
                event
                for event in reversed(creator_events)
                if event.team == shot.team
                and event.frameId <= shot.frameId
                and (shot.frameId - event.frameId) <= CREATION_FRAME_WINDOW
                and not (event.frameId == shot.frameId and event.timestamp > shot.timestamp)
                and event.fromTrackId != shot.playerId
            ),
            None,
        )
        if creator is None or creator.fromTrackId is None:
            continue
        player = ensure(shot.team, creator.fromTrackId)
        player["xgCreated"] = _round_two(player["xgCreated"] + shot.xg)

    labelled_shots = bool(shots)
    ranked_players = []
    for player in players.values():
        published_created = None if not labelled_shots else _round_two(player["xgCreated"])
        published_taken = None if not labelled_shots else _round_two(player["xgTaken"])
        published = {**player, "xgCreated": published_created, "xgTaken": published_taken}
        label = _select_player_label(published)
        ranked_players.append(
            {
                "trackId": player["trackId"],
                "team": player["team"],
                "label": label,
                "summary": _build_player_summary(published, label),
                "involvements": player["involvements"],
                "xgCreated": published_created,
                "xgTaken": published_taken,
                "ballWins": player["ballWins"],
                "actions": dict(player["actions"]),
            }
        )

    if not ranked_players:
        return {}

    top_creator = next(
        iter(
            sorted(
                [player for player in ranked_players if (player["xgCreated"] or 0) > 0 or player["actions"].get("through_ball", 0) > 0],
                key=lambda player: (-(player["xgCreated"] or 0), -player["actions"].get("through_ball", 0), player["trackId"]),
            )
        ),
        None,
    )
    top_finisher = next(
        iter(
            sorted(
                [player for player in ranked_players if (player["xgTaken"] or 0) > 0 or player["actions"].get("shot", 0) > 0],
                key=lambda player: (-(player["xgTaken"] or 0), -player["actions"].get("shot", 0), player["trackId"]),
            )
        ),
        None,
    )
    top_ball_winner = next(
        iter(
            sorted(
                [player for player in ranked_players if player["ballWins"] > 0],
                key=lambda player: (-player["ballWins"], -player["actions"].get("interception", 0), player["trackId"]),
            )
        ),
        None,
    )

    used_keys = {
        (player["team"], player["trackId"])
        for player in (top_creator, top_finisher, top_ball_winner)
        if player is not None
    }
    other_players = [
        player
        for player in sorted(
            ranked_players,
            key=lambda item: (-item["involvements"], -((item["xgCreated"] or 0) + (item["xgTaken"] or 0)), item["trackId"]),
        )
        if (player["team"], player["trackId"]) not in used_keys
    ][:3]

    return {
        "topCreator": top_creator,
        "topFinisher": top_finisher,
        "topBallWinner": top_ball_winner,
        "otherKeyPlayers": other_players,
    }


def _published_metric(summary: MatchSummary, metric: str) -> float | None:
    for item in summary.metricAvailability:
        if item.metric == metric:
            return item.published_value()
    return None


def _build_match_signals(summary: MatchSummary | None, formation_timeline: list[FormationSegment] | None) -> dict:
    if summary is None:
        return {}
    my_ppda = _published_metric(summary, "my_team_ppda")
    enemy_ppda = _published_metric(summary, "enemy_ppda")
    pressing_edge = None if my_ppda is None or enemy_ppda is None else _round_two(enemy_ppda - my_ppda)
    if not summary.metricAvailability:
        pressing_edge = (
            None
            if summary.enemyPpda is None or summary.myTeamPpda is None
            else _round_two(summary.enemyPpda - summary.myTeamPpda)
        )
    return {
        "possession": summary.possession,
        "xgBalance": (
            None
            if summary.myTeamXg is None or summary.enemyXg is None
            else _round_two(summary.myTeamXg - summary.enemyXg)
        ),
        "pressingEdge": pressing_edge,
        "shotQualityLabel": "experimental_shot_quality",
        "defensiveLineEdge": (
            None
            if summary.myTeamDefensiveLineHeight is None or summary.enemyDefensiveLineHeight is None
            else _round_two(summary.myTeamDefensiveLineHeight - summary.enemyDefensiveLineHeight)
        ),
        "recentFormations": [
            {
                "formation": segment.formation,
                "startTimestamp": segment.startTimestamp,
                "endTimestamp": segment.endTimestamp,
            }
            for segment in (formation_timeline or [])[-3:]
        ],
    }


def _build_match_context(
    frames: list[FrameData],
    summary: MatchSummary | None,
    events: list[DetectedEvent] | None,
    formation_timeline: list[FormationSegment] | None,
    shots: list[ShotAnalytics] | None,
) -> dict:
    context = {
        "sampledFrames": _sample_frames(frames, sample_size=6),
    }
    if summary is not None:
        context["summary"] = summary.model_dump(mode="json")
    if events is not None:
        context["eventSummary"] = _build_event_summary(events, shots)
        context["recentEvents"] = [event.model_dump(mode="json") for event in events[:12]]
    if formation_timeline is not None:
        context["formationTimeline"] = [segment.model_dump(mode="json") for segment in formation_timeline]
    if shots is not None:
        context["shots"] = [shot.model_dump(mode="json") for shot in shots[:10]]
    player_focus = _build_player_focus(events, shots)
    if player_focus:
        context["playerFocus"] = player_focus
    match_signals = _build_match_signals(summary, formation_timeline)
    if match_signals:
        context["matchSignals"] = match_signals
    return context


def build_prompt(
    analysis_type: str,
    frames: list[FrameData],
    current_frame: FrameData | None = None,
    *,
    summary: MatchSummary | None = None,
    events: list[DetectedEvent] | None = None,
    formation_timeline: list[FormationSegment] | None = None,
    shots: list[ShotAnalytics] | None = None,
    attack_direction: Literal["left_to_right", "right_to_left"] = "left_to_right",
) -> str:
    direction_context = (
        f"My team attacks {attack_direction} toward "
        f"{'decreasing' if attack_direction == 'right_to_left' else 'increasing'} x; "
        "the opponent attacks the opposite direction. Coordinates are the original 0-100 display coordinates. "
    )
    if analysis_type == "offside" and current_frame:
        return (
            direction_context + "You are a football tactician API. Based on this frame data: "
            f"{json.dumps(current_frame.model_dump(mode='json'))}. "
            'Determine if any my-team player is behind the last enemy defender. '
            'Return JSON {"offside": boolean, "offside_x": number, "explanation": string}. '
            "This is a review prompt only: do not present it as a validated IFAB Law 11 decision; "
            "involvement, first contact, restarts and eligible body parts are not measured."
        )
    if analysis_type == "spacing" and current_frame:
        return (
            direction_context + "You are a football tactician API. Based on this frame data: "
            f"{json.dumps(current_frame.model_dump(mode='json'))}. "
            'Analyze the horizontal distance between the leftmost and rightmost my-team players. '
            'Return JSON {"width": number, "too_wide": boolean, "explanation": string}.'
        )
    if analysis_type == "tactical_report":
        context = _build_match_context(frames, summary, events, formation_timeline, shots)
        context["attackDirection"] = attack_direction
        return (
            "You are an elite football analyst AI. Use the derived match context below as the primary source of truth, "
            "and only use sampled frames as supporting context. Return JSON with "
            '{"attacking": string, "defensive": string, "pressing": string, "key_player": number, '
            '"weaknesses": string, "rating": number, "summary": string, "evidence": string[], '
            '"event_summary": {"eventCounts": object, "topPlayers": array}, "player_focus": object}. '
            f"Context: {json.dumps(context)}"
        )
    if analysis_type == "drills":
        context = _build_match_context(frames, summary, events, formation_timeline, shots)
        context["attackDirection"] = attack_direction
        return (
            "You are a professional football coaching assistant. Suggest 3 training drills from this derived match context and "
            'return JSON {"drills": [{"name": string, "objective": string, "setup": string, "duration": string}], '
            '"focus_area": string, "evidence": string[], "player_focus": object}. '
            f"Context: {json.dumps(context)}"
        )
    raise ValueError(f"Unsupported analysis type: {analysis_type}")


def run_analysis(
    analysis_type: str,
    frames: list[FrameData],
    *,
    provider: str = "local",
    attack_direction: Literal["left_to_right", "right_to_left"] = "left_to_right",
    current_frame_index: int | None = None,
    summary: MatchSummary | None = None,
    events: list[DetectedEvent] | None = None,
    formation_timeline: list[FormationSegment] | None = None,
    shots: list[ShotAnalytics] | None = None,
) -> dict:
    current_frame = frames[current_frame_index] if current_frame_index is not None and frames else None
    prompt = build_prompt(
        analysis_type,
        frames,
        current_frame=current_frame,
        summary=summary,
        events=events,
        formation_timeline=formation_timeline,
        shots=shots,
        attack_direction=attack_direction,
    )

    if provider == "local":
        return execute_local(prompt, analysis_type, _validate_provider_output)

    if provider == "cloud":
        return execute_cloud(prompt, analysis_type, _validate_provider_output)

    raise ValueError(f"Unsupported provider: {provider}")
