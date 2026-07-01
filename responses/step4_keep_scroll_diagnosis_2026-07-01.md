# Step 4 — Keep scroll-shift diagnosis

**Date:** 2026-07-01  
**Method:** Code inspection only — no code changed.

---

## Is it real?

Yes. The mechanism is deterministic: it follows from the browser's scroll anchoring
spec and the height delta between the entry-state block and the confirmed-state block.
No guessing is involved.

---

## The mechanism, step by step

### 1. What `s4Keep` actually does to the DOM (line 264)

```javascript
var row = elById('s4-row--' + key);
if(row){ row.outerHTML = j.slot_html; }   // ← the only DOM mutation
```

One synchronous DOM replacement. No `window.scrollY` read or write anywhere before
or after. No `requestAnimationFrame`. No `scrollIntoView`. The scroll position is
untouched by the code.

### 2. The height delta

**Entry-state block** (`s4-row--{key}` in the empty branch) — with 2 dishes:

| Element | Approx height |
|---|---|
| Slot label div | ~20 px |
| Dish row 0: `<select>` + `<textarea rows=2>` name + `<details>` collapsed + `<input>` prot + Remove button div | ~170–200 px |
| Dish row 1: same | ~170–200 px |
| "+ Add a dish" button div | ~38 px |
| "Keep this meal" button div | ~42 px |
| Msg div (min-height 1em) | ~18 px |
| **Total** | **~460–520 px** |

With 3 dishes: ~630–720 px.

**Confirmed-state block** (`s4-row--{key}` in the confirmed branch):

| Element | Approx height |
|---|---|
| Slot label div | ~20 px |
| Meal name div | ~24 px |
| Recipe label div | ~22 px |
| Source/tag row (optional) | ~20 px |
| Change button + msg div | ~52 px |
| **Total** | **~138–140 px** |

**Height removed from the page:**
- 2-dish entry → confirmed: **~320–380 px**
- 3-dish entry → confirmed: **~490–580 px**

### 3. What the browser does with that height loss

After `outerHTML` fires, the browser performs a synchronous reflow:
- The replaced element is shorter by ~350–550 px
- Every element below it in the document flow shifts **up** by that amount
- `window.scrollY` is unchanged at the instant of the DOM mutation

**Scroll anchoring** (CSS Scroll Anchoring spec; enabled by default in Chrome 56+,
Firefox 66+, Safari 15.4+) then runs:

The browser has pre-selected an **anchor node** — the first element that was
partially inside the viewport and did not itself change. Because Lauren was reading
the entry block and clicked the Keep button (which is at the bottom of that block),
the anchor is most likely the **next slot row or day-card header** that was just
below or at the bottom edge of the entry block.

When the entry block collapses, the anchor node moves UP by ~350–550 px. Scroll
anchoring compensates by **decreasing `window.scrollY`** by the same amount to keep
the anchor visually stationary.

Net visual result from Lauren's perspective:

```
Before Keep:
  viewport top  ─────────────────
  [ previous slot (confirmed)   ]
  [ entry block row 0 (pasta)   ]  ← Lauren filled this in
  [ entry block row 1 (bread)   ]
  [ + Add a dish ]
  [ Keep this meal ] ← Lauren clicks this
  viewport bottom ─────────────────
  [ next slot row ]   (below viewport, anchor)

After outerHTML + scroll anchoring:
  viewport top  ─────────────────
  [ previous slot (confirmed)   ]  ← scrollY decreased; this is higher now
  viewport bottom ─────────────────
  [ confirmed "Pasta w/ Bread"  ]  ← just scrolled OUT of view below bottom,
  [ next slot row ]                   or barely clipped
```

From Lauren's point of view: she clicked Keep and the content she was looking at
**vanished upward** out of view. To find the confirmed row she has to scroll
**down** — which matches her report exactly.

### 4. Why only on multi-dish entries

A 1-dish entry block is ~270–300 px; a confirmed row is ~140 px; delta ~150 px.
Scroll anchoring still adjusts scrollY, but only by ~150 px — typically small enough
that the confirmed row remains in the lower portion of the viewport.

A 2-dish entry block adds a second full dish row (~180 px), raising the delta to
~330–380 px. On a typical mobile viewport (667–812 px tall) this is nearly half the
screen. The confirmed row ends up just below or at the viewport bottom edge, or
fully off-screen. Lauren has to scroll down to find it.

A 3-dish entry is worse still.

### 5. Why the existing comment was incomplete

Lines 222–228 say:

```
Keep (s4Keep) and Change (s4Change) do NOT reload: on success they inject the
server-rendered slot row… Rule 20 scroll-restore is therefore not needed for them.
```

This is correct as far as it goes: Rule 20's `sessionStorage.setItem('s4ScrollY') +
window.location.href` pattern prevents a full-navigation scroll-to-top. That problem
does not exist here — `outerHTML` is not navigation, and the page does not reset to
the top.

What the comment did not account for is a **different** scroll-shift mechanism: a
large in-place height reduction triggers scroll anchoring, which moves the viewport
programmatically in the same rendering frame. Rule 20's pattern would not fix this
even if applied (saving scrollY before the fetch and restoring it after would fight
scroll anchoring, not cure the root cause). The correct fix is a different operation
entirely — but the comment's reasoning led to no scroll handling at all being added.

### 6. Summary

| Question | Answer |
|---|---|
| Real? | Yes — reproducible by layout arithmetic + scroll anchoring spec |
| Triggered by navigation? | No — pure layout reflow from `outerHTML` height reduction |
| Triggered by Rule 20's reload path? | No — this is the no-reload path |
| Mechanism | Entry block collapses ~350–550 px; scroll anchoring decreases scrollY to keep content below the swap visually stable; confirmed row moves off-screen |
| Why worse with more dishes? | Each additional dish row adds ~170–200 px to the height delta, proportionally larger scrollY adjustment |
| Which line of JS causes it? | Line 264: `row.outerHTML = j.slot_html` — no scroll guard around it |
