"""Grouped chat/app command handlers."""

from src.tools.commanding.handlers.learning import LEARNING_HANDLERS
from src.tools.commanding.handlers.ops import OPS_HANDLERS
from src.tools.commanding.handlers.repo import REPO_HANDLERS
from src.tools.commanding.handlers.review import REVIEW_HANDLERS

ALL_HANDLER_GROUPS = (
    OPS_HANDLERS,
    REVIEW_HANDLERS,
    REPO_HANDLERS,
    LEARNING_HANDLERS,
)

__all__ = ["ALL_HANDLER_GROUPS", "LEARNING_HANDLERS", "OPS_HANDLERS", "REPO_HANDLERS", "REVIEW_HANDLERS"]
