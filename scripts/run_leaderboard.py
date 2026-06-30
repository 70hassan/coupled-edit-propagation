"""
Run the capability leaderboard.

By default this runs the three deterministic baselines (noop, partial, gold)
which require no API access. These prove the leaderboard pipeline works
end-to-end and bracket the expected score range for any real model.

To add real models, set the appropriate environment variables and pass
--include-real:

    export OPENAI_API_KEY=...
    export ANTHROPIC_API_KEY=...
    export OPENROUTER_API_KEY=...
    python scripts/run_leaderboard.py --include-real --split eval

The script writes LEADERBOARD.md at the repo root.
"""

import argparse
import sys
from pathlib import Path

from coupled_edit_env.leaderboard import (
    NoopBaseline,
    PartialBaseline,
    GoldBaseline,
    OpenAIAdapter,
    AnthropicAdapter,
    OpenRouterAdapter,
    run_leaderboard,
)
from coupled_edit_env.leaderboard.runner import wilson_interval


DEFAULT_ADAPTERS = [
    NoopBaseline(),
    PartialBaseline(),
    GoldBaseline(),
]

REAL_ADAPTERS = [
    OpenAIAdapter("gpt-4o-mini"),
    OpenAIAdapter("gpt-4o"),
    AnthropicAdapter("claude-3-5-sonnet-20241022"),
    AnthropicAdapter("claude-3-5-haiku-20241022"),
    OpenRouterAdapter("google/gemini-2.0-flash-exp:free"),
    OpenRouterAdapter("meta-llama/llama-3.3-70b-instruct"),
]


def emit_markdown(report, output_path: Path):
    lines = [
        "# Capability-Only Leaderboard",
        "",
        f"Split: `{report.split}`",
        f"Tasks: {len(report.results[0].per_task_scores) if report.results else 0}",
        f"Models attempted: {len(report.results)}",
        "",
        "Models are ranked by the **lower bound of a bootstrap 95% CI on mean ",
        "score** (Building a Sound RL Environment, Tier 1 Requirement 2). The ",
        "pass-rate Wilson interval is also reported.",
        "",
        "## Ranked Results",
        "",
        "| Rank | Model | Pass | Mean | Mean 95% CI | Pass 95% CI | Time (s) |",
        "|------|-------|------|-----:|:-----------:|:-----------:|---------:|",
    ]
    for rank, (r, p_lo, p_hi, m_lo, m_hi) in enumerate(report.sorted_by_lower_bound(), start=1):
        pass_str = f"{r.n_passed}/{r.n_total}"
        lines.append(
            f"| {rank} | `{r.model_name}` | {pass_str} | {r.mean:.3f} | "
            f"[{m_lo:.3f}, {m_hi:.3f}] | [{p_lo:.3f}, {p_hi:.3f}] | "
            f"{r.total_seconds:.1f} |"
        )

    lines.append("")
    lines.append("## Per-Task Scores")
    lines.append("")
    if report.results:
        task_ids = report.results[0].per_task_ids
        header = "| Model | " + " | ".join(task_ids) + " |"
        sep = "|---|" + "---|" * len(task_ids)
        lines.append(header)
        lines.append(sep)
        for r in report.results:
            scores = " | ".join(f"{s:.2f}" for s in r.per_task_scores)
            lines.append(f"| `{r.model_name}` | {scores} |")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Deterministic baselines (noop, partial, gold) require no API access ")
    lines.append("  and bracket the expected range for real models.")
    lines.append("- Real model rows appear only when the corresponding API key is set.")
    lines.append("- Ranking by CI lower bound penalises models with fewer samples or ")
    lines.append("  higher variance, per Tier-1 guidance.")
    lines.append("- Scaffold: single-turn plain prompt completion. Temperature 0.0.")
    lines.append("  This matches the simplest possible scaffold; production-scaffold ")
    lines.append("  numbers (Claude Code, Codex CLI) would likely be higher.")

    output_path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Run the capability leaderboard")
    parser.add_argument("--split", choices=["train", "eval", "both"], default="eval")
    parser.add_argument("--include-real", action="store_true",
                        help="Include real model adapters (requires API keys)")
    parser.add_argument("--output", default="LEADERBOARD.md")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    adapters = list(DEFAULT_ADAPTERS)
    if args.include_real:
        for adapter in REAL_ADAPTERS:
            if adapter.is_available():
                adapters.append(adapter)
            else:
                print(f"  SKIP {adapter.name}: API key or SDK not available")

    progress_fn = print if args.verbose else None

    if args.split == "both":
        from coupled_edit_env.leaderboard.runner import LeaderboardReport
        combined = LeaderboardReport(split="train+eval")
        train_report = run_leaderboard(adapters, split="train", on_progress=progress_fn)
        eval_report = run_leaderboard(adapters, split="eval", on_progress=progress_fn)
        by_name = {}
        for r in train_report.results + eval_report.results:
            if r.model_name not in by_name:
                from coupled_edit_env.leaderboard.runner import ModelResult
                by_name[r.model_name] = ModelResult(model_name=r.model_name, provider=r.provider)
            by_name[r.model_name].per_task_scores.extend(r.per_task_scores)
            by_name[r.model_name].per_task_passed.extend(r.per_task_passed)
            by_name[r.model_name].per_task_ids.extend(r.per_task_ids)
            by_name[r.model_name].total_seconds += r.total_seconds
        combined.results = list(by_name.values())
        print(f"\nCombined leaderboard (train + eval = 8 tasks):")
        print(combined.format_table())
        out_path = Path(args.output)
        emit_markdown(combined, out_path)
        print(f"\nReport written to: {out_path.resolve()}")
    else:
        print(f"\nRunning leaderboard on split='{args.split}' with {len(adapters)} adapters...")
        report = run_leaderboard(adapters, split=args.split, on_progress=progress_fn)
        print(report.format_table())
        out_path = Path(args.output)
        emit_markdown(report, out_path)
        print(f"\nReport written to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
