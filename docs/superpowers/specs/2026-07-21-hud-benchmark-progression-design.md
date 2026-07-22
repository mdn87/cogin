# Cogin HUD Benchmark Progression Design

Status: approved and final

Date: 2026-07-21

Primary audience: Matt, selecting and routing model/effort configurations for agentic coding

## Decision

The HUD will use an evidence-first progression trace as its main view. Compact scorecards summarize the selected model/effort condition, but they do not replace the underlying task sequence or collapse it into a single winner score.

The first implementation target is Taxonomy Bench's generated, standalone `report.html`. The data derivation should remain independent of HTML so the same view model can later be embedded in a LUGOS HUD. Live event streaming and a new HUD application are outside this implementation slice.

## Terminology and source truth

- **Taxonomy graph**: Marble's prerequisite directed acyclic graph (DAG). It contains branches and many valid topological traversals.
- **Benchmark progression**: the deterministic linear order produced by the current suite generator: tiers 1 through 8, with independently sampled tasks within each tier.
- **Curriculum path**: a future suite built from one declared topological walk or connected prerequisite chain. It is not the current benchmark.
- **Task family**: the run record's `kind` value. The eight current kinds are `semantic_match`, `direct_prerequisites`, `reverse_unlocks`, `transitive_prerequisites`, `topological_order`, `shortest_path`, `mastery_plan`, and `integrity_audit`.
- **First-pass progression**: the run-ordered sequence whose attempt records have `phase="first"`. This is the primary trace.
- **Recovery phase**: attempt records with `phase="retry"`. These cognitive retries run only after every first attempt is complete.
- **Blind retry**: `retry_policy="blind"`.
- **Feedback retry**: `retry_policy="feedback"`; the UI may describe this as diagnostic feedback, but must retain the stored policy value in details.

The UI must say **Benchmark Progression**, not **Marble Curriculum Path**. Current tasks do not form one cumulative reasoning chain, and one task's answer does not become the next task's input.

## Goals

1. Show where a model/effort condition remains reliable, begins to destabilize, and breaks down more consistently.
2. Preserve exact outcomes, partial credit, speed, resource use, and scorer diagnostics at task level.
3. Make isolated failures, isolated successes beyond the frontier, recovery after retry, and infrastructure errors visible.
4. Support repeatable comparison without presenting a single session as a stable model estimate.
5. Produce an operator-oriented routing interpretation for agentic coding while identifying which conclusions are benchmark evidence and which are heuristic proxies.

## Non-goals

- A psychometric intelligence score or school-grade-equivalent label.
- A claim that benchmark tiers are universal difficulty levels.
- A claim that Marble graph performance directly proves coding-task success.
- A new connected curriculum-walk suite.
- Live execution transport, server push, or a new HUD host application.
- Cross-provider token comparisons when providers define token classes differently.

## Approaches considered

### Summary scorecards only

Fast to scan, but they hide where degradation begins and make evidence hard to audit.

### Binary pass/fail timeline

Shows ordering, but discards partial correctness, failure cause, uncertainty, and recovery behavior. Large pass/fail boxes become decorative rather than informative.

### Evidence-first progression trace — selected

Shows the ordered first-pass record, continuous diagnostics, and derived frontier markers. Scorecards remain a compact index into that evidence.

## Information hierarchy

The desktop report uses the following order:

1. **Condition identity**: requested and resolved model, effort, suite hash and seed, session mode, output mode, retry policy, repeat count, benchmark version, and taxonomy version.
2. **Routing interpretation**: one concise recommendation plus an explicit confidence/evidence note.
3. **Frontier strip**: reliable frontier, instability onset, sustained breakdown, peak isolated success, first-attempt latency, retry recovery, and unsupported-output proxy.
4. **Progression workspace**: the scrolling task trace as the largest visual region, with a diagnostic sidebar on wide screens.
5. **Aggregate scorecards**: speed, consistency, recovery, failure signatures, and task-family behavior.
6. **Run metadata**: reproducibility details and raw configuration in collapsed sections.

On narrow screens, the same sections stack in that order. The trace remains above aggregate scorecards.

## Progression trace

### Ordering

The primary trace contains one row per first attempt in suite order. Tier headers are sticky and show the tier's exact count, mean partial score, median latency, and task count.

The trace must not imply that difficulty rises smoothly within a tier. Each row names its task family because later tiers change task composition as well as graph complexity.

### Row content

Every task row shows:

- sequence index and stable task ID
- tier and task family
- exact outcome as text
- partial score from `0.00` to `1.00`
- first-attempt latency
- reported token use, or `not reported`
- one concise failure explanation derived from scorer feedback/details
- retry outcome, if any, explicitly labeled `recovery phase`

Outcome wording is factual rather than decorative:

- `1.00 exact`
- `0.72 non-exact · 2 prerequisites missing`
- `0.88 non-exact · 1 precedence violation`
- `unparseable · required JSON object not found`
- `unscored · infrastructure error`

Color is a redundant cue only. Text and shape must still communicate the result in monochrome.

### Expanded details

Selecting a row exposes:

- model response
- scorer feedback
- scorer-specific numeric details
- latency and usage for every attempt
- retry policy/context and recovery sequence
- infrastructure error text when applicable

The standard report does not require the private expected answer. If an operator explicitly generates a private local report with the suite available, a canonical expected-versus-actual diff may be shown for `id`, `ids_set`, and `issues_set` scorers. `topological_order`, `shortest_path`, and `mastery_plan` can have multiple valid answers; their private detail view shows constraint validation—required nodes, allowed edges, endpoint/length requirements, dependency order, and target position—rather than pretending there is one canonical sequence. Public/exported reports must never expose private scorer constraints or answer keys.

### Retry representation

Retries are visually connected to their original task for diagnosis, but they are labeled as a later **Recovery phase**. They must not appear as though they happened inline before the next first attempt.

The first-pass trace remains the basis for the degradation curve. Retry results affect eventual strength and recovery metrics, not the first-pass progression line.

### Navigation and filtering

- A compact right-side minimap has one mark per task and supports jumping to a tier or anomaly.
- Filters include all tasks, non-exact only, task family, and retries.
- Expanding a row must not alter ordering.

## Derived markers

All markers display their counts and definitions in a tooltip/detail label. They are navigation aids, not replacement scores.

### First miss

The earliest scored first attempt that is not exact. An early isolated miss does not by itself end the reliable frontier.

### Reliable frontier

Use the benchmark's existing definition unchanged: the highest consecutive tier, beginning at tier 1, where at least two-thirds of scored tasks pass exactly on first attempt.

### Instability onset

The first scored tier immediately after the reliable frontier. The label includes its exact count, for example `Tier 5 · 2/4 exact`, so the threshold is not hidden. If the reliable frontier is `0` because Tier 1 is below threshold, instability onset is Tier 1 and the HUD says `No reliable tier · Tier 1 · x/y exact`. If every evaluated tier is reliable, report `not observed`; if no tier has a scored task, report `not measurable`.

### Sustained breakdown

The first of two consecutive tiers that each fall below the two-thirds exact threshold, provided the two tiers contain at least eight scored tasks combined. Otherwise report `not established` rather than forcing a conclusion.

### Peak isolated success

The highest tier containing any exact first attempt. It is shown separately from the reliable frontier.

### Rolling degradation curve

Plot trailing first-attempt exact rate and trailing mean partial score. Infer the typical tier size from `run.json` as the median count of task records across populated tiers, rounded up. The default window is `max(8, 2 × inferred tier size)` scored tasks and is displayed beside the chart. Before the window fills, show the actual smaller sample size. Infrastructure errors are gaps, not failures. No private suite fields are required.

## Repeats and uncertainty

A single run is labeled **session evidence**. Model-level wording is allowed only when repeated runs are selected.

For repeats of the same suite and condition:

- align outcomes by stable task ID
- show `x/y exact`, median partial score, and outcome flip rate per task
- show Wilson intervals and sample counts for aggregate exact rates
- preserve each individual run as a selectable trace

For different seeds, do not align task IDs as if they were the same task. Compare at tier and task-family level, or show separate traces.

The HUD follows the benchmark guidance of at least three repeats for model-level conclusions but does not prevent smaller runs. It instead labels their evidence as limited.

## Failure taxonomy and risk proxy

The derivation layer maps `kind`, parse flags, scorer feedback, and scorer-specific details into stable diagnostic codes. The run does not store scorer type directly, so `kind` is the required disambiguator. A task can have more than one code.

| Task `kind` | Scorer | Diagnostic derivation |
|---|---|---|
| `semantic_match` | `id` | `selection.incorrect` when a string ID is present but not exact; `format.wrong_shape` when `actual_type` is not `str` |
| `direct_prerequisites` | `ids_set` | `set.missing`, `set.extra`, and `sequence.duplicate` from the corresponding counts |
| `reverse_unlocks` | `ids_set` | `set.missing`, `set.extra`, and `sequence.duplicate` from the corresponding counts |
| `transitive_prerequisites` | `ids_set` | `set.missing`, `set.extra`, and `sequence.duplicate` from the corresponding counts |
| `topological_order` | `topological_order` | `order.node_coverage` when `node_f1 < 1`; `order.precedence` when `violated_edges > 0`; `sequence.duplicate` from `duplicate_count` |
| `shortest_path` | `shortest_path` | `path.endpoint` when endpoints fail; `path.invalid_edge` when step compliance is below 1; `path.non_shortest` when length fails; `sequence.duplicate` when `unique` is false |
| `mastery_plan` | `mastery_plan` | `plan.coverage` when `set_f1 < 1`; `plan.dependency` when edge compliance is below 1; `plan.target_not_last` when false; `sequence.duplicate` from `duplicate_count` |
| `integrity_audit` | `issues_set` | `integrity.miss` from `missing_count`; `integrity.false_positive` from `extra_count`; `sequence.duplicate` from `duplicate_count` |

Format and infrastructure codes apply before task-specific codes:

- `format.unparseable`: neither strict nor recovered JSON produced a JSON object.
- `format.wrong_shape`: JSON parsed, but the required field/type validation failed.
- `infrastructure`: the attempt has an infrastructure `error` and no cognitive score.

When a format or infrastructure code applies, do not invent task-specific codes from absent scorer details.

The HUD may calculate an **unsupported-output proxy** from extra IDs/issues and invalid graph steps. It must not label that number as a general hallucination rate; Taxonomy Bench can detect unsupported graph outputs, not every kind of factual hallucination relevant to coding.

## Agentic-coding routing interpretation

The benchmark supports routing through capability proxies:

- semantic matching and direct prerequisites: bounded selection and immediate dependency identification
- reverse unlocks: reverse-dependency tracing, downstream impact analysis, and blast-radius estimation
- transitive prerequisites and topological order: multi-hop dependency reasoning and ordering
- shortest path and mastery plan: constrained planning and efficient sequencing
- integrity audit: contradiction and structural-error detection

The HUD may state recommendations such as `use this effort for multi-hop planning; require independent verification beyond Tier 5`. It must label the Marble-to-coding mapping as a **routing heuristic** until coding-specific hidden evaluations validate the relationship.

No recommendation may be derived from one composite score alone. The recommendation must cite the relevant frontier, task-family evidence, latency, consistency, and unsupported-output proxy.

## Visual requirements

- Preserve the established dark LUGOS operator-HUD direction.
- Use typography, alignment, thin rails, and spacing for hierarchy; avoid large pass/fail pills or grids of status boxes.
- Base body text is at least `15px`; supporting text is at least `13px`; primary task values are at least `15px`.
- Do not place required meaning only in color or hover state.
- Keep row density high enough to see roughly 8–12 tasks on a 900px-high desktop viewport.
- The selected task and keyboard focus must be visually distinct.
- The report remains usable at 200% zoom and at a 768px viewport width.

## Components and boundaries

### Progression derivation

A pure derivation layer consumes a run and produces a presentation-neutral view model. It owns ordering, marker calculations, rolling windows, repeat aggregation, and diagnostic codes.

### HTML report renderer

The renderer consumes the view model and produces the standalone report. It owns formatting, layout, expansion behavior, filters, and the minimap. It does not recalculate benchmark metrics.

### Routing interpretation

A separate rule layer consumes explicit evidence fields and emits a recommendation plus the evidence references used. Keeping it separate allows the wording or routing policy to change without changing scoring.

### Deferred / forward compatibility

A future HUD adapter can consume the same view model, but it is not implemented in this slice and must not force a framework or event protocol into the static report. Live-follow behavior is also deferred: if a later component receives live events, following the newest row pauses when the operator scrolls away and resumes only through an explicit `Resume follow` control. Neither event ingestion nor follow-mode controls belong in the current implementation plan.

## Data flow

```text
run.json (task order, attempts, embedded summary)
                  |
                  v
        progression derivation
        - task rows
        - diagnostic codes
        - frontier markers
        - repeat evidence
                  |
                  v
      presentation-neutral view model
             /             \
            v               v
   standalone report    future HUD adapter
```

The existing run format already records task ID, tier, kind, attempts, score details, latency, usage, errors, and the summary. The first implementation derives the view from those fields and does not require a run-format migration or access to the private suite.

## Intentional new derivations

These display semantics intentionally differ from current aggregate-report defaults and must be computed from raw run records:

- Missing token usage becomes `not reported`; do not reuse paths that default absent token counts to zero.
- No retry budget becomes `not measured`; do not render a missing recovery rate as `0%`.
- Per-tier median latency is computed from first-attempt `latency_ms` values because it is not stored in `summary.json`.
- Typical tier size and rolling-window size are inferred from task-record counts, not private suite metadata.

## Missing and incompatible data

- Infrastructure failures are shown and excluded from cognitive accuracy denominators.
- Missing token fields display `not reported`, not zero.
- No retry budget displays `not measured` for recovery rather than `0%`.
- A tier with insufficient scored tasks displays its raw count and limited-evidence warning.
- Isolated and continuous sessions are never pooled.
- Prompt-output and schema-output format reliability are not pooled.
- Provider token efficiency is not ranked when token definitions are incompatible.
- A resolved-model change within a condition is prominently flagged.

## Testing strategy

### Derivation tests

- trace order exactly matches run task order
- exact, non-exact, unparseable, wrong-shape, and infrastructure outcomes map correctly
- reliable frontier remains identical to `summarize_run`
- first miss, instability onset, sustained breakdown, and peak success cover boundary cases
- rolling windows exclude infrastructure failures without treating them as successes
- retry branches never alter first-pass metrics
- the explicit `kind`-to-scorer mapping produces all applicable failure codes, including topological node coverage
- missing usage and zero-retry runs produce `not reported`/`not measured`

### Repeat tests

- fixed-suite repeats align only by task ID
- different seeds cannot enter same-task agreement calculations
- confidence intervals and sample counts match known fixtures
- mixed session/output modes are rejected from pooled summaries

### Report tests

- generated HTML contains all tasks and tier headers
- filters and detail expansion work without network access
- private scorer constraints are absent from the standard report
- outcome meaning remains understandable with color disabled
- body/supporting type respects the minimum sizes
- screenshots at desktop and 768px widths preserve trace priority and readable text

## Acceptance criteria

The design is complete when a generated report lets the operator answer, without opening raw JSON:

1. How far did this model/effort condition remain reliable?
2. Where did non-exact answers become more frequent?
3. Was degradation gradual, task-family-specific, or a sharp cliff?
4. What precisely went wrong on each non-exact task?
5. Which failures recovered during the later retry phase?
6. How much time and reported compute did the capability require?
7. Which conclusions come from a single session versus repeated evidence?
8. What agentic-coding routing recommendation follows, and which parts are only heuristic proxies?

The result must remain an evidence profile rather than a single bounded capability label.
