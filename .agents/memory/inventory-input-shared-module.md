---
name: Shared inventory input module
description: static/inventory_input.js is the reusable source for the dictate/parse/save inventory trio
---

`static/inventory_input.js` owns `window.toggleMic`, `window.parseInventory`, `window.saveInventory`
(extracted from `static/meals.js`). Any page that uses them (Meal Planner, and the upcoming Meal
Wizard Step 2) must include it **before** scripts that call them, and must expose these DOM IDs:
`mic-btn, inv-paste-raw, inv-parse-status, inv-fridge, inv-freezer, inv-pantry, inv-use-soon, inv-status`.

`saveInventory` POSTs urlencoded `data=<json>` to `/meal-save-inventory` (NOT a _JSON_PATHS route).

**Why:** wizard reuse requires one source of truth, not a copy. Both files are self-contained IIFEs.
The wake-lock helper (`requestWakeLock`/`_wakeLock`) is intentionally **duplicated** in each IIFE
rather than globalized — `meals.js` still needs its own copy for `releaseWakeLock` / visibilitychange
/ on-load call, and duplicating avoids any load-order coupling between the two files.

**How to apply:** when wiring inventory input into a new page, add the `<script src="/static/inventory_input.js">`
tag first, reuse the 8 IDs verbatim, and do not re-implement the trio.
