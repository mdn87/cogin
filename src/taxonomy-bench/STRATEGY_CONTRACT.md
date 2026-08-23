# Cogin stable strategy contract

Cogin exports cognitive strategies through the installed
`cogin_strategy_contract` package and its bundled `manifest.json`. This is a
data-only contract: loading or materializing a strategy never calls a provider,
opens a model session, or changes benchmark state.

## Version 1 contract

The manifest is strict JSON with these independent versions:

- `schema_version` identifies the JSON shape.
- `contract_version` identifies the consumer-facing strategy protocol.
- `implementation_version` identifies the content bundle.

Each strategy has a stable ID, positive revision, instruction placement,
purpose, exact content, and SHA-256 content digest. Version 1 exports:

- `cogin.strategy.bounded-divergence`
- `cogin.strategy.concrete-restatement`

IDs are never normalized or silently aliased. An unknown ID fails lookup.
Changing the meaning of a strategy requires a new stable ID; compatible content
refinement increments its revision and the implementation version.

`implementation_sha256` is SHA-256 over canonical UTF-8 JSON for the complete
manifest after removing only the self-referential `implementation_sha256`
field. Canonical JSON sorts object keys, uses compact separators, preserves
array order, rejects non-finite numbers, and retains Unicode. This digest binds
the ordered strategy inventory, all metadata, and every content digest.

## Python API

```python
from cogin_strategy_contract import (
    get_strategy,
    load_manifest,
    materialize_strategy,
    strategy_ids,
)

manifest = load_manifest()
available = strategy_ids()
strategy = get_strategy("cogin.strategy.bounded-divergence")
instruction = materialize_strategy(strategy.id)
```

`load_manifest()` verifies the strict shape, content hashes, sorted unique IDs,
supported contract version, and implementation hash every time. It returns a
fresh copy so caller mutation cannot alter later resolutions.

## Adapter boundary

An external adapter should bind all three of these values:

1. `contract_version`
2. `implementation_version`
3. `implementation_sha256`

The adapter maps its local technique ID to the exact Cogin strategy ID and
must fail closed when a required strategy is missing or any hash differs. The
adapter should consume only this public contract, not benchmark retry helpers,
provider classes, private run data, or internal prompt-building functions.
