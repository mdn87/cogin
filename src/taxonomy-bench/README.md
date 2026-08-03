# Taxonomy Bench

Taxonomy Bench converts the [Marble Skill Taxonomy](https://github.com/withmarbleapp/os-taxonomy) into a deterministic, progressively difficult AI benchmark. It tests how far a model gets, how quickly it gets there, and how much it improves when allowed to retry.

The benchmark is designed for two distinct questions:

1. **Base session strength** - what the model gets exactly right on its first attempt.
2. **Recovery strength** - which first-attempt failures it fixes with blind or diagnostic retries.

It does not claim to measure general intelligence or produce an IQ-equivalent score. It produces a session-specific strength profile over semantic matching, dependency reasoning, graph traversal, planning, integrity checking, output reliability, latency, and token use.

## What it measures

Each seeded suite contains eight difficulty tiers built from the taxonomy's topic records and prerequisite DAG.

| Task family | What it tests |
|---|---|
| Semantic topic identification | Matching descriptions and evidence to closely related topic names |
| Direct prerequisites | Filtering local graph edges and respecting edge direction |
| Reverse unlocks | Reversing the dependency relation correctly |
| Transitive prerequisites | Multi-hop closure with depth, strength, and distractor constraints |
| Topological ordering | Producing any valid order under multiple dependency constraints |
| Shortest path | Finding a minimum prerequisite-to-target path through branches |
| Mastery planning | Constructing the minimal remaining hard-prerequisite learning sequence |
| Integrity audit | Detecting unknown endpoints, self-dependencies, and invalid edge strengths |

The main report includes:

- `base_strength_0_100`: difficulty-weighted exact correctness on first attempts
- `eventual_strength_0_100`: the same score after allowed retries
- `retry_lift_points`: eventual minus first-attempt weighted score
- `retry_recovery_rate`: fraction of retried first-attempt failures corrected
- `reliable_frontier_first`: highest consecutive tier with at least two-thirds exact passes
- first-attempt and eventual accuracy by tier
- scored coverage plus first-attempt and retry infrastructure error counts
- median and p90 latency
- strict JSON compliance and parser-recovered JSON rates
- input, output, cached-input, reasoning, and total token counts when the provider exposes them
- provider-returned model identifiers when available, which can reveal snapshot or routing differences
- difficulty-weighted points per minute and per 1,000 output tokens

## Experimental controls

The harness separates effects that are commonly conflated:

- **Cognitive retries** are model attempts after an incorrect answer.
- **Transport retries** are SDK or network retries after infrastructure failures.
- **Isolated sessions** start each task without prior task context.
- **Continuous sessions** chain first attempts through one Responses API conversation.
- **Fresh retries** resubmit the full task without the failed response in context.
- **Continued retries** branch from the failed response and let the model reconsider it.
- **Blind retries** only say the prior answer was incorrect.
- **Feedback retries** include diagnostic counts or constraint failures without revealing the answer.
- **Prompt output mode** measures both reasoning and JSON-format reliability.
- **Schema output mode** uses Structured Outputs to isolate semantic and graph reasoning from formatting errors.

All first attempts are completed before any cognitive retries. This keeps the no-retry baseline paired with the retry result and prevents an earlier retry from altering a later task's first-attempt context.

The OpenAI SDK provider sets transport retries to zero unless explicitly changed. This prevents hidden SDK retries from contaminating the intended no-retry condition.

## Requirements

- Python 3.10 or newer
- A local checkout of `withmarbleapp/os-taxonomy`
- The `openai` Python package only when using the OpenAI provider
- Claude Code and/or Codex CLI with subscription authentication for Wave runs

From the directory containing the unpacked `taxonomy-bench/` folder, clone the taxonomy beside it and install the CLI:

```bash
git clone https://github.com/withmarbleapp/os-taxonomy.git os-taxonomy
cd taxonomy-bench
python -m venv .venv
source .venv/bin/activate
pip install -e ".[openai]"
```

The source script also runs without installation:

```bash
python taxonomy_bench.py validate --taxonomy sample_data
```

Set an API key for OpenAI runs:

```bash
export OPENAI_API_KEY="..."
```

## Validate the source taxonomy

```bash
python taxonomy_bench.py validate \
  --taxonomy ../os-taxonomy \
  --verify-checksums
```

The benchmark loads `data/topics.json`, `data/dependencies.json`, and `data/manifest.json`. Curriculum standards are not required.

## Generate a reproducible suite

```bash
python taxonomy_bench.py generate \
  --taxonomy ../os-taxonomy \
  --seed 42 \
  --max-tier 8 \
  --tasks-per-tier 4 \
  --out suites/taxonomy-v1-seed42.private.json
```

This creates:

- a private suite containing hidden scorer data
- a public JSONL prompt file with no answer keys
- a response-template JSONL file for testing a model through a separate UI

Do not expose the private suite to an agent that can inspect its filesystem. It contains the hidden answers and validation constraints.

## Run the subscription CLI Wave

Wave mode measures complete Claude Code or Codex CLI session configurations,
not foundation models in isolation. It enforces subscription authentication,
model identity, tool-free isolated subjects, one task-local session per task,
family locks, role-matched pair barriers, and whole-repeat restart after
infrastructure failure.

Before preparation, create and explicitly approve two directories outside this
repository: a controller-global control root and a sterile subject root. The
CLI requires both to exist; it never chooses or creates an external path.

```powershell
taxonomy-bench wave prepare `
  --suite suites/taxonomy-v1-seed42.private.json `
  --out wave-runs/wave-1 `
  --control-root C:/operator-approved/cogin-control

taxonomy-bench wave preflight `
  --manifest wave-runs/wave-1/manifest.json `
  --lane claude-opus-5 `
  --subject-root C:/operator-approved/sterile-subjects

taxonomy-bench wave run `
  --manifest wave-runs/wave-1/manifest.json `
  --lane claude-opus-5 `
  --subject-root C:/operator-approved/sterile-subjects

taxonomy-bench wave aggregate `
  --manifest wave-runs/wave-1/manifest.json `
  --pair 1
```

Run one Claude and one Codex lane concurrently within a pair. Pair 2 remains
closed until Pair 1 has two complete lane reports and its pair aggregation
marker; the same rule applies to Pair 3. Authentication, entitlement, rate
limit, timeout, fallback, model mismatch, and process failures abandon the
affected repeat and are never scored as wrong answers. Raw private suites,
run envelopes, and subject state under `wave-runs/` remain uncommitted.

The generic `run` command intentionally rejects `claude-cli` and `codex-cli`;
subscription subjects must use the immutable manifest and Wave gates.

## Run one model and effort level

```bash
python taxonomy_bench.py run \
  --suite suites/taxonomy-v1-seed42.private.json \
  --provider openai \
  --model YOUR_MODEL_ID \
  --effort medium \
  --session isolated \
  --retries 2 \
  --retry-policy feedback \
  --retry-context continued \
  --output-mode prompt \
  --transport-retries 0 \
  --tool-access none \
  --condition-label "isolated prompt-mode baseline" \
  --out runs
```

The first-attempt fields in this one run are the paired **without-retries** result. The eventual fields are the **with-retries** result, so a separate no-retry run is not required. Use `--retries 0` when an explicitly retry-free execution is needed.

The output directory contains:

- `summary.json`
- `run.json`
- `attempts.jsonl`
- `report.html`
- a copy of the private suite and public prompt file

`report.html` is an evidence-first trace of Benchmark Progression, not a curriculum path. It labels each first attempt as exact, non-exact with partial/diagnostic evidence, unparseable/wrong-shape, or unscored infrastructure. Retries appear below their originating task as later Recovery-phase attempts; they never change first-pass curves.

The progression view marks the first miss, the reliable frontier (the highest consecutive tier meeting the existing two-thirds exact-pass rule), instability onset, sustained breakdown, and any peak isolated success. Its rolling window uses scored tasks only and shows infrastructure gaps rather than treating them as incorrect answers. Unsupported-output is a graph-output proxy, not a general hallucination rate. Marble-to-agentic-coding mapping is a routing heuristic, not proof of coding performance. Missing usage is shown as **not reported**; a condition without retry measurement is **not measured**.

Reasoning effort values are passed through to the provider because supported values are model-dependent.

## Compare models and effort levels

```bash
python taxonomy_bench.py matrix \
  --suite suites/taxonomy-v1-seed42.private.json \
  --provider openai \
  --models MODEL_ID_A,MODEL_ID_B \
  --efforts low,medium,high \
  --repeats 3 \
  --session isolated \
  --retries 2 \
  --retry-policy feedback \
  --retry-context continued \
  --output-mode schema \
  --transport-retries 0 \
  --out matrix-runs
```

`matrix.html` groups fixed-suite, identical conditions and labels 1, 2, and 3+ repeats as session, limited, and repeated evidence. It shows Wilson intervals, flip rates, task-family behavior, and links to every individual run. It does not produce a composite winner or rank individual runs.

For an inexpensive smoke test, use `--max-tier 4 --tasks-per-tier 2 --repeats 1`.

## Test a current chat or UI session manually

Generate the suite and use the public prompt JSONL. For a continuous-session measurement, paste each prompt into the same target session in order. For an isolated measurement, use a fresh session for every prompt. Record the raw response and elapsed time in the response template:

```json
{"task_id":"t01-01-semantic_match","attempt":1,"text":"{\"id\":\"mt_...\"}","latency_ms":1820}
```

Score the collected file without exposing the answer key to the tested session:

```bash
python taxonomy_bench.py score \
  --suite suites/taxonomy-v1-seed42.private.json \
  --responses responses.jsonl \
  --model "ChatGPT UI session" \
  --effort "selected UI effort" \
  --source manual-session \
  --out scored-runs
```

Use one response row per attempt. Add contiguous rows with `"attempt": 2`, `3`, and so on to measure manual retries. Keep the private suite outside the tested model's accessible files or tools.

## Test a local model or another provider

The command provider sends each prompt to a process on standard input and reads the model answer from standard output:

```bash
python taxonomy_bench.py run \
  --suite suites/taxonomy-v1-seed42.private.json \
  --provider command \
  --command "python my_model_wrapper.py" \
  --model local-model-name \
  --effort default \
  --session isolated \
  --retries 1 \
  --retry-context fresh
```

The wrapper receives `TAXONOMY_BENCH_MODEL` and `TAXONOMY_BENCH_EFFORT` as environment variables. Continuous session mode requires a provider that exposes conversation-state identifiers, so it is not available through the simple command adapter.

## Recommended evaluation protocol

For a defensible comparison:

1. Generate one private suite and reuse it for every model and effort condition.
2. Use isolated sessions for base capability comparisons.
3. Run continuous sessions separately to measure context accumulation, adaptation, and fatigue.
4. Use prompt output mode and schema output mode as separate experiments.
5. Keep transport retries at zero or report them explicitly.
6. Use at least four tasks per tier and three repeated runs for serious comparisons.
7. Compare raw metrics and confidence intervals, not only the weighted score.
8. Record model snapshot IDs, provider, effort, tool access, system instructions, date, and region when available.

A retry lift is not equivalent to higher base intelligence. A model can have weak first-attempt performance and strong error recovery, or the reverse. The report keeps those dimensions separate.

## Tests

```bash
pip install -e ".[test]"
pytest -q
```

The included synthetic fixture validates all eight task tiers without redistributing Marble's dataset.

## Licensing and attribution

The benchmark code is MIT licensed. The Marble taxonomy data is not included.

Generated suites and reports can contain Marble-authored text and taxonomy relationships. Those outputs may be subject to the upstream ODbL 1.0 and CC BY-SA 4.0 terms. The harness embeds this attribution in generated reports:

> Marble Skill Taxonomy (v1) · © Generative Spark, Inc. (Marble) · https://withmarble.com · licensed under ODbL 1.0 (database) and CC BY-SA 4.0 (content).

Review the upstream repository's `LICENSE`, `LICENSE-CONTENT`, and `PROVENANCE.md` before redistributing generated suites or modified taxonomy data.
