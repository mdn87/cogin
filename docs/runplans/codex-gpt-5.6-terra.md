# GPT-5.6 Terra Runplan

## Lane

- Provider surface: Codex CLI with ChatGPT subscription access
- Requested selector: `gpt-5.6-terra`
- Pair: Claude Sonnet 5
- Pair order: 2
- Reasoning effort: medium

## Resolution Gate

Run preflight through the native `codex-cli` provider and record the exact
provider-resolved identifier. Proceed only when it resolves to GPT-5.6 Terra.
A Sol, Luna, older model, API-key route, or unverified resolution invalidates
the lane.

## Subject Contract

Use fresh Codex subject sessions in a sterile directory. Calibration sessions
are ephemeral. During a primary repeat, preserve each task's session identifier
only until that task's continued retries finish; never reuse it for another
task. Ignore user configuration and project rules, disable the shell tool and
web search, load no MCP servers or plugins, and use a read-only sandbox.
Consume machine-readable event output.

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

Stop for model mismatch, non-subscription authentication, private-suite
exposure, enabled subject tools, CLI-version drift, or a changed protocol
manifest. Treat subscription exhaustion and provider errors as infrastructure
failures.

## Completion Evidence

Report the requested and resolved model, Codex CLI version, suite hash,
calibration run ID, three successful primary run IDs, abandoned run IDs,
attempt and retry counts, infrastructure gaps, and artifact paths.
