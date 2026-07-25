# GPT-5.6 Sol Runplan

## Lane

- Provider surface: Codex CLI with ChatGPT subscription access
- Requested selector: `gpt-5.6-sol`
- Pair: Claude Opus 5
- Pair order: 1
- Reasoning effort: medium

## Resolution Gate

Run preflight through the native `codex-cli` provider. Record the exact
provider-resolved model identifier. Proceed only when it resolves to GPT-5.6
Sol. A Terra, Luna, older model, API-key route, or unverified resolution
invalidates the lane.

## Subject Contract

Use fresh, ephemeral Codex subject sessions in a sterile directory. Ignore
user configuration and project rules, disable the shell tool and web search,
load no MCP servers or plugins, and use a read-only sandbox. Consume
machine-readable event output and preserve a task-local session only for
continued retries.

## Run Sequence

1. Run the shared preflight.
2. Run the eight-task calibration with no cognitive retries.
3. Validate exact model resolution, strict/recoverable JSON rates, scored
   coverage, latency capture, and absence of fallback.
4. Run three full repeats sequentially.
5. After all first attempts, run up to two diagnostic continued-context
   retries for each first-attempt failure.
6. Render the lane report and Pair 1 comparison.

## Stop Conditions

Stop for model mismatch, non-subscription authentication, private-suite
exposure, enabled subject tools, CLI-version drift, or a changed protocol
manifest. Treat subscription exhaustion and provider errors as infrastructure
failures.

## Completion Evidence

Report the requested and resolved model, Codex CLI version, suite hash, three
run IDs, attempt counts, retry counts, infrastructure gaps, and artifact paths.

