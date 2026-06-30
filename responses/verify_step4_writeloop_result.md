# Rule 9 follow-up — Step 4 write-loop harness result

## Why this run (Rule 9 + Rule 14)
The shipped Step 4 scroll fix touches the inline JS that drives **more than one** server write path (`s4Keep`→`/meal-wizard-step4-confirm`, `s4Change`→`/meal-wizard-step4-remove`, `s4Lock`→`/meal-wizard-step4-lock`, `s4Generate`→`/meal-wizard-generate`). Rule 9 requires the relevant verify harness for any change to a multi-caller function, so the Keep/Confirm + Change/remove write loop is re-verified here.

## Command
```
python data/verify_meal_wizard_step4_writeloop.py
```

## Result — PASS (exit 0)
```
PASS confirm POST returns 200 {ok:true}
PASS confirmed meal persisted to session
PASS confirmed meal is locked
PASS GUARD 1: recipe_on_request auto-set True (client omitted it)
PASS confirmed meal has empty recipe_id
PASS GET page shows the confirmed meal
PASS confirmed meal shows a 'Change' button
PASS confirmed meal shows 'No recipe needed'
PASS GUARD 2: recipe_id present -> recipe_on_request left False
PASS GUARD 3: recipe_on_request already True -> left True
PASS remove POST clears the slot from the session
PASS removed slot returns to the empty entry state
PASS prefill (past) meal renders locked with NO 'Change' button

PASS all G1b-2a write-loop + guard checks passed
EXIT=0
```

## What this confirms
- **Keep/Confirm path**: confirm POST → 200 `{ok:true}`, meal persists to session, locks, and the GET page renders it with a **Change** button + "No recipe needed".
- **recipe_on_request guards** (all 3): auto-set True when client omits it; left False when a `recipe_id` is present; left True when already True.
- **Change/remove path**: remove POST clears the slot; the slot returns to the empty-entry state.
- **Prefill (past) meal**: renders locked with **no** Change button.

The scroll fix changed only client-side navigation timing (save `scrollY` before each `window.location.href`, restore on load); these server write paths are unchanged and remain green.

## Scope
Verification only — no code changed this turn.
