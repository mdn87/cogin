# Milestone Implementation Orchestration

## Purpose

This document guides an agent through implementing a single milestone from start to finish. It provides a structured 12-step process to take a milestone from "Not Started" to "Complete" with full validation and documentation.

## Trigger

This orchestration activates when:
- User says "Implement M{n}" or "Run PLAN-M{n}.md"
- Agent is prompted with: "Please read PLAN-M{n}.md. Implement this plan per the instructions in that file."
- A previous milestone completes and it's time to start the next one

---

## Three Phases

### PHASE 1: PRE-IMPLEMENTATION

#### Step 1: Read and Confirm

- Read the entire milestone file (PLAN-M{n}.md) carefully
- Summarize the **Scope** (in-scope and out-of-scope items) and **Acceptance Criteria**
- If anything is ambiguous or contradicts the architecture, ask the user for clarification before proceeding
- Confirm with the user: "Ready to implement M{n}? Any adjustments?"
- Wait for user confirmation

#### Step 2: Resolve Deferred Questions

- Review the **Deferred Questions** table in the milestone file
- For any row where the "Answer" column is empty, ask the user for the answer
- Record the answer in the table before proceeding
- If a question cannot be answered, mark it "Cannot answer — proceeding with assumption: {assumption}"

#### Step 3: Tool Check

- Read `.scaffold/tools/manifest.json` and `.scaffold/references/registry.json` to understand available tools, their constraints, and activation status
- Review the Tool-Milestone Matrix in the plan to see which tools are expected for this milestone
- Cross-reference against the Implementation Sequence to confirm tool availability
- Verify permission alignment for intended full-auto skip behavior:
  - Project level: `.claude/settings.json`
  - System level (VS Code): `C:/Users/{user}/AppData/Roaming/Code/User/settings.json` on Windows
  - Intended result: safe whitelisted commands auto-skip confirmation; non-whitelisted commands still require approval
- If a tool is not available but is needed, ask the user: "M{n} requires {tool}. Is it available?"
- If system-level settings are inaccessible, notify the user and continue with project-level permissions while documenting the gap
- Log the active tools for this milestone (to be recorded in step 11)

#### Step 4: Context Loading

- Read `docs/architecture.md` to understand the current design and any assumptions
- Read `docs/decisions/` (if exists) to review architectural decision records relevant to this milestone
- Read the previous milestone file(s) (PLAN-M{n-1}.md) to understand what was built and any lessons learned
- Note any architecture changes, new abstractions, or breaking changes introduced in prior milestones
- Confirm understanding: "Architecture reviewed. Ready to proceed? (yes/no)"

---

### PHASE 2: IMPLEMENTATION

#### Step 5: Execute Implementation Steps

- Work through the **Implementation Sequence** in order (step 1, then step 2, then step 3, etc.)
- For each step:
  1. Read all files listed under "Files:" in that step
  2. Understand the existing code, patterns, and conventions
  3. Make targeted edits per the "Action:" description using the Edit tool (prefer Edit over Write for existing files)
  4. Validate the change locally (compile, run tests, linting, etc.) before moving to the next step
  5. If a step reveals ambiguity or a blocker, pause and ask the user before proceeding

#### Step 6: Run Validation

- Execute all **Automated** checks listed in the Validation section
  - Run each command listed
  - Record the output/result in the validation table
  - If any check fails, fix the issue and re-run until it passes
- Verify all **Human-Verifiable** checklist items
  - Go through each item and manually confirm it has been satisfied
  - Mark as complete
- Once all automated and human-verifiable checks pass, proceed to Phase 3

---

### PHASE 3: POST-IMPLEMENTATION

#### Step 7: Tool Audit (Passive)

- Compare the tools listed in the Tool-Milestone Matrix against what was actually used during implementation
- Log observations:
  - Tools used as expected: ✓
  - Tools used unexpectedly: {tool_name} — {why it was needed}
  - Tools not needed: {tool_name} — {why it wasn't needed}
  - Tools unavailable: {tool_name} — {impact}
- Add notes to the milestone file comments if significant deviations occurred

#### Step 8: Cross-Agent Review

- If this milestone is a handoff to another agent or a critical juncture, trigger a review
- Follow the process in `.scaffold/orchestration/milestone-review.md` (if it exists)
- Address any objections or change requests from reviewers
- Record review results in the **Cross-Agent Review** section of the Validation table
  - KISS: Evaluate simplicity of solution
  - Codebase Style: Confirm adherence to existing patterns
  - Correctness: Verify the implementation matches the spec
  - Goal Fulfillment: Confirm acceptance criteria are met
- Mark each category as ✓ (pass), ⚠ (caution), or ✗ (fail)
- If any fail, address and re-review before proceeding

#### Step 9: Documentation

- Work through the **Documentation Actions** checklist:
  - [ ] Update `docs/INDEX.md` to list this milestone
  - [ ] Update `docs/plans/PLAN-OVERVIEW.md` with M{n} completion and status change
  - [ ] Create ADRs for significant decisions (if any)
  - [ ] Update `docs/architecture.md` if the design changed
  - [ ] Add lessons learned to this file or a comments section
- Ensure all documentation is current and linked from INDEX.md

#### Step 10: Better Engineering Prompt

- Ask the user: "Milestone M{n} complete. Run better-engineering review? (yes/no)"
- If user says yes:
  - Follow the process in `.scaffold/orchestration/better-engineering.md` (if it exists)
  - Review the implementation for code quality, performance, security, maintainability
  - Address any findings and re-validate if changes are made
- If user says no: proceed to step 11

#### Step 11: Usage Log

- Append an entry to `.scaffold/project/usage-log.json` (create if doesn't exist):
  ```json
  {
    "milestone": "M{n}",
    "date": "{YYYY-MM-DD}",
    "status": "complete",
    "used_tools": ["{tool1}", "{tool2}", ...],
    "available_tools": ["{all tools from Tool-Milestone Matrix}"],
    "notes": "{any relevant observations from tool audit}"
  }
  ```
- This log helps track tool usage and effectiveness over time

#### Step 12: Handoff (if ending session)

- If the session is ending and the next milestone needs to be started:
  - Refresh project documentation for tasks completed or newly identified in this session
  - Add a clear documentation update notice in the handoff state (or explicitly note that no doc updates were needed)
  - Follow the `.claude/handoff.md` skill process
  - Update `.claude/handoff.md` with:
    - Session summary: "Completed M{n}: {milestone title}"
    - Documentation refresh notice: docs updated or explicit no-change confirmation
    - Current state: architecture changes, new abstractions, lessons learned
    - Next up: "Start M{n+1}: {title}" with any specific context needed
  - Ensure `.claude/handoff.md` and `.claude/handoff-history/` are in `.gitignore`

---

## State Transitions

Update the milestone file Status field as you progress:

| Step | Status |
|------|--------|
| After Step 1–4 | In Progress |
| After Step 5–6 | In Progress (validating) |
| After Step 8 | Review (awaiting final sign-off) |
| After Step 9–12 | Complete |

---

## Quick Reference

### Key Files

- **Current milestone**: `docs/plans/PLAN-M{n}.md`
- **Full plan**: `docs/plans/PLAN.md`
- **Architecture**: `docs/architecture.md`
- **Tools manifest**: `.scaffold/tools/manifest.json`
- **Previous milestones**: `docs/plans/PLAN-M{n-1}.md`

### Commands

- **Read files**: Use Read tool (not cat/head)
- **Search files**: Use Grep tool (not grep)
- **Find files**: Use Glob tool (not find)
- **Edit files**: Use Edit tool (prefer over Write)
- **Validate**: Run commands listed in Validation section

### When Stuck

1. Pause and review the milestone scope — is the current task in-scope?
2. Check deferred questions — has the answer been provided?
3. Verify architecture.md alignment — are assumptions still valid?
4. Ask the user — don't guess or assume
5. Record blockers in a comment at the top of the milestone file for handoff

---

## Notes

- Validation is critical — don't skip automated or human-verifiable checks
- Cross-agent review catches issues early — don't bypass it
- Tool audit informs better planning in future milestones
- Documentation is part of the milestone — don't defer it
- Handoff notes save time for the next session or agent
