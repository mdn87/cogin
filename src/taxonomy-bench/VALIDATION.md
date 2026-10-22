# Validation record

## 0.5.0 Antigravity lanes and Pair 1 calibration — 2026-10-22

Completed local checks:

- All 225 automated tests passed. The 36 new tests cover the following:
  - the Antigravity provider's command shape, stdin event transport, isolated
    profile, deny-all permission profile, permission-mode and model checks,
    silent-new-conversation detection, error and timeout classification, and
    quota-free preflight;
  - the Google lane set, manifest-scoped pair markers and locks, one
    subject-root marker per manifest, `wave run --calibration-only`, the agy
    self-update guard, and a fake-agy end-to-end Google pair;
  - UTF-8 subprocess decoding.
- The `taxonomy_bench-0.5.0-py3-none-any.whl` wheel built and was installed
  without dependencies into a scratch virtual environment. That install reported
  `taxonomy-bench 0.5.0`, exposed `wave prepare --lanes` and
  `wave run --calibration-only`, and validated `sample_data` with 64 topics,
  156 edges, and no errors.
- Release packaging verified 28 mapped SHA-256 checksums and the exact
  29-entry archive.

Live checks, run with operator approval for about 16 calibration runs:

- The 2026-08-02 Wave 1 manifest `544fb7e3…` pinned Claude Code `2.1.195` and
  Codex `0.146.0`. The installed versions had moved to `2.1.296` and `0.163.0`,
  which the controller rejects as drift. No lane had run against it, so it was
  kept as evidence in `wave-runs/wave-1-superseded-20260802`.
- A fresh Wave 1 manifest, `dbd05d3d331efeea798b981561b39dc25feb8207e60dafc42046619881cbea26`,
  uses the same suite (`ce79e1cc…`), the same calibration IDs, and the same Claude
  and Codex tool-policy hashes as the 2026-08-02 record. Both Pair 1 lanes passed
  preflight with subscription auth and matching requested and resolved models.
- Before calibration, one trivial prompt was sent through the exact Claude and
  Codex subject invocations. Claude reported zero tools and zero MCP servers, and
  `modelUsage` resolved to `claude-opus-5`. Codex answered on `gpt-5.6-sol`.
  Neither left files in the working directory.
- Both Pair 1 calibrations were admitted (`wave run --calibration-only`):
  - `claude-opus-5`: 8 of 8 exact on the first attempt, all strict JSON,
    5.0–7.5 s per task, no infrastructure errors.
  - `gpt-5.6-sol`: 8 of 8 exact on the first attempt, all strict JSON, no
    infrastructure errors. Six tasks took 3.3–5.0 s; `t02-01` took 268.5 s and
    `t03-02` took 293.4 s.

  Both lanes now show status `calibrated`, so the next `wave run` for each
  starts at primary repeat 1.
- The Google lane set manifest,
  `738bc787c2216856989facac94f21b9ee1671e555d1e126e749ee8568f77e2c5`, shares
  Wave 1's protocol hash, suite, calibration IDs, instruction hash, and control
  root. It pins agy `1.4.5`. Both `gemini-4-argon-medium` and
  `gemini-3.8-flash-medium` passed preflight without a model turn: listed by
  `agy models`, selected by `/model`, and subscription quota groups reported by
  `/quota`.
- During the first Google preparation, an unguarded `agy --version` updated
  agy from 1.4.4 to 1.4.5. That 1.4.4 manifest (`0f6b8324…`) was superseded
  before any run and kept in `wave-runs/google-1-superseded-agy144`. The version
  probe now sets `AGY_CLI_DISABLE_AUTO_UPDATE=1`, and a regression test covers
  it. The agy binary's timestamp did not change across the second preparation
  and preflight.
- No raw auth output, account identifiers, credential values, conversation or
  session IDs, private-suite contents, or subject transcripts are recorded here.

## Stable strategy contract 1.0.0 — 2026-08-23

- All 189 automated tests passed. The nine strategy-contract tests cover exact
  stable IDs, canonical hash reproducibility, content materialization, caller
  isolation, content and implementation tamper rejection, unknown IDs, and
  strict schema fields.
- The `taxonomy_bench-0.4.0-py3-none-any.whl` wheel built successfully and
  contains the strategy API, manifest, and JSON schema as package data.
- An isolated import from the wheel resolved both stable IDs and verified
  implementation digest
  `c9412a5cf5db505d5b97dddd89dd8a35e59198655b5f598cb1f5f8df95171bf9`.
- Release packaging verified 28 mapped SHA-256 checksums and the exact 29-entry
  archive.
- No provider, authentication, or live model path was invoked.

## 0.3.0 Wave 1 controller — 2026-08-02

Completed local checks:

- All 180 automated tests passed, including manifest preparation, sanitized
  preflight, calibration admission, immediate infrastructure abort, session-ID
  redaction, abandoned-repeat restart, lane publication, and six-run pair
  aggregation. The end-to-end smoke uses test-controlled fake Claude and Codex
  CLI process runners, proves two-family concurrency, and never reads live
  credential stores or invokes installed model CLIs.
- The `taxonomy_bench-0.3.0-py3-none-any.whl` wheel built successfully and was
  force-installed without dependencies.
- The installed console entry point reported `taxonomy-bench 0.3.0`; its help
  exposes `wave prepare`, `wave preflight`, `wave run`, and `wave aggregate`.
- Installed-package validation of `sample_data` reported 64 topics, 156 edges,
  and no errors.
- Release packaging verified 23 mapped SHA-256 checksums and the exact 24-entry
  archive, including all six runtime modules and both subscription/Wave test
  modules.
- `git diff --check` passed.

Live subscription preflight completed on 2026-08-02:

- Upstream Marble taxonomy commit: `96a7933754af672e1bfdbf7ecb05c325860c6e0d`;
  its 1,590 topics, 3,221 edges, counts, and file checksums validated.
- The generated seed-42 private suite contains 32 tasks across tiers 1-8.
  Suite SHA-256: `ce79e1cc1ea9e9e42e6de238a8467676e5e9a1fcf4bf7528083db05c4b1e3fc0`.
- Immutable manifest:
  `544fb7e37f341b3250630b62b2e6da91f54ab00c371fc151bd93e88bf3f166e2`.
- Claude Code `2.1.195` reported subscription auth for `claude-opus-5`,
  `claude-sonnet-5`, and `claude-fable-5`; requested and resolved lane
  identities matched.
- Codex CLI `0.146.0` reported ChatGPT subscription auth for `gpt-5.6-sol`,
  `gpt-5.6-terra`, and `gpt-5.6-luna`; requested and resolved lane identities
  matched.
- Claude tool-policy hash:
  `c5261e5b1c20ad95855af8711c99fdf41629b5240772f5090211eec8a82e5ef6`.
  Codex tool-policy hash:
  `7dc5f047daf288d5e99e0204e0332b8d0058ad9ca1c4fe10bb9f98eb99467d0c`.
- No raw auth output, account identifiers, credential values, subject session
  state, private suite contents, or external execution paths are recorded.

Codex `login status` writes its successful ChatGPT marker to stderr in 0.146.0.
The adapter now accepts the marker from either output stream and returns only
sanitized auth metadata; a regression test covers this contract.

## 0.2.0 HUD progression — 2026-07-21

Validated on 2026-07-21.

Completed checks:

- All 93 automated tests passed, including regressions for untrusted scorer-feedback redaction and wheel metadata/version validation.
- The `taxonomy_bench-0.2.0-py3-none-any.whl` wheel built successfully and was force-installed into the project-local `.venv`.
- `taxonomy-bench --version` reported `taxonomy-bench 0.2.0`.
- `taxonomy-bench validate --taxonomy src/taxonomy-bench/sample_data` reported a valid package with 64 topics, 156 dependencies, and no errors.
- Release packaging verified the wheel's filename and internal package metadata, all 18 mapped SHA-256 checksums, and the exact 19-entry archive set, including only the 0.2.0 wheel and excluding any 0.1.0 wheel.
- Browser QA of the run report was completed at 1440x900, 768x900, and a 720x900 zoom-equivalent viewport.
- Browser QA of the matrix report was completed at 1440x900 and 768x900.
- No horizontal overflow was present at the checked report or matrix viewports.
- The desktop trace showed 8 task entries, with body and supporting text rendered at 15px and 13px respectively.
- Filters and disclosure controls worked, and repeat recoveries were collapsed by default.
- Browser QA produced no console warnings or errors.
- Browser QA screenshots are stored under the ignored `.superpowers/hud-visual` directory.

The upstream repository structure, schemas, validation logic, and representative topic and dependency records were inspected through GitHub. A full local run against the 1,590-topic upstream data was not executed in this sandbox because direct GitHub cloning was blocked by DNS/network restrictions. The package does not bundle upstream data.
