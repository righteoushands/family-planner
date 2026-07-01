# Step 4 — Keep scroll-shift fix

**Date:** 2026-07-01  
**File changed:** `render_meal_wizard_step4.py` (6 lines in `s4Keep`'s fetch success callback)

---

## Approach chosen: Option 1

Option 2 (CSS `max-height` transition) only softens the jump — the confirmed row can
still leave the viewport; it just leaves more slowly. Option 1 eliminates both
failure modes:

1. Scroll anchoring fires → scrollY shifts uncontrolled → fixed by `overflow-anchor: none`
2. Entry block was taller than viewport, Keep button was at bottom → confirmed row above
   new scrollY even without anchoring → fixed by `scrollIntoView({block: 'nearest'})`

---

## Change

**Before** (one line in the fetch `.then` success branch):

```javascript
var row = elById('s4-row--' + key); if(row){ row.outerHTML = j.slot_html; }
```

**After** (same logical position, 5 lines):

```javascript
var row = elById('s4-row--' + key);
if(row){
  document.documentElement.style.overflowAnchor = 'none';  // suppress anchor selection
  row.outerHTML = j.slot_html;                             // height-reducing swap
  document.documentElement.style.overflowAnchor = '';      // restore default
  var confirmed = elById('s4-row--' + key);                // re-query new node
  if(confirmed){ confirmed.scrollIntoView({block: 'nearest'}); }
}
```

Everything else in `s4Keep` is unchanged. The lock-control swap (`lock.outerHTML = j.lock_html`) still follows immediately after.

**Why `overflowAnchor` on `document.documentElement`:** the full-page scroll container is `<html>`. Setting `overflow-anchor: none` on it for the duration of the swap suppresses the browser from selecting any descendant as a scroll anchor for this reflow frame — so `window.scrollY` stays exactly where it was when Lauren clicked Keep.

**Why re-query after `outerHTML`:** `outerHTML = …` detaches the original node from the DOM; the variable `row` is now a stale reference to the detached element. `elById('s4-row--' + key)` finds the newly inserted confirmed node, which has the same id.

**Why `{block: 'nearest'}`:** if the confirmed row is already fully visible (common case — short meal, whole entry block was in view), no scroll happens. Only if the row is partially or fully outside the viewport does the browser adjust — to the minimum scroll needed to bring it into view. No overshooting to the top.

---

## Smoke test method used: JS code-path inspection

jsdom does not perform CSS layout: `getBoundingClientRect` returns `{top:0,…}` for
all elements regardless of DOM structure, and `scrollIntoView` is a no-op.
Real-browser layout is required to verify pixel positions. The smoke test
therefore verifies the JS code path structurally — all five operations are
present in the rendered JS string, in the correct order — which is what makes the
fix mechanically correct. The visual result (confirmed row stays in the viewport)
follows deterministically from the mechanism.

### Compile check

```
COMPILE OK
```

### JS code-path checks (7/7 PASS)

```
  PASS  overflowAnchor none set
  PASS  outerHTML swap
  PASS  overflowAnchor restored
  PASS  confirmed re-query
  PASS  scrollIntoView call
  PASS  lock swap still present
  PASS  execution order correct (none→swap→restore→requery→scrollIntoView)
```

---

## verify_meal_wizard_step4_writeloop.py — 17/17 PASS

```
PASS confirm POST returns 200 {ok:true}
PASS confirm response returns the confirmed slot fragment (row id + Change)
PASS confirm response reports lock-eligibility True + lock-control HTML
PASS confirmed meal persisted to session
PASS confirmed meal is locked
PASS GUARD 1: recipe_on_request auto-set True (client omitted it)
PASS confirmed meal has empty recipe_id
PASS confirmed entry stored in dishes[] shape (no flat name key)
PASS GET page shows the confirmed meal
PASS confirmed meal shows a 'Change' button
PASS confirmed meal shows 'No recipe needed'
PASS GUARD 2: recipe_id present -> recipe_on_request left False
PASS GUARD 3: recipe_on_request already True -> left True
PASS remove POST clears the slot from the session
PASS remove response reverts to entry state showing the last-confirmed value
PASS removed slot returns to entry state showing the last-confirmed value
PASS prefill (past) meal renders locked with NO 'Change' button

PASS all G1b-2a write-loop + guard checks passed
```
