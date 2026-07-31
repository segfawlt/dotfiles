---
description: Review and clean up docs/learnings/ — detect stale references, duplicates, and obsolete docs. Use when the user asks to "refresh my learnings", "audit docs/learnings/", or on a monthly cadence. Do not trigger for general debugging or refactor work unless the user explicitly points at docs/learnings/.
---

# Compound Refresh

Maintain the quality of `docs/learnings/` over time. Reviews existing learnings against the current codebase and removes or updates drifted ones.

## When to Invoke

- User says "refresh my learnings", "audit docs/learnings/", "clean up stale learnings"
- Monthly maintenance cadence (suggested)
- After a major refactor or dependency upgrade that may have invalidated references
- When `compound` flagged a related learning as potentially superseded

## Interaction

Ask **one question at a time** using the platform's blocking question tool. Prefer **multiple choice** with a recommendation. Lead with evidence — don't ask before you have it.

## Scope Selection

If the user provides a scope hint (filename, category, or module), narrow to that scope. Otherwise, process all of `docs/learnings/`.

For broad scope (20+ learnings), do a lightweight triage:

1. Read frontmatter of all learnings, group by category
2. For each cluster, check if primary referenced files still exist
3. Recommend starting with the cluster that has the most broken references

## Maintenance Outcomes

For each candidate learning, classify into one of five outcomes:

| Outcome         | When                                                             | Action                                                       |
| --------------- | ---------------------------------------------------------------- | ------------------------------------------------------------ |
| **Keep**        | Still accurate and still useful                                  | No file edit. Report reviewed-without-edits.                 |
| **Update**      | Core lesson correct, but file paths/names/links drifted          | Apply in-place edits, set `last_updated: <today>`            |
| **Consolidate** | Two learnings overlap heavily but are both correct               | Merge unique content into canonical doc, delete subsumed doc |
| **Replace**     | Core guidance is now misleading, but a better replacement exists | Write a successor (use the `compound` skill), delete the old |
| **Delete**      | Code/workflow gone, problem domain gone, no inbound links        | Delete the file. Git history preserves it.                   |

## Drift Classification: Update vs Replace

The critical question: **is the drift cosmetic or substantive?**

- **Update territory** — file paths moved, classes renamed, links broke, but the recommended approach still works. Fix the references.
- **Replace territory** — the recommended fix conflicts with current code, the pattern changed, or the architecture shifted. Write a new learning via the `compound` skill, then delete the old.

If you find yourself rewriting the "Solution" or "Why This Works" section, stop — that's Replace, not Update.

## Before Deleting: Check Three Things

1. **Is the implementation gone?** Use Grep to search for the file paths or class names in the learning. If the code moved, prefer Update.
2. **Is the problem domain still active?** Before deleting a learning about Discord permissions, check if the project still uses Discord permissions. If yes, the concept persists — that's Replace, not Delete.
3. **Are there inbound links?** Use Grep on all `*.md` files in the repo for the filename slug. If other docs cite this learning, signal Replace (don't leave dangling references).

**Auto-delete only when all three hold:**

- Implementation is gone (or fully superseded)
- Problem domain is gone
- Inbound links are absent or only decorative ("see also" pointers)

If any condition fails, prefer Update, Replace, or Consolidate.

## Delete, Don't Archive

There is no `_archived/` directory. When a doc is no longer useful, delete the file. Git history preserves it. A dedicated archive directory accumulates stale docs that pollute search results.

## Term Accumulation Check

After processing learnings, check `docs/learnings/README.md` → "## Pending Terms":

- If the list has **5+ terms** → suggest bootstrapping `CONCEPTS.md` (project vocabulary glossary) at repo root
- If less → no action

**Bootstrap process** (one-time action when threshold hit):

1. Create `CONCEPTS.md` at repo root with this preamble:

   > Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded from accumulated learnings, then accretes over time; direct edits are fine. Glossary only, not a spec or catch-all.

2. Copy the "Pending Terms" list into the new file as bullet entries (one line each: term — short definition)
3. Empty the "## Pending Terms" section in `docs/learnings/README.md` (replace contents with `_(no pending terms)_`)

## Reference Count: Promote Candidates

The `compound` skill tracks references via the "## Promote Candidates" section in `docs/learnings/README.md`. A learning hits "promote candidate" status after 3 references.

This refresh skill does NOT auto-promote. It only:
- Verifies the reference counts in the README are accurate
- Surfaces the "Promote Candidates" list for human review

The human decides what becomes a rule in `AGENTS.md`. The agent never writes to `AGENTS.md` directly.

## Discoverability Check

Verify `AGENTS.md` mentions `docs/learnings/` so future agents can find it. If not, the refresh can add a one-line mention (with user consent).

## What This Skill Does NOT Do

- **No automatic promotion to AGENTS.md** — you decide what becomes a rule
- **No parallel subagents** — single-pass review, no fan-out
- **No headless/automated mode** — interactive by design
