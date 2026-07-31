---
description: Use after fixing a non-trivial bug, solving a tricky problem, or discovering a non-obvious workaround, to capture a durable lesson in docs/learnings/. Trigger phrases: "that worked", "it's fixed", "working now", "problem solved".
---

# Compound Learning

Document a solved problem so future agents don't re-discover the lesson. The first time you solve a problem takes research; document it, and the next occurrence takes minutes.

## When to Invoke

Invoke this skill when ALL three are true:

1. The problem has been **solved and verified** (not in-progress, not unverified)
2. The lesson is **non-trivial** (not a typo, not a single-line tweak)
3. The lesson is **durable** (would a future agent make the same mistake without this?)

Trigger phrases that should prompt invocation: "that worked", "it's fixed", "working now", "problem solved".

If only 1-2 of the three conditions are met, skip — output the skip message below and do nothing.

## Quality Gate (Is This Worthy?)

Before writing, run through these four questions. If **2 or more are yes**, write the learning. If unsure, err toward not writing.

- Would a future agent make the same mistake without this?
- Is this a non-obvious workaround for a library, framework, or Discord.js quirk?
- Does this contradict a likely assumption (e.g., "X must be called before Y")?
- Will this pattern recur in the same module/area?

## Storage

**Path:** `docs/learnings/<category>/<slug>.md`

**Categories** (use the first one that fits, add a new one only if nothing matches):

- `build-errors/` — TypeScript, Vite, pnpm, bundler issues
- `test-failures/` — Vitest, mock setup, assertion gotchas
- `runtime-errors/` — Production crashes, unhandled rejections
- `database-issues/` — Drizzle, PostgreSQL, migrations, JSONB
- `permissions/` — Discord permission bits, role hierarchy, overwrites
- `bot-lifecycle/` — Discord.js cache, event handlers, reconnection
- `auth/` — Better Auth, OAuth, session handling
- `integration-issues/` — Hono routes, SSE, middleware interactions
- `logic-errors/` — Diff engine, execution engine, planning session bugs
- `architecture-patterns/` — Project structure, module boundaries, design decisions
- `design-patterns/` — Reusable non-architectural patterns
- `conventions/` — Team-agreed way of doing something
- `tooling-decisions/` — Library or tool choices with durable rationale
- `best-practices/` — Fallback only when no narrower category applies

**Slug:** kebab-case, descriptive, 3-6 words. Examples: `jsonb-casting-for-plan-data`, `discord-perm-overwrite-order`, `drizzle-must-quote-snake-case`.

**Filename includes NO date** — the `date:` frontmatter field is canonical. This prevents re-numbering on every write.

## Format (Two Tracks)

**Bug track** — for fixes to broken code:

```markdown
---
title: Short searchable title
category: database-issues
module: planning/diff-engine
tags: [drizzle, jsonb, type-cast]
problem_type: runtime-error
date: 2026-06-20
---

# Short Title

## Problem

1-2 sentence description of the issue.

## Symptoms

Observable symptoms (error messages, behavior). Include the actual error text.

## What Didn't Work

Failed investigation attempts and why they failed. This prevents the next agent from re-trying them.

## Solution

The actual fix with code examples. Use before/after when applicable.

```ts
// Before
const data = row.plan_data;

// After
const data = row.plan_data as unknown as PlanData;
```

## Why This Works

Root cause explanation — why the solution addresses the underlying problem.

## Prevention

Strategies to avoid recurrence. Include test cases or assertions where applicable (adapt to your actual case).

```ts
it("should cast JSONB to PlanData", () => {
// Example — adapt to the actual behavior you want to verify
expect(row.planData).toMatchObject({ steps: expect.any(Array) });
});
```

## References

0
```

**Knowledge track** — for design decisions, patterns, or non-bug lessons:

```markdown
---
title: Short searchable title
category: architecture-patterns
module: packages/shared
tags: [execute-context, testing, mocks]
problem_type: design-decision
date: 2026-06-20
---

# Short Title

## Context

What situation, gap, or friction prompted this guidance.

## Guidance

The practice, pattern, or recommendation. Include code examples when useful.

## Why This Matters

Rationale and impact of following or not following this guidance.

## When to Apply

Conditions or situations where this applies.

## Examples

Concrete before/after or usage examples showing the practice in action.

## References

0
```

**Frontmatter rules:**

- All four required: `title`, `category`, `tags`, `date`
- `module` is optional but recommended (helps grep by area)
- `problem_type` is optional but recommended (e.g., `runtime-error`, `build-error`, `design-decision`, `convention`)
- `last_updated` is OPTIONAL — include ONLY when updating an existing doc (omit on new docs)
- `tags` must be a YAML array (use `[]` if none, never inline comma-separated)

**YAML safety:** Quote any value containing ` #` (space-hash) or `: ` (colon-space) to prevent silent YAML truncation. The `title:` field is the most common offender.

**`## References` section:** Every learning ends with a `## References` heading followed by a single integer count. Starts at `0` for new docs. The agent increments this integer when the learning is re-consulted in a future session (see Workflow Step 6).

## Workflow (Read This Before Writing)

**Step 1: Overlap detection**

Before writing, search the target category directory for similar problems using the Grep and Glob tools (NOT bash `ls`/`grep`):

- Use `Glob` to list files in `docs/learnings/<category>/`
- Use `Grep` to search for keywords in titles, tags, and module fields across the category
- Also Grep the README index for related tags

If a closely related learning exists, **read it first** and assess overlap:

| Overlap                                              | Action                                                                                                    |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **High** (same problem + same root cause + same fix) | **Update the existing doc** with fresher context. Add `last_updated: <today>`. Do not create a duplicate. |
| **Moderate** (same area, different angle)            | Create the new doc, then add a "Related" link in both files                                               |
| **Low or none**                                      | Create the new doc normally                                                                               |

Two docs describing the same problem will drift apart. Updating the existing one is always better than creating a second one that immediately needs consolidation.

**Step 2: Write the file**

Create `docs/learnings/<category>/<slug>.md` with the appropriate track template. Include the `## References` section at the bottom, initialized to `0`.

**Step 3: Update the README index**

Edit `docs/learnings/README.md` to add a bullet in the relevant category section:

```markdown
# Learnings Index

## database-issues/

- [JSONB casting for plan_data](./database-issues/jsonb-casting-for-plan-data.md) — must cast `as unknown as PlanData` to read. `#drizzle #jsonb`
```

If `docs/learnings/README.md` does not exist yet, create it with the standard preamble:

```markdown
# Learnings Index

Indexed catalog of durable lessons captured by the `compound` skill. Read at session start; check entries with relevant tags before non-trivial work.

## Pending Terms

Domain-specific terms flagged for `CONCEPTS.md` (project vocabulary glossary). When this list has 5+ terms, bootstrap `CONCEPTS.md` at repo root.

## Promote Candidates

Lessons referenced 3+ times that may deserve a spot in `AGENTS.md` as a project-wide rule. Review weekly.

## <Category Name>/

- [Title](./<category>/<slug>.md) — summary. `#tag1 #tag2`
```

**Step 4: Term surfacing**

After writing, scan the new learning for project-specific terms that have meaning beyond their obvious dictionary definition. Strong examples in this project: `Tombstone`, `Symbol`, `DesiredState`, `DriftEvent`, `Assumption`, `PlanStatus`, `IterationType`. (Self-explanatory UI surface names like `Studio` and `Dashboard` do NOT qualify — they're not domain terms with project-specific meaning.)

If you identify a qualifying term:

- If `CONCEPTS.md` exists at repo root → add the term to it (one-line definition)
- If not → add the term to the "## Pending Terms" section of `docs/learnings/README.md`

When "## Pending Terms" accumulates 5+ terms, you (or `compound-refresh`) should bootstrap `CONCEPTS.md` from the list.

**Step 5: Discoverability Check**

Verify that `AGENTS.md` would lead an agent to discover `docs/learnings/` before starting work in a documented area. The check is: does `AGENTS.md` mention `docs/learnings/` anywhere?

- If yes → no action needed
- If no → add a single line to the "Compound Learnings" section in `AGENTS.md`

This runs every time the skill is invoked. If the mention is already present, do nothing.

**Step 6: Reference tracking (when consulting an existing learning)**

When you apply an existing learning to a current problem (i.e., you read a learning file and use its guidance), increment its `## References` count by 1 using the Edit tool. If the count reaches **3 or more**, add a bullet to the "## Promote Candidates" section of `docs/learnings/README.md` with the learning's title and a one-line rationale (e.g., "Used in 3 bug fixes across X, Y, Z").

The user reviews "Promote Candidates" weekly and decides whether to promote any of them to `AGENTS.md` as a project-wide rule. You (the agent) never write to `AGENTS.md` directly.

## Preconditions (Advisory)

This skill is advisory, not enforced. The preconditions are:

- `problem_solved` — the problem has a working fix
- `solution_verified` — the fix has been tested or observed working
- `non_trivial` — not a typo, not a one-line change

If any precondition fails, the agent may still proceed but should note which condition failed in the learning's "What Didn't Work" section (so future agents know the solution is unverified).

## Outputs (What to Tell the User)

**On success (wrote a learning):**

```
Learning captured: docs/learnings/<category>/<slug>.md — <title>.
Term surfaced: <term or "none">.
References: <n> (this counts as 1).
```

**On skip (decided not to write):**

```
No learning captured — <one-sentence reason, e.g., "the fix was a single-line typo" or "the lesson isn't durable enough to merit a learning">.
```

**On update (modified existing doc):**

```
Learning updated: docs/learnings/<category>/<slug>.md — <title>.
```

## What This Skill Does NOT Do

- **No automatic promotion to AGENTS.md** — the agent only flags candidates; you decide what becomes a rule
- **No parallel subagents** — single-pass, no fan-out
- **No session history search** — that's a separate concern
- **No specialized agent reviews** — write the learning, move on
