# Cross-Agent Review Orchestration

## Purpose

Get a second opinion from a different agent on completed milestone implementation across four dimensions: simplicity, consistency, correctness, and goal fulfillment.

## Trigger

Called by `milestone-run.md` step 8 after implementation is complete and tests pass.

---

## Review Dimensions

Each dimension is reviewed independently. The reviewing agent must answer PASS or OBJECTION.

### 1. KISS (Simplicity)

> "Review the implementation for this milestone. Focus ONLY on simplicity: Is anything over-engineered? Are there simpler approaches that achieve the same result? Are there unnecessary abstractions, indirections, or future-proofing? Answer: PASS (no issues) or OBJECTION (with specific concerns and simpler alternatives)."

### 2. Codebase Style (Consistency)

> "Review the implementation for this milestone. Focus ONLY on codebase consistency: Does the new code follow existing patterns and conventions? Are naming conventions, file organization, and code structure consistent? Does it feel like it belongs in this codebase? Answer: PASS (no issues) or OBJECTION (with specific inconsistencies)."

### 3. Correctness

> "Review the implementation for this milestone. Focus ONLY on correctness: Are there bugs, logic errors, or unhandled edge cases? Are there race conditions, resource leaks, or security issues? Do the tests actually test the right things? Answer: PASS (no issues) or OBJECTION (with specific bugs or concerns)."

### 4. Goal Fulfillment

> "Review the implementation for this milestone. Focus ONLY on goal fulfillment: Does the implementation achieve what the milestone's acceptance criteria defined? Is anything missing from the acceptance criteria? Is anything implemented that wasn't in scope? Answer: PASS (no issues) or OBJECTION (with specific gaps or scope creep)."

---

## Execution

### Codex CLI (Preferred)

```bash
bash .scaffold/tools/codex-review.sh \
  --dimension KISS \
  --milestone docs/milestones/PLAN-M{n}.md \
  --files "src/foo.py src/bar.py"
```

Run once per dimension, replacing `--dimension` with `KISS`, `style`, `correctness`, and `goals`.

### Manual Paste Fallback

If Codex CLI is unavailable, `codex-review.sh` outputs a structured prompt. Copy the full output and paste it into a fresh Claude or Codex session (no prior context). Collect the response.

Structured prompt format:

```
=== REVIEW REQUEST: {DIMENSION} ===
Milestone: {path}
Files changed: {list}

{dimension prompt}

Context:
{milestone file content}

=== FILES ===
{file contents}
===
```

---

## Handling Objections

1. Read the objection carefully — assess whether it is valid.
2. If valid: fix the issue, re-run the affected dimension.
3. If not valid: document the disagreement and reasoning, mark PASS with note.
4. Loop until all four dimensions return PASS.
5. If any dimension still OBJECTs after 3 iterations: escalate to the user before continuing.

---

## Output

1. Update the milestone file's **Cross-Agent Review** section with results (PASS/OBJECTION per dimension, iteration count).
2. Save the full exchange (prompts + responses) to `docs/reviews/M{n}-review.md`.
