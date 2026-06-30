"""
Command-line interface for running evaluations against the environment.
"""

import argparse
import json
import sys
from pathlib import Path

from coupled_edit_env.environment import load_environment
from coupled_edit_env.verifier import verify_solution


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate model outputs against the Coupled Edit Propagation environment"
    )
    parser.add_argument(
        "--split", choices=["train", "eval"], default="eval",
        help="Which task split to evaluate on"
    )
    parser.add_argument(
        "--task-id", type=str, default=None,
        help="Run a specific task by ID (optional)"
    )
    parser.add_argument(
        "--solution-dir", type=str, default=None,
        help="Directory containing solution files (one .txt per task_id)"
    )
    parser.add_argument(
        "--list-tasks", action="store_true",
        help="Just list available tasks and exit"
    )
    parser.add_argument(
        "--show-prompt", type=str, default=None,
        help="Show the prompt for a specific task ID"
    )

    args = parser.parse_args()
    env = load_environment(split=args.split)

    if args.list_tasks:
        print(f"Environment: {env.name}")
        print(f"Split: {args.split}")
        print(f"Tasks: {len(env.tasks)}")
        print("-" * 60)
        for task in env.tasks:
            print(f"  {task.task_id} (difficulty: {task.difficulty})")
        return

    if args.show_prompt:
        for task in env.tasks:
            if task.task_id == args.show_prompt:
                print(task.to_prompt())
                return
        print(f"Task '{args.show_prompt}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.solution_dir is None:
        print("No --solution-dir provided. Use --list-tasks to see available tasks.")
        print("Use --show-prompt TASK_ID to see a task's prompt.")
        sys.exit(0)

    solution_dir = Path(args.solution_dir)
    if not solution_dir.exists():
        print(f"Solution directory not found: {solution_dir}", file=sys.stderr)
        sys.exit(1)

    results = []
    tasks_to_run = env.tasks
    if args.task_id:
        tasks_to_run = [t for t in env.tasks if t.task_id == args.task_id]
        if not tasks_to_run:
            print(f"Task '{args.task_id}' not found in {args.split} split.", file=sys.stderr)
            sys.exit(1)

    for task in tasks_to_run:
        solution_file = solution_dir / f"{task.task_id}.txt"
        if not solution_file.exists():
            print(f"  SKIP  {task.task_id} (no solution file)")
            results.append({"task_id": task.task_id, "score": 0.0, "skipped": True})
            continue

        solution_text = solution_file.read_text()
        result = verify_solution(task, solution_text)

        status = "PASS" if result.passed else "FAIL"
        print(f"  {status}  {task.task_id}: score={result.score:.2f} "
              f"({result.tests_passed}/{result.tests_total} tests)")

        if result.reverted_source:
            print(f"        [CHEAT DETECTED: source reverted]")
        if result.oracle_leak_detected:
            print(f"        [CHEAT DETECTED: oracle leak]")

        results.append({
            "task_id": task.task_id,
            "score": result.score,
            "tests_passed": result.tests_passed,
            "tests_total": result.tests_total,
            "passed": result.passed,
        })

    print("\n" + "=" * 60)
    scores = [r["score"] for r in results if not r.get("skipped")]
    if scores:
        mean_score = sum(scores) / len(scores)
        print(f"Mean score: {mean_score:.3f} ({len(scores)} tasks evaluated)")
    else:
        print("No tasks evaluated.")


if __name__ == "__main__":
    main()
