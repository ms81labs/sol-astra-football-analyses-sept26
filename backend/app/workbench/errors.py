from __future__ import annotations


class DomainError(RuntimeError):
    pass


class IdempotencyConflict(DomainError):
    def __init__(self, request_id: str):
        super().__init__("idempotent request payload mismatch")
        self.request_id = request_id


class ReconciliationRequired(DomainError):
    pass


class RetryBudgetExhausted(DomainError):
    pass


class BudgetExhausted(DomainError):
    pass


class StaleTransition(DomainError):
    def __init__(self, *, expected: int, actual: int):
        super().__init__("stale job transition")
        self.expected = expected
        self.actual = actual


class NotOwner(DomainError):
    pass


class StaleRevision(DomainError):
    def __init__(self, *, expected: int, actual: int):
        super().__init__("stale revision")
        self.expected = expected
        self.actual = actual


class RouteRetired(DomainError):
    def __init__(self, replacement: str):
        super().__init__("route retired")
        self.replacement = replacement


class CorrectionApplicationError(DomainError):
    def __init__(self, command_id: str, message: str):
        super().__init__(message)
        self.command_id = command_id
