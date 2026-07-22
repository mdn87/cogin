# Plan Initialization Orchestration

## Purpose

This document guides an agent through creating a structured project plan from existing project context. It produces a complete set of planning artifacts: `PLAN.md`, individual `PLAN-M{n}.md` files for each milestone, and a `PLAN-OVERVIEW.md` summary.

## Trigger

This orchestration activates when:
- User says "init plan", "create a plan", "plan this project"
- User starts a new project and asks for planning
- An agent is asked to initialize project planning from context

---

## Sequence

### 1. Gather Context (LOW compute)

Read these files to understand the existing project state:

- `README.md` — project overview and working agreement
- `docs/project-brief.md` — project vision and scope (if exists)
- `docs/architecture.md` — current architecture and design decisions
- `.claude/handoff.md` — previous session notes and current state (if exists)
- `.claude/settings.json` — project-level command permissions (if exists)
- VS Code user settings (`C:/Users/{user}/AppData/Roaming/Code/User/settings.json` on Windows) — system-level approval/auto-skip behavior (if accessible)
- `docs/plans/PLAN.md` — existing plan (if exists)
- `.scaffold/tools/manifest.json` — available tools and activation status (if exists)
- `docs/INDEX.md` — current documentation index

Take notes on:
- Project name and purpose
- Current tech stack
- Existing structure and conventions
- Any documented constraints or decisions
- Whether permissions are aligned for intended full-auto skip behavior: whitelisted safe commands run without prompts, non-whitelisted commands remain gated

---

### 2. Assess Existing State

Determine the project status:

**Is this a new project or existing project?**
- New: no existing plan, few or no source files
- Existing: has source code, README, architecture docs

**Does an existing plan exist?**
- If yes: review `docs/plans/PLAN.md` and ask user if they want to update it or create a new one
- If no: proceed to create a new plan

**What is the detected stack?**
- Based on repo contents (package.json, Cargo.toml, .csproj, etc.) and architecture docs
- Note any dependencies, frameworks, or major libraries

**What context is documented vs. missing?**
- Documented: architecture, project brief, decisions
- Missing: goals, constraints, success criteria, milestone breakdown, tool assignments

Report findings to the user: "I found a {new|existing} {stack} project. Existing plan: {yes|no}. Missing: {list}. Ready to proceed? (yes/no)"

---

### 3. Prompt for Missing Information

Ask the user **one question at a time** for any missing information. If the user skips a question or says "I don't know," record it in the "Open Questions" table of the plan.

**Question sequence:**

1. **Concept**: "What is the core concept? What is being built and why? (2-3 sentences)"

2. **Goals**: "What are the concrete outcomes or deliverables? (list them)"

3. **Constraints**: "What limits the implementation? (e.g., time, resources, technical limitations)"

4. **Success Criteria**: "How will we know the project is successful? (list measurable criteria)"

5. **Milestone Preferences**: "How many milestones do you envision? What are the major phases? (e.g., 'Foundation → Core Features → Polish' or 'Design → Build → Deploy')"

6. **Tool Needs**: "What tools or platforms are critical to this project? (e.g., databases, APIs, CI/CD, monitoring)"

7. **Team & Roles**: "Who is involved? What are the key roles or constraints around implementation?"

8. **Success Metrics**: "What metrics will we track to validate success? (e.g., performance, user adoption, code quality)"

For each question the user skips or answers "unclear," record in "Open Questions":
```
| {Question} | {Relevant Milestone} | No |
```

---

### 4. Build the Plan

Using `PLAN-TEMPLATE.md` as a base, create `docs/plans/PLAN.md`:

- Fill **Metadata** with project name, creation date, status (Draft)
- Fill **Concept** from user input (or "To be determined" if not provided)
- Fill **Goals** from user input
- Fill **Constraints** from user input and detected context (e.g., existing tech, codebase state)
- Fill **Architecture Overview** by referencing `docs/architecture.md` and noting key components
- Create **Milestone Breakdown** by:
  - Breaking user goals into 3–5 milestones based on logical dependencies
  - Assigning titles and scope to each (e.g., M1: Foundation, M2: Core Features, M3: Integration)
  - Setting Status to "Not Started" and filling Dependencies based on sequence
- Create **Tool-Milestone Matrix** by mapping tools/platforms to milestones
- Fill **Open Questions** with any gaps from step 3

**Example milestone sequence:**
- M1: Setup & Foundation (project structure, core abstractions, CI/CD)
- M2: Core Features (primary deliverables based on goals)
- M3: Integration & Polish (cross-feature work, documentation, deployment)
- M4: Validation & Hardening (testing, performance, security review)

---

### 5. Build Milestone Files

For each milestone in the Milestone Breakdown, create `docs/plans/PLAN-M{n}.md` using `MILESTONE-TEMPLATE.md`:

- Fill **Metadata** with plan name, milestone number, status (Not Started), dependencies
- Fill **Scope** by expanding the goal into in-scope and out-of-scope items
- Define **Acceptance Criteria** (measurable ways to know the milestone is done)
- Create **Implementation Sequence** by breaking scope into 3–7 logical steps, each with:
  - Step title
  - Files involved (paths to be created/modified)
  - Action (what to do with those files)
- Leave **Deferred Questions** empty (to be filled during implementation)
- Use the standard **Orchestration Instructions** from the template
- Create placeholder **Documentation Actions** checklist
- Create placeholder **Validation** tables (to be filled during implementation)

---

### 6. Build the Overview

Create `docs/plans/PLAN-OVERVIEW.md` with:

**Header:**
```markdown
# Plan Overview
Generated: {date}
Plan: {project_name}
```

**Milestones Table:**
```
| # | Title | Scope | Dependencies | Status |
|---|-------|-------|--------------|--------|
| M1 | {title} | {1-line scope} | {list} | Not Started |
| M2 | {title} | {1-line scope} | {list} | Not Started |
```

**Tool-Milestone Matrix** — copy directly from PLAN.md

**Quick Links:**
```markdown
- [Full Plan](./PLAN.md)
- [M1 Details](./PLAN-M1.md)
- [M2 Details](./PLAN-M2.md)
...
```

---

### 7. Update Architecture

Review the plan against `docs/architecture.md`:

- Does the architecture support the planned milestones?
- Are there any missing components, abstractions, or decisions?
- If the plan reveals new requirements, update `docs/architecture.md` to document them

Add a note: "Architecture reviewed and aligned with {project_name} master plan on {date}."

---

### 8. Update Index

Add the new plan files to `docs/INDEX.md`:

```markdown
### Planning
- [Master Plan](./plans/PLAN.md)
- [Plan Overview](./plans/PLAN-OVERVIEW.md)
- [M1: {Title}](./plans/PLAN-M1.md)
- [M2: {Title}](./plans/PLAN-M2.md)
...
```

---

## Output

Once complete, present the user with:

1. **Plan Summary**
   ```
   Plan created: {project_name} — Master Plan
   Milestones: {M1 title}, {M2 title}, {M3 title}
   Deferred Questions: {count}
   ```

2. **Open Questions** (if any)
   ```
   | Question | Milestone | Status |
   |----------|-----------|--------|
   | {Q1} | {M} | Deferred |
   ```

3. **Next Step**
   ```
   Ready to implement M1?
   Command: Read docs/plans/PLAN-M1.md and run milestone-run.md
   ```

---

## Notes

- Keep questions open-ended and non-leading
- If the user is uncertain, it's OK to defer to "Open Questions" — don't force decisions
- Milestones should be achievable in 1–3 weeks of focused work
- Dependencies ensure logical sequence; avoid cycles
- Tool-Milestone Matrix helps track which capabilities/platforms are used when
