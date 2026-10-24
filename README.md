# cogin

**Taxonomy Bench** — a provider-independent AI benchmark built from the
[Marble Skill Taxonomy](https://github.com/withmarbleapp/os-taxonomy). It turns
the taxonomy's topic graph into eight progressively harder task families and
measures how far a model gets on its first attempt, how quickly, and how much it
recovers when allowed to retry.

It does **not** claim to measure general intelligence. It produces a
session-specific strength profile over semantic matching, dependency reasoning,
graph traversal, planning, integrity checking, output reliability, latency, and
token use.

## What it measures

Eight difficulty tiers built from the taxonomy's records and prerequisite DAG:
semantic topic identification, direct prerequisites, reverse unlocks, transitive
prerequisites, topological ordering, shortest path, mastery planning, and
integrity audit. Reports separate **base strength** (first-attempt exact
correctness) from **recovery strength** (failures fixed on retry), and isolate
cognitive retries from transport retries so an SDK retry never contaminates the
no-retry baseline.

## The code and tests

The implementation, full documentation, and automated tests live in
[`src/taxonomy-bench/`](src/taxonomy-bench/) — see its
[README](src/taxonomy-bench/README.md) for the complete metric list, the
experimental controls, and provider setup.

```bash
# from src/taxonomy-bench, with os-taxonomy cloned beside it
python -m venv .venv && source .venv/bin/activate
pip install -e ".[openai]"
python taxonomy_bench.py validate --taxonomy sample_data
```

## Layout

- [`src/taxonomy-bench/`](src/taxonomy-bench/) — the benchmark package, CLI, and tests
- [`src/agent-cli-harness/`](src/agent-cli-harness/) — separate pinned experiment for agent CLI repository work
- [`docs/evidence/agent-cli-comparison-2026-10-24.md`](docs/evidence/agent-cli-comparison-2026-10-24.md) — unattended CLI results and remaining comparison limits
- [`src/taxonomy-bench/STRATEGY_CONTRACT.md`](src/taxonomy-bench/STRATEGY_CONTRACT.md) — the data-only cognitive-strategy export contract
- [`docs/runplans/matrix-2.md`](docs/runplans/matrix-2.md) — the expanded model and reasoning-effort experiment
- [`docs/evidence/matrix-2-results-2026-10-23.md`](docs/evidence/matrix-2-results-2026-10-23.md) — live results, limitations, and machine-readable condition profiles
- [`docs/evidence/orca-profile-integration-2026-10-24.md`](docs/evidence/orca-profile-integration-2026-10-24.md) — imported profiles and verified Orca behavior selection
