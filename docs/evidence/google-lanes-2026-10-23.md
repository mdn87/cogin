# Google lane results — 2026-10-23

Both Google lanes completed the Wave 1 protocol through Antigravity CLI 1.4.6. Each lane passed its eight-task calibration and all 96 primary first attempts across three 32-task repeats. The controller published both lane reports and the pair report.

## Results

| Lane | Calibration | Primary repeats (exact first attempts) | Strict JSON | Primary median latency |
|---|---:|---|---:|---:|
| `gemini-4-argon-medium` | 8/8 | 32/32, 32/32, 32/32 | 100% | 7.015 s |
| `gemini-3.8-flash-medium` | 8/8 | 32/32, 32/32, 32/32 | 100% | 9.854 s |

Both lanes had 100% scored coverage and a base strength score of 100 in each primary repeat. No recovery attempts were needed, and there were no infrastructure errors, abandoned runs, or invalidations. Calibration is excluded from the primary results.

These results measure CLI session configurations on one fixed suite. Both lanes reached the accuracy ceiling, so this run does not distinguish their accuracy or measure recovery ability. The latency figures pool the 96 primary first attempts for each lane; they are observations from sequential runs, not a controlled speed ranking.

## Provenance

- Benchmark: checked-out Taxonomy Bench 0.5.0. The global console entry point still reports 0.3.0, so execution used `python src/taxonomy-bench/taxonomy_bench.py`.
- Authentication: subscription; requested and resolved selectors matched the lane IDs in every attempt.
- Manifest: `cd5854e56d052feaa899bd64bb14902ab25e542593841ff44673d91f85e28d8c`.
- Private-suite SHA-256: `ce79e1cc1ea9e9e42e6de238a8467676e5e9a1fcf4bf7528083db05c4b1e3fc0`.
- Conditions: medium effort, isolated task sessions, prompt JSON, no tools, zero transport retries, and up to two diagnostic continued-context retries after the first pass. Both lanes ran sequentially under the Antigravity family lock.
- The original agy 1.4.5 manifest (`738bc787c2216856989facac94f21b9ee1671e555d1e126e749ee8568f77e2c5`) remains untouched and has no lane runs.
- The initial guarded version probe returned 1.4.5, but isolated preflight returned 1.4.6. The provider environment contained `AGY_CLI_DISABLE_AUTO_UPDATE=1`; the cause of the intervening binary replacement was not established. A fresh manifest was prepared in a new directory before calibration. Suite hash, protocol, calibration IDs, instructions, lanes, and control root matched the old manifest.
- Identity remains client-reported: agy lists and selects the model, then echoes the selector in its init event. It does not supply an independent server-reported model identifier. Tools are advertised but denied by the isolated permission profile; see [CLI characterization](agy-cli-characterization.md).

## Verification

- All 225 automated tests passed before the runs; no benchmark code changed.
- Verified all 208 attempts: 16 calibration and 192 primary, with exact task coverage, nonnegative finite latency, strict JSON, and no infrastructure errors.
- Verified manifest and suite hashes, per-run configuration and policy hashes, model selectors, and agy version 1.4.6.
- Verified 208 distinct task-session hashes and removal of resumable session IDs from finalized run artifacts.
- Recomputed every run summary and matched it to the saved summaries.
- Validated the hashes of both lane reports and the pair report; the pair contains exactly six accepted primary runs and has its manifest-scoped aggregation marker.

## Local artifacts

The private suite, transcripts, and full reports remain gitignored under `src/taxonomy-bench/wave-runs/google-1-agy146/`:

- `reports/pair-1/matrix.html` and `matrix.json`: paired report.
- `reports/lane-gemini-4-argon-medium/` and `reports/lane-gemini-3.8-flash-medium/`: lane reports.
- `runs/<run ID>/`: per-run report and metrics.

| Lane | Phase | Run ID |
|---|---|---|
| `gemini-4-argon-medium` | Calibration | `wave-gemini-4-argon-medium-calibration-0-20261023T230144430405Z-4c4d2973229b` |
| `gemini-4-argon-medium` | Primary 1 | `wave-gemini-4-argon-medium-primary-1-20261023T230243638290Z-f74949f79bb2` |
| `gemini-4-argon-medium` | Primary 2 | `wave-gemini-4-argon-medium-primary-2-20261023T230644455341Z-7b5cdba9916e` |
| `gemini-4-argon-medium` | Primary 3 | `wave-gemini-4-argon-medium-primary-3-20261023T231122358128Z-3a273ecb0c00` |
| `gemini-3.8-flash-medium` | Calibration | `wave-gemini-3.8-flash-medium-calibration-0-20261023T231633114899Z-afba8d149450` |
| `gemini-3.8-flash-medium` | Primary 1 | `wave-gemini-3.8-flash-medium-primary-1-20261023T231758278101Z-c5cd1a2f7102` |
| `gemini-3.8-flash-medium` | Primary 2 | `wave-gemini-3.8-flash-medium-primary-2-20261023T232424838326Z-9fae8a5dd334` |
| `gemini-3.8-flash-medium` | Primary 3 | `wave-gemini-3.8-flash-medium-primary-3-20261023T233055078136Z-6775942d7fda` |

Taxonomy attribution: Marble Skill Taxonomy (v1), Generative Spark, Inc. (Marble), https://withmarble.com; ODbL 1.0 for the database and CC BY-SA 4.0 for content. This summary contains no private task text or answer keys.
