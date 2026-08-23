"""Stable, versioned Cogin cognitive-strategy export contract."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from importlib import resources

CONTRACT_VERSION = "1.0.0"
MANIFEST_KIND = "cogin.strategy-manifest"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SEMVER_RE = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
_STRATEGY_ID_RE = re.compile(r"cogin\.strategy\.[a-z0-9][a-z0-9.-]*\Z")
_MANIFEST_FIELDS = {
    "schema_version",
    "kind",
    "contract_version",
    "implementation_version",
    "implementation_sha256",
    "strategies",
}
_STRATEGY_FIELDS = {
    "id",
    "revision",
    "kind",
    "placement",
    "purpose",
    "content",
    "content_sha256",
}


class StrategyContractError(ValueError):
    """Raised when the exported strategy contract is invalid."""


@dataclass(frozen=True, slots=True)
class Strategy:
    """One validated, materializable Cogin cognitive strategy."""

    id: str
    revision: int
    kind: str
    placement: str
    purpose: str
    content: str
    content_sha256: str


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise StrategyContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def canonical_json(value: object) -> str:
    """Serialize a JSON value using Cogin's canonical hash representation."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise StrategyContractError("value is not canonical JSON") from exc


def canonical_sha256(value: object) -> str:
    """Return a lowercase SHA-256 digest of canonical JSON."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def content_sha256(content: str) -> str:
    """Return the hash used to bind exact materialized strategy content."""

    if not isinstance(content, str):
        raise StrategyContractError("strategy content must be a string")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _nonblank(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise StrategyContractError(f"{field} must be a nonblank canonical string")
    return value


def implementation_sha256(manifest: Mapping[str, object]) -> str:
    """Hash the full strategy manifest except its self-referential digest."""

    payload = dict(manifest)
    if "implementation_sha256" not in payload:
        raise StrategyContractError("manifest has no implementation_sha256 field")
    del payload["implementation_sha256"]
    return canonical_sha256(payload)


def validate_manifest(manifest: object) -> dict[str, object]:
    """Strictly validate and return an isolated strategy-manifest copy."""

    if not isinstance(manifest, Mapping) or any(
        not isinstance(key, str) for key in manifest
    ):
        raise StrategyContractError("strategy manifest must be an object")
    if set(manifest) != _MANIFEST_FIELDS:
        raise StrategyContractError("strategy manifest fields are invalid")
    if manifest["schema_version"] != 1 or isinstance(manifest["schema_version"], bool):
        raise StrategyContractError("schema_version must be integer 1")
    if manifest["kind"] != MANIFEST_KIND:
        raise StrategyContractError("strategy manifest kind is invalid")
    contract_version = _nonblank(manifest["contract_version"], "contract_version")
    if contract_version != CONTRACT_VERSION:
        raise StrategyContractError("strategy contract version is unsupported")
    version = _nonblank(manifest["implementation_version"], "implementation_version")
    if _SEMVER_RE.fullmatch(version) is None:
        raise StrategyContractError("implementation_version is not semantic versioning")
    digest = _nonblank(manifest["implementation_sha256"], "implementation_sha256")
    if _SHA256_RE.fullmatch(digest) is None:
        raise StrategyContractError("implementation_sha256 is invalid")

    strategies = manifest["strategies"]
    if not isinstance(strategies, list) or not strategies:
        raise StrategyContractError("strategies must be a nonempty list")
    seen: set[str] = set()
    previous_id = ""
    for raw in strategies:
        if not isinstance(raw, Mapping) or set(raw) != _STRATEGY_FIELDS:
            raise StrategyContractError("strategy fields are invalid")
        identifier = _nonblank(raw["id"], "strategy.id")
        if _STRATEGY_ID_RE.fullmatch(identifier) is None:
            raise StrategyContractError("strategy.id is invalid")
        if identifier in seen:
            raise StrategyContractError("strategy IDs must be unique")
        if previous_id and identifier <= previous_id:
            raise StrategyContractError("strategies must be sorted by ID")
        seen.add(identifier)
        previous_id = identifier
        revision = raw["revision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise StrategyContractError("strategy.revision must be a positive integer")
        if raw["kind"] != "instruction":
            raise StrategyContractError("strategy.kind is unsupported")
        if raw["placement"] != "after-role-before-task":
            raise StrategyContractError("strategy.placement is unsupported")
        _nonblank(raw["purpose"], "strategy.purpose")
        content = _nonblank(raw["content"], "strategy.content")
        content_digest = _nonblank(raw["content_sha256"], "strategy.content_sha256")
        if _SHA256_RE.fullmatch(content_digest) is None:
            raise StrategyContractError("strategy.content_sha256 is invalid")
        if content_sha256(content) != content_digest:
            raise StrategyContractError(
                f"strategy content hash does not match for {identifier}"
            )

    if implementation_sha256(manifest) != digest:
        raise StrategyContractError("strategy implementation hash does not match")
    return deepcopy(dict(manifest))


def load_manifest() -> dict[str, object]:
    """Load and validate the manifest bundled with the installed package."""

    try:
        text = (
            resources.files(__package__)
            .joinpath("manifest.json")
            .read_text(encoding="utf-8")
        )
        value = json.loads(text, object_pairs_hook=_unique_object)
    except StrategyContractError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise StrategyContractError("bundled strategy manifest is unavailable") from exc
    return validate_manifest(value)


def strategy_ids() -> tuple[str, ...]:
    """Return every stable strategy ID in deterministic order."""

    return tuple(item["id"] for item in load_manifest()["strategies"])


def get_strategy(identifier: str) -> Strategy:
    """Resolve one stable ID or reject it without fallback or normalization."""

    for item in load_manifest()["strategies"]:
        if item["id"] == identifier:
            return Strategy(**item)
    raise StrategyContractError(f"unknown Cogin strategy ID: {identifier!r}")


def materialize_strategy(identifier: str) -> str:
    """Return the exact instruction content bound by the strategy digest."""

    return get_strategy(identifier).content


__all__ = [
    "CONTRACT_VERSION",
    "MANIFEST_KIND",
    "Strategy",
    "StrategyContractError",
    "canonical_json",
    "canonical_sha256",
    "content_sha256",
    "get_strategy",
    "implementation_sha256",
    "load_manifest",
    "materialize_strategy",
    "strategy_ids",
    "validate_manifest",
]
