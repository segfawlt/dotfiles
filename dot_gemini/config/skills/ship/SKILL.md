---
name: ship
description: >-
  Use this skill when the user invokes /ship or asks to wrap up, clean up
  everything, merge all finished worktrees into main, verify tests/typecheck,
  prune secondary worktrees, and push to the remote repository.
---

# Ship: End-to-End Worktree Integration, Verification & Push (`/ship`)

Execute this runbook autonomously from start to finish whenever the user runs `/ship` (or says *"clean up everything and push"* after finishing work).

> **Hard Safety Invariants:**
> 1. **Never `git push` broken code:** Verification (`typecheck`, `lint`, `test` / `build`) MUST pass on `main` before pushing.
> 2. **Never `git push --force` to `main`/`master`.**
> 3. **Never discard unverified user work** (`git reset --hard`, `git checkout -- .`, `git clean -fd`) without explicit confirmation; selectively commit finished work or stash unfinished local WIP (`git stash push -u -m "ship: pre-merge WIP"`).

---

## Step 1: Audit & Reconcile All Worktrees (`worktree-sync`)

1. Run `git wt-sync` from the repository to inspect all worktrees, uncommitted changes (including on `main`), stuck Git operations, nested worktrees, detached `HEAD`s, squash-equivalents, stashes, and unmerged local branches.
2. Read and execute the full [**`worktree-sync` SKILL.md**](../worktree-sync/SKILL.md) runbook:
   - **If secondary worktrees exist (`Total trees > 1`):** Stabilize stuck states/branch placement, selectively commit finished dirty work (excluding `.env*`, logs, `node_modules/`, build junk, and nested worktrees), merge all finished branches into `main` in lowest-risk order, inspect `👀 SEMANTIC OVERLAP` files, and resolve lockfile/mechanical conflicts cleanly.
   - **If only the primary worktree exists (`Total trees == 1`):** Ensure primary is on `main`, resolve any stuck Git operations, selectively stage and commit any finished uncommitted task files on `main`, and check if any `📌 Unmerged local branches` reported by `git wt-sync` belong to the finished cohort.

---

## Step 2: Run Full Verification Gate on `main`

From the primary worktree on `main`, detect and run the project's verification suite (check `package.json`, `Cargo.toml`, `pyproject.toml`, `Makefile`, or `AGENTS.md` / `GEMINI.md` if unsure):
- Typecheck & lint (e.g., `pnpm typecheck && pnpm lint`, `cargo check`, `ruff check` / `mypy`).
- Test & build gate (e.g., `pnpm test`, `npm test`, `cargo test`, `pytest`, `go test ./...`).
- **If verification fails:** Fix integration regressions on `main`, commit the fix cleanly, and re-verify until green. If failure stems from ambiguous product requirements, **stop before pushing** and ask the user.

---

## Step 3: Prune Merged Worktrees & Restore Temporary Stashes

1. Remove all merged and verified squash-equivalent secondary worktrees and their local branches:
   ```bash
   git wt-sync --prune-merged
   ```
2. Run a sanity check (`git status --short` and `git diff --check`) to confirm `main` is clean and free of conflict markers or accidental secret/junk files.

---

## Step 4: Sync with Remote & Push `main`

1. **Check remote configuration:**
   ```bash
   git remote -v
   ```
   *(If no Git remote is configured, skip pushing and note that local integration & cleanup are complete).*
2. **Fetch & handle upstream movement safely:**
   - Check upstream tracking branch:
     ```bash
     git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>/dev/null
     ```
   - If upstream exists (e.g. `origin/main`):
     1. Run `git fetch origin`.
     2. Check if remote has new commits (`git rev-list --count HEAD..@{u}`).
     3. If remote moved ahead, run `git pull --rebase` (resolve trivial lockfile/additive conflicts if needed and re-run verification before pushing; stop and ask if non-trivial conflict occurs).
     4. Push cleanly:
        ```bash
        git push
        ```
   - If `origin` exists but `main` has no upstream set yet:
     ```bash
     git push -u origin main
     ```
3. **Restore pre-merge local WIP stash (if created in Step 1):**
   If you created a `wt-sync` / `ship` stash for unfinished local tweaks on `main`, run `git stash pop` after pushing so the user's local workspace state is restored.

---

## Step 5: Report Concise Ship Summary

Conclude with a brief summary covering:
- Branches/worktrees integrated (and any uncommitted work committed or stashed).
- Verification commands run and passed.
- Secondary worktrees and branches pruned.
- Remote push status (`origin/main` commit range pushed).
