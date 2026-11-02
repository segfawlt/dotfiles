# Playwright Browser & UI Audit Plugin (`playwright`)

Packages `@playwright/mcp` (Chromium extension bridge) and `/ui-flaw-scan` into an on-demand plugin so backend/CLI sessions do not boot Chromium MCP or carry 25 `browser_*` tool schemas.

## Toggle Commands

```bash
# Enable before a frontend / UI testing session:
agy plugin enable playwright

# Disable again when done:
agy plugin disable playwright
```
(Or toggle interactively via `/plugin` inside `agy`.)
