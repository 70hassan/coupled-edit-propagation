# Capability-Only Leaderboard

Split: `train+eval`
Tasks: 8
Models attempted: 3

Models are ranked by the **lower bound of a bootstrap 95% CI on mean 
score** (Building a Sound RL Environment, Tier 1 Requirement 2). The 
pass-rate Wilson interval is also reported.

## Ranked Results

| Rank | Model | Pass | Mean | Mean 95% CI | Pass 95% CI | Time (s) |
|------|-------|------|-----:|:-----------:|:-----------:|---------:|
| 1 | `gold-baseline` | 8/8 | 1.000 | [1.000, 1.000] | [0.676, 1.000] | 2.7 |
| 2 | `partial-baseline` | 0/8 | 0.477 | [0.360, 0.604] | [0.000, 0.324] | 3.0 |
| 3 | `noop-baseline` | 0/8 | 0.186 | [0.063, 0.358] | [0.000, 0.324] | 1.9 |

## Per-Task Scores

| Model | task_001_inventory | task_002_scheduler | task_003_pipeline | task_004_auth | task_005_calculator | task_006_event_bus | task_007_cache | task_008_formatter |
|---|---|---|---|---|---|---|---|---|
| `noop-baseline` | 0.18 | 0.67 | 0.00 | 0.25 | 0.25 | 0.00 | 0.14 | 0.00 |
| `partial-baseline` | 0.64 | 0.78 | 0.50 | 0.50 | 0.25 | 0.20 | 0.50 | 0.45 |
| `gold-baseline` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## Notes

- Deterministic baselines (noop, partial, gold) require no API access 
  and bracket the expected range for real models.
- Real model rows appear only when the corresponding API key is set.
- Ranking by CI lower bound penalises models with fewer samples or 
  higher variance, per Tier-1 guidance.
- Scaffold: single-turn plain prompt completion. Temperature 0.0.
  This matches the simplest possible scaffold; production-scaffold 
  numbers (Claude Code, Codex CLI) would likely be higher.