from __future__ import annotations

import re

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import ReviewBundle


# Tactical theme keywords mapping
TACTICAL_KEYWORDS = {
    "high_press": [
        "high press", "high pressing", "aggressive press", "pressing high",
        "counter press", "counterpress", "win ball high", "press high",
        "force turnovers", "early press", "intense pressing", "high block",
        "pressing trigger", "gegenpress"
    ],
    "low_block": [
        "low block", "low defensive block", "deep block", "deep defensive",
        "defend deep", "sit back", "low line", "compact block",
        "defensive shape", "organized defense", "low press"
    ],
    "mid_block": [
        "mid block", "middle block", "medium block", "balanced block",
        "moderate press", "balanced defense", "midfield press"
    ],
    "counter_attack": [
        "counter attack", "counter-attack", "counterattack", "fast break",
        "quick transition", "explosive counter", "hit on break",
        "direct counter", "quick transitions", "fast counter"
    ],
    "possession_based": [
        "possession", "keep ball", "keep possession", "patient build-up",
        "build from back", "dominate possession", "ball retention",
        "high possession", "control the game"
    ],
    "direct_play": [
        "direct play", "long ball", "direct", "long passes",
        "vertical passing", "quick ball forward", "bypass midfield",
        "route one", "direct approach"
    ],
    "wing_play": [
        "wing play", "flank play", "wide play", "wings",
        "cross from wide", "width creation", "asymmetric play",
        "overlap", "underlap", "wide overload"
    ],
    "through_balls": [
        "through ball", "through balls", "split pass", "vertical ball",
        "killer pass", "breaking lines", "line-breaking pass",
        "passes in behind", "in-behind"
    ],
    "defensive_transition": [
        "lose ball", "lose possession", "turnover", "transitional defense",
        "recover position", "defensive transition", "regain shape",
        "compact after losing ball"
    ],
    "offensive_transition": [
        "win ball", "gain possession", "offensive transition", "attack after winning",
        "transition to attack", "quick recovery", "turnover to attack"
    ],
    "deep_defense": [
        "deep defense", "defensive third", "protect goal", "drop deep",
        "narrow defense", "compact shape", "low defensive line"
    ],
    "aggressive_press": [
        "aggressive press", "intense press", "heavy press", "man-to-man press",
        "hunt in groups", "aggressive pressure", "high intensity press"
    ],
    "passive_press": [
        "passive press", "soft press", "containment", "wait and press",
        "low intensity", "passive defense", "controlled press"
    ],
}


def _normalize_text(text: str) -> str:
    """Normalize text for keyword matching."""
    return text.lower().strip()


def _score_theme_match(text: str, keywords: list[str]) -> float:
    """Score how well text matches a theme's keywords."""
    normalized = _normalize_text(text)
    matches = sum(1 for kw in keywords if kw in normalized)
    if matches == 0:
        return 0.0
    # Score based on number of keyword matches
    return min(matches / len(keywords) * 100, 100.0)


def _detect_themes_from_summary(summary: dict) -> list[tuple[str, float]]:
    """Detect tactical themes from match summary data.
    
    Returns list of (theme, score) tuples sorted by score descending.
    """
    theme_scores: dict[str, float] = {}
    
    # Build searchable text from summary
    summary_text_parts = []
    
    # Key metrics
    possession = summary.get("possession")
    if possession is not None:
        summary_text_parts.append(f"possession {possession} percent")
    
    ppda_my = summary.get("myTeamPpda", 0)
    if 0 < ppda_my < 8:
        summary_text_parts.append("high press aggressive press ppda")
    elif ppda_my > 15:
        summary_text_parts.append("low press passive press ppda")
    
    # Defensive line height
    def_line = summary.get("myTeamDefensiveLineHeight", 50)
    if def_line > 60:
        summary_text_parts.append("high defensive line high block")
    elif def_line < 40:
        summary_text_parts.append("low defensive line deep defense low block")
    
    # Block height
    block_height = summary.get("myTeamBlockHeight", "mid_block")
    summary_text_parts.append(block_height.replace("_", " "))
    
    # Regain zones
    regain_zones = summary.get("myTeamRegainZones", {})
    if regain_zones.get("attacking_third", 0) > 3:
        summary_text_parts.append("high press win ball in attacking third")
    if regain_zones.get("defensive_third", 0) > 5:
        summary_text_parts.append("deep defense low block regain in defensive third")
    
    # Transition exposure
    trans_exp = summary.get("myTeamTransitionExposure", 0)
    if trans_exp > 2:
        summary_text_parts.append("vulnerable transition")
    elif trans_exp < 1:
        summary_text_parts.append("solid transition")
    
    # xG
    xg_my = summary.get("myTeamXg", 0)
    xg_enemy = summary.get("enemyXg", 0)
    if xg_my > xg_enemy * 1.5:
        summary_text_parts.append("dominant attack high quality chances")
    
    summary_text = " ".join(summary_text_parts)
    
    # Score each theme
    for theme, keywords in TACTICAL_KEYWORDS.items():
        score = _score_theme_match(summary_text, keywords)
        if score > 0:
            theme_scores[theme] = score
    
    return sorted(theme_scores.items(), key=lambda x: -x[1])


def _parse_nl_query(query: str) -> tuple[list[str], list[str]]:
    """Parse natural language query into positive and negative theme requirements.
    
    Returns (required_themes, excluded_themes).
    """
    required: list[str] = []
    excluded: list[str] = []
    negative = False
    # ponytail: explicit clause negation; use a parser if richer grammar is required.
    parts = re.split(r"\b(without|not|no|avoid|exclude|don't|dont|but|with)\b|([,;.!])", _normalize_text(query))
    for part in filter(None, parts):
        if part in {"without", "not", "no", "avoid", "exclude", "don't", "dont"}:
            negative = True
            continue
        if part in {"but", "with", ",", ";", ".", "!"}:
            negative = False
            continue
        target = excluded if negative else required
        for theme, keywords in TACTICAL_KEYWORDS.items():
            if theme not in target and any(re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", part) for kw in keywords):
                target.append(theme)
    return required, excluded


def _calculate_query_relevance(
    query: str,
    summary: dict,
    detected_themes: list[tuple[str, float]],
) -> tuple[float, list[str]]:
    """Calculate relevance score for a match based on query.
    
    Returns (score, matched_themes).
    """
    query_lower = _normalize_text(query)
    matched_themes = []
    
    # Parse query requirements
    required_themes, excluded_themes = _parse_nl_query(query)
    if summary.get("possession") is None:
        required_themes = [theme for theme in required_themes if theme != "possession_based"]
    
    # Check for explicit theme mentions
    explicit_theme_matches = 0
    for theme in required_themes:
        if theme not in excluded_themes:
            explicit_theme_matches += 1
            if theme not in matched_themes:
                matched_themes.append(theme)
    
    # Calculate theme-based score
    theme_score = 0.0
    detected_dict = dict(detected_themes)
    
    for theme in required_themes:
        if theme in excluded_themes:
            continue
        score = detected_dict.get(theme, 0)
        if score > 30:  # Threshold for match
            theme_score += score * 0.5
        elif score > 0:
            theme_score += score * 0.2  # Partial credit
        else:
            theme_score -= 20  # Penalty for missing required theme
    
    for theme in excluded_themes:
        if detected_dict.get(theme, 0) > 0:
            theme_score -= 30  # Penalty for excluded theme present
    
    # Boost for explicit theme mentions in query
    base_score = explicit_theme_matches * 15
    if excluded_themes and not required_themes:
        base_score = 25
    
    # Mention of possession
    if "possession" in query_lower:
        possession = summary.get("possession")
        if possession is not None and "high" in query_lower and possession > 60:
            base_score += 20
        elif possession is not None and "low" in query_lower and possession < 40:
            base_score += 20
    
    # Mention of press/pressing
    if "press" in query_lower:
        ppda = summary.get("myTeamPpda", 10)
        if "aggressive" in query_lower or "high" in query_lower:
            if 0 < ppda < 8:
                base_score += 20
        elif "low" in query_lower or "passive" in query_lower:
            if ppda > 15:
                base_score += 20
    
    final_score = min(100.0, max(0.0, base_score + theme_score))
    return round(final_score, 1), matched_themes


def _generate_match_summary_text(summary: dict, matched_themes: list[str]) -> str:
    """Generate a brief summary explaining why this match matched."""
    parts = []
    
    possession = summary.get("possession")
    if possession is not None and possession > 65:
        parts.append(f"High possession ({possession}%)")
    elif possession is not None and possession < 35:
        parts.append(f"Low possession ({possession}%)")
    
    block = summary.get("myTeamBlockHeight", "mid_block")
    if block:
        parts.append(f"{block.replace('_', ' ')}")
    
    ppda = summary.get("myTeamPpda", 0)
    if ppda > 15:
        parts.append(f"High PPDA ({ppda}) - passive approach")
    elif 0 < ppda < 8:
        parts.append(f"Low PPDA ({ppda}) - aggressive press")
    
    if matched_themes:
        theme_names = [t.replace("_", " ").title() for t in matched_themes[:3]]
        if theme_names:
            parts.append(f"Themes: {', '.join(theme_names)}")
    
    return " | ".join(parts) if parts else "Standard tactical match profile"


def search_matches_by_tactical_themes(
    query: str,
    matches_data: list[dict],
    detected_themes_per_match: dict[str, list[tuple[str, float]]] | None = None,
) -> list[dict]:
    """Search matches by tactical themes using natural language query.
    
    Args:
        query: Natural language search query
        matches_data: List of dicts with 'matchId', 'matchName', 'summary'
        detected_themes_per_match: Optional pre-computed themes per match
    
    Returns:
        List of result dicts sorted by relevance score
    """
    results = []
    
    # Parse query requirements
    required_themes, excluded_themes = _parse_nl_query(query)
    
    for match_data in matches_data:
        match_id = match_data.get("matchId", "")
        match_name = match_data.get("matchName", "")
        summary = match_data.get("summary", {})
        
        # Get or compute detected themes
        if detected_themes_per_match and match_id in detected_themes_per_match:
            detected_themes = detected_themes_per_match[match_id]
        else:
            detected_themes = _detect_themes_from_summary(summary)
        
        detected_dict = dict(detected_themes)
        
        # Check exclusions first
        excluded_match = False
        for theme in excluded_themes:
            if detected_dict.get(theme, 0) > 0:
                excluded_match = True
                break
        
        if excluded_match:
            continue
        
        # Calculate relevance
        score, matched_themes = _calculate_query_relevance(query, summary, detected_themes)
        
        # Apply query-specific scoring
        for theme in required_themes:
            if detected_dict.get(theme, 0) > 30:
                score = min(100, score + 10)  # Boost for required theme
        
        if score < 10:  # Minimum threshold
            continue
        
        # Build matched themes list
        all_matched = list(matched_themes)
        for theme, theme_score in detected_themes[:3]:
            if theme_score > 50 and theme not in all_matched:
                all_matched.append(theme)
        
        results.append({
            "matchId": match_id,
            "matchName": match_name,
            "relevanceScore": score,
            "matchedThemes": all_matched[:5],
            "summary": _generate_match_summary_text(summary, all_matched),
            "summaryData": summary,
        })
    
    # Sort by relevance score descending
    results.sort(key=lambda x: -x["relevanceScore"])
    return results


def search_bundles_by_tactical_themes(
    query: str,
    bundles: list[ReviewBundle],
) -> list[dict]:
    """Search bundles by tactical themes.
    
    Args:
        query: Natural language search query
        bundles: List of ReviewBundle objects
    
    Returns:
        List of result dicts sorted by relevance
    """
    results = []
    required_themes, excluded_themes = _parse_nl_query(query)
    query_lower = _normalize_text(query)
    
    for bundle in bundles:
        score = 0.0
        matched_themes = []
        
        # Check tags for theme matches
        bundle_text = " ".join([
            bundle.name.lower(),
            bundle.description.lower(),
            " ".join(bundle.tags)
        ])
        
        for theme, keywords in TACTICAL_KEYWORDS.items():
            if any(kw in bundle_text for kw in keywords):
                matched_themes.append(theme)
                score += 15
        
        # Check if query terms appear in bundle
        for word in query_lower.split():
            if len(word) > 3 and word in bundle_text:
                score += 5
        
        # An excluded theme is a filter, not a small ranking penalty.
        if any(theme in matched_themes for theme in excluded_themes):
            continue
        if excluded_themes and not required_themes:
            score = max(score, 25)
        
        if score < 5:
            continue
        
        results.append({
            "bundleId": bundle.id,
            "bundleName": bundle.name,
            "relevanceScore": min(100, score),
            "matchedThemes": matched_themes[:5],
            "itemCount": len(bundle.items),
            "description": bundle.description,
        })
    
    results.sort(key=lambda x: -x["relevanceScore"])
    return results


def detect_themes_for_match(summary: dict) -> dict:
    """Detect all tactical themes for a match.
    
    Returns dict with 'detectedThemes' and 'themeDetails'.
    """
    themes = _detect_themes_from_summary(summary)
    detected = [theme for theme, score in themes if score > 20]
    details = {theme: round(score, 1) for theme, score in themes}
    
    return {
        "detectedThemes": detected,
        "themeDetails": details,
    }
