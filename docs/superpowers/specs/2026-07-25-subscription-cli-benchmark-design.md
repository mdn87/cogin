# Subscription CLI Benchmark Design

## Goal

Measure six current subscription-backed coding-agent configurations with one
frozen Taxonomy Bench protocol, then reuse that protocol for older model
generations.

Wave 1 covers:

- Claude Sonnet 5, Opus 5, and Fable 5 through Claude Code with a Max
  subscription.
- GPT-5.6 Sol, Terra, and Luna through Codex with ChatGPT subscription access.

The result is a profile of each CLI session configuration. It is not a claim
about the raw foundation model independent of its agent harness.

## Execution Shape

Only two lanes may run concurrently: one Claude lane and one Codex lane. The
role-matched pair order is:

1. Claude Opus 5 and GPT-5.6 Sol
2. Claude Sonnet 5 and GPT-5.6 Terra
3. Claude Fable 5 and GPT-5.6 Luna

Runs within the same subscription family are sequential. This prevents models
from competing with sibling lanes for the same subscription capacity. Pair
N+1 does not start until both lanes in Pair N have completed and the coordinator
has rendered that pair's report.

The top-level CLI session is the run operator, not the benchmark subject. It
reads a model-specific runplan and drives Cogin. Cogin launches fresh,
isolated subject sessions for benchmark attempts. The operator must never
answer a benchmark task or make the private suite visible to a subject.

## Protocol

Every lane uses the same locked manifest and suite hash.

- Seed: 42
- Calibration: a fixed eight-task subset of the full suite containing the first
  two task IDs in ascending lexical order from each of tiers 1-4, recorded in
  the manifest, one repeat, no cognitive retries
- Primary baseline: tiers 1-8, four tasks per tier, three repeats
- Session mode: isolated
- Reasoning effort: medium
- Output mode: prompt JSON
- Tool access: none
- Transport retries: zero
- Recovery study: up to two cognitive retries per first-attempt failure,
  stopping after exact success, with diagnostic feedback and continued
  task-local context
- Ordering: within each independent 32-task repeat, all first attempts finish
  before any cognitive retry for that repeat begins

The controller may run one Claude and one Codex lane at the same time. Repeats
inside a lane remain sequential. Recovery for repeat N completes before repeat
N+1 begins; there is no lane-wide, pair-wide, or wave-wide retry barrier.

## Isolation Boundary

The controller owns the private suite, scorer, suite hash, and run manifest.
Each subject receives only its current public prompt and the required response
shape.

Subject sessions run from a sterile directory with no repository checkout,
private suite, project instructions, plugins, MCP servers, web access, or file
tools. Each task receives its own session. For a primary repeat, that task-local
session identifier and public conversation state may persist only until its
continued retries finish; it is never reused by another task. Calibration
sessions, which have no retries, are ephemeral. A run is invalid if a subject
can inspect the private suite or if an operator provides task answers.

## Model Resolution

The requested selector and provider-resolved identifier are both recorded.

- Codex selectors are `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`.
- Claude selectors are `opus`, `sonnet`, and `fable`.

Claude aliases are accepted only when preflight resolves them to the intended
generation-5 lane. Automatic fallback and silent model switching are disabled.
A mismatch stops the lane before calibration.

## Run Lifecycle

1. Validate the Cogin checkout and run the automated tests.
2. Validate subscription authentication without exposing credentials.
3. Generate the full 32-task private suite, select and record the fixed
   calibration task IDs from that suite, then lock the Wave 1 manifest and suite
   hash before any calibration run.
4. Preflight the requested selector and capture the resolved model, CLI
   version, effort, session mode, and enabled tools.
5. Run calibration.
6. Apply the objective calibration admission gate:
   - all eight first attempts have durable attempt records;
   - requested and resolved models match and no fallback occurs;
   - suite hash, task IDs, instruction hash, tool-policy hash, invocation hash,
     and CLI version match the manifest;
   - all eight tasks are scored and have nonnegative latency;
   - no infrastructure, isolation, parser-process, or report-generation failure
     occurs.
   A subject's malformed JSON is a scored model outcome and does not fail
   calibration. A parser crash, missing attempt, or unscored harness result does.
7. If calibration passes, run the three primary repeats.
8. Within each repeat, run recovery attempts only after that repeat's 32 first
   attempts are complete.
9. Render per-run and lane reports.
10. After both lanes in a pair complete, have the Wave 1 coordinator run the
    post-pair aggregation once and render the paired matrix report.
11. Record completion or a precise invalidation reason.

Rate limits, authentication failures, unavailable models, and provider
outages are infrastructure outcomes. They are never scored as incorrect model
answers. A repeat interrupted by infrastructure failure is restarted from the
beginning after capacity recovers.

## Readiness Gate

Execution requires native subscription CLI adapters that:

- invoke Codex and Claude Code without API keys or pay-as-you-go fallback;
- parse machine-readable CLI output;
- record requested and resolved model identifiers;
- enforce sterile, tool-free subject sessions;
- preserve task-local session identifiers for continued retries and discard
  them after the task's recovery phase;
- detect fallback, rate-limit, authentication, timeout, and process failures;
- keep run outputs isolated by lane and repeat.

It also requires controller support that:

- creates an immutable manifest containing the full-suite hash, fixed
  calibration task IDs, protocol version, base-instruction hash, tool-policy
  hash, invocation-configuration hash, and diagnostic-feedback-policy hash;
- enforces a cross-process family lock allowing at most one Claude and one
  Codex lane;
- checkpoints first-attempt and recovery phases within each repeat;
- abandons and restarts an entire repeat after infrastructure interruption
  while preserving the abandoned run's provenance;
- records lane completion and lets one Wave 1 coordinator aggregate a pair only
  after both lanes are complete.

The existing generic command provider does not satisfy this contract. The
native adapters and the controller capabilities above are both implementation
work. Run operators must not substitute incomplete or generic behavior
silently.

## Artifacts

The shared runplan index is `docs/runplans/README.md`. Each model has a
dedicated runplan in that directory. `docs/runplans/OPERATOR-PROMPT.md`
contains the reusable top-level prompt.

Private suites and raw run artifacts are not committed. Published summaries
must preserve provenance and upstream Marble attribution without exposing
answer keys.

## Success Criteria

- All six selectors pass model-resolution preflight.
- Every scored condition uses the same suite hash and protocol manifest.
- No run exposes private scorer data to a subject.
- Calibration completes without unresolved infrastructure or parsing defects.
- Each primary lane produces three complete repeats and a rendered report.
- Calibration run IDs and any abandoned run IDs remain in provenance.
- Requested and resolved model identifiers are visible in every result.
- Cross-provider reports describe CLI session configurations and do not claim a
  raw-model or general-intelligence winner.
