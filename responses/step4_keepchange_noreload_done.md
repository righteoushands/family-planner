# Step 4 — Keep / Change buttons now swap in place (no reload, no flash)

**Status: DONE and verified.**

## What you asked for
Remove the full-page reload (and the flash that came with it) when you tap
**Keep** or **Change** on a meal slot in Meal Wizard Step 4 — using an
optimistic, no-reload DOM swap. **Set this plan** and **Generate** were to be
left exactly as they are (they still do a full reload). Done — those two were
not touched.

## What changed
- **Keep** and **Change** no longer navigate the page. On success they now
  receive the freshly server-rendered slot row plus the lock control and inject
  them in place, so only that one slot updates — no white flash, no scroll jump.
- The **server is still the single source of truth.** The browser does not
  rebuild any markup itself; it just drops in HTML the server rendered, using the
  same rendering helpers the full page uses (so the in-place version and the
  full-page version can't drift apart).
- The lock button re-evaluates correctly after each change — if a slot becomes
  (or stops being) eligible to lock, the **Set this plan** control updates to
  match.
- The old scroll-save workaround was removed from Keep/Change only (it's no
  longer needed without a reload). Set this plan and Generate keep their scroll
  behavior.

## How it was verified
- `py_compile` clean on `app.py` and `render_meal_wizard_step4.py`.
- All three Step 4 test harnesses pass:
  - **Read-only render** — 13/13, including a new check that the page exposes the
    per-slot row ids and the lock-control id (the hooks the in-place swap needs).
  - **Write-loop (Keep/Change/remove)** — 17/17, including new checks that the
    confirm and remove responses now return the rendered slot fragment + lock
    control for in-place injection (instead of expecting a reload).
  - **Lock flow** — 19/19, confirming Set this plan / Generate are unchanged.
- Independent code review: **PASS** — confirmed correct, no XSS in the injected
  fragments (meal text is escaped server-side), and no drift between the
  full-page and fragment renders.

## One cleanup note
While running an in-process smoke test, I accidentally cleared the live meal
wizard session. I restored it from the last committed version, so your saved
inventory (fridge / freezer / pantry contents) is back intact.

## Result
Tapping **Keep** or **Change** in Step 4 is now instant and silent — the slot
updates in place with no page reload and no flash. Everything else in Step 4
behaves exactly as before.
