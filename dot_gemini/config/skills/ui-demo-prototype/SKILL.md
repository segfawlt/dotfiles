---
name: ui-demo-prototype
description: >-
  Build and iterate on live interactive UI draft prototypes on a dedicated
  scratch port before touching production code. Use when the user asks for a
  draft/demo design on a port, wants to compare UI/UX layouts interactively, or
  requests a non-trivial page redesign.
---

# Interactive UI Demo Prototyping (`ui-demo-prototype`)

Use this workflow to iterate on UI/UX designs in a live browser port **without mutating repository files** until the user approves the design and asks to implement.

## Step 1: Isolated Scratch Server Using Real Repo Tokens

1. **Zero repo mutations:** Create the prototype inside `<artifactDir>/scratch/<slug>/` (never inside the git working tree while still in planning/design mode).
2. **Instant setup (no `npm install` bloat):**
   - **Inside a Vite / frontend workspace:**
     - Symlink the workspace's existing `node_modules` (e.g., `ln -s <repo>/apps/web/node_modules ./node_modules`).
     - Copy or import the project's **real** CSS tokens (`index.css`), `tailwind.config.*`, theme attributes (`data-theme`), and surrounding app chrome (rail, sidebar, wrapper widths) so the demo reflects real viewport space and real components—catching shell constraints like `max-w-*` wrappers immediately.
     - In `vite.config.ts`, restrict filesystem serving (`server: { host: '0.0.0.0', port, strictPort: true, fs: { strict: true, allow: [scratchDir, repoWebDir] } }`) so binding `0.0.0.0` is safe on LAN/Wi-Fi.
   - **Outside a Vite workspace (standalone concept / landing-page draft):**
     - Build a single zero-external-request `index.html` (CSS custom properties + `prefers-reduced-motion`) and serve via `python3 -m http.server <port> --bind 127.0.0.1` (`--bind 0.0.0.0` only if LAN/Tailscale access is needed).
   - Always include an inline SVG data-URI favicon in `index.html` so browser console checks stay `404`-free.
3. **Launch & lifecycle:**
   - Pick an unused port (check with `ss -tlnp`) and start the scratch server with `IsDaemon: true`.
   - When the user approves the draft and asks to implement in production, **kill the scratch daemon task** cleanly (`manage_task` -> `kill`).

---

## Step 2: Visual Hierarchy & Anti-"AI-Slop" Rules

Benchmark against real reference tools in the problem space (**Linear**, **Stripe**, **Clerk**, **GitHub**, **Vercel**) before writing markup/JSX:

1. **One canonical home per signal (zero duplication):**
   - Never repeat the same status/flag across directory row + hero KPI + alert banner + summary card.
   - Never invent filler cards (e.g., a redundant `"Risk Signals"` box) just to complete a symmetric 2×2 Bento grid.
2. **Restrained semantic color (no rainbow pill soup):**
   - Avoid tinted-fill + tinted-border + tinted-text capsules and ALL-CAPS + icon headers on every container.
   - Default to the repo's design grammar (e.g., monochrome surface chips with a `6px` semantic dot; reserve color for small dots and primary actions).
3. **3-tier typographic & surface hierarchy (avoid "flat list of text"):**
   - Do **not** overcorrect away from cards by making every heading `12px` on one flat background.
   - Separate sections using **scale + single-layer surface contrast** (never nested boxes-inside-boxes):
     - **Tier 1 (Hero / Identity Header):** Elevated `surface` header with a `20–22px` (`font-semibold tracking-tight`) primary title.
     - **Tier 2 (Canvas Landmarks):** Darker `canvas` stage with **`16–18px` bold section headlines placed *outside/above* single-layer `surface` blocks**, separated by `28–32px` vertical spacing and subtle `border-t` chapter rules.
     - **Tier 3 (Data & Rows):** `18–20px` `tabular-nums` summary metrics where warranted, `13px` primary row copy, and `11–12px` muted metadata.
4. **Workspace expansion / focus UX:**
   - For dense master-detail views, pair full-bleed split view with a **Focus / Fullscreen** toggle (`?focus=1`, `F` / `Esc`, plus `← Back` and `‹ / ›` item stepping) that collapses secondary sidebars/lists while keeping top-level app navigation anchored.

---

## Step 3: Multi-Archetype Fixtures (Adaptive States)

Never mock only a single "maximalist" power-user/incident record. Include at least **3 contrasting realistic fixtures** in `mockData.ts` (or a compact switcher):
1. **Active / Heavy state:** Full metrics summary, active status reason, and populated history tables.
2. **Normal / Clean state:** Collapse heavy incident grids into a single calm status bar (e.g., `Clean standing`)—**never** render a `0 / 0 / 0 / 0` stat grid or stacked empty-state boxes for clean records.
3. **Edge / Partial state:** e.g., brand-new or pending record with zero history, verifying passive caution notes don't trigger empty active-incident grids.

---

## Step 4: Mandatory Browser Screenshot Self-Critique

Before presenting the port URL to the user (and after every major visual revision):
1. Render the live port at desktop resolution (e.g., `1512×980`) and verify `0` `pageerror`s / console errors:
   - Prefer a short local Playwright script (`node -e` via workspace `playwright` package) so `pageerror`s and multi-state clicks are captured without needing the global `playwright` MCP plugin enabled; fall back to `/usr/sbin/chromium --headless --screenshot=<path> --window-size=1512,980 <url>` (or Playwright MCP if active).
2. Capture and inspect (`read_file`) screenshots of **both** the **heavy/flagged** fixture and the **clean/edge** fixture.
3. Check the actual pixels as a critical designer: verify section headlines read clearly at a glance, check for wasted viewport width, and fix any flat text walls, duplicated badges, or empty `0`-value grids **before** asking the user to review.
