---
name: Anthropic model strings (live verification)
description: Which Anthropic model strings actually resolve with this app's API key, and which are dead.
---

# Anthropic model strings — verify per call, don't trust documented defaults

Model strings are NOT uniform across this app, and some documented ones are dead.
Always probe a candidate cheaply (max_tokens=5) against the live key before wiring
it into a route.

**Verified against the live `anthropic_api_key` (June 2026):**
- `claude-sonnet-4-20250514` → **404 not_found** (DEAD — do not use; it is the stale
  value claud.md warns about). The 404 surfaces as `raise_for_status()` →
  `"404 Client Error: Not Found for url"`, so any fallback check must match
  `"404"`/`"not found"`, not just `"not_found"`.
- `claude-sonnet-4-6` → **200 OK** (working Sonnet — use this for Sonnet calls).
- `claude-sonnet-4-5` / `claude-sonnet-4-5-20250929` → 200 OK.
- `claude-haiku-4-5-20251001` → 200 OK (Lorenzo's verified model).

**Why:** claud.md documents `claude-sonnet-4-20250514` as stale/unverified; it is in
fact fully retired for this key and will 404 in production. Several handlers in
app.py still hardcode it (grep `claude-sonnet-4-20250514`) — they will fail if/when
those branches run. The Meal Wizard generate route (`/meal-wizard-generate`) was
switched to `claude-sonnet-4-6`.

**How to apply:** when adding or fixing any Sonnet call, use `claude-sonnet-4-6` (or
re-probe), never `claude-sonnet-4-20250514`. The other hardcoded `20250514` call
sites in app.py are latent bugs to fix when touched.
