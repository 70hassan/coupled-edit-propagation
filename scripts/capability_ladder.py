"""
Capability ladder demonstration.

Generates a graded series of solutions per task, from "no changes" through
"partial fix" to "full gold solution", and shows that the verifier produces
a monotonically increasing score across the ladder.

This addresses the Tier-2 "reward density and non-saturation" requirement:
the reward must be graded enough that each step in capability is statistically
separated, and the environment is neither saturated by strong solutions nor
impossible for weak ones.

Run: python scripts/capability_ladder.py
"""

from coupled_edit_env.environment import load_environment
from coupled_edit_env.verifier import verify_solution
from coupled_edit_env.adversarial.cheats import cheat_noop, cheat_shape_forgery
from coupled_edit_env.gold_solutions import GOLD_SOLUTIONS
from coupled_edit_env.partial_solutions import PARTIAL_SOLUTIONS


def gather_all_tasks():
    tasks = []
    for split in ["train", "eval"]:
        env = load_environment(split=split)
        tasks.extend(env.tasks)
    return tasks


def evaluate_ladder(task):
    """For one task, evaluate 4 graded solutions of increasing quality."""
    ladder = []

    noop_out = cheat_noop(task)
    r = verify_solution(task, noop_out)
    ladder.append(("0_noop", r.score, f"{r.tests_passed}/{r.tests_total}"))

    forgery_out = cheat_shape_forgery(task)
    r = verify_solution(task, forgery_out)
    ladder.append(("1_shape_forgery", r.score, f"{r.tests_passed}/{r.tests_total}"))

    partial_out = PARTIAL_SOLUTIONS.get(task.task_id, "")
    r = verify_solution(task, partial_out)
    ladder.append(("2_partial", r.score, f"{r.tests_passed}/{r.tests_total}"))

    gold_out = GOLD_SOLUTIONS.get(task.task_id, "")
    r = verify_solution(task, gold_out)
    ladder.append(("3_gold", r.score, f"{r.tests_passed}/{r.tests_total}"))

    return ladder


def main():
    tasks = gather_all_tasks()
    print("=" * 78)
    print("  CAPABILITY LADDER - Coupled Edit Propagation Environment")
    print("=" * 78)
    print()
    print("  Each task evaluated at four levels:")
    print("    0_noop          : project files unchanged (broken downstream)")
    print("    1_shape_forgery : right types, wrong arithmetic in callers")
    print("    2_partial       : one caller fixed, others still broken")
    print("    3_gold          : full reference solution")
    print()

    header = f"  {'task':<22} {'noop':>10} {'forgery':>10} {'partial':>10} {'gold':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    monotone_count = 0
    for task in tasks:
        ladder = evaluate_ladder(task)
        scores = [score for _, score, _ in ladder]
        is_monotone = all(scores[i] <= scores[i + 1] for i in range(len(scores) - 1))
        if is_monotone:
            monotone_count += 1
        marker = " " if is_monotone else "!"
        print(
            f"{marker} {task.task_id:<22} "
            f"{scores[0]:>10.3f} {scores[1]:>10.3f} {scores[2]:>10.3f} {scores[3]:>10.3f}"
        )

    print()
    print(f"  Monotonically increasing across ladder: {monotone_count}/{len(tasks)} tasks")
    print()
    print("  Interpretation:")
    print("    A monotone ladder confirms the reward signal scales with capability.")
    print("    Non-monotone steps would indicate hidden tests that fail in ways")
    print("    uncorrelated with solution quality (which would be a verifier defect).")
    print("=" * 78)


if __name__ == "__main__":
    main()
