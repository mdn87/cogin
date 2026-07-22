# Validation record

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
