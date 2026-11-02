---
name: ui-flaw-scan
description: Two-pass UI audit combining live Playwright browser testing with static frontend source review. Covers desktop + mobile viewports, auth/anon states, console/network errors, open redirects, swallowed errors, and accessibility.
---

# UI Flaw Scan Playbook

Two-pass audit combining live browser testing with static source review. Proven on Vite + React SPAs; adapt route paths, auth storage, and output paths to the current repository.

## Pass 1 — Live Playwright Scan
- Reuse stored auth state if present (e.g., `e2e/.auth/user.json`) for authenticated runs; also run an unauthenticated pass.
- Cover every route in the app's route table at desktop AND ~390px mobile widths.
- Watch console and network requests for 401s/5xxs, unhandled rejections, and duplicate API calls.
- Test: redirects (including `returnTo` handling), empty states, disabled-submit guards, spinners that never resolve, horizontal overflow, clipped controls at mobile width, and dead-end error pages.
- Save screenshots to a scratch/temp dir; note route + viewport per shot.

## Pass 2 — Static Source Audit
Search the frontend source for recurring bug patterns:
- `new EventSource(` or hardcoded `/api/` strings that bypass the API base-URL helper (breaks split-origin deploys).
- `try/finally` or `await` without `.catch`/`catch` → unhandled rejections = silent dead clicks.
- `res.ok ? json : null` → swallows server errors as empty states.
- Redirect validation: `startsWith("/")` without rejecting `//` accepts `//evil.com` (protocol-relative open redirect).
- Module-level caches keyed on user-scoped data surviving logout.
- Serialized fetch chains (`await a` → `await b` when independent) causing multi-second renders.
- Accessibility: clickable `div`/`li` without `tabIndex`/`role`/keyboard handler, `outline: none` without focus replacement, unlabeled inputs, `window.prompt`/`window.confirm` for destructive actions.
- Dead routes in route table; `navigate()` / `<Link>` targets that do not match registered routes.

## Verify Before Reporting
- Confirm every high-severity claim against live source (`file:line`) before writing it up.
- Distinguish initial-load-only issues from live-SPA-session issues.

## Output
- Report consolidated findings (or write to `docs/issues/ui-scan-<date>.md` when requested) with `file:line` references, severity, and a concise **Verified OK** section listing routes and checks actually exercised.
