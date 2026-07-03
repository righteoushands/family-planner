# DIAGNOSIS — Step 4 day-header vs meal-text styling (2026-07-03)
## Diagnosis only. Zero code changes were made.

---

## PART 0 — claud.md READ-BACK (Rule 15): every rule, pasted back

**Python 3.11 hard rules — never violate these**
1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside the f-string instead
3. All GET routing uses elif chains in do_GET — never a bare if, never nested if
   blocks for routing. POST routing in do_POST ALSO uses elif chains
   (`elif path == "/route-name": ... return`) — verified June 28 2026 against the
   live code. ONE exception: the multipart recipe routes (/recipe-save,
   /recipe-import) share an `elif path in (...)` outer block with nested `if`
   inner blocks ONLY to share upload-parsing setup — do NOT copy that pattern
   for ordinary JSON or form routes. [CORRECTED June 28 2026: an older note
   claiming standalone-if do_POST blocks was wrong; code wins.]
4. Never put import statements inside if blocks or functions [KNOWN DEVIATION:
   several live do_POST handlers use inline imports; new code keeps imports at
   module top]
5. All file writes use safe_save_json (tmp file + os.replace) — never
   open(f,'w') directly
6. No walrus operator (:=)
7. Never use a raw newline escape inside a JS string within a Python string
   literal — the browser must receive the escape sequence, not a raw newline
8. multipart/form-data: when fetch POSTs use FormData, do_POST must sniff
   Content-Type and parse with cgi.FieldStorage; empty POST data → check
   Content-Type first
9. py_compile is syntax-only: always run an in-process smoke test after it,
   then the relevant existing verify harness for the area touched, and paste
   the result. Never skip the harness for changes touching shared data files,
   save paths, or functions called from more than one place.
10. Test fixtures must never write to live data; harnesses operate on temp
    copies; never call write helpers on live data during testing
10a. ISOLATION MUST BE STRUCTURAL, NOT PROCEDURAL — any harness reading or
    writing app data must import its isolation guard (mw_test_isolation) as
    the literal first project import, call it before the first write, and the
    guard must raise (not warn) on a live path. Snapshot-and-restore is NOT
    equivalent. Extend the existing isolation module for new data stores.
11. Never double-escape HTML entities — escape() exactly once
12. Rule 7 (no raw newline in embedded JS) applies to ALL files with JS in
    Python, not just render_frol_wizard.py
13. FROL WIZARD NESTED FORM ADDENDUM — any form in a section body posting to
    /frol-wizard suppresses Save and Continue (_body_has_form checks
    action="/frol-wizard"); always confirm a new form's action
14. PRE-FLIGHT CHECKLIST — (1) how many files, list them, unknown = diagnose
    first; (2) JS in f-strings? flag the backslash-n rule; (3) forms? confirm
    none post to /frol-wizard; (4) root cause confirmed or assumed? assumed =
    diagnose first; (5) multi-file? break into single-purpose instructions;
    (6) data-shape change? confirm before/after structure explicitly
15. CLAUD.MD READ-BACK REQUIRED — read claud.md each session, paste back every
    rule, identify which apply; if unable to paste accurately, stop and ask
    Lauren to re-paste
16. MAGNIFICA HUMANITAS DESIGN PRINCIPLES — the app must never become an
    optimization engine; persons, not projects. (1) Tool not authority —
    suggestions never prescriptions; (2) companions serve real relationships,
    never replace them; (3) AI supports thinking, never replaces it; (4) be
    transparent about what AI is; no theological claims with personal
    authority; prayer texts from verified Catholic sources only; (5) language
    of grace not performance — no gamification, streaks, shaming scores; a
    hard day is never failure; (6) subsidiarity — Lauren is always the
    authority; (7) formation in digital wisdom — JP finishes high school able
    to plan his day without the app. Every feature answers yes to at least one
    of: faithful to truth / learn and teach one another / real closeness and
    physical presence / justice and peace at home — and harms none.
17. ONE FIX PER INSTRUCTION — never bundle unrelated fixes; multi-file builds
    become sequential single-purpose phases with compile check + report
    between each
18. AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER — June 1–Aug 15 2026, every
    build request is checked against the plan; off-plan requests flagged
    first; new ideas go post-September; scope is cut first, never quality
19. BUILD FOR A FUTURE SECOND FAMILY — no hardcoded family specifics; identity
    and config in app_settings.json; all data I/O through data_helpers.py; no
    cheap-to-avoid single-user assumptions [KNOWN DEBT: build_lorenzo_context
    hardcodes the roster; do not deepen]
20. PRESERVE SCROLL ON SAME-PAGE RELOADS — fetch() POSTs that reload the SAME
    page must save window.scrollY to sessionStorage before navigating, then
    restore + clear on load; forward navigations exempt;
    render_meal_wizard_step4.py is the reference implementation
21. SESSION HELPER SHALLOW-MERGE — update_meal_wizard_session merges top-level
    only; writing a whole nested key REPLACES it and drops sibling inner keys;
    read fresh → .update() → write, snapshotting immediately before the write
    [KNOWN DEVIATION July 1 2026: bit the Step 4 confirm-mirror; fixed]
22. MERGE-BASED GENERATE NO LONGER PRUNES — stale suggested_meals entries
    accumulate but are render-gated (inert), EXCEPT a stale date::slot
    re-entering window×to_plan while unconfirmed resurfaces its old
    suggestion; low severity, logged not fixed; cross-ref KI-001/KI-002

**Named sections also read:** People; Data file patterns; Route patterns
(_JSON_PATHS is LOCAL inside do_POST); Anchor-tag navigation; AI calls
(Lorenzo = claude-haiku-4-5-20251001; _repair_and_parse_json is
plan-importer-only); Change discipline (additive only; known-issues tracker
lives OUTSIDE the repo); FROL form-bypass trap; DOC CORRECTION LOG.

**Rules that apply to THIS task (styling diagnosis, read-only):**
- **15** — this read-back.
- **14** — pre-flight item 4 is exactly what this is: root cause must be
  CONFIRMED before any fix spec — this diagnosis confirms it from the real
  code, no fix drafted.
- **17** — diagnosis only, no code changes; any fix will be its own
  single-purpose instruction.
- **9 / 10 / 10a** — not triggered (nothing compiled, no tests, no data
  touched; every value below is pasted from source files read-only).
- Rules 1/2/7/12 are context for any FUTURE fix (these styles live in module-
  level constants precisely to stay out of f-strings — a fix would edit
  constants only).

---

## PART 1 — WHERE THE TWO STYLES LIVE (exact source, verbatim)

Both are module-level constants in render_meal_wizard_step4.py.

### 1a. The DAY HEADER ("Monday — July 6") — lines 64–65, applied at line 502

```python
_S4_DAY_HEADER = ("font-family:" + _HEADING_FONT + ";font-size:1.15em;font-weight:600;"
                  "color:var(--ink);margin:0;padding:12px 16px 2px;")
```

with, at line 40:

```python
_HEADING_FONT = "'Cormorant Garamond', serif"
```

Applied (lines 501–505):

```python
    header = (
        f'<h3 style="{_S4_DAY_HEADER}">'
        f'<span style="{_S4_SEASON_DOT}background:{season_color};"></span>'
        f'{weekday} \u2014 {date_label}</h3>'
    )
```

So the rendered CSS string on the h3 is literally:

```
font-family:'Cormorant Garamond', serif;font-size:1.15em;font-weight:600;color:var(--ink);margin:0;padding:12px 16px 2px;
```

### 1b. The MEAL/DISH TEXT underneath — lines 76–78, applied at lines 355 and 485–488

```python
_S4_SLOT_LABEL = "font-weight:600;color:var(--ink);font-size:0.92em;"
_S4_MEAL_NAME = "color:var(--ink);font-size:0.95em;margin-top:2px;"
_S4_META = "color:var(--ink-muted);font-size:0.85em;margin-top:2px;"
```

Applied — slot label (line 355):

```python
    label_html = f'<div style="{_S4_SLOT_LABEL}">{escape(label)}</div>'
```

Applied — meal name + recipe line (lines 485–488):

```python
    return (f'<div id="s4-row--{key}" style="{_S4_SLOT_ROW}">{label_html}'
            f'<div style="{_S4_MEAL_NAME}">{name}</div>'
            f'<div style="{_S4_META}">{recipe}</div>'
            f'{tags_html}{change_html}</div>')
```

Neither _S4_SLOT_LABEL nor _S4_MEAL_NAME declares a font-family, so they
inherit the page BODY font from html_page (ui_helpers.py) — not Cormorant.

### 1c. What the CSS variables resolve to (ui_helpers.py lines 576–577 — the
stylesheet html_page injects on every Step 4 page)

```css
  --ink:          #1c1610;
  --ink-muted:    #6b5e4e;
```

---

## PART 2 — SIDE BY SIDE: the actual values

| Property | Day header ("Monday — July 6") | Slot label ("Dinner") | Meal name ("Tacos") | Recipe/meta line |
|---|---|---|---|---|
| Constant | `_S4_DAY_HEADER` | `_S4_SLOT_LABEL` | `_S4_MEAL_NAME` | `_S4_META` |
| font-size | **1.15em** | 0.92em | 0.95em | 0.85em |
| font-weight | **600** | **600** (same!) | normal (400, inherited) | normal (400, inherited) |
| color | **var(--ink) = #1c1610** | **var(--ink) = #1c1610** (same!) | **var(--ink) = #1c1610** (same!) | var(--ink-muted) = #6b5e4e |
| font-family | 'Cormorant Garamond', serif | body font (inherited) | body font (inherited) | body font (inherited) |
| element | h3 | div | div | div |

Nearby rows inside the same day card, for completeness:

| Row | Constant | size / weight / color |
|---|---|---|
| Season label ("Ordinary Time") | `_S4_SEASON_LABEL` | 0.82em / 400 / #6b5e4e muted |
| Event rows | `_S4_EVENT_ROW` | 0.92em / 400 / #1c1610 ink |
| "Nothing planned" italic | `_S4_QUIET` | 0.9em / 400 italic / #6b5e4e muted |

---

## PART 3 — WHAT IS ACTUALLY CREATING THE LOW-CONTRAST EFFECT

Three compounding facts, all confirmed above:

1. **Identical color.** The day header, the slot label, AND the meal name are
   all the same ink `#1c1610`. Color separates nothing.
2. **Identical weight vs the slot label.** The header is 600 — but so is
   every slot label ("Breakfast"/"Lunch"/"Dinner") sitting right under it.
   Weight separates the header from dish NAMES (400) but not from the bold
   slot labels that visually dominate each row.
3. **The size gap is small and then eaten by the font itself.** 1.15em vs
   0.92–0.95em is only a ~20–25% nominal difference — and Cormorant Garamond
   has a notably small x-height and light strokes, so at 1.15em it renders
   visually about the SAME optical size as (or smaller-looking than) the
   0.92em bold body-font slot labels. The one thing that DOES distinguish the
   header — the serif family — is an elegance cue, not a hierarchy cue, at
   this size.

Net effect: within a day card, the eye meets a stack of same-color text where
the bold body-font "Dinner" labels carry more visual punch than the serif
date header above them — so the day boundary reads weak. (For comparison, the
page's own h1 solves this with the same serif at 2em + 600: the family works
as a heading when the size actually leads.)

Diagnosis complete. No fix drafted, per instruction — when you want one, the
likely knobs (size, weight, or a distinguishing color/rule on
`_S4_DAY_HEADER` only, one constant, one file) are a clean single-purpose
Rule 17 instruction.
