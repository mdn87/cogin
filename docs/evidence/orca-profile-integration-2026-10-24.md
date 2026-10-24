# Orca profile integration — 2026-10-24

Orca now consumes all eight Matrix 2 model-and-effort profiles and uses one
provisional observation to change a real behavior-selection decision.
[Orca PR #6](https://github.com/mdn87/lugos-orca/pull/6) merged as
`070176cdbca98f2ab58d3bab25821f40010db31e`.

On native Windows through `codex-cli`, client-resolved `gpt-6-luna` at low
effort and adaptation tier 2 now selects
`instruction.check-graph-constraints`. The instruction asks the model to check
graph answers against supplied nodes, directed edges, and output constraints.
Tier 1, medium effort, and GPT-6.1 Sol production controls do not select it.
Tests also cover unknown/different model labels, MCP routing, and macOS.
No skill support, capability, model selection, retry budget, or launch
authority changed. The stable Cogin strategy contract remains unchanged.

The importer pins the published profile Git blob, preserves every original
run ID through an explicit receipt mapping, and retains scores, effort,
provenance, and limitations. All observations are provisional; no strategy
effectiveness is claimed. A hash mismatch stops import before writing.

Verification: 167 behavior/CLI tests passed, with 3 platform skips. Four
production CLI controls passed again on the merged revision. The full suite
initially reported 1,013 passes, 47 skips, and 33 failures. Two dirty-registry
failures passed after the Git index was refreshed; all remaining 31 failures
reproduced at unchanged baseline `66352ca`. Their exact test IDs and the
production advice hashes are in the [verification record](orca-profile-integration-2026-10-24.json).

This verifies Orca's production selection, not an accuracy improvement or
Autowork worker activation. The evidence uses 32 fixed tasks repeated three
times. Model identity is client-selected, and the current selector protocol
cannot automatically enforce the evidence's Codex CLI version. Review the
observation on harness upgrades.

The agent CLI comparison harness remains specification-only and was excluded
from this batch.
