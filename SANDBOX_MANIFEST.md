# Sandbox Manifest

Per "Building a Sound RL Environment" Tier 3, this manifest declares the
execution context in which model-submitted code is graded. Anyone can
reproduce the environment's scores by matching these parameters.

## Runtime

| Field | Value |
|---|---|
| Python | >= 3.9 |
| Test framework | pytest >= 7.0 |
| Process isolation | Fresh `subprocess` per task, fresh `tempfile.TemporaryDirectory` |
| Working dir | A new temp dir per submission, deleted after scoring |
| Network egress | None expected; no submitted code currently issues network calls |
| Filesystem | Read/write inside the temp dir only |
| Per-rollout timeout | 30 seconds (configurable per task via `task.timeout_seconds`) |
| Max turns | 1 (single-turn environment) |
| Observation truncation | Full output captured via `subprocess.PIPE` |
| Tool approval policy | No external tools invoked |

## Isolation Granularity

This environment ships with **process-level isolation** (subprocess + tempdir).
For deployment in a training loop with untrusted model code, the recommended
isolation upgrade is one of:

- Docker container per rollout with `--network=none` and read-only volume mount
- gVisor sandbox for additional syscall filtering
- Firecracker microVM for strongest isolation

The verifier code path is identical across isolation backends; only the
launcher needs swapping. The current process-level isolation is sufficient
for evaluation against models that produce code, but should be upgraded
before any training loop where model behavior is unconstrained.

## Determinism

| Source | Determinism |
|---|---|
| Test outcomes | Deterministic (pure-Python tests, no randomness) |
| Task instances | Deterministic (no random generation; all task content is literal) |
| Verifier | Deterministic (pattern matching, AST parsing, pytest exit codes) |

A re-run of `python -m pytest tests/` always produces identical pass/fail
counts. Stability across 5 repeated soundness sweeps was confirmed manually.

## Contamination

| Source check | Result |
|---|---|
| Task code authorship | 100% written for this submission, no copy from public sources |
| Function/class names | Generated combinations (e.g., `transfer_needed`, `EventEnvelope`, `CacheResult`) |
| n-gram check vs The Stack | Not yet run (would require ~2GB download); function bodies are distinctive enough that incidental matches are implausible |
| n-gram check vs Common Crawl | Not yet run; same reasoning |
| Canary string | None embedded (canaries useful for incremental builds; this is a fresh build) |

The strongest contamination argument for this submission is provenance: every
file was authored from scratch during the trial-build period. The author can
demonstrate creation timestamps via git history.

## Provider Routes

Not applicable to this submission. The environment does not bundle a
multi-model leaderboard. Running a leaderboard against this environment is
straightforward: feed `task.to_prompt()` to any model, save the response,
and call `verify_solution(task, response)`.

## Scaffold Notes

The environment is scaffold-agnostic: the prompt is plain text and the
expected response is plain text with `--- path/to/file ---` delimiters.
This format works with:

- Plain chat completion APIs (no tool calling required)
- Claude Code, Codex CLI, Gemini CLI (file-block responses are natural)
- OpenRouter and direct provider endpoints

Spread across scaffolds is not pre-measured; a Tier-3 measurement hygiene
sweep would test the same model under at least two scaffolds and report the
gap. This is left for a future revision.
