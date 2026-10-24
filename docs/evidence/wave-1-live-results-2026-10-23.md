# Claude/Codex Wave 1 results — 2026-10-23

All six lanes completed calibration and three primary repeats, and all three pair reports were published. The 576 primary tasks produced 567 exact first attempts. These totals exclude calibration and abandoned runs.

**Attribution correction, discovered during matrix expansion:** saved CLI turn contexts show that all nine Codex recovery turns used GPT-6.1 Sol, not the requested Terra or Luna. Codex effort was also left unset in both initial and recovery turns despite the report label of medium. First-attempt model selections match their lanes; recovery scores cannot be attributed to those models. The immutable raw reports preserve this historical harness behavior. Matrix 2 binds model and effort explicitly and reruns Terra and Luna as controls.

## Results

| Lane | Primary repeats: exact first attempts | First attempts | Observed final outputs (mixed-model recovery) | Retry attempts | Primary median latency |
|---|---|---:|---:|---:|---:|
| `claude-opus-5` | 32/32, 32/32, 32/32 | 96/96 | 96/96 | 0 | 3.489 s |
| `gpt-5.6-sol` | 32/32, 32/32, 32/32 | 96/96 | 96/96 | 0 | 3.876 s |
| `claude-sonnet-5` | 32/32, 32/32, 32/32 | 96/96 | 96/96 | 0 | 4.186 s |
| `gpt-5.6-terra` | 32/32, 31/32, 31/32 | 94/96 | 96/96 | 2 | 4.141 s |
| `claude-fable-5` | 32/32, 32/32, 32/32 | 96/96 | 96/96 | 0 | 5.147 s |
| `gpt-5.6-luna` | 29/32, 31/32, 29/32 | 89/96 | 96/96 | 7 | 3.365 s |

All 576 primary first responses were strict JSON. Every accepted run had full scored coverage and no infrastructure errors. Opus, Sonnet, Fable, and Sol reached the suite's accuracy ceiling; recovery was therefore not measured for those lanes. The two Terra failures and seven Luna failures received correct outputs on their first retries, but those turns used GPT-6.1 Sol and are not evidence of Terra or Luna recovery ability.

These results describe CLI session configurations on one fixed 32-task suite. They do not establish a general intelligence ranking. The latency figures pool each lane's 96 primary first attempts; paired execution, subscription load, and the small fixed suite limit comparisons.

## Provenance and interruptions

- Benchmark: checked-out Taxonomy Bench 0.5.0; invoked through the Python entry point because the global console entry point still reports 0.3.0.
- Claude Code: 2.1.296. Codex CLI: 0.163.0. Neither CLI version changed during this session.
- Manifest: `dbd05d3d331efeea798b981561b39dc25feb8207e60dafc42046619881cbea26`.
- Private-suite SHA-256: `ce79e1cc1ea9e9e42e6de238a8467676e5e9a1fcf4bf7528083db05c4b1e3fc0`.
- Recorded conditions: medium effort, isolated task sessions, prompt JSON, no-tool policy, zero transport retries, and up to two diagnostic continued-context retries after each repeat's first pass. Claude effort was explicit; Codex effort was not bound by its invocation, so its medium label is not verified.
- Pairs ran in order, with at most one lane per subscription family and aggregation completed before the next pair began.
- Pair 1 calibration was admitted on October 22. All 18 primary runs and the other four calibrations completed in this session, October 23 local time (October 24 UTC).
- Claude model identity is checked from its model-usage output. Codex does not emit independent model identity in the consumed JSONL; its recorded resolved model is the requested selector. Treat Codex identity as client-selected, not server-verified.

Three interrupted runs remain preserved and excluded from scores:

- `wave-claude-opus-5-primary-1-20261024T014045121456Z-58b073937b59`: OAuth refresh-lock failure before the first model response.
- `wave-claude-opus-5-primary-1-20261024T014128654105Z-894255b2f608`: OAuth refresh-lock failure before the first model response.
- `wave-gpt-5.6-terra-primary-2-20261024T015542712271Z-532e9063c4e7`: Repeat 2 interrupted during recovery because the Codex resume command rejected misplaced options.

The Claude OAuth lock cleared before the approved backup operation could rename it. No lock backup or credential edit was made; the next whole-repeat restart succeeded.

Terra's first recovery attempt exposed an adapter bug: `--sandbox` and `--cd` appeared after `codex exec resume`, where the CLI rejected them. Commit `40da894` moves them to the parent `exec` command and explicitly reads retry text from stdin. Sandbox policy, subject root, model selection, suite, manifest, and scoring were unchanged. The failed repeat was restarted from task 1 after a separate harmless two-turn continuation probe passed. Both accepted Terra recovery attempts and all seven Luna retries then produced correct outputs; the later session-context audit found that they used GPT-6.1 Sol. The probe is not part of the benchmark results.

## Verification

- The initial 225-test suite passed; after the adapter fix, all 226 tests passed, including a regression test against the installed CLI argument parser. That test reproduced the original rejection before the fix.
- A separate live continuation probe verified the same session and retained context without using benchmark tasks. It did not check the resumed model; the later audit caught the model switch.
- The repaired wheel built successfully; packaging verified 28 SHA-256 entries and the exact 29-entry archive.
- Verified all 24 accepted runs: six calibrations, 18 primary repeats, 624 distinct task sessions, and 633 scored attempts including nine recovery attempts.
- Checked exact task coverage, finite nonnegative latencies, recorded selectors and CLI versions, manifest/suite and invocation/policy hashes, and absence of classified infrastructure errors in accepted runs. Recorded selectors alone did not detect the recovery model switch.
- Recomputed every accepted run summary and matched it to the saved summary. Checked removal of resumable session IDs from finalized task and attempt fields.
- Validated all six lane-report hashes and all three pair-report hashes and manifest-scoped aggregation markers. Each pair contains exactly six accepted primary runs.
- Abandoned envelopes remain private. Their process errors are infrastructure outcomes and do not enter the accepted-run totals.

## Local artifacts

The private suite, raw attempts, and full reports remain gitignored under `src/taxonomy-bench/wave-runs/wave-1/`:

- `reports/pair-1/matrix.html`, `reports/pair-2/matrix.html`, and `reports/pair-3/matrix.html`: paired reports, each with matching matrix JSON and hashes.
- `reports/lane-<lane>/`: lane reports.
- `runs/<run ID>/`: accepted per-run reports and metrics.
- `envelopes/`: durable attempts, including abandoned runs.

| Lane | Phase | Run ID |
|---|---|---|
| `claude-opus-5` | Calibration | `wave-claude-opus-5-calibration-0-20261022T050414096206Z-0f4022fa9cd7` |
| `claude-opus-5` | Primary 1 | `wave-claude-opus-5-primary-1-20261024T014524106303Z-67c5b4608d1b` |
| `claude-opus-5` | Primary 2 | `wave-claude-opus-5-primary-2-20261024T014732824723Z-00e8912abc1d` |
| `claude-opus-5` | Primary 3 | `wave-claude-opus-5-primary-3-20261024T014945714593Z-48ab22993733` |
| `gpt-5.6-sol` | Calibration | `wave-gpt-5.6-sol-calibration-0-20261022T050416521961Z-a21481211700` |
| `gpt-5.6-sol` | Primary 1 | `wave-gpt-5.6-sol-primary-1-20261024T014044998690Z-951d7b76f295` |
| `gpt-5.6-sol` | Primary 2 | `wave-gpt-5.6-sol-primary-2-20261024T014255717902Z-53f822cf0997` |
| `gpt-5.6-sol` | Primary 3 | `wave-gpt-5.6-sol-primary-3-20261024T014517066681Z-8ff8f469d2ee` |
| `claude-sonnet-5` | Calibration | `wave-claude-sonnet-5-calibration-0-20261024T015224424326Z-fa8fbc97373b` |
| `claude-sonnet-5` | Primary 1 | `wave-claude-sonnet-5-primary-1-20261024T015302739798Z-7370c8579d2d` |
| `claude-sonnet-5` | Primary 2 | `wave-claude-sonnet-5-primary-2-20261024T015611499303Z-a9aec6324187` |
| `claude-sonnet-5` | Primary 3 | `wave-claude-sonnet-5-primary-3-20261024T015917628563Z-9ecf2fc13fb4` |
| `gpt-5.6-terra` | Calibration | `wave-gpt-5.6-terra-calibration-0-20261024T015224410746Z-05c74cea21a2` |
| `gpt-5.6-terra` | Primary 1 | `wave-gpt-5.6-terra-primary-1-20261024T015257289470Z-710118580994` |
| `gpt-5.6-terra` | Primary 2 | `wave-gpt-5.6-terra-primary-2-20261024T020108368355Z-e95d58cf66d2` |
| `gpt-5.6-terra` | Primary 3 | `wave-gpt-5.6-terra-primary-3-20261024T020339816548Z-7127e1ba85e0` |
| `claude-fable-5` | Calibration | `wave-claude-fable-5-calibration-0-20261024T020654507896Z-3fb45a4a47d5` |
| `claude-fable-5` | Primary 1 | `wave-claude-fable-5-primary-1-20261024T020735699260Z-e7805fc9300b` |
| `claude-fable-5` | Primary 2 | `wave-claude-fable-5-primary-2-20261024T021051932883Z-dedcc2e98752` |
| `claude-fable-5` | Primary 3 | `wave-claude-fable-5-primary-3-20261024T021415412474Z-d7f99758aa95` |
| `gpt-5.6-luna` | Calibration | `wave-gpt-5.6-luna-calibration-0-20261024T020654403665Z-9b78ee969e79` |
| `gpt-5.6-luna` | Primary 1 | `wave-gpt-5.6-luna-primary-1-20261024T020722018690Z-30fbe4d78ef9` |
| `gpt-5.6-luna` | Primary 2 | `wave-gpt-5.6-luna-primary-2-20261024T020934131812Z-186f773a2d6e` |
| `gpt-5.6-luna` | Primary 3 | `wave-gpt-5.6-luna-primary-3-20261024T021134623622Z-a0e649c6c934` |

Taxonomy attribution: Marble Skill Taxonomy (v1), Generative Spark, Inc. (Marble), https://withmarble.com; ODbL 1.0 for the database and CC BY-SA 4.0 for content. This summary contains no private task text or answer keys.
