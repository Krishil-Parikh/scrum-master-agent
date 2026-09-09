"""The task-execution loop and the objective completion gate."""

from .verification import CriterionResult, VerificationReport, verify_task
from .task_graph import TaskRunResult, build_task_graph, run_task

__all__ = [
    "verify_task",
    "VerificationReport",
    "CriterionResult",
    "run_task",
    "build_task_graph",
    "TaskRunResult",
]
