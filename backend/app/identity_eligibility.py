"""C02 identity revision and conservative whole-metric coverage contract.

Approval is a recorded review of specific source/association bytes and ordered
identity edits. A track/partial-interval review never certifies a full match.
Readers use only the committed manifest context, not today's mutable command log.
"""
from __future__ import annotations

import math
import re
from .semantic_commands import digest, SemanticCommandError


def _identity_change(command) -> bool:
    return command.kind in {"track_split", "track_join", "team_mapping"} or (
        command.kind == "config_set" and "myTeamCluster" in command.payload.get("values", {}))


def revision_for(storage, match_id, history):
    root = storage.generations.root(match_id)
    source = None
    for name in ("raw_rows.json", "review_base_frames.json"):
        path = root / name
        if path.is_file():
            source = storage._sha256_file(path)
            break
    if source is None:
        path = storage.get_match_input_path(match_id)
        source = storage._sha256_file(path)
    included = [c for c in history if c.applyState in {"applied", "applying"}]
    changed = {c.correctionId for c in included if _identity_change(c)}
    sequence = [{"id":c.commandId,"kind":c.kind,"payload":c.payload} for c in included
                if _identity_change(c) or c.kind=="undo" and c.payload.get("of") in changed]
    # Undo changes the review revision too: it does not silently restore approval.
    association = None
    association_path = root / "tracking_identity.json"
    if association_path.is_file():
        association = storage._sha256_file(association_path)
    return "identity_" + digest({"observations":source,"association":association,"edits":sequence}), source


def required_scope(frames):
    times = [f.timestamp for f in frames]
    tracks = sorted({str(p.id) for f in frames for field in ("myTeam","enemies","unassignedPlayers") for p in getattr(f,field)})
    return {"intervalStart": min(times) if times else 0.0,
            "intervalEnd": math.nextafter(max(times), math.inf) if times else 0.0,
            "trackIds":tracks, "teamScope":"all"}


def approval_payload(storage, match_id, payload, history, *, author):
    allowed={"reviewed","identityRevision","intervalStart","intervalEnd","trackIds","teamScope"}
    if set(payload)-allowed or payload.get("reviewed") is not True:
        raise SemanticCommandError("INVALID_IDENTITY_APPROVAL", "A review must specify valid approval scope")
    frames=storage.load_frames(match_id)
    scope=required_scope(frames)
    if not scope["trackIds"] or scope["intervalEnd"] <= scope["intervalStart"]:
        raise SemanticCommandError("IDENTITY_SOURCE_UNAVAILABLE", "No identity observations are available",status_code=409)
    revision,observations=revision_for(storage,match_id,history)
    if payload.get("identityRevision",revision)!=revision:
        raise SemanticCommandError("STALE_IDENTITY_REVISION", "Review refers to another identity revision",status_code=409)
    start,end=payload.get('intervalStart',scope['intervalStart']),payload.get('intervalEnd',scope['intervalEnd'])
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (start,end)) or start>=end:
        raise SemanticCommandError("INVALID_APPROVAL_INTERVAL", "Approval interval must be finite and ordered")
    if start<scope['intervalStart'] or end>scope['intervalEnd']:
        raise SemanticCommandError("INVALID_APPROVAL_INTERVAL", "Review cannot claim unobserved time")
    tracks=payload.get('trackIds',scope['trackIds'])
    if not isinstance(tracks,list) or not tracks or any(type(v) not in (int,str) for v in tracks):
        raise SemanticCommandError("INVALID_APPROVAL_SCOPE", "Review subjects must be known track IDs")
    tracks=sorted(set(map(str,tracks)))
    if not set(tracks)<=set(scope['trackIds']):
        raise SemanticCommandError("UNKNOWN_TRACK", "Review references unknown subjects")
    team=payload.get('teamScope','all')
    if team not in {'all','my_team','enemy'}:
        raise SemanticCommandError("INVALID_APPROVAL_SCOPE", "Review team scope is invalid")
    return {"reviewed":True,"schemaVersion":1,"identityRevision":revision,"observationDigest":observations,
            "intervalStart":float(start),"intervalEnd":float(end),"trackIds":tracks,"teamScope":team,"reviewer":author}


def context_for(storage,match_id,frames,commands):
    history=storage._load_correction_log(match_id).history(match_id)
    revision,observations=revision_for(storage,match_id,history)
    approvals=[dict(c.payload) for c in commands if c.kind=='identity_validate' and c.payload.get('schemaVersion')==1]
    return {"schemaVersion":1,"identityRevision":revision,"observationDigest":observations,
            "requiredScope":required_scope(frames),"approvals":approvals}


def identity_eligibility(context):
    """One fail-closed conservative calculator for publication and readers."""
    unavailable = {"continuous": False, "identityRevision": None,
                   "reasonCodes": ["IDENTITY_APPROVAL_UNSCOPED"]}
    if not isinstance(context, dict) or context.get("schemaVersion") != 1:
        return unavailable
    revision, observations = context.get("identityRevision"), context.get("observationDigest")
    if (not isinstance(revision, str) or not re.fullmatch(r"identity_[a-f0-9]{64}", revision)
        or not isinstance(observations, str) or not re.fullmatch(r"[a-f0-9]{64}", observations)):
        return unavailable
    scope = context.get("requiredScope")
    approvals = context.get("approvals")
    if not isinstance(scope, dict) or not isinstance(approvals, list):
        return unavailable
    def interval(value):
        start, end = value.get("intervalStart"), value.get("intervalEnd")
        return (type(start) in (int, float) and type(end) in (int, float)
                and math.isfinite(start) and math.isfinite(end) and start < end)
    def subjects(value):
        tracks = value.get("trackIds")
        return isinstance(tracks, list) and bool(tracks) and all(isinstance(t, str) and bool(t) for t in tracks)
    approved = False
    if interval(scope) and subjects(scope):
        for approval in approvals:
            if not isinstance(approval, dict) or not interval(approval) or not subjects(approval):
                continue
            reviewer = approval.get("reviewer")
            if (approval.get("schemaVersion") == 1 and approval.get("reviewed") is True
                and isinstance(reviewer, str) and reviewer.strip()
                and approval.get("identityRevision") == revision
                and approval.get("observationDigest") == observations
                and approval.get("teamScope") == "all"
                and approval["intervalStart"] <= scope["intervalStart"]
                and approval["intervalEnd"] >= scope["intervalEnd"]
                and set(approval["trackIds"]) >= set(scope["trackIds"])):
                approved = True
                break
    return {"continuous": approved, "identityRevision": revision,
            "reasonCodes": [] if approved else ["IDENTITY_APPROVAL_REVISION_OR_COVERAGE_REQUIRED"]}
