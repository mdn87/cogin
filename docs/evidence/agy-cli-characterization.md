# Antigravity CLI (`agy`) Characterization

Recorded 2026-10-22 on `4070pc` against `agy` 1.4.4
(`%LOCALAPPDATA%\agy\bin\agy.exe`, a native executable rather than an npm
shim). Gemini CLI 0.65.0 is also installed; nothing here uses it.

This document records observed behavior only. Session identifiers, account
identifiers, quota percentages, and raw logs are omitted. The probes used
`gemini-3.8-flash-low` with trivial prompts in empty scratch directories.

## Authentication

- `agy` authenticated with a consumer Google account through the operating
  system keyring. The log reported `ChainedAuth: authenticated via keyring`
  and `authMethod=consumer`, and model traffic went to the Code Assist
  endpoint (`daily-cloudcode-pa.googleapis.com`).
- `GEMINI_API_KEY` is set in this machine's environment. The isolated probes
  removed it from the child environment, and authentication still succeeded
  through the keyring. Any provider must remove it as well, so that a run can
  never fall back to API-key billing.
- Authentication does not depend on the user profile directory. With
  `USERPROFILE` and `HOME` pointed at an empty directory, the keyring login
  still succeeded.

## Quota-free probes

Two slash commands answer in print mode without starting a model turn. Both
reported zero tokens and an empty `conversation_id`.

- `agy --print=/quota --output-format json` reports subscription quota
  buckets: "Gemini Models", "Claude and GPT models", and "Gemini 4 Argon",
  each with weekly and five-hour windows, a remaining fraction, and a reset
  time. A response that contains these buckets is evidence of subscription
  entitlement.
- `agy --print=/model --model <id> --output-format json` returns
  `command.data` with `id`, `label`, and `effort` for the selected model.

In Git Bash, MSYS path conversion rewrites a leading `/` in an argument into a
Windows path. Set `MSYS_NO_PATHCONV=1` there. Python's `subprocess` with an
argument list is not affected. Two probes in this session reached the model by
mistake because of this conversion.

## Models

`agy models` printed tab-separated rows. Effort is part of the model ID:

- `gemini-4-argon-low`, `gemini-4-argon-medium`, `gemini-4-argon-high`
- `gemini-3.8-flash-low`, `gemini-3.8-flash-medium`, `gemini-3.8-flash-high`
- `claude-opus-5-5-low`, `claude-opus-5-5-medium`, `claude-opus-5-5-high`
- `claude-sonnet-5-5-low`, `claude-sonnet-5-5-medium`,
  `claude-sonnet-5-5-high`
- `gpt-oss-120b-medium`

`agy models --output-format json` failed in 1.4.4 with
`flags provided but not defined: -output-format`, although the changelog
describes that flag.

## Output shapes

`--output-format json` returns one document:

```json
{"conversation_id":"<conversation-uuid>","status":"SUCCESS","response":"{\"ok\":true}\n","duration_seconds":6.5,"num_turns":1,"usage":{"input_tokens":12708,"output_tokens":5,"thinking_tokens":0,"cache_read_tokens":0,"total_tokens":12713}}
```

`--output-format stream-json` returns NDJSON events: one `init`, several
`step_update`, and one terminal `result` with the same fields as the JSON
document:

```json
{"event":"init","conversation_id":"<conversation-uuid>","init":{"model":"gemini-3.8-flash-low","cwd":"<cwd>","tools":["<60 tool names>"],"permission_mode":"always-proceed"}}
{"event":"step_update","step_update":{"conversation_id":"<conversation-uuid>","step_index":1,"state":"DONE","step_type":"agent_response","text_delta":"\n","duration_seconds":3.2,"usage":{"input_tokens":12702,"output_tokens":28,"thinking_tokens":23,"cache_read_tokens":0,"total_tokens":12730}}}
{"event":"result","result":{"conversation_id":"<conversation-uuid>","status":"SUCCESS","response":"{\"ok\":true}\n","duration_seconds":4.9,"num_turns":1,"usage":{"input_tokens":12702,"output_tokens":28,"thinking_tokens":23,"cache_read_tokens":0,"total_tokens":12730}}}
```

Input validation failures return `"status":"ERROR"` with an `error` string and
exit 1. A dangling `--print` exits 2.

## Model identity

No output event carries a server-reported model. `init.model` repeats the
requested selector. The log file records the selector being forwarded as a
model override (for example, `label="Gemini 3.8 Flash (Low)"`), which is still
client-side evidence.

This is the same class of gap recorded for Codex in
`wave-1-cli-characterization.md`. The strongest available identity evidence
is the following combination: the selector is listed by `agy models`, it is
accepted by `/model`, and `init.model` echoes it.

## Prompt transport over stdin

The prompt can go through stdin instead of the command line:

```text
agy --print= --input-format stream-json --output-format stream-json ...
```

Each stdin line is one turn:

```json
{"event":"user","message":{"content":"<prompt text>"}}
```

- `--print` must carry an attached empty value (`--print=`). A bare
  `--print` takes the next flag as its prompt and fails with exit 2.
- Other event names (`user_message`, `user_input`, `prompt`, `message`) are
  ignored with a warning. A `user` event without `message.content` fails.
- Newlines, quotes, embedded JSON, and non-ASCII text round-tripped exactly.

## Continuation

- `--conversation <id>` resumed the earlier conversation. The result kept the
  same `conversation_id`, `num_turns` increased to 2, and the model repeated
  its earlier answer exactly.
- An unknown ID is fail-open. `agy` printed
  `warning: conversation "<id>" not found` to stderr, exited 0, and answered
  in a new conversation with a different ID. A caller must compare the
  returned `conversation_id` with the requested one.
- Conversations persist under `<home>/.gemini/antigravity-cli/conversations`.
  `agy` has no flag that disables persistence. An isolated home per run gives
  each session its own store.

## Isolation

With the real profile, the child loaded one user `hooks.json` (a Lugos
agent-mail hook), the `lugos-toolset` plugin, and `~/.gemini/GEMINI.md`. The
trivial prompt cost 12,708 input tokens in that configuration.

With `USERPROFILE` and `HOME` set to an empty directory, the log reported
`loaded 0 named hooks`, and the user `config.json` was not found. The same
prompt cost 8,106 input tokens, and authentication still succeeded through
the keyring.

## Tools and permissions

- Print mode advertises 60 tools in `init.tools`, including `run_command`,
  `write_to_file`, `search_web`, browser control, and subagents. The list did
  not change when permissions were restricted.
- Without a settings file, `permission_mode` is `always-proceed`, so every
  tool call is auto-approved.
- `<home>/.gemini/antigravity-cli/settings.json` containing
  `{"permissions":{"allow":[],"deny":[...]}}` loaded as the CLI permission
  set and changed `permission_mode` to `request-review`.
- These deny rules were accepted: `read_file(*)`, `write_file(*)`,
  `read_url(*)`, `execute_url(*)`, `command(*)`, and `mcp(*)`.
- `unsandboxed(*)` is rejected in 1.4.4 with
  `Invalid "unsandboxed" permission rules found; they are ignored and grant nothing`.
  The retired Autowork executor's deny list included that rule.
- Denial happens when a tool is called. The model still sees every tool. This
  differs from Claude Code's `--tools ""`, which removes the tools from the
  session, and it must be recorded as an asymmetry in any cross-family
  comparison.

## Other behavior

- `--mode plan` with `--disable-slash-commands` prints
  `warning: --mode plan has no effect while slash command expansion is disabled.`
  The retired Autowork executor passed both flags, so its plan mode had no
  effect.
- The 1.4.x changelog states that when `--print-timeout` expires mid-turn, the
  CLI returns the partial output, exits successfully, and writes a warning to
  stderr. A caller must therefore treat a timeout warning as an
  infrastructure timeout even when the exit code is 0. That path was not
  exercised here.
- The changelog states that model or agent errors after a partial stream exit
  with code 3.
- The install directory contains an `agy.exe.<n>.old` from a self-update.
  Setting `AGY_CLI_DISABLE_AUTO_UPDATE=1` keeps the version fixed during a run.
- An unguarded `agy --version` updated the binary in place from 1.4.4 to 1.4.5
  at 01:04:30 on 2026-10-22. That was during `wave prepare`, before
  `_cli_version` set `AGY_CLI_DISABLE_AUTO_UPDATE=1`. The 1.4.4 manifest was
  superseded rather than run, and a fresh manifest now pins 1.4.5. The 1.4.5
  changelog changes only UI, performance, and plugin loading, plus one fix for
  silent retries after content-safety blocks. On 1.4.5, the Autowork live slice
  re-verified stdin transport, the parsed permission profile (through
  `--print=/permissions`), the `request-review` mode, and a command denial. The
  quota-free `/quota` and `/model` probes were also re-run. Conversation resume
  was last verified on 1.4.4.
