from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from cogin_strategy_contract import (
    CONTRACT_VERSION,
    StrategyContractError,
    canonical_sha256,
    content_sha256,
    get_strategy,
    implementation_sha256,
    load_manifest,
    materialize_strategy,
    strategy_ids,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_exported_manifest_has_exact_stable_identity_and_hashes():
    manifest = load_manifest()

    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "cogin.strategy-manifest"
    assert manifest["contract_version"] == CONTRACT_VERSION == "1.0.0"
    assert manifest["implementation_version"] == "1.0.0"
    assert manifest["implementation_sha256"] == (
        "c9412a5cf5db505d5b97dddd89dd8a35e59198655b5f598cb1f5f8df95171bf9"
    )
    assert implementation_sha256(manifest) == manifest["implementation_sha256"]
    assert strategy_ids() == (
        "cogin.strategy.bounded-divergence",
        "cogin.strategy.concrete-restatement",
    )


def test_canonical_hash_is_reproducible_across_mapping_order():
    left = {
        "strategy": "cogin.strategy.bounded-divergence",
        "configuration": {"limit": 3, "mode": "bounded"},
    }
    right = {
        "configuration": {"mode": "bounded", "limit": 3},
        "strategy": "cogin.strategy.bounded-divergence",
    }

    assert canonical_sha256(left) == canonical_sha256(right)


def test_strategy_lookup_materializes_exact_hash_bound_content():
    for identifier in strategy_ids():
        strategy = get_strategy(identifier)
        content = materialize_strategy(identifier)

        assert strategy.id == identifier
        assert content == strategy.content
        assert content_sha256(content) == strategy.content_sha256


def test_content_tampering_is_rejected_before_materialization():
    tampered = deepcopy(load_manifest())
    tampered["strategies"][0]["content"] += " Expand the solution anyway."

    with pytest.raises(StrategyContractError, match="content hash does not match"):
        validate_manifest(tampered)


def test_manifest_hash_rejects_tampering_even_with_updated_content_hash():
    tampered = deepcopy(load_manifest())
    strategy = tampered["strategies"][0]
    strategy["content"] += " Expand the solution anyway."
    strategy["content_sha256"] = content_sha256(strategy["content"])

    with pytest.raises(
        StrategyContractError,
        match="implementation hash does not match",
    ):
        validate_manifest(tampered)


def test_unknown_strategy_id_fails_without_alias_or_fallback():
    with pytest.raises(StrategyContractError, match="unknown Cogin strategy ID"):
        get_strategy("cogin.strategy.unknown")


def test_manifest_validation_rejects_unknown_fields():
    malformed = deepcopy(load_manifest())
    malformed["unexpected"] = True

    with pytest.raises(StrategyContractError, match="manifest fields are invalid"):
        validate_manifest(malformed)


def test_loaded_manifest_is_isolated_from_caller_mutation():
    first = load_manifest()
    first["strategies"][0]["content"] = "changed by caller"

    second = load_manifest()
    assert second["strategies"][0]["content"] != "changed by caller"


def test_checked_in_schema_is_strict_and_matches_the_exported_contract():
    schema = json.loads(
        (ROOT / "cogin_strategy_contract" / "strategy-manifest.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "kind",
        "contract_version",
        "implementation_version",
        "implementation_sha256",
        "strategies",
    }
    strategy_schema = schema["properties"]["strategies"]["items"]
    assert strategy_schema["additionalProperties"] is False
    assert strategy_schema["properties"]["id"]["pattern"].startswith(
        "^cogin\\.strategy\\."
    )
