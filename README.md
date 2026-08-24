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

The implementation, full documentation, and the 188-test suite live in
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
- [`src/taxonomy-bench/STRATEGY_CONTRACT.md`](src/taxonomy-bench/STRATEGY_CONTRACT.md) — the data-only cognitive-strategy export contract
