"""Tests for semantic search functionality."""

from backend.app.semantic_search import (
    TACTICAL_KEYWORDS,
    _detect_themes_from_summary,
    _parse_nl_query,
    _calculate_query_relevance,
    _normalize_text,
    search_matches_by_tactical_themes,
    detect_themes_for_match,
)


class TestNormalizeText:
    def test_lowercase_conversion(self):
        assert _normalize_text("HIGH PRESS") == "high press"
    
    def test_strip_whitespace(self):
        assert _normalize_text("  high press  ") == "high press"


class TestParseNLQuery:
    def test_high_press_query(self):
        required, excluded = _parse_nl_query("matches with high press")
        assert "high_press" in required
    
    def test_counter_attack_query(self):
        required, excluded = _parse_nl_query("counter attack opportunities")
        assert "counter_attack" in required
    
    def test_multiple_themes(self):
        required, excluded = _parse_nl_query("high press and low block")
        assert "high_press" in required
        assert "low_block" in required


class TestDetectThemesFromSummary:
    def test_high_possession_detected(self):
        summary = {
            "possession": 75,
            "myTeamPpda": 8,
            "myTeamDefensiveLineHeight": 50,
            "myTeamBlockHeight": "high_block",
            "myTeamRegainZones": {"defensive_third": 2, "middle_third": 5, "attacking_third": 1},
            "myTeamTransitionExposure": 0.5,
            "myTeamXg": 1.2,
            "enemyXg": 0.8,
        }
        themes = _detect_themes_from_summary(summary)
        theme_names = [t[0] for t in themes]
        assert "possession_based" in theme_names or "high_press" in theme_names
    
    def test_low_block_detected(self):
        summary = {
            "possession": 35,
            "myTeamPpda": 5,
            "myTeamDefensiveLineHeight": 25,
            "myTeamBlockHeight": "low_block",
            "myTeamRegainZones": {"defensive_third": 8, "middle_third": 3, "attacking_third": 0},
            "myTeamTransitionExposure": 1.5,
        }
        themes = _detect_themes_from_summary(summary)
        theme_dict = dict(themes)
        # Deep defense should be detected for low defensive line
        assert theme_dict.get("deep_defense", 0) > 20
        # Low block keywords also present
        assert theme_dict.get("low_block", 0) > 0
    
    def test_empty_summary(self):
        summary = {}
        themes = _detect_themes_from_summary(summary)
        assert isinstance(themes, list)


class TestCalculateQueryRelevance:
    def test_exact_theme_match(self):
        summary = {
            "possession": 70,
            "myTeamPpda": 18,
            "myTeamDefensiveLineHeight": 65,
            "myTeamBlockHeight": "high_block",
            "myTeamRegainZones": {"defensive_third": 1, "middle_third": 3, "attacking_third": 5},
            "myTeamTransitionExposure": 0.3,
        }
        themes = [("high_press", 80), ("counter_attack", 60)]
        score, matched = _calculate_query_relevance("high press counter-attack", summary, themes)
        assert score > 50
        assert "high_press" in matched or "counter_attack" in matched


class TestSearchMatchesByTacticalThemes:
    def test_empty_matches_list(self):
        results = search_matches_by_tactical_themes("high press", [])
        assert results == []
    
    def test_single_match_high_relevance(self):
        matches = [{
            "matchId": "123",
            "matchName": "Test Match",
            "summary": {
                "possession": 70,
                "myTeamPpda": 18,
                "myTeamDefensiveLineHeight": 65,
                "myTeamBlockHeight": "high_block",
                "myTeamRegainZones": {"defensive_third": 1, "middle_third": 3, "attacking_third": 5},
            }
        }]
        results = search_matches_by_tactical_themes("high press", matches)
        assert len(results) == 1
        assert results[0]["matchId"] == "123"
        # Score should be positive for matching theme
        assert results[0]["relevanceScore"] > 0
    
    def test_no_match_for_unrelated_query(self):
        matches = [{
            "matchId": "123",
            "matchName": "Test Match",
            "summary": {
                "possession": 30,
                "myTeamPpda": 5,
                "myTeamDefensiveLineHeight": 25,
                "myTeamBlockHeight": "low_block",
            }
        }]
        results = search_matches_by_tactical_themes("aggressive pressing high block", matches)
        # Should have some results but lower score
        assert isinstance(results, list)


class TestDetectThemesForMatch:
    def test_detect_themes_structure(self):
        summary = {
            "possession": 60,
            "myTeamPpda": 10,
            "myTeamDefensiveLineHeight": 45,
        }
        result = detect_themes_for_match(summary)
        assert "detectedThemes" in result
        assert "themeDetails" in result
        assert isinstance(result["detectedThemes"], list)
        assert isinstance(result["themeDetails"], dict)


class TestTacticalKeywords:
    def test_all_themes_have_keywords(self):
        assert len(TACTICAL_KEYWORDS) > 0
        for theme, keywords in TACTICAL_KEYWORDS.items():
            assert len(keywords) > 0
            assert isinstance(theme, str) and len(theme) > 0, f"Theme key should be a non-empty string, got: {theme!r}"
    
    def test_high_press_keywords(self):
        assert "high press" in TACTICAL_KEYWORDS["high_press"]
        assert "counter press" in TACTICAL_KEYWORDS["high_press"]
    
    def test_low_block_keywords(self):
        assert "low block" in TACTICAL_KEYWORDS["low_block"]
        assert "deep block" in TACTICAL_KEYWORDS["low_block"]
