---
name: memory
description: Manage, search, sync, or toggle the shared repository memory store (~/.agents/memories/) used across Antigravity and Pi. Triggered by /memory or when the user asks to remember a durable repo pitfall, search past session rollouts, check memory status, or force memory consolidation.
---

# Shared Repository Memory (`/memory`)

Manage the progressive-disclosure repository memory system stored at `~/.agents/memories/<workspace-slug>/` via `~/.local/bin/agent-memory`.

## Subcommands

Run the matching command via `run_command` based on the user's request (`$ARGUMENTS`):

- **Status** (`/memory` or `/memory status`):
  ```bash
  ~/.local/bin/agent-memory status
  ```
- **Search past sessions & memory** (`/memory search <query>`):
  ```bash
  ~/.local/bin/agent-memory search "<query>"
  ```
  *(Add `--all` to search across every repository instead of only the active workspace.)*
- **Audit memory staleness & git drift** (`/memory drift`):
  ```bash
  ~/.local/bin/agent-memory drift
  ```
- **Save an explicit durable note / pitfall immediately** (`/memory remember <note>`):
  ```bash
  ~/.local/bin/agent-memory remember "<concise durable technical note>"
  ```
- **Force immediate Stage-1 + Stage-2 consolidation** (`/memory sync`):
  ```bash
  ~/.local/bin/agent-memory sync --force
  ```
- **Toggle memory injection & auto-sync** (`/memory on` or `/memory off`):
  ```bash
  ~/.local/bin/agent-memory on
  ~/.local/bin/agent-memory off
  ```
- **Change consolidation model** (`/memory model <model-id>`):
  ```bash
  ~/.local/bin/agent-memory model gemini-3.8-flash-low
  ```

## Operating Rules

1. Never store secrets, tokens, credentials, or transient debugging chatter.
2. Treat `MEMORY.md` and `rollout_summaries/` as advisory heuristics — always verify claims against current repository files before acting on them.
