# PLAN-M{n}: {Milestone Title}

## Table of Contents
- [Scope](#scope)
- [Acceptance Criteria](#acceptance-criteria)
- [Deferred Questions](#deferred-questions)
- [Implementation Sequence](#implementation-sequence)
- [Orchestration Instructions](#orchestration-instructions)
- [Documentation Actions](#documentation-actions)
- [Validation](#validation)

---

## Metadata

| Field | Value |
|-------|-------|
| **Plan** | {plan_name} |
| **Milestone** | M{n} |
| **Status** | Not Started \| In Progress \| Review \| Complete |
| **Dependencies** | {M1, M2, ...} |

---

## Scope

### In Scope
{What is included in this milestone? List features, components, or capabilities being built.}

### Out of Scope
{What is explicitly not included? What will be deferred to later milestones?}

---

## Acceptance Criteria

- {Measurable criterion that must be satisfied}
- {Measurable criterion that must be satisfied}
- {Measurable criterion that must be satisfied}

---

## Deferred Questions

| Question | Answer | Answered By |
|----------|--------|-------------|
| {A question that arose during planning but doesn't block implementation} |  | — |
| {A question that should be answered before the next milestone} |  | — |

---

## Implementation Sequence

1. **{Step 1 Title}**
   - Files: `path/to/file.md`, `path/to/file.rs`
   - Action: {Describe what to do}

2. **{Step 2 Title}**
   - Files: `path/to/file.md`, `path/to/file.rs`
   - Action: {Describe what to do}

3. **{Step 3 Title}**
   - Files: `path/to/file.md`, `path/to/file.rs`
   - Action: {Describe what to do}

---

## Orchestration Instructions

> These instructions tell the implementing agent how to behave when working through this milestone.

1. **Read and Confirm Scope**: Read this entire milestone file. Summarize the Scope and Acceptance Criteria. If anything is ambiguous, ask the user for clarification before proceeding.

2. **Confirm with User**: Present the scope summary and ask "Ready to implement M{n}? Any adjustments?" Wait for confirmation.

3. **Check Deferred Questions**: Review the "Deferred Questions" table. For any row where "Answer" is empty, ask the user for the answer before proceeding. Record answers in this table.

4. **Review Tools Manifest**: Read `.scaffold/tools/manifest.json` and `.scaffold/references/registry.json` to understand available tools and their constraints. Note which tools are activated for this project.

5. **Execute Implementation Steps**: Work through the "Implementation Sequence" in order. For each step, read the relevant files, understand the existing code, make targeted edits, and validate locally before moving to the next step.

6. **Run Validation**: Execute all checks in the "Validation" section. For any failing check, fix the issue and re-run until all checks pass. Record results in the validation tables.

7. **Trigger Cross-Agent Review**: If this is a handoff to another agent or a blocking point, follow `.scaffold/orchestration/milestone-review.md`. Address any objections and record results in the Validation section.

8. **Update This File**: Change Status from "In Progress" to "Review" once implementation is complete. Note any blockers, deviations, or lessons learned in comments at the top of the file if needed.

9. **Update PLAN-OVERVIEW**: After validation passes, update `docs/plans/PLAN-OVERVIEW.md` to reflect M{n} completion. Update the Milestones table Status column and any dependency changes.

10. **Complete Documentation Actions**: Work through the "Documentation Actions" checklist below. Create ADRs for significant decisions, update INDEX.md, and ensure all supporting docs are current.

---

## Documentation Actions

- [ ] Update `docs/INDEX.md` to list this milestone file
- [ ] Update `docs/plans/PLAN-OVERVIEW.md` with M{n} completion status
- [ ] Create ADRs for significant decisions made during implementation (if any)
- [ ] Update `docs/architecture.md` if the design changed
- [ ] Add any lessons learned to this file under "Deferred Questions" or a new "Notes" section

---

## Validation

### Automated

| Check | Command | Result | Pass |
|-------|---------|--------|------|
| {Check description} | `{command to run}` | — | ❌ |
| {Check description} | `{command to run}` | — | ❌ |
| {Check description} | `{command to run}` | — | ❌ |

### Human-Verifiable

- [ ] {Can be verified by inspection or manual testing}
- [ ] {Can be verified by inspection or manual testing}
- [ ] {Can be verified by inspection or manual testing}

### Cross-Agent Review

| Aspect | Result |
|--------|--------|
| **KISS** (Keep It Simple, Stupid) | ⊘ |
| **Codebase Style** (matches existing patterns) | ⊘ |
| **Correctness** (implements spec correctly) | ⊘ |
| **Goal Fulfillment** (meets acceptance criteria) | ⊘ |

