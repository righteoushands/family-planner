# Step 4 jsdom Tests — Remove-floor & Clone-integrity

**Date:** 2026-07-01  
**File:** `/tmp/s4test/test_remove_floor_and_clone.js`  
**Result:** 18 PASS, 0 FAIL

---

## What was built

The `/tmp/s4test/` directory was gone (wiped between sessions), so the jsdom environment was rebuilt from scratch:

- `npm init -y` + `npm install jsdom` in `/tmp/s4test/`
- HTML fixture constructed inline in the test script, matching the exact structure emitted by `_s4_slot_block` (empty branch) and the `#s4-dish-template` block in `render_meal_wizard_step4.py`
- `_S4_JS` injected via `window.eval(S4_JS)` — only `s4AddDish` and `s4RemoveDish` are exercised; the other functions (`s4Keep`, `s4Change`, `s4Lock`, `s4Generate`) are stubbed so the IIFE loads cleanly

---

## Test 1 — Remove-floor (7 assertions)

**Scenario:** Start with 1 rendered row (rm button `display:none`). Add a second row via `s4AddDish`. Click Remove on row 2. Attempt Remove on the sole surviving row.

| Assertion | Result |
|---|---|
| Precondition: 1 row rendered | PASS |
| Precondition: row 0 rm button has `display:none` | PASS |
| After `s4AddDish`: 2 rows in container | PASS |
| Added row rm button is visible (not `display:none`) | PASS |
| After removing row 2: exactly 1 row remains | PASS |
| Surviving row rm button still `display:none` | PASS |
| Remove on sole row is a no-op: still 1 row (floor enforced) | PASS |

**Confirms:** `s4RemoveDish` correctly refuses to drop below 1 row, and the original row 0's hidden rm button is not re-shown by the removal path.

---

## Test 2 — Clone-integrity (11 assertions)

**Scenario:** Add two rows (1 → 2 → 3). Verify row 3 is independent of row 2: distinct node, all fields empty, mutation of row 2 does not leak into row 3, and removing row 3 leaves row 2 fully intact.

| Assertion | Result |
|---|---|
| 3 rows present after two `s4AddDish` calls | PASS |
| row3 is a distinct DOM node from row2 | PASS |
| row3 `cat` value is empty | PASS |
| row3 `name` value is empty | PASS |
| row3 `ing` value is empty | PASS |
| row3 `prot` value is empty | PASS |
| row3 rm button is visible | PASS |
| row3 name still empty after mutating row2 name | PASS |
| After removing row3: 2 rows remain | PASS |
| row2 is still in container (same node reference) | PASS |
| row2 name intact (`"Pasta Bake"`) after row3 removed | PASS |

**Confirms:** `cloneNode(true)` deep-clones correctly; `s4AddDish` clears all `input/textarea/select` values on the clone; the clone is a new DOM node; removing a later row never corrupts an earlier one.

---

## Full output

```
── Test 1: Remove-floor (≥ 1 row enforced) ──
  PASS  precondition: 1 row rendered
  PASS  precondition: row 0 rm button has display:none
  PASS  after s4AddDish: 2 rows in container
  PASS  added row rm button is visible (not display:none)
  PASS  after removing row 2: exactly 1 row remains
  PASS  surviving row rm button still display:none
  PASS  Remove on sole row is no-op: still 1 row

── Test 2: Clone-integrity (row 3 independent) ──
  PASS  3 rows present after two s4AddDish calls
  PASS  row3 is a distinct DOM node from row2
  PASS  row3 cat value is empty
  PASS  row3 name value is empty
  PASS  row3 ing value is empty
  PASS  row3 prot value is empty
  PASS  row3 rm button is visible
  PASS  row3 name still empty after mutating row2 name
  PASS  after removing row3: 2 rows remain
  PASS  row2 is still in container
  PASS  row2 name intact after row3 removed

──────────────────────────────────────────────────
Results: 18 PASS, 0 FAIL
```
