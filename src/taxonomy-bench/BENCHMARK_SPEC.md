# Benchmark specification

## Goal

Estimate the current model-session performance frontier over deterministic tasks generated from a curriculum prerequisite graph. The benchmark measures first-attempt exactness, retry recovery, speed, output reliability, and resource use. It is not a psychometric intelligence test.

## Unit of evaluation

A run is defined by:

- taxonomy version and checksum
- suite seed and suite hash
- requested and provider-resolved model identifiers
- provider SDK or adapter version when available
- reasoning effort or equivalent compute setting
- output mode
- session mode
- retry budget, policy, and context mode
- transport retry setting
- system/developer instructions
- tool availability
- timestamp

Changing any of these produces a different experimental condition.

## Suite construction

A suite contains equal numbers of tasks at tiers 1 through 8. Generation is deterministic for a fixed taxonomy version, seed, maximum tier, and tasks-per-tier value.

The generator selects real topics and edges, constructs bounded local subgraphs, introduces disconnected distractors, and stores private scorer constraints. Public prompts contain no answer key.

### Difficulty tiers

Tier difficulty rises through candidate similarity, edge count, path depth, branch count, simultaneous constraints, required sequence length, and injected integrity faults. Tier numbers are ordinal within this benchmark. They are not comparable to difficulty scales from unrelated benchmarks.

### Exact and partial scoring

The frontier uses exact pass/fail scoring.

Partial scores are diagnostic:

- set tasks use set F1
- topological tasks combine node-set F1 and edge-precedence compliance
- path tasks combine endpoint correctness, valid-edge ratio, and shortest-length correctness
- mastery plans combine required-set F1, dependency compliance, and target-last correctness

Partial scores do not count as passes.

## Retry design

### Cognitive retries

A cognitive retry occurs only after a valid model response is scored as incorrect.

- Blind: the model is told only that the answer is incorrect.
- Feedback: the model receives non-answer diagnostic information, such as missing/extra counts or the number of violated constraints.

### Retry context

- Fresh: resubmit the complete task without linking to the failed response.
- Continued: branch from the failed response using provider conversation state.

### Retry schedule

All first attempts run before retries. This preserves an uncontaminated no-retry baseline, including in continuous-session mode. Retries then branch from each failed task. This design measures recovery without allowing an early retry to alter later first attempts.

### Transport failures

Infrastructure failures are reported separately and excluded from cognitive accuracy denominators. Provider transport retries are configured independently. The default is zero.

## Session modes

### Isolated

Every first attempt starts without prior benchmark task context. This is the preferred mode for comparing base capability across models and effort levels.

### Continuous

First attempts are chained through one provider conversation. This measures performance under accumulated instructions, prior examples, context growth, and possible adaptation. It should not be mixed with isolated results.

## Primary metrics

### Base strength

Difficulty-weighted exact first-attempt score:

`100 × Σ(tier × first_pass) / Σ(tier)`

### Eventual strength

The same formula using pass status after the retry budget.

### Retry lift

`eventual_strength - base_strength`

### Retry recovery rate

`retried first-attempt failures eventually corrected / retried first-attempt failures`

### Reliable frontier

The highest consecutive tier, beginning at tier 1, where at least two-thirds of scored tasks pass exactly. A run can also report a higher peak tier with isolated successes, but that is not considered a reliable frontier.

### Speed

- median first-attempt latency
- p90 first-attempt latency
- median cumulative time to first correct answer
- difficulty-weighted first-pass points per minute

### Resource efficiency

- input tokens
- cached input tokens
- output tokens
- reasoning tokens
- total tokens
- difficulty-weighted first-pass points per 1,000 output tokens

Token accounting depends on provider support and must not be compared when providers define token classes differently.

### Format reliability

- strict JSON rate: the full response parses directly as the requested JSON object
- recovered JSON rate: a JSON object can be extracted from fences or surrounding prose

Schema output mode largely removes this dimension and must be reported separately from prompt output mode.

## Statistical guidance

A single run is a session measurement, not a stable model estimate. For model-level conclusions:

- use at least three repeats per condition
- keep the suite fixed across conditions
- rotate or add seeds to test robustness
- report individual runs and variance
- use confidence intervals for unweighted accuracy
- do not rank configurations whose differences are smaller than run-to-run variation

Latency includes provider and network effects. It is not pure model compute time.

## Threats to validity

- Taxonomy-specific graph reasoning is narrower than general intelligence.
- Semantic tasks may reward prior familiarity with elementary curriculum language.
- Model providers can silently change routing, snapshots, caching, and infrastructure.
- Continuous sessions introduce order and context effects.
- Public suites can become contaminated if widely circulated.
- Tool-enabled agents can inspect private answer keys unless filesystem isolation is enforced.
- A high retry score can reflect correction skill rather than first-pass reasoning strength.
- Structured Outputs can improve syntax without improving semantic correctness.

## Reproducibility record

Archive these files for every published comparison:

- private suite hash, without exposing it to tested agents
- public prompt JSONL
- run JSON
- attempts JSONL
- summary JSON
- model/provider configuration
- package versions
- benchmark version and commit hash
- provider-resolved model ID and SDK version
- taxonomy version and manifest checksums
