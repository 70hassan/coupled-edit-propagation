# Coupled Edit Propagation

An RL environment that evaluates whether models can propagate changes across
semantically-coupled code when a function's contract changes.

## The problem this targets

When a function's return type, error handling, or interface changes, every
caller that depends on the old contract has to be updated. Frontier coding
models consistently fix the target function but miss callers elsewhere. This
environment gives a clean, behavioral signal for that exact capability:
the verifier passes a submission only when both the change is preserved and
every downstream caller has been correctly repaired.

## Quick start

```bash
pip install -e ".[dev]"
pytest tests/ -v                                    # full test sweep
python scripts/soundness_receipt.py                  # false-accept / false-reject receipt
python scripts/capability_ladder.py                  # graded scoring across solution quality
python scripts/run_leaderboard.py --split both       # baseline leaderboard (no API needed)
python -m coupled_edit_env.cli --list-tasks
```

To run a real-model leaderboard, set any of `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY` and pass `--include-real`:

```bash
export OPENAI_API_KEY=sk-...
python scripts/run_leaderboard.py --include-real --split both
```

## What's in here

```
coupled-edit-propagation/
  README.md                          this file
  SANDBOX_MANIFEST.md                runtime, isolation, contamination notes
  LEADERBOARD.md                     latest leaderboard run (auto-generated)
  pyproject.toml                     installable as a wheel
  src/coupled_edit_env/
    types.py                         TaskInstance dataclass
    environment.py                   load_environment()
    verifier.py                      AST-aware verifier with cheat detection
    cli.py                           command-line evaluation tool
    gold_solutions.py                reference solutions (one per task)
    partial_solutions.py             graded partial fixes for capability ladder
    tasks/                           8 task instances (4 train, 4 eval)
    adversarial/cheats.py            7 task-agnostic cheat strategies
    leaderboard/
      adapters.py                    OpenAI / Anthropic / OpenRouter adapters
      runner.py                      rollout + scoring + CI computation
  tests/
    test_environment.py              structure and loading
    test_correct_solutions.py        gold solutions all score 1.0
    test_verifier_soundness.py       every cheat x every task, none scores 1.0
  scripts/
    soundness_receipt.py             formal report with Wilson 95% CIs
    capability_ladder.py             graded scoring demonstration
    run_leaderboard.py               multi-model leaderboard runner
```

## The eight tasks

Each task presents a Python project where one function was intentionally
modified. The model must find and repair every downstream caller without
reverting the original change.

| Task | Coupling type | Difficulty | Tests |
|------|--------------|------------|-------|
| 001 Inventory | Return type: int -> dict | Easy | 11 |
| 002 Scheduler | Error handling: None-return -> exception | Easy-Medium | 9 |
| 003 Pipeline | Data shape: flat dict -> nested envelope | Medium | 8 |
| 004 Auth | Sync -> async with transitive propagation | Medium-Hard | 12 |
| 005 Calculator | Token format: strings -> objects | Medium | 12 |
| 006 Event Bus | Handler signature change with multiple consumers | Hard | 10 |
| 007 Cache | Combined: async + return type change | Hard | 14 |
| 008 Formatter | Flat list -> recursive tree | Hard | 11 |

## How the verifier scores

Four layers, in order:

1. **Parse**: extract `--- path/to/file ---` blocks from the response.
2. **Oracle leak check**: regex scan for imports of test files or ground truth.
3. **Revert check**: AST-extracts the modified function and compares against
   per-task revert indicators. Also flags sync/async mismatch.
4. **Behavioral test execution**: run visible + hidden tests in a fresh
   tempdir; score = passed / total.

The verifier never trusts any self-reported metric. Score comes only from
the pytest exit state of the submitted code.

## Soundness receipt (latest run)

```
Trials              : 56  (7 cheats x 8 tasks)
False accepts       : 0
Wilson 95% CI       : [0.0000, 0.0642]

Gold solutions      : 8/8 score exactly 1.0
False rejects       : 0
Wilson 95% CI       : [0.0000, 0.3244]
```

Plus 24 edge-case trials (empty / garbage / wrong-format submissions across
all tasks): all score 0.0 as expected.

Run `python scripts/soundness_receipt.py` to regenerate.

## Capability ladder (latest run)

The verifier produces a graded reward that scales with solution quality:

| Task | Noop | Shape-forgery | Partial fix | Gold |
|------|------|---------------|-------------|------|
| 001 Inventory | 0.18 | 0.18 | 0.64 | 1.00 |
| 002 Scheduler | 0.67 | 0.67 | 0.78 | 1.00 |
| 003 Pipeline | 0.00 | 0.00 | 0.50 | 1.00 |
| 004 Auth | 0.25 | 0.25 | 0.50 | 1.00 |
| 005 Calculator | 0.25 | 0.25 | 0.25 | 1.00 |
| 006 Event Bus | 0.00 | 0.00 | 0.20 | 1.00 |
| 007 Cache | 0.14 | 0.14 | 0.50 | 1.00 |
| 008 Formatter | 0.00 | 0.00 | 0.45 | 1.00 |

All 8 tasks show monotonic increase. The gradient is wide enough for a
training loop to extract a useful signal.

## Library usage

```python
from coupled_edit_env import load_environment
from coupled_edit_env.verifier import verify_solution

env = load_environment(split="eval")

for task in env.tasks:
    prompt = task.to_prompt()
    model_output = call_your_model(prompt)
    result = verify_solution(task, model_output)
    print(f"{task.task_id}: score={result.score:.2f} "
          f"({result.tests_passed}/{result.tests_total})")
```

## Requirements

- Python >= 3.9
- pytest >= 7.0
- No external API calls needed for the environment itself
