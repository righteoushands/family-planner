# claud.md — new Rule 20 added (Preserve scroll on same-page reloads)

Added as Rule 20 in `claud.md`, directly after Rule 19's known-debt note and before "Current major features". Pasted back verbatim below.

## Rule 20 (new) — verbatim

> **20.  PRESERVE SCROLL ON SAME-PAGE RELOADS** — Any fetch() POST that, on success, navigates via window.location.href to the SAME page (a full reload of the page the user is already on, not a forward navigation to a different step or a different page) MUST save window.scrollY to sessionStorage immediately before setting window.location.href, then on the next page load restore the position with window.scrollTo and clear the sessionStorage key (read → scrollTo → removeItem, gated on document.readyState / DOMContentLoaded). This stops multi-item list pages from jumping to the top after an action. Forward navigations to a different page/step are exempt (jumping to the top is correct there). render_meal_wizard_step4.py is the reference implementation (the s4Keep / s4Change / s4Lock / s4Generate navigations + s4RestoreScroll). Keep this client-side only and obey Rules 7 & 12 (no raw newline in embedded JS).

## Notes
- **Scope of the rule:** only `window.location.href` → *same* page. Forward navigations (e.g. Step 2 → Step 3) and `location.reload()` callers (browsers already restore scroll on reload) are explicitly out of scope.
- **Reference implementation:** `render_meal_wizard_step4.py` — saves `window.scrollY` to `sessionStorage` before each navigation and restores+clears it via `s4RestoreScroll()` on load.
- **Cross-references:** ties to Rule 7 & Rule 12 (no raw newline in embedded JS) so any future implementation of this rule stays Python-3.11-safe.
- Per the earlier diagnosis, the existing true-match sites that this rule now governs are `render_meal_wizard_step3.py` and `render_prayer.py` (delete/add intention) — not changed here (this turn only adds the rule).

## Scope
Documentation only — `claud.md` edited to add Rule 20. No application code changed.
