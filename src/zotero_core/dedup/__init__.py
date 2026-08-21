"""Finding works a library holds twice, and folding them back into one."""

from .applier import apply_merge_plan, review_backlog
from .grouper import CONFIDENT_RULES, choose_master, find_duplicates
from .models import (
    ACTIONS,
    MERGE,
    REVIEW,
    SKIP,
    TRASH,
    WRITING_ACTIONS,
    DuplicateGroup,
    MergePlan,
)

__all__ = [
    "ACTIONS",
    "CONFIDENT_RULES",
    "MERGE",
    "REVIEW",
    "SKIP",
    "TRASH",
    "WRITING_ACTIONS",
    "DuplicateGroup",
    "MergePlan",
    "apply_merge_plan",
    "choose_master",
    "find_duplicates",
    "review_backlog",
]
