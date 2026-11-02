---
name: systematic-debugging
description: >-
  Root-cause debugging workflow for bugs, test failures, flaky tests,
  regressions, and multi-layer failures. Load automatically before proposing
  fixes whenever unexpected behavior or failing tests occur.
---

# Systematic Root-Cause Debugging

Find and verify the root cause before writing a fix. Symptom patches mask bugs and waste turns.

## 1. Reproduce & Isolate Before Editing

1. **Read complete failure output:** Inspect full stack traces, exit codes, stderr, and line numbers without skimming.
2. **Check recent delta:** Inspect `git status`, `git diff`, and recent commits/config changes in the failing path.
3. **Lock a deterministic repro:** Identify the smallest command, test, or request that triggers the failure reliably. If non-deterministic, gather instrumentation data first — never guess at fixes blind.

---

## 2. Single-Pass Multi-Boundary Probing

When a failure crosses multiple layers (`UI → API → service → DB`, `hook → CLI → subprocess`, `CI → build → env`):
- Instrument entry/exit inputs, config/env presence, and status at **each component boundary in a single diagnostic run** rather than guessing one layer per turn.
- Run once to pinpoint the exact boundary where valid input turns into missing/corrupt output, then remove temporary debug probes before committing.

---

## 3. Backward Call-Chain Tracing

When an error surfaces deep in the call stack (empty path, `undefined` field, wrong working directory, invalid ID):
1. Do **not** paper over the crash site (`if (!val) return`) as your primary fix.
2. Trace callers **upward** step-by-step to find where the bad/uninitialized value originated.
3. Fix the bug at the **source**, and keep local input/invariant guards at lower layers strictly as defense-in-depth.

---

## 4. Flaky & State-Polluted Tests

- **Condition waiting over `sleep`:** Never fix async test races by bumping `sleep()` / `setTimeout()` delays (unless explicitly testing timer/debounce durations). Poll or await the observable state transition (`waitFor(() => condition)` with a clear timeout message).
- **Suite pollution ("passes alone, fails together"):** When a test fails only alongside other tests due to leaked files, DB rows, mocks, or env vars, bisect the offending test file with `./scripts/find-polluter.sh <polluted_path_or_marker> '<test_glob>'`.

---

## 5. One Hypothesis at a Time & 2-Strike Stop

1. State one falsifiable root-cause hypothesis and make the smallest change to test it.
2. **Verify Red → Green:** Confirm a regression test fails without the fix (or reproduce the failure before applying), then passes with the fix.
3. **2-Strike Circuit Breaker:** If **2 consecutive fix attempts** fail to resolve the issue, **stop patching**, revert the failed edits so they don't compound, and re-examine the architecture or surface what doesn't add up to the user.
