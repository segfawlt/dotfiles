#!/usr/bin/env python3
"""
rtk-safe-hook.py: Destructive Command Safety Gate & RTK Proxy for Antigravity (`agy`).
- Protects against unprompted data-loss commands (force push, reset --hard, clean -f,
  discarding restore/checkout, stash drop/clear, worktree sandbox escapes, staged .env secrets).
- Injects exact casualty previews (modified files or remote commits lost) into user confirmation.
- Strips commit messages and heredocs to eliminate false-positive safety prompts.
- Delegates all safe shell commands directly to `rtk hook antigravity`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

COMMIT_MSG_RE = re.compile(
    r"(?:-m|--message)(?:\s+|=)(?:\"(?:[^\"\\]|\\.)*\"|\x27(?:[^\x27\\]|\\.)*\x27)"
)
HEREDOC_RE = re.compile(r"<<-?\s*[\x27\"]?([A-Za-z0-9_]+)[\x27\"]?[\s\S]*?\n\s*\1\b")
ECHO_MSG_RE = re.compile(
    r"\b(?:echo|printf)\s+(?:\"(?:[^\"\\]|\\.)*\"|\x27(?:[^\x27\\]|\\.)*\x27)"
)

DESTRUCTIVE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("git reset --hard", re.compile(r"\bgit\b[^\n;|&]*\breset\s+--hard\b")),
    (
        "git force push",
        re.compile(
            r"\bgit\b[^\n;|&]*\bpush\b[^\n;|&]*(?:--force(?:-with-lease)?|(?:\s|^)-[a-zA-Z]*f\b|(?:\s|^)\+[a-zA-Z0-9_\-./:]+)"
        ),
    ),
    ("git clean -f", re.compile(r"\bgit\b[^\n;|&]*\bclean\b[^\n;|&]*-[A-Za-z]*f")),
    ("git branch -D", re.compile(r"\bgit\b[^\n;|&]*\bbranch\b[^\n;|&]*\s-D\b")),
    ("git stash drop/clear", re.compile(r"\bgit\b[^\n;|&]*\bstash\b[^\n;|&]*\b(?:drop|clear)\b")),
    (
        "SQL/ORM destructive drop/reset",
        re.compile(
            r"(?i)\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE|drizzle-kit\s+drop|prisma\s+migrate\s+reset)\b"
        ),
    ),
    (
        "Docker volume/system prune",
        re.compile(r"\bdocker\s+(?:system\s+prune|volume\s+(?:rm|prune))\b"),
    ),
    (
        "Low-level disk/perm mutation",
        re.compile(r"\b(?:mkfs(?:\.\w+)?|dd\s+if=|chmod\s+-R\s+777)\b"),
    ),
]

RM_RF_RE = re.compile(
    r"(?:^|[;&|]\s*|\bsudo\s+)rm\s+(?:-[A-Za-z]*[rf][A-Za-z]*\s+|--(?:recursive|force)\s+)+(.+)"
)

ENV_SECRET_RE = re.compile(r"(?:^|/)\.env(?:\.[a-zA-Z0-9_\-]+)*$")
ENV_SAFE_SUFFIXES = (".example", ".sample", ".template", ".schema", ".dist", ".defaults")


def sanitize_command(cmd: str) -> str:
    s = HEREDOC_RE.sub("<<EOF...EOF", cmd)
    s = COMMIT_MSG_RE.sub("-m ''", s)
    s = ECHO_MSG_RE.sub("echo ''", s)
    return s


def is_safe_tmp_rm(rest: str) -> bool:
    if any(sep in rest for sep in (";", "&&", "||", "|", "`", "$(")):
        return False
    tokens = [t.strip("'\"") for t in rest.split() if not t.startswith("-")]
    if not tokens:
        return False
    for tok in tokens:
        if ".." in tok or tok in ("/tmp", "/tmp/"):
            return False
        if not tok.startswith("/tmp/"):
            return False
    return True


def is_git_restore_destructive(cmd_segment: str) -> bool:
    if not re.search(r"\bgit\b[^\n;|&]*\brestore\b", cmd_segment):
        return False
    has_staged = bool(re.search(r"\b--staged\b|(?:\s|^)-[a-zA-Z]*S\b", cmd_segment))
    has_worktree = bool(re.search(r"\b--worktree\b|(?:\s|^)-[a-zA-Z]*W\b", cmd_segment))
    if has_staged and not has_worktree:
        return False
    return True


def check_worktree_add(cmd: str) -> str | None:
    m = re.search(r"\bgit\b[^\n;|&]*\bworktree\s+add\b(.*)", cmd)
    if not m:
        return None
    raw_tokens = m.group(1).strip().split()
    path_token = None
    skip_next = False
    for t in raw_tokens:
        if skip_next:
            skip_next = False
            continue
        if t in ("-b", "-B"):
            skip_next = True
            continue
        if t.startswith(("-b", "-B")):
            continue
        if t.startswith("-"):
            continue
        path_token = t.strip("'\"")
        break
    if path_token:
        if ".worktrees/" not in path_token and not path_token.endswith(".worktrees"):
            return (
                f"git worktree outside .worktrees/<slug> ('{path_token}'). "
                f"Antigravity sandbox requires worktrees to live in .worktrees/ so file tools are not blocked."
            )
    return None


def resolve_target_repo(cmd: str, workspace_paths: list[str]) -> Path:
    m_c = re.search(r"""\bgit\s+-C\s+["']?([^\s;&|"')]+)""", cmd)
    if m_c:
        p = Path(m_c.group(1)).expanduser()
        if p.is_dir():
            return p
    m_cd = re.search(r"""(?:^|[;&|]\s*)\bcd\s+["']?([^\s;&|"')]+)""", cmd)
    if m_cd:
        p = Path(m_cd.group(1)).expanduser()
        if p.is_dir():
            return p
    for wp in workspace_paths:
        p = Path(wp).expanduser()
        if p.is_dir():
            return p
    return Path.cwd()


def check_staged_env_secrets(repo_dir: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if proc.returncode != 0:
            return []
        found: list[str] = []
        for line in proc.stdout.splitlines():
            name = line.strip()
            if not name:
                continue
            lower = name.lower()
            if any(lower.endswith(sfx) for sfx in ENV_SAFE_SUFFIXES):
                continue
            if ENV_SECRET_RE.search(lower):
                found.append(name)
        return found
    except Exception:
        return []


def inspect_casualties(repo_dir: Path, label: str, cmd: str) -> str:
    lines: list[str] = []
    try:
        if "clean" in label:
            flags = ["-n"]
            if "-x" in cmd:
                flags.append("-x")
            if "-d" in cmd:
                flags.append("-d")
            proc = subprocess.run(
                ["git", "-C", str(repo_dir), "clean", *flags],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            raw = [
                l.strip().replace("Would remove ", "")
                for l in proc.stdout.splitlines()
                if l.strip()
            ]
            if raw:
                lines.append(
                    "Untracked files to be deleted:\n  • "
                    + "\n  • ".join(raw[:8])
                    + (f"\n  ... ({len(raw) - 8} more)" if len(raw) > 8 else "")
                )
        elif "reset" in label or "discard" in label or "restore" in label:
            proc = subprocess.run(
                ["git", "-C", str(repo_dir), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            raw = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
            if raw:
                lines.append(
                    "Uncommitted modifications to be discarded:\n  • "
                    + "\n  • ".join(raw[:8])
                    + (f"\n  ... ({len(raw) - 8} more)" if len(raw) > 8 else "")
                )
            if "reset" in label and "--hard" in cmd:
                m_ref = re.search(r"\breset\s+--hard\s+([^\s;&|]+)", cmd)
                target_ref = m_ref.group(1) if m_ref else None
                if target_ref and target_ref != "HEAD":
                    log_proc = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repo_dir),
                            "log",
                            "--oneline",
                            "-n",
                            "8",
                            f"{target_ref}..HEAD",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=1.5,
                    )
                    commits = [l.strip() for l in log_proc.stdout.splitlines() if l.strip()]
                    if commits:
                        lines.append(
                            f"Commits leaving branch ({len(commits)}+):\n  • "
                            + "\n  • ".join(commits)
                        )
        elif "stash" in label:
            proc = subprocess.run(
                ["git", "-C", str(repo_dir), "stash", "list"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            stashes = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
            if stashes:
                lines.append("Stashes to be dropped:\n  • " + "\n  • ".join(stashes[:5]))
        elif "push" in label:
            proc = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_dir),
                    "log",
                    "--format=%h %s",
                    "-n",
                    "6",
                    "HEAD..@{push}",
                ],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            lost = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
            if lost:
                lines.append(
                    "Remote commits to be dropped (as of last fetch):\n  • " + "\n  • ".join(lost)
                )
    except Exception:
        pass

    return "\n\n".join(lines)


def check_destructive(cmd: str, repo_dir: Path) -> tuple[str, str] | None:
    sanitized = sanitize_command(cmd)

    # 1. Staged .env check on commit
    if re.search(r"\bgit\b[^\n;|&]*\bcommit\b", sanitized):
        staged_env = check_staged_env_secrets(repo_dir)
        if staged_env:
            return (
                "staged .env secret file",
                f"Secret file(s) staged for commit:\n  • "
                + "\n  • ".join(staged_env)
                + "\nUnstage before committing ('git restore --staged <file>') unless explicitly intended.",
            )

    # 2. Worktree add path check
    wt_issue = check_worktree_add(sanitized)
    if wt_issue:
        return (wt_issue, "")

    # 3. Git restore destructive check
    if is_git_restore_destructive(sanitized):
        casualties = inspect_casualties(repo_dir, "restore", sanitized)
        return ("git restore working tree", casualties)

    # 4. Checkout discard
    if re.search(r"\bgit\b[^\n;|&]*\bcheckout\s+--\s+\S+", sanitized):
        casualties = inspect_casualties(repo_dir, "discard", sanitized)
        return ("git checkout -- (discard)", casualties)

    # 5. Destructive rules table
    for label, pat in DESTRUCTIVE_RULES:
        if pat.search(sanitized):
            casualties = inspect_casualties(repo_dir, label, sanitized)
            return (label, casualties)

    # 6. rm -rf outside /tmp/
    m = RM_RF_RE.search(sanitized)
    if m and not is_safe_tmp_rm(m.group(1)):
        return ("rm -rf outside /tmp/", "")

    return None


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
    workspace_paths = payload.get("workspacePaths") or []
    repo_dir = resolve_target_repo(cmd, workspace_paths)

    match_result = check_destructive(cmd, repo_dir)
    if match_result:
        label, casualties = match_result
        if casualties:
            reason = (
                f"Safety gate ({label}):\n{casualties}\nConfirm before running destructive command."
            )
        else:
            reason = f"Safety gate ({label}): confirm before running destructive command."
        print(json.dumps({"decision": "ask", "reason": reason}))
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
