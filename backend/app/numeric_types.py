"""Runtime-exact numeric type guards shared by legacy data readers."""
from typing import TypeGuard


def is_builtin_number(value: object) -> TypeGuard[int | float]:
    """Recognize only builtin int/float, excluding bool and numeric subclasses.

    This is a type check, not a range or finiteness policy. Callers retain their
    own availability and value-validation rules.
    """
    return type(value) in (int, float)
