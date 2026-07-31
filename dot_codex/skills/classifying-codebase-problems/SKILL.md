---
description: Use when user asks generally to scan, review, inspect, or analyze a codebase for logic issues, bugs, architecture flaws, design issues, broken flows, critical problems, or unoptimized system behavior before implementation
---

# Classifying Codebase Problems

## Overview

Use this for correctness-first codebase scans. Find problems that can break behavior, block flows, corrupt state, expose data, or waste important system work. Do not turn the scan into a technical-debt audit.

## When To Use

Use when the user asks generally to:

- scan or review the codebase
- find problems, bugs, logic issues, or broken flows
- inspect architecture flaws or system design issues
- look for critical issues or unoptimized system behavior
- analyze risks before deciding what to fix

Do not use this for normal implementation, requested code review of a diff, or broad maintainability cleanup.

## Scan Scope

Primary targets:

- logic bugs
- broken user or system flows
- architecture flaws that affect correctness
- state, cache, race, lifecycle, or data consistency problems
- invalid assumptions between layers
- unreliable execution or recovery paths
- unoptimized flows that block users or waste important work

Incidental high-impact targets:

- security exposure
- data loss or corruption risk
- severe performance bottleneck affecting real flow
- operational risk that can break execution

Exclude by default:

- generic technical debt
- style, naming, or formatting issues
- refactor-only ideas
- missing tests by themselves
- "cleaner code" suggestions
- speculative architecture improvements with no behavior risk

## Classification Rule

Classify every reported problem into one of these buckets.

| Bucket                          | Use For                                                                                                                                                    |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Straightforward Problems        | Clear bug, missing guard, broken contract, consistency mismatch, false crash, data leak, or obvious risk where existing code implies the correct behavior. |
| Decision-Required Problems      | Real issue with product behavior, schema/data model, UX, ownership, persistence, destructive behavior, compatibility, or multiple valid fixes.             |
| Incidental High-Impact Problems | Security, corruption, severe performance, or operational risks discovered while scanning outside the primary target.                                       |

If a problem is straightforward, do not ask the user to decide. Explain that build mode can fix it later.

If a problem needs a decision, give 2-3 options, tradeoffs, and one recommendation.

## Output Format

Do not include file paths or line numbers by default. Focus on background, failure mode, impact, and fix direction. Include file references only if the user asks for evidence, implementation handoff needs precision, or the finding would be ambiguous without them.

```md
## Straightforward Problems

These are clear issues. Build-mode agent can fix them without user decision.

1. [Severity] [Problem]
   - Background: system flow involved
   - Issue: what is wrong
   - Impact: what can break, leak, corrupt, or block
   - Fix direction: what build mode should change

## Decision-Required Problems

These are real issues, but user choice is needed before implementation.

1. [Severity] [Problem]
   - Background: system flow involved
   - Issue: what is wrong
   - Impact: what can break or become hard later
   - Options:
     - A: option with tradeoff
     - B: option with tradeoff
     - C: option with tradeoff
   - Recommendation: preferred option and why

## Incidental High-Impact Problems

Use this section only if needed.

1. [Severity] [Problem]
   - Background:
   - Issue:
   - Impact:
   - Fix direction or decision needed:

## Recommended Build Batch

Straightforward:

1. ...

Needs approval:

1. ...
```

## Severity Guidance

- Critical: cross-user data exposure, destructive corruption, auth bypass, or execution path that can break core safety guarantees.
- High: broken primary flow, race causing overlapping mutations, lost approved state, failed rollback/recovery, or invalid execution input.
- Medium: correctness risk with narrower scope, stale UI/server state, inconsistent validation, or degraded recovery.
- Low: minor correctness issue with limited impact.

## Common Mistakes

| Mistake                                             | Correct Behavior                                                       |
| --------------------------------------------------- | ---------------------------------------------------------------------- |
| Listing technical debt because it looks messy       | Skip it unless it causes behavior risk.                                |
| Reporting file references first                     | Explain background and impact first.                                   |
| Mixing obvious fixes with decision items            | Separate buckets clearly.                                              |
| Asking user about clear bugs                        | Mark straightforward and leave for build mode.                         |
| Ignoring security because user did not say security | Report incidental high-impact security issues.                         |
| Suggesting rewrites                                 | Prefer smallest fix direction unless architecture choice is the issue. |
