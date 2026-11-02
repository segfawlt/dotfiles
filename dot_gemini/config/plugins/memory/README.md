# Shared Repo Memory Plugin (`memory`)

Progressive-disclosure, 2-stage consolidated repository memory shared between **Antigravity (`agy`)** and **Pi (`pi`)** under `~/.agents/memories/<workspace-slug>/`.

- **Startup (`SessionStart`)**: Injects compact `memory_summary.md` (~280 tokens) + file pointers once per session (100% prompt-cache safe).
- **On-Demand**: Full `MEMORY.md`, auto-extracted `skills/<name>/SKILL.md`, and FTS5 BM25 rollout search (`agy memory search "<query>"`).
- **Detached Consolidation**: Idle finished transcripts from both `agy` and `pi` are distilled in the background via `~/.local/bin/agent-memory`.
