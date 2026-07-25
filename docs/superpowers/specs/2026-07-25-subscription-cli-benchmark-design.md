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
from competing with sibling lanes for the same subscription capacity.

The top-level CLI session is the run operator, not the benchmark subject. It
reads a model-specific runplan and drives Cogin. Cogin launches fresh,
isolated subject sessions for benchmark attempts. The operator must never
answer a benchmark task or make the private suite visible to a subject.

## Protocol

Every lane uses the same locked manifest and suite hash.

- Seed: 42
- Calibration: tiers 1-4, two tasks per tier, one repeat, no cognitive retries
- Primary baseline: tiers 1-8, four tasks per tier, three repeats
- Session mode: isolated
- Reasoning effort: medium
- Output mode: prompt JSON
- Tool access: none
- Transport retries: zero
- Recovery study: two cognitive retries, diagnostic feedback, continued
  task-local context
- Ordering: all first attempts finish before any cognitive retry begins

The controller may run one Claude and one Codex lane at the same time. Repeats
inside a lane remain sequential.

## Isolation Boundary

The controller owns the private suite, scorer, suite hash, and run manifest.
Each subject receives only its current public prompt and the required response
shape.

Subject sessions run from a sterile directory with no repository checkout,
private suite, project instructions, plugins, MCP servers, web access, or file
tools. A run is invalid if a subject can inspect the private suite or if an
operator provides task answers.

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
3. Create and lock the Wave 1 manifest before any calibration run.
4. Preflight the requested selector and capture the resolved model, CLI
   version, effort, session mode, and enabled tools.
5. Run calibration.
6. Inspect coverage, parsing, infrastructure failures, and output provenance.
7. If calibration passes, run the three primary repeats.
8. Run recovery attempts only after all first attempts are complete.
9. Render per-run and paired matrix reports.
10. Record completion or a precise invalidation reason.

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
- preserve task-local session identifiers for continued retries;
- detect fallback, rate-limit, authentication, timeout, and process failures;
- keep run outputs isolated by lane and repeat.

The existing generic command provider does not satisfy this contract. Run
operators must not substitute it silently.

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
- Requested and resolved model identifiers are visible in every result.
- Cross-provider reports describe CLI session configurations and do not claim a
  raw-model or general-intelligence winner.

