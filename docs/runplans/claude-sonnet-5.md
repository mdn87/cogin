# Claude Sonnet 5 Runplan

## Lane

- Provider surface: Claude Code with Claude Max subscription
- Requested selector: `sonnet`
- Pair: GPT-5.6 Terra
- Pair order: 2
- Reasoning effort: medium

## Resolution Gate

Run preflight through the native `claude-cli` provider and record the exact
provider-resolved identifier. Proceed only when Claude Code identifies Sonnet
generation 5. Disable fallback; Opus, Fable, an older Sonnet, or unverified
alias resolution invalidates the lane.

## Subject Contract

Use fresh, tool-free, isolated Claude Code subject sessions. Disable
customizations, project instructions, plugins, MCP servers, Chrome, session
persistence for isolated attempts, and all built-in tools. Use
machine-readable output and preserve a task-local session only for continued
retries.

## Run Sequence

1. Run shared preflight and the eight-task no-retry calibration.
2. Validate model resolution, JSON parsing, scored coverage, latency capture,
   and absence of fallback.
3. Run three full repeats sequentially.
4. After first attempts, run up to two diagnostic continued-context retries for
   each initial failure.
5. Render the lane report and Pair 2 comparison.

## Stop Conditions

Stop for model switching, unresolved entitlement, private-suite exposure,
enabled subject tools, CLI-version drift, or a changed protocol manifest.
Treat subscription exhaustion and provider errors as infrastructure failures.

## Completion Evidence

Report the requested selector, resolved model, Claude Code version, suite hash,
three run IDs, attempt and retry counts, infrastructure gaps, and artifact
paths.

