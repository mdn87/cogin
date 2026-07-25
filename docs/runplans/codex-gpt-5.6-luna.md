# GPT-5.6 Luna Runplan

## Lane

- Provider surface: Codex CLI with ChatGPT subscription access
- Requested selector: `gpt-5.6-luna`
- Pair: Claude Fable 5
- Pair order: 3
- Reasoning effort: medium

## Resolution Gate

Run preflight through the native `codex-cli` provider and record the exact
provider-resolved identifier. Proceed only when it resolves to GPT-5.6 Luna. A
Sol, Terra, older model, API-key route, or unverified resolution invalidates
the lane.

## Subject Contract

Use fresh, ephemeral Codex subject sessions in a sterile directory. Ignore
user configuration and project rules, disable the shell tool and web search,
load no MCP servers or plugins, and use a read-only sandbox. Consume
machine-readable event output and preserve a task-local session only for
continued retries.

## Run Sequence

1. Run shared preflight and the eight-task no-retry calibration.
2. Validate model resolution, JSON parsing, scored coverage, latency capture,
   and absence of fallback.
3. Run three full repeats sequentially.
4. After first attempts, run up to two diagnostic continued-context retries for
   each initial failure.
5. Render the lane report and Pair 3 comparison.

## Stop Conditions

Stop for model mismatch, non-subscription authentication, private-suite
exposure, enabled subject tools, CLI-version drift, or a changed protocol
manifest. Treat subscription exhaustion and provider errors as infrastructure
failures.

## Completion Evidence

Report the requested and resolved model, Codex CLI version, suite hash, three
run IDs, attempt and retry counts, infrastructure gaps, and artifact paths.

