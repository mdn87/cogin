# Expanded model and effort matrix

## Scope and acceptance

Matrix 2 extends the completed Wave 1 reports with GPT-6.1 Sol and GPT-6 Luna at explicit low, medium, and high reasoning effort. It also reruns GPT-5.6 Terra and GPT-5.6 Luna at explicit medium effort to replace their historical mixed-model recovery evidence. The fixed suite, calibration task IDs, scoring, task isolation, and three-repeat design stay the same. This step does not integrate Orca or build an agent-task harness.

Completion requires eight admitted calibrations, 24 complete primary repeats, four paired reports, and one combined profile report. Verify every saved primary turn's selected model, reasoning effort, and read-only sandbox against the lane, including recovery turns. Preserve and exclude infrastructure-abandoned repeats. Publish results and limitations, with no private task text or answer keys.

## Schedule

| Pair | First lane | Second lane |
|---|---|---|
| 1 | gpt-5.6-terra-medium | gpt-5.6-luna-medium |
| 2 | gpt-6.1-sol-low | gpt-6-luna-low |
| 3 | gpt-6.1-sol-medium | gpt-6-luna-medium |
| 4 | gpt-6.1-sol-high | gpt-6-luna-high |

All lanes share the Codex subscription family and run sequentially. Finish each pair report before starting the next pair. Model and effort support were checked against the current local CLI model catalog; live calibration is the entitlement check.

## Protocol 1.1

The controller stores effort in each lane and its provider metadata, includes it in the invocation hash, passes it to both fresh and resumed CLI turns, and labels it in run and lane reports. The protocol hash differs from Wave 1's medium-only declaration; old manifests remain unchanged. Existing pair barriers, family locks, eight-task calibration, three 32-task repeats, zero transport retries, and at most two continued-context diagnostic retries still apply.

Codex uses `-m <selector>` on both fresh and resumed turns and `-c model_reasoning_effort="<level>"`. The [official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) documents this effort setting. Saved local turn contexts independently verify what the client selected; they are not server-side model identity proof.

Historical Codex runs did not explicitly set effort. Their recovery commands also omitted the model, causing the nine recovery turns to use the default GPT-6.1 Sol. Do not pool that recovery evidence with the corrected model-specific profiles or treat historical medium labels as verified effort conditions. See the correction in the Wave 1 results summary.

## Execution

Use the checked-out Python entry point (0.5.0), the existing approved subject root and controller root, and the original private suite. Prepare a separate directory with `wave prepare --lanes matrix-2`. Then use `wave preflight`, `wave run`, and `wave aggregate` with that manifest, following the schedule above. Never edit a prepared manifest to accommodate CLI drift.

The six new conditions are the core expansion. The two legacy controls validate same-model recovery after the adapter correction. Report first-attempt and eventual accuracy separately; when no failures occur, recovery ability is unmeasured. Interpret latency and token counts as observations, not a general ranking.
