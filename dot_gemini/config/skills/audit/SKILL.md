---
name: audit
description: >-
  Audit a repository, subsystem, or existing findings list for correctness bugs,
  broken flows, unsafe cross-layer assumptions, and production risk — fixing
  unambiguous local bugs immediately and escalating contract/architecture
  decisions. Triggered by /audit, code-audit requests, or audit triage.
---

# Codebase Audit & Autonomous Triage (`/audit`)

Run correctness-first audits without turning them into style or tech-debt inventories. Report and act **only** on problems with a concrete failure mode, meaningful impact, and verified evidence.

## Execution Mode

- **Default — Audit, Fix & Escalate:** Investigate with full evidence rigor, **autonomously fix and verify** every unambiguous in-boundary problem right away, and report remaining items as structured escalations (`decision` / `disputed` / `deferred`).
- **Report-Only Override:** Switch to read-only investigation (zero file mutations) **only** when the user explicitly asks not to edit code yet (e.g., *"audit only"*, *"report only"*, *"don't fix yet"*).

---

## 1. Audit Contract & Scope

Before scanning, bound the audit from the request and repository layout:
- Surfaces, entry points, and user/data/operational guarantees they must preserve.
- Runtime exercise feasibility, exclusions, and prior audit/issue docs (e.g., `docs/issues/`) so known or regressed items are classified accurately rather than re-reported as new.
- For repository-wide audits, partition by real system boundaries (trust boundaries, persistence, concurrency, external side effects, recovery). Never claim full-repository coverage when only representative files were sampled.

**Primary targets:**
- Logic bugs, broken user/system flows, and invalid cross-layer contracts.
- State, cache, lifecycle, race, and data-consistency failures.
- Unreliable cancellation, persistence, rollback, or recovery paths.
- Authorization, tenant-boundary, secret-exposure, or data-corruption risks.
- Severe wasted work or resource-exhaustion bottlenecks on realistic inputs.

**Exclude** (unless causing a concrete failure mode above):
- Style, naming, formatting, preferred abstractions, or missing tests by themselves.
- Speculative scaling concerns without a reachable path to failure.
- Broad rewrites when a surgical fix resolves the risk.

---

## 2. Evidence Standard

Treat pattern searches as candidate generation only — confirm a reachable failure mode before acting or reporting:
- Cite the exact `file` and symbol, tracing **trigger → violated guarantee → impact** across callers, validation, transactions, outer guards, and recovery paths.
- Label evidence **`Observed`** when exercised at runtime, or **`Inferred`** when established from code inspection only. Never present unexecuted behavior as observed.
- Reproduce Critical/High issues when a safe local/runtime path exists (state the exact constraint if not).
- Deduplicate by root cause (group repeated callsites sharing one fix and impact).

---

## 3. Autonomy vs. Escalation Boundary

You own **"how"**; the user owns **"what"** and **"why"**.

### Fix Immediately (Straightforward — Local & Reversible)
In default mode, implement and verify (`test`, `typecheck`, `lint`) without asking first when the code and contracts imply one clear fix:
- Missing guards, null/edge crashes, broken internal contracts, race/leak fixes, error handling, stronger types, dead-code cleanup, and regression tests that preserve externally visible contracts.
- Mark out-of-scope high-impact discoveries `Incidental` (fix if straightforward and safe; do not widen the rest of the scan around them).

### Escalate — Never Fix Autonomously
Leave untouched and report even when a fix looks obvious if resolution touches:
- Product behavior or foundational architecture choices.
- Public APIs, wire contracts, schemas, or database models/migrations.
- Security, authentication, or permission semantics.
- New dependencies or infrastructure changes.
- Destructive operations or anything expensive/hard to reverse.
- Any finding with multiple reasonable fixes carrying real tradeoffs.

---

## 4. Severity & Output Format

**Severity** reflects demonstrated reach and impact (lower confidence ≠ lower severity — gather evidence or drop weak candidates):
- **Critical:** Cross-tenant auth bypass, secret exposure, irreversible corruption, or core safety compromise.
- **High:** Broken primary flow, overlapping mutations, lost state, or failed recovery affecting real users.
- **Medium:** Bounded correctness failure, stale state, validation gap, or degraded recovery with a reachable trigger.
- **Low:** Contained correctness bug with narrow impact (never use `Low` for style or weak guesses).

**Output structure** (omit empty sections):

1. **Coverage:** Audited surfaces/guarantees, runtime checks run, and material limits (plus a brief **Verified OK** note only for major guarantees actually exercised).
2. **Fixed:** **One line per fixed item** — `[Severity] file/symbol`: what was broken, what changed, and verification passed.
3. **Escalated / Unresolved** (ordered by severity, then blast radius), each tagged with one label:
   - **`decision`** — crosses the escalation boundary or has multiple valid fixes. Include `Observed`/`Inferred` evidence, concrete failure mode, 2–3 options with tradeoffs, and **one clear recommendation**. *(Use `ask_question` only when an immediate choice blocks requested follow-up work.)*
   - **`disputed`** — *(when triaging an external review or prior report)* live code/outer guards prove it is not a real issue.
   - **`deferred`** — real bounded issue that is low-value or high-churn right now.
