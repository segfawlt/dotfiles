# Instant Post-Edit Diagnostics (`diagnostics` v1.0.0)

OMP-style immediate post-edit syntax & parse feedback for Antigravity (`agy`), built natively on Antigravity's hook lifecycle with **zero conversation token bloat**.

## Architecture

- **`PostToolUse` (`edit_file|write_file`, `<50ms`):** Runs in-memory / native-speed syntax checks on the touched file and stages broken files in `~/.agents/diagnostics/pending/<cid>.json`. If a subsequent edit fixes the file, staged errors are cleared immediately.
- **`PreInvocation` (`<20ms`):** Pops staged errors, re-verifies on disk, and injects a transient `ephemeralMessage` (`<diagnostics>...</diagnostics>`) + concise inline UI badge. Transient `ephemeralMessage` blocks disappear once the turn ends.
- **`Stop` (`NO_TOOL_CALL` safety net):** Prevents finishing a turn while a file edited in the session still fails syntax parsing on disk (max 1 continuation per user prompt).

## Supported Languages & Checkers

| Checker | Extensions / Shebangs | Engine |
| :--- | :--- | :--- |
| `python` | `.py`, `.pyi`, `#!...python` | Python `compile()` AST (`<1ms`) + optional `ruff` (`E9,F63,F7,F82`) |
| `ts-js` | `.ts`, `.tsx`, `.mts`, `.cts`, `.jsx`, `.js`, `.mjs`, `.cjs`, `#!...bun\|node` | `Bun.Transpiler` (`~12ms`) + optional repo-local `oxlint` correctness |
| `json` | `.json`, `.jsonc`, `tsconfig*.json`, `.vscode/*.json` | Python `json.loads` (`<1ms`) + `Bun.JSONC.parse` for JSONC |
| `jsonl` | `.jsonl`, `.ndjson` | Line-by-line `json.loads` (`<3ms`) |
| `toml` | `.toml` | Python `tomllib.loads` (`<1ms`) |
| `yaml` | `.yaml`, `.yml` | `PyYAML` (`safe_load_all`) or `Bun.YAML.parse` |
| `shell` | `.sh`, `.bash`, `.zsh`, `#!...sh\|bash\|zsh` | `bash -n` / `sh -n` + optional `shellcheck -S error` |
| `fish` | `.fish`, `#!...fish` | `fish --no-execute` (`<12ms`) |
| `go` | `.go` | `gofmt -e` (when installed) |

## Usage

```bash
agy diagnostics status
agy diagnostics check src/
agy diagnostics logs -n 30
agy diagnostics checker yaml off
agy diagnostics off
```
