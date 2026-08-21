"""Execute an approved merge plan through a backend."""

from __future__ import annotations

from .models import MERGE, REVIEW, TRASH, MergePlan


def apply_merge_plan(plan: MergePlan, backend) -> MergePlan:
    """Merge and trash exactly what the plan says, and nothing it left open.

    Groups still marked ``review`` are skipped rather than guessed at. They
    stay in the returned plan with their action unchanged, so a caller can
    report how much was deliberately not done -- a merge run that quietly
    left half the library untouched is indistinguishable from a clean one.
    """
    plan.validate()

    for group in plan.groups:
        if group.action == MERGE:
            others = group.other_keys
            if others:
                backend.merge_items(group.master_key, others)
        elif group.action == TRASH:
            backend.trash_items(group.keys)

    plan.applied = True
    return plan


def review_backlog(plan: MergePlan) -> list:
    """The groups an apply would skip, for the caller to show."""
    return [group for group in plan.groups if group.action == REVIEW]
