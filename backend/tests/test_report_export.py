from datetime import datetime, timezone

from backend.app.report_export import build_match_report_export, render_match_report_html
from backend.app.schemas import DetectedEvent, MatchConfig, MatchRecord, MatchSummary


def test_render_report_html_includes_core_match_sections():
    html = render_match_report_html(
        match_name="Sample Match",
        input_mode="tracking_json",
        exported_at="2026-03-28T00:00:00+00:00",
        summary={
            "possession": 67,
            "myTeamXg": 1.24,
            "enemyXg": 0.48,
            "formation": "4-3-3",
            "myTeamPpda": 7.1,
            "enemyPpda": 11.3,
            "myTeamDefensiveLineHeight": 24.5,
            "enemyDefensiveLineHeight": 19.8,
            "myTeamHighPressRegains": 4,
            "enemyHighPressRegains": 1,
            "myTeamCounterpressRecoverySeconds": 3.4,
            "enemyCounterpressRecoverySeconds": 5.6,
        },
        formation_timeline=[
            {"formation": "4-3-3", "startTimestamp": 0.0, "endTimestamp": 14.0},
        ],
        event_summary={"eventCounts": {"pass": 18, "shot": 4}},
        tactical_report={
            "summary": "Positive attacking output",
            "rating": 8,
            "attacking": "Strong wide play",
        },
        drills={
            "focus_area": "Rest defense",
            "drills": [
                {
                    "name": "Wave Press",
                    "objective": "Recover quickly",
                    "setup": "6v4",
                    "duration": "12 min",
                }
            ],
        },
    )

    assert "Sample Match" in html
    assert "Positive attacking output" in html
    assert "Wave Press" in html
    assert "4-3-3" in html
    assert "67%" in html


def test_render_report_html_shows_fallback_when_no_coach_outputs_exist():
    html = render_match_report_html(
        match_name="Sample Match",
        input_mode="tracking_json",
        exported_at="2026-03-28T00:00:00+00:00",
        summary={"possession": 51, "myTeamXg": 0.8, "enemyXg": 0.7, "formation": "4-4-2"},
        formation_timeline=[],
        event_summary={"eventCounts": {"turnover": 3}},
        tactical_report=None,
        drills=None,
    )

    assert "Coach report not generated yet" in html
    assert "Training drills not generated yet" in html


def test_report_with_unknown_possession_does_not_repeat_cached_tactical_claims():
    html = render_match_report_html(
        match_name="Unresolved Teams", input_mode="video", exported_at="2026-09-15T00:00:00Z",
        summary={"possession": None, "myTeamXg": 0, "enemyXg": 0, "formation": "-"},
        formation_timeline=[], event_summary={"eventCounts": {}},
        tactical_report={"summary": "We controlled 50% possession", "attacking": "Dominant team"},
        drills=None,
    )
    assert "50% possession" not in html
    assert "Dominant team" not in html
    assert "Possession was not measured" in html
    assert "Data Confidence" in html


def test_render_report_html_labels_low_confidence_ball_data():
    html = render_match_report_html(
        match_name="Low Confidence Match",
        input_mode="video",
        exported_at="2026-04-11T00:00:00+00:00",
        summary={
            "possession": 50,
            "myTeamXg": 0.0,
            "enemyXg": 0.0,
            "formation": "-",
            "ballSignalStatus": "untrusted",
            "ballSignalMessage": "Ball coverage too low for tactical interpretation.",
            "truthGateReasons": ["Need withBallFrames/frameCount >= 25% for truthful 5-10 minute analysis"],
        },
        formation_timeline=[],
        event_summary={"eventCounts": {}},
        tactical_report={"summary": "Review-only tactical report."},
        drills=None,
    )

    assert "Data Confidence" in html
    assert "Ball coverage too low for tactical interpretation." in html
    assert "Need withBallFrames/frameCount &gt;= 25% for truthful 5-10 minute analysis" in html


def test_render_report_html_does_not_publish_unknown_ppda_as_zero():
    html = render_match_report_html(
        match_name="Unknown PPDA",
        input_mode="video",
        exported_at="2026-09-16T00:00:00+00:00",
        summary={
            "possession": 50,
            "myTeamXg": 0.42,
            "enemyXg": 0.0,
            "formation": "4-3-3",
            "myTeamPpda": 0.0,
            "enemyPpda": 0.0,
            "metricAvailability": [
                {
                    "metric": "my_team_ppda",
                    "availability": "unknown",
                    "value": None,
                    "reasonCodes": ["ZERO_DENOMINATOR"],
                },
                {
                    "metric": "enemy_ppda",
                    "availability": "unknown",
                    "value": None,
                    "reasonCodes": ["ZERO_DENOMINATOR"],
                },
                {
                    "metric": "experimental_shot_quality",
                    "availability": "experimental",
                    "value": 0.42,
                    "publishedLabel": "experimental_shot_quality",
                },
            ],
        },
        formation_timeline=[],
        event_summary={"eventCounts": {}},
        tactical_report=None,
        drills=None,
    )

    assert "Unavailable" in html
    assert "experimental shot quality" in html.lower()
    assert "My Team PPDA" in html
    assert ">0.0<" not in html.replace("0.42", "SHOT")


def _sample_match() -> MatchRecord:
    now = datetime.now(timezone.utc)
    return MatchRecord(
        id="match-1",
        name="Grounded Match",
        inputMode="video",
        status="ready",
        originalFilename="clip.mp4",
        config=MatchConfig(),
        createdAt=now,
        updatedAt=now,
    )


def _sample_summary() -> MatchSummary:
    return MatchSummary(
        possession=55,
        myTeamDistance=0,
        enemyDistance=0,
        myTeamAvgPos={"x": 50.0, "y": 50.0},
        enemyAvgPos={"x": 50.0, "y": 50.0},
        myTeamTopSpeed=0.0,
        enemyTopSpeed=0.0,
        myTeamSprints=0,
        enemySprints=0,
        formation="4-3-3",
    )


def test_build_match_report_export_does_not_imply_whole_match_frequency() -> None:
    html = build_match_report_export(
        match=_sample_match(),
        summary=_sample_summary(),
        formation_timeline=[],
        shots=[],
        events=[
            DetectedEvent(type="shot", frameId=12, timestamp=4.0, description="Reviewed shot in box"),
        ],
        tactical_report={"summary": "Three reviewed passages created chances.", "evidence": ["Reviewed shot in box"]},
        drills=None,
    )
    assert "do not establish a whole-match frequency" in html.lower()
    assert 'data-whole-match-frequency="false"' in html


def test_build_match_report_export_rejects_fabricated_evidence_from_publication() -> None:
    html = build_match_report_export(
        match=_sample_match(),
        summary=_sample_summary(),
        formation_timeline=[],
        shots=[],
        events=[
            DetectedEvent(type="pass", frameId=3, timestamp=1.0, description="Observed pass"),
        ],
        tactical_report={"summary": "Invented dominance from missing clip", "evidence": ["not-a-real-evidence-id"]},
        drills=None,
    )
    assert "Invented dominance from missing clip" not in html
    assert "Coach report not generated yet" in html

