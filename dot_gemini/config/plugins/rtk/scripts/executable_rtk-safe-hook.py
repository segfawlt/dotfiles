#!/usr/bin/env python3
"""
rtk-safe-hook.py: Wraps `rtk hook antigravity` with a quote/heredoc-aware Git & Shell Guard.
- Hard-blocks (`deny`) unambiguous workspace/secret mistakes (staging real `.env` files,
  creating git worktrees outside `<repo>/.worktrees/<slug>`).
- Prompts (`ask`) with a live casualty preview (exact dirty files, unmerged commits, stash
  entries, or remote commits) before destructive git discards, force-pushes, `rm` outside
  `/tmp/`, DB drops, or direct `main` commits while secondary `.worktrees/*` are active.
- Delegates normal commands to `~/.local/bin/rtk hook antigravity`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

MAX_PREVIEW_LINES = 8

SHELL_INTERPRETERS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
SQL_CLIENTS = {"psql", "sqlite3", "mysql", "mariadb", "cockroach", "duckdb"}
COMMAND_WRAPPERS = {"sudo", "env", "command", "nohup", "time", "nice"}

SAFE_ENV_EXACT = {
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.schema",
    ".env.defaults",
    ".env.dist",
}
SAFE_ENV_SUFFIXES = (".example", ".sample", ".template", ".schema", ".dist", ".md", ".txt")

GIT_GLOBAL_VAL_FLAGS = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--super-prefix",
    "--config-env",
}
GIT_PUSH_VAL_FLAGS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}

SQL_DROP_RE = re.compile(
    r"(?i)\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)\b|TRUNCATE\s+TABLE\b|drizzle-kit\s+drop\b|prisma\s+migrate\s+reset\b)"
)
HEREDOC_START_RE = re.compile(r"<<(-?)\s*(?:'([^']*)'|\"([^\"]*)\"|\\?([A-Za-z0-9_.-]+))")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def run_git_out(cwd: Path, *args: str, timeout: float = 1.5) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        if proc.returncode == 0:
            return proc.stdout
        return None
    except Exception:
        return None


def run_git_ok(cwd: Path, *args: str, timeout: float = 1.5) -> bool:
    return run_git_out(cwd, *args, timeout=timeout) is not None


def format_preview_list(raw: str | None, empty_label: str) -> str:
    if raw is None:
        return f"\n  ({empty_label})"
    lines = [
         re.sub(r"^Would remove\s+", "", ln.strip())
        for ln in raw.splitlines()
        if ln.strip()
    ]
    if not lines:
        return f"\n  ({empty_label})"
    shown = "\n".join(f"  {ln}" for ln in lines[:MAX_PREVIEW_LINES])
    extra = f"\n  ... +{len(lines) - MAX_PREVIEW_LINES} more" if len(lines) > MAX_PREVIEW_LINES else ""
    return f"\n{shown}{extra}"


def is_secret_env_path(rel_or_abs: str) -> bool:
    name = Path(rel_or_abs.strip()).name
    if not name:
        return False
    low = name.lower()
    if low in SAFE_ENV_EXACT or low.endswith(SAFE_ENV_SUFFIXES):
        return False
    return low == ".env" or low.startswith(".env.")


def strip_and_collect_heredocs(cmd: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Strip heredoc bodies from `cmd` so multiline commit messages/files never false-trigger
    command parsers, while returning `(header_line, body)` pairs in case the header pipes
    into a shell (`bash <<EOF`) or SQL client (`psql <<EOF`).
    """
    lines = cmd.splitlines()
    kept_lines: list[str] = []
    heredocs: list[tuple[str, str]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        kept_lines.append(line)
        # Ignore heredoc markers inside single/double quotes on simple one-liners like -m "..."
        matches = list(_find_unquoted_heredocs(line))
        i += 1
        for strip_tabs, delim in matches:
            body_lines: list[str] = []
            while i < n:
                cand = lines[i]
                check = cand.lstrip("\t") if strip_tabs else cand
                if check.strip() == delim:
                    i += 1
                    break
                body_lines.append(cand)
                i += 1
            heredocs.append((line, "\n".join(body_lines)))
    return "\n".join(kept_lines), heredocs


def _find_unquoted_heredocs(line: str) -> list[tuple[bool, str]]:
    found: list[tuple[bool, str]] = []
    in_sq = False
    in_dq = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and not in_sq and i + 1 < n:
            i += 2
            continue
        if ch == "'" and not in_dq:
            in_sq = not in_sq
            i += 1
            continue
        if ch == '"' and not in_sq:
            in_dq = not in_dq
            i += 1
            continue
        if not in_sq and ch == "#" and (i == 0 or line[i - 1].isspace()):
            break
        # Allow heredocs outside quotes OR inside `$(cat <<EOF` command substitutions
        if not in_sq and line.startswith("<<", i) and not line.startswith("<<<", i):
            m = HEREDOC_START_RE.match(line, i)
            if m:
                strip_tabs = bool(m.group(1))
                delim = m.group(2) or m.group(3) or m.group(4) or ""
                if delim:
                    found.append((strip_tabs, delim))
                i = m.end()
                continue
        i += 1
    return found


def extract_subshells(text: str) -> list[str]:
    """Extract `$(...)` and backtick command substitutions outside single quotes."""
    subs: list[str] = []
    in_sq = False
    in_dq = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and not in_sq and i + 1 < n:
            i += 2
            continue
        if ch == "'" and not in_dq:
            in_sq = not in_sq
            i += 1
            continue
        if ch == '"' and not in_sq:
            in_dq = not in_dq
            i += 1
            continue
        if not in_sq and text.startswith("$(", i) and not text.startswith("$((", i):
            depth = 1
            j = i + 2
            sub_sq = False
            sub_dq = False
            while j < n and depth > 0:
                c = text[j]
                if c == "\\" and not sub_sq and j + 1 < n:
                    j += 2
                    continue
                if c == "'" and not sub_dq:
                    sub_sq = not sub_sq
                elif c == '"' and not sub_sq:
                    sub_dq = not sub_dq
                elif not sub_sq and not sub_dq:
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                j += 1
            inner = text[i + 2 : max(i + 2, j - 1)].strip()
            if inner:
                subs.append(inner)
            i = j
            continue
        if not in_sq and ch == "`":
            j = i + 1
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if text[j] == "`":
                    break
                j += 1
            inner = text[i + 1 : j].strip()
            if inner:
                subs.append(inner)
            i = j + 1
            continue
        i += 1
    return subs


def split_shell_segments(text: str) -> list[list[str]]:
    """Split shell command string into tokenized argv lists per command segment."""
    segments: list[list[str]] = []
    cur_tokens: list[str] = []
    buf: list[str] = []
    token_started = False
    in_sq = False
    in_dq = False
    i = 0
    n = len(text)

    def flush_tok() -> None:
        nonlocal token_started
        if token_started or buf:
            cur_tokens.append("".join(buf))
            buf.clear()
            token_started = False

    def flush_seg() -> None:
        flush_tok()
        if cur_tokens:
            segments.append(list(cur_tokens))
            cur_tokens.clear()

    while i < n:
        ch = text[i]
        if in_sq:
            if ch == "'":
                in_sq = False
            else:
                buf.append(ch)
            i += 1
            continue
        if in_dq:
            if ch == "\\" and i + 1 < n and text[i + 1] in {'"', "\\", "$", "`"}:
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_dq = False
            else:
                buf.append(ch)
            i += 1
            continue

        # Unquoted context
        if ch == "\\":
            if i + 1 < n:
                if text[i + 1] != "\n":
                    buf.append(text[i + 1])
                    token_started = True
                i += 2
            else:
                i += 1
            continue
        if ch == "'":
            in_sq = True
            token_started = True
            i += 1
            continue
        if ch == '"':
            in_dq = True
            token_started = True
            i += 1
            continue
        if ch == "#" and not token_started and not buf:
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch in {";", "\n"}:
            flush_seg()
            i += 1
            continue
        if ch in {"(", ")"}:
            flush_seg()
            i += 1
            continue
        if ch in {"&", "|"}:
            # Handle &&, ||, |, & (ignore >&2 / 2>&1 redirections)
            if ch == "&" and i > 0 and text[i - 1] in {">", "<"}:
                buf.append(ch)
                token_started = True
                i += 1
                continue
            flush_seg()
            if i + 1 < n and text[i + 1] == ch:
                i += 2
            else:
                i += 1
            continue
        if ch in {">", "<"}:
            # Skip redirection operator + target filename token
            flush_tok()
            while i < n and text[i] in {">", "<", "&"}:
                i += 1
            while i < n and text[i] in {" ", "\t"}:
                i += 1
            # Consume target word of redirection so `> /tmp/out` isn't mistaken for an operand
            while i < n and text[i] not in {" ", "\t", ";", "\n", "|", "&", "(", ")"}:
                if text[i] == "'":
                    i += 1
                    while i < n and text[i] != "'":
                        i += 1
                elif text[i] == '"':
                    i += 1
                    while i < n and text[i] != '"':
                        if text[i] == "\\" and i + 1 < n:
                            i += 1
                        i += 1
                elif text[i] == "\\" and i + 1 < n:
                    i += 1
                i += 1
            continue
        if ch.isspace():
            flush_tok()
            i += 1
            continue

        buf.append(ch)
        token_started = True
        i += 1

    flush_seg()
    return segments


def unwrap_command_prefix(tokens: list[str]) -> list[str]:
    """Strip leading VAR=val assignments, sudo/env/command/rtk wrappers."""
    idx = 0
    n = len(tokens)
    while idx < n:
        tok = tokens[idx]
        if ASSIGN_RE.match(tok):
            idx += 1
            continue
        base = Path(tok).name
        if base == "rtk":
            idx += 1
            if idx < n and tokens[idx] == "bypass":
                idx += 1
            continue
        if base in COMMAND_WRAPPERS:
            idx += 1
            while idx < n:
                flag = tokens[idx]
                if base == "sudo" and flag in {"-u", "-g", "-C", "-D", "-R", "-T"}:
                    idx += 2
                elif base == "env" and flag in {"-u", "-C", "-S"}:
                    idx += 2
                elif base == "env" and ASSIGN_RE.match(flag):
                    idx += 1
                elif flag == "--":
                    idx += 1
                    break
                elif flag.startswith("-"):
                    idx += 1
                else:
                    break
            continue
        break
    return tokens[idx:]


def is_safe_tmp_rm(paths: list[str]) -> bool:
    if not paths:
        return False
    for raw in paths:
        p = raw.strip()
        if not p or "$" in p or "`" in p or "*" in p or "?" in p:
            return False
        norm = os.path.normpath(p)
        if p in ("/tmp", "/tmp/") or norm == "/tmp" or not norm.startswith("/tmp/"):
            return False
    return True


def check_rm_command(argv: list[str]) -> tuple[str, str] | None:
    has_rf = False
    paths: list[str] = []
    after_dd = False
    for tok in argv[1:]:
        if after_dd:
            paths.append(tok)
        elif tok == "--":
            after_dd = True
        elif tok in {"--recursive", "--force"}:
            has_rf = True
        elif tok.startswith("-") and not tok.startswith("--"):
            if any(c in tok[1:] for c in ("r", "R", "f")):
                has_rf = True
        elif not tok.startswith("-"):
            paths.append(tok)
    if has_rf and not is_safe_tmp_rm(paths):
        preview = "\n".join(f"  {p}" for p in paths[:MAX_PREVIEW_LINES])
        return ("ask", f"Safety gate (rm outside /tmp/): confirm before deleting:\n{preview or '  (unspecified paths)'}")
    return None


def parse_git_invocation(argv: list[str], cwd: Path) -> tuple[Path, str, list[str]] | None:
    git_cwd = cwd
    i = 1
    n = len(argv)
    while i < n:
        tok = argv[i]
        if tok in GIT_GLOBAL_VAL_FLAGS:
            if tok == "-C" and i + 1 < n:
                cand = os.path.expanduser(argv[i + 1])
                git_cwd = (git_cwd / cand).resolve(strict=False)
            i += 2
            continue
        if tok.startswith("-C") and len(tok) > 2:
            cand = os.path.expanduser(tok[2:])
            git_cwd = (git_cwd / cand).resolve(strict=False)
            i += 1
            continue
        if any(tok.startswith(f"{f}=") for f in GIT_GLOBAL_VAL_FLAGS if f.startswith("--")):
            i += 1
            continue
        if tok == "--":
            i += 1
            break
        if tok.startswith("-"):
            i += 1
            continue
        return (git_cwd, tok, argv[i + 1 :])
    return None


def resolve_primary_repo_root(git_cwd: Path) -> Path | None:
    common = run_git_out(git_cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common:
        cpath = Path(common.strip()).resolve(strict=False)
        if cpath.name == ".git":
            return cpath.parent
    top = run_git_out(git_cwd, "rev-parse", "--show-toplevel")
    if top:
        return Path(top.strip()).resolve(strict=False)
    return None


def preview_git_discard(git_cwd: Path, sub: str, args: list[str]) -> str:
    if sub == "stash":
        sub_op = args[0] if args else ""
        stash_all = run_git_out(git_cwd, "stash", "list")
        if sub_op == "clear":
            return format_preview_list(stash_all, "no stash entries")
        ref_arg = next((a for a in args[1:] if not a.startswith("-")), "0")
        ref = f"stash@{{{ref_arg}}}" if ref_arg.isdigit() else ref_arg
        matched = (
            "\n".join(ln for ln in (stash_all or "").splitlines() if ln.startswith(f"{ref}:"))
            if stash_all is not None
            else None
        )
        return format_preview_list(matched, f"no entry matching {ref}")

    if sub == "clean":
        clean_args: list[str] = []
        for a in args:
            if a in {"--force", "--interactive", "--quiet", "-f", "-i", "-q"}:
                continue
            if a.startswith("-") and not a.startswith("--"):
                stripped = "-" + re.sub(r"[fiq]", "", a[1:])
                if stripped != "-":
                    clean_args.append(stripped)
            else:
                clean_args.append(a)
        out = run_git_out(git_cwd, "clean", "-n", *clean_args)
        return format_preview_list(out, "nothing untracked to remove")

    # reset / restore / checkout
    dd = args.index("--") if "--" in args else -1
    if dd != -1:
        paths = args[dd + 1 :]
    elif sub == "restore":
        paths = [
            a
            for idx, a in enumerate(args)
            if not a.startswith("-") and (idx == 0 or args[idx - 1] not in {"-s", "--source"})
        ]
    elif sub == "checkout":
        paths = [
            a for a in args if not a.startswith("-") and (git_cwd / a).exists()
        ]
    else:
        paths = []

    status_cmd = ["status", "--porcelain", "--untracked-files=no"]
    if paths:
        status_cmd.extend(["--", *paths])
    dirty = format_preview_list(run_git_out(git_cwd, *status_cmd), "no uncommitted tracked changes")

    if sub == "reset":
        operands = [a for a in (args[:dd] if dd != -1 else args) if not a.startswith("-")]
        ref = operands[0] if operands else None
        if ref and ref != "HEAD":
            dropped = run_git_out(git_cwd, "log", "--oneline", "--end-of-options", f"{ref}..HEAD")
            if dropped and dropped.strip():
                commits = format_preview_list(dropped, "")
                return f"{dirty}\n  Commits leaving HEAD:{commits}"
    return dirty


def preview_force_push(git_cwd: Path, args: list[str]) -> tuple[str, bool]:
    positional: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in GIT_PUSH_VAL_FLAGS:
            i += 2
            continue
        if any(a.startswith(f"{f}=") for f in GIT_PUSH_VAL_FLAGS if f.startswith("--")):
            i += 1
            continue
        if not a.startswith("-"):
            positional.append(a)
        i += 1

    remote = positional[0] if positional else ""
    spec = positional[1] if len(positional) > 1 else ""
    clean_spec = spec.lstrip("+")
    if ":" in clean_spec:
        src, dst = clean_spec.split(":", 1)
    else:
        src, dst = clean_spec, clean_spec

    branch = (dst or src or "").removeprefix("refs/heads/")
    if not branch or branch == "HEAD":
        cur = run_git_out(git_cwd, "symbolic-ref", "--quiet", "--short", "HEAD")
        branch = (cur or "HEAD").strip()

    is_main = branch in {"main", "master"}
    target = f"refs/remotes/{remote}/{branch}" if remote else "@{push}"
    label = f"{remote}/{branch}" if remote else branch

    if not run_git_ok(git_cwd, "rev-parse", "--verify", "-q", target):
        return (f"\n  (no fetched ref for {label} to compare)", is_main)

    log_out = run_git_out(git_cwd, "log", "--oneline", "--end-of-options", f"{src or 'HEAD'}..{target}")
    return (f"\n  Remote {label} loses (as of last fetch):{format_preview_list(log_out, '0 commits lacking locally')}", is_main)


def check_git_command(git_cwd: Path, sub: str, args: list[str]) -> tuple[str, str] | None:
    # 1. Hard-block staging or committing real .env files
    if sub == "add":
        if not any(a in {"-n", "--dry-run"} for a in args):
            dd = args.index("--") if "--" in args else -1
            cands = args[dd + 1 :] if dd != -1 else [a for a in args if not a.startswith("-")]
            bad_env = [p for p in cands if is_secret_env_path(p)]
            if bad_env:
                return (
                    "deny",
                    f"Blocked git add on secret env file(s): {', '.join(bad_env)}. Keep real .env files unstaged.",
                )
        return None

    if sub == "commit":
        if any(a in {"--dry-run", "--short", "--porcelain"} for a in args):
            return None
        staged_out = run_git_out(git_cwd, "diff", "--cached", "--name-only", "--diff-filter=ACMR") or ""
        staged = [ln.strip() for ln in staged_out.splitlines() if ln.strip()]
        has_all = any(
            a == "--all" or (a.startswith("-") and not a.startswith("--") and "a" in a[1:] and a != "--amend")
            for a in args
        )
        if has_all:
            wt_out = run_git_out(git_cwd, "diff", "--name-only", "--diff-filter=ACMR") or ""
            staged.extend(ln.strip() for ln in wt_out.splitlines() if ln.strip())
        bad_env = sorted({p for p in staged if is_secret_env_path(p)})
        if bad_env:
            return (
                "deny",
                f"Blocked git commit: secret file staged ({', '.join(bad_env)}). Unstage first via `git restore --staged {' '.join(bad_env)}`.",
            )

        # Prompt on direct main/master commit ONLY when active secondary worktrees exist (and not finishing a merge)
        cur_branch = (run_git_out(git_cwd, "symbolic-ref", "--quiet", "--short", "HEAD") or "").strip()
        if cur_branch in {"main", "master"}:
            git_dir = (run_git_out(git_cwd, "rev-parse", "--git-dir") or "").strip()
            is_merge = bool(git_dir and (git_cwd / git_dir / "MERGE_HEAD").exists())
            if not is_merge:
                wt_raw = run_git_out(git_cwd, "worktree", "list", "--porcelain") or ""
                wt_paths = [
                    ln.removeprefix("worktree ").strip()
                    for ln in wt_raw.splitlines()
                    if ln.startswith("worktree ")
                ]
                if len(wt_paths) > 1:
                    sec = ", ".join(Path(p).name for p in wt_paths[1:4])
                    return (
                        "ask",
                        f"Direct commit on `{cur_branch}` while secondary worktrees are active ({sec}). Confirm if intentional (or commit on the feature worktree first so `git wt-sync` stays clean).",
                    )
        return None

    # 2. Hard-block `git worktree add` outside `<repo>/.worktrees/<slug>`
    if sub == "worktree" and args:
        wt_sub = args[0]
        wt_args = args[1:]
        if wt_sub == "add":
            pos: list[str] = []
            i = 0
            after_dd = False
            while i < len(wt_args):
                a = wt_args[i]
                if after_dd:
                    pos.append(a)
                elif a == "--":
                    after_dd = True
                elif a in {"-b", "-B", "--reason"}:
                    i += 1
                elif not a.startswith("-"):
                    pos.append(a)
                i += 1
            if pos:
                wt_target = (git_cwd / os.path.expanduser(pos[0])).resolve(strict=False)
                repo_root = resolve_primary_repo_root(git_cwd)
                if repo_root is not None:
                    allowed_dir = (repo_root / ".worktrees").resolve(strict=False)
                    if wt_target == allowed_dir or allowed_dir not in wt_target.parents:
                        return (
                            "deny",
                            f"Blocked `git worktree add {pos[0]}`: worktrees must live inside `{repo_root}/.worktrees/<slug>` so files stay inside Antigravity's workspace sandbox.",
                        )
            return None

        if wt_sub == "remove":
            is_force = any(
                a == "--force" or (a.startswith("-") and not a.startswith("--") and "f" in a[1:])
                for a in wt_args
            )
            if is_force:
                targets = [a for a in wt_args if not a.startswith("-")]
                wt_dir = (git_cwd / os.path.expanduser(targets[0])).resolve(strict=False) if targets else None
                preview = (
                    format_preview_list(run_git_out(wt_dir, "status", "--porcelain"), "clean worktree")
                    if wt_dir and wt_dir.is_dir()
                    else "\n  (worktree status unavailable)"
                )
                return ("ask", f"Safety gate (git worktree remove --force): confirm before removing worktree:{preview}")
        return None

    # 3. Git discards with exact casualty previews
    if sub == "reset":
        if any(a in {"--hard", "--merge"} for a in args):
            preview = preview_git_discard(git_cwd, "reset", args)
            return ("ask", f"Safety gate (git reset): confirm before discarding work:{preview}")
        return None

    if sub == "restore":
        has_staged = any(
            a == "--staged" or (a.startswith("-") and not a.startswith("--") and "S" in a[1:])
            for a in args
        )
        has_worktree = any(
            a == "--worktree" or (a.startswith("-") and not a.startswith("--") and "W" in a[1:])
            for a in args
        )
        # `git restore --staged <file>` without `-W` only unstages and loses zero working-tree edits
        if not has_staged or has_worktree:
            preview = preview_git_discard(git_cwd, "restore", args)
            return ("ask", f"Safety gate (git restore): confirm before discarding working-tree edits:{preview}")
        return None

    if sub == "checkout":
        has_branch_create = any(a in {"-b", "-B", "--orphan", "-d", "--detach"} for a in args)
        if not has_branch_create:
            has_dd = "--" in args
            dd_idx = args.index("--") if has_dd else -1
            dd_paths = args[dd_idx + 1 :] if has_dd else []
            non_flags = [a for a in args if not a.startswith("-")]
            is_dot = "." in non_flags
            # `git checkout <file>` where <file> is dirty on disk and not a valid rev/branch
            existing_file_discard = (
                len(non_flags) == 1
                and (git_cwd / non_flags[0]).is_file()
                and not run_git_ok(git_cwd, "rev-parse", "--verify", "-q", f"refs/heads/{non_flags[0]}")
            )
            if (has_dd and dd_paths) or is_dot or existing_file_discard:
                preview = preview_git_discard(git_cwd, "checkout", args)
                return ("ask", f"Safety gate (git checkout discard): confirm before discarding working-tree edits:{preview}")
        return None

    if sub == "clean":
        has_dry = any(
            a == "--dry-run" or (a.startswith("-") and not a.startswith("--") and "n" in a[1:])
            for a in args
        )
        has_force = any(
            a == "--force" or (a.startswith("-") and not a.startswith("--") and "f" in a[1:])
            for a in args
        )
        if has_force and not has_dry:
            preview = preview_git_discard(git_cwd, "clean", args)
            return ("ask", f"Safety gate (git clean): confirm before deleting untracked files:{preview}")
        return None

    if sub == "stash" and args and args[0] in {"drop", "clear"}:
        preview = preview_git_discard(git_cwd, "stash", args)
        return ("ask", f"Safety gate (git stash {args[0]}): confirm before dropping stash:{preview}")

    # 4. Git force-push (including +refspec) with remote loss preview
    if sub == "push":
        if any(a in {"-n", "--dry-run"} for a in args):
            return None
        has_force_flag = any(
            a in {"--force", "--force-with-lease", "--force-if-includes"}
            or a.startswith("--force-with-lease=")
            or (a.startswith("-") and not a.startswith("--") and "f" in a[1:])
            for a in args
        )
        # Check leading `+` on refspec arguments (after remote name)
        pos_args: list[str] = []
        i = 0
        while i < len(args):
            a = args[i]
            if a in GIT_PUSH_VAL_FLAGS:
                i += 2
                continue
            if not a.startswith("-"):
                pos_args.append(a)
            i += 1
        has_plus_refspec = any(spec.startswith("+") for spec in pos_args[1:])
        if has_force_flag or has_plus_refspec:
            preview, is_main = preview_force_push(git_cwd, args)
            main_warn = " [WARNING: target is main/master!]" if is_main else ""
            return ("ask", f"Safety gate (git force push){main_warn}: confirm before overwriting remote:{preview}")
        return None

    # 5. Git branch -D with unmerged commits preview
    if sub == "branch":
        has_force_del = any(
            a == "-D"
            or (a.startswith("-") and not a.startswith("--") and "D" in a[1:])
            for a in args
        ) or (
            any(a in {"-d", "--delete"} for a in args)
            and any(a in {"-f", "--force"} for a in args)
        )
        if has_force_del:
            branches = [a for a in args if not a.startswith("-")]
            unmerged_notes: list[str] = []
            for br in branches[:4]:
                out = run_git_out(git_cwd, "log", "--oneline", "--end-of-options", f"HEAD..{br}")
                if out and out.strip():
                    cnt = len([ln for ln in out.splitlines() if ln.strip()])
                    first = out.splitlines()[0].strip()
                    unmerged_notes.append(f"  {br}: {cnt} unmerged commit(s) (latest: {first})")
                else:
                    unmerged_notes.append(f"  {br}: 0 unmerged commits vs HEAD")
            detail = "\n" + "\n".join(unmerged_notes) if unmerged_notes else ""
            return ("ask", f"Safety gate (git branch -D): confirm before force-deleting branch:{detail}")
        return None

    return None


def check_non_git_segment(argv: list[str]) -> tuple[str, str] | None:
    if not argv:
        return None
    prog = Path(argv[0]).name

    if prog == "rm":
        return check_rm_command(argv)

    if prog == "find" and "-delete" in argv[1:]:
        target = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else "."
        if not is_safe_tmp_rm([target]):
            return ("ask", f"Safety gate (find -delete on {target}): confirm before deleting files.")

    if prog == "docker" and len(argv) >= 3:
        if argv[1] == "system" and argv[2] == "prune":
            return ("ask", "Safety gate (docker system prune): confirm before pruning Docker resources.")
        if argv[1] == "volume" and argv[2] in {"rm", "prune"}:
            return ("ask", f"Safety gate (docker volume {argv[2]}): confirm before removing Docker volumes.")

    if prog.startswith("mkfs"):
        return ("ask", f"Safety gate ({prog}): confirm before formatting filesystem.")

    if prog == "dd" and any(a.startswith("if=") for a in argv[1:]):
        return ("ask", "Safety gate (dd): confirm before low-level block write.")

    if prog == "chmod":
        has_rec = any(a in {"-R", "--recursive"} for a in argv[1:])
        if has_rec and "777" in argv[1:]:
            return ("ask", "Safety gate (chmod -R 777): confirm before recursive world-writable permissions.")

    if prog in {"npx", "pnpm", "bunx", "yarn", "drizzle-kit", "prisma"}:
        joined = " ".join(argv)
        if SQL_DROP_RE.search(joined):
            return ("ask", "Safety gate (ORM drop/reset): confirm before destructive database schema reset.")

    if prog in SQL_CLIENTS:
        joined = " ".join(argv[1:])
        if SQL_DROP_RE.search(joined):
            return ("ask", f"Safety gate ({prog} SQL drop/truncate): confirm before destructive SQL statement.")

    # Inline subshell execution: `bash -c "..."`, `sh -c "..."`
    if prog in SHELL_INTERPRETERS:
        for idx, tok in enumerate(argv[1:], start=1):
            if tok == "-c" and idx + 1 < len(argv):
                return evaluate_command(argv[idx + 1], Path.cwd())

    return None


def evaluate_command(cmd: str, initial_cwd: Path) -> tuple[str, str] | None:
    if not cmd or not cmd.strip():
        return None

    stripped_cmd, heredocs = strip_and_collect_heredocs(cmd)
    segments = split_shell_segments(stripped_cmd)

    # Also inspect `$(...)` and backtick command substitutions
    for sub_cmd in extract_subshells(stripped_cmd):
        res = evaluate_command(sub_cmd, initial_cwd)
        if res is not None:
            return res

    cwd = initial_cwd
    severity_hit: tuple[str, str] | None = None

    for raw_tokens in segments:
        argv = unwrap_command_prefix(raw_tokens)
        if not argv:
            continue

        prog = Path(argv[0]).name

        # Track working directory changes (`cd <dir>`) across chained segments
        if prog == "cd":
            target = argv[1] if len(argv) > 1 else os.path.expanduser("~")
            if target != "-" and "$" not in target and "`" not in target:
                cwd = (cwd / os.path.expanduser(target)).resolve(strict=False)
            continue

        res: tuple[str, str] | None = None
        if prog == "git":
            parsed = parse_git_invocation(argv, cwd)
            if parsed is not None:
                git_cwd, sub, git_args = parsed
                res = check_git_command(git_cwd, sub, git_args)
        else:
            res = check_non_git_segment(argv)

        if res is not None:
            if res[0] == "deny":
                return res
            if severity_hit is None:
                severity_hit = res

    # Inspect heredoc bodies ONLY when fed to an interpreter (`bash <<EOF`) or SQL client (`psql <<EOF`)
    for header, body in heredocs:
        if not body.strip():
            continue
        header_segs = split_shell_segments(header)
        for h_tokens in header_segs:
            h_argv = unwrap_command_prefix(h_tokens)
            if not h_argv:
                continue
            h_prog = Path(h_argv[0]).name
            if h_prog in SHELL_INTERPRETERS:
                res = evaluate_command(body, cwd)
                if res is not None:
                    if res[0] == "deny":
                        return res
                    if severity_hit is None:
                        severity_hit = res
            elif h_prog in SQL_CLIENTS and SQL_DROP_RE.search(body):
                if severity_hit is None:
                    severity_hit = ("ask", f"Safety gate ({h_prog} heredoc SQL drop/truncate): confirm before destructive SQL.")

    return severity_hit


def resolve_initial_cwd(payload: dict[str, Any]) -> Path:
    wpaths = payload.get("workspacePaths")
    if isinstance(wpaths, list) and wpaths:
        cand = Path(str(wpaths[0])).expanduser()
        if cand.is_dir():
            return cand.resolve(strict=False)
    return Path.cwd()


def main() -> int:
    raw = sys.stdin.read()
    if os.environ.get("AGY_HOOK_INTERNAL") == "1":
        print(json.dumps({"decision": "allow"}))
        return 0

    try:
        payload = json.loads(raw or "{}")
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return 0

    cmd = str(((payload.get("toolCall") or {}).get("args") or {}).get("CommandLine") or "")
    initial_cwd = resolve_initial_cwd(payload)
    verdict = evaluate_command(cmd, initial_cwd)
    if verdict is not None:
        decision, reason = verdict
        print(json.dumps({"decision": decision, "reason": reason}))
        return 0

    rtk_bin = str(Path.home() / ".local" / "bin" / "rtk")
    if not os.path.isfile(rtk_bin):
        rtk_bin = shutil.which("rtk") or ""
    if not rtk_bin:
        print(json.dumps({"decision": "allow"}))
        return 0

    try:
        proc = subprocess.run(
            [rtk_bin, "hook", "antigravity"],
            input=raw,
            capture_output=True,
            text=True,
            timeout=8,
        )
        out = proc.stdout.strip()
        if proc.returncode == 0 and out:
            print(out)
            return 0
    except Exception:
        pass

    print(json.dumps({"decision": "allow"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
