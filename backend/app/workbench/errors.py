from __future__ import annotations


class DomainError(Exception):
    pass


class IdempotencyConflict(DomainError):
    def __init__(self, request_id: str):
        super().__init__("idempotent request payload mismatch")
        self.request_id = request_id


class StaleRevision(DomainError):
    def __init__(self, *, expected: int, actual: int):
        super().__init__("stale revision")
        self.expected = expected
        self.actual = actual


class RouteRetired(DomainError):
    def __init__(self, replacement: str):
        super().__init__("route retired")
        self.replacement = replacement
