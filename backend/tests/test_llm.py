from backend.app.llm import build_prompt
from backend.app.schemas import DetectedEvent, MatchSummary, ShotAnalytics


def test_tactical_report_prompt_uses_derived_summary_and_events():
    summary = MatchSummary(
        possession=61,
        myTeamDistance=1042,
        enemyDistance=980,
        myTeamAvgPos={"x": 57.4, "y": 48.1},
        enemyAvgPos={"x": 43.2, "y": 50.3},
        myTeamTopSpeed=31.4,
        enemyTopSpeed=29.1,
        myTeamSprints=12,
        enemySprints=9,
        formation="4-3-3",
    )
    events = [
        DetectedEvent(type="pass", frameId=1, timestamp=0.2, team="my_team", fromTrackId=7, toTrackId=11, description="7 pass to 11"),
        DetectedEvent(type="pass", frameId=2, timestamp=0.4, team="my_team", fromTrackId=11, toTrackId=9, description="11 pass to 9"),
        DetectedEvent(type="shot", frameId=3, timestamp=0.6, team="my_team", fromTrackId=9, toTrackId=None, description="9 shot"),
        DetectedEvent(type="turnover", frameId=4, timestamp=0.8, team="enemy", fromTrackId=None, toTrackId=18, description="enemy turnover"),
    ]

    prompt = build_prompt("tactical_report", [], summary=summary, events=events)

    assert "formation" in prompt
    assert "4-3-3" in prompt
    assert '"pass": 2' in prompt
    assert '"shot": 1' in prompt
    assert '"turnover": 1' in prompt
    assert "trackId" in prompt
    assert "7" in prompt


def test_tactical_report_prompt_includes_player_focus_and_match_signals():
    summary = MatchSummary(
        possession=61,
        myTeamDistance=1042,
        enemyDistance=980,
        myTeamAvgPos={"x": 57.4, "y": 48.1},
        enemyAvgPos={"x": 43.2, "y": 50.3},
        myTeamTopSpeed=31.4,
        enemyTopSpeed=29.1,
        myTeamSprints=12,
        enemySprints=9,
        myTeamXg=1.22,
        enemyXg=0.48,
        myTeamDefensiveLineHeight=24,
        enemyDefensiveLineHeight=30,
        myTeamDefensiveTeamLength=37,
        enemyDefensiveTeamLength=42,
        myTeamPpda=6.1,
        enemyPpda=8.4,
        myTeamHighPressRegains=4,
        enemyHighPressRegains=1,
        myTeamCounterpressRecoverySeconds=3.2,
        enemyCounterpressRecoverySeconds=5.1,
        formation="4-3-3",
    )
    events = [
        DetectedEvent(type="through_ball", frameId=2, timestamp=0.4, team="my_team", fromTrackId=7, toTrackId=9, description="7 through ball to 9"),
        DetectedEvent(type="shot", frameId=3, timestamp=0.6, team="my_team", fromTrackId=9, description="9 shot"),
        DetectedEvent(type="interception", frameId=4, timestamp=0.8, team="enemy", toTrackId=18, description="18 interception"),
    ]
    shots = [
        ShotAnalytics(frameId=3, timestamp=0.6, team="my_team", playerId=9, x=90, y=50, inBox=True, xg=0.38, distanceToGoal=10.0, angleDegrees=30.0),
    ]

    prompt = build_prompt("tactical_report", [], summary=summary, events=events, shots=shots)

    assert "playerFocus" in prompt
    assert "matchSignals" in prompt
    assert "topCreator" in prompt
    assert "topFinisher" in prompt
    assert "topBallWinner" in prompt
    assert "through_ball" in prompt
    assert "0.38" in prompt


def test_drills_prompt_includes_player_focus_and_contextual_signals():
    summary = MatchSummary(
        possession=54,
        myTeamDistance=1005,
        enemyDistance=1010,
        myTeamAvgPos={"x": 53.0, "y": 49.1},
        enemyAvgPos={"x": 47.8, "y": 49.6},
        myTeamTopSpeed=30.0,
        enemyTopSpeed=29.0,
        myTeamSprints=10,
        enemySprints=11,
        myTeamXg=0.84,
        enemyXg=0.65,
        myTeamDefensiveLineHeight=22,
        enemyDefensiveLineHeight=28,
        myTeamDefensiveTeamLength=36,
        enemyDefensiveTeamLength=40,
        myTeamPpda=7.2,
        enemyPpda=8.1,
        myTeamHighPressRegains=3,
        enemyHighPressRegains=2,
        myTeamCounterpressRecoverySeconds=3.8,
        enemyCounterpressRecoverySeconds=4.9,
        formation="4-2-3-1",
    )
    events = [
        DetectedEvent(type="pass", frameId=1, timestamp=0.2, team="my_team", fromTrackId=6, toTrackId=10, description="6 pass to 10"),
        DetectedEvent(type="shot", frameId=2, timestamp=0.4, team="my_team", fromTrackId=10, description="10 shot"),
    ]
    shots = [
        ShotAnalytics(frameId=2, timestamp=0.4, team="my_team", playerId=10, x=88, y=52, inBox=True, xg=0.27, distanceToGoal=12.0, angleDegrees=24.0),
    ]

    prompt = build_prompt("drills", [], summary=summary, events=events, shots=shots)

    assert "playerFocus" in prompt
    assert "matchSignals" in prompt
    assert '"focus_area"' in prompt
