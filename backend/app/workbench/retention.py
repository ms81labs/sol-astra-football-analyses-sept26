"""GA-12/7.2 retention. Frozen evaluation and user originals are not disposable cache."""

from __future__ import annotations

PROTECTED = frozenset({"frozen_evaluation", "user_owned_original_media"})


def may_delete(kind: str, *, authorised_policy: bool) -> bool:
    if kind in PROTECTED:
        return False
    return authorised_policy
