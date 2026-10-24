# Expanded live matrix results — 2026-10-23

Eight conditions completed calibration and three primary repeats each: GPT-6.1 Sol and GPT-6 Luna at low, medium, and high effort, plus corrected medium-effort controls for GPT-5.6 Terra and GPT-5.6 Luna. Four pair reports and one combined report are complete. The 768 primary observations produced 704 exact first attempts and 755 exact eventual results, using 86 diagnostic retry attempts.

## Results

| Model | Effort | Exact first attempts by repeat | First attempts | After recovery | Retry attempts | Median first latency |
|---|---|---|---:|---:|---:|---:|
| `gpt-5.6-terra` | medium | 32/32, 30/32, 32/32 | 94/96 | 96/96 | 2 | 4.161 s |
| `gpt-5.6-luna` | medium | 29/32, 28/32, 28/32 | 85/96 | 95/96 | 12 | 3.352 s |
| `gpt-6.1-sol` | low | 32/32, 32/32, 32/32 | 96/96 | 96/96 | 0 | 4.185 s |
| `gpt-6-luna` | low | 26/32, 25/32, 23/32 | 74/96 | 87/96 | 34 | 3.145 s |
| `gpt-6.1-sol` | medium | 32/32, 32/32, 32/32 | 96/96 | 96/96 | 0 | 4.289 s |
| `gpt-6-luna` | medium | 26/32, 24/32, 26/32 | 76/96 | 93/96 | 27 | 3.196 s |
| `gpt-6.1-sol` | high | 32/32, 32/32, 32/32 | 96/96 | 96/96 | 0 | 4.764 s |
| `gpt-6-luna` | high | 28/32, 29/32, 30/32 | 87/96 | 96/96 | 11 | 3.638 s |

Calibration is excluded from these scores. All 768 primary first responses were strict JSON. Every accepted run had full scored coverage and no infrastructure errors; 0 repeats were abandoned.

The [machine-readable profiles](matrix-2-profiles-2026-10-23.json) contain per-tier first and eventual scores, recovery rates, calibration results, all 32 accepted run IDs, and provenance hashes. A null recovery rate means no first-attempt failures occurred, so recovery ability was not measured.

## What this evidence supports

These are condition profiles over one fixed suite of 32 tasks repeated three times, not 96 independent task samples or a general model ranking. Each tier contains four distinct tasks and twelve observations per condition. The report's descriptive confidence intervals do not establish population-level certainty across new tasks.

All lanes ran sequentially in a fixed order on one subscription family. Latency differences are observations, not controlled causal effects of effort. Each failure could receive at most two continued-context diagnostic retries after the first pass; transport retries were disabled.

The historical Wave 1 Codex runs left effort unset and used GPT-6.1 Sol on all nine recovery turns. Those runs are excluded from this matrix. The new Terra and Luna controls explicitly bind the requested model and effort on both initial and recovery turns. The [Wave 1 correction](wave-1-live-results-2026-10-23.md) preserves the earlier evidence and explains the attribution problem.

## Verification and provenance

- Benchmark 0.5.0, protocol 1.1, source commit `87bff90`, Codex CLI 0.163.0. The [run plan](../runplans/matrix-2.md) records scope, controls, and pair order.
- Manifest: `f992f669372cff59ff2c778d679e2055af246aee90cc3cd39fba0fa7d41b1f92`.
- Private-suite SHA-256: `ce79e1cc1ea9e9e42e6de238a8467676e5e9a1fcf4bf7528083db05c4b1e3fc0`. It matches Wave 1; tasks and answer keys remain private.
- All 32 accepted runs were checked for task coverage, recomputed summary equality, model selectors, explicit effort, CLI version, invocation and policy hashes, finite latencies, and absence of infrastructure errors. Final artifacts omit resumable session IDs.
- All 832 task sessions are distinct across calibrations and primary repeats; they contain 918 scored attempts including recovery.
- Every saved primary turn, including retries, matched its lane's selected model, effort, and read-only sandbox. No subject tool calls were observed. This verifies client selections, not server-side model identity; advertised tool availability was not independently captured.
- All eight lane-report hashes, four pair-report hashes, and manifest-scoped pair completion markers passed validation. The combined report contains exactly 24 primary runs and eight conditions, each with three repeats.
- All 230 automated tests passed after the adapter and controller changes. The wheel built successfully, and release packaging verified 28 checksums and the exact 29-entry archive.

## Artifacts and next boundary

Full reports and raw attempts remain gitignored under `src/taxonomy-bench/wave-runs/matrix-2/`: `reports/pair-1/` through `reports/pair-4/`, eight lane reports, and `reports/combined/matrix.html` with JSON and SHA-256 hashes. The same directory retains `verify_runs.py`, `audit_sessions.py`, and `publish_results.py` for reproducing the checks and publication from the saved runs.

Combined JSON SHA-256: `85661885afcf7c2db40d39842bcecb30e9f7d0fafad9838178ab080be4696e2d`. Combined HTML SHA-256: `b338bd8af7f1f42f7e5e40631883a6c021690767e090c4028c9a4ef7daa89dd8`.

This completes model and effort expansion. These benchmark profiles do not modify the stable strategy contract or implement Orca routing. Feeding the profiles into Orca remains the next separate board step; the agent CLI comparison harness is also unchanged.
