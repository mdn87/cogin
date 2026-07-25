# Claude Opus 5 Runplan

## Lane

- Provider surface: Claude Code with Claude Max subscription
- Requested selector: `opus`
- Pair: GPT-5.6 Sol
- Pair order: 1
- Reasoning effort: medium

## Resolution Gate

Run preflight through the native `claude-cli` provider. Record the exact
provider-resolved model identifier. Proceed only when Claude Code identifies
the lane as Opus generation 5. Disable fallback; a Sonnet, Fable, older Opus,
or unverified alias resolution invalidates the lane.

## Subject Contract

Use fresh, tool-free, isolated Claude Code subject sessions. Disable
customizations, project instructions, plugins, MCP servers, Chrome, session
persistence for isolated attempts, and all built-in tools. Use
machine-readable output and preserve a task-local session only when performing
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

Stop for model switching, unresolved entitlement, private-suite exposure,
enabled subject tools, CLI-version drift, or a changed protocol manifest.
Treat subscription exhaustion and provider errors as infrastructure failures.

## Completion Evidence

Report the requested selector, resolved model, Claude Code version, suite hash,
three run IDs, attempt counts, retry counts, infrastructure gaps, and artifact
paths.

