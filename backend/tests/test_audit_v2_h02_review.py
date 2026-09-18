from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.app.processor import reprocess_video_match
from backend.app.schemas import ColorClusterSummary, MatchConfig
from backend.app.storage import Storage


FIXTURE = Path(__file__).parent / "fixtures" / "raw_rows_two_teams.json"


def install_raw_row_match(storage: Storage, tmp_path: Path) -> str:
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len({row["Frame_ID"] for row in rows}) >= 40
    source = tmp_path / "two-teams.mp4"
    source.write_bytes(b"fixture")
    match = storage.create_match(
        "Raw row team mapping",
        "video",
        source.name,
        source,
        MatchConfig(myTeamCluster=0),
    )
    storage.save_raw_rows(match.id, rows)
    storage.update_match_status(
        match.id,
        status="ready",
        team_clusters=[
            ColorClusterSummary(clusterId=0, rgbCentroid=[255.0, 0.0, 0.0], trackIds=[7]),
            ColorClusterSummary(clusterId=1, rgbCentroid=[0.0, 0.0, 255.0], trackIds=[18]),
        ],
    )
    reprocess_video_match(storage, match.id)
    return match.id


def _team_for_track(storage: Storage, match_id: str, track_id: int) -> str | None:
    frame = storage.load_frames(match_id)[0]
    if any(player.id == track_id for player in frame.myTeam):
        return "my_team"
    if any(player.id == track_id for player in frame.enemies):
        return "enemy"
    return None


def test_t02_raw_row_team_swap_survives_rebuild_and_restart(tmp_path: Path) -> None:
    """B04 / T02: corrections must change the effective config before raw-row classification."""
    storage_root = tmp_path / "storage"
    storage = Storage(storage_root)
    match_id = install_raw_row_match(storage, tmp_path)
    assert _team_for_track(storage, match_id, 7) == "my_team"

    storage.submit_correction(match_id, kind="team_mapping", payload={"swap": True})
    assert _team_for_track(storage, match_id, 7) == "enemy"

    reprocess_video_match(storage, match_id)
    assert _team_for_track(storage, match_id, 7) == "enemy"

    restarted = Storage(storage_root)
    assert _team_for_track(restarted, match_id, 7) == "enemy"
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from backend.app.storage import Storage; "
                "s=Storage(sys.argv[1]); f=s.load_frames(sys.argv[2])[0]; "
                "print('enemy' if any(p.id == 7 for p in f.enemies) else 'not-enemy')"
            ),
            str(storage_root),
            match_id,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert check.stdout.strip() == "enemy"
