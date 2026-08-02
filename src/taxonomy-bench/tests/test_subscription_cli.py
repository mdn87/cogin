"""Sanitized subscription CLI characterization tests.

These fixtures are based on live CLI output captured on 2026-08-01 with
Codex CLI 0.146.0 and Claude Code 2.1.195. Real identifiers, account
details, timestamps, and usage values have been replaced with obvious
fixture values. No raw CLI output is committed.
"""

from __future__ import annotations

import json
import os as _os_module
from pathlib import Path as _Path

from taxonomy_bench_cli import (
    ClaudeCliProvider,
    CodexCliProvider,
    ProcessResult,
)
from taxonomy_bench_protocol import BASE_INSTRUCTIONS


# ---------------------------------------------------------------------------
# Sanitized Codex JSONL fixture (actual observed shape, 2026-08-01)
# ---------------------------------------------------------------------------

CODEX_SUCCESS_JSONL = """\
{"type":"thread.started","thread_id":"thread_fixture"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{\\"ok\\":true}"}}
{"type":"turn.completed","usage":{"input_tokens":17997,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":9,"reasoning_output_tokens":0}}
"""

CODEX_JSONL_WITH_REASONING = """\
{"type":"thread.started","thread_id":"thread_fixture_2"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{\\"answer\\":42}"}}
{"type":"turn.completed","usage":{"input_tokens":18000,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":50,"reasoning_output_tokens":200}}
"""

CODEX_MALFORMED_JSONL = """\
{"type":"thread.started","thread_id":"thread_fixture_bad"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{\\"ok\\":true}"
"""

CODEX_NO_AGENT_MESSAGE = """\
{"type":"thread.started","thread_id":"thread_fixture_no_msg"}
{"type":"turn.started"}
{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":4}}
"""

CODEX_NO_THREAD_ID = """\
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{}"}}
{"type":"turn.completed","usage":{}}
"""

CODEX_AUTH_FAILURE_STDERR = "Error: Authentication failed. Please run `codex login`."
CODEX_RATE_LIMIT_STDERR = "Error: Rate limit exceeded. Please try again later."


# ---------------------------------------------------------------------------
# Sanitized Claude JSON fixture (actual observed shape, 2026-08-01)
# ---------------------------------------------------------------------------

CLAUDE_SUCCESS_JSON = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "api_error_status": None,
    "duration_ms": 2418,
    "duration_api_ms": 3404,
    "num_turns": 1,
    "result": '{"ok":true}',
    "stop_reason": "end_turn",
    "session_id": "session_fixture",
    "total_cost_usd": 0.058967,
    "usage": {
        "input_tokens": 1,
        "cache_creation_input_tokens": 2897,
        "cache_read_input_tokens": 0,
        "output_tokens": 9,
    },
    "modelUsage": {
        "claude-fable-5": {
            "inputTokens": 1,
            "outputTokens": 9,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 2897,
            "webSearchRequests": 0,
            "costUSD": 0.0584,
            "contextWindow": 1000000,
            "maxOutputTokens": 64000,
        },
        "claude-haiku-4-5-20251001": {
            "inputTokens": 507,
            "outputTokens": 12,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 0,
            "webSearchRequests": 0,
            "costUSD": 0.000567,
            "contextWindow": 200000,
            "maxOutputTokens": 32000,
        },
    },
    "permission_denials": [],
    "terminal_reason": "completed",
    "uuid": "uuid_fixture",
}

CLAUDE_SUCCESS_ALT_MODEL = {
    **CLAUDE_SUCCESS_JSON,
    "modelUsage": {
        "claude-opus-5": {
            "inputTokens": 50,
            "outputTokens": 10,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 5000,
            "webSearchRequests": 0,
            "costUSD": 0.75,
            "contextWindow": 1000000,
            "maxOutputTokens": 64000,
        }
    },
    "result": '{"ok":true}',
}

CLAUDE_AUTH_ERROR_JSON = {
    "type": "result",
    "subtype": "error_during_execution",
    "is_error": True,
    "api_error_status": "401 Unauthorized",
    "duration_ms": 100,
    "duration_api_ms": 0,
    "num_turns": 0,
    "result": "",
    "session_id": None,
    "stop_reason": "error",
    "total_cost_usd": 0,
    "usage": {},
    "modelUsage": {},
    "permission_denials": [],
    "terminal_reason": "error",
}

CLAUDE_RATE_LIMIT_JSON = {
    "type": "result",
    "subtype": "error_during_execution",
    "is_error": True,
    "api_error_status": "429 Too Many Requests",
    "duration_ms": 500,
    "duration_api_ms": 0,
    "num_turns": 0,
    "result": "",
    "session_id": None,
    "stop_reason": "error",
    "total_cost_usd": 0,
    "usage": {},
    "modelUsage": {},
    "permission_denials": [],
    "terminal_reason": "error",
}

CLAUDE_MODEL_MISMATCH_JSON = {
    **CLAUDE_SUCCESS_JSON,
    "modelUsage": {
        "claude-sonnet-5": {
            "inputTokens": 1,
            "outputTokens": 9,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 2897,
            "webSearchRequests": 0,
            "costUSD": 0.0584,
            "contextWindow": 1000000,
            "maxOutputTokens": 64000,
        },
        "claude-haiku-4-5-20251001": {
            "inputTokens": 507,
            "outputTokens": 12,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 0,
            "webSearchRequests": 0,
            "costUSD": 0.000567,
            "contextWindow": 200000,
            "maxOutputTokens": 32000,
        },
    },
}

CLAUDE_NO_SESSION_JSON = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "api_error_status": None,
    "duration_ms": 2000,
    "duration_api_ms": 3000,
    "num_turns": 1,
    "result": '{"ok":true}',
    "stop_reason": "end_turn",
    "session_id": None,
    "total_cost_usd": 0.05,
    "usage": {"input_tokens": 1, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 0, "output_tokens": 9},
    "modelUsage": {
        "claude-sonnet-5": {
            "inputTokens": 1,
            "outputTokens": 9,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 1000,
            "webSearchRequests": 0,
            "costUSD": 0.05,
            "contextWindow": 1000000,
            "maxOutputTokens": 64000,
        }
    },
    "permission_denials": [],
    "terminal_reason": "completed",
}

CLAUDE_ERROR_JSON = {
    "type": "result",
    "subtype": "error_during_execution",
    "is_error": True,
    "api_error_status": None,
    "duration_ms": 2840,
    "num_turns": 1,
    "result": "",
    "session_id": "session_fixture_err",
    "stop_reason": "error",
    "total_cost_usd": 0,
    "usage": {"input_tokens": 0, "output_tokens": 0},
    "modelUsage": {},
    "permission_denials": [],
    "terminal_reason": "error",
}


# ---------------------------------------------------------------------------
# Fixture-shape tests
# ---------------------------------------------------------------------------

class TestCodexFixtureShape:
    def test_codex_success_lines_are_valid_json(self):
        for line in CODEX_SUCCESS_JSONL.splitlines():
            if line.strip():
                obj = json.loads(line)
                assert isinstance(obj, dict)

    def test_codex_success_has_thread_id(self):
        lines = [json.loads(line) for line in CODEX_SUCCESS_JSONL.splitlines() if line.strip()]
        assert lines[0]["type"] == "thread.started"
        assert "thread_id" in lines[0]

    def test_codex_success_has_agent_message(self):
        lines = [json.loads(line) for line in CODEX_SUCCESS_JSONL.splitlines() if line.strip()]
        agent_msgs = [line for line in lines if line.get("type") == "item.completed" and line.get("item", {}).get("type") == "agent_message"]
        assert len(agent_msgs) >= 1
        assert "text" in agent_msgs[0]["item"]

    def test_codex_success_has_usage(self):
        lines = [json.loads(line) for line in CODEX_SUCCESS_JSONL.splitlines() if line.strip()]
        turns = [line for line in lines if line.get("type") == "turn.completed"]
        assert len(turns) >= 1
        assert "usage" in turns[0]

    def test_codex_no_model_field(self):
        lines = [json.loads(line) for line in CODEX_SUCCESS_JSONL.splitlines() if line.strip()]
        for line in lines:
            assert "model" not in line

    def test_codex_no_agent_message_has_no_text(self):
        lines = [json.loads(line) for line in CODEX_NO_AGENT_MESSAGE.splitlines() if line.strip()]
        agent_msgs = [line for line in lines if line.get("type") == "item.completed" and line.get("item", {}).get("type") == "agent_message"]
        assert len(agent_msgs) == 0

    def test_codex_no_thread_id_missing(self):
        lines = [json.loads(line) for line in CODEX_NO_THREAD_ID.splitlines() if line.strip()]
        threads = [line for line in lines if line.get("type") == "thread.started"]
        assert len(threads) == 0

    def test_codex_with_reasoning_has_usage(self):
        lines = [json.loads(line) for line in CODEX_JSONL_WITH_REASONING.splitlines() if line.strip()]
        turns = [line for line in lines if line.get("type") == "turn.completed"]
        assert len(turns) >= 1
        assert "reasoning_output_tokens" in turns[0]["usage"]


class TestClaudeFixtureShape:
    def test_claude_success_is_valid_json(self):
        assert isinstance(CLAUDE_SUCCESS_JSON, dict)

    def test_claude_success_has_session_id(self):
        assert CLAUDE_SUCCESS_JSON["session_id"] == "session_fixture"

    def test_claude_success_has_result_field(self):
        assert "result" in CLAUDE_SUCCESS_JSON
        assert CLAUDE_SUCCESS_JSON["result"] is not None

    def test_claude_success_has_model_usage(self):
        assert "modelUsage" in CLAUDE_SUCCESS_JSON
        assert isinstance(CLAUDE_SUCCESS_JSON["modelUsage"], dict)
        assert len(CLAUDE_SUCCESS_JSON["modelUsage"]) > 0

    def test_claude_error_is_error_true(self):
        assert CLAUDE_ERROR_JSON["is_error"] is True

    def test_claude_auth_error_has_status(self):
        assert CLAUDE_AUTH_ERROR_JSON["api_error_status"] == "401 Unauthorized"
        assert CLAUDE_AUTH_ERROR_JSON["session_id"] is None

    def test_claude_rate_limit_has_status(self):
        assert CLAUDE_RATE_LIMIT_JSON["api_error_status"] == "429 Too Many Requests"

    def test_claude_model_mismatch_has_wrong_model(self):
        primary_models = [k for k in CLAUDE_MODEL_MISMATCH_JSON["modelUsage"] if k.startswith("claude-") and "haiku" not in k]
        assert "claude-sonnet-5" in primary_models
        assert "claude-opus-5" not in primary_models

    def test_claude_no_session_is_none(self):
        assert CLAUDE_NO_SESSION_JSON["session_id"] is None

    def test_claude_success_is_error_false(self):
        assert CLAUDE_SUCCESS_JSON["is_error"] is False

    def test_claude_alt_model_has_opus(self):
        assert "claude-opus-5" in CLAUDE_SUCCESS_ALT_MODEL["modelUsage"]


# ---------------------------------------------------------------------------
# Provider tests with fake process runners
# ---------------------------------------------------------------------------

INFRA_ERROR_KINDS = {
    "authentication", "entitlement", "rate_limit", "timeout",
    "process", "malformed_provider_output", "model_mismatch",
    "fallback", "isolation",
}


def _make_claude_success(model_name: str) -> dict:
    """Create a Claude success fixture with the given model."""
    return {
        **CLAUDE_SUCCESS_JSON,
        "modelUsage": {
            model_name: {
                "inputTokens": 1, "outputTokens": 9,
                "cacheReadInputTokens": 0, "cacheCreationInputTokens": 2897,
                "webSearchRequests": 0, "costUSD": 0.0584,
                "contextWindow": 1000000, "maxOutputTokens": 64000,
            }
        },
    }


def _fake_runner(stdout: str, returncode: int = 0, stderr: str = "", latency_ms: float = 100.0):
    def runner(args, stdin_text, cwd, timeout, env):
        return ProcessResult(args=tuple(args), returncode=returncode, stdout=stdout, stderr=stderr, latency_ms=latency_ms)
    return runner


def _find_model_invocation(captured: list[ProcessResult]) -> ProcessResult:
    """Find the model-invocation call (not the --version call)."""
    for r in captured:
        args = list(r.args)
        if "-p" in args or "exec" in args:
            return r
    return captured[-1]


class TestClaudeProvider:

    def test_claude_command_construction_fresh(self):
        captured: list[ProcessResult] = []
        json_ok = json.dumps(_make_claude_success("claude-fable-5"))

        def record_runner(args, stdin_text, cwd, timeout, env):
            r = ProcessResult(args=tuple(args), returncode=0, stdout=json_ok, stderr="", latency_ms=100.0)
            captured.append(r)
            return r

        provider = ClaudeCliProvider(selector="claude-fable-5", subject_root=_Path.cwd(), persistent=True, runner=record_runner)
        provider.cli_path = "claude"
        result = provider.complete("Test prompt", {})
        assert result.text == '{"ok":true}'
        assert not result.error
        assert len(captured) >= 1
        invocation = _find_model_invocation(captured)
        args = list(invocation.args)
        assert "--model" in args
        assert "claude-fable-5" in args
        assert "--output-format" in args
        assert "json" in args
        assert "--safe-mode" in args
        assert "--tools" in args
        assert "--no-chrome" in args
        assert "--disable-slash-commands" in args
        assert "--no-session-persistence" not in args
        assert "--resume" not in args

    def test_claude_command_construction_ephemeral(self):
        captured: list[ProcessResult] = []
        json_ok = json.dumps(_make_claude_success("claude-sonnet-5"))

        def record_runner(args, stdin_text, cwd, timeout, env):
            r = ProcessResult(args=tuple(args), returncode=0, stdout=json_ok, stderr="", latency_ms=100.0)
            captured.append(r)
            return r

        provider = ClaudeCliProvider(selector="claude-sonnet-5", persistent=False, runner=record_runner)
        provider.cli_path = "claude"
        result = provider.complete("Test", {})
        assert not result.error
        invocation = _find_model_invocation(captured)
        args = list(invocation.args)
        assert "--no-session-persistence" in args

    def test_claude_command_construction_continuation(self):
        captured: list[ProcessResult] = []
        json_ok = json.dumps(_make_claude_success("claude-opus-5"))

        def record_runner(args, stdin_text, cwd, timeout, env):
            r = ProcessResult(args=tuple(args), returncode=0, stdout=json_ok, stderr="", latency_ms=100.0)
            captured.append(r)
            return r

        provider = ClaudeCliProvider(selector="claude-opus-5", runner=record_runner)
        provider.cli_path = "claude"
        result = provider.complete("Retry instruction", {}, previous_response_id="session_fixture")
        assert not result.error
        invocation = _find_model_invocation(captured)
        args = list(invocation.args)
        assert "--resume" in args
        assert "session_fixture" in args

    def test_claude_auth_rejection(self):
        runner = _fake_runner(json.dumps(CLAUDE_AUTH_ERROR_JSON))
        provider = ClaudeCliProvider(selector="claude-fable-5", runner=runner)
        provider.cli_path = "claude"
        result = provider.complete("prompt", {})
        assert result.error is not None
        assert result.error_kind == "authentication"

    def test_claude_rate_limit(self):
        runner = _fake_runner(json.dumps(CLAUDE_RATE_LIMIT_JSON))
        provider = ClaudeCliProvider(selector="claude-fable-5", runner=runner)
        provider.cli_path = "claude"
        result = provider.complete("prompt", {})
        assert result.error_kind == "rate_limit"

    def test_claude_model_mismatch(self):
        runner = _fake_runner(json.dumps(CLAUDE_MODEL_MISMATCH_JSON))
        provider = ClaudeCliProvider(selector="claude-opus-5", expected_model="claude-opus-5", runner=runner)
        provider.cli_path = "claude"
        result = provider.complete("prompt", {})
        assert result.error_kind == "model_mismatch"

    def test_claude_missing_session_id_ephemeral(self):
        runner = _fake_runner(json.dumps(CLAUDE_NO_SESSION_JSON))
        provider = ClaudeCliProvider(selector="claude-sonnet-5", persistent=False, runner=runner)
        provider.cli_path = "claude"
        result = provider.complete("prompt", {})
        assert result.response_id is None
        assert not result.error

    def test_claude_prompt_goes_through_stdin(self):
        captured_stdin: list[str] = []
        json_ok = json.dumps(_make_claude_success("claude-fable-5"))

        def record_runner(args, stdin_text, cwd, timeout, env):
            captured_stdin.append(stdin_text)
            return ProcessResult(args=tuple(args), returncode=0, stdout=json_ok, stderr="", latency_ms=100.0)

        provider = ClaudeCliProvider(selector="claude-fable-5", runner=record_runner)
        provider.cli_path = "claude"
        prompt = 'Return {"key": "value"} and unicode test'
        provider.complete(prompt, {})
        assert len(captured_stdin) >= 1
        assert BASE_INSTRUCTIONS in captured_stdin[0]
        assert prompt in captured_stdin[0]

    def test_claude_continuation_stdin_instruction_only(self):
        captured_stdin: list[str] = []
        json_ok = json.dumps(_make_claude_success("claude-fable-5"))

        def record_runner(args, stdin_text, cwd, timeout, env):
            captured_stdin.append(stdin_text)
            return ProcessResult(args=tuple(args), returncode=0, stdout=json_ok, stderr="", latency_ms=100.0)

        provider = ClaudeCliProvider(selector="claude-fable-5", runner=record_runner)
        provider.cli_path = "claude"
        retry_msg = "Retry 1. Correct your answer."
        provider.complete(retry_msg, {}, previous_response_id="session_fixture")
        assert len(captured_stdin) >= 1
        assert captured_stdin[0] == retry_msg
        assert BASE_INSTRUCTIONS not in captured_stdin[0]

    def test_claude_env_sanitization(self):
        captured_envs: list[dict] = []
        json_ok = json.dumps(_make_claude_success("claude-fable-5"))
        _os_module.environ["OPENAI_API_KEY"] = "test-key-openai"
        _os_module.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
        _os_module.environ["ANTHROPIC_AUTH_TOKEN"] = "test-token"

        def record_runner(args, stdin_text, cwd, timeout, env):
            captured_envs.append(dict(env))
            return ProcessResult(args=tuple(args), returncode=0, stdout=json_ok, stderr="", latency_ms=100.0)

        try:
            provider = ClaudeCliProvider(selector="claude-fable-5", runner=record_runner)
            provider.cli_path = "claude"
            provider.complete("test", {})
            assert len(captured_envs) >= 1
            env = captured_envs[0]
            forbidden = {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}
            for key in env:
                assert key.upper() not in {f.upper() for f in forbidden}, f"Forbidden key in env: {key}"
        finally:
            del _os_module.environ["OPENAI_API_KEY"]
            del _os_module.environ["ANTHROPIC_API_KEY"]
            del _os_module.environ["ANTHROPIC_AUTH_TOKEN"]

    def test_claude_provider_metadata(self):
        json_ok = json.dumps(_make_claude_success("claude-fable-5"))
        runner = _fake_runner(json_ok)
        provider = ClaudeCliProvider(selector="claude-fable-5", runner=runner)
        provider.cli_path = "claude"
        result = provider.complete("prompt", {})
        assert "instruction_hash" in result.provider_metadata
        assert "invocation_hash" in result.provider_metadata
        assert "tool_policy_hash" in result.provider_metadata


class TestCodexProvider:

    def test_codex_command_construction_fresh(self):
        captured: list[ProcessResult] = []

        def record_runner(args, stdin_text, cwd, timeout, env):
            r = ProcessResult(args=tuple(args), returncode=0, stdout=CODEX_SUCCESS_JSONL, stderr="", latency_ms=100.0)
            captured.append(r)
            return r

        provider = CodexCliProvider(selector="gpt-5.6-sol", subject_root=_Path.cwd(), persistent=True, runner=record_runner)
        provider.cli_path = "codex"
        result = provider.complete("Test prompt", {})
        assert result.text == '{"ok":true}'
        assert not result.error
        assert len(captured) >= 1
        invocation = _find_model_invocation(captured)
        args = list(invocation.args)
        assert "--json" in args
        assert "--sandbox" in args
        assert "read-only" in args
        assert "--skip-git-repo-check" in args
        assert "--ignore-user-config" in args
        assert "--ignore-rules" in args
        assert "-m" in args
        assert "gpt-5.6-sol" in args
        assert "--ephemeral" not in args

    def test_codex_command_construction_ephemeral(self):
        captured: list[ProcessResult] = []

        def record_runner(args, stdin_text, cwd, timeout, env):
            r = ProcessResult(args=tuple(args), returncode=0, stdout=CODEX_SUCCESS_JSONL, stderr="", latency_ms=100.0)
            captured.append(r)
            return r

        provider = CodexCliProvider(selector="gpt-5.6-sol", persistent=False, runner=record_runner)
        provider.cli_path = "codex"
        result = provider.complete("Test", {})
        assert not result.error
        invocation = _find_model_invocation(captured)
        args = list(invocation.args)
        assert "--ephemeral" in args

    def test_codex_command_construction_continuation(self):
        captured: list[ProcessResult] = []

        def record_runner(args, stdin_text, cwd, timeout, env):
            r = ProcessResult(args=tuple(args), returncode=0, stdout=CODEX_SUCCESS_JSONL, stderr="", latency_ms=100.0)
            captured.append(r)
            return r

        provider = CodexCliProvider(selector="gpt-5.6-sol", runner=record_runner)
        provider.cli_path = "codex"
        result = provider.complete("Retry", {}, previous_response_id="thread_fixture")
        assert not result.error
        invocation = _find_model_invocation(captured)
        args = list(invocation.args)
        assert "resume" in args
        assert "thread_fixture" in args

    def test_codex_malformed_jsonl(self):
        runner = _fake_runner(CODEX_MALFORMED_JSONL)
        provider = CodexCliProvider(selector="gpt-5.6-sol", runner=runner)
        provider.cli_path = "codex"
        result = provider.complete("test", {})
        assert result.error_kind == "malformed_provider_output"

    def test_codex_no_agent_message(self):
        runner = _fake_runner(CODEX_NO_AGENT_MESSAGE)
        provider = CodexCliProvider(selector="gpt-5.6-sol", runner=runner)
        provider.cli_path = "codex"
        result = provider.complete("test", {})
        assert result.error_kind == "malformed_provider_output"

    def test_codex_thread_id_present(self):
        runner = _fake_runner(CODEX_SUCCESS_JSONL)
        provider = CodexCliProvider(selector="gpt-5.6-sol", runner=runner)
        provider.cli_path = "codex"
        result = provider.complete("test", {})
        assert result.response_id == "thread_fixture"

    def test_codex_prompt_goes_through_stdin(self):
        captured_stdin: list[str] = []

        def record_runner(args, stdin_text, cwd, timeout, env):
            captured_stdin.append(stdin_text)
            return ProcessResult(args=tuple(args), returncode=0, stdout=CODEX_SUCCESS_JSONL, stderr="", latency_ms=100.0)

        provider = CodexCliProvider(selector="gpt-5.6-sol", runner=record_runner)
        provider.cli_path = "codex"
        prompt = "Test prompt with unicode"
        provider.complete(prompt, {})
        assert len(captured_stdin) >= 1
        assert BASE_INSTRUCTIONS in captured_stdin[0]
        assert prompt in captured_stdin[0]

    def test_codex_continuation_stdin_instruction_only(self):
        captured_stdin: list[str] = []

        def record_runner(args, stdin_text, cwd, timeout, env):
            captured_stdin.append(stdin_text)
            return ProcessResult(args=tuple(args), returncode=0, stdout=CODEX_SUCCESS_JSONL, stderr="", latency_ms=100.0)

        provider = CodexCliProvider(selector="gpt-5.6-sol", runner=record_runner)
        provider.cli_path = "codex"
        retry_msg = "Retry 1. Fix it."
        provider.complete(retry_msg, {}, previous_response_id="thread_fixture")
        assert len(captured_stdin) >= 1
        assert captured_stdin[0] == retry_msg
        assert BASE_INSTRUCTIONS not in captured_stdin[0]

    def test_codex_env_sanitization(self):
        captured_envs: list[dict] = []
        _os_module.environ["OPENAI_API_KEY"] = "test-key-openai"
        _os_module.environ["CODEX_API_KEY"] = "test-key-codex"

        def record_runner(args, stdin_text, cwd, timeout, env):
            captured_envs.append(dict(env))
            return ProcessResult(args=tuple(args), returncode=0, stdout=CODEX_SUCCESS_JSONL, stderr="", latency_ms=100.0)

        try:
            provider = CodexCliProvider(selector="gpt-5.6-sol", runner=record_runner)
            provider.cli_path = "codex"
            provider.complete("test", {})
            assert len(captured_envs) >= 1
            env = captured_envs[0]
            for key in env:
                assert "API_KEY" not in key.upper() or "CODEX" not in key
                assert "OPENAI_API_KEY" not in key.upper()
        finally:
            del _os_module.environ["OPENAI_API_KEY"]
            del _os_module.environ["CODEX_API_KEY"]