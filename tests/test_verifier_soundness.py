"""
Adversarial test sweep: every cheat class is applied to every task.

This is the false-accept leg of the soundness receipt: if any cheat scores 1.0
on any task, that is a false accept. The target is zero false accepts.

The sweep generates a Cartesian product of (8 tasks) x (7 cheat classes) = 56
attack attempts. Empty/malformed submissions add another 24 cases for a total
of 80 adversarial trials.
"""

import pytest
from coupled_edit_env.environment import load_environment
from coupled_edit_env.verifier import verify_solution
from coupled_edit_env.adversarial.cheats import ALL_CHEATS


def _all_tasks():
    tasks = []
    for split in ["train", "eval"]:
        env = load_environment(split=split)
        tasks.extend(env.tasks)
    return tasks


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: t.task_id)
@pytest.mark.parametrize("cheat_name", list(ALL_CHEATS.keys()))
def test_cheat_does_not_score_perfect(task, cheat_name):
    """No cheat strategy may achieve a perfect score on any task.

    This is the core soundness property. If any combination of (task, cheat)
    scores 1.0, the verifier has a hole.
    """
    cheat_fn = ALL_CHEATS[cheat_name]
    cheat_output = cheat_fn(task)
    result = verify_solution(task, cheat_output)
    assert result.score < 1.0, (
        f"FALSE ACCEPT: cheat '{cheat_name}' scored {result.score:.3f} on {task.task_id}. "
        f"Tests: {result.tests_passed}/{result.tests_total}. "
        f"Flags: reverted={result.reverted_source}, oracle_leak={result.oracle_leak_detected}"
    )


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: t.task_id)
def test_empty_submission_scores_zero(task):
    result = verify_solution(task, "")
    assert result.score == 0.0


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: t.task_id)
def test_garbage_submission_scores_zero(task):
    result = verify_solution(task, "lorem ipsum dolor sit amet\nfoo bar baz")
    assert result.score == 0.0


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: t.task_id)
def test_codeblock_only_submission_scores_zero(task):
    result = verify_solution(task, "```python\nprint('hello')\n```")
    assert result.score == 0.0


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: t.task_id)
def test_oracle_leak_flagged(task):
    """The oracle_read cheat must trigger the oracle_leak_detected flag."""
    cheat_output = ALL_CHEATS["oracle_read"](task)
    result = verify_solution(task, cheat_output)
    assert result.oracle_leak_detected, (
        f"Oracle read cheat on {task.task_id} did NOT trigger oracle leak flag"
    )
    assert result.score == 0.0


@pytest.mark.parametrize("task", _all_tasks(), ids=lambda t: t.task_id)
def test_revert_async_flagged(task):
    """For async-modified tasks, the revert cheat must trigger the revert flag."""
    if not task.modified_is_async:
        pytest.skip("Task does not have an async modification")
    cheat_output = ALL_CHEATS["revert"](task)
    result = verify_solution(task, cheat_output)
    assert result.reverted_source or result.score < 1.0, (
        f"Async revert on {task.task_id} not caught"
    )
