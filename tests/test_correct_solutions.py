"""
Tests that correct (gold) solutions score exactly 1.0 on every task.

This is the false-reject leg of the soundness receipt: if the verifier ever
rejects a known-correct solution, that is a false-reject. The target is zero
false-rejects across all 8 tasks.
"""

import pytest
from coupled_edit_env.environment import load_environment
from coupled_edit_env.verifier import verify_solution
from coupled_edit_env.gold_solutions import GOLD_SOLUTIONS


def _all_tasks():
    tasks = []
    for split in ["train", "eval"]:
        env = load_environment(split=split)
        tasks.extend(env.tasks)
    return tasks


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: t.task_id)
def test_gold_solution_scores_perfect(task):
    """Every gold solution must achieve a perfect score on its task."""
    assert task.task_id in GOLD_SOLUTIONS, (
        f"Missing gold solution for {task.task_id}"
    )
    gold = GOLD_SOLUTIONS[task.task_id]
    result = verify_solution(task, gold)
    assert result.score == 1.0, (
        f"Gold solution for {task.task_id} scored {result.score:.3f} "
        f"({result.tests_passed}/{result.tests_total}). "
        f"Error: {result.error_message}"
    )
    assert not result.reverted_source
    assert not result.oracle_leak_detected


def test_all_tasks_have_gold_solutions():
    """Every task in the registry must have a gold solution defined."""
    for task in _all_tasks():
        assert task.task_id in GOLD_SOLUTIONS, (
            f"Task {task.task_id} has no gold solution defined"
        )
