# Sancta Familia — Step 3 Nav + Step 2 Inventory Parser Scoping (READ-ONLY)

**Scope:** (A) Why the Step 3 "Saved" screen has no path to Step 4, and whether any Step 4 link exists anywhere in the wizard. (B) How the Step 2 inventory parser splits input and routes items into fridge/freezer/pantry/use_soon, what triggers `use_soon`, and whether dictation feeds it directly. **No code was changed.**

---

## RULE 15 — CLAUD.MD READ-BACK

**Stack:** Python 3.11; raw `http.server` (`app.py` + `render_*.py`); no framework (no Flask/Django/FastAPI); JSON files in `data/`, no DB; frontend = HTML/CSS/JS rendered as Python strings; Anthropic via `urllib.request` (no SDK).

**People:** Lauren (Mom), John (Dad), JP (14, 9th), Joseph (12, 7th), Michael (5, K), James (13 mo — not assignable). Always title-case; Mom = Lauren; James excluded from school renderers/gradebook.

**Python 3.11 hard rules:**
1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — use a variable outside the f-string.
3. All GET routing uses `elif` chains in `do_GET`; POST routing in `do_POST` ALSO uses `elif` chains (`elif path == "/route": … return`). Sole exception: the multipart recipe routes (`/recipe-save`, `/recipe-import`) share an outer `elif path in (...)` with nested inner `if path == ...` blocks ONLY to share upload-parsing setup — do not copy that for ordinary JSON/form routes. *(June 28 2026 correction: do_POST is elif chains, not standalone-if; code wins.)*
4. Never put imports inside if-blocks or functions. *(Known deviation, not a license: some live `do_POST` handlers use inline `import json as _json`; new code keeps imports at top.)*
5. All file writes use `safe_save_json` (tmp + `os.replace`) — never `open(f,'w')`.
6. No walrus operator (`:=`).
7. Never use a literal backslash-n inside a JS string within a Python string literal — use the escaped form so the browser gets the escape sequence.
8. multipart/form-data: sniff Content-Type and parse with `cgi.FieldStorage`; if a POST gets empty data, check Content-Type first.
9. `py_compile` passes ≠ runtime correct — run an in-process smoke test, then the relevant `verify_phase_*.py`/`verify_*` harness and paste the result; don't skip the harness for shared data files, save paths, or multi-caller functions.
10. Test fixtures never write to live data — operate on a temp copy, restore from backup after.
11. No double-escaping HTML entities — let `escape()` run once; use plain ampersands in source.
12. The JS-newline rule (7) applies to ALL files embedding JS in Python (render_schedule, render_timeblock, render_lucy, render_lorenzo, etc.).

**Data file patterns:** mostly `data/*.json` flat dicts/lists; person keys title-case in progress/chores/events, lowercase in `auth/pins.json` + `profiles/`; compound progress keys `YYYY-MM-DD::Person::task`; date keys `YYYY-MM-DD` (most), `YYYY-Www` (meal_plan), `YYYY-MM` (cycle).

**Route patterns:** GET → `render_*.py` returning HTML; POST chained as `elif path == "/route"`; JSON POST bodies must be registered in `_JSON_PATHS` (a LOCAL set inside `do_POST`, ~app.py 3536) or the form-parser silently consumes the payload.

**Anchor-tag navigation:** plain `<a href>` cannot POST/mutate state; needed state must travel in the query string or be persisted before the click; destination handler must accept + persist it (FROL counter-pattern).

**AI calls:** model NOT uniform — Lorenzo uses `claude-haiku-4-5-20251001` (the Sonnet value is stale/unverified elsewhere); called via `urllib.request`; key from `app_settings.json`; `_repair_and_parse_json()` is a nested local in the plan-import handler ONLY (Lorenzo doesn't use it).

**Change discipline:** all changes additive; never delete/modify existing behavior unless required; flag out-of-scope file edits; keep modules <800 lines (`render_plan_importer.py` is 1,114 — JS lives in `static/js/plan_importer_{core,consult}.js`).

**FROL form-bypass trap / Rule 13:** `_section_chrome`'s `_body_has_form` looks for `action="/frol-wizard"`; any section-body form posting there suppresses Save & Continue; forms to `/frol-set-variant`, `/frol-add-activity`, `/frol-delete-activity` are safe.

**Rules 14–19:**
14. Pre-flight checklist (files touched? JS-in-f-strings? form handling/nested frol forms? root cause confirmed vs assumed? multiple files? data-shape change?).
15. Claud.md read-back required at session start (this).
16. Magnifica Humanitas — tool not authority; suggestions never prescriptions; companions serve real relationships; AI supports not replaces thinking; language of grace (no gamification/streaks/shaming); subsidiarity (Lauren is the authority); formation in digital wisdom.
17. One fix per instruction unless same file + directly related; multi-file builds → sequential single-purpose phases with compile + report between.
18. Aug-15 build plan is the priority filter (June 1–Aug 15 2026); flag off-plan builds; scope cut first, not quality.
19. Build for a future second family — no hardcoded family specifics; keep identity/config in `app_settings.json`; reads/writes through `data_helpers.py`. *(Known debt: `build_lorenzo_context` hardcodes the roster — don't deepen it.)*

**Rules that apply here:** Rule 15 (read-back, done) and Rule 14 (pre-flight, since this scopes the Step 3→4 nav gap + a Step 2 parser change). This pass itself was read-only.

---

## A) NAVIGATION — the Step 3 "Saved" screen has no path to Step 4

### A1. The `?saved=1` confirmation render — button block, VERBATIM
`render_meal_wizard_step3.py`, inside `_saved_confirmation_body` (lines 414–422):

```python
    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">Saved \u2713</h1>'
        f'<p style="{_S3_SUBTITLE}">Step 3 of 6 \u2014 What are we planning this week</p>'
        f'<p style="{_S3_HINT}">{escape(note)}</p>'
        f'{summary}'
        f'<a href="/meal-wizard-step3" style="{_S3_LINK_GHOST}">Edit these choices</a>'
        f'<a href="/meal-wizard" style="{_S3_LINK_BTN}">Back to the wizard</a>'
    )
```

Where each one points:
- **"Edit these choices"** → `<a href="/meal-wizard-step3">` (reloads the editable Step 3 form).
- **"Back to the wizard"** → `<a href="/meal-wizard">` (the wizard landing route — see A3).

Both are plain `<a href>` anchors (no `onclick`). **Neither points to Step 4.** There is no "Continue to Step 4" / "Next" button on the saved-confirmation screen.

Context (how the saved view is selected) — lines 431–434:
```python
def render_meal_wizard_step3(user: str, saved: bool = False) -> str:
    """Step 3 of the Meal Planning Wizard. When `saved` is True, render the
    saved-confirmation view instead of the editable form."""
    body = _saved_confirmation_body(user) if saved else _build_form(user)
```
And the client redirect that lands here after a successful save (line 178, inside `s3Save`):
```python
    "      .then(function(j){ if(j && j.ok){ window.location.href = '/meal-wizard-step3?saved=1'; }"
```

### A2. Any link to `meal-wizard-step4` anywhere in the wizard flow?
`rg "meal-wizard-step4" render_meal_wizard*.py` — **the ONLY matches are inside `render_meal_wizard_step4.py` itself**, and every one is a `fetch()` POST endpoint, not a navigational link INTO Step 4:

```
render_meal_wizard_step4.py
11:  ...via /meal-wizard-step4-confirm; each confirmed non-prefill meal gets a "Change"
12:  button that removes it via /meal-wizard-step4-remove so Lauren can re-enter.
207:    "    fetch('/meal-wizard-step4-confirm', { method:'POST',"
210:    "      .then(function(j){ if(j && j.ok){ window.location.href = '/meal-wizard-step4'; }"
219:    "    fetch('/meal-wizard-step4-remove', { method:'POST',"
222:    "      .then(function(j){ if(j && j.ok){ window.location.href = '/meal-wizard-step4'; }"
229:    "    fetch('/meal-wizard-step4-lock', { method:'POST',"
232:    "      .then(function(j){ if(j && j.ok){ window.location.href = '/meal-wizard-step4'; }"
```

Findings:
- **No `render_meal_wizard*` file links TO `/meal-wizard-step4` except Step 4's own self-reloads** (the `window.location.href = '/meal-wizard-step4'` lines fire only from inside Step 4, after a confirm/remove/lock POST).
- Step 3 (neither the editable form nor the saved view) contains **no** reference to Step 4. Step 4 is currently reachable only by typing/knowing the `/meal-wizard-step4` URL directly — there is **no in-flow link from Step 3 → Step 4**.

### A3. Where "Back to the wizard" goes (the landing route)
"Back to the wizard" → `/meal-wizard` (the wizard landing GET route in `app.py`). It does **not** advance to Step 4; it returns to the wizard's landing/hub page.

**Net:** the wizard flow dead-ends at the Step 3 "Saved" screen. Its two buttons go *back* to Step 3 (`/meal-wizard-step3`) and *back* to the landing (`/meal-wizard`). Nothing in the rendered wizard links *forward* to `/meal-wizard-step4`.

---

## B) STEP 2 INVENTORY PARSER — `static/inventory_input.js`

### B1. `parseInventory` — VERBATIM (lines 91–167)
```javascript
  /* ── Parse Inventory ── */
  window.parseInventory = function () {
    var raw = document.getElementById("inv-paste-raw");
    var st  = document.getElementById("inv-parse-status");
    if (!raw) return;

    var text = raw.value.trim();
    if (!text) {
      if (st) {
        st.style.color = "#c0392b";
        st.textContent = "Nothing to parse — type or dictate your inventory first.";
        setTimeout(function () { st.textContent = ""; st.style.color = "#27ae60"; }, 3000);
      }
      return;
    }

    /* Step 1 — tag section keywords with unambiguous markers */
    text = text
      .replace(/\b(in\s+(the\s+|my\s+))?(fridge|refrigerator)\b[\s:,]*/gi, "\n__FRIDGE__\n")
      .replace(/\b(in\s+(the\s+|my\s+))?freezer\b[\s:,]*/gi,               "\n__FREEZER__\n")
      .replace(/\bfrozen\b[\s:,]*/gi,                                        "\n__FREEZER__\n")
      .replace(/\b(in\s+(the\s+|my\s+))?(pantry|cabinet|cupboard|shelf|shelves|dry\s+goods)\b[\s:,]*/gi, "\n__PANTRY__\n")
      .replace(/\b(use\s+soon|need\s+to\s+use(\s+(soon|up))?|going\s+bad)\b[\s:,]*/gi, "\n__SOON__\n")
      .replace(/\b(expir\w+|wilting)\b/gi,                                   "\n__SOON__\n$1");

    /* Step 2 — split on "I have", periods, semicolons */
    text = text
      .replace(/\.\s*I\s+(also\s+)?(have|got)\s+/gi, "\n")
      .replace(/\bI\s+(also\s+)?(have|got)\s+/gi,   "\n")
      .replace(/[.;]\s+/g,                            "\n");

    /* Step 3 — parse lines into buckets */
    var chunks = { fridge: [], freezer: [], pantry: [], use_soon: [] };
    var current = "pantry";

    text.split("\n").forEach(function (line) {
      var l = line.replace(/^[\s,;:]+/, "").replace(/[\s,;:]+$/, "");
      if (!l) return;

      if (l === "__FRIDGE__")  { current = "fridge";   return; }
      if (l === "__FREEZER__") { current = "freezer";  return; }
      if (l === "__PANTRY__")  { current = "pantry";   return; }
      if (l === "__SOON__")    { current = "use_soon"; return; }

      /* split comma-separated items within the line */
      l.split(",").forEach(function (item) {
        var it = item.replace(/^[\s,;:]+/, "").replace(/[\s,;:]+$/, "");
        it = it.replace(/^(and|also|plus|some|any|a|an)\s+/i, "");
        it = it.replace(/^(I\s+)?(also\s+)?(have|got)\s+/i, "");
        it = it.trim();
        if (it && it.length > 1) chunks[current].push(it);
      });
    });

    var filled = 0;
    var elF = document.getElementById("inv-fridge");
    var elZ = document.getElementById("inv-freezer");
    var elP = document.getElementById("inv-pantry");
    var elS = document.getElementById("inv-use-soon");

    if (elF && chunks.fridge.length)   { elF.value = chunks.fridge.join("\n");   filled++; }
    if (elZ && chunks.freezer.length)  { elZ.value = chunks.freezer.join("\n");  filled++; }
    if (elP && chunks.pantry.length)   { elP.value = chunks.pantry.join("\n");   filled++; }
    if (elS && chunks.use_soon.length) { elS.value = chunks.use_soon.join(", "); filled++; }

    if (st) {
      if (filled) {
        var total = chunks.fridge.length + chunks.freezer.length +
                    chunks.pantry.length + chunks.use_soon.length;
        st.style.color = "#27ae60";
        st.textContent = total + " item" + (total === 1 ? "" : "s") + " parsed \u2713 \u2014 review and save.";
      } else {
        st.style.color = "#c0392b";
        st.textContent = "Couldn\u2019t parse \u2014 try: \"In the fridge I have eggs. Freezer: ground beef. Pantry: rice.\"";
      }
      setTimeout(function () { st.textContent = ""; st.style.color = "#27ae60"; }, 5000);
    }
  };
```

### How it splits input
1. **Step 1 — section tagging (regex `replace`):** location keywords are replaced with marker tokens on their own lines: `fridge`/`refrigerator` → `__FRIDGE__`; `freezer` and `frozen` → `__FREEZER__`; `pantry`/`cabinet`/`cupboard`/`shelf`/`shelves`/`dry goods` → `__PANTRY__`; use-soon phrases → `__SOON__` (see B2).
2. **Step 2 — sentence/clause splitting:** `". I (also) have/got "`, `" I (also) have/got "`, and any `.` or `;` followed by whitespace are all replaced with newlines.
3. **Step 3 — line walk into buckets:** iterate each line. A bare marker line switches the `current` bucket. Otherwise the line is split on commas; each item is trimmed, has leading filler stripped (`and|also|plus|some|any|a|an` and `(I )(also )have/got`), and — if longer than 1 char — pushed into `chunks[current]`.

### How items are assigned to fridge / freezer / pantry / use_soon
- Assignment is **positional/stateful**, governed by the `current` variable, which **defaults to `"pantry"`** (line 123).
- An item lands in whatever bucket `current` holds *at the moment that line is read*. `current` only changes when a marker line (`__FRIDGE__` / `__FREEZER__` / `__PANTRY__` / `__SOON__`) is encountered.
- **Consequence:** any items spoken/typed *before the first location keyword* fall into **pantry** (the default). Items keep flowing into the last-named section until the next keyword appears.
- The parsed results are written back into the four textareas: `inv-fridge`, `inv-freezer`, `inv-pantry` are joined with newlines; **`inv-use-soon` is joined with `", "`** (comma-space) — a deliberate formatting difference for the use-soon field.

### B2. What routes an item into `use_soon`? (Lauren's use-soon is empty)
An item is placed in `use_soon` **only** when `current === "use_soon"`, which happens **only** after one of these phrases appears in the raw text and becomes a `__SOON__` marker (lines 112–113):
- `use soon`
- `need to use`, `need to use soon`, `need to use up`
- `going bad`
- `expir…` (e.g. expires, expiring, expired — `expir\w+`)
- `wilting`

Notes that explain why Lauren's use-soon ends up empty:
- There is **no inference** — nothing classifies an item as use-soon by perishability, date, or category. The bucket is filled **purely** by the presence of one of those trigger phrases in the dictated/typed text.
- The `expir…`/`wilting` rule (line 113) inserts `__SOON__` **before** the matched word but **keeps the word** (`"\n__SOON__\n$1"`), so the item text remains; the plainer triggers (line 112) consume the phrase entirely.
- If Lauren never says one of those phrases, the `use_soon` bucket stays `[]`, `chunks.use_soon.length` is 0, so `inv-use-soon` is never written — i.e. **empty by design unless a trigger phrase is spoken.**

### B3. Does raw dictated speech feed straight into `parseInventory`?
**Not automatically — there is a manual step in between.** The flow:
- `window.toggleMic` (lines 30–88) runs Web Speech (`SpeechRecognition`/`webkitSpeechRecognition`, `continuous`+`interimResults`) and writes the transcript **into the `inv-paste-raw` textarea** (`ta.value = committed + interim;` line 69; finalized to `committed` on `onend`, line 76).
- `parseInventory` (line 92) reads its input from **`document.getElementById("inv-paste-raw")`** — the same textarea.

So dictation and typing both land in the **same** `inv-paste-raw` box, and **`parseInventory` only runs when it is explicitly invoked** (by the Parse button / handler) — it is **not** called from the mic `onresult`/`onend` callbacks. Dictated speech populates the textarea, but the user must trigger parsing; raw speech does **not** stream directly through the parser on its own.

---

## Summary
- **A (Nav):** The Step 3 `?saved=1` screen's two anchors go to `/meal-wizard-step3` ("Edit these choices") and `/meal-wizard` ("Back to the wizard") — both *backward*. No `render_meal_wizard*` file links forward to `/meal-wizard-step4`; the only `meal-wizard-step4` references are Step 4's own POST `fetch` endpoints and self-reloads. **Step 4 has no in-flow entry point from Step 3.**
- **B (Inventory):** `parseInventory` tags section keywords → splits on "I have"/periods/semicolons → walks lines into four buckets with a **stateful `current` that defaults to `pantry`**. `use_soon` is filled **only** by explicit trigger phrases (`use soon`, `need to use (up/soon)`, `going bad`, `expir…`, `wilting`) — there's no automatic perishability inference, which is why Lauren's use-soon is empty. Dictation writes into `inv-paste-raw`; parsing is a **separate manual action**, not an automatic pipe from speech.
