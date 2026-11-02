---
name: worktree-sync
description: >-
  Use this skill when the user asks to audit, sync, merge, reconcile, or clean up
  multiple Git worktrees into the main branch after parallel development or agent
  sessions. Detects uncommitted work, fork-point mismatches, textual conflicts,
  cross-worktree semantic overlaps ("ghost conflicts"), lockfiles, and cascade conflicts.
---

# Autonomous Git Worktree Sync & Reconciliation (`worktree-sync`)

When multiple agent sessions or parallel developers work across isolated Git worktrees, integrating everything back into `main` must be methodical, non-destructive, and resilient against real-world Git edge cases.

Follow this runbook when the user says **"everything is finished"**, **"merge all worktrees"**, or requests a multi-worktree audit and cleanup.

---

## Core Philosophy & Non-Destructive Invariants

1. **Autonomous End-to-End Ownership**: When invoked, guide the integration to completion: audit all worktrees, stabilize broken repository states, triage uncommitted work, execute ordered merges, verify semantic integrity, and safely prune merged trees.
2. **Never Discard Unverified Work**: Never execute destructive commands (`git checkout -- .`, `git clean -fd`, `git reset --hard`) on user work without explicit confirmation. If uncommitted files exist:
   - For legitimate finished feature edits: stage selectively and commit.
   - For unfinished local WIP or collision blocks: stash safely using `git stash push -u -m "wt-sync: pre-merge WIP"`.
   - For obvious build artifacts or secret files (`.env`, `node_modules`, `dist/`): warn and exclude from commits.
3. **Primary Worktree Integration**: Always perform merges from the **primary worktree** on the target branch (`main`). Never attempt to check out `main` inside a secondary worktree.

---

## Step 1: Run Zero-Mutation Audit (`git wt-sync`)

Run the diagnostic script from anywhere in the repository:

```bash
git wt-sync
```

*(Or invoke [scripts/git-wt-sync](./scripts/git-wt-sync) directly).*

### Audit Output Interpretation

The script is **100% read-only** (zero temporary objects written to the real repository `.git/objects`). Read the output systematically:

1. **Header Placement Alerts**:
   - `🚨 TARGET BRANCH MISPLACED`: Target branch (`main`) is checked out in a secondary worktree rather than the primary worktree.
   - `⚠️ PRIMARY WORKTREE ON '<other>'`: The primary worktree is checked out on a feature branch instead of `main`.
   - `Stashes found`: Reminds you of unpopped stashes that might contain unfinished work.
2. **Worktree Status Badges & Operations**:
   - `[👻 MISSING DIR]`: Worktree directory was deleted on disk without running `git worktree remove`. Unmerged commits on that branch are still audited!
   - `[🔒 LOCKED: <reason>]`: Worktree is pinned by the user/system; `--prune-merged` will safely skip deleting it.
   - `🚨 IN-PROGRESS REBASE / MERGE / CHERRY-PICK`: Git operation in progress with pending conflicts.
   - `🔒 INDEX LOCKED`: Stale `index.lock` exists.
   - `🚨 NESTED WORKTREE NOT GITIGNORED`: A secondary worktree was created inside another worktree's tree without being ignored.
3. **Commit & Working Tree States**:
   - `⚠️ N uncommitted file(s)`: Breakdown of unmerged, staged, unstaged, and untracked files.
   - `⚠️ Suspicious untracked`: Flags `.env*`, `*.log`, `node_modules/`, `build/`, etc.
   - `🚨 LEFTOVER CONFLICT MARKERS`: Detected committed or staged `<<<<<<<` markers.
4. **Merge Readiness**:
   - `✅ Already merged / identical`: 0 commits ahead, 0 dirty files — ready to prune.
   - `✅ Already integrated (squash/patch-equivalent, 0 net diff)`: Squash-merged into `main` previously; safe to prune with `git branch -D`.
   - `✅ Clean merge into main`: Clean 3-way merge, no file overlap.
   - `👀 SEMANTIC OVERLAP`: Clean text merge, but touched files overlapping with other worktrees or commits on `main`.
   - `⚠️ BLOCKED BY DIRTY 'main'`: Branch edits merge cleanly with committed `main`, but collide with uncommitted files in `main`.
   - `❌ CONFLICTS WITH UNCOMMITTED WORK IN 'main'`: Edits conflict directly with dirty lines in `main`.
   - `⚠️ LOCKFILE-ONLY CONFLICT`: Conflicted files are exclusively lockfiles (`pnpm-lock.yaml`, `package-lock.json`, `Cargo.lock`, `uv.lock`, etc.).
   - `💥 CASCADE CONFLICT`: Branch merges cleanly alone against `main`, but will conflict once preceding peer branches are merged.
   - `📌 Unmerged local branches (no active worktree)`: Local branches with commits ahead of `main` that have no checkout.

---

## Step 2: Stabilize Stuck States, Nested Worktrees, & Branch Placement

Before attempting merges, eliminate broken states:

### A. Resolve In-Progress Operations & Stale Locks
- If an operation was aborted or left half-finished:
  ```bash
  # In the affected worktree:
  git -C "<wt_path>" rebase --abort    # or git merge --abort / git cherry-pick --abort
  ```
- If a crashed process left `index.lock`:
  ```bash
  rm -f "$(git -C "<wt_path>" rev-parse --path-format=absolute --git-path index.lock)"
  ```

### B. Ignore Nested Worktrees
If `git wt-sync` reports `🚨 NESTED WORKTREE NOT GITIGNORED: .worktrees/<name>`:
Add `.worktrees/` to the repository's local exclude file so it does not pollute `git status`:
```bash
echo ".worktrees/" >> "$(git rev-parse --git-common-dir)/info/exclude"
```

### C. Fix Target Branch Placement
- If primary worktree is on a feature branch (`feat/x`) and `main` is not checked out:
  1. Commit or stash any work on the primary worktree:
     ```bash
     git commit -m "feat/x: save work"   # or git stash push -u -m "WIP on feat/x"
     ```
  2. Switch primary worktree to `main`:
     ```bash
     git checkout main
     ```
- If `main` is checked out in secondary worktree `<sec_wt>`:
  1. Inside `<sec_wt>`, switch away from `main` to preserve any work on a descriptive branch (or detach if clean with 0 commits ahead):
     ```bash
     git -C "<sec_wt>" checkout -b "wt/<topic>"   # or `checkout --detach` if clean
     ```
  2. Inside primary worktree, checkout `main`:
     ```bash
     git checkout main
     ```

---

## Step 3: Triage Dirty Work in `main` AND Secondary Worktrees

### A. Triage Dirty Files in `main`
Git `merge` strictly refuses to merge any branch that touches files that are dirty or untracked in `main`.
1. **Legitimate finished code on `main`**:
   ```bash
   git add <files>
   git commit -m "chore: commit finished edits on main"
   ```
2. **Unfinished local WIP or experiments on `main`**:
   ```bash
   git stash push -u -m "wt-sync: pre-merge main WIP"
   ```
3. **Untracked files that duplicate incoming branch files identically**:
   If an untracked file was manually copied across trees and matches the incoming branch byte-for-byte, remove it so `git merge` can track it:
   ```bash
   rm "<untracked_file>"
   ```

### B. Triage Secondary Worktrees (Including Detached `HEAD`)
1. **Detached HEAD worktrees with uncommitted work**:
   Attach a local branch so commits are never lost when the worktree is removed:
   ```bash
   git -C "<wt_path>" checkout -b "wt/<descriptive-name>"
   ```
2. **Commit finished secondary work**:
   - Check status and diff:
     ```bash
     git -C "<wt_path>" status --short
     git -C "<wt_path>" diff
     ```
   - Stage source files while excluding junk (`.env*`, `*.log`, build outputs):
     ```bash
     git -C "<wt_path>" add -u -- .
     git -C "<wt_path>" add <new_source_files>
     git -C "<wt_path>" commit -m "<descriptive feature message>"
     ```
3. **Verify no leftover conflict markers**:
   ```bash
   git -C "<wt_path>" diff --check HEAD~1 HEAD
   ```

---

## Step 4: Ordered Merge, Semantic Overlaps, & Conflict Resolution

Re-run `git wt-sync` to get a fresh audit plan.

### A. Merge Order Strategy
Execute merges from the **primary worktree** on `main`:
1. **Skip already merged & squash-equivalent branches**:
   Branches flagged `✅ Already merged` or `✅ Squash/patch-equivalent` require no merge — leave them for Step 5 pruning.
2. **Merge clean independent branches first** (no semantic overlap):
   ```bash
   git merge --no-ff "<branch>" -m "Merge branch '<branch>'"
   ```
3. **Merge clean semantic-overlap branches second** (`👀 SEMANTIC OVERLAP`):
   ```bash
   git merge --no-ff "<branch>" -m "Merge branch '<branch>'"
   ```
   - **Immediately read the combined symbols**: inspect the overlapping files flagged by `git wt-sync` around modified functions, imports, and data structures.
   - **Run Verification Gate**: run the repository's fast verification command (e.g. `pnpm typecheck`, `npm test`, `cargo check`, `pytest`). Do not proceed to the next branch until verification passes!

### B. Resolving Conflicts Safely
Always rebase inside the **secondary worktree** so that `main` remains green and working:

```bash
git -C "<wt_path>" rebase main
```

Resolve according to the conflict tier:

1. **Lockfile-Only Conflict (`⚠️ LOCKFILE-ONLY CONFLICT`)**:
   Never resolve lockfile conflicts by hand!
   - Ensure the dependency manifest (`package.json`, `Cargo.toml`, `pyproject.toml`) retains additions from both sides (keep dependencies from both branches if manifests conflicted).
   - Check out `main`'s version of the lockfile only as a temporary placeholder to unblock rebase:
     ```bash
     git -C "<wt_path>" checkout --ours <lockfile>
     ```
   - Regenerate the lockfile cleanly via the project package manager:
     - Node / pnpm: `pnpm install` (or `npm install` / `yarn install`)
     - Rust: `cargo check` or `cargo generate-lockfile`
     - Python: `uv lock` or `poetry lock --no-update`
     - Go: `go mod tidy`
   - Stage the updated lockfile and manifest, then continue rebase:
     ```bash
     git -C "<wt_path>" add <lockfile> <manifest>
     git -C "<wt_path>" rebase --continue
     ```

2. **Additive / Structural / Signature Adaptations**:
   - Inspect both sides of history:
     ```bash
     git -C "<wt_path>" log -p main..HEAD
     ```
   - Adapt the function calls, imports, or schemas to match `main`'s updated contracts.
   - Run verification in `<wt_path>` to ensure tests pass.
   - Continue rebase:
     ```bash
     git -C "<wt_path>" add <resolved_files>
     git -C "<wt_path>" rebase --continue
     ```

3. **Contradictory Product / Design Intent**:
   If two worktrees implemented conflicting product logic, do not guess:
   - Ask the user concisely which behavior takes precedence.
   - **Optional Handoff Prompt**: If an external agent session is active in `<wt_path>`, provide a structured handoff prompt:
     ```text
     The main branch has been updated with parallel commits touching:
     - <file>: <summary of change on main>

     Please rebase your branch in '<wt_path>':
     1. git -C "<wt_path>" rebase main
     2. Resolve conflicts in <file> preserving your feature while adopting main's new signature.
     3. Verify tests pass and commit.
     ```

4. Once rebased, re-run `git wt-sync` and merge cleanly into `main`:
   ```bash
   git merge --no-ff "<branch>" -m "Merge branch '<branch>'"
   ```

---

## Step 5: Final Verification, Stash Pop, & Prune

1. **Full Verification on `main`**:
   Run full test suite, build, and linter on the unified `main` branch:
   ```bash
   pnpm test && pnpm typecheck   # or repository equivalent
   ```
2. **Restore Stashed WIP (if any)**:
   If you stashed local work from `main` in Step 3:
   ```bash
   git stash pop
   ```
3. **Review Orphan Branches**:
   If `git wt-sync` listed `📌 Unmerged local branches (no active worktree)`, confirm with the user whether they should be merged or deleted.
4. **Safely Prune Merged Trees & Local Branches**:
   ```bash
   git wt-sync --prune-merged
   ```
   - Automatically removes secondary worktrees whose commits are integrated or 0 net diff.
   - Deletes clean merged branches (`git branch -d`) and verified squash-merged branches (`git branch -D`).
   - Automatically skips `locked` worktrees.
   - Cleans up stale metadata with `git worktree prune`.
