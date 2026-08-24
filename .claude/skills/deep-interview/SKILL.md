---
name: deep-interview
description: >
  Socratic requirements interview with mathematical ambiguity gating that also
  stress-tests the plan against your project's domain model and documents
  decisions inline. Asks ONE targeted question per round, scores clarity across
  weighted dimensions, sharpens terminology against the CONTEXT.md glossary,
  cross-references claims with the code to surface contradictions, and refuses
  to finish until ambiguity drops below threshold. Use when the user has a fuzzy
  idea OR a plan to harden and says "deep interview", "interview me", "ask me
  everything", "don't assume", "socratic", "grill me", "stress-test this plan",
  "sharpen the terminology", "I'm not sure exactly what I want", or wants rigorous
  requirements gathering before building. Designed for interactive sessions (`/q`);
  pass `--auto` to run it unattended end-to-end — self-answering every question with
  the recommended option, then implementing the spec, opening a merge request, and
  driving CI green. Writes a spec to `run/deep-interview/`, and maintains a durable
  `CONTEXT.md` glossary and `docs/adr/` ADRs.
argument-hint: "[--quick|--standard|--deep] [--auto] <idea or vague description>"
---

<Purpose>
Deep Interview replaces a vague idea (or an under-specified plan) with a
crystal-clear, domain-consistent specification through Socratic questioning. It
asks targeted questions that expose hidden assumptions, measures clarity across
weighted dimensions after every answer, sharpens terminology against the
project's documented language, cross-references claims against the actual code,
and refuses to finish until ambiguity drops below the resolved threshold. It
produces three artifacts (see Outputs). This is a **requirements-first** skill: it
hardens the requirements before any code and never implements, runs experiments,
commits, or pushes *while interviewing* — but once the spec is written the user may
choose to build it in the same session (see Phase 5).

`--auto` runs the same interview **unattended**: instead of putting each question to
the user, you answer it yourself with the recommendation you would have offered, and
record that as an assumption. Every other mechanic — targeting, scoring, the
threshold gate, challenge modes, the glossary and ADR writes — is unchanged. It then
takes the recommended option at the Phase 5 handoff as well, so an unattended run
goes all the way to a merge request: interview → implement → open MR →
`/fix-pipelines`. It never merges; the MR is where the human reviews both the code
and the assumptions it was built on.
</Purpose>

<Outputs>
Every run produces up to three artifacts. The glossary and ADRs are **durable,
tracked files written automatically (no approval prompt)** — they land as
uncommitted changes for the user to review via `git`:

- **Spec** — `run/deep-interview/deep-interview-{slug}.md`. The full, ephemeral
  record (gitignored): clarity scores, topology, ontology, transcript, the
  resolved goal/constraints/criteria.
- **Glossary** — `CONTEXT.md` (or per-context `CONTEXT.md` via `CONTEXT-MAP.md`).
  A durable glossary of domain terms, updated **inline** as terms resolve. Format:
  [references/CONTEXT-FORMAT.md](./references/CONTEXT-FORMAT.md). Glossary only —
  zero implementation detail.
- **ADRs** — `docs/adr/NNNN-slug.md`. Durable decision records, written
  automatically for resolved assumptions that meet all three criteria. Format and
  criteria: [references/ADR-FORMAT.md](./references/ADR-FORMAT.md).

The spec is ephemeral; `CONTEXT.md` and ADRs persist in the repo.
</Outputs>

<Use_When>
- The user has a vague idea and wants thorough requirements gathering before execution.
- The user has a plan and wants it stress-tested against the existing domain model and language.
- The user says "deep interview", "interview me", "ask me everything", "don't assume", "grill me", "stress-test this plan", "sharpen the terminology".
- The task is complex enough that jumping to code would waste cycles on scope discovery.
- The user wants mathematically-validated clarity, consistent terminology, and recorded decisions before committing to a direction.
</Use_When>

<Do_Not_Use_When>
- The user already has a detailed, specific request (file paths, function names, acceptance criteria) — execute directly.
- The user wants a quick fix or a single obvious change.
- The user says "just do it" / "skip the questions" — respect that: write a best-effort spec from what you have with `Status: EARLY_EXIT`, and stop. Do not implement.
- The user already has a spec/plan and asks to execute it.
</Do_Not_Use_When>

<Requirements>
By default this skill is driven entirely by `AskUserQuestion` (one question per
round), so it only works in an **interactive session** where that tool is available —
in arkhip that means a `/q` (or `/self`) session, which wires the Telegram answer
channel. If `AskUserQuestion` is not available, do not fake the loop: either re-run
with `--auto`, or ask the single most important clarifying question as a normal
message and stop for the user's reply.

**`--auto` is the supported way to run without that channel.** It never calls
`AskUserQuestion` at all, so it works in any session — but it buys that autonomy by
answering with *your* judgement rather than the user's, so every auto-answer is
recorded as an assumption and the run is labelled as unattended throughout (Phase 4)
and again on the merge request it ends at. Do not use `--auto` as a shortcut when the
user is available: a real answer beats a good guess, and here the guess gets built.
</Requirements>

<Execution_Policy>
- Ask ONE question at a time — never batch multiple questions.
- Target the WEAKEST clarity dimension with each question; name it and say why it is the bottleneck.
- Run the Round 0 topology gate once (lock the top-level component list) before any ambiguity scoring.
- For brownfield, gather codebase facts yourself with Grep/Glob/Read BEFORE asking the user, and cite the evidence (file path, symbol, pattern) that triggered each question.
- **Challenge terminology against the glossary.** When the user uses a term that conflicts with `CONTEXT.md`, or a vague/overloaded term, call it out and propose a precise canonical name immediately.
- **Cross-reference claims with code.** When the user states how something works, check whether the code agrees; if it contradicts, surface it ("your code cancels whole Orders, but you said partial cancellation is possible — which is right?").
- **Update `CONTEXT.md` inline.** When a term is resolved or sharpened, write it to the glossary right there — don't batch. Glossary only, no implementation detail.
- Score ambiguity after every answer and display the breakdown transparently. Glossary conflicts and unresolved code contradictions hold the relevant dimension's clarity down (see scoring).
- When the locked topology has multiple active components, score and target each one so depth on one component cannot hide ambiguity in its siblings.
- Do not declare the spec ready until ambiguity ≤ threshold (or the user chooses early exit).
- Allow early exit with a clear warning if ambiguity is still high.
- Challenge modes activate at specific round thresholds to shift perspective (Phase 3).
- While interviewing (Phases 1–4) the only ephemeral writes go to `run/deep-interview/`; durable writes are limited to `CONTEXT.md` and `docs/adr/`. Do not edit product source, run mutating commands, commit, or push during the interview — implementation, when the user opts into it at the Phase 5 handoff, then runs in the current session.

**Under `--auto` (unattended), these additionally hold:**
- **Never call `AskUserQuestion`** — not at the Round 0 topology gate, not in any Phase 2 round, not at the Phase 5 handoff. Print the question and answer it yourself.
- **Answer with the recommendation you already owe the user** — the same one 2a requires you to state. Do not invent a *different* answer because nobody is checking, and do not soften a question into one you can trivially answer.
- **Ask real questions anyway.** Auto mode changes who answers, not whether the assumption gets exposed. A round that asks nothing sharp is a wasted round, and a self-answer never earns a dimension ≥ 0.9 on its own — evidence does (code you read, a glossary term you reconciled, a constraint the input actually states).
- **Every auto-answer is an assumption**, carried into the spec's assumptions table with `Source: auto` so the user can overturn any single one — on the MR, which is where an unattended run lands.
- **Then build it.** `--auto` takes the recommended option at the Phase 5 handoff too: implement, open the MR, `/fix-pipelines` (see Phase 5). Still nothing during Phases 1–4, and still never a merge.
</Execution_Policy>

<Steps>

## Phase 1: Initialize

1. **Parse arguments** from `{{ARGUMENTS}}`:
   - Flags are recognized **only as leading tokens** — the run of `--…` words before
     the idea text starts. Once a non-flag word appears, everything after it is idea
     text, even if it contains something that looks like a flag. (`/deep-interview
     --auto add a --auto flag` → auto **on**, idea `add a --auto flag`; `/deep-interview
     add a --auto flag` → auto **off**, because the request is *about* the flag.)
   - Extract the threshold flag (default `--standard`):
     - `--quick` → threshold `0.35` (fast, accepts more residual ambiguity)
     - `--standard` → threshold `0.20` (default)
     - `--deep` → threshold `0.10` (most rigorous)
   - Extract `--auto` (default off) → **unattended mode**: you answer every question
     yourself with your own recommendation instead of asking the user. Orthogonal to
     the threshold flag — `--deep --auto` is a rigorous unattended run. An unknown
     `--flag` in leading position is not a silent no-op: say you ignored it and carry on.
   - The remaining text is the user's initial idea/plan. Announce the resolved threshold
     **and mode** up front, so a misparse is visible before the first question rather
     than after the last.
   - If the initial input is oversized (pasted logs/transcripts/files), first compress it into a concise prompt-safe summary that preserves intent, decisions, constraints, unknowns, and cited files/symbols. Treat that summary as the canonical input for all later prompts.

2. **Detect brownfield vs greenfield** using Grep/Glob/Read in the current directory:
   - Check for existing source files, package/config files, and git history.
   - If source exists AND the input references modifying/extending something → **brownfield**.
   - Otherwise → **greenfield**.

3. **Load the domain model** (both modes):
   - Read `CONTEXT.md` if present. If `CONTEXT-MAP.md` exists, the repo has multiple contexts — read it, find the relevant context's `CONTEXT.md`, and infer which one this topic belongs to (ask if unclear). See [references/CONTEXT-FORMAT.md](./references/CONTEXT-FORMAT.md).
   - **Seed the ontology from the glossary**: adopt the existing canonical term names so questions and the spec reuse them instead of inventing synonyms.
   - Read existing ADRs in `docs/adr/` (if any) so you don't re-litigate settled decisions.

4. **For brownfield**, build first-round context before designing questions:
   - Use Grep/Glob/Read to map the relevant codebase areas; remember concrete file paths, symbols, and patterns.
   - Use this so you never ask the user about facts the code already reveals, and so you can surface contradictions later.

5. **Announce the interview** to the user. The first line must state the threshold:

   > Deep Interview threshold: {threshold_percent} (mode: {quick|standard|deep})
   >
   > Starting deep interview. I'll ask one targeted question at a time and show your
   > clarity score after each answer. We proceed to a spec once ambiguity drops
   > below {threshold_percent}. I'll sharpen terminology in CONTEXT.md and record
   > genuine trade-offs as ADRs along the way.
   >
   > **Your idea/plan:** "{initial_input}"
   > **Project type:** {greenfield|brownfield}
   > **Glossary:** {loaded N terms from CONTEXT.md | none yet}
   > **Current ambiguity:** 100% (we haven't started yet)

   Under `--auto`, replace the second paragraph with this — it must be explicit that
   nobody is being asked, and that the result is assumption-based:

   > **Unattended (`--auto`):** I'll ask myself one targeted question at a time and
   > answer each with my own recommendation, showing the clarity score after each. No
   > questions will come to you. Every self-answer is recorded as an **assumption** in
   > the spec, so review them — any one of them may be wrong. Once the spec is ready
   > I'll implement it, open a merge request, and drive CI green — I won't merge, so
   > the MR is where you check both the code and the assumptions behind it.

## Round 0: Topology Enumeration Gate

Run this once, after Phase 1 and before any ambiguity scoring. The goal is to lock
the **shape** of the scope before depth-first questioning overfits to the most-
described component.

1. **Enumerate candidate top-level components** from the (summarized) input and brownfield context:
   - Extract top-level workstreams/surfaces/integrations/deliverables that can succeed or fail independently.
   - Prefer 1–6 components; group siblings if more appear. Do not treat sub-features or fields as top-level components unless the user framed them as independent outcomes.
2. **Ask one confirmation question** (via `AskUserQuestion`) before Round 1:

   ```
   Round 0 | Topology confirmation | Ambiguity: not scored yet

   I'm reading this as {N} top-level component(s):
   1. {component_name}: {one_sentence_description}
   2. ...

   Is that topology right? Should any component be added, removed, merged, split, or explicitly deferred?
   ```

   Offer contextually relevant options (e.g. **Looks right**, **Add/remove/merge**, **Defer one or more**) plus free-text. This is the only pre-scoring question and preserves the one-question-per-round rule.

   **Under `--auto`:** print the same block, then self-confirm the enumeration you
   just derived (`Auto: confirming this topology as-is`) and continue. Deferring a
   component unattended needs a reason from the input itself — the user's silence is
   not a deferral, so default to marking every enumerated component `active`.
3. **Lock the topology in working memory** after the answer: a normalized list of components, each marked `active` or `deferred` (with the confirmed deferral reason — the user's, or under `--auto` the one the input itself gives). Deferred components are excluded from ambiguity math but must still appear in the final spec.
4. **Single-component pass-through:** if the confirmation leaves one active component, proceed normally while still carrying it into scoring and the spec.

## Phase 2: Interview Loop

Repeat until `ambiguity ≤ threshold` OR the user exits early.

### 2a. Generate the next question
Consider: the (summarized) input; prior Q&A trimmed to fit; current per-dimension clarity scores; the locked topology and which active component is weakest; the active challenge mode (Phase 3); the loaded glossary; and brownfield context summarized to cited paths/symbols.

**Targeting strategy:**
- Pick the active component + dimension pair with the LOWEST clarity score.
- When several active components are similarly weak, rotate across them instead of repeatedly probing the same one.
- State in one sentence why this component/dimension is now the bottleneck.
- Expose ASSUMPTIONS — don't gather feature lists.
- **Prefer a glossary-conflict or code-contradiction question when one exists** — these are the highest-leverage clarifications. Cite the conflicting glossary term or the contradicting file/symbol.
- If the scope is conceptually fuzzy (entities keep shifting, core noun unstable), switch to an ontology-style question ("what IS the core thing here?") before returning to detail questions.
- For each question, also give your **recommended answer** so the user can confirm or correct rather than start from scratch.

**Question styles by dimension:**
| Dimension | Style | Example |
|-----------|-------|---------|
| Goal Clarity | "What exactly happens when…?" | "When you say 'manage tasks', what's the first action a user takes?" |
| Constraint Clarity | "What are the boundaries?" | "Should this work offline, or is connectivity assumed?" |
| Success Criteria | "How do we know it works?" | "If I showed you the finished product, what would make you say 'yes, that's it'?" |
| Context Clarity (brownfield) | "How does this fit / does the code agree?" | "I found JWT auth in `src/auth/` (passport + JWT). Extend that path or diverge?" |
| Terminology (glossary) | "Which term do you mean?" | "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?" |
| Contradiction (code vs claim) | "Your code says otherwise" | "Your code cancels entire Orders, but you said partial cancellation is possible — which is right?" |
| Scope-fuzzy / ontology | "What IS the core thing?" | "You've named Tasks, Projects, and Workspaces — which is the core entity and which are supporting views?" |

### 2b. Ask the question
Use `AskUserQuestion`. Present it with context:

```
Round {n} | Component: {target_component} | Targeting: {weakest_dimension} | Why now: {one_sentence_rationale} | Ambiguity: {score}%

{question}
(My recommendation: {recommended_answer})
```
Offer contextually relevant options plus free-text. Where helpful, make the recommended answer the first option.

**Under `--auto`:** do not call the tool. Print the same block as a normal message,
then answer it yourself with that recommendation and say so — the reader must be able
to see both the question and who answered it:

```
Round {n} | Component: … | Targeting: … | Why now: … | Ambiguity: {score}%

{question}
**A (auto):** {recommended_answer} — {one_sentence_why_this_is_the_right_default}
```

Treat that as the round's answer and continue to 2c unchanged. Two things stay
honest here: the answer must be the recommendation you would have shown the user
(not a weaker one that scores better), and a self-answer is *weaker evidence* than a
user's — so it moves a dimension less than a confirmed answer would, and cannot on
its own take one to ≥ 0.9. When the recommendation rests on something you have not
verified, say which fact would change it; that sentence is what makes the assumption
reviewable later.

### 2c. Score ambiguity
After the answer, score each dimension from 0.0–1.0 using your own careful, consistent judgment (apply the same standard every round). Honor the locked topology: score every active component independently; never drop a confirmed sibling just because another is already clear.

Score each dimension:
1. **Goal Clarity** — Is the primary objective unambiguous? Can you state it in one sentence without qualifiers, naming the key entities and relationships? **An entity whose name conflicts with the glossary, or stays fuzzy/overloaded, holds this down.**
2. **Constraint Clarity** — Are boundaries, limitations, and non-goals clear?
3. **Success Criteria Clarity** — Could you write a test that verifies success? Are acceptance criteria concrete?
4. **Context Clarity** (brownfield only) — Do we understand the existing system well enough to change it safely? Do the entities map to real codebase structures? **An unresolved contradiction between a claim and the code holds this down.**

For each dimension note: score, a one-sentence justification, and the remaining gap (if score < 0.9).

**Compute ambiguity** from the weighted clarity (use the minimum / weakest-component score across active components for each dimension):
- Greenfield: `ambiguity = 1 − (goal×0.40 + constraints×0.30 + criteria×0.30)`
- Brownfield: `ambiguity = 1 − (goal×0.35 + constraints×0.25 + criteria×0.25 + context×0.15)`

**Track ontology (key entities):** list the entities (nouns) discussed this round with type, key fields, and relationships. From round 2 on, reuse prior entity names (and glossary names) where the concept is the same; only name new entities for genuinely new concepts. Compute `stability_ratio = (stable + renamed) / total` (round 1 = N/A; renamed = same type + >50% field overlap counts toward stability). Briefly show which entities matched vs. are new/removed.

### 2d. Persist resolved terms to the glossary (inline)
If this round resolved or sharpened a domain term — a canonical name chosen, an overloaded word disambiguated, a glossary conflict settled — **write it to `CONTEXT.md` now** using [references/CONTEXT-FORMAT.md](./references/CONTEXT-FORMAT.md). Create `CONTEXT.md` lazily if it doesn't exist yet (pick the right per-context file when `CONTEXT-MAP.md` is present). Keep it a glossary: definition + `_Avoid_` synonyms, no implementation detail. Don't batch — capture terms as they crystallize.

### 2e. Report progress
```
Round {n} complete.

| Dimension | Score | Weight | Weighted | Gap |
|-----------|-------|--------|----------|-----|
| Goal | {s} | {w} | {s*w} | {gap or "Clear"} |
| Constraints | {s} | {w} | {s*w} | {gap or "Clear"} |
| Success Criteria | {s} | {w} | {s*w} | {gap or "Clear"} |
| Context (brownfield) | {s} | {w} | {s*w} | {gap or "Clear"} |
| **Ambiguity** | | | **{score}%** | |

**Topology:** Targeted {target_component} | Active: {active_count} | Deferred: {deferred_count}
**Ontology:** {entity_count} entities | Stability: {stability_ratio} | New: {n} | Changed: {n} | Stable: {n}
{--auto only → **Answered:** auto ({auto_answers_so_far} of {n} rounds self-answered)}
**Glossary:** {terms_written_this_round} term(s) written to CONTEXT.md ({total} total)
**Next target:** {target_component} / {weakest_dimension} — {rationale}

{ambiguity ≤ threshold ? "Clarity threshold met — ready to write the spec." : "Focusing next question on: {weakest_dimension}"}
```

### 2f. Check limits
- **Round 3+:** allow early exit if the user says "enough", "let's go", "build it".
- **Round 10:** soft warning — "We're at 10 rounds. Ambiguity: {score}%. Continue or proceed with current clarity?"
- **Round 20:** hard cap — proceed with whatever clarity exists, noting the risk.

**Under `--auto`** the user-driven limits have nobody to drive them, so:
- **No early exit** — there is no "enough" to hear.
- **No round cap.** Neither the round-10 warning nor the round-20 cap applies: an
  unattended run interviews until the clarity threshold is met. Auto mode exists to
  reach a *sound* spec without supervision, and stopping at an arbitrary round would
  hand the implementation step (which auto also runs) a spec it knows is still
  ambiguous.
- **The stall rule is what bounds it instead** — and it matters more, not less, since
  it is now the *only* terminator besides the threshold. Measure it against the **best
  (lowest) ambiguity reached so far**, not against the previous round: if 3 consecutive
  rounds fail to beat that best by ≥ 0.05, you are talking to yourself. A score that
  drifts or oscillates without converging must trip this — otherwise an unattended run
  loops with nobody watching. Switch to Ontologist; if that does not beat the best
  either, stop, write the spec with `Status: EARLY_EXIT`, and state the residual
  ambiguity plainly. A run that cannot converge ends there.

## Phase 3: Challenge Modes

At specific round thresholds, shift the questioning perspective. Each mode is used
ONCE, then normal Socratic questioning resumes. These are prompt-perspective shifts
for your own next question — not separate agents.

- **Round 4+ — Contrarian:** challenge the core assumption. "What if the opposite were true?" / "What if this constraint doesn't actually exist?"
- **Round 6+ — Simplifier:** probe whether complexity can be removed. "What's the simplest version that's still valuable?" / "Which constraints are necessary vs. assumed?"
- **Round 8+ — Ontologist** (only if ambiguity still > 0.3): find the essence. Given the tracked entities, ask "What IS this, really?" / "Which entity is the CORE concept and which are supporting?"

## Phase 4: Crystallize the Spec & Record Decisions

When ambiguity ≤ threshold (or hard cap / early exit):

1. Derive a short kebab-case `{slug}` from the input (e.g. `task-manager-cli`).
2. Write the spec to **`run/deep-interview/deep-interview-{slug}.md`** (create the
   directory first, e.g. `mkdir -p run/deep-interview`). `run/` is gitignored, so
   the spec is a working artifact. Surface the full path to the user when done.
3. **Reconcile the glossary:** ensure every canonical entity from the final ontology
   is present in `CONTEXT.md`. Write any that are still missing.
4. **Write ADRs automatically:** for each row in "Assumptions Exposed & Resolved"
   that meets all three criteria (hard-to-reverse / surprising / real trade-off —
   see [references/ADR-FORMAT.md](./references/ADR-FORMAT.md)), write
   `docs/adr/NNNN-slug.md` (scan for the next number; create `docs/adr/` lazily).
   No approval prompt — if it qualifies, record it; if it fails any criterion, skip
   it. List the ADRs created.
   - **Under `--auto`**, an ADR records a decision *you* made, not one the user
     confirmed, so give it `status: proposed` frontmatter (lowercase key, matching
     the existing ADRs) and one line naming the unattended run as its origin. The three criteria are unchanged: auto mode is not
     a reason to record more decisions, and definitely not a reason to record fewer.

Spec structure:

```markdown
# Deep Interview Spec: {title}

## Metadata
- Rounds: {count}
- Final Ambiguity: {score}%
- Type: greenfield | brownfield
- Threshold: {threshold} (mode: {quick|standard|deep})
- Answered by: {user (interactive) | auto (unattended, --auto)}
- Status: {PASSED | PASSED (auto) | EARLY_EXIT}
- Glossary terms written: {n} | ADRs written: {n}

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | {s} | {w} | {s*w} |
| Constraint Clarity | {s} | {w} | {s*w} |
| Success Criteria | {s} | {w} | {s*w} |
| Context Clarity | {s} | {w} | {s*w} |
| **Ambiguity** | | | **{1-total}** |

## Topology
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| {name} | {active|deferred} | {description} | {covered criteria or deferral reason} |

## Goal
{crystal-clear goal statement covering every active topology component}

## Constraints
- {constraint}

## Non-Goals
- {explicitly excluded scope}

## Acceptance Criteria
- [ ] {testable criterion}

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution | Source | ADR |
|------------|-----------|------------|--------|-----|
| {assumption} | {how questioned} | {what was decided} | {user \| auto} | {docs/adr/NNNN-slug.md or "—"} |

{--auto only: "Every `auto` row above is my judgement, not a confirmed requirement.
Correct any of them and re-run, or tell me which to change before building."}

## Technical Context
{brownfield: relevant codebase findings with file paths/symbols; note any contradictions found and how they were resolved}
{greenfield: technology choices and constraints}

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships | In glossary |
|--------|------|--------|---------------|-------------|
| {name} | {type} | {fields} | {relationships} | {yes/no} |

## Ontology Convergence
| Round | Entities | New | Changed | Stable | Stability |
|-------|----------|-----|---------|--------|-----------|
| 1 | {n} | {n} | - | - | - |
| … | … | … | … | … | … |

## Documentation Written
- Glossary: {CONTEXT.md path}, {n} term(s)
- ADRs: {list of docs/adr/NNNN-slug.md, or "none warranted"}

## Interview Transcript
<details><summary>Full Q&A ({n} rounds)</summary>

### Round 1
**Q:** {question}
**A{ (auto) if self-answered}:** {answer}
**Ambiguity:** {score}%

…
</details>
```

## Phase 5: Done — Build in this session (if chosen)

Through Phases 1–4 the skill only gathers requirements — it does not edit product
source, run experiments, commit, or push while interviewing. That boundary holds in
every mode; what differs is who picks the next step once the artifacts are written.
Interactively it is the user's call, never automatic (under `--auto`, see the
subsection below). The spec's `Status` (`PASSED` or `EARLY_EXIT`) records the
interview outcome; present the result and let the user choose via `AskUserQuestion`:

**"Your spec is ready (ambiguity: {score}%) at `run/deep-interview/deep-interview-{slug}.md`. I also wrote {n} glossary term(s) to CONTEXT.md and {n} ADR(s) to docs/adr/ (uncommitted — review with `git diff`). What next?"**
- **Implement it, open MR, `/fix-pipelines`** — "Build the spec in this session, push it as a merge request, then drive CI green." (Recommended)
- **Refine further** — return to the Phase 2 loop to keep raising clarity.
- **Done for now** — stop; the spec, glossary, and ADRs stay on disk for review.

The recommended option is a **three-step chain**, all in the current session — do not
defer any step to, or propose, a separate command or pipeline (in particular, do
**not** suggest `/experiment_changes` or `/self`); you are already in the session that
should carry it out:

1. **Implement it** — build the spec from the resolved goal, constraints, and
   acceptance criteria. Before committing, check `git status`: branch off the
   resolved base (never commit on the default branch) and stage **only** the files
   your implementation touched. Project workdirs and experiment worktrees are
   routinely dirty, and a blanket `git add -A` would sweep unrelated work into an
   unattended commit and push it under this interview's name.
2. **Open MR** — push the branch and open a merge request (`glab mr create`); never
   merge it. The human review you are converging on happens *there*.
3. **Drive CI green** — pull the failed jobs from the MR's latest pipeline and fix
   them, iterating until CI is green or a failure is genuinely out of scope (say
   which, and why). Use the `/fix-pipelines` skill — arkhip provisions it (alongside
   `review-mr` and `claude-audit`) to **every** session it launches (ADR 0032), so a
   session in a managed project has it and its `fetch_pipeline.py`. Outside an
   arkhip-launched session it may be absent; then do the same thing directly (`glab
   ci list`/`glab ci trace`, or the pipelines/jobs API), which needs a `GITLAB_TOKEN`
   in the environment. If neither is available, say so plainly and hand back the MR
   link with CI unverified — do not report the chain as complete.

### Under `--auto`: take it end-to-end

`--auto` takes the recommended option here too — it does not stop at the spec. Do
**not** call `AskUserQuestion`; post the summary as a plain message and then run all
three steps: implement, open the MR, `/fix-pipelines`.

**"Spec ready (ambiguity: {score}%, unattended) at `run/deep-interview/deep-interview-{slug}.md`. {n} glossary term(s) → CONTEXT.md, {n} ADR(s) → docs/adr/. {n} of the resolved assumptions are mine, not yours — building on them now; the MR is where you overturn any of them."**

The MR is what makes this safe to do unattended: nothing merges, every self-answered
assumption is visible in the diff and the spec, and CI has run against it by the time
anyone looks. So carry the labelling through to the end — the MR description must say
the requirements came from an unattended interview, and list the `Source: auto`
assumptions the branch is built on, so a reviewer knows which parts nobody confirmed.

</Steps>

<Reference>
## Flags
| Flag | Effect |
|------|--------|
| `--quick` / `--standard` / `--deep` | Threshold `0.35` / `0.20` (default) / `0.10` |
| `--auto` | Unattended: self-answer every question with your own recommendation; never call `AskUserQuestion`; no round cap; then implement → open MR → `/fix-pipelines` |

Flags are read **only from leading tokens**; anything after the first non-flag word is
idea text. The two axes are orthogonal (`--deep --auto` is valid).

## Interactive vs `--auto`
| | Interactive (default) | `--auto` |
|---|---|---|
| Round 0 gate, Phase 2 rounds | `AskUserQuestion` | printed + self-answered |
| Answer source | the user | your stated recommendation |
| Early exit / round caps | user decides; caps at 10 (warn) / 20 (hard) | no early exit, no round cap — threshold gate + stall rule only |
| Assumption `Source` | `user` | `auto` |
| ADR status | (none) | `proposed` |
| Phase 5 | asks; runs the chain if chosen | takes it: implement → MR → `/fix-pipelines` |
| Everything else (scoring, threshold, challenge modes, glossary/ADR writes) | — | identical |

## Dimension weights
| Dimension | Greenfield | Brownfield |
|-----------|-----------|------------|
| Goal Clarity | 40% | 35% |
| Constraint Clarity | 30% | 25% |
| Success Criteria | 30% | 25% |
| Context Clarity | — | 15% |

Brownfield adds Context Clarity because changing existing code safely requires understanding the system.

## Challenge modes
| Mode | Activates | Purpose |
|------|-----------|---------|
| Contrarian | Round 4+ | Challenge assumptions |
| Simplifier | Round 6+ | Remove complexity |
| Ontologist | Round 8+ (if ambiguity > 0.3) | Find the essence |

## Durable docs
- Glossary format & single/multi-context rules: [references/CONTEXT-FORMAT.md](./references/CONTEXT-FORMAT.md)
- ADR format & the 3 criteria: [references/ADR-FORMAT.md](./references/ADR-FORMAT.md)

## Ambiguity interpretation
| Score | Meaning | Action |
|-------|---------|--------|
| ≤ threshold | Clear enough | Write the spec |
| Just above threshold | Minor gaps | Continue interviewing |
| Moderate | Significant gaps | Focus the weakest dimension |
| High | Very unclear | Reframe (Ontologist) |

## Stop conditions
- **Hard cap (20 rounds):** proceed with current clarity, note the risk. (No cap under `--auto`.)
- **Soft warning (10 rounds):** offer to continue or proceed. (Not applicable under `--auto` — nobody to warn.)
- **Early exit (round 3+):** allow with a clear warning if ambiguity > threshold. (Not applicable under `--auto`.)
- **User says "stop"/"cancel":** stop immediately.
- **Ambiguity stalls** (3 rounds without beating the best score so far by ≥ 0.05): switch to Ontologist mode to reframe. Under `--auto` this is the only thing bounding the loop, so if the reframe does not beat it either, write the spec (`EARLY_EXIT`) and move on.
- **All dimensions ≥ 0.9:** skip to the spec.
- **Brownfield exploration fails:** proceed as greenfield, note the limitation.
</Reference>

<Examples>
<Good>
Targeting the weakest dimension:
```
Scores: Goal=0.9, Constraints=0.4, Criteria=0.7 → target Constraints (lowest).
"You said this should 'work on mobile'. Native app, responsive web, or PWA? Any specific devices/OS versions to support?"
(My recommendation: responsive web first, native later.)
```
Why: names the weakest dimension, explains the bottleneck, asks one specific question, offers a recommendation.
</Good>

<Good>
Glossary conflict surfaced and written inline:
```
"Your CONTEXT.md defines 'Account' as the billing entity, but here you're using it for the logged-in person — that's the 'User'. Shall I keep Account = billing and call this one User?"
[on confirm → writes/updates User and Account in CONTEXT.md immediately]
```
Why: catches a terminology clash against the glossary, proposes the canonical split, and persists it without batching.
</Good>

<Good>
Code-contradiction surfacing (brownfield):
```
[greps src/ → finds OrderService.cancel() cancels the whole order]
"You said partial cancellation is supported, but `OrderService.cancel()` in `src/orders/service.py` cancels the entire Order with no line-item path. Which is correct — add partial cancel, or is full-only the intended scope?"
```
Why: checked the code first, cited the exact symbol, and forced the contradiction to resolve (holds Context Clarity down until it does).
</Good>

<Good>
ADR written automatically at crystallization:
```
Assumption resolved: "Use event sourcing for the write model, project to Postgres for reads."
→ hard-to-reverse ✓, surprising ✓, real trade-off ✓ → writes docs/adr/0003-event-sourced-write-model.md (no prompt).
```
Why: meets all three criteria, so it's recorded; an easily-reversible choice would be skipped.
</Good>

<Good>
An unattended round (`--auto`) that still exposes an assumption:
```
Round 3 | Component: sync engine | Targeting: Constraints | Why now: conflict handling is the only unscored boundary | Ambiguity: 41%

Do two devices editing the same note offline converge automatically, or does the user resolve conflicts?
**A (auto):** Last-write-wins on a per-field basis — the input calls this a "notes app", not a collaborative editor, and CRDT machinery is a different product. This flips if notes are ever co-edited live.
```
Why: asks the question it would have asked a human, answers with the recommendation it owed them, marks it `(auto)`, and names the fact that would overturn it — so it lands in the spec as a reviewable assumption.
</Good>

<Bad>
Batching questions: "What's the audience? And tech stack? And how should auth work?" — shallow answers, inaccurate scoring.
</Bad>

<Bad>
`--auto` rubber-stamping: "Round 1 | A (auto): yes, that's right. Ambiguity: 8% → writing spec." — one soft question self-answered to clear the threshold. Auto mode changes who answers, not whether the assumption gets exposed; clarity still has to be earned round by round.
</Bad>

<Bad>
`--auto` stopping at the spec, or stopping at the MR: the recommended option is the whole chain — implement, open MR, `/fix-pipelines` — and auto takes all of it. A branch pushed with red CI is an unfinished run, not a delivered one.
</Bad>

<Bad>
`--auto` merging its own MR, or pushing to the default branch: the merge request *is* the review gate that makes an unattended run acceptable. Open it and stop there.
</Bad>

<Bad>
Asking about codebase facts: "What database does your project use?" — should have grepped. Never ask what the code already tells you.
</Bad>

<Bad>
Putting implementation detail in CONTEXT.md: "Order: stored in the orders table, indexed on customer_id." — CONTEXT.md is a glossary, not a schema. Keep it to what the term IS.
</Bad>
</Examples>

<Final_Checklist>
- [ ] Threshold resolved from the mode flag and announced as the first line; `--auto` read only from leading tokens and its mode announced too.
- [ ] CONTEXT.md / CONTEXT-MAP.md and existing ADRs loaded; ontology seeded from the glossary.
- [ ] Brownfield/greenfield detected via Grep/Glob/Read; brownfield questions cite repo evidence.
- [ ] Round 0 topology gate completed before any ambiguity scoring.
- [ ] One question per round, each naming the weakest dimension, why it's the target, and a recommended answer.
- [ ] Glossary conflicts and code contradictions surfaced (with citations) and used to hold the relevant clarity dimension down.
- [ ] Ambiguity scored and displayed after every round using the correct weights.
- [ ] Resolved terms written to CONTEXT.md inline (glossary only, no implementation detail).
- [ ] Challenge modes activated at rounds 4 / 6 / 8 (each once).
- [ ] Multi-component interviews rotate targeting across active components.
- [ ] Spec written to `run/deep-interview/deep-interview-{slug}.md`.
- [ ] ADRs written automatically for assumptions meeting all 3 criteria (sparingly); none otherwise.
- [ ] Spec includes topology, goal, constraints, non-goals, acceptance criteria, clarity breakdown, ontology, documentation-written list, and transcript.
- [ ] During the interview, no product source mutated and no commands run beyond exploration + the spec/glossary/ADR writes; building happens only after the Phase 5 handoff, in the current session, if the user opts in.
- [ ] Final handoff offered via AskUserQuestion (**interactive only** — never under `--auto`); spec/glossary/ADR paths surfaced to the user.
- [ ] Under `--auto`: zero `AskUserQuestion` calls; every round printed with its question and `A (auto)` answer; assumptions tagged `Source: auto`; spec `Status: PASSED (auto)`; any ADR `status: proposed`; no round cap (threshold gate + stall rule only).
- [ ] Under `--auto`, the Phase 5 chain ran to the end: implemented (only its own files staged, off the default branch), MR opened (never merged) with the unattended origin and `Source: auto` assumptions in its description, and CI driven green — or, where the pipeline could not be reached at all, that stated plainly rather than reported as done.
</Final_Checklist>

Task: {{ARGUMENTS}}
