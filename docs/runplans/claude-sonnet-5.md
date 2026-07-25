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
persistence for calibration attempts, and all built-in tools. During a primary
repeat, preserve each task's session identifier only until that task's
continued retries finish; never reuse it for another task. Use
machine-readable output.

## Run Sequence

1. Run shared preflight and the eight-task no-retry calibration.
2. Validate model resolution, JSON parsing, scored coverage, latency capture,
   and absence of fallback.
3. Run three full repeats sequentially.
4. Within each repeat, after all 32 first attempts, run up to two diagnostic
   continued-context retries for each initial failure, stopping after exact
   success.
5. Render the lane report. The Wave 1 coordinator renders the Pair 2 comparison
   after both lanes complete.

## Stop Conditions

Stop for model switching, unresolved entitlement, non-subscription
authentication, private-suite exposure, enabled subject tools, CLI-version
drift, or a changed protocol manifest. Treat subscription exhaustion and
provider errors as infrastructure failures.

## Completion Evidence

Report the requested selector, resolved model, Claude Code version, suite hash,
calibration run ID, three successful primary run IDs, abandoned run IDs,
attempt and retry counts, infrastructure gaps, and artifact paths.
