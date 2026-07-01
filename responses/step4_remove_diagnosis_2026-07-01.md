# Step 4 — Remove-row bug diagnosis

**Date:** 2026-07-01  
**Method:** 7 jsdom behavioral scenarios, 30 assertions  
**Result: Bug does NOT reproduce in the JS under any tested scenario. 30/30 PASS.**

The DOM/JS mechanism is identified below. The cause of Lauren's live report is not
`s4RemoveDish` — it is `s4Keep`'s `outerHTML` replacement. Details follow.

---

## Test matrix

| Scenario | Description | Result |
|---|---|---|
| D1 | Remove middle row of 3 (index 1) — the originally untested case | PASS (2 rows remain, correct identity) |
| D2 | Remove index 1 of 4 rows | PASS (3 rows remain, correct identity) |
| D3 | Remove index 2 of 4 rows (third of four) | PASS (3 rows remain, correct identity) |
| D4 | Rapid: add-add-remove(middle)-remove(last) | PASS (floor enforced, 1 row remains) |
| D5 | Stale-ref double-click: same detached button called twice synchronously | PASS (second call is no-op) |
| D6 | Multi-slot page: remove in slot B cannot affect slot A | PASS (slot A unchanged) |
| D7 | `querySelectorAll` scope: container count vs document count | PASS (container correctly scoped) |

---

## Exact DOM/JS mechanism for each scenario

### D1 — Remove middle row of 3

```
Before:  container → [row0(id=row0), row1(id=row1), row2(id=row2)]
s4RemoveDish(rmBtn(row1)):
  btn.closest('.s4dr')          → row1  ✓
  container = row1.parentNode   → s4-dishes--{key}  ✓
  container.querySelectorAll('.s4dr').length  → 3  > 1  ✓
  container.removeChild(row1)
After:   container → [row0, row2]
row1.parentNode === null  ✓
```

`closest` walks straight up to the immediate `.s4dr` parent. Non-last removal is identical to last-row removal — the function doesn't know or care about position.

### D5 — Stale-ref double-click (the double-click path)

```
Call 1:  btn.closest('.s4dr') → row1 (still attached)
         container = row1.parentNode  (valid)
         count = 2 > 1  → removeChild(row1)
         row1 now detached, parentNode = null

Call 2 (same btn, now detached):
         btn.closest('.s4dr') → row1 (found — traversal works inside detached subtree)
         container = row1.parentNode  → null
         if(container && ...)  → FALSE (null guard fires)
         → no-op
```

Double-clicking Remove is safe. The second call hits the `if(container && ...)` null guard and does nothing.

### D7 — The scope finding (important)

```
s4-dishes--{key} container:  2 .s4dr rows     ← what s4RemoveDish counts
document (whole page):       3 .s4dr nodes    ← container rows + 1 inside hidden #s4-dish-template
```

`s4RemoveDish` uses `container.querySelectorAll('.s4dr')` (scoped to the slot's container), **not** `document.querySelectorAll`. The template's hidden `.s4dr` is NOT a descendant of any slot container — it is a sibling at the body level — so it is never counted in the floor check. Correct.

---

## Why the bug does not reproduce: the JS is correct

`s4RemoveDish` has no path that removes more than one row per call:

```javascript
window.s4RemoveDish = function(btn){
    var row = btn ? btn.closest('.s4dr') : null;   // exactly one row
    if(!row){ return; }
    var container = row.parentNode;
    if(container && container.querySelectorAll('.s4dr').length > 1){
        container.removeChild(row);                 // exactly one removeChild
    }
};
```

One `closest` call → one node reference. One `removeChild` call. No loop, no querySelectorAll-then-iterate, no outerHTML assignment, no event re-dispatch. Under no jsdom scenario (middle row, rapid sequence, double-click, multi-slot) does more than one row leave the container per `s4RemoveDish` invocation.

---

## The actual mechanism: `s4Keep`'s `outerHTML` replacement

The one function that **does** make ALL dish rows disappear at once — by design — is `s4Keep`'s success branch:

```javascript
var row = elById('s4-row--' + key);
if(row){ row.outerHTML = j.slot_html; }    // ← replaces the entire slot div
```

When Keep succeeds, `j.slot_html` is the server-rendered **confirmed** slot view. That view has no `s4-dishes--{key}` container, no `.s4dr` rows, no Add button, no inputs — only the formatted dish name, recipe label, source tag, and a Change button. The entire entry UI (all rows Lauren added) is atomically replaced by this one `outerHTML` write.

**This is the only in-scope mechanism that makes multiple rows vanish in one user action.** It is intentional — it collapses the entry affordance into the confirmed summary — but it fires when the user clicks "Keep this meal", not "Remove".

---

## Probable cause of Lauren's live report

Lauren clicked **"Keep this meal"** while she had 2–3 dish rows visible. The Keep POST succeeded, the `outerHTML` replacement fired, and all input rows were replaced by the single-line confirmed summary. From her perspective: she clicked a button and multiple rows disappeared instantly.

The "Keep this meal" button and the "Remove" button on the last-added row sit close together vertically:

```
[+ Add a dish]
[Keep this meal]      ← full-width gold button
  ┌──────────────────────────┐
  │ row 1  ... [Remove]      │   ← "Remove" is inside a dish row just above
  └──────────────────────────┘
```

On a mobile viewport or small screen, the Keep button and the Remove button of the row immediately above it are adjacent. A tap slightly off-center reaches Keep, not Remove.

---

## What is NOT the cause

| Hypothesis | Ruled out by |
|---|---|
| `s4RemoveDish` removes multiple rows per call | D1–D4: all confirm exactly one row removed, correct survivors |
| Double-click of Remove removes 2 rows | D5: second call hits `parentNode===null` guard, is a no-op |
| Cross-slot contamination | D6: slot A unchanged when slot B's row is removed |
| Document-wide `querySelectorAll` miscounting the floor | D7: code uses `container.querySelectorAll`, template excluded |
| Middle-row `closest` climbing to wrong ancestor | D1: `closest('.s4dr')` correctly finds the immediate parent row |

---

## Recommendation (diagnosis only — no code changed)

The bug is in the UX, not the JS:

1. **Confirm with Lauren**: ask her to reproduce and note which button label was shown on the action that triggered the collapse. If it was "Keep this meal" and she thought it was "Remove", the above explains it completely.
2. If it genuinely was Remove, the next investigation step is a real-browser session with DevTools open — jsdom confirms the logic is correct, so any remaining issue would be browser-specific (rendering engine, `<details>` state, event delegation layer added by an extension) and cannot be diagnosed further from source inspection alone.

---

## Full test output

```
── D1 — Remove middle row of 3 (index 1) ──
  PASS  precondition: 3 rows  [count=3]
  PASS  row1 rm btn visible before remove
  PASS  after remove: container has 2 rows  [count=2]
  PASS  row0 still present (data-id=row0)
  PASS  row2 still present (data-id=row2)
  PASS  row1 is gone (not in container)
  PASS  removed row1 is detached (parentNode=null)  [parentNode=null]
  INFO  doc-wide .s4dr count = 3 (container=2, template=1 hidden, total expected=3)

── D2 — Remove index 1 of 4 rows ──
  PASS  precondition: 4 rows  [count=4]
  PASS  after remove: 3 rows remain  [count=3]
  PASS  index 0 = row0
  PASS  index 1 = row2 (row1 gone, row2 shifted up)
  PASS  index 2 = row3

── D3 — Remove index 2 of 4 rows (third of four) ──
  PASS  after remove: 3 rows remain  [count=3]
  PASS  row0 at index 0
  PASS  row1 at index 1
  PASS  row3 at index 2
  PASS  row2 detached

── D4 — Rapid: add add remove-middle remove-last ──
  PASS  after first remove: 2 rows  [count=2]
  PASS  survivors are r0 and r2
  PASS  after second remove: 1 row (floor enforced)  [count=1]
  PASS  sole survivor is r0

── D5 — Double-click simulation: s4RemoveDish(btn) called twice with same btn ──
  PASS  after 1st call: 1 row (r1 removed)  [count=1]
  PASS  after 2nd call (stale btn): still 1 row — no phantom removal  [count=1]
  PASS  r0 still present
  INFO  detached btn.closest('.s4dr') = found (detached .s4dr, parentNode=null)

── D6 — Multi-slot: remove in slot B does not affect slot A ──
  PASS  slot A: 3 rows  [count=3]
  PASS  slot B: 2 rows  [count=2]
  PASS  slot A unchanged: still 3 rows  [count=3]
  PASS  slot B: 1 row remains  [count=1]

── D7 — querySelectorAll scope: container count vs document count ──
  PASS  container .s4dr count = 2  [got=2]
  PASS  document .s4dr count = 3 (container rows + template)  [got=3]
  INFO  container scoping confirmed: 2 vs document 3

────────────────────────────────────────────────────────────
Results: 30 PASS, 0 FAIL
────────────────────────────────────────────────────────────
```
