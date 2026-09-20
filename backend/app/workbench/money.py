"""Exact money normalization shared by admission and billing projections.

Legacy REAL values are interpreted as their persisted decimal representation;
we cannot reconstruct precision that an old writer already discarded. New
charge rows retain exact decimal text alongside the compatibility REAL column.
Public JSON numbers are a presentation boundary, never admission operands.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

ZERO = Decimal(0)
MAX_MONEY = Decimal("1000000000000000")


def money(value: Any, *, signed: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("money must be a finite decimal number, not a boolean")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid decimal money") from exc
    if not result.is_finite() or (not signed and result < ZERO) or abs(result) > MAX_MONEY:
        raise ValueError("money is negative, non-finite or outside the supported range")
    if result.as_tuple().exponent < -12:
        raise ValueError("money supports at most 12 fractional decimal places")
    return result


def total(values) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return sum(values, ZERO)


def text(value: Decimal) -> str:
    return format(value, "f")


def admission_money(value: Any) -> Decimal:
    """Reject ceilings/reservations the legacy numeric envelope cannot preserve.

    This guard is not used for invoices: a truthful charge keeps its exact text
    even when its numeric presentation is rounded or it exceeds the budget.
    """
    exact = money(value)
    if money(float(exact)) != exact:
        raise ValueError("MONEY_REPRESENTATION_UNSUPPORTED")
    return exact
