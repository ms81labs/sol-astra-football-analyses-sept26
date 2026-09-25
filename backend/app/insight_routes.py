"""Aggregate dashboard and tactical-search API routes."""

from typing import Annotated

import math
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from .schemas import (
    DashboardComparison,
    DashboardResponse,
    DashboardSummary,
    MatchRecord,
    SeasonTrendPoint,
)
from .semantic_search import (
    detect_themes_for_match,
    search_bundles_by_tactical_themes,
    search_matches_by_tactical_themes,
)
from .storage import Storage


def _dashboard_metric_value(summary: dict, *, field: str, metric: str) -> float | None:
    """A missing/withheld measurement is not zero, including historical summaries."""
    record = next(
        (item for item in summary.get("metricAvailability") or [] if item.get("metric") == metric),
        None,
    )
    if record is not None and record.get("availability") not in {"available", "experimental"}:
        return None
    value = summary.get(field) if record is None else record.get("value")
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return float(value)


def _dashboard_average(summaries: list[dict], *, field: str, metric: str, digits: int = 1) -> float | None:
    values = [value for summary in summaries
              if (value := _dashboard_metric_value(summary, field=field, metric=metric)) is not None]
    return round(sum(values) / len(values), digits) if values else None


def _dashboard_difference(latest: dict, previous: dict, *, field: str, metric: str) -> float | None:
    left = _dashboard_metric_value(latest, field=field, metric=metric)
    right = _dashboard_metric_value(previous, field=field, metric=metric)
    return round(left - right, 1) if left is not None and right is not None else None


def _xg_balance(summary: dict) -> float | None:
    my_xg = summary.get("myTeamXg")
    enemy_xg = summary.get("enemyXg")
    if my_xg is None or enemy_xg is None:
        return None
    return round(float(my_xg) - float(enemy_xg), 2)


def create_insight_router(
    storage: Storage,
    require_match: Callable[..., MatchRecord],
) -> APIRouter:
    router = APIRouter()

    # ===== Dashboard =====

    @router.get("/api/aggregate/dashboard")
    def get_dashboard() -> dict:
        """Aggregate stats across all completed matches."""
        all_matches = storage.list_matches_with_analytics()
        if not all_matches:
            empty = DashboardResponse(
                summary=DashboardSummary(
                    matchCount=0, avgPossession=None, avgMyTeamXg=None, avgEnemyXg=None,
                    avgXgDiff=None, avgMyTeamSprints=None, avgEnemySprints=None,
                    mostUsedFormation=None,
                ),
            )
            return empty.model_dump(mode="json")

        summaries = [m["summary"] for m in all_matches]
        measured_possession = [s["possession"] for s in summaries if s.get("possession") is not None]
        avg_pos = sum(measured_possession) / len(measured_possession) if measured_possession else None
        avg_my_xg = _dashboard_average(summaries, field="myTeamXg", metric="my_team_experimental_shot_quality_sum", digits=2)
        avg_enemy_xg = _dashboard_average(summaries, field="enemyXg", metric="enemy_experimental_shot_quality_sum", digits=2)
        avg_xg_diff = None if avg_my_xg is None or avg_enemy_xg is None else round(avg_my_xg - avg_enemy_xg, 2)
        avg_my_sprints = _dashboard_average(summaries, field="myTeamSprints", metric="my_team_sprints")
        avg_enemy_sprints = _dashboard_average(summaries, field="enemySprints", metric="enemy_sprints")

        from collections import Counter
        formations = [s.get("formation") for s in summaries if s.get("formation") and s.get("formation") != "-"]
        most_used = Counter(formations).most_common(1)[0][0] if formations else None

        summary = DashboardSummary(
            matchCount=len(summaries),
            avgPossession=round(avg_pos, 1) if avg_pos is not None else None,
            avgMyTeamXg=avg_my_xg,
            avgEnemyXg=avg_enemy_xg,
            avgXgDiff=avg_xg_diff,
            avgMyTeamSprints=avg_my_sprints,
            avgEnemySprints=avg_enemy_sprints,
            mostUsedFormation=most_used,
        )

        # Season trends — one point per match
        sorted_matches = sorted(all_matches, key=lambda m: m["createdAt"])
        from .schemas import MatchSummary as MSS
        trends = [
            SeasonTrendPoint(
                matchId=m["matchId"],
                name=m["matchName"],
                date=m["createdAt"],
                summary=MSS.model_validate(m["summary"]),
            )
            for m in sorted_matches
        ]

        # Comparison delta between last 2 matches
        last_two = sorted(all_matches, key=lambda m: m["createdAt"], reverse=True)[:2]
        comparison = None
        if len(last_two) == 2:
            latest, previous = last_two[0], last_two[1]
            s_latest = latest["summary"]
            s_prev = previous["summary"]
            comparison = DashboardComparison(
                latestMatchId=latest["matchId"],
                latestMatchName=latest["matchName"],
                previousMatchId=previous["matchId"],
                previousMatchName=previous["matchName"],
                possessionDelta=(
                    round(s_latest["possession"] - s_prev["possession"], 1)
                    if s_latest.get("possession") is not None and s_prev.get("possession") is not None
                    else None
                ),
                xgDiffDelta=(
                    round(latest_balance - previous_balance, 2)
                    if (latest_balance := _xg_balance(s_latest)) is not None
                    and (previous_balance := _xg_balance(s_prev)) is not None
                    else None
                ),
                myTeamSprintsDelta=_dashboard_difference(
                    s_latest, s_prev, field="myTeamSprints", metric="my_team_sprints",
                ),
                enemySprintsDelta=_dashboard_difference(
                    s_latest, s_prev, field="enemySprints", metric="enemy_sprints",
                ),
            )

        response = DashboardResponse(
            summary=summary,
            comparison=comparison,
            opponentRollups=[],
            playerTrendSnapshots=[],
            trends=trends,
        )
        return response.model_dump(mode="json")

    # ===== Semantic Search / Tactical Theme Search =====

    @router.get("/api/search/matches")
    def search_matches(
        q: str,
        limit: int = 10,
        match_ids: str | None = None,
    ) -> dict:
        """Search matches by tactical themes using natural language.
        
        Args:
            q: Natural language search query (e.g., "high press counter-attacks")
            limit: Maximum number of results (default 10, max 50)
            match_ids: Optional comma-separated list of match IDs to search
        
        Returns:
            Semantic search results with relevance scores and matched themes
        """
        limit = min(max(1, limit), 50)
        match_id_list = match_ids.split(",") if match_ids else None
        
        # Get all matches with analytics
        all_matches = storage.list_matches_with_analytics()
        
        # Filter by specific match IDs if provided
        if match_id_list:
            all_matches = [m for m in all_matches if m["matchId"] in match_id_list]
        
        if not all_matches:
            return {
                "query": q,
                "results": [],
                "totalMatches": 0,
                "searchMetadata": {
                    "availableMatches": 0,
                    "filtersApplied": bool(match_ids),
                },
            }
        
        # Perform semantic search
        results = search_matches_by_tactical_themes(q, all_matches)
        
        # Apply limit
        results = results[:limit]
        
        return {
            "query": q,
            "results": results,
            "totalMatches": len(results),
            "searchMetadata": {
                "availableMatches": len(all_matches),
                "filtersApplied": bool(match_ids),
            },
        }

    @router.get("/api/search/bundles")
    def search_bundles(q: str, limit: int = 10) -> dict:
        """Search bundles by tactical themes using natural language.
        
        Args:
            q: Natural language search query (e.g., "counter-attack wing play")
            limit: Maximum number of results (default 10, max 50)
        
        Returns:
            Bundle search results with relevance scores and matched themes
        """
        limit = min(max(1, limit), 50)
        bundles = storage.list_review_bundles()
        results = search_bundles_by_tactical_themes(q, bundles)
        results = results[:limit]
        
        return {
            "query": q,
            "results": results,
            "totalMatches": len(results),
        }

    @router.get("/api/matches/{match_id}/themes")
    def get_match_themes(match: Annotated[MatchRecord, Depends(require_match)]) -> dict:
        """Get detected tactical themes for a specific match.
        
        Returns:
            Match with detected tactical themes and strength scores
        """
        try:
            summary, _, _, _ = storage.load_analytics(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
        
        theme_data = detect_themes_for_match(summary.model_dump(mode="json"))
        
        return {
            "matchId": match.id,
            **theme_data,
        }

    @router.get("/api/search/tactical-themes")
    def list_tactical_themes() -> dict:
        """List available tactical themes for search.
        
        Returns:
            Dictionary of available tactical themes with descriptions
        """
        from .semantic_search import TACTICAL_KEYWORDS
        
        theme_descriptions = {
            "high_press": "Aggressive pressing in the opponent's half, often triggering counter-attacks",
            "low_block": "Deep defensive shape, compact and organized around the penalty area",
            "mid_block": "Balanced defensive shape in the middle third",
            "counter_attack": "Fast transitions after winning possession, bypassing midfield",
            "possession_based": "High possession, patient build-up play from the back",
            "direct_play": "Long balls and vertical passing to bypass midfield",
            "wing_play": "Attacks through the flanks with crosses from wide positions",
            "through_balls": "Vertical passes breaking the defensive line",
            "defensive_transition": "Regaining defensive shape after losing possession",
            "offensive_transition": "Quick attack after winning possession high up",
            "deep_defense": "Very low defensive line, protecting the goal closely",
            "aggressive_press": "Intense man-to-man pressing, hunting in groups",
            "passive_press": "Soft containment, waiting for the opponent to make mistakes",
        }
        
        return {
            "themes": [
                {
                    "id": theme_id,
                    "description": theme_descriptions.get(theme_id, ""),
                    "keywords": TACTICAL_KEYWORDS.get(theme_id, [])[:5],  # Top 5 keywords
                }
                for theme_id in TACTICAL_KEYWORDS
            ]
        }

    return router
