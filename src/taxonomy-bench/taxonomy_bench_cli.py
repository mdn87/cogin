"""Subscription CLI provider infrastructure.

This module defines the base provider contract for subscription-backed
CLI invocation (Claude Code, Codex). It imports from taxonomy_bench_protocol
but never from taxonomy_bench (the main module imports from here).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from taxonomy_bench_protocol import BASE_INSTRUCTIONS, BenchError, canonical_hash, compose_subject_prompt


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Completion:
    """Result of a single provider completion call."""

    text: str
    latency_ms: float
    resolved_model: str | None = None
    response_id: str | None = None
    request_id: str | None = None
    usage: dict[str, int] = dataclasses.field(default_factory=dict)
    status: str | None = None
    incomplete_reason: str | None = None
    error: str | None = None
    error_kind: str | None = None
    provider_metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


class Provider:
    """Abstract base for all benchmark providers."""

    supports_sessions: bool = False

    def complete(
        self,
        prompt: str,
        output_schema: Mapping[str, Any],
        previous_response_id: str | None = None,
    ) -> Completion:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Infrastructure error classification
# ---------------------------------------------------------------------------

INFRA_ERROR_KINDS = frozenset({
    "authentication",
    "entitlement",
    "rate_limit",
    "timeout",
    "process",
    "malformed_provider_output",
    "model_mismatch",
    "fallback",
    "isolation",
})


# ---------------------------------------------------------------------------
# Process runner seam (injectable for testing)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ProcessResult:
    """Result of a subprocess invocation."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    latency_ms: float


ProcessRunner = Callable[
    [Sequence[str], str, Path, float, Mapping[str, str]],
    ProcessResult,
]


def _production_runner(
    args: Sequence[str],
    stdin_text: str,
    cwd: Path,
    timeout: float,
    env: Mapping[str, str],
) -> ProcessResult:
    """Real subprocess runner using shutil.which() to locate executables."""
    t0 = time.perf_counter()
    process = subprocess.run(
        list(args),
        input=stdin_text,
        text=True,
        capture_output=True,
        cwd=str(cwd),
        timeout=timeout,
        check=False,
        env=dict(env),
    )
    latency_ms = (time.perf_counter() - t0) * 1000
    return ProcessResult(
        args=tuple(args),
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Sanitized child environment
# ---------------------------------------------------------------------------

_FORBIDDEN_ENV_PREFIXES = (
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "AZURE_CLIENT_SECRET",
)


def _sanitized_env() -> dict[str, str]:
    """Build a minimal inherited environment with API keys removed."""
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if any(upper.startswith(prefix.upper()) for prefix in _FORBIDDEN_ENV_PREFIXES):
            continue
        env[key] = value
    return env


# ---------------------------------------------------------------------------
# Claude Code subscription provider
# ---------------------------------------------------------------------------


class ClaudeCliProvider(Provider):
    """Provider that invokes the Claude Code CLI with subscription auth."""

    supports_sessions = True
    family = "claude"

    def __init__(
        self,
        selector: str,
        expected_model: str | None = None,
        effort: str = "medium",
        timeout: float = 600.0,
        subject_root: Path | None = None,
        persistent: bool = False,
        runner: ProcessRunner = _production_runner,
    ) -> None:
        self.selector = selector
        self.expected_model = expected_model or selector
        self.effort = effort
        self.timeout = timeout
        self.subject_root = subject_root or Path.cwd()
        self.persistent = persistent
        self._runner = runner

        # Resolve CLI path
        self.cli_path = shutil.which("claude")
        if self.cli_path is None:
            # Windows npm global fallback
            candidate = os.path.expandvars(r"%APPDATA%\npm\claude.cmd")
            if os.path.isfile(candidate):
                self.cli_path = candidate
        if self.cli_path is None:
            raise BenchError("Claude Code CLI not found; install with npm install -g @anthropic-ai/claude-code")

        # Compute hashes for manifest metadata
        self._cached_version: str | None = None
        self.invocation_hash = canonical_hash({
            "selector": self.selector,
            "effort": self.effort,
            "tools": "",
            "safe_mode": True,
            "no_chrome": True,
            "disable_slash_commands": True,
        })
        self.tool_policy_hash = canonical_hash({
            "tools": "",
            "safe_mode": True,
            "strict_mcp_config": True,
        })
        self.auth_mode = "subscription"
        self._instruction_hash = canonical_hash(BASE_INSTRUCTIONS)

    def _cli_version(self) -> str:
        """Get installed Claude Code CLI version (cached)."""
        if self._cached_version is not None:
            return self._cached_version
        try:
            result = self._runner(
                [self.cli_path, "--version"],
                "",
                self.subject_root,
                10.0,
                _sanitized_env(),
            )
            self._cached_version = result.stdout.strip()
        except Exception:
            self._cached_version = "unknown"
        return self._cached_version

    def _invoke(self, args: list[str], stdin_text: str = "") -> ProcessResult:
        """Run the Claude CLI with sanitized environment and timeout."""
        return self._runner(
            args,
            stdin_text,
            self.subject_root,
            self.timeout,
            _sanitized_env(),
        )

    def preflight(self) -> dict[str, Any]:
        """Verify subscription authentication and model availability."""
        result = self._invoke([self.cli_path, "auth", "status", "--json"])
        if result.returncode != 0:
            raise BenchError(
                f"Claude auth check failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        try:
            status = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise BenchError(f"Claude auth status not valid JSON: {exc}") from exc

        if not status.get("loggedIn"):
            raise BenchError("Claude is not logged in")
        auth_method = status.get("authMethod", "")
        api_provider = status.get("apiProvider", "")
        if auth_method != "claude.ai" or api_provider != "firstParty":
            raise BenchError(
                f"Claude is authenticated via {auth_method}/{api_provider}, not subscription"
            )
        sub_type = status.get("subscriptionType", "unknown")
        return {
            "auth_method": auth_method,
            "subscription_type": sub_type,
            "email": status.get("email", ""),
            "organization": status.get("orgName", ""),
        }

    def complete(
        self,
        prompt: str,
        output_schema: Mapping[str, Any],
        previous_response_id: str | None = None,
    ) -> Completion:
        # Reject schema mode; Wave 1 uses prompt output only
        if isinstance(output_schema, Mapping) and output_schema.get("type"):
            # This is a structural schema, not a simple shape hint
            pass  # Accept but don't pass schema to CLI

        cli_args = [self.cli_path, "-p", "--output-format", "json"]
        cli_args.extend(["--model", self.selector])
        cli_args.extend(["--effort", self.effort])
        cli_args.extend(["--safe-mode"])
        cli_args.extend(["--tools", '""'])
        cli_args.extend(["--no-chrome"])
        cli_args.extend(["--disable-slash-commands"])

        if previous_response_id is not None:
            # Continued retry: resume the task-local session
            cli_args.extend(["--resume", previous_response_id])
        elif not self.persistent:
            # Ephemeral calibration: no session persistence
            cli_args.extend(["--no-session-persistence"])

        # Determine stdin content
        if previous_response_id is not None:
            # Continued retry: send only the retry instruction
            stdin_content = prompt
        else:
            # Fresh subject session: send full composed prompt
            stdin_content = compose_subject_prompt(prompt)

        try:
            result = self._invoke(cli_args, stdin_content)
        except subprocess.TimeoutExpired:
            return Completion(
                text="",
                latency_ms=self.timeout * 1000,
                error="Claude CLI timed out",
                error_kind="timeout",
            )
        except Exception as exc:
            return Completion(
                text="",
                latency_ms=0,
                error=f"Claude CLI process error: {type(exc).__name__}: {exc}",
                error_kind="process",
            )

        # Parse output
        if result.returncode != 0:
            return Completion(
                text=result.stdout,
                latency_ms=result.latency_ms,
                error=f"Claude CLI exited {result.returncode}: {result.stderr.strip()[:500]}",
                error_kind="process",
            )

        try:
            doc = json.loads(result.stdout)
        except json.JSONDecodeError:
            return Completion(
                text=result.stdout,
                latency_ms=result.latency_ms,
                error="Claude CLI output is not valid JSON",
                error_kind="malformed_provider_output",
            )

        # Check for error response
        if doc.get("is_error"):
            api_status = doc.get("api_error_status", "")
            error_kind = "process"
            if api_status:
                if "401" in str(api_status):
                    error_kind = "authentication"
                elif "429" in str(api_status):
                    error_kind = "rate_limit"
                elif "402" in str(api_status):
                    error_kind = "entitlement"
            return Completion(
                text=doc.get("result", ""),
                latency_ms=result.latency_ms,
                error=f"Claude returned error: {api_status or 'unknown'}",
                error_kind=error_kind,
                resolved_model=self._resolve_model(doc),
            )

        # Check for model identity
        resolved = self._resolve_model(doc)
        if resolved and not self._model_matches(resolved):
            return Completion(
                text=doc.get("result", ""),
                latency_ms=result.latency_ms,
                error=f"Model mismatch: expected {self.expected_model}, got {resolved}",
                error_kind="model_mismatch",
                resolved_model=resolved,
                response_id=doc.get("session_id"),
            )

        # Success
        return Completion(
            text=doc.get("result", ""),
            latency_ms=result.latency_ms,
            resolved_model=resolved,
            response_id=doc.get("session_id"),
            usage={
                "input_tokens": doc.get("usage", {}).get("input_tokens", 0),
                "output_tokens": doc.get("usage", {}).get("output_tokens", 0),
                "cache_creation_input_tokens": doc.get("usage", {}).get("cache_creation_input_tokens", 0),
                "cache_read_input_tokens": doc.get("usage", {}).get("cache_read_input_tokens", 0),
            },
            status=doc.get("stop_reason", "completed"),
            provider_metadata={
                "provider_version": self._cli_version(),
                "instruction_hash": self._instruction_hash,
                "invocation_hash": self.invocation_hash,
                "tool_policy_hash": self.tool_policy_hash,
            },
        )

    @staticmethod
    def _resolve_model(doc: dict[str, Any]) -> str | None:
        """Extract the primary resolved model from modelUsage."""
        model_usage = doc.get("modelUsage", {})
        if not model_usage:
            return None
        # The primary model is the non-haiku model with the most tokens
        candidates = {
            k: v.get("inputTokens", 0) + v.get("outputTokens", 0)
            for k, v in model_usage.items()
            if "haiku" not in k.lower()
        }
        if candidates:
            return max(candidates, key=lambda k: candidates[k])
        # Fallback: return the first key
        return next(iter(model_usage), None)

    def _model_matches(self, resolved: str) -> bool:
        """Check if the resolved model matches the expected selector."""
        expected_lower = self.expected_model.lower()
        resolved_lower = resolved.lower()
        return expected_lower in resolved_lower or resolved_lower in expected_lower


# ---------------------------------------------------------------------------
# Codex CLI subscription provider
# ---------------------------------------------------------------------------


class CodexCliProvider(Provider):
    """Provider that invokes the Codex CLI with subscription auth."""

    supports_sessions = True
    family = "codex"

    def __init__(
        self,
        selector: str,
        expected_model: str | None = None,
        effort: str = "medium",
        timeout: float = 600.0,
        subject_root: Path | None = None,
        persistent: bool = False,
        runner: ProcessRunner = _production_runner,
    ) -> None:
        self.selector = selector
        self.expected_model = expected_model or selector
        self.effort = effort
        self.timeout = timeout
        self.subject_root = subject_root or Path.cwd()
        self.persistent = persistent
        self._runner = runner

        # Resolve CLI path
        self.cli_path = shutil.which("codex")
        if self.cli_path is None:
            candidate = os.path.expandvars(r"%APPDATA%\npm\codex.cmd")
            if os.path.isfile(candidate):
                self.cli_path = candidate
        if self.cli_path is None:
            raise BenchError("Codex CLI not found; install with npm install -g @anthropic-ai/codex")

        self._cached_version: str | None = None
        self.invocation_hash = canonical_hash({
            "selector": self.selector,
            "sandbox": "read-only",
            "ignore_user_config": True,
            "ignore_rules": True,
        })
        self.tool_policy_hash = canonical_hash({
            "sandbox": "read-only",
            "ignore_user_config": True,
            "ignore_rules": True,
        })
        self.auth_mode = "subscription"
        self._instruction_hash = canonical_hash(BASE_INSTRUCTIONS)

    def _cli_version(self) -> str:
        if self._cached_version is not None:
            return self._cached_version
        try:
            result = self._runner(
                [self.cli_path, "--version"],
                "",
                self.subject_root,
                10.0,
                _sanitized_env(),
            )
            self._cached_version = result.stdout.strip()
        except Exception:
            self._cached_version = "unknown"
        return self._cached_version

    def _invoke(self, args: list[str], stdin_text: str = "") -> ProcessResult:
        return self._runner(
            args,
            stdin_text,
            self.subject_root,
            self.timeout,
            _sanitized_env(),
        )

    def preflight(self) -> dict[str, Any]:
        """Verify subscription authentication."""
        result = self._invoke([self.cli_path, "login", "status"])
        if result.returncode != 0:
            raise BenchError(
                f"Codex auth check failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        stdout = result.stdout.strip()
        if "Logged in using ChatGPT" not in stdout:
            raise BenchError(f"Codex not authenticated via ChatGPT subscription: {stdout}")
        return {"auth_method": "chatgpt", "raw": stdout}

    def complete(
        self,
        prompt: str,
        output_schema: Mapping[str, Any],
        previous_response_id: str | None = None,
    ) -> Completion:
        if previous_response_id is not None:
            # Continued retry: resume the task-local session
            cli_args = [
                self.cli_path, "exec", "resume", previous_response_id,
                "--json", "--sandbox", "read-only",
                "--ignore-user-config", "--ignore-rules",
                "--skip-git-repo-check",
                "--cd", str(self.subject_root),
            ]
            stdin_content = prompt  # Retry instruction only
        else:
            cli_args = [
                self.cli_path, "exec", "--json",
                "--sandbox", "read-only",
                "--skip-git-repo-check",
                "--ignore-user-config", "--ignore-rules",
                "-m", self.selector,
                "-",
            ]
            if not self.persistent:
                cli_args.append("--ephemeral")
            if self.subject_root:
                cli_args.extend(["--cd", str(self.subject_root)])
            stdin_content = compose_subject_prompt(prompt)

        try:
            result = self._invoke(cli_args, stdin_content)
        except subprocess.TimeoutExpired:
            return Completion(
                text="",
                latency_ms=self.timeout * 1000,
                error="Codex CLI timed out",
                error_kind="timeout",
            )
        except Exception as exc:
            return Completion(
                text="",
                latency_ms=0,
                error=f"Codex CLI process error: {type(exc).__name__}: {exc}",
                error_kind="process",
            )

        if result.returncode != 0:
            error_kind = "process"
            stderr_lower = result.stderr.lower()
            if "authentication" in stderr_lower or "login" in stderr_lower:
                error_kind = "authentication"
            elif "rate limit" in stderr_lower:
                error_kind = "rate_limit"
            return Completion(
                text=result.stdout,
                latency_ms=result.latency_ms,
                error=f"Codex CLI exited {result.returncode}: {result.stderr.strip()[:500]}",
                error_kind=error_kind,
            )

        # Parse JSONL
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        thread_id: str | None = None
        response_text: str | None = None
        usage: dict[str, int] = {}
        resolved_model: str | None = None

        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                return Completion(
                    text=result.stdout,
                    latency_ms=result.latency_ms,
                    error="Codex CLI output contains invalid JSONL",
                    error_kind="malformed_provider_output",
                )

            event_type = event.get("type", "")

            if event_type == "thread.started":
                thread_id = event.get("thread_id")

            elif event_type == "item.completed":
                item = event.get("item", {})
                if item.get("type") == "agent_message":
                    response_text = item.get("text", "")

            elif event_type == "turn.completed":
                raw_usage = event.get("usage", {})
                if isinstance(raw_usage, dict):
                    usage = {
                        "input_tokens": raw_usage.get("input_tokens", 0),
                        "cached_input_tokens": raw_usage.get("cached_input_tokens", 0),
                        "cache_write_input_tokens": raw_usage.get("cache_write_input_tokens", 0),
                        "output_tokens": raw_usage.get("output_tokens", 0),
                        "reasoning_output_tokens": raw_usage.get("reasoning_output_tokens", 0),
                    }

        if response_text is None:
            return Completion(
                text="",
                latency_ms=result.latency_ms,
                error="Codex CLI produced no agent_message",
                error_kind="malformed_provider_output",
                response_id=thread_id,
            )

        if not self.persistent and previous_response_id is None:
            # Ephemeral — no thread_id check needed
            pass
        elif self.persistent and thread_id is None:
            return Completion(
                text=response_text,
                latency_ms=result.latency_ms,
                error="Codex CLI produced no thread_id for persisted session",
                error_kind="malformed_provider_output",
            )

        # Note: Codex 0.146.0 does not emit model identity in JSONL output.
        # We record the requested selector as resolved_model since the CLI
        # does not provide a way to independently verify.
        resolved_model = self.selector if not resolved_model else resolved_model

        return Completion(
            text=response_text,
            latency_ms=result.latency_ms,
            resolved_model=resolved_model,
            response_id=thread_id,
            usage=usage,
            status="completed",
            provider_metadata={
                "provider_version": self._cli_version(),
                "instruction_hash": self._instruction_hash,
                "invocation_hash": self.invocation_hash,
                "tool_policy_hash": self.tool_policy_hash,
            },
        )