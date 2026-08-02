# Wave 1 CLI Characterization

**Date:** 2026-08-01
**Operator:** mdn87 (matthew.d.newman@gmail.com)

## Codex CLI

- **Version:** codex-cli 0.146.0
- **Install path:** `C:\Users\Matt\AppData\Roaming\npm\codex.cmd` (npm global)
- **Auth:** `codex login status` → `Logged in using ChatGPT`
- **Auth type:** ChatGPT subscription (not API key)

### Non-interactive invocation

```
codex exec --json --sandbox read-only --skip-git-repo-check --ephemeral
  --ignore-user-config --ignore-rules -m <selector> --
```

Prompt is sent via stdin. The `-` argument reads stdin.

### Response shape (JSONL)

```
{"type":"thread.started","thread_id":"<thread-uuid>"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"<response-json>"}}
{"type":"turn.completed","usage":{"input_tokens":...,"cached_input_tokens":...,"cache_write_input_tokens":...,"output_tokens":...,"reasoning_output_tokens":...}}
```

### Key observations

- `thread_id` is the session/resume identifier (UUID).
- The final response text is in `item.text` where `item.type == "agent_message"`.
- Usage is in `turn.completed.usage`.
- **BLOCKING DISCOVERY:** No `model` field exists in any event. The resolved model
  cannot be proven from the JSONL output alone. The CLI reports no model-identity
  event.
- No explicit status or error event for infrastructure failures — errors
  manifest as nonzero exit codes and stderr text.

### Exit codes

- `0` on success.
- `1` on error (unknown feature flag, config errors, etc.).
- Timeout exits with a nonzero code (signal-dependent on Windows).

### Continuation

```
codex exec resume <thread-id> --json --sandbox read-only --skip-git-repo-check
  --ignore-user-config --ignore-rules --cd <sterile-dir>
```

## Claude Code CLI

- **Version:** 2.1.195 (Claude Code)
- **Install path:** `C:\Users\Matt\AppData\Roaming\npm\claude.cmd` (npm global)
- **Auth:** `claude auth status --json` → `loggedIn: true`, `authMethod: "claude.ai"`, `apiProvider: "firstParty"`, `subscriptionType: "max"`
- **Account:** matthew.d.newman@gmail.com (Max subscription)

### Non-interactive invocation

```
claude -p --output-format json --model <selector>
  --effort medium --safe-mode --tools ""
  --no-chrome --no-session-persistence --disable-slash-commands
```

Prompt is sent via stdin.

### Response shape (JSON)

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "api_error_status": null,
  "duration_ms": ...,
  "duration_api_ms": ...,
  "num_turns": 1,
  "result": "<response-json>",
  "stop_reason": "end_turn",
  "session_id": "<session-uuid>",
  "total_cost_usd": ...,
  "usage": {
    "input_tokens": ...,
    "cache_creation_input_tokens": ...,
    "cache_read_input_tokens": ...,
    "output_tokens": ...,
    "server_tool_use": { ... },
    "service_tier": "...",
    ...
  },
  "modelUsage": {
    "<model-name>": {
      "inputTokens": ...,
      "outputTokens": ...,
      "cacheReadInputTokens": 0,
      "cacheCreationInputTokens": ...,
      "webSearchRequests": 0,
      "costUSD": ...,
      "contextWindow": ...,
      "maxOutputTokens": ...
    }
  },
  "permission_denials": [],
  "terminal_reason": "completed"
}
```

### Key observations

- `session_id` is the session/resume identifier (UUID).
- The final response text is in `result`.
- Usage is at the top level in `usage`.
- **Resolved model identity** is available in `modelUsage` — a dict keyed by
  model name with per-model usage breakdown. The target model key indicates it
  was used. Auxiliary models (e.g., haiku for caching) also appear.
- `is_error: true` indicates an error result.
- `api_error_status` carries API-level error codes.
- `stop_reason` indicates why the turn ended.

### Exit codes

- `0` on success.
- Nonzero on error.

### Continuation

```
claude -p --resume <session-id> --output-format json
  --tools "" --safe-mode --no-chrome
```

## Auth methods summary

| CLI    | Auth check                                             | Subscription indicator   | API key fallback detectable                                  |
| ------ | ------------------------------------------------------ | ------------------------ | ------------------------------------------------------------ |
| codex  | `codex login status` → "Logged in using ChatGPT"       | Yes                      | `Logged in using API key` or similar                         |
| claude | `claude auth status --json` → `subscriptionType` field | Yes (`max`, `pro`, etc.) | `authMethod` != `claude.ai` or `apiProvider` != `firstParty` |

## Model resolution

| CLI    | Resolved model available? | How                                                               |
| ------ | ------------------------- | ----------------------------------------------------------------- |
| codex  | **NO**                    | No `model` field in any JSONL event                               |
| claude | Yes                       | `modelUsage` dict keys — the primary target model is identifiable |

**Blocking discovery for Codex:** The Codex CLI 0.146.0 does not emit the resolved
model in its JSONL output. This means the Wave 1 provider cannot prove model
identity from the CLI response. Options:

1. Rely on `codex login status` to confirm subscription auth and trust the
   `--model <selector>` argument was honored.
2. File a feature request with the Codex CLI team to add model identity events.
3. Use the subscription auth check as the model-identity gate at the CLI level.

Per the design specification, the provider must not weaken the model-resolution
gate. This discovery blocks the resolved-model check for Codex lanes and must
be noted in the implementation.
