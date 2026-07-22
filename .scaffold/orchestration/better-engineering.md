# Better Engineering Review

## Purpose

Assess opportunities for architectural improvement after milestone completion. This is an opt-in process — not every milestone needs it, and not every finding needs to be addressed.

## Trigger

User opts in after the milestone completion prompt. The implementing agent asks: "Run better-engineering review? (yes/no)"

---

## Process

### Step 1 — Independent Assessments

Claude and Codex each independently assess the completed implementation across five areas. Neither sees the other's assessment at this stage.

Assessment areas (rate each by severity and effort):

| Area | What to evaluate |
|------|-----------------|
| Architecture | Structure, boundaries, coupling, cohesion |
| Code Quality | Clarity, duplication, complexity |
| Testing | Coverage gaps, test design, brittleness |
| Performance | Hotspots, inefficiencies, unnecessary work |
| Maintainability | Changeability, documentation, onboarding friction |

For each finding: describe the issue, rate severity (low/medium/high), rate effort to address (small/medium/large).

### Step 2 — Cross-Review

A fresh instance of each agent reviews the other's assessment. Response options per finding:

- **AGREE** — finding is valid and well-described
- **DISAGREE** — finding is not valid (explain why)
- **ENHANCE** — finding is valid but incomplete or understated (add detail)

### Step 3 — Present to User

Compile results into `docs/reviews/M{n}-better-eng.md`:

- Findings table: area, finding summary, severity, effort, Claude verdict, Codex verdict
- Detail sections: full description + cross-review notes for each finding
- Disagreements called out explicitly

### Step 4 — User Decides

Present the compiled findings to the user. The human is the taste arbiter — they decide which findings to address, defer, or discard. Not every finding needs action.

### Step 5 — Create Sub-Milestones

For each finding the user elects to address, create a `PLAN-M{n}-BE{k}.md` file following the standard milestone template.

Example: findings 1 and 3 from M4 become `PLAN-M4-BE1.md` and `PLAN-M4-BE3.md`.

---

## Important Notes

- The human decides what matters — architectural taste is not purely objective.
- Sub-milestones created from better-engineering reviews do not trigger another better-engineering review when completed.
- Keep findings concrete and actionable. Vague concerns ("could be cleaner") are not useful.
- If Claude and Codex disagree on a finding, present both perspectives without resolving it — let the user decide.
