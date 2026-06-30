"""
Leaderboard runner.

Given a list of ModelAdapters and a list of TaskInstances, runs each model on
each task, scores the response with verify_solution(), and reports mean reward
with Wilson 95% confidence intervals plus pairwise significance tests on the
differences between models.
"""

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from coupled_edit_env.environment import load_environment
from coupled_edit_env.verifier import verify_solution
from coupled_edit_env.leaderboard.adapters import ModelAdapter


@dataclass
class ModelResult:
    model_name: str
    provider: str
    per_task_scores: List[float] = field(default_factory=list)
    per_task_passed: List[bool] = field(default_factory=list)
    per_task_ids: List[str] = field(default_factory=list)
    total_seconds: float = 0.0

    @property
    def mean(self) -> float:
        return sum(self.per_task_scores) / len(self.per_task_scores) if self.per_task_scores else 0.0

    @property
    def n_passed(self) -> int:
        return sum(1 for p in self.per_task_passed if p)

    @property
    def n_total(self) -> int:
        return len(self.per_task_scores)


@dataclass
class LeaderboardReport:
    results: List[ModelResult] = field(default_factory=list)
    split: str = "eval"

    def sorted_by_lower_bound(self) -> List[Tuple[ModelResult, float, float, float, float]]:
        """Sort models by the lower bound of their mean-score CI.

        Returns rows of (result, pass_ci_low, pass_ci_high, mean_ci_low, mean_ci_high).
        Ranking key: mean-score CI lower bound (more informative under partial credit).
        Tie-breaker: pass-rate CI lower bound, then observed mean.
        """
        out = []
        for r in self.results:
            p_lo, p_hi = wilson_interval(r.n_passed, r.n_total)
            m_lo, m_hi = bootstrap_mean_interval(r.per_task_scores)
            out.append((r, p_lo, p_hi, m_lo, m_hi))
        out.sort(key=lambda x: (x[3], x[1], x[0].mean), reverse=True)
        return out

    def format_table(self) -> str:
        header = (
            f"  {'rank':<5} {'model':<32} {'pass':<8} {'mean':<8} "
            f"{'mean CI':<18} {'pass CI':<18} {'time (s)':<10}\n"
            f"  {'-' * 5} {'-' * 32} {'-' * 8} {'-' * 8} {'-' * 18} {'-' * 18} {'-' * 10}\n"
        )
        lines = [header]
        for rank, (r, p_lo, p_hi, m_lo, m_hi) in enumerate(self.sorted_by_lower_bound(), start=1):
            pass_str = f"{r.n_passed}/{r.n_total}"
            mean_ci = f"[{m_lo:.3f}, {m_hi:.3f}]"
            pass_ci = f"[{p_lo:.3f}, {p_hi:.3f}]"
            lines.append(
                f"  {rank:<5} {r.model_name:<32} {pass_str:<8} {r.mean:<8.3f} "
                f"{mean_ci:<18} {pass_ci:<18} {r.total_seconds:<10.1f}"
            )
        return "\n".join(lines)


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval at 95% confidence (z=1.96)."""
    if trials == 0:
        return (0.0, 1.0)
    p_hat = successes / trials
    denom = 1 + z * z / trials
    centre = (p_hat + z * z / (2 * trials)) / denom
    spread = z * math.sqrt(p_hat * (1 - p_hat) / trials + z * z / (4 * trials * trials)) / denom
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def bootstrap_mean_interval(
    scores: List[float], n_resamples: int = 2000, confidence: float = 0.95, seed: int = 0
) -> Tuple[float, float]:
    """Bootstrap percentile CI for the mean of a list of scores.

    Uses the standard non-parametric bootstrap. With a small n (8 tasks) this
    is more honest than a normal-approximation CI because it makes no
    distributional assumption.
    """
    import random
    if not scores:
        return (0.0, 1.0)
    rng = random.Random(seed)
    n = len(scores)
    means = []
    for _ in range(n_resamples):
        sample = [scores[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = (1 - confidence) / 2
    lo = means[int(alpha * n_resamples)]
    hi = means[int((1 - alpha) * n_resamples)]
    return (lo, hi)


def run_leaderboard(
    adapters: List[ModelAdapter],
    split: str = "eval",
    on_progress: Optional[callable] = None,
) -> LeaderboardReport:
    """Run every adapter on every task in the split and score the responses.

    Returns a LeaderboardReport with mean and per-model CIs.
    """
    env = load_environment(split=split)
    report = LeaderboardReport(split=split)

    for adapter in adapters:
        result = ModelResult(model_name=adapter.name, provider=adapter.provider)
        if not adapter.is_available():
            if on_progress:
                on_progress(f"SKIP {adapter.name}: not available (missing key or SDK)")
            report.results.append(result)
            continue

        t0 = time.time()
        for task in env.tasks:
            prompt = task.to_prompt()
            try:
                response = adapter.generate(prompt, task_id=task.task_id)
            except Exception as e:
                response = ""
                if on_progress:
                    on_progress(f"  {adapter.name} on {task.task_id}: ERROR {e}")

            v = verify_solution(task, response)
            result.per_task_scores.append(v.score)
            result.per_task_passed.append(v.passed)
            result.per_task_ids.append(task.task_id)
            if on_progress:
                on_progress(
                    f"  {adapter.name} on {task.task_id}: score={v.score:.3f} "
                    f"({v.tests_passed}/{v.tests_total})"
                )
        result.total_seconds = time.time() - t0
        report.results.append(result)

    return report
