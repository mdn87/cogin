"""Sanitized subscription CLI characterization tests.

These fixtures are based on live CLI output captured on 2026-08-01 with
Codex CLI 0.146.0 and Claude Code 2.1.195. Real identifiers, account
details, timestamps, and usage values have been replaced with obvious
fixture values. No raw CLI output is committed.
"""

from __future__ import annotations

import json


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

# Codex error: malformed JSONL (incomplete line)
CODEX_MALFORMED_JSONL = """\
{"type":"thread.started","thread_id":"thread_fixture_bad"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{\\"ok\\":true}"
"""

# Codex output without agent_message item
CODEX_NO_AGENT_MESSAGE = """\
{"type":"thread.started","thread_id":"thread_fixture_no_msg"}
{"type":"turn.started"}
{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":4}}
"""

# Codex output without thread_id
CODEX_NO_THREAD_ID = """\
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{}"}}
{"type":"turn.completed","usage":{}}
"""

# Codex nonzero exit (simulated stderr)
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
    "ttft_ms": 2368,
    "ttft_stream_ms": 2258,
    "time_to_request_ms": 16,
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
        "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
        "service_tier": "standard",
        "cache_creation": {"ephemeral_1h_input_tokens": 2897, "ephemeral_5m_input_tokens": 0},
        "inference_geo": "not_available",
        "iterations": [
            {
                "input_tokens": 1,
                "output_tokens": 9,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 2897,
                "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 2897},
                "type": "message",
            }
        ],
        "speed": "standard",
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

# Claude error: is_error true
CLAUDE_ERROR_JSON = {
    "type": "result",
    "subtype": "error_during_execution",
    "is_error": True,
    "api_error_status": None,
    "duration_ms": 2840,
    "duration_api_ms": 0,
    "num_turns": 1,
    "result": "",
    "session_id": "session_fixture_err",
    "stop_reason": "error",
    "total_cost_usd": 0,
    "usage": {
        "input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 0,
    },
    "modelUsage": {},
    "permission_denials": [],
    "terminal_reason": "error",
    "uuid": "uuid_fixture",
}

# Claude auth failure (simulated)
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
    "uuid": "uuid_fixture",
}

# Claude rate limit
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
    "uuid": "uuid_fixture",
}

# Claude model mismatch (provider reported a different model than requested)
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

# Claude missing session ID (no-session-persistence used for calibration = no session_id)
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
    "usage": {
        "input_tokens": 1,
        "cache_creation_input_tokens": 1000,
        "cache_read_input_tokens": 0,
        "output_tokens": 9,
    },
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
    "uuid": "uuid_fixture",
}


# ---------------------------------------------------------------------------
# Step 4: Fixture-shape tests (each shape is valid/parseable)
# ---------------------------------------------------------------------------


class TestCodexFixtureShape:
    def test_codex_success_lines_are_valid_json(self):
        """Each line of the sanitized Codex JSONL must be valid JSON."""
        for line in CODEX_SUCCESS_JSONL.splitlines():
            if line.strip():
                obj = json.loads(line)
                assert isinstance(obj, dict)

    def test_codex_success_has_thread_id(self):
        """First event must be thread.started with a thread_id."""
        lines = [json.loads(line) for line in CODEX_SUCCESS_JSONL.splitlines() if line.strip()]
        assert lines[0]["type"] == "thread.started"
        assert "thread_id" in lines[0]

    def test_codex_success_has_agent_message(self):
        """An item.completed with agent_message type must be present."""
        lines = [json.loads(line) for line in CODEX_SUCCESS_JSONL.splitlines() if line.strip()]
        agent_msgs = [
            line for line in lines
            if line.get("type") == "item.completed"
            and line.get("item", {}).get("type") == "agent_message"
        ]
        assert len(agent_msgs) >= 1
        assert "text" in agent_msgs[0]["item"]

    def test_codex_success_has_usage(self):
        """A turn.completed with usage must be present."""
        lines = [json.loads(line) for line in CODEX_SUCCESS_JSONL.splitlines() if line.strip()]
        turns = [line for line in lines if line.get("type") == "turn.completed"]
        assert len(turns) >= 1
        assert "usage" in turns[0]

    def test_codex_no_model_field(self):
        """Verify: Codex JSONL has no model field in any event (blocking discovery)."""
        lines = [json.loads(line) for line in CODEX_SUCCESS_JSONL.splitlines() if line.strip()]
        for line in lines:
            assert "model" not in line, f"Unexpected model field: {line}"

    def test_codex_malformed_jsonl_is_invalid(self):
        """Malformed JSONL must fail parsing."""
        lines = CODEX_MALFORMED_JSONL.splitlines()
        with open("/nul") as f:
            pass
        parse_errors = 0
        for i, line in enumerate(lines):
            if line.strip():
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    parse_errors += 1
        assert parse_errors > 0, "Expected at least one parse error in malformed JSONL"

    def test_codex_no_agent_message_has_no_text(self):
        """Output without agent_message yields no text."""
        lines = [json.loads(line) for line in CODEX_NO_AGENT_MESSAGE.splitlines() if line.strip()]
        agent_msgs = [
            line for line in lines
            if line.get("type") == "item.completed"
            and line.get("item", {}).get("type") == "agent_message"
        ]
        assert len(agent_msgs) == 0

    def test_codex_no_thread_id_missing(self):
        """Output without thread.started has no thread_id."""
        lines = [json.loads(line) for line in CODEX_NO_THREAD_ID.splitlines() if line.strip()]
        threads = [line for line in lines if line.get("type") == "thread.started"]
        assert len(threads) == 0

    def test_codex_with_reasoning_has_usage(self):
        """Codex output with reasoning tokens still has usage."""
        lines = [json.loads(line) for line in CODEX_JSONL_WITH_REASONING.splitlines() if line.strip()]
        turns = [line for line in lines if line.get("type") == "turn.completed"]
        assert len(turns) >= 1
        assert "reasoning_output_tokens" in turns[0]["usage"]


class TestClaudeFixtureShape:
    def test_claude_success_is_valid_json(self):
        """Sanitized Claude JSON document must be valid."""
        assert isinstance(CLAUDE_SUCCESS_JSON, dict)

    def test_claude_success_has_session_id(self):
        """Successful Claude response must have a session_id."""
        assert CLAUDE_SUCCESS_JSON["session_id"] == "session_fixture"

    def test_claude_success_has_result_field(self):
        """Successful Claude response must have a result field."""
        assert "result" in CLAUDE_SUCCESS_JSON
        assert CLAUDE_SUCCESS_JSON["result"] is not None

    def test_claude_success_has_model_usage(self):
        """Claude response must have modelUsage dict with resolved model."""
        assert "modelUsage" in CLAUDE_SUCCESS_JSON
        assert isinstance(CLAUDE_SUCCESS_JSON["modelUsage"], dict)
        assert len(CLAUDE_SUCCESS_JSON["modelUsage"]) > 0

    def test_claude_error_is_error_true(self):
        """Claude error fixture has is_error=True."""
        assert CLAUDE_ERROR_JSON["is_error"] is True

    def test_claude_auth_error_has_status(self):
        """Claude auth error fixture has API error status."""
        assert CLAUDE_AUTH_ERROR_JSON["api_error_status"] == "401 Unauthorized"
        assert CLAUDE_AUTH_ERROR_JSON["session_id"] is None

    def test_claude_rate_limit_has_status(self):
        """Claude rate limit fixture has API error status."""
        assert CLAUDE_RATE_LIMIT_JSON["api_error_status"] == "429 Too Many Requests"

    def test_claude_model_mismatch_has_wrong_model(self):
        """Claude model mismatch has a different model than expected."""
        primary_models = [
            k for k in CLAUDE_MODEL_MISMATCH_JSON["modelUsage"]
            if k.startswith("claude-") and "haiku" not in k
        ]
        # Should have sonnet, not the expected opus-5
        assert "claude-sonnet-5" in primary_models
        assert "claude-opus-5" not in primary_models

    def test_claude_no_session_is_none(self):
        """Claude ephemeral (no-session-persistence) has session_id=None."""
        assert CLAUDE_NO_SESSION_JSON["session_id"] is None

    def test_claude_success_is_error_false(self):
        """Claude success fixture has is_error=False."""
        assert CLAUDE_SUCCESS_JSON["is_error"] is False

    def test_claude_alt_model_has_opus(self):
        """Alt model fixture has claude-opus-5."""
        assert "claude-opus-5" in CLAUDE_SUCCESS_ALT_MODEL["modelUsage"]