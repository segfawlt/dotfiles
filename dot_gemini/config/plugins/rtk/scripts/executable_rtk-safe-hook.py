#!/usr/bin/env python3
"""
rtk-safe-hook.py: Wraps official `rtk hook antigravity` with a Destructive Command Safety Gate.
- Destructive shell/git/db commands return `{"decision": "ask", ...}` instead of RTK's blanket `"allow"`.
- Normal commands delegate directly to `/home/domixi/.local/bin/rtk hook antigravity`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DESTRUCTIVE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("git reset --hard", re.compile(r"\bgit\b[^\n;|&]*\breset\s+--hard\b")),
    ("git force push", re.compile(r"\bgit\b[^\n;|&]*\bpush\b[^\n;|&]*(?:--force(?:-with-lease)?|\s-f(?:\s|$))")),
    ("git clean -f", re.compile(r"\bgit\b[^\n;|&]*\bclean\b[^\n;|&]*-[A-Za-z]*f")),
    ("git discard working tree", re.compile(r"\bgit\b[^\n;|&]*\b(?:checkout\s+--\s+\.|restore\s+(?:--worktree\s+)?\.)(?:\s|$)")),
    ("git branch -D", re.compile(r"\bgit\b[^\n;|&]*\bbranch\b[^\n;|&]*\s-D\b")),
    ("SQL/ORM destructive drop/reset", re.compile(r"(?i)\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE|drizzle-kit\s+drop|prisma\s+migrate\s+reset)\b")),
    ("Docker volume/system prune", re.compile(r"\bdocker\s+(?:system\s+prune|volume\s+(?:rm|prune))\b")),
    ("Low-level disk/perm mutation", re.compile(r"\b(?:mkfs(?:\.\w+)?|dd\s+if=|chmod\s+-R\s+777)\b")),
]

RM_RF_RE = re.compile(r"(?:^|[;&|]\s*|\bsudo\s+)rm\s+(?:-[A-Za-z]*[rf][A-Za-z]*\s+|--(?:recursive|force)\s+)+(.+)")


def is_safe_tmp_rm(rest: str) -> bool:
    # Only allow unprompted rm -rf when every target is explicitly inside /tmp/ without traversal or chaining
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


def check_destructive(cmd: str) -> str | None:
    for label, pat in DESTRUCTIVE_RULES:
        if pat.search(cmd):
            return label
    m = RM_RF_RE.search(cmd)
    if m and not is_safe_tmp_rm(m.group(1)):
        return "rm -rf outside /tmp/"
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
    matched = check_destructive(cmd)
    if matched:
        print(
            json.dumps(
                {
                    "decision": "ask",
                    "reason": f"Safety gate ({matched}): confirm before running destructive command.",
                }
            )
        )
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
