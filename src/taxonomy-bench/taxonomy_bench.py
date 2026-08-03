#!/usr/bin/env python3
"""Taxonomy Bench

A deterministic, progressively difficult benchmark generated from the Marble
Skill Taxonomy. It measures first-attempt ability, retry recovery, graph
reasoning, latency, token use, and JSON reliability.

The taxonomy data is not bundled. Point the CLI at a checkout of:
https://github.com/withmarbleapp/os-taxonomy
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import random
import shlex
import statistics
import subprocess
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from taxonomy_bench_cli import Completion, Provider
from taxonomy_bench_progression import derive_condition_evidence, wilson_interval
from taxonomy_bench_protocol import BASE_INSTRUCTIONS, BenchError
from taxonomy_bench_report import (
    render_matrix_html as _render_matrix_html,
    render_run_html as _render_run_html,
)

FORMAT_VERSION = 1
BENCHMARK_VERSION = "0.3.0"
ATTRIBUTION = (
    "Marble Skill Taxonomy (v1) · © Generative Spark, Inc. (Marble) · "
    "https://withmarble.com · licensed under ODbL 1.0 (database) and "
    "CC BY-SA 4.0 (content)."
)
RELATION_RULE = "In every edge, topicId depends on prerequisiteId."


@dataclasses.dataclass(frozen=True)
class Topic:
    id: str
    type: str
    subject: str
    domain: str | None
    name: str | None
    description: str
    age_start: int | None
    age_end: int | None
    evidence: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Topic":
        return cls(
            id=str(value.get("id", "")),
            type=str(value.get("type", "")),
            subject=str(value.get("subject", "")),
            domain=value.get("domain"),
            name=value.get("name"),
            description=str(value.get("description", "")),
            age_start=value.get("ageRangeStart"),
            age_end=value.get("ageRangeEnd"),
            evidence=tuple(str(item) for item in value.get("evidence", []) if isinstance(item, str)),
        )

    def compact(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "subject": self.subject,
            "domain": self.domain,
            "type": self.type,
            "ageRangeStart": self.age_start,
            "ageRangeEnd": self.age_end,
        }


@dataclasses.dataclass(frozen=True)
class Edge:
    topic_id: str
    prerequisite_id: str
    strength: str
    reason: str = ""

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Edge":
        return cls(
            topic_id=str(value.get("topicId", "")),
            prerequisite_id=str(value.get("prerequisiteId", "")),
            strength=str(value.get("strength", "")),
            reason=str(value.get("reason", "")),
        )

    def compact(self) -> dict[str, str]:
        return {
            "topicId": self.topic_id,
            "prerequisiteId": self.prerequisite_id,
            "strength": self.strength,
        }


class Taxonomy:
    def __init__(
        self,
        topics: Sequence[Topic],
        edges: Sequence[Edge],
        manifest: Mapping[str, Any] | None = None,
        source_path: Path | None = None,
    ) -> None:
        self.topics = list(topics)
        self.edges = list(edges)
        self.by_id = {topic.id: topic for topic in topics}
        self.manifest = dict(manifest or {})
        self.source_path = source_path

        self.prereqs: dict[str, list[Edge]] = defaultdict(list)
        self.unlocks: dict[str, list[Edge]] = defaultdict(list)
        for edge in edges:
            self.prereqs[edge.topic_id].append(edge)
            self.unlocks[edge.prerequisite_id].append(edge)

    @staticmethod
    def _resolve_data_dir(path: str | Path) -> Path:
        root = Path(path).expanduser().resolve()
        candidates = [root / "data", root]
        for candidate in candidates:
            if (candidate / "topics.json").is_file() and (candidate / "dependencies.json").is_file():
                return candidate
        raise BenchError(
            f"Could not find topics.json and dependencies.json under {root} or {root / 'data'}"
        )

    @classmethod
    def load(cls, path: str | Path) -> "Taxonomy":
        data_dir = cls._resolve_data_dir(path)
        topics_doc = json.loads((data_dir / "topics.json").read_text(encoding="utf-8"))
        deps_doc = json.loads((data_dir / "dependencies.json").read_text(encoding="utf-8"))
        manifest_path = data_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

        topics = [Topic.from_dict(item) for item in topics_doc.get("topics", [])]
        edges = [Edge.from_dict(item) for item in deps_doc.get("dependencies", [])]
        taxonomy = cls(topics, edges, manifest=manifest, source_path=data_dir)
        taxonomy._declared_topic_count = topics_doc.get("topicCount")
        taxonomy._declared_edge_count = deps_doc.get("edgeCount")
        return taxonomy

    def validate(self, verify_checksums: bool = False) -> list[str]:
        errors: list[str] = []
        allowed_types = {"CONCEPTUAL", "PROCEDURAL", "REPRESENTATIONAL", "LANGUAGE", "META"}

        declared_topics = getattr(self, "_declared_topic_count", None)
        declared_edges = getattr(self, "_declared_edge_count", None)
        if declared_topics is not None and declared_topics != len(self.topics):
            errors.append(f"topicCount {declared_topics} != {len(self.topics)}")
        if declared_edges is not None and declared_edges != len(self.edges):
            errors.append(f"edgeCount {declared_edges} != {len(self.edges)}")

        seen: set[str] = set()
        for topic in self.topics:
            if not topic.id.startswith("mt_"):
                errors.append(f"malformed topic id: {topic.id}")
            if topic.id in seen:
                errors.append(f"duplicate topic id: {topic.id}")
            seen.add(topic.id)
            if topic.type not in allowed_types:
                errors.append(f"topic {topic.id}: invalid type {topic.type}")
            if not topic.description:
                errors.append(f"topic {topic.id}: empty description")

        for index, edge in enumerate(self.edges):
            if edge.topic_id not in self.by_id:
                errors.append(f"edge {index}: unknown topicId {edge.topic_id}")
            if edge.prerequisite_id not in self.by_id:
                errors.append(f"edge {index}: unknown prerequisiteId {edge.prerequisite_id}")
            if edge.topic_id == edge.prerequisite_id:
                errors.append(f"edge {index}: self-dependency {edge.topic_id}")
            if edge.strength not in {"hard", "soft"}:
                errors.append(f"edge {index}: invalid strength {edge.strength}")

        cycle = self.find_cycle(hard_only=False)
        if cycle:
            errors.append("dependency graph contains a cycle: " + " -> ".join(cycle))

        counts = self.manifest.get("counts", {}) if isinstance(self.manifest, Mapping) else {}
        if counts:
            if counts.get("topics") not in {None, len(self.topics)}:
                errors.append(f"manifest topics {counts.get('topics')} != {len(self.topics)}")
            if counts.get("dependencies") not in {None, len(self.edges)}:
                errors.append(f"manifest dependencies {counts.get('dependencies')} != {len(self.edges)}")

        if verify_checksums and self.source_path and isinstance(self.manifest.get("files"), Mapping):
            for name, metadata in self.manifest["files"].items():
                file_path = self.source_path / name
                expected = metadata.get("sha256") if isinstance(metadata, Mapping) else None
                if expected and file_path.exists():
                    actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
                    if actual != expected:
                        errors.append(f"checksum mismatch for {name}")
        return errors

    def find_cycle(self, hard_only: bool = False) -> list[str] | None:
        state: dict[str, int] = {}
        parent: dict[str, str] = {}

        def visit(node: str) -> list[str] | None:
            state[node] = 1
            for edge in self.unlocks.get(node, []):
                if hard_only and edge.strength != "hard":
                    continue
                nxt = edge.topic_id
                if state.get(nxt, 0) == 0:
                    parent[nxt] = node
                    found = visit(nxt)
                    if found:
                        return found
                elif state.get(nxt) == 1:
                    cycle = [nxt]
                    cursor = node
                    while cursor != nxt and cursor in parent:
                        cycle.append(cursor)
                        cursor = parent[cursor]
                    cycle.append(nxt)
                    cycle.reverse()
                    return cycle
            state[node] = 2
            return None

        for topic_id in self.by_id:
            if state.get(topic_id, 0) == 0:
                cycle = visit(topic_id)
                if cycle:
                    return cycle
        return None

    def ancestors(
        self,
        target_id: str,
        hard_only: bool = False,
        max_depth: int | None = None,
        allowed_nodes: set[str] | None = None,
    ) -> dict[str, int]:
        distances: dict[str, int] = {}
        queue: deque[tuple[str, int]] = deque([(target_id, 0)])
        while queue:
            node, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue
            for edge in self.prereqs.get(node, []):
                if hard_only and edge.strength != "hard":
                    continue
                prereq = edge.prerequisite_id
                if allowed_nodes is not None and prereq not in allowed_nodes:
                    continue
                next_depth = depth + 1
                if prereq not in distances or next_depth < distances[prereq]:
                    distances[prereq] = next_depth
                    queue.append((prereq, next_depth))
        return distances

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
        hard_only: bool = False,
        allowed_nodes: set[str] | None = None,
    ) -> list[str] | None:
        if source_id == target_id:
            return [source_id]
        queue: deque[str] = deque([source_id])
        parent: dict[str, str | None] = {source_id: None}
        while queue:
            node = queue.popleft()
            for edge in self.unlocks.get(node, []):
                if hard_only and edge.strength != "hard":
                    continue
                nxt = edge.topic_id
                if allowed_nodes is not None and nxt not in allowed_nodes:
                    continue
                if nxt in parent:
                    continue
                parent[nxt] = node
                if nxt == target_id:
                    path = [target_id]
                    cursor: str | None = target_id
                    while cursor is not None and parent[cursor] is not None:
                        cursor = parent[cursor]
                        if cursor is not None:
                            path.append(cursor)
                    path.reverse()
                    return path
                queue.append(nxt)
        return None

    def induced_edges(self, nodes: set[str], hard_only: bool = False) -> list[Edge]:
        return [
            edge
            for edge in self.edges
            if edge.topic_id in nodes
            and edge.prerequisite_id in nodes
            and (not hard_only or edge.strength == "hard")
        ]

    def topological_order(self, nodes: set[str], edges: Sequence[Edge]) -> list[str] | None:
        indegree = {node: 0 for node in nodes}
        outgoing: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            if edge.topic_id in nodes and edge.prerequisite_id in nodes:
                outgoing[edge.prerequisite_id].append(edge.topic_id)
                indegree[edge.topic_id] += 1
        ready = deque(sorted(node for node, degree in indegree.items() if degree == 0))
        order: list[str] = []
        while ready:
            node = ready.popleft()
            order.append(node)
            for nxt in sorted(outgoing.get(node, [])):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
        return order if len(order) == len(nodes) else None

    def compact_topics(self, ids: Iterable[str]) -> list[dict[str, Any]]:
        return [self.by_id[topic_id].compact() for topic_id in sorted(set(ids)) if topic_id in self.by_id]


ID_SCHEMA = {
    "type": "object",
    "properties": {"id": {"type": "string"}},
    "required": ["id"],
    "additionalProperties": False,
}
IDS_SCHEMA = {
    "type": "object",
    "properties": {"ids": {"type": "array", "items": {"type": "string"}}},
    "required": ["ids"],
    "additionalProperties": False,
}
ISSUES_SCHEMA = {
    "type": "object",
    "properties": {"issues": {"type": "array", "items": {"type": "string"}}},
    "required": ["issues"],
    "additionalProperties": False,
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False)


def _task_prompt(title: str, question: str, context: Mapping[str, Any], example: str) -> str:
    return (
        f"{title}\n\n"
        f"{RELATION_RULE}\n"
        f"{question}\n\n"
        f"Context:\n{_json(context)}\n\n"
        f"Required response shape: {example}\n"
        "Return one JSON object only."
    )


class SuiteGenerator:
    TIER_KINDS: dict[int, tuple[str, ...]] = {
        1: ("semantic_match", "direct_prerequisites"),
        2: ("direct_prerequisites", "reverse_unlocks", "semantic_match"),
        3: ("transitive_prerequisites", "reverse_unlocks", "direct_prerequisites"),
        4: ("transitive_prerequisites", "topological_order"),
        5: ("shortest_path", "topological_order", "mastery_plan"),
        6: ("integrity_audit", "shortest_path", "mastery_plan"),
        7: ("transitive_prerequisites", "topological_order", "shortest_path", "integrity_audit"),
        8: ("mastery_plan", "integrity_audit", "shortest_path", "topological_order"),
    }

    def __init__(self, taxonomy: Taxonomy, seed: int) -> None:
        self.taxonomy = taxonomy
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(self, max_tier: int = 8, tasks_per_tier: int = 4) -> dict[str, Any]:
        if max_tier < 1 or max_tier > 8:
            raise BenchError("max_tier must be between 1 and 8")
        if tasks_per_tier < 1:
            raise BenchError("tasks_per_tier must be at least 1")

        tasks: list[dict[str, Any]] = []
        for tier in range(1, max_tier + 1):
            kinds = self.TIER_KINDS[tier]
            for index in range(tasks_per_tier):
                kind = kinds[index % len(kinds)]
                builder = getattr(self, f"_build_{kind}")
                task = builder(tier)
                task["id"] = f"t{tier:02d}-{index + 1:02d}-{kind}"
                task["tier"] = tier
                task["kind"] = kind
                tasks.append(task)

        taxonomy_version = self.taxonomy.manifest.get("taxonomyVersion") or self.taxonomy.manifest.get("version")
        suite = {
            "format_version": FORMAT_VERSION,
            "benchmark_version": BENCHMARK_VERSION,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "seed": self.seed,
            "max_tier": max_tier,
            "tasks_per_tier": tasks_per_tier,
            "taxonomy": {
                "name": self.taxonomy.manifest.get("dataset", "Marble Skill Taxonomy"),
                "version": taxonomy_version or "unknown",
                "topic_count": len(self.taxonomy.topics),
                "edge_count": len(self.taxonomy.edges),
                "attribution": ATTRIBUTION,
            },
            "tasks": tasks,
        }
        suite["suite_hash"] = suite_hash(suite)
        return suite

    def _pick(self, values: Sequence[Any], message: str) -> Any:
        if not values:
            raise BenchError(message)
        return self.rng.choice(list(values))

    def _sample_disjoint_edges(self, excluded_nodes: set[str], count: int) -> list[Edge]:
        candidates = [
            edge
            for edge in self.taxonomy.edges
            if edge.topic_id not in excluded_nodes and edge.prerequisite_id not in excluded_nodes
        ]
        if not candidates or count <= 0:
            return []
        return self.rng.sample(candidates, min(count, len(candidates)))

    def _connected_ancestor_nodes(
        self,
        target_id: str,
        hard_only: bool,
        goal: int,
    ) -> set[str] | None:
        nodes = {target_id}
        queue: deque[str] = deque([target_id])
        while queue and len(nodes) < goal:
            node = queue.popleft()
            edges = [
                edge
                for edge in self.taxonomy.prereqs.get(node, [])
                if not hard_only or edge.strength == "hard"
            ]
            self.rng.shuffle(edges)
            for edge in edges:
                if edge.prerequisite_id not in nodes:
                    nodes.add(edge.prerequisite_id)
                    queue.append(edge.prerequisite_id)
                    if len(nodes) >= goal:
                        break
        return nodes if len(nodes) >= goal else None

    def _build_semantic_match(self, tier: int) -> dict[str, Any]:
        valid = [topic for topic in self.taxonomy.topics if topic.name and topic.description]
        target = self._pick(valid, "No topics available for semantic matching")
        candidate_count = min(8, 4 + (tier - 1) // 2)

        same_domain = [
            topic
            for topic in valid
            if topic.id != target.id
            and topic.subject == target.subject
            and topic.domain == target.domain
        ]
        same_subject = [
            topic
            for topic in valid
            if topic.id != target.id and topic.subject == target.subject and topic not in same_domain
        ]
        other = [topic for topic in valid if topic.id != target.id and topic.subject != target.subject]
        pool = same_domain + same_subject + other
        distractors: list[Topic] = []
        for group in (same_domain, same_subject, other):
            remaining = candidate_count - 1 - len(distractors)
            if remaining <= 0:
                break
            available = [item for item in group if item not in distractors]
            distractors.extend(self.rng.sample(available, min(remaining, len(available))))
        if len(distractors) < candidate_count - 1:
            remaining_pool = [item for item in pool if item not in distractors]
            distractors.extend(
                self.rng.sample(remaining_pool, min(candidate_count - 1 - len(distractors), len(remaining_pool)))
            )

        options = [target, *distractors]
        self.rng.shuffle(options)
        query = {
            "description": target.description,
            "evidence": list(target.evidence[: min(3, len(target.evidence))]),
            "type": target.type,
            "ageRangeStart": target.age_start,
            "ageRangeEnd": target.age_end,
        }
        context = {
            "query": query,
            "options": [{"id": option.id, "name": option.name} for option in options],
        }
        prompt = _task_prompt(
            "Semantic topic identification",
            "Choose the single option whose name best matches the query description and evidence.",
            context,
            '{"id":"mt_..."}',
        )
        return {
            "prompt": prompt,
            "output_schema": ID_SCHEMA,
            "scorer": {"type": "id", "expected": target.id},
        }

    def _build_direct_prerequisites(self, tier: int) -> dict[str, Any]:
        hard_only = tier >= 2 and tier % 2 == 0
        candidates = []
        for topic in self.taxonomy.topics:
            edges = self.taxonomy.prereqs.get(topic.id, [])
            relevant = [edge for edge in edges if not hard_only or edge.strength == "hard"]
            if relevant:
                candidates.append(topic)
        target = self._pick(candidates, "No topic has direct prerequisites")
        target_edges = list(self.taxonomy.prereqs[target.id])
        expected = sorted(
            edge.prerequisite_id
            for edge in target_edges
            if not hard_only or edge.strength == "hard"
        )
        excluded = {target.id, *(edge.prerequisite_id for edge in target_edges)}
        distractors = self._sample_disjoint_edges(excluded, 4 + tier * 2)
        context_edges = [*target_edges, *distractors]
        self.rng.shuffle(context_edges)
        ids = {target.id}
        for edge in context_edges:
            ids.add(edge.topic_id)
            ids.add(edge.prerequisite_id)
        context = {
            "target": self.taxonomy.by_id[target.id].compact(),
            "hardOnly": hard_only,
            "topics": self.taxonomy.compact_topics(ids),
            "edges": [edge.compact() for edge in context_edges],
        }
        qualifier = "hard direct prerequisite" if hard_only else "direct prerequisite"
        prompt = _task_prompt(
            "Direct prerequisite extraction",
            f"Return the IDs of every {qualifier} of the target according to the supplied edges. "
            "Ignore unrelated edges. Order does not matter.",
            context,
            '{"ids":["mt_...", "mt_..."]}',
        )
        return {
            "prompt": prompt,
            "output_schema": IDS_SCHEMA,
            "scorer": {"type": "ids_set", "expected": expected},
        }

    def _build_reverse_unlocks(self, tier: int) -> dict[str, Any]:
        hard_only = tier >= 3 and tier % 2 == 1
        candidates = []
        for topic in self.taxonomy.topics:
            relevant = [
                edge
                for edge in self.taxonomy.unlocks.get(topic.id, [])
                if not hard_only or edge.strength == "hard"
            ]
            if relevant:
                candidates.append(topic)
        source = self._pick(candidates, "No topic unlocks another topic")
        source_edges = list(self.taxonomy.unlocks[source.id])
        expected = sorted(
            edge.topic_id
            for edge in source_edges
            if not hard_only or edge.strength == "hard"
        )
        excluded = {source.id, *(edge.topic_id for edge in source_edges)}
        distractors = self._sample_disjoint_edges(excluded, 5 + tier * 2)
        context_edges = [*source_edges, *distractors]
        self.rng.shuffle(context_edges)
        ids = {source.id}
        for edge in context_edges:
            ids.add(edge.topic_id)
            ids.add(edge.prerequisite_id)
        context = {
            "sourcePrerequisite": self.taxonomy.by_id[source.id].compact(),
            "hardOnly": hard_only,
            "topics": self.taxonomy.compact_topics(ids),
            "edges": [edge.compact() for edge in context_edges],
        }
        qualifier = "hard " if hard_only else ""
        prompt = _task_prompt(
            "Reverse dependency extraction",
            f"Return every topic ID directly unlocked by the source prerequisite through a {qualifier}edge. "
            "An unlocked topic has sourcePrerequisite.id as its prerequisiteId. Order does not matter.",
            context,
            '{"ids":["mt_...", "mt_..."]}',
        )
        return {
            "prompt": prompt,
            "output_schema": IDS_SCHEMA,
            "scorer": {"type": "ids_set", "expected": expected},
        }

    def _build_transitive_prerequisites(self, tier: int) -> dict[str, Any]:
        hard_only = tier % 2 == 0
        depth = min(4, 2 + max(0, tier - 3) // 2)
        min_count = 3
        max_count = min(24, 6 + tier * 2)
        target: Topic | None = None
        distances: dict[str, int] = {}
        candidates = list(self.taxonomy.topics)
        self.rng.shuffle(candidates)
        for candidate in candidates:
            found = self.taxonomy.ancestors(candidate.id, hard_only=hard_only, max_depth=depth)
            if min_count <= len(found) <= max_count:
                target = candidate
                distances = found
                break
        if target is None:
            raise BenchError("Could not generate a bounded transitive prerequisite task")

        relevant_nodes = {target.id, *distances.keys()}
        relevant_edges = self.taxonomy.induced_edges(relevant_nodes, hard_only=False)
        distractors = self._sample_disjoint_edges(relevant_nodes, 3 + tier)
        context_edges = [*relevant_edges, *distractors]
        self.rng.shuffle(context_edges)
        ids = set(relevant_nodes)
        for edge in distractors:
            ids.add(edge.topic_id)
            ids.add(edge.prerequisite_id)
        context = {
            "target": target.compact(),
            "maximumHops": depth,
            "hardOnly": hard_only,
            "topics": self.taxonomy.compact_topics(ids),
            "edges": [edge.compact() for edge in context_edges],
        }
        qualifier = "using only hard edges" if hard_only else "using hard or soft edges"
        prompt = _task_prompt(
            "Bounded transitive prerequisite closure",
            f"Return all prerequisite IDs reachable from target.id in one to {depth} dependency hops, {qualifier}. "
            "Ignore disconnected distractor components. Order does not matter.",
            context,
            '{"ids":["mt_...", "mt_..."]}',
        )
        return {
            "prompt": prompt,
            "output_schema": IDS_SCHEMA,
            "scorer": {"type": "ids_set", "expected": sorted(distances)},
        }

    def _build_topological_order(self, tier: int) -> dict[str, Any]:
        goal = min(14, 5 + tier)
        candidates = list(self.taxonomy.topics)
        self.rng.shuffle(candidates)
        nodes: set[str] | None = None
        target: Topic | None = None
        edges: list[Edge] = []
        for candidate in candidates:
            candidate_nodes = self._connected_ancestor_nodes(candidate.id, hard_only=False, goal=goal)
            if not candidate_nodes:
                continue
            candidate_edges = self.taxonomy.induced_edges(candidate_nodes, hard_only=False)
            if len(candidate_edges) >= goal - 1 and self.taxonomy.topological_order(candidate_nodes, candidate_edges):
                nodes = candidate_nodes
                target = candidate
                edges = candidate_edges
                break
        if nodes is None or target is None:
            raise BenchError("Could not generate a connected topological ordering task")

        shuffled_edges = list(edges)
        self.rng.shuffle(shuffled_edges)
        context = {
            "nodes": self.taxonomy.compact_topics(nodes),
            "edges": [edge.compact() for edge in shuffled_edges],
        }
        prompt = _task_prompt(
            "Dependency-respecting topological order",
            "Return all and only the supplied node IDs in one valid learning order. Every prerequisiteId must appear "
            "before its topicId for every supplied edge. Multiple orders may be valid.",
            context,
            '{"ids":["mt_first", "mt_second", "mt_last"]}',
        )
        scorer_edges = [[edge.prerequisite_id, edge.topic_id] for edge in edges]
        return {
            "prompt": prompt,
            "output_schema": IDS_SCHEMA,
            "scorer": {
                "type": "topological_order",
                "nodes": sorted(nodes),
                "edges": scorer_edges,
            },
        }

    def _build_shortest_path(self, tier: int) -> dict[str, Any]:
        hard_only = tier % 2 == 1
        min_distance = 2
        max_distance = min(5, 2 + max(0, tier - 4))
        candidates = list(self.taxonomy.topics)
        self.rng.shuffle(candidates)
        source: str | None = None
        target: Topic | None = None
        base_path: list[str] | None = None
        for candidate in candidates:
            distances = self.taxonomy.ancestors(candidate.id, hard_only=hard_only, max_depth=max_distance)
            eligible = [node for node, distance in distances.items() if min_distance <= distance <= max_distance]
            if not eligible:
                continue
            preferred_distance = max(distance for node, distance in distances.items() if node in eligible)
            preferred = [node for node in eligible if distances[node] == preferred_distance]
            candidate_source = self.rng.choice(preferred)
            path = self.taxonomy.shortest_path(candidate_source, candidate.id, hard_only=hard_only)
            if path and min_distance <= len(path) - 1 <= max_distance:
                source = candidate_source
                target = candidate
                base_path = path
                break
        if source is None or target is None or base_path is None:
            raise BenchError("Could not generate a shortest-path task")

        nodes = set(base_path)
        ancestor_pool = list(
            self.taxonomy.ancestors(target.id, hard_only=hard_only, max_depth=(len(base_path) - 1) + 1).keys()
        )
        self.rng.shuffle(ancestor_pool)
        goal = min(20, 8 + tier)
        for node in ancestor_pool:
            if len(nodes) >= goal:
                break
            nodes.add(node)
        nodes.add(target.id)
        context_edges = self.taxonomy.induced_edges(nodes, hard_only=False)
        shortest = self.taxonomy.shortest_path(source, target.id, hard_only=hard_only, allowed_nodes=nodes)
        if not shortest:
            raise BenchError("Generated shortest-path context disconnected the source and target")

        self.rng.shuffle(context_edges)
        context = {
            "source": self.taxonomy.by_id[source].compact(),
            "target": target.compact(),
            "hardOnly": hard_only,
            "nodes": self.taxonomy.compact_topics(nodes),
            "edges": [edge.compact() for edge in context_edges],
        }
        qualifier = "using only hard edges" if hard_only else "using hard or soft edges"
        prompt = _task_prompt(
            "Shortest prerequisite-to-target path",
            f"Return one shortest valid path from source.id to target.id, {qualifier}. Include both endpoints. "
            "Each consecutive pair must follow prerequisiteId -> topicId.",
            context,
            '{"ids":["mt_source", "mt_intermediate", "mt_target"]}',
        )
        valid_pairs = [
            [edge.prerequisite_id, edge.topic_id]
            for edge in context_edges
            if not hard_only or edge.strength == "hard"
        ]
        return {
            "prompt": prompt,
            "output_schema": IDS_SCHEMA,
            "scorer": {
                "type": "shortest_path",
                "source": source,
                "target": target.id,
                "minimum_edges": len(shortest) - 1,
                "edges": valid_pairs,
            },
        }

    def _build_mastery_plan(self, tier: int) -> dict[str, Any]:
        goal = min(16, 7 + tier)
        candidates = list(self.taxonomy.topics)
        self.rng.shuffle(candidates)
        selected: tuple[Topic, set[str], list[Edge], set[str], set[str]] | None = None
        for target in candidates:
            nodes = self._connected_ancestor_nodes(target.id, hard_only=True, goal=goal)
            if not nodes:
                continue
            hard_edges = self.taxonomy.induced_edges(nodes, hard_only=True)
            if len(hard_edges) < goal - 1:
                continue
            possible_mastered = sorted(nodes - {target.id})
            if len(possible_mastered) < 2:
                continue
            mastered_count = max(1, min(len(possible_mastered) - 1, goal // 3))
            mastered = set(self.rng.sample(possible_mastered, mastered_count))

            required = {target.id}
            stack = [target.id]
            while stack:
                node = stack.pop()
                for edge in hard_edges:
                    if edge.topic_id != node:
                        continue
                    prereq = edge.prerequisite_id
                    if prereq in mastered or prereq in required:
                        continue
                    required.add(prereq)
                    stack.append(prereq)
            if len(required) < 3:
                continue
            selected = (target, nodes, hard_edges, mastered, required)
            break
        if selected is None:
            raise BenchError("Could not generate a mastery planning task")

        target, nodes, hard_edges, mastered, required = selected
        all_context_edges = self.taxonomy.induced_edges(nodes, hard_only=False)
        self.rng.shuffle(all_context_edges)
        context = {
            "target": target.compact(),
            "masteredIds": sorted(mastered),
            "nodes": self.taxonomy.compact_topics(nodes),
            "edges": [edge.compact() for edge in all_context_edges],
        }
        prompt = _task_prompt(
            "Minimal hard-prerequisite learning plan",
            "Return the shortest sequence of unmastered topic IDs needed to learn the target. Follow only hard "
            "dependencies, stop traversing behind any mastered topic, include the target, place every required hard "
            "prerequisite before the topic that needs it, and place target.id last.",
            context,
            '{"ids":["mt_needed_first", "mt_target"]}',
        )
        required_edges = [
            [edge.prerequisite_id, edge.topic_id]
            for edge in hard_edges
            if edge.prerequisite_id in required and edge.topic_id in required
        ]
        return {
            "prompt": prompt,
            "output_schema": IDS_SCHEMA,
            "scorer": {
                "type": "mastery_plan",
                "required": sorted(required),
                "target": target.id,
                "edges": required_edges,
            },
        }

    def _build_integrity_audit(self, tier: int) -> dict[str, Any]:
        edge_count = min(24, 8 + tier * 2)
        unique_edges: list[Edge] = []
        seen: set[tuple[str, str, str]] = set()
        shuffled = list(self.taxonomy.edges)
        self.rng.shuffle(shuffled)
        for edge in shuffled:
            key = (edge.topic_id, edge.prerequisite_id, edge.strength)
            if key in seen:
                continue
            seen.add(key)
            unique_edges.append(edge)
            if len(unique_edges) >= edge_count:
                break
        if len(unique_edges) < 6:
            raise BenchError("Not enough edges for integrity audit")

        context_edges = [edge.compact() for edge in unique_edges]
        known_ids = sorted(
            {value for edge in unique_edges for value in (edge.topic_id, edge.prerequisite_id)}
        )
        issue_types = [
            "unknown_topicId",
            "unknown_prerequisiteId",
            "self_dependency",
            "bad_strength",
        ]
        issue_count = min(4, 2 + max(0, tier - 6))
        selected_types = self.rng.sample(issue_types, issue_count)
        indices = self.rng.sample(range(len(context_edges)), issue_count)
        expected: list[str] = []
        for issue_type, index in zip(selected_types, indices):
            edge = context_edges[index]
            if issue_type == "unknown_topicId":
                edge["topicId"] = f"mt_UNKNOWN_TOPIC_{index}"
            elif issue_type == "unknown_prerequisiteId":
                edge["prerequisiteId"] = f"mt_UNKNOWN_PREREQ_{index}"
            elif issue_type == "self_dependency":
                edge["prerequisiteId"] = edge["topicId"]
            elif issue_type == "bad_strength":
                edge["strength"] = "medium"
            expected.append(f"{issue_type}@{index}")

        context = {
            "knownTopicIds": known_ids,
            "edges": context_edges,
            "allowedStrengths": ["hard", "soft"],
            "issueCodes": [
                "unknown_topicId@index",
                "unknown_prerequisiteId@index",
                "self_dependency@index",
                "bad_strength@index",
            ],
        }
        prompt = _task_prompt(
            "Dependency integrity audit",
            "Audit every zero-based edge index. Report all and only the issue codes defined in context. An endpoint is "
            "unknown when absent from knownTopicIds. A self-dependency has identical topicId and prerequisiteId. "
            "Order does not matter.",
            context,
            '{"issues":["unknown_topicId@3", "bad_strength@7"]}',
        )
        return {
            "prompt": prompt,
            "output_schema": ISSUES_SCHEMA,
            "scorer": {"type": "issues_set", "expected": sorted(expected)},
        }


def suite_hash(suite: Mapping[str, Any]) -> str:
    copy = dict(suite)
    copy.pop("suite_hash", None)
    copy.pop("created_at", None)
    payload = json.dumps(copy, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def public_suite(suite: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in suite.items() if key != "tasks"}
    result["tasks"] = [
        {
            "id": task["id"],
            "tier": task["tier"],
            "kind": task["kind"],
            "prompt": task["prompt"],
            "output_schema": task["output_schema"],
        }
        for task in suite["tasks"]
    ]
    return result


def load_suite(path: str | Path) -> dict[str, Any]:
    suite = json.loads(Path(path).read_text(encoding="utf-8"))
    if suite.get("format_version") != FORMAT_VERSION:
        raise BenchError(
            f"Unsupported suite format {suite.get('format_version')}; expected {FORMAT_VERSION}"
        )
    for task in suite.get("tasks", []):
        if "scorer" not in task:
            raise BenchError("A private suite with scorer data is required for running or scoring")
    expected_hash = suite.get("suite_hash")
    actual_hash = suite_hash(suite)
    if expected_hash and expected_hash != actual_hash:
        raise BenchError(
            f"Suite hash mismatch: declared {expected_hash}, calculated {actual_hash}. "
            "The suite may have been modified or corrupted."
        )
    suite["suite_hash"] = actual_hash
    return suite


def write_suite_files(suite: Mapping[str, Any], private_path: Path, public_path: Path | None = None) -> None:
    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_text(_json(suite) + "\n", encoding="utf-8")
    if public_path:
        public_path.parent.mkdir(parents=True, exist_ok=True)
        with public_path.open("w", encoding="utf-8") as handle:
            for task in public_suite(suite)["tasks"]:
                handle.write(json.dumps(task, ensure_ascii=False) + "\n")


@dataclasses.dataclass
class ParseResult:
    value: Any | None
    strict_json: bool
    recovered_json: bool
    error: str | None = None


def _extract_balanced_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        start = text.find("{", start + 1)
    return None


def parse_answer(text: str) -> ParseResult:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
        if isinstance(value, dict):
            return ParseResult(value=value, strict_json=True, recovered_json=False)
        return ParseResult(value=None, strict_json=False, recovered_json=False, error="JSON root is not an object")
    except json.JSONDecodeError:
        pass

    candidate = stripped
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            candidate = "\n".join(lines[1:-1]).strip()
            try:
                value = json.loads(candidate)
                if isinstance(value, dict):
                    return ParseResult(value=value, strict_json=False, recovered_json=True)
            except json.JSONDecodeError:
                pass

    balanced = _extract_balanced_object(stripped)
    if balanced:
        try:
            value = json.loads(balanced)
            if isinstance(value, dict):
                return ParseResult(value=value, strict_json=False, recovered_json=True)
        except json.JSONDecodeError:
            pass
    return ParseResult(value=None, strict_json=False, recovered_json=False, error="No parseable JSON object")


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return list(value)


def _set_f1(expected: set[str], actual: set[str]) -> float:
    if not expected and not actual:
        return 1.0
    if not actual:
        return 0.0
    true_positive = len(expected & actual)
    precision = true_positive / len(actual) if actual else 0.0
    recall = true_positive / len(expected) if expected else 1.0
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def score_text(task: Mapping[str, Any], text: str) -> dict[str, Any]:
    parsed = parse_answer(text)
    base = {
        "exact": False,
        "partial": 0.0,
        "strict_json": parsed.strict_json,
        "recovered_json": parsed.recovered_json,
        "feedback": "The response was not parseable as the required JSON object.",
        "details": {},
    }
    if parsed.value is None:
        return base

    scorer = task["scorer"]
    scorer_type = scorer["type"]

    if scorer_type == "id":
        actual = parsed.value.get("id")
        expected = scorer["expected"]
        exact = isinstance(actual, str) and actual == expected
        return {
            **base,
            "exact": exact,
            "partial": 1.0 if exact else 0.0,
            "feedback": "Correct." if exact else "The selected topic ID is incorrect.",
            "details": {"actual_type": type(actual).__name__},
        }

    if scorer_type in {"ids_set", "issues_set"}:
        key = "ids" if scorer_type == "ids_set" else "issues"
        values = _string_list(parsed.value.get(key))
        if values is None:
            return {
                **base,
                "feedback": f"The '{key}' field must be an array of strings.",
            }
        expected = set(scorer["expected"])
        actual = set(values)
        f1 = _set_f1(expected, actual)
        exact = expected == actual and len(values) == len(actual)
        missing = len(expected - actual)
        extra = len(actual - expected)
        return {
            **base,
            "exact": exact,
            "partial": f1,
            "feedback": (
                "Correct."
                if exact
                else f"The set is incorrect. Missing count: {missing}. Extra count: {extra}. "
                f"Duplicate count: {len(values) - len(actual)}."
            ),
            "details": {"missing_count": missing, "extra_count": extra, "duplicate_count": len(values) - len(actual)},
        }

    if scorer_type == "topological_order":
        values = _string_list(parsed.value.get("ids"))
        if values is None:
            return {**base, "feedback": "The 'ids' field must be an array of strings."}
        expected_nodes = set(scorer["nodes"])
        actual_nodes = set(values)
        node_f1 = _set_f1(expected_nodes, actual_nodes)
        positions: dict[str, int] = {}
        for index, node in enumerate(values):
            positions.setdefault(node, index)
        edges = [tuple(pair) for pair in scorer["edges"]]
        satisfied = sum(
            1
            for prereq, topic in edges
            if prereq in positions and topic in positions and positions[prereq] < positions[topic]
        )
        edge_ratio = satisfied / len(edges) if edges else 1.0
        unique = len(values) == len(actual_nodes)
        exact = actual_nodes == expected_nodes and len(values) == len(expected_nodes) and unique and satisfied == len(edges)
        partial = 0.6 * node_f1 + 0.4 * edge_ratio
        violated = len(edges) - satisfied
        return {
            **base,
            "exact": exact,
            "partial": partial,
            "feedback": (
                "Correct."
                if exact
                else f"The order has node coverage, duplication, or precedence errors. Violated or unevaluable edge count: {violated}."
            ),
            "details": {
                "node_f1": node_f1,
                "edge_compliance": edge_ratio,
                "duplicate_count": len(values) - len(actual_nodes),
                "violated_edges": violated,
            },
        }

    if scorer_type == "shortest_path":
        values = _string_list(parsed.value.get("ids"))
        if values is None:
            return {**base, "feedback": "The 'ids' field must be an array of strings."}
        valid_pairs = {tuple(pair) for pair in scorer["edges"]}
        steps = list(zip(values, values[1:]))
        valid_step_count = sum(1 for pair in steps if pair in valid_pairs)
        step_ratio = valid_step_count / len(steps) if steps else 0.0
        endpoints_ok = bool(values) and values[0] == scorer["source"] and values[-1] == scorer["target"]
        length_ok = len(values) - 1 == scorer["minimum_edges"]
        unique = len(values) == len(set(values))
        exact = endpoints_ok and length_ok and unique and valid_step_count == len(steps)
        partial = 0.35 * (1.0 if endpoints_ok else 0.0) + 0.45 * step_ratio + 0.2 * (1.0 if length_ok else 0.0)
        return {
            **base,
            "exact": exact,
            "partial": partial,
            "feedback": (
                "Correct."
                if exact
                else "The path has an endpoint, edge-direction, cycle, or shortest-length error. "
                f"The minimum edge count is {scorer['minimum_edges']}."
            ),
            "details": {
                "endpoints_ok": endpoints_ok,
                "step_compliance": step_ratio,
                "length_ok": length_ok,
                "unique": unique,
            },
        }

    if scorer_type == "mastery_plan":
        values = _string_list(parsed.value.get("ids"))
        if values is None:
            return {**base, "feedback": "The 'ids' field must be an array of strings."}
        required = set(scorer["required"])
        actual = set(values)
        set_f1 = _set_f1(required, actual)
        positions: dict[str, int] = {}
        for index, node in enumerate(values):
            positions.setdefault(node, index)
        edges = [tuple(pair) for pair in scorer["edges"]]
        satisfied = sum(
            1
            for prereq, topic in edges
            if prereq in positions and topic in positions and positions[prereq] < positions[topic]
        )
        edge_ratio = satisfied / len(edges) if edges else 1.0
        target_last = bool(values) and values[-1] == scorer["target"]
        unique = len(values) == len(actual)
        exact = actual == required and len(values) == len(required) and unique and edge_ratio == 1.0 and target_last
        partial = 0.55 * set_f1 + 0.35 * edge_ratio + 0.1 * (1.0 if target_last else 0.0)
        return {
            **base,
            "exact": exact,
            "partial": partial,
            "feedback": (
                "Correct."
                if exact
                else "The plan has missing or unnecessary topics, dependency-order violations, duplicates, or does not end with the target. "
                f"Missing count: {len(required - actual)}. Extra count: {len(actual - required)}."
            ),
            "details": {
                "set_f1": set_f1,
                "edge_compliance": edge_ratio,
                "target_last": target_last,
                "duplicate_count": len(values) - len(actual),
            },
        }

    return {**base, "feedback": f"Unknown scorer type: {scorer_type}"}


class OpenAIProvider(Provider):
    supports_sessions = True

    def __init__(
        self,
        model: str,
        effort: str,
        output_mode: str,
        max_output_tokens: int,
        timeout: float,
        transport_retries: int,
        store: bool,
    ) -> None:
        try:
            import openai
            OpenAI = openai.OpenAI
        except (ImportError, AttributeError) as exc:
            raise BenchError("The OpenAI provider requires: pip install openai") from exc
        self.model = model
        self.effort = effort
        self.output_mode = output_mode
        self.max_output_tokens = max_output_tokens
        self.store = store
        self.provider_version = getattr(openai, "__version__", None)
        self.client = OpenAI(max_retries=transport_retries, timeout=timeout)

    @staticmethod
    def _extract_output_text(response: Any) -> str:
        try:
            value = response.output_text
            if isinstance(value, str):
                return value
        except Exception:
            pass
        chunks: list[str] = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) == "output_text":
                    text = getattr(content, "text", None)
                    if isinstance(text, str):
                        chunks.append(text)
        return "".join(chunks)

    @staticmethod
    def _usage(response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        details = getattr(usage, "output_tokens_details", None)
        input_details = getattr(usage, "input_tokens_details", None)
        return {
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "cached_input_tokens": int(getattr(input_details, "cached_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "reasoning_tokens": int(getattr(details, "reasoning_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }

    def complete(
        self,
        prompt: str,
        output_schema: Mapping[str, Any],
        previous_response_id: str | None = None,
    ) -> Completion:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "instructions": BASE_INSTRUCTIONS,
            "input": prompt,
            "max_output_tokens": self.max_output_tokens,
            "store": self.store,
        }
        if self.effort and self.effort != "default":
            kwargs["reasoning"] = {"effort": self.effort}
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id
        if self.output_mode == "schema":
            kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "taxonomy_bench_answer",
                    "schema": dict(output_schema),
                    "strict": True,
                }
            }

        started = time.perf_counter()
        try:
            response = self.client.responses.create(**kwargs)
        except Exception as exc:
            return Completion(
                text="",
                latency_ms=(time.perf_counter() - started) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
        latency_ms = (time.perf_counter() - started) * 1000
        incomplete = getattr(response, "incomplete_details", None)
        return Completion(
            text=self._extract_output_text(response),
            latency_ms=latency_ms,
            resolved_model=getattr(response, "model", None),
            response_id=getattr(response, "id", None),
            request_id=getattr(response, "_request_id", None),
            usage=self._usage(response),
            status=getattr(response, "status", None),
            incomplete_reason=getattr(incomplete, "reason", None) if incomplete else None,
        )


class CommandProvider(Provider):
    def __init__(self, command: str, timeout: float, model: str = "command", effort: str = "default") -> None:
        if not command.strip():
            raise BenchError("--command is required for the command provider")
        self.command = shlex.split(command)
        self.timeout = timeout
        self.model = model
        self.effort = effort

    def complete(
        self,
        prompt: str,
        output_schema: Mapping[str, Any],
        previous_response_id: str | None = None,
    ) -> Completion:
        env = os.environ.copy()
        env["TAXONOMY_BENCH_MODEL"] = self.model
        env["TAXONOMY_BENCH_EFFORT"] = self.effort
        started = time.perf_counter()
        try:
            process = subprocess.run(
                self.command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
                env=env,
            )
        except Exception as exc:
            return Completion(
                text="",
                latency_ms=(time.perf_counter() - started) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )
        latency_ms = (time.perf_counter() - started) * 1000
        if process.returncode != 0:
            return Completion(
                text=process.stdout,
                latency_ms=latency_ms,
                error=f"Command exited {process.returncode}: {process.stderr.strip()}",
            )
        return Completion(
            text=process.stdout,
            latency_ms=latency_ms,
            resolved_model=self.model,
            status="completed",
        )


def _attempt_record(
    attempt_number: int,
    completion: Completion,
    score: Mapping[str, Any] | None,
    phase: str,
) -> dict[str, Any]:
    return {
        "attempt": attempt_number,
        "phase": phase,
        "text": completion.text,
        "latency_ms": round(completion.latency_ms, 3),
        "resolved_model": completion.resolved_model,
        "response_id": completion.response_id,
        "request_id": completion.request_id,
        "usage": completion.usage,
        "status": completion.status,
        "incomplete_reason": completion.incomplete_reason,
        "error": completion.error,
        "error_kind": completion.error_kind,
        "provider_metadata": completion.provider_metadata,
        "score": dict(score) if score is not None else None,
    }


def _retry_prompt(
    task: Mapping[str, Any],
    attempt_number: int,
    policy: str,
    previous_text: str,
    previous_score: Mapping[str, Any],
    continued: bool,
) -> str:
    if policy == "feedback":
        diagnostic = previous_score.get("feedback", "The previous answer was incorrect.")
    else:
        diagnostic = "The previous answer was incorrect. Re-solve the task independently."

    instruction = (
        f"Retry {attempt_number - 1}. {diagnostic} Return only the JSON object in the originally requested shape."
    )
    if continued:
        return instruction
    if policy == "feedback":
        return (
            task["prompt"]
            + "\n\nPrevious answer:\n"
            + previous_text
            + "\n\nDiagnostic feedback:\n"
            + diagnostic
            + "\n\nTry again. Return one JSON object only."
        )
    return task["prompt"] + "\n\nThis is a fresh retry. Re-solve independently and return one JSON object only."


def execute_run(
    suite: Mapping[str, Any],
    provider: Provider,
    run_meta: Mapping[str, Any],
    retries: int,
    retry_policy: str,
    retry_context: str,
    session_mode: str,
    progress: bool = True,
    attempt_checkpoint: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if session_mode == "continuous" and not provider.supports_sessions:
        raise BenchError("The selected provider does not support continuous sessions")
    if retries > 0 and retry_context == "continued" and not provider.supports_sessions:
        raise BenchError("The selected provider does not support continued retry context; use --retry-context fresh")
    if retries < 0:
        raise BenchError("retries cannot be negative")

    tasks = list(suite["tasks"])
    records: list[dict[str, Any]] = []
    session_previous_id: str | None = None
    configuration = dict(run_meta)
    run_id_override = configuration.pop("_run_id", None)
    run = {
        "format_version": FORMAT_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "run_id": str(run_id_override or run_id(run_meta, suite)),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "suite_hash": suite.get("suite_hash") or suite_hash(suite),
        "suite_seed": suite.get("seed"),
        "taxonomy": suite.get("taxonomy", {}),
        "configuration": {
            **configuration,
            "retries": retries,
            "retry_policy": retry_policy,
            "retry_context": retry_context,
            "retry_schedule": "after_first_pass",
            "session_mode": session_mode,
        },
        "tasks": records,
    }

    # Phase 1: run every first attempt before any cognitive retries. This keeps the
    # no-retry baseline paired and uncontaminated by earlier retries.
    for index, task in enumerate(tasks, start=1):
        base_previous_id = session_previous_id if session_mode == "continuous" else None
        if progress:
            print(
                f"[{index}/{len(tasks)}] tier {task['tier']} {task['kind']} first attempt",
                file=sys.stderr,
                flush=True,
            )
        completion = provider.complete(
            task["prompt"],
            task["output_schema"],
            previous_response_id=base_previous_id,
        )
        score = None if completion.error else score_text(task, completion.text)
        record = {
            "task_id": task["id"],
            "tier": task["tier"],
            "kind": task["kind"],
            "base_previous_response_id": base_previous_id,
            "attempts": [_attempt_record(1, completion, score, "first")],
        }
        records.append(record)
        if attempt_checkpoint is not None:
            attempt_checkpoint(run["run_id"], run)
        if session_mode == "continuous" and completion.response_id:
            session_previous_id = completion.response_id

    # Phase 2: branch retries from each failed task. This preserves the exact first
    # pass while measuring blind or diagnostic recovery.
    if retries > 0:
        for index, (task, record) in enumerate(zip(tasks, records), start=1):
            first = record["attempts"][0]
            if first["error"] or (first["score"] and first["score"]["exact"]):
                continue
            previous_attempt = first
            if retry_context == "continued":
                previous_id = first["response_id"]
            else:
                previous_id = record["base_previous_response_id"] if session_mode == "continuous" else None

            for retry_index in range(1, retries + 1):
                attempt_number = retry_index + 1
                if progress:
                    print(
                        f"[{index}/{len(tasks)}] tier {task['tier']} {task['kind']} retry {retry_index}/{retries}",
                        file=sys.stderr,
                        flush=True,
                    )
                continued = retry_context == "continued" and previous_id is not None
                retry_prompt = _retry_prompt(
                    task=task,
                    attempt_number=attempt_number,
                    policy=retry_policy,
                    previous_text=previous_attempt["text"],
                    previous_score=previous_attempt["score"] or {},
                    continued=continued,
                )
                completion = provider.complete(
                    retry_prompt,
                    task["output_schema"],
                    previous_response_id=previous_id if continued or session_mode == "continuous" else None,
                )
                score = None if completion.error else score_text(task, completion.text)
                attempt = _attempt_record(attempt_number, completion, score, "retry")
                record["attempts"].append(attempt)
                if attempt_checkpoint is not None:
                    attempt_checkpoint(run["run_id"], run)
                if completion.error:
                    break
                previous_attempt = attempt
                if retry_context == "continued" and completion.response_id:
                    previous_id = completion.response_id
                if score and score["exact"]:
                    break

    if attempt_checkpoint is None:
        run["run_id"] = str(run_id_override or run_id(run_meta, suite))
        run["created_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    run["summary"] = summarize_run(run)
    return run


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return sorted_values[low]
    weight = position - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def _sum_usage(attempts: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for attempt in attempts:
        for key, value in (attempt.get("usage") or {}).items():
            if isinstance(value, (int, float)):
                totals[key] += int(value)
    return dict(totals)


def _frontier(by_tier: Mapping[int, Mapping[str, Any]], key: str, threshold: float = 2 / 3) -> int:
    frontier = 0
    for tier in sorted(by_tier):
        total = by_tier[tier]["scored"]
        passed = by_tier[tier][key]
        rate = passed / total if total else 0.0
        if rate + 1e-12 >= threshold:
            frontier = tier
        else:
            break
    return frontier


def summarize_run(run: Mapping[str, Any]) -> dict[str, Any]:
    records = list(run["tasks"])
    scored_records = [record for record in records if not record["attempts"][0].get("error")]
    infra_errors = len(records) - len(scored_records)
    total_infra_errors = sum(
        1 for record in records for attempt in record["attempts"] if attempt.get("error")
    )
    retry_infra_errors = sum(
        1
        for record in records
        for attempt in record["attempts"][1:]
        if attempt.get("error")
    )
    resolved_models = sorted(
        {
            str(attempt["resolved_model"])
            for record in records
            for attempt in record["attempts"]
            if attempt.get("resolved_model")
        }
    )

    first_passes = 0
    eventual_passes = 0
    first_partials: list[float] = []
    eventual_partials: list[float] = []
    first_latencies: list[float] = []
    all_latencies: list[float] = []
    time_to_correct: list[float] = []
    strict_first = 0
    recovered_first = 0
    first_attempts: list[Mapping[str, Any]] = []
    all_attempts: list[Mapping[str, Any]] = []
    by_tier: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"scored": 0, "first_passes": 0, "eventual_passes": 0, "first_partial_sum": 0.0, "eventual_partial_sum": 0.0}
    )
    first_failures = 0
    retried_failures = 0
    recovered_failures = 0
    weighted_denominator = 0.0
    weighted_first = 0.0
    weighted_eventual = 0.0

    for record in scored_records:
        attempts = [attempt for attempt in record["attempts"] if not attempt.get("error") and attempt.get("score")]
        if not attempts:
            continue
        first = attempts[0]
        eventual = next((attempt for attempt in attempts if attempt["score"]["exact"]), attempts[-1])
        first_exact = bool(first["score"]["exact"])
        eventual_exact = any(bool(attempt["score"]["exact"]) for attempt in attempts)
        first_passes += int(first_exact)
        eventual_passes += int(eventual_exact)
        first_partials.append(float(first["score"]["partial"]))
        eventual_partials.append(max(float(attempt["score"]["partial"]) for attempt in attempts))
        first_latencies.append(float(first["latency_ms"]))
        all_latencies.extend(float(attempt["latency_ms"]) for attempt in attempts)
        strict_first += int(bool(first["score"]["strict_json"]))
        recovered_first += int(bool(first["score"]["recovered_json"]))
        first_attempts.append(first)
        all_attempts.extend(attempts)

        elapsed = 0.0
        for attempt in attempts:
            elapsed += float(attempt["latency_ms"])
            if attempt["score"]["exact"]:
                time_to_correct.append(elapsed)
                break

        tier = int(record["tier"])
        tier_row = by_tier[tier]
        tier_row["scored"] += 1
        tier_row["first_passes"] += int(first_exact)
        tier_row["eventual_passes"] += int(eventual_exact)
        tier_row["first_partial_sum"] += float(first["score"]["partial"])
        tier_row["eventual_partial_sum"] += max(float(attempt["score"]["partial"]) for attempt in attempts)

        weighted_denominator += tier
        weighted_first += tier * int(first_exact)
        weighted_eventual += tier * int(eventual_exact)
        if not first_exact:
            first_failures += 1
            if len(attempts) > 1:
                retried_failures += 1
                recovered_failures += int(eventual_exact)

    tier_summary: dict[str, Any] = {}
    for tier, row in sorted(by_tier.items()):
        scored = row["scored"]
        tier_summary[str(tier)] = {
            "scored": scored,
            "first_passes": row["first_passes"],
            "eventual_passes": row["eventual_passes"],
            "first_accuracy": row["first_passes"] / scored if scored else None,
            "eventual_accuracy": row["eventual_passes"] / scored if scored else None,
            "first_partial_mean": row["first_partial_sum"] / scored if scored else None,
            "eventual_partial_mean": row["eventual_partial_sum"] / scored if scored else None,
        }

    scored = len(scored_records)
    lower, upper = wilson_interval(first_passes, scored)
    total_first_ms = sum(first_latencies)
    total_all_ms = sum(all_latencies)
    weighted_points_per_minute = (
        weighted_first / (total_first_ms / 60000) if total_first_ms > 0 else None
    )
    first_usage = _sum_usage(first_attempts)
    all_usage = _sum_usage(all_attempts)
    output_tokens = first_usage.get("output_tokens", 0)
    points_per_1k_output = weighted_first / (output_tokens / 1000) if output_tokens else None

    by_tier_int = {int(key): value for key, value in tier_summary.items()}
    summary = {
        "task_count": len(records),
        "scored_task_count": scored,
        "scored_coverage": scored / len(records) if records else None,
        "infrastructure_error_count": infra_errors,
        "total_infrastructure_error_count": total_infra_errors,
        "retry_infrastructure_error_count": retry_infra_errors,
        "resolved_models": resolved_models,
        "first_attempt_passes": first_passes,
        "eventual_passes": eventual_passes,
        "first_attempt_accuracy": first_passes / scored if scored else None,
        "first_attempt_accuracy_95ci": [lower, upper],
        "eventual_accuracy": eventual_passes / scored if scored else None,
        "base_strength_0_100": 100 * weighted_first / weighted_denominator if weighted_denominator else None,
        "eventual_strength_0_100": 100 * weighted_eventual / weighted_denominator if weighted_denominator else None,
        "retry_lift_points": 100 * (weighted_eventual - weighted_first) / weighted_denominator if weighted_denominator else None,
        "retry_recovery_rate": recovered_failures / retried_failures if retried_failures else None,
        "recovered_failures": recovered_failures,
        "retried_failures": retried_failures,
        "first_attempt_failures": first_failures,
        "reliable_frontier_first": _frontier(by_tier_int, "first_passes") if by_tier_int else 0,
        "reliable_frontier_eventual": _frontier(by_tier_int, "eventual_passes") if by_tier_int else 0,
        "peak_tier_first": max((record["tier"] for record in scored_records if record["attempts"][0]["score"]["exact"]), default=0),
        "peak_tier_eventual": max(
            (
                record["tier"]
                for record in scored_records
                if any(attempt.get("score", {}).get("exact") for attempt in record["attempts"] if attempt.get("score"))
            ),
            default=0,
        ),
        "first_partial_mean": statistics.fmean(first_partials) if first_partials else None,
        "eventual_partial_mean": statistics.fmean(eventual_partials) if eventual_partials else None,
        "strict_json_rate_first": strict_first / scored if scored else None,
        "recovered_json_rate_first": recovered_first / scored if scored else None,
        "latency_ms": {
            "first_total": total_first_ms,
            "all_total": total_all_ms,
            "first_median": statistics.median(first_latencies) if first_latencies else None,
            "first_p90": _percentile(first_latencies, 0.9),
            "time_to_correct_median": statistics.median(time_to_correct) if time_to_correct else None,
        },
        "efficiency": {
            "difficulty_weighted_points_per_minute_first": weighted_points_per_minute,
            "difficulty_weighted_points_per_1k_output_tokens_first": points_per_1k_output,
        },
        "usage_first": first_usage,
        "usage_all": all_usage,
        "by_tier": tier_summary,
        "interpretation": {
            "base_strength": "Difficulty-weighted exact correctness on first attempts.",
            "eventual_strength": "The same score after allowed cognitive retries.",
            "reliable_frontier": "Highest consecutive tier with at least two-thirds exact passes.",
            "retry_recovery": "Fraction of first-attempt failures corrected within the retry budget.",
        },
    }
    return summary


def run_id(meta: Mapping[str, Any], suite: Mapping[str, Any]) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond // 1000:03d}Z"
    model = safe_slug(str(meta.get("model", "model")))
    effort = safe_slug(str(meta.get("effort", "default")))
    return f"{timestamp}-{model}-{effort}-{suite.get('suite_hash') or suite_hash(suite)}"


def safe_slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in cleaned.split("-") if part)[:80] or "run"


def save_run(run: Mapping[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run.json").write_text(_json(run) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(_json(run["summary"]) + "\n", encoding="utf-8")
    with (out_dir / "attempts.jsonl").open("w", encoding="utf-8") as handle:
        for task in run["tasks"]:
            for attempt in task["attempts"]:
                row = {
                    "task_id": task["task_id"],
                    "tier": task["tier"],
                    "kind": task["kind"],
                    **attempt,
                }
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "report.html").write_text(render_run_html(run), encoding="utf-8")


def render_run_html(run: Mapping[str, Any]) -> str:
    return _render_run_html(run, attribution=ATTRIBUTION)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise BenchError(f"Invalid JSONL at line {line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise BenchError(f"JSONL line {line_number} is not an object")
            rows.append(value)
    return rows


def score_external_responses(
    suite: Mapping[str, Any],
    responses: Sequence[Mapping[str, Any]],
    meta: Mapping[str, Any],
) -> dict[str, Any]:
    tasks_by_id = {task["id"]: task for task in suite["tasks"]}
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in responses:
        task_id = row.get("task_id")
        if task_id not in tasks_by_id:
            raise BenchError(f"Unknown task_id in responses: {task_id}")
        grouped[str(task_id)].append(row)

    records: list[dict[str, Any]] = []
    for task in suite["tasks"]:
        rows = sorted(grouped.get(task["id"], []), key=lambda row: int(row.get("attempt", 1)))
        attempts: list[dict[str, Any]] = []
        if not rows:
            completion = Completion(text="", latency_ms=0, error="No response supplied")
            attempts.append(_attempt_record(1, completion, None, "first"))
        else:
            attempt_numbers = [int(row.get("attempt", 1)) for row in rows]
            if attempt_numbers[0] != 1:
                raise BenchError(f"Responses for {task['id']} must begin with attempt 1")
            if len(attempt_numbers) != len(set(attempt_numbers)):
                raise BenchError(f"Responses for {task['id']} contain duplicate attempt numbers")
            expected_numbers = list(range(1, attempt_numbers[-1] + 1))
            if attempt_numbers != expected_numbers:
                raise BenchError(f"Responses for {task['id']} must use contiguous attempt numbers")
            for row, attempt_number in zip(rows, attempt_numbers):
                text = str(row.get("text", ""))
                completion = Completion(
                    text=text,
                    latency_ms=float(row.get("latency_ms", 0) or 0),
                    resolved_model=(str(row["resolved_model"]) if row.get("resolved_model") else None),
                    usage=dict(row.get("usage", {}) or {}),
                    status=str(row.get("status", "completed")),
                    error=row.get("error"),
                )
                score = None if completion.error else score_text(task, text)
                attempts.append(
                    _attempt_record(
                        attempt_number,
                        completion,
                        score,
                        "first" if attempt_number == 1 else "retry",
                    )
                )
        records.append(
            {
                "task_id": task["id"],
                "tier": task["tier"],
                "kind": task["kind"],
                "base_previous_response_id": None,
                "attempts": attempts,
            }
        )

    run = {
        "format_version": FORMAT_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "run_id": run_id(meta, suite),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "suite_hash": suite.get("suite_hash") or suite_hash(suite),
        "suite_seed": suite.get("seed"),
        "taxonomy": suite.get("taxonomy", {}),
        "configuration": dict(meta),
        "tasks": records,
    }
    run["summary"] = summarize_run(run)
    return run


def aggregate_matrix(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        summary = run["summary"]
        config = run["configuration"]
        rows.append(
            {
                "run_id": run["run_id"],
                "model": config.get("model"),
                "resolved_models": summary.get("resolved_models", []),
                "effort": config.get("effort"),
                "repeat": config.get("repeat", 1),
                "base_strength": summary.get("base_strength_0_100"),
                "eventual_strength": summary.get("eventual_strength_0_100"),
                "retry_lift": summary.get("retry_lift_points"),
                "first_accuracy": summary.get("first_attempt_accuracy"),
                "eventual_accuracy": summary.get("eventual_accuracy"),
                "recovery": summary.get("retry_recovery_rate"),
                "frontier_first": summary.get("reliable_frontier_first"),
                "frontier_eventual": summary.get("reliable_frontier_eventual"),
                "median_latency_ms": summary.get("latency_ms", {}).get("first_median"),
                "reasoning_tokens": summary.get("usage_first", {}).get("reasoning_tokens"),
                "total_tokens": summary.get("usage_first", {}).get("total_tokens"),
                "points_per_minute": summary.get("efficiency", {}).get("difficulty_weighted_points_per_minute_first"),
                "infra_errors": summary.get("infrastructure_error_count"),
            }
        )
    return {
        "format_version": FORMAT_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runs": rows,
        "conditions": derive_condition_evidence(list(runs)),
    }


def render_matrix_html(matrix: Mapping[str, Any]) -> str:
    return _render_matrix_html(matrix, attribution=ATTRIBUTION)


def build_provider(args: argparse.Namespace, model: str | None = None, effort: str | None = None) -> Provider:
    selected_model = model if model is not None else getattr(args, "model", None)
    selected_effort = effort if effort is not None else (getattr(args, "effort", None) or "default")
    if args.provider in ("claude-cli", "codex-cli"):
        raise BenchError(
            f"Provider '{args.provider}' is manifest-bound. Use "
            "'taxonomy-bench wave preflight' or 'taxonomy-bench wave run'."
        )
    if args.provider == "openai":
        if not selected_model:
            raise BenchError("--model is required for the OpenAI provider")
        return OpenAIProvider(
            model=selected_model,
            effort=selected_effort,
            output_mode=args.output_mode,
            max_output_tokens=args.max_output_tokens,
            timeout=args.timeout,
            transport_retries=args.transport_retries,
            store=args.store or args.session == "continuous" or (args.retries > 0 and args.retry_context == "continued"),
        )
    return CommandProvider(
        command=args.command,
        timeout=args.timeout,
        model=selected_model or "command",
        effort=selected_effort,
    )


def get_or_generate_suite(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "suite", None):
        return load_suite(args.suite)
    if not getattr(args, "taxonomy", None):
        raise BenchError("Provide either --suite or --taxonomy")
    taxonomy = Taxonomy.load(args.taxonomy)
    errors = taxonomy.validate(verify_checksums=getattr(args, "verify_checksums", False))
    if errors:
        preview = "\n".join(f"- {error}" for error in errors[:20])
        raise BenchError(f"Taxonomy validation failed:\n{preview}")
    return SuiteGenerator(taxonomy, seed=args.seed).generate(
        max_tier=args.max_tier,
        tasks_per_tier=args.tasks_per_tier,
    )


def add_suite_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--suite", help="Private suite JSON generated by this tool")
    parser.add_argument("--taxonomy", help="Path to os-taxonomy checkout or its data directory")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-tier", type=int, default=8)
    parser.add_argument("--tasks-per-tier", type=int, default=4)
    parser.add_argument("--verify-checksums", action="store_true")


def add_provider_args(parser: argparse.ArgumentParser, matrix: bool = False) -> None:
    parser.add_argument(
        "--provider",
        choices=["openai", "command", "claude-cli", "codex-cli"],
        default="openai",
    )
    if not matrix:
        parser.add_argument(
            "--model",
            default=os.environ.get("OPENAI_MODEL"),
            help="Provider model ID. Defaults to OPENAI_MODEL when set.",
        )
        parser.add_argument("--effort", default="default", help="Pass-through reasoning effort, such as low, medium, high, xhigh, or max")
    parser.add_argument("--command", default="", help="Executable command that reads the prompt on stdin and writes the answer on stdout")
    parser.add_argument("--output-mode", choices=["prompt", "schema"], default="prompt", help="Prompt-only JSON measures format reliability; schema mode isolates semantic reasoning")
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--transport-retries", type=int, default=0, help="Network/API retries, separate from cognitive retries")
    parser.add_argument("--store", action="store_true", help="Request response storage. Automatically enabled when response IDs are needed")
    parser.add_argument("--retries", type=int, default=2, help="Cognitive retries after an incorrect first answer")
    parser.add_argument("--retry-policy", choices=["blind", "feedback"], default="feedback")
    parser.add_argument("--retry-context", choices=["fresh", "continued"], default="continued")
    parser.add_argument("--session", choices=["isolated", "continuous"], default="isolated")
    parser.add_argument("--condition-label", default="", help="Optional human-readable experimental condition")
    parser.add_argument("--tool-access", default="none", help="Record tool availability for reproducibility")
    parser.add_argument("--notes", default="", help="Optional run notes stored in metadata")


def command_validate(args: argparse.Namespace) -> int:
    taxonomy = Taxonomy.load(args.taxonomy)
    errors = taxonomy.validate(verify_checksums=args.verify_checksums)
    payload = {
        "valid": not errors,
        "topic_count": len(taxonomy.topics),
        "edge_count": len(taxonomy.edges),
        "errors": errors,
    }
    print(_json(payload))
    return 0 if not errors else 1


def command_generate(args: argparse.Namespace) -> int:
    taxonomy = Taxonomy.load(args.taxonomy)
    errors = taxonomy.validate(verify_checksums=args.verify_checksums)
    if errors:
        raise BenchError("Taxonomy validation failed:\n" + "\n".join(f"- {error}" for error in errors[:20]))
    suite = SuiteGenerator(taxonomy, seed=args.seed).generate(args.max_tier, args.tasks_per_tier)
    private_path = Path(args.out)
    public_path = Path(args.public_out) if args.public_out else private_path.with_name(private_path.stem + ".public.jsonl")
    write_suite_files(suite, private_path, public_path)
    template = public_path.with_name("responses.template.jsonl")
    with template.open("w", encoding="utf-8") as handle:
        for task in suite["tasks"]:
            handle.write(json.dumps({"task_id": task["id"], "attempt": 1, "text": "", "latency_ms": 0}) + "\n")
    print(_json({"private_suite": str(private_path), "public_prompts": str(public_path), "response_template": str(template), "suite_hash": suite["suite_hash"]}))
    return 0


def command_run(args: argparse.Namespace) -> int:
    suite = get_or_generate_suite(args)
    provider = build_provider(args)
    meta = {
        "provider": args.provider,
        "model": getattr(provider, "model", None) or args.model or "command",
        "effort": getattr(provider, "effort", None) or args.effort,
        "output_mode": args.output_mode,
        "transport_retries": args.transport_retries,
        "provider_version": getattr(provider, "provider_version", None),
        "condition_label": args.condition_label,
        "tool_access": args.tool_access,
        "notes": args.notes,
    }
    run = execute_run(
        suite=suite,
        provider=provider,
        run_meta=meta,
        retries=args.retries,
        retry_policy=args.retry_policy,
        retry_context=args.retry_context,
        session_mode=args.session,
        progress=not args.quiet,
    )
    out_dir = Path(args.out) / run["run_id"]
    save_run(run, out_dir)
    write_suite_files(suite, out_dir / "suite.private.json", out_dir / "suite.public.jsonl")
    print(_json({"run_dir": str(out_dir), "summary": run["summary"]}))
    return 0


def command_matrix(args: argparse.Namespace) -> int:
    if args.provider != "openai":
        raise BenchError("matrix currently supports the OpenAI provider")
    suite = get_or_generate_suite(args)
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    efforts = [item.strip() for item in args.efforts.split(",") if item.strip()]
    if not models or not efforts:
        raise BenchError("--models and --efforts must contain at least one value")
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)
    write_suite_files(suite, root / "suite.private.json", root / "suite.public.jsonl")
    runs: list[dict[str, Any]] = []
    for model in models:
        for effort in efforts:
            for repeat in range(1, args.repeats + 1):
                provider = build_provider(args, model=model, effort=effort)
                meta = {
                    "provider": args.provider,
                    "model": model,
                    "effort": effort,
                    "repeat": repeat,
                    "output_mode": args.output_mode,
                    "transport_retries": args.transport_retries,
                    "provider_version": getattr(provider, "provider_version", None),
                    "condition_label": args.condition_label,
                    "tool_access": args.tool_access,
                    "notes": args.notes,
                }
                run = execute_run(
                    suite=suite,
                    provider=provider,
                    run_meta=meta,
                    retries=args.retries,
                    retry_policy=args.retry_policy,
                    retry_context=args.retry_context,
                    session_mode=args.session,
                    progress=not args.quiet,
                )
                run_dir = root / run["run_id"]
                save_run(run, run_dir)
                runs.append(run)
    matrix = aggregate_matrix(runs)
    (root / "matrix.json").write_text(_json(matrix) + "\n", encoding="utf-8")
    (root / "matrix.html").write_text(render_matrix_html(matrix), encoding="utf-8")
    print(_json({"matrix_dir": str(root), "run_count": len(runs)}))
    return 0


def command_score(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    responses = read_jsonl(args.responses)
    meta = {
        "provider": "external",
        "model": args.model,
        "effort": args.effort,
        "source": args.source,
        "tool_access": args.tool_access,
        "notes": args.notes,
    }
    run = score_external_responses(suite, responses, meta)
    out_dir = Path(args.out) / run["run_id"]
    save_run(run, out_dir)
    print(_json({"run_dir": str(out_dir), "summary": run["summary"]}))
    return 0


def command_wave_prepare(args: argparse.Namespace) -> int:
    import taxonomy_bench_wave as wave

    suite_path = Path(args.suite)
    control_root = Path(args.control_root)
    out_dir = Path(args.out)
    if not control_root.exists() or not control_root.is_dir():
        raise BenchError(
            f"Control root {control_root} must already exist and be a directory"
        )
    suite = load_suite(suite_path)
    metadata = wave.collect_provider_metadata()
    manifest = wave.prepare_manifest(
        suite, suite_path, control_root, metadata, out_dir
    )
    print(_json({
        "manifest": str(out_dir / "manifest.json"),
        "manifest_hash": manifest["manifest_hash"],
    }))
    return 0


def _wave_controller(args: argparse.Namespace):
    import taxonomy_bench_wave as wave

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return wave.WaveController(
        manifest_path=manifest_path,
        control_root=Path(manifest["control_root"]),
        subject_root=Path(args.subject_root),
        wave_dir=manifest_path.parent,
    )


def command_wave_preflight(args: argparse.Namespace) -> int:
    controller = _wave_controller(args)
    print(_json(controller.preflight_lane(args.lane)))
    return 0


def command_wave_run(args: argparse.Namespace) -> int:
    return int(_wave_controller(args).run_lane(args.lane))


def command_wave_aggregate(args: argparse.Namespace) -> int:
    import taxonomy_bench_wave as wave

    report = wave.aggregate_pair(Path(args.manifest), args.pair)
    print(_json({"pair": args.pair, "report_dir": str(report)}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate and run a progressive AI reasoning benchmark from the Marble Skill Taxonomy."
    )
    parser.add_argument("--version", action="version", version=f"taxonomy-bench {BENCHMARK_VERSION}")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate the taxonomy graph")
    validate_parser.add_argument("--taxonomy", required=True)
    validate_parser.add_argument("--verify-checksums", action="store_true")
    validate_parser.set_defaults(func=command_validate)

    generate_parser = subparsers.add_parser("generate", help="Generate a reproducible private suite and public prompts")
    generate_parser.add_argument("--taxonomy", required=True)
    generate_parser.add_argument("--seed", type=int, default=42)
    generate_parser.add_argument("--max-tier", type=int, default=8)
    generate_parser.add_argument("--tasks-per-tier", type=int, default=4)
    generate_parser.add_argument("--verify-checksums", action="store_true")
    generate_parser.add_argument("--out", default="suite.private.json")
    generate_parser.add_argument("--public-out")
    generate_parser.set_defaults(func=command_generate)

    run_parser = subparsers.add_parser("run", help="Run one model/effort configuration")
    add_suite_source_args(run_parser)
    add_provider_args(run_parser)
    run_parser.add_argument("--out", default="runs")
    run_parser.add_argument("--quiet", action="store_true")
    run_parser.set_defaults(func=command_run)

    matrix_parser = subparsers.add_parser("matrix", help="Compare multiple model and reasoning-effort configurations")
    add_suite_source_args(matrix_parser)
    add_provider_args(matrix_parser, matrix=True)
    matrix_parser.add_argument("--models", required=True, help="Comma-separated model IDs")
    matrix_parser.add_argument("--efforts", default="low,medium,high", help="Comma-separated effort values")
    matrix_parser.add_argument("--repeats", type=int, default=1)
    matrix_parser.add_argument("--out", default="matrix-runs")
    matrix_parser.add_argument("--quiet", action="store_true")
    matrix_parser.set_defaults(func=command_matrix)

    score_parser = subparsers.add_parser("score", help="Score responses collected from a UI session or another harness")
    score_parser.add_argument("--suite", required=True)
    score_parser.add_argument("--responses", required=True)
    score_parser.add_argument("--model", default="unknown")
    score_parser.add_argument("--effort", default="unknown")
    score_parser.add_argument("--source", default="manual-session")
    score_parser.add_argument("--tool-access", default="unreported")
    score_parser.add_argument("--notes", default="")
    score_parser.add_argument("--out", default="scored-runs")
    score_parser.set_defaults(func=command_score)

    wave_parser = subparsers.add_parser(
        "wave", help="Wave 1 subscription benchmark controller"
    )
    wave_subparsers = wave_parser.add_subparsers(
        dest="wave_command", required=True
    )

    wave_prepare = wave_subparsers.add_parser(
        "prepare", help="Create an immutable Wave manifest"
    )
    wave_prepare.add_argument("--suite", required=True)
    wave_prepare.add_argument("--out", required=True)
    wave_prepare.add_argument("--control-root", required=True)
    wave_prepare.set_defaults(func=command_wave_prepare)

    wave_preflight = wave_subparsers.add_parser(
        "preflight", help="Verify one manifest-bound subscription lane"
    )
    wave_preflight.add_argument("--manifest", required=True)
    wave_preflight.add_argument("--lane", required=True, choices=sorted(
        __import__("taxonomy_bench_wave").WAVE1_LANES
    ))
    wave_preflight.add_argument("--subject-root", required=True)
    wave_preflight.set_defaults(func=command_wave_preflight)

    wave_run = wave_subparsers.add_parser(
        "run", help="Execute or resume one Wave lane"
    )
    wave_run.add_argument("--manifest", required=True)
    wave_run.add_argument("--lane", required=True, choices=sorted(
        __import__("taxonomy_bench_wave").WAVE1_LANES
    ))
    wave_run.add_argument("--subject-root", required=True)
    wave_run.set_defaults(func=command_wave_run)

    wave_aggregate = wave_subparsers.add_parser(
        "aggregate", help="Publish one completed role-matched pair"
    )
    wave_aggregate.add_argument("--manifest", required=True)
    wave_aggregate.add_argument("--pair", required=True, type=int)
    wave_aggregate.set_defaults(func=command_wave_aggregate)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BenchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
