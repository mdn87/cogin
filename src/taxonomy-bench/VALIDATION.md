# Validation record

Validated on 2026-07-21.

Completed checks:

- Six automated tests passed.
- All eight task tiers were generated and exactly scored with an oracle provider.
- Paired first-attempt and retry recovery behavior was verified.
- Strict and recoverable JSON parsing was verified.
- Invalid topological orders were rejected.
- Private-suite tampering was rejected by suite-hash validation.
- Malformed manual retry numbering was rejected.
- Suite generation completed across 50 additional seeds with 32 tasks per seed.
- The wheel built successfully, installed into a clean virtual environment, and ran `validate`, `generate`, and `--version` successfully.
- The bundled 64-topic, 156-edge synthetic fixture passed graph validation.

The upstream repository structure, schemas, validation logic, and representative topic and dependency records were inspected through GitHub. A full local run against the 1,590-topic upstream data was not executed in this sandbox because direct GitHub cloning was blocked by DNS/network restrictions. The package does not bundle upstream data.
