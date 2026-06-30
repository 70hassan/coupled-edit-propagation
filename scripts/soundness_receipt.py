"""
Generate the formal soundness receipt for the environment.

Computes false-accept and false-reject rates with Wilson 95% confidence intervals,
following the Tier-1 requirement in Building a Sound RL Environment.

Definitions used:
- False accept: a cheat submission scoring 1.0 (the verifier was fooled).
- False reject: a known-correct submission scoring less than 1.0.

Run: python scripts/soundness_receipt.py
"""

import math
from coupled_edit_env.environment import load_environment
from coupled_edit_env.verifier import verify_solution
from coupled_edit_env.adversarial.cheats import ALL_CHEATS
from coupled_edit_env.gold_solutions import GOLD_SOLUTIONS


def wilson_interval(successes: int, trials: int, z: float = 1.96):
    """Wilson score interval at 95% confidence (z=1.96)."""
    if trials == 0:
        return (0.0, 1.0)
    p_hat = successes / trials
    denom = 1 + z * z / trials
    centre = (p_hat + z * z / (2 * trials)) / denom
    spread = z * math.sqrt(p_hat * (1 - p_hat) / trials + z * z / (4 * trials * trials)) / denom
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def gather_all_tasks():
    tasks = []
    for split in ["train", "eval"]:
        env = load_environment(split=split)
        tasks.extend(env.tasks)
    return tasks


def run_false_accept_sweep(tasks):
    rows = []
    n_trials = 0
    n_false_accepts = 0
    per_class = {}

    for cheat_name, cheat_fn in ALL_CHEATS.items():
        for task in tasks:
            output = cheat_fn(task)
            result = verify_solution(task, output)
            is_false_accept = result.score == 1.0
            rows.append({
                "cheat": cheat_name,
                "task": task.task_id,
                "score": result.score,
                "false_accept": is_false_accept,
                "reverted": result.reverted_source,
                "oracle_leak": result.oracle_leak_detected,
            })
            n_trials += 1
            if is_false_accept:
                n_false_accepts += 1
            per_class.setdefault(cheat_name, [0, 0])
            per_class[cheat_name][1] += 1
            if is_false_accept:
                per_class[cheat_name][0] += 1

    return rows, n_trials, n_false_accepts, per_class


def run_false_reject_sweep(tasks):
    rows = []
    n_trials = 0
    n_false_rejects = 0

    for task in tasks:
        gold = GOLD_SOLUTIONS.get(task.task_id)
        if gold is None:
            continue
        result = verify_solution(task, gold)
        is_false_reject = result.score < 1.0
        rows.append({
            "task": task.task_id,
            "score": result.score,
            "tests": f"{result.tests_passed}/{result.tests_total}",
            "false_reject": is_false_reject,
        })
        n_trials += 1
        if is_false_reject:
            n_false_rejects += 1

    return rows, n_trials, n_false_rejects


def main():
    tasks = gather_all_tasks()
    print("=" * 72)
    print(f"  SOUNDNESS RECEIPT - Coupled Edit Propagation Environment")
    print(f"  Tasks evaluated: {len(tasks)}")
    print("=" * 72)

    print("\n[1] FALSE-ACCEPT RATE")
    print("    Adversarial cheats applied to every task.")
    print()
    rows, n, fa, per_class = run_false_accept_sweep(tasks)
    rate = fa / n if n > 0 else 0
    lo, hi = wilson_interval(fa, n)
    print(f"    Trials              : {n}")
    print(f"    False accepts       : {fa}")
    print(f"    Rate                : {rate:.4f}")
    print(f"    Wilson 95% CI       : [{lo:.4f}, {hi:.4f}]")
    print()
    print("    Per-class breakdown:")
    print(f"    {'cheat':<14} {'trials':>8} {'fa':>5} {'rate':>8} {'CI low':>10} {'CI high':>10}")
    print(f"    {'-' * 14} {'-' * 8} {'-' * 5} {'-' * 8} {'-' * 10} {'-' * 10}")
    for cheat_name, (cfa, cn) in per_class.items():
        crate = cfa / cn if cn > 0 else 0
        clo, chi = wilson_interval(cfa, cn)
        print(f"    {cheat_name:<14} {cn:>8} {cfa:>5} {crate:>8.4f} {clo:>10.4f} {chi:>10.4f}")

    print("\n[2] FALSE-REJECT RATE")
    print("    Gold (reference) solutions on every task.")
    print()
    g_rows, gn, fr = run_false_reject_sweep(tasks)
    g_rate = fr / gn if gn > 0 else 0
    g_lo, g_hi = wilson_interval(fr, gn)
    print(f"    Trials              : {gn}")
    print(f"    False rejects       : {fr}")
    print(f"    Rate                : {g_rate:.4f}")
    print(f"    Wilson 95% CI       : [{g_lo:.4f}, {g_hi:.4f}]")
    print()
    print(f"    {'task':<22} {'score':>8} {'tests':>10} {'verdict':>10}")
    print(f"    {'-' * 22} {'-' * 8} {'-' * 10} {'-' * 10}")
    for row in g_rows:
        verdict = "FALSE_REJ" if row["false_reject"] else "OK"
        print(f"    {row['task']:<22} {row['score']:>8.3f} {row['tests']:>10} {verdict:>10}")

    print()
    print("=" * 72)
    print("  Verdict: ", end="")
    if fa == 0 and fr == 0:
        print("PASS - zero false accepts, zero false rejects.")
    else:
        print(f"FAIL - {fa} false accepts, {fr} false rejects.")
    print("=" * 72)


if __name__ == "__main__":
    main()
