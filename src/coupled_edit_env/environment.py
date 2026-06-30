"""
Core environment loader following the verifiers package convention.
Exposes load_environment() which returns task instances and the verifier.
"""

from dataclasses import dataclass
from typing import Callable, List

from coupled_edit_env.types import TaskInstance
from coupled_edit_env.verifier import verify_solution
from coupled_edit_env.tasks import TASK_REGISTRY


@dataclass
class Environment:
    name: str
    tasks: List[TaskInstance]
    verify: Callable
    max_turns: int = 1
    timeout_seconds: int = 60

    def __len__(self):
        return len(self.tasks)

    def __iter__(self):
        return iter(self.tasks)


def load_environment(split: str = "eval") -> Environment:
    """
    Load the Coupled Edit Propagation environment.

    Args:
        split: 'train' or 'eval'. Train split is for development,
               eval split is held out for final scoring.

    Returns:
        Environment object with tasks and verifier.
    """
    tasks = []
    registry = TASK_REGISTRY.get(split, TASK_REGISTRY["eval"])

    for task_factory in registry:
        tasks.append(task_factory())

    return Environment(
        name="coupled-edit-propagation",
        tasks=tasks,
        verify=verify_solution,
        max_turns=1,
        timeout_seconds=60,
    )
