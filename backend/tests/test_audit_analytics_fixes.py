"""Behavioral regressions for the September code audit."""
import pytest
import lap
from backend.app.analytics import assign_ball_possession, summarize_match
from backend.app.processor import _compute_outputs_and_match_state
from backend.app.schemas import BallData, FrameData, PlayerData
from backend.app.semantic_search import _parse_nl_query, search_matches_by_tactical_themes
from backend.app.team_classification import ColorClusterResult, classify_player_row_by_cluster


def test_lap_partial_assignment_does_not_lose_cheap_match():
    total, x, y = lap.lapjv([[.1, .51], [.51, 1]], cost_limit=.5)
    assert total == pytest.approx(.1)
    assert x.tolist() == y.tolist() == [0, -1]
    total, x, y = lap.lapjv([[.1, .51, .8], [.51, 1, .9]], cost_limit=.5)
    assert x.tolist() == [0, -1]
    assert y.tolist() == [0, -1, -1]


def test_right_to_left_preserves_mirrored_shots_and_display_coordinates():
    outputs = []
    for x, direction in [(90, 'left_to_right'), (10, 'right_to_left')]:
        frames = [FrameData(frameId=0, timestamp=0, ball=BallData(x=x,y=50), myTeam=[PlayerData(id=1,x=x,y=50)]), FrameData(frameId=1,timestamp=.2,myTeam=[PlayerData(id=1,x=x,y=50)])]
        result = _compute_outputs_and_match_state(frames, attack_direction=direction)
        enriched, summary, events, _, _, shots, _ = result
        assert [event.type for event in events] == ['shot']
        assert shots[0].x == x
        assert enriched[0].myTeam[0].x == x
        assert summary.myTeamAvgPos['x'] == x
        outputs.append(shots[0].xg)
    assert outputs == [.71, .71]


@pytest.mark.parametrize('hz', [5,10])
def test_continuous_run_counts_one_sprint_independent_of_sample_rate(hz):
    frames=[FrameData(frameId=i,timestamp=i/hz,myTeam=[PlayerData(id=1,x=10+8*(i/hz)/1.05,y=50)]) for i in range(hz*2+1)]
    result=summarize_match(frames,assign_ball_possession(frames), identity_continuous=True)
    assert result.myTeamSprints == 1
    assert result.myTeamDistance == 16
    # A missing observation ends the sprint rather than linking across the gap.
    frames[hz] = frames[hz].model_copy(update={'myTeam': []})
    assert summarize_match(frames,assign_ball_possession(frames), identity_continuous=True).myTeamSprints == 2


def test_unknown_team_remains_unassigned_and_competes_for_possession():
    clusters=ColorClusterResult(trackToCluster={1:0,2:1},clusters=[])
    assert classify_player_row_by_cluster({'Entity_Type':'player','Track_ID':99},clusters,0)['Entity_Type']=='player'
    frame=FrameData(frameId=0,timestamp=0,ball=BallData(x=50,y=50),myTeam=[PlayerData(id=1,x=55,y=50)],unassignedPlayers=[PlayerData(id=99,x=50,y=50)])
    owner=assign_ball_possession([frame])[0]
    assert (owner.team,owner.trackId)==('unassigned',99)


def test_ppda_search_and_negation_follow_metrics_and_query_order():
    matches=[{'matchId':str(p),'summary':{'myTeamPpda':p}} for p in [0,5,20]]
    found=search_matches_by_tactical_themes('high press',matches)
    assert found[0]['matchId']=='5'
    assert all(item['matchId']!='0' for item in found)
    assert _parse_nl_query('high press without low block') == (['high_press'],['low_block'])
    assert _parse_nl_query('without wing play') == ([],['wing_play'])
    assert _parse_nl_query('noteworthy high press') == (['high_press'],[])
    excluded=search_matches_by_tactical_themes('high press without low block',[{'matchId':'low','summary':{'myTeamPpda':5,'myTeamBlockHeight':'low_block'}}])
    assert excluded == []


def test_unmeasured_possession_does_not_claim_high_possession_in_search():
    matches = [{"matchId": "unknown", "matchName": "Unresolved Teams", "summary": {"possession": None}}]
    assert search_matches_by_tactical_themes("high possession", matches) == []


def test_mixed_search_does_not_claim_possession_from_the_query_alone():
    matches = [{"matchId": "unknown", "matchName": "Pressing Only", "summary": {"possession": None, "myTeamPpda": 5}}]
    result = search_matches_by_tactical_themes("high possession and high press", matches)
    assert len(result) == 1
    assert "high_press" in result[0]["matchedThemes"]
    assert "possession_based" not in result[0]["matchedThemes"]
    assert "Possession Based" not in result[0]["summary"]


@pytest.mark.parametrize('input_mode', ['tracking_json', 'video'])
def test_processing_and_reprocessing_apply_direction_to_saved_outputs(tmp_path, input_mode):
    import json
    from backend.app.processor import process_match, persist_remote_video_result, reprocess_video_match
    from backend.app.storage import Storage
    from backend.app.schemas import MatchConfig
    rows=[{'Frame_ID':i,'Timestamp':i*.2,'Entity_Type':'my_team','Track_ID':1,'X':10,'Y':50,'Conf':1} for i in range(2)]
    rows.append({'Frame_ID':0,'Timestamp':0,'Entity_Type':'ball','Track_ID':-1,'X':10,'Y':50,'Conf':1})
    source=tmp_path/'source.json'
    source.write_text(json.dumps(rows))
    storage=Storage(tmp_path/'storage')
    match=storage.create_match(name='direction', input_mode=input_mode, original_filename=source.name, input_path=source,config=MatchConfig(attackDirection='right_to_left'))
    job=storage.create_job(match.id)
    if input_mode=='tracking_json':
        process_match(storage,job.id)
    else:
        persist_remote_video_result(storage,job.id,{'rows':rows})
    summary,_,_,shots=storage.load_analytics(match.id)
    assert summary.myTeamXg==.71
    assert shots[0].x==10
    assert storage.load_frames(match.id)[0].myTeam[0].x==10
    reprocess_video_match(storage,match.id,config=MatchConfig(attackDirection='left_to_right'))
    summary,_,_,shots=storage.load_analytics(match.id)
    assert summary.myTeamXg is None
    assert shots==[]
    assert storage.load_frames(match.id)[0].myTeam[0].x==10


def test_direction_mirrors_defensive_shape_pressing_and_formation():
    from dataclasses import replace
    from backend.app.schemas import BallOwnership, DetectedEvent
    frames=[FrameData(frameId=0,timestamp=0, myTeam=[PlayerData(id=i,x=x,y=50) for i,x in enumerate([5,25,25,25,25,60])],enemies=[PlayerData(id=20,x=65,y=50)])]
    ownership=[BallOwnership(frameId=0,timestamp=0,team='enemy',trackId=20)]
    events=[DetectedEvent(type='pass',frameId=0,timestamp=0,team='enemy',fromTrackId=20,toTrackId=20,description='pass'),DetectedEvent(type='recovery',frameId=0,timestamp=0,team='my_team',toTrackId=5,description='recovery')]
    mirrored=[frame.model_copy(update={field:[replace(p,x=100-p.x) for p in getattr(frame,field)] for field in ['myTeam','enemies']}) for frame in frames]
    forward=summarize_match(frames,ownership,events=events)
    reverse=summarize_match(mirrored,ownership,events=events,attack_direction='right_to_left')
    for field in ['formation','myTeamDefensiveLineHeight','myTeamDefensiveTeamLength','myTeamPpda','myTeamHighPressRegains','myTeamRegainZones','myTeamBlockHeight']:
        assert getattr(reverse,field)==getattr(forward,field)
    assert forward.myTeamHighPressRegains==1
    assert forward.myTeamPpda==1
