"""Versioned C02 semantic command admission and replay.

This module changes analytical inputs only. Current rights/provider policy and
presentation metadata are never restored by undo or by a historical snapshot.
Legacy payloads remain byte-for-byte unchanged because generations bind their
command digest. Proven old team mappings are resolved from retained snapshots.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .generations import semantic_config
from .schemas import MatchConfig
from .workbench.errors import DomainError
from .workbench.review import Correction

ANALYTICAL_FIELDS = frozenset(semantic_config(MatchConfig())) - {'calibrationCommitted'}
POLICY_FIELDS = frozenset({'rights', 'llmProvider'})
METADATA_FIELDS = frozenset({'homeTeam', 'awayTeam'})
CONTROL_FIELDS = frozenset({'expectedVersion', 'baseGeneration', 'commandId', 'idempotencyKey'})


class SemanticCommandError(DomainError):
    def __init__(self, code: str, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def active_commands(history: list[Correction]) -> list[Correction]:
    included = [c for c in history if c.applyState in {'applied', 'applying'}]
    undone = {c.payload.get('of') for c in included if c.kind == 'undo'}
    return [c for c in included if c.kind != 'undo' and c.correctionId not in undone]


def validate_config_values(values: dict, current: MatchConfig) -> dict:
    if not isinstance(values, dict) or not values or set(values) - ANALYTICAL_FIELDS:
        raise SemanticCommandError('INVALID_SEMANTIC_CONFIG', 'Only declared analytical configuration fields are allowed')
    validated = MatchConfig.model_validate({**current.model_dump(mode='python'), **values}, strict=True)
    return {key: validated.model_dump(mode='json')[key] for key in values}


def validate_cluster(value: Any, clusters: set[int]) -> int:
    if type(value) is not int or value not in clusters:
        raise SemanticCommandError('UNKNOWN_TEAM_CLUSTER', 'An explicit target must be a detected selectable cluster')
    return value


def canonical_team_mapping(payload: dict, *, clusters: set[int], selected: int | None,
                           tracking_role: str, input_mode: str) -> dict:
    """Resolve an operation ONCE at admission; replay never picks alternatives."""
    if input_mode == 'tracking_json' and not clusters:
        if 'targetCluster' in payload or 'myTeamCluster' in payload or 'pair' in payload:
            raise SemanticCommandError('INVALID_TEAM_MAPPING', 'Named tracking teams require a role target, not a colour cluster')
        if 'targetRole' in payload:
            target = payload['targetRole']
        elif payload.get('swap') is True:
            target = 'enemy' if tracking_role == 'my_team' else 'my_team'
        else:
            raise SemanticCommandError('INVALID_TEAM_MAPPING', 'Supply swap:true or an explicit tracking targetRole')
        if not isinstance(target, str) or target not in {'my_team', 'enemy'}:
            raise SemanticCommandError('INVALID_TEAM_MAPPING', 'Unknown tracking team role')
        return {'operation': 'select_role', 'targetRole': target, 'expectedSourceSelection': tracking_role}
    if 'targetCluster' in payload or 'myTeamCluster' in payload:
        target = validate_cluster(payload.get('targetCluster', payload.get('myTeamCluster')), clusters)
        return {'operation': 'select_cluster', 'targetCluster': target, 'expectedSourceSelection': selected}
    if payload.get('swap') is not True:
        raise SemanticCommandError('INVALID_TEAM_MAPPING', 'Supply an explicit target or swap:true')
    pair = payload.get('pair')
    if pair is None:
        if len(clusters) != 2 or selected not in clusters:
            raise SemanticCommandError('AMBIGUOUS_TEAM_SWAP', 'A bare swap requires exactly two known teams and a selected team')
        pair = sorted(clusters)
    if not isinstance(pair, list) or len(pair) != 2 or any(type(v) is not int for v in pair) or len(set(pair)) != 2:
        raise SemanticCommandError('INVALID_TEAM_PAIR', 'A swap pair must name two distinct detected clusters')
    if not set(pair) <= clusters or selected not in pair:
        raise SemanticCommandError('INVALID_TEAM_PAIR', 'The pair must contain the current selection and a known other cluster')
    target = pair[1] if selected == pair[0] else pair[0]
    return {'operation': 'select_cluster', 'targetCluster': target, 'expectedSourceSelection': selected, 'pair': pair}


def command_track_ids(command: Correction) -> set[str]:
    fields = ('trackId', 'newTrackId', 'leftTrackId', 'rightTrackId')
    return {str(command.payload[k]) for k in fields if command.payload.get(k) not in (None, '')}


def validate_undo(original: Correction, history: list[Correction]) -> None:
    if original.kind == 'undo':
        raise SemanticCommandError('REDO_UNSUPPORTED', 'Undo-of-undo/redo is not supported', status_code=409)
    active = active_commands(history)
    if original.applyState != 'applied' or original.correctionId not in {c.correctionId for c in active}:
        raise SemanticCommandError('COMMAND_NOT_ACTIVE', 'Only an active applied command can be undone', status_code=409)
    if original.kind == 'playlist_item' and any(
        later.kind == 'playlist_item' and later.payload.get('replaces') == original.correctionId
        for later in active
    ):
        raise SemanticCommandError('COMMAND_DEPENDENCY_CONFLICT', 'Undo the later clip edit first', status_code=409)
    if original.kind in {'track_split', 'track_join'}:
        touched = command_track_ids(original)
        for later in active:
            if later.version <= original.version or later.kind not in {'track_split', 'track_join'}:
                continue
            if touched & command_track_ids(later):
                raise SemanticCommandError('COMMAND_DEPENDENCY_CONFLICT', 'Undo dependent identity edits first', status_code=409)
