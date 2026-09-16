from __future__ import annotations

import json

import backend.scripts.promote_selected_cluster_for_proof as promote_selected_cluster_for_proof


def test_promote_selected_cluster_for_proof_cli_prints_before_after_and_recommendation(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "backend.scripts.promote_selected_cluster_for_proof.promote_selected_cluster_for_proof",
        lambda **kwargs: {
            "savedMatchId": "match-123",
            "selectedClusterId": 0,
            "before": {"controlledPossessionFrames": 0, "eventFamilyCount": 1},
            "after": {"controlledPossessionFrames": 33, "eventFamilyCount": 3},
            "improvedFields": ["controlledPossessionFrames", "eventFamilyCount"],
            "remainingTruthGateReasons": ["Need acceptedBallFrames/frameCount >= 25% for truthful 5-10 minute analysis"],
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "promote_selected_cluster_for_proof.py",
            "--storage-root",
            str(tmp_path),
            "--match-id",
            "match-123",
        ],
    )

    promote_selected_cluster_for_proof.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["savedMatchId"] == "match-123"
    assert payload["selectedClusterId"] == 0
    assert payload["after"]["controlledPossessionFrames"] == 33
