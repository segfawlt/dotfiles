---
name: diagnostics
description: Configure, toggle, run, or inspect logs of the Instant Post-Edit Diagnostics system (status, on, off, checker, check, logs, reset). Triggered by /diagnostics or when the user asks to toggle post-edit syntax checks, toggle a language checker, check files, or view diagnostics logs.
---

# Instant Post-Edit Diagnostics (`/diagnostics`)

Manage the sub-50ms post-edit syntax & error diagnostics hook (`~/.local/bin/agy-diagnostics`) across Lead and subagent sessions.

## CLI Subcommands

Run `~/.local/bin/agy-diagnostics` (or `agy diagnostics` in interactive shells) via `run_command`:

```bash
# View status, counters, and detected host checkers
~/.local/bin/agy-diagnostics status

# Enable or disable globally
~/.local/bin/agy-diagnostics on
~/.local/bin/agy-diagnostics off

# Toggle an individual language checker (python, ts-js, json, jsonl, toml, yaml, shell, fish, go)
~/.local/bin/agy-diagnostics checker ts-js on
~/.local/bin/agy-diagnostics checker yaml off

# Manually run fast syntax diagnostics on file(s) or a directory
~/.local/bin/agy-diagnostics check path/to/file.ts -v

# Inspect recent caught/cleared/injected diagnostic events
~/.local/bin/agy-diagnostics logs -n 30

# Reset counters, pending session files, and logs
~/.local/bin/agy-diagnostics reset
```

## How It Works

1. **`PostToolUse` (`edit_file` / `write_file`, `<50ms`):** Immediately parses the edited file (`compile()` AST for Python, `Bun.Transpiler` for TS/TSX/JSX/JS, `json` / `Bun.JSONC` for JSON & `tsconfig.json`, `tomllib` for TOML, `PyYAML` / `Bun.YAML` for YAML, `bash -n` / `fish --no-execute` for shell scripts, `gofmt -e` for Go, plus optional repo-local `ruff` / `oxlint` correctness rules). Fixes in subsequent edits clear staged errors immediately.
2. **`PreInvocation` (`<20ms`):** Injects a transient `ephemeralMessage` (`<diagnostics>...</diagnostics>`) and inline UI badge on the very next model step. Because `ephemeralMessage` vanishes after the turn, fixed typos add **zero** permanent token bloat to conversation history.
3. **`Stop` (`NO_TOOL_CALL` safety net):** Re-verifies any previously flagged file on disk before allowing turn completion, blocking once per prompt if an edited file is still syntactically broken.
