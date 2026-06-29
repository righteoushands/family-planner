# Meal Wizard — G1c (Lorenzo One-Pass Generation) Diagnosis

**READ-ONLY. Nothing was changed.** This scopes the "Lorenzo generates the week in one pass and pre-fills the empty Step 4 slots" build. Goal: do NOT build a second generator if a usable one exists. Verbatim code under each heading; reuse-vs-rebuild decision called out explicitly.

---

## RULE 15 — CLAUD.MD READ-BACK

**Stack:** Python 3.11; raw `http.server` (`app.py` + `render_*.py`); no framework; JSON files in `data/`, no DB; HTML/CSS/JS rendered as Python strings; Anthropic via `urllib.request` / `requests` (no SDK).

**People:** Lauren (Mom), John (Dad), JP (14), Joseph (12), Michael (5), James (13 mo, not assignable). Title-case; Mom = Lauren; James excluded from school/assignable renderers.

**Python 3.11 hard rules:**
1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — pull the value into a variable first.
3. GET routing = `elif` chains in `do_GET`; POST routing = `elif` chains in `do_POST` (`elif path == "/route": … return`). Sole exception: multipart recipe routes share an outer `elif path in (...)` with nested inner `if`.
4. Never put imports inside if-blocks or functions. *(Known deviation, not a license: many live `do_POST` handlers do `import json as _json, requests as _req` inline — `/meal-generate` is one of them. New code keeps imports at top.)*
5. All file writes via `safe_save_json` (tmp + `os.replace`) — never `open(f,'w')`.
6. No walrus (`:=`).
7. Never put a literal backslash-n inside a JS string embedded in a Python literal — use the escaped form.
8. multipart/form-data: sniff Content-Type, parse with `cgi.FieldStorage`.
9. `py_compile` ≠ runtime-correct — in-process smoke test, then run the relevant `verify_*` harness and paste results.
10. Test fixtures never touch live data — temp copy, restore after.
11. No double-escaping HTML — let `escape()` run once.
12. Rule 7 applies to ALL files embedding JS in Python.
13. FROL form-bypass trap: `_section_chrome` suppresses Save & Continue if a section body posts to `action="/frol-wizard"`.
14. Pre-flight checklist before building.
15. Read-back at session start (this).
16. Magnifica Humanitas — tool serves the family; suggestions not prescriptions; subsidiarity (Lauren is the authority); language of grace (no gamification/shaming).
17. One fix per instruction unless same file + directly related; multi-file → sequential single-purpose phases with compile + report between.
18. Aug-15 build plan is the priority filter; flag off-plan; cut scope before quality.
19. Build for a future second family — no hardcoded family specifics; identity/config in `app_settings.json`; reads/writes through `data_helpers.py`. *(Known debt: `build_lorenzo_context` hardcodes the McAdams roster — don't deepen it.)*

**Which rules apply to a one-pass whole-week AI generation filling `confirmed_meals` slots (NOT the chat flow):**
- **Rule 4 (CRITICAL here):** generation must fill ONLY empty slots and never clobber an already-confirmed/locked meal in `confirmed_meals`. Additive only.
- **Rule 19 (CRITICAL here):** `build_lorenzo_context` already hardcodes the roster — a new generator must NOT copy that; pull family facts from `app_settings.json` / pass them in, and read/write the session through `data_helpers.py`.
- **Rule 5:** any write to the wizard session must go through `save_meal_wizard_session` / `update_meal_wizard_session` (which already use `safe_save_json`). Never write the file directly.
- **Rules 1/2/4-import:** if the generator lands in a `do_POST` handler, follow the prevailing inline-import style there OR (preferred) put imports at module top; no f-string quote/backslash violations in any prompt assembly.
- **Rule 9/10:** in-process smoke + a `verify_*` harness; fixtures on a temp copy.
- **Rule 16:** generated meals are a *draft* Lauren edits/confirms — never auto-lock; "pre-fill" not "decide."
- **Rule 17/18:** this is one build; confirm it's on the Aug-15 plan; if multi-file, phase it.
- **NOT central:** Rule 13 (no FROL form), Rule 8 (no multipart), Rule 11 (no new HTML escaping unless rendering the draft).

---

# PART A — WHAT GENERATION ALREADY EXISTS

There are **two distinct meal generators**, plus the Lorenzo chat write-path (Part C). Neither of the two generators targets the wizard session — both target the **legacy weekly meal-plan store** (`load_meal_plan`/`save_meal_plan`, i.e. `data/meal_plan*.json` keyed by week), NOT `confirmed_meals` in the wizard session.

## A1. `/meal-generate` — the REAL generator (full handler, app.py 10873–10983) VERBATIM

```python
            elif path == "/meal-generate":
                import json as _json, requests as _req
                wk     = clean_text(data.get("week",[""])[0]) or _week_key()
                raw_inv = data.get("inventory",["{}"])[0]
                try:   inv_in = _json.loads(raw_inv)
                except: inv_in = {}
                # Save inventory first
                inv = load_inventory()
                for k in ("fridge","freezer","pantry","use_soon"):
                    if k in inv_in: inv[k] = clean_text(inv_in[k])
                save_inventory(inv)
                # Get cycle phase and capacity from today's anchor
                from render_morning_anchor import _get_anchor_state
                from datetime import date as _date
                anchor = _get_anchor_state(_date.today().isoformat())
                cycle_phase = anchor.get("cycle_phase","")
                capacity    = anchor.get("capacity","")
                # Build prompt (include any saved constraints for this week)
                _plan_for_constraints = load_meal_plan(wk)
                _constraints_for_gen  = _plan_for_constraints.get("constraints","")
                prompt = _build_meal_prompt(inv, cycle_phase, capacity,
                                            constraints=_constraints_for_gen)
                # Call Anthropic API
                settings = load_app_settings()
                api_key  = (settings.get("anthropic_api_key","")
                            or settings.get("family_constraints",{}).get("anthropic_api_key",""))
                if not api_key:
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    self.end_headers()
                    try: self.wfile.write(_json.dumps({"error":"No API key set in Settings"}).encode())
                    except BrokenPipeError: pass
                    return
                try:
                    resp = _req.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-sonnet-4-20250514",
                            "max_tokens": 4096,
                            "messages": [{"role":"user","content": prompt}],
                        },
                        timeout=90,
                    )
                    resp.raise_for_status()
                    resp_json = resp.json()
                    text = "".join(
                        b.get("text","") for b in resp_json.get("content",[])
                        if b.get("type") == "text"
                    )
                    # Extract JSON from response — multi-strategy robust parse
                    import re as _re
                    parsed = {}
                    # Strategy 1: JSON inside ```json ... ``` fences
                    fence_m = _re.search(r'```json\s*([\s\S]*?)\s*```', text)
                    candidates = []
                    if fence_m:
                        candidates.append(fence_m.group(1))
                    # Strategy 2: outermost {...} block
                    brace_m = _re.search(r'\{[\s\S]*\}', text)
                    if brace_m:
                        candidates.append(brace_m.group())
                    for cand in candidates:
                        try:
                            parsed = _json.loads(cand)
                            break
                        except _json.JSONDecodeError:
                            # Strategy 3: strip trailing commas before } or ]
                            cleaned = _re.sub(r',\s*([}\]])', r'\1', cand)
                            try:
                                parsed = _json.loads(cleaned)
                                break
                            except Exception:
                                pass
                    # Extract the day plan (7 day keys) vs metadata
                    from render_meals import DAYS as _DAYS
                    if not parsed:
                        raise ValueError("Claude response could not be parsed as JSON. Raw: " + text[:400])
                    days_out = {d: parsed.get(d,{}) for d in _DAYS}
                    grocery_gaps  = parsed.get("grocery_gaps", [])
                    prep_notes    = parsed.get("prep_notes", {})
                    use_soon_used = parsed.get("use_soon_used", [])
                    # Save plan
                    plan = load_meal_plan(wk)
                    plan["days"]          = days_out
                    plan["grocery_gaps"]  = grocery_gaps
                    plan["prep_notes"]    = prep_notes
                    plan["use_soon_used"] = use_soon_used
                    plan["generated"]     = True
                    plan["week"]          = wk
                    plan["start"]         = wk
                    save_meal_plan(plan)
                    result = {
                        "ok": True,
                        "days": days_out,
                        "grocery_gaps": grocery_gaps,
                        "prep_notes": prep_notes,
                        "use_soon_used": use_soon_used,
                    }
                except Exception as e:
                    result = {"error": str(e)}
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps(result).encode())
                except BrokenPipeError: pass
                return
```

**What it does / writes:** Saves inventory, reads cycle phase + capacity from the morning anchor, builds the prompt via `_build_meal_prompt` (Part F-adjacent / shown below), calls **Sonnet (`claude-sonnet-4-20250514`), max_tokens 4096, timeout 90s** via `requests.post`, robust-parses JSON (fenced → outermost-brace → trailing-comma strip), then **WRITES the legacy store directly**: `plan["days"|"grocery_gaps"|"prep_notes"|"use_soon_used"|"generated"|"week"|"start"]` → `save_meal_plan(plan)`. It also returns the same data in `result` JSON.

- **days_out:** `{day: parsed.get(day,{}) for d in DAYS}` — full 7-day dict, each day a slot dict (`breakfast/lunch/dinner/dessert/snacks/dad_lunch/boys_help`).
- **grocery_gaps:** list (ingredients not in inventory).
- **prep_notes:** object (one note/day).
- **use_soon_used:** list.
- **generated:** `True` flag on the plan.

## A2. `/ai-meal-plan` — the SECOND, weaker generator (route + function) VERBATIM

Route (app.py 11576–11587):
```python
            elif path == "/ai-meal-plan":
                import json as _j
                from render_ai_daily import ai_meal_plan
                wk_in = clean_text(data.get("week_key",[""])[0])
                try:
                    result = ai_meal_plan(wk_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return
```

Function `ai_meal_plan` (render_ai_daily.py 142–175):
```python
def ai_meal_plan(week_key: str) -> dict:
    """Suggest a full week of meals."""
    try:
        from render_settings import load_app_settings
        settings   = load_app_settings()
        meal_rules = settings.get("meal_rules", [])
        rules_str  = "\n".join(f"- {r.get('rule','')}" for r in meal_rules) if meal_rules else "No specific rules saved."

        try:
            from render_meals import load_meal_plan, slot_display_text
            existing = load_meal_plan(week_key)
            existing_meals = []
            for day, meals in existing.get("days", {}).items():
                dinner = slot_display_text(meals.get("dinner"))
                if dinner:
                    existing_meals.append(f"{day}: {dinner}")
            existing_str = "\n".join(existing_meals) if existing_meals else "None planned yet."
        except Exception:
            existing_str = "None planned yet."

        prompt = (
            f"You are a Catholic homeschool family meal planner.\n"
            f"Liturgical season: {_season()}.\n"
            f"Meal rules:\n{rules_str}\n\n"
            f"Already planned this week:\n{existing_str}\n\n"
            f"Suggest dinners for any unplanned days Monday–Friday (and optionally Sat/Sun). "
            f"Format each as: 'Monday — Meal name (brief note)'. "
            f"Consider the liturgical season (e.g. meatless Fridays in Lent). "
            f"Keep meals practical for a busy homeschool family."
        )
        text = _call_claude(prompt, 400)
        return {"html": _format_html(text), "text": text}
    except Exception as e:
        return {"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "text": ""}
```

**What it does / writes:** **Writes NOTHING.** Returns `{"html","text"}` — free-text dinner *suggestions only*, dinners-only, Haiku @ max_tokens 400 (via `_call_claude`, Part E). Output is unstructured prose formatted to HTML (`_format_html`), not parseable into slots. Display-only.

## A3. Other AI-produces-meals sites (grep of Anthropic call sites near "meal")
- **app.py 5810 `/lorenzo-chat`** — the conversational chef. Does NOT one-pass-generate a week; it edits slots reactively via `[MEAL_UPDATE:…]` tags it emits, parsed at app.py 5908+ (Part C). Writes the **legacy** store (`save_meal_plan`), one slot at a time, on user assent. Haiku, max_tokens 1500 (chat sites cluster at 1500/1200 across app.py).
- **app.py 10873 `/meal-generate`** — A1 above. The real generator.
- **render_ai_daily.py 142 `/ai-meal-plan`** — A2 above. Suggestions only, no write.
- No other site asks an AI to produce a day/week of meals. (Other Anthropic sites are Lucy, school/examen planners, plan-importer, assignment analyzer — non-meal.)

## A4. Reuse-vs-rebuild decision (explicit)

| Generator | Writes store? | Returns structured data? | Output shape | Targets wizard `confirmed_meals`? |
|---|---|---|---|---|
| `/meal-generate` (A1) | **YES — `save_meal_plan` (legacy weekly store)** | **YES — also returns `days/grocery_gaps/prep_notes/use_soon_used` in `result`** | 7-day × slot dict, each slot a plain string (`boys_help` combined string) | **NO** |
| `ai_meal_plan` (A2) | NO | NO (HTML/text prose) | free-text dinner suggestions | NO |
| `/lorenzo-chat` (C) | YES — `save_meal_plan` per-slot | partial (tag-driven) | one slot at a time | NO |

**Recommendation (for the build, not done here):**
- **Do NOT build a brand-new model-calling generator from scratch.** `/meal-generate` already does the hard part well: prompt assembly (`_build_meal_prompt`), a 4096-token Sonnet call, and a battle-tested multi-strategy JSON parse. **Reuse that prompt+call+parse pattern.**
- **BUT it cannot be reused as-is**, because (a) it writes the **legacy weekly store** (`save_meal_plan`), not the wizard session's `confirmed_meals`; (b) its output slot shape (plain strings + `boys_help` combined) does **not** match the wizard's `confirmed_meals` entry shape (a dict with `protein`, `source`, `recipe_id`/`skip_shopping`, etc. — see Part F); (c) it has no concept of "only fill empty slots / never clobber confirmed" (Rule 4); (d) it ignores the wizard's `confirmed_what_to_plan`/`confirmed_complexity`/`planning_window`/`used_proteins`.
- **Cleanest path:** a new wizard generation endpoint (e.g. `/meal-wizard-generate`) that (1) borrows the `_build_meal_prompt`-style assembly + the `/meal-generate` Sonnet-call + robust-parse, but feeds it the **wizard session inputs** (Part F) and asks for the **`confirmed_meals` entry shape**; (2) on parse, **merges into `confirmed_meals` only for slots not already present** (Rule 4); (3) marks each generated entry `source:"lorenzo"` (Part F shows source tags already rendered in Step 4); (4) persists via `update_meal_wizard_session` + `recompute_used_proteins`. The model call/parse is reuse; the I/O target and slot shape are the rebuild.

---

# PART B — LORENZO'S SYSTEM-PROMPT TAIL (write-tag protocol, fake-pattern ban, never-fake-a-save)

From `build_lorenzo_context` (render_lorenzo.py). Head (475–557) establishes identity + roster + time-phase (**Rule 19 debt: roster is hardcoded here**). The behavioral tail VERBATIM (558–668):

```python
    lines += [
        "",
        "== YOUR DIRECT ACCESS (DO NOT DENY THIS) ==",
        "You have LIVE, READ-ONLY access to the data shown below in this prompt:",
        "  • THIS WEEK'S MEAL PLAN — every day, every slot, already loaded under '== CURRENT MEAL PLAN ==' below.",
        "  • PANTRY / FRIDGE / FREEZER inventory — under '== PANTRY ==' below.",
        "  • Standing meal rules, saved recipe cards, Lauren's capacity, John's status.",
        "You also have WRITE access. You can change the meal plan in real time by emitting these tags",
        "in your replies (the server parses them and saves to the same file Lauren sees in the Menu Planner):",
        "  • [MEAL_UPDATE:Day:slot]meal name[/MEAL_UPDATE]   ← edit a single slot",
        "  • [MEAL_UPDATE:Day:slot][/MEAL_UPDATE]            ← clear a slot",
        "  • [MEAL_UPDATE:Day:slot|recipe=rNNN]meal name[/MEAL_UPDATE]",
        "       ← same as above but ALSO links the slot to a saved recipe card.",
        "       Use the bracketed id from the SAVED RECIPE CARDS section. Only valid",
        "       on the food slots: breakfast, lunch, dinner, dessert, snacks, dad_lunch.",
        "       Linked slots auto-populate prep & cook times for the cook timer and let",
        "       Lauren tap straight through to the recipe from the meal-plan UI.",
        "  • [MEAL_UPDATE:Day:helpers]…[/MEAL_UPDATE]        ← assign kids",
        "  • [MEAL_UPDATE:Day:prep_time|cook_time|serve_time]…[/MEAL_UPDATE]",
        "  • [RECIPE_CARD:add]{json}[/RECIPE_CARD]           ← save a recipe to the library",
        "  • [RULE:add]rule text[/RULE]                      ← add a permanent meal rule",
        "  • <meal_constraint_update>…</meal_constraint_update>  ← rewrite all standing constraints",
        "  • <frol_update weekday=\"Monday\" person=\"JP\">     ← assign helper jobs / time blocks",
        "      4:30 PM: Brine the chicken in salt water",
        "      4:45 PM: Set the dinner table",
        "    </frol_update>",
        "      person= one of: JP, Joseph, Michael, Lauren (Mom), John, or Family.",
        "      Each line MUST be 'H:MM AM/PM: task text'. Saves directly to that",
        "      person's day_template — shows up immediately on their Day List and",
        "      in the FROL. Use this for kitchen helper assignments instead of",
        "      handing off to Izzy.",
        "",
        "🚫 FORBIDDEN — DO NOT EVER EMIT THESE FAKE PATTERNS (server ignores them, work is lost):",
        "    <function_calls>…</function_calls>",
        "    <invoke name=\"…\">…</invoke>",
        "    <parameter name=\"…\">…</parameter>",
        "    update_meal_plan({...}), function_call({...}), or any JSON RPC-looking call.",
        "  These are tool-use formats from your training. THIS APP DOES NOT USE THEM.",
        "  ONLY the bracket/XML tags listed above are real. If you emit anything else,",
        "  nothing saves and you will have lied to Lauren about it being 'done'.",
        "",
        "✅ WORKED EXAMPLE — adding a Helpers field for every day at once:",
        "  Just emit one tag per day, plain and simple, anywhere in your reply:",
        "    [MEAL_UPDATE:Monday:helpers]JP brines chicken; Joseph peels potatoes; Michael rinses broccoli[/MEAL_UPDATE]",
        "    [MEAL_UPDATE:Tuesday:helpers]Joseph reheats; Michael sets table[/MEAL_UPDATE]",
        "    [MEAL_UPDATE:Wednesday:helpers]…[/MEAL_UPDATE]",
        "    …and so on for Thu/Fri/Sat/Sun.",
        "  Same pattern for desserts: [MEAL_UPDATE:Monday:dessert]Apple slices with cinnamon[/MEAL_UPDATE]",
        "  The server strips these tags out of your reply before Lauren sees it, and",
        "  saves them to the meal plan file. Then say in plain English what you did.",
        "",
        "When Lauren asks for a multi-field update (e.g. 'add a helpers row AND a desserts",
        "row'), do BOTH in the same reply — emit one tag per (day, field) combination.",
        "Don't skip half her request.",
        "",
        "🛑 NEVER FAKE A SAVE — ASK INSTEAD:",
        "If Lauren asks you to save a meal but you're missing information needed to emit a",
        "valid [MEAL_UPDATE:Day:slot]meal[/MEAL_UPDATE] tag — i.e. you don't know which",
        "DAY (Monday/Tuesday/…/Sunday), don't know which SLOT (breakfast/lunch/dinner/",
        "dessert/snacks/dad_lunch/helpers/prep_time/cook_time/serve_time), or the meal",
        "name is ambiguous (e.g. 'the chicken thing', 'that soup we talked about', 'the",
        "usual') — DO NOT guess, DO NOT silently skip the save, and DO NOT confirm a",
        "save that didn't happen. Instead, ask ONE specific clarifying question to get",
        "the missing piece. Examples:",
        "  • Missing day:  'Which day should I put the chicken thighs on?'",
        "  • Missing slot: 'Is the lentil soup for lunch or dinner Tuesday?'",
        "  • Ambiguous meal: 'When you say the chicken thing — do you mean the brined",
        "    roast chicken or the sheet-pan thighs?'",
        "ABSOLUTE RULE: never write the words 'saved', 'done', 'updated', 'added',",
        "'got it' (in a save-confirmation sense), 'all set', or 'is now …' UNLESS the",
        "same reply also contains a valid [MEAL_UPDATE:…]…[/MEAL_UPDATE] tag (or one",
        "of the other real save tags listed above). Confirmations without a save tag",
        "are lies — the false-confirmation guard will flag them and Lauren will see a",
        "warning over your reply. Ask the clarifying question instead.",
```

(Then 633–668: "INFER MEAL CHANGES FROM CASUAL SPEECH" + a 4-step PROCESS requiring a yes/no confirmation *before* emitting a save tag, and the "NEVER tell Lauren you can't see the plan" block. Knowledge stack `== CURRENT MEAL PLAN ==` / `== PANTRY ==` / `== STANDING MEAL RULES ==` / `== CALENDAR THIS WEEK ==` are appended at 670–681.)

**Note for the "5 HARD RULES" block requested:** there is **no literally-labelled "5 HARD RULES" section** in `build_lorenzo_context`. The functionally-equivalent hard constraints are the three emoji blocks above: 🚫 FORBIDDEN fake patterns, 🛑 NEVER FAKE A SAVE, and the "ABSOLUTE RULE" save-word ban. If a later part of the file (past 704) carries a "HARD RULES" header it was not in this range; flagging so the build doesn't assume it exists.

**Implication for generation:** Lorenzo's whole save contract is **bracket-tag, one-slot, on-assent, anti-fake-confirmation** — built for *conversational* editing of the **legacy** store. A one-pass wizard generator should **not** reuse the `[MEAL_UPDATE]` tag pipeline (it writes the wrong store and is per-slot/confirmation-gated). Use a **structured-JSON** request instead (Part C / Part A4).

---

# PART C — OUTPUT PARSING (JSON vs bracket-tags)

## C1. `/lorenzo-chat` `_meal_rx` + apply block (app.py 5908–6036) VERBATIM
```python
                _meal_rx = _re.compile(
                    r'\[MEAL_UPDATE:([^:\]]+):([^|\]]+)(?:\|recipe=([^\]]+))?\]'
                    r'([\s\S]*?)\[\/MEAL_UPDATE\]',
                    _re.IGNORECASE
                )
                try:
                    from render_meals import MEAL_SLOT_SET as _DICT_OK_SLOTS
                except Exception:
                    _DICT_OK_SLOTS = {"breakfast","lunch","dinner","dessert","snacks","dad_lunch"}
                _meal_updates_found = []
                for _mm in _meal_rx.finditer(text):
                    _mday  = _mm.group(1).strip()
                    _mslot = _mm.group(2).strip().lower()
                    _mrid  = (_mm.group(3) or "").strip()
                    if _mrid and not _re.fullmatch(r"[^\s\[\]]+", _mrid):
                        print(f"[lorenzo MEAL_UPDATE] rejected malformed recipe_id: {_mrid!r}")
                        _mrid = ""
                    _mmeal = _mm.group(4).strip()
                    if _mday and _mslot:
                        _save_ok = False
                        try:
                            _wk = _planning_week_key()
                            _plan = load_meal_plan(_wk)
                            if _mmeal:
                                if _mrid and _mslot in _DICT_OK_SLOTS:
                                    _plan["days"].setdefault(_mday, {})[_mslot] = {
                                        "display":   _mmeal,
                                        "recipe_id": _mrid,
                                    }
                                    # ... (dinner timing/kid-helper auto-stamp, fill-blanks-only) ...
                                else:
                                    _plan["days"].setdefault(_mday, {})[_mslot] = _mmeal
                            else:
                                _plan["days"].setdefault(_mday, {}).pop(_mslot, None)
                            _plan["start"] = _plan.get("start") or _wk
                            save_meal_plan(_plan)
                            _save_ok = True
                        except Exception as _se:
                            print(f"[lorenzo MEAL_UPDATE] save failed for {_mday}/{_mslot}: {_se}")
                        if _save_ok:
                            _meal_updates_found.append((_mday, _mslot))
                # ... advance planning session, then SERVER-DRIVEN SAVE CONFIRMATION:
                if _meal_updates_found:
                    _total_meal_tags = sum(1 for _ in _meal_rx.finditer(text))
                    _any_meal_failed = _total_meal_tags > len(_meal_updates_found)
                    _saved_pairs = ", ".join(f"{_cd}/{_cs}" for (_cd, _cs) in _meal_updates_found)
                    _confirm_line = f"✓ Saved: {_saved_pairs}"
                    if _any_meal_failed:
                        _confirm_line += " | ⚠ Some updates could not be saved — the tag may have been malformed."
                    # ... strips model's own save-claim lines, appends deterministic _confirm_line ...
```

This is **bracket-tag parsing**, writing the **legacy** store per slot — not JSON, not the wizard session. Confirms the chat path is the wrong reuse target for one-pass JSON generation.

## C2. `_repair_and_parse_json` — confirmation it is nested-local ONLY (app.py 8424–8466) VERBATIM
```python
                def _repair_and_parse_json(raw_str):
                    """Try to parse JSON, repairing common LLM mistakes."""
                    # Attempt 1: as-is
                    try: return _pij.loads(raw_str)
                    except Exception: pass
                    # Attempt 2: remove trailing commas before } or ]
                    import re as _re2
                    fixed = _re2.sub(r',(\s*[}\]])', r'\1', raw_str)
                    try: return _pij.loads(fixed)
                    except Exception: pass
                    # Attempt 3: escape literal newlines inside string values
                    def _fix_newlines(s):
                        result, in_str, i = [], False, 0
                        while i < len(s):
                            c = s[i]
                            if c == '"' and (i == 0 or s[i-1] != '\\'):
                                in_str = not in_str
                                result.append(c)
                            elif in_str and c == '\n': result.append('\\n')
                            elif in_str and c == '\r': result.append('\\r')
                            elif in_str and c == '\t': result.append('\\t')
                            else: result.append(c)
                            i += 1
                        return ''.join(result)
                    fixed2 = _fix_newlines(fixed)
                    try: return _pij.loads(fixed2)
                    except Exception: pass
                    fixed3 = _re2.sub(r',(\s*[}\]])', r'\1', fixed2)
                    try: return _pij.loads(fixed3)
                    except Exception: pass
                    fixed4 = _re2.sub(r'("|\d|true|false|null|}|])\s*\n(\s*)("|\{|\[)', r'\1,\n\2\3', fixed3)
                    try: return _pij.loads(fixed4)
                    except Exception: pass
                    fixed5 = _re2.sub(r',(\s*[}\]])', r'\1', fixed4)
                    return _pij.loads(fixed5)  # raise if still broken
```
**Confirmed:** `_repair_and_parse_json` is defined ONLY at app.py 8424, **nested inside the plan-import handler** (its three call-sites are all in the same handler, 8493/8498/8505). `rg "def .*repair|def .*parse_json"` across `app.py`, `data_helpers.py`, `render_meals.py` finds **no module-level JSON-repair helper**. A new generation call cannot import/reuse it — it would have to either be promoted to module level (out of scope, touches the plan-import handler) or, more cheaply, copy the `/meal-generate` inline 3-strategy parse (C3).

## C3. Existing "ask Anthropic for JSON and parse a structured object" — the cleanest pattern to follow
**`/meal-generate` (A1)** is the cleanest precedent and the one a week-generation should mirror: it requests JSON-only output (via `_build_meal_prompt`'s "OUTPUT FORMAT (JSON only…)" instruction), then parses with the inline 3-strategy block (```json fence → outermost `{...}` → trailing-comma strip). The plan-import handler (8412+) is a second, heavier precedent (system prompt + `_repair_and_parse_json` 6-attempt repair + outermost-brace scan + `_safe_empty_parsed` fallback) — more robust but tangled into that handler. **For a week generator, copy `/meal-generate`'s pattern** (lighter, self-contained, already proven on this exact "7-day meal JSON" shape).

---

# PART D — KNOWLEDGE-STACK HELPER OUTPUT SHAPES (render_lorenzo.py)

These are what a generation prompt can lean on (all return **strings**, fail-soft).

### `_get_inventory` (197–208) — returns e.g.:
```
Fridge: eggs, butter, 2 lb ground beef, spinach
Freezer: chicken thighs, salmon fillets, peas
Pantry: rice, black beans, pasta, canned tomatoes
```
(`use_soon` is **NOT** included here — it's read separately by `_build_meal_prompt`/inventory; see Part F. Falls back to `"No inventory recorded."` / `"Inventory unavailable."`.)

### `_get_saved_recipes` (210–246) — returns e.g.:
```
Saved recipe cards (2 total).
Each entry starts with its recipe id in [brackets]. To link a meal-plan
slot to one of these recipes, use [MEAL_UPDATE:Day:slot|recipe=ID]name[/MEAL_UPDATE].
  - [r001] Brined Roast Chicken (Serves 6 | Prep 20 min | Cook 90 min): chicken, kosher salt, butter, lemon, thyme, garlic...
  - [r014] Lentil Soup (Serves 8 | Prep 15 min | Cook 45 min): lentils, carrots, onion, celery, broth, cumin
```
(Each line prefixed with the recipe id in `[brackets]`; first 5 ingredients previewed. Fallbacks: `"No recipe cards saved yet."` / `"Recipe cards unavailable."`)

### `_get_meal_constraints` (248–280) — returns e.g.:
```
No pork. Friday meatless. Keep dinners under 45 min on co-op days.

Standing meal rules:
- Tuesday is leftovers day
- Fish fry every Friday
- One batch soup at the start of the week
```
(Concatenates free-text `family_constraints.meal_constraints` + `data/meal_rules.json` list (PRIMARY store) + legacy `lorenzo_rules`. Fallback: `"No standing meal constraints recorded."`)

### `_get_current_meal_plan(iso)` (66–195) — returns a multi-section string: a header (week start, last-saved time, AI-generated flag, "authoritative" note), then `Day: Breakfast: … | Dinner: … [recipe rNNN]` per day, then a `== GAPS IN THIS WEEK'S PLAN ==` audit listing blank food/meta slots, vague "leftovers", malformed days. Reads the **legacy** store via `_planning_week_key()`/`load_meal_plan`. Fallback: `"Could not load meal plan: {e}"`. (This describes the *legacy* plan, not the wizard session — relevant only as "what's already on the fridge card," not as the wizard's confirmed set.)

### `_get_calendar_this_week(iso)` (336–385) — returns e.g.:
```
Today (Jun 29, 2026-06-29):
  - 09:00-10:00 Co-op drop-off — for JP
Thursday (Jul 2, 2026-07-02):
  - 17:00 Soccer practice — for Joseph
```
(7-day merged/deduped event listing via `data_helpers.get_merged_calendar_events`. Fallbacks: `"No events scheduled in the next 7 days."` / `"Calendar unavailable."`) — useful for "busy night → sheet-pan" shaping.

---

# PART E — AI CALL PLUMBING

**No single shared "call the model" helper exists app-wide.** Anthropic calls are inline at each site (`urllib.request` in render_*.py; `requests` in some app.py handlers). The closest thing to a shared helper is **`render_ai_daily._call_claude`** (used only by the `render_ai_daily` planners — daily schedule, meal suggestions, school plan, examen).

`_call_claude` (render_ai_daily.py 26–44) VERBATIM:
```python
def _call_claude(prompt: str, max_tokens: int = 600) -> str:
    import urllib.request as _ur
    key = _api_key()
    if not key:
        raise ValueError("No API key found. Add your Anthropic API key in Settings → AI & Planning.")
    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = _ur.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={"Content-Type":"application/json","x-api-key":key,
                 "anthropic-version":"2023-06-01"}
    )
    with _ur.urlopen(req, timeout=25) as resp:
        result = json.loads(resp.read())
    return result["content"][0]["text"].strip()
```

**Model / max_tokens / timeout in use:**
| Site | Model | max_tokens | timeout |
|---|---|---|---|
| `/meal-generate` (the real week generator, A1) | **claude-sonnet-4-20250514** | **4096** | **90s** |
| `ai_meal_plan` via `_call_claude` (A2) | claude-haiku-4-5-20251001 | 400 | 25s |
| `_call_claude` default | claude-haiku-4-5-20251001 | 600 | 25s |
| `/lorenzo-chat` | claude-haiku-4-5-20251001 | 1500 | (per-site) |
| plan-import handler | (sonnet/opus variants seen 3425/3445) | 4000 | 90s |

**For a whole-week wizard generation:** mirror `/meal-generate`'s real numbers — **Sonnet-class model, ~4096 max_tokens, ~90s timeout**. `_call_claude`'s Haiku@600/25s is far too small/short for a 7-day structured plan and is Haiku (the chat tier). Do not route a week-generator through `_call_claude`.

---

# PART F — SESSION INPUTS THE GENERATION WILL CONSUME

Session is read via `data_helpers.load_meal_wizard_session()` (returns `{}` when none) and written via `update_meal_wizard_session(updates)` / `save_meal_wizard_session(session)` (both `safe_save_json`, Rule 5). Confirmed keys + where each is set, with realistic examples:

- **`confirmed_what_to_plan`** — list of slot kinds chosen in Step 3 (set app.py ~10731). e.g. `["dinner", "breakfast"]`. Step 4 reads it at render_meal_wizard_step4.py 384.
- **`confirmed_complexity`** — string (set ~10732). e.g. `"normal"` (Step 3 default at render_meal_wizard_step3.py 302; labels via `_S3_CX_LABELS`).
- **`planning_window`** — `{"start_iso","end_iso"}` (set ~10692/10733). e.g. `{"start_iso":"2026-06-29","end_iso":"2026-07-05"}`. Step 4 reads at 383.
- **`confirmed_inventory`** — combined inventory string (set ~10657). e.g. `"Fridge: eggs, spinach\nFreezer: chicken thighs\nPantry: rice"`. Step 4 reads it but **intentionally leaves it unused** (render_meal_wizard_step4.py 386–388: `_inventory = ... # read-but-unused`).
- **`use_soon_items`** — set ~10658 from `inv.get("use_soon","")`. e.g. `"spinach, strawberries"`. (The generation should surface these first — same intent as `_build_meal_prompt`'s "USE SOON (priority)".)
- **`confirmed_meals`** — **the dict the generation must NOT overwrite (Rule 4).** Keyed `"YYYY-MM-DD::slot"` (per `get_confirmed_meals` docstring, data_helpers 3320). Set/merged at app.py 10725/10729/10734, 10801–10805 (`s4Keep`), 10837–10841 (`s4Change`). Each entry is a **dict** carrying at least `protein`, `source` (`manual`/`lorenzo`/`prefill`), and recipe linkage (`recipe_id` / `recipe_on_request` / `skip_shopping`); pre-filled past meals are written **locked + off-shopping** (app.py 10701+; verify_meal_wizard_step3 asserts "prefilled meal has correct locked/off-shopping shape"). Step 4's harness confirms rendered cues: `source tags (manual/lorenzo/prefill) present`, `recipe_id → 'Recipe attached'`, `recipe_on_request → 'No recipe needed'`, half-confirmed → `'Recipe: not set yet'`, `skip_shopping → 'off shopping list'`.
- **`used_proteins`** — de-duped lowercase protein list, **derived** from `confirmed_meals` via `recompute_used_proteins(confirmed_meals)` (data_helpers 3327–3345); persisted alongside `confirmed_meals` (app.py 10805/10841). e.g. `["chicken","beef"]`. Reads ONLY each entry's `protein` field (food cooked just for the littles lives in `ingredients`, excluded). Generation should pass this in so the week doesn't repeat proteins, and must `recompute_used_proteins` after merging new meals.

**How to tell which slots are ALREADY confirmed (so generation fills only empties, never clobbers — Rule 4):**
- A slot is "taken" iff its `"YYYY-MM-DD::slot"` key **exists in `confirmed_meals`**. Build the target slot set from `planning_window` (each date in `[start_iso, end_iso]`) × `confirmed_what_to_plan` (the slot kinds), then **filter out any key already present in `confirmed_meals`** — generate only for the remainder.
- `prefill`-sourced entries are already locked/off-shopping; they are present in `confirmed_meals` and so are naturally skipped by the "key exists" test. Do **not** special-case-overwrite them.
- After generating, **merge with existing-wins** (`{**generated, **confirmed_meals}` semantics — confirmed always wins), tag new entries `source:"lorenzo"`, then persist via `update_meal_wizard_session({"confirmed_meals":..., "used_proteins": recompute_used_proteins(...)})`.

---

## Bottom line
- **A usable generator exists (`/meal-generate`): reuse its prompt-assembly + Sonnet@4096/90s call + 3-strategy JSON parse, but NOT its write target or slot shape.** It writes the legacy weekly store as plain-string slots; the wizard needs `confirmed_meals` dict-entries merged additively.
- `ai_meal_plan` (suggestions-only, Haiku@400, no write) and the `[MEAL_UPDATE]` chat path (per-slot, legacy store, confirmation-gated) are **not** reuse targets for one-pass JSON generation.
- `_repair_and_parse_json` is a **nested local** in the plan-import handler only; no module-level repair helper — copy `/meal-generate`'s inline parse instead.
- The generation must read `confirmed_what_to_plan / confirmed_complexity / planning_window / confirmed_inventory / use_soon_items / used_proteins`, **fill only `"date::slot"` keys not already in `confirmed_meals`** (Rule 4), tag new entries `source:"lorenzo"`, and persist via `update_meal_wizard_session` + `recompute_used_proteins` (Rule 5). Roster facts must come from config, not a copy of `build_lorenzo_context`'s hardcoded list (Rule 19).
