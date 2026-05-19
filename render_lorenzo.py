"""
render_lorenzo.py — Lorenzo, AI personal chef for the McAdams family.

Named after Saint Lawrence (San Lorenzo), patron saint of cooks — martyred on
a gridiron in 258 AD and reputed to have said "Turn me over, I'm done on this
side." Warm, skilled, and never rattled by the heat.

Lorenzo knows this family's kitchen, schedule, inventory, and constraints.
Full features: voice input, read-aloud TTS, image attachment, rule saving,
temp vs. permanent adjustment distinction, and "Hey Lorenzo" wake word.

API: POST /lorenzo-chat     → Claude response
     POST /lorenzo-rule-save → save permanent rule to meal_constraints
"""
import json
import os
from datetime import date, timedelta
from html import escape
from companion_handoffs import companion_system_block, handoff_js, frol_context_block, frol_edit_instructions

try:
    from zoneinfo import ZoneInfo
    _EASTERN = ZoneInfo("America/New_York")
except ImportError:
    import pytz
    _EASTERN = pytz.timezone("America/New_York")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _today_eastern() -> date:
    from datetime import datetime
    return datetime.now(_EASTERN).date()

def _hour_eastern() -> int:
    from datetime import datetime
    return datetime.now(_EASTERN).hour

def _ej(s: str) -> str:
    return json.dumps(str(s))

def _load_app_settings() -> dict:
    path = "data/app_settings.json"
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _load_lorenzo_history_safe() -> list:
    try:
        from data_helpers import load_lorenzo_history
        return load_lorenzo_history()
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Context builders
# ─────────────────────────────────────────────────────────────────────────────

def _get_current_meal_plan(iso: str) -> str:
    try:
        import os as _os, datetime as _dt2
        from render_meals import (
            load_meal_plan, _plan_path, _week_key, _planning_week_key,
            slot_display_text, slot_recipe_id,
        )
        # Use the SAME week the fridge-card print page shows (Mon–Thu = this
        # week; Fri/Sat/Sun = next week). Otherwise Lorenzo and the print
        # card disagree about which file is "the plan."
        _active_wk = _planning_week_key()
        plan = load_meal_plan(_active_wk)
        days_data = plan.get("days", {})
        # Resolve the actual file path that load_meal_plan ended up reading.
        _start = plan.get("start") or _active_wk
        _path  = _plan_path(_start)
        if _os.path.exists(_path):
            try:
                from zoneinfo import ZoneInfo as _ZI
                _tz = _ZI("America/New_York")
            except Exception:
                _tz = None
            _mtime_utc = _dt2.datetime.fromtimestamp(_os.path.getmtime(_path), tz=_dt2.timezone.utc)
            _mtime = _mtime_utc.astimezone(_tz) if _tz else _mtime_utc
            _now   = _dt2.datetime.now(tz=_tz) if _tz else _dt2.datetime.now(tz=_dt2.timezone.utc)
            _delta = _now - _mtime
            _hrs   = _delta.total_seconds() / 3600
            if _hrs < 1:
                _ago = f"{int(_delta.total_seconds()/60)} minutes ago"
            elif _hrs < 24:
                _ago = f"about {int(_hrs)} hours ago"
            else:
                _ago = f"{int(_hrs/24)} days ago"
            _saved = _mtime.strftime("%Y-%m-%d %I:%M %p %Z") + f" ({_ago})"
        else:
            _saved = "never (no file on disk)"
        _was_generated = "YES — by the AI generator" if plan.get("generated") else "no — manually edited or empty"
        if not days_data:
            return (f"No meal plan found for the week of {_start}. "
                    f"(File path: {_path}, last saved: {_saved}.)")
        lines = [
            f"This week's meal plan (week starting {_start}).",
            f"  Last saved to disk: {_saved}.  AI-generated: {_was_generated}.",
            f"  This is the CURRENT plan — there is no newer version. "
            f"Treat it as authoritative.",
            "",
        ]
        # Track gaps for the audit section
        try:
            from render_meals import DAYS as _CANON_DAYS
        except Exception:
            _CANON_DAYS = ("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")
        food_slots = ("breakfast", "lunch", "dinner", "dessert", "snacks", "dad_lunch")
        meta_slots = ("prep_time", "cook_time", "serve_time", "helpers")
        # Some legacy/alternate keys mean "filled" for a given canonical slot.
        slot_aliases = {"helpers": ("helpers", "boys_help")}
        gaps_food: dict = {s: [] for s in food_slots}
        gaps_meta: dict = {s: [] for s in meta_slots}
        vague_leftovers: list = []
        malformed_days: list = []
        for day_name in _CANON_DAYS:
            slots = days_data.get(day_name)
            if not isinstance(slots, dict):
                malformed_days.append(day_name)
                for s in food_slots: gaps_food[s].append(day_name)
                for s in meta_slots: gaps_meta[s].append(day_name)
                continue
            parts = []
            for slot in food_slots:
                raw = slots.get(slot, "")
                val = slot_display_text(raw)
                rid = slot_recipe_id(raw)
                if val:
                    rendered = f"{slot.capitalize()}: {val}"
                    if rid:
                        rendered += f"  [recipe {rid}]"
                    parts.append(rendered)
                    if val.lower() in ("leftovers", "leftover"):
                        vague_leftovers.append(f"{day_name} {slot}")
                else:
                    gaps_food[slot].append(day_name)
            for slot in meta_slots:
                keys_to_check = slot_aliases.get(slot, (slot,))
                filled = False
                for k in keys_to_check:
                    raw = slots.get(k, "")
                    v = (raw or "").strip() if isinstance(raw, str) else raw
                    if v:
                        filled = True
                        break
                if not filled:
                    gaps_meta[slot].append(day_name)
            if parts:
                lines.append(f"  {day_name}: " + " | ".join(parts))
        # Append gap audit
        lines += ["", "== GAPS IN THIS WEEK'S PLAN (proactively offer to fill) =="]
        any_gap = False
        for slot, days in gaps_food.items():
            if days:
                any_gap = True
                if len(days) == 7:
                    lines.append(f"  • {slot}: BLANK every day (Mon–Sun)")
                else:
                    lines.append(f"  • {slot}: missing on {', '.join(days)}")
        for slot, days in gaps_meta.items():
            if days:
                any_gap = True
                if len(days) == 7:
                    lines.append(f"  • {slot}: BLANK every day (Mon–Sun)")
                else:
                    lines.append(f"  • {slot}: missing on {', '.join(days)}")
        if vague_leftovers:
            any_gap = True
            lines.append(f"  • vague 'leftovers' entries (specify which dish): "
                         + ", ".join(vague_leftovers))
        if malformed_days:
            any_gap = True
            lines.append(f"  • malformed/missing day data (whole day blank): "
                         + ", ".join(malformed_days))
        if not any_gap:
            lines.append("  (none — every field on every day is filled in)")
        lines += [
            "",
            "When Lauren mentions printing the fridge card, reviewing the week, or 'is",
            "anything missing', volunteer the gaps above and offer concrete fills using",
            "[MEAL_UPDATE:Day:slot] tags. Don't make her ask twice.",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Could not load meal plan: {e}"

def _get_inventory() -> str:
    try:
        from render_meals import load_inventory
        inv = load_inventory()
        parts = []
        for section in ("fridge", "freezer", "pantry"):
            val = inv.get(section, "").strip()
            if val:
                parts.append(f"{section.capitalize()}: {val}")
        return "\n".join(parts) if parts else "No inventory recorded."
    except Exception:
        return "Inventory unavailable."

def _get_saved_recipes() -> str:
    """Return a compact summary of saved recipe cards for the system prompt.
    Each line begins with the recipe id in square brackets so Lorenzo can
    drop it straight into a [MEAL_UPDATE:Day:slot|recipe=ID] tag without
    guessing or hallucinating an id."""
    try:
        from data_helpers import load_recipes
        recipes = load_recipes()
        if not recipes:
            return "No recipe cards saved yet."
        lines = [
            f"Saved recipe cards ({len(recipes)} total).",
            "Each entry starts with its recipe id in [brackets]. To link a meal-plan",
            "slot to one of these recipes, use [MEAL_UPDATE:Day:slot|recipe=ID]name[/MEAL_UPDATE].",
        ]
        for r in recipes:
            rid       = r.get("id", "")
            name      = r.get("name", "Unknown")
            servings  = r.get("servings", "")
            prep      = r.get("prep_time", "")
            cook      = r.get("cook_time", "")
            ingr_raw  = r.get("ingredients", [])
            # Handle both list-of-strings and legacy plain-string formats
            if isinstance(ingr_raw, list):
                ingr_preview = ", ".join(ingr_raw[:5]) + ("..." if len(ingr_raw) > 5 else "")
            else:
                ingr_str = str(ingr_raw)
                ingr_preview = ingr_str[:80] + ("..." if len(ingr_str) > 80 else "")
            timing    = " | ".join(x for x in [f"Serves {servings}" if servings else "",
                                               f"Prep {prep}" if prep else "",
                                               f"Cook {cook}" if cook else ""] if x)
            id_tag    = f"[{rid}] " if rid else ""
            lines.append(f"  - {id_tag}{name}" + (f" ({timing})" if timing else "") +
                         (f": {ingr_preview}" if ingr_preview else ""))
        return "\n".join(lines)
    except Exception:
        return "Recipe cards unavailable."

def _get_meal_constraints() -> str:
    try:
        import os as _os2
        parts = []
        # 1. Free-form constraints text from settings (used by meal_constraint_update tag)
        settings = _load_app_settings()
        fc = settings.get("family_constraints", {})
        text = fc.get("meal_constraints", "").strip()
        if text:
            parts.append(text)
        # 2. Standing rules from meal_rules.json — the PRIMARY rule store
        RULES_FILE = "data/meal_rules.json"
        if _os2.path.exists(RULES_FILE):
            try:
                import json as _jm
                rules = _jm.load(open(RULES_FILE))
                if isinstance(rules, list) and rules:
                    rule_lines = [
                        f"- {r['rule']}"
                        for r in rules
                        if isinstance(r, dict) and r.get("rule", "").strip()
                    ]
                    if rule_lines:
                        parts.append("Standing meal rules:\n" + "\n".join(rule_lines))
            except Exception:
                pass
        # 3. Legacy lorenzo_rules list in settings (backward compat)
        lr = fc.get("lorenzo_rules", [])
        if isinstance(lr, list) and lr:
            parts.append("Additional rules:\n" + "\n".join(f"- {r}" for r in lr))
        return "\n\n".join(parts) if parts else "No standing meal constraints recorded."
    except Exception:
        return "Constraints unavailable."

def _get_lucy_capacity(iso: str) -> str:
    try:
        from render_morning_anchor import _get_anchor_state
        anchor = _get_anchor_state(iso)
        cap = anchor.get("capacity", "").strip().lower()
        if cap == "high":
            return "HIGH — full energy, Lauren can handle more involved cooking."
        elif cap == "medium":
            return "MEDIUM — moderate energy, prefer meals that don't require too much hands-on time."
        elif cap == "low":
            return "LOW — limited energy. Favor simple, minimal-effort meals."
        return "Not set for today."
    except Exception:
        return "Capacity data unavailable."

def _get_john_status(iso: str) -> str:
    try:
        from render_morning_anchor import _get_anchor_state
        anchor = _get_anchor_state(iso)
        status = anchor.get("john_status", "").strip()
        if not status:
            return ""
        if status.lower() in ("wfh", "working from home", "home office", "work from home"):
            return "John is WFH today — he can help with lunch prep or keeping James occupied."
        elif "travel" in status.lower() or "away" in status.lower():
            return "John is traveling — Lauren is solo today. Keep meal complexity low."
        return f"John: {status}"
    except Exception:
        return ""

def _get_liturgical_note(iso: str) -> str:
    try:
        from datetime import date as _d
        d = _d.fromisoformat(iso)
        notes = []
        if d.weekday() == 4:
            easter = _get_easter(d.year)
            lent_start = easter - timedelta(days=46)
            lent_end   = easter - timedelta(days=1)
            if lent_start <= d <= lent_end:
                notes.append("FRIDAY IN LENT — no meat. Fish, eggs, legumes, or meatless dishes only.")
            else:
                notes.append("Friday — encourage a small act of penance (meatless meal preferred).")
        easter = _get_easter(d.year)
        ash_wed  = easter - timedelta(days=46)
        good_fri = easter - timedelta(days=2)
        if d == ash_wed:
            notes.append("ASH WEDNESDAY — full fast and abstinence. No meat, very simple meals only.")
        if d == good_fri:
            notes.append("GOOD FRIDAY — strict fast and abstinence. No meat. Very simple meals.")
        return " | ".join(notes) if notes else ""
    except Exception:
        return ""

def _get_calendar_this_week(iso: str) -> str:
    """Return a compact text listing of events for the next 7 days starting at iso.
    Uses expand_local_events_for_range; safe-fallback string on any error."""
    try:
        from datetime import date as _dc, timedelta as _td
        from data_helpers import expand_local_events_for_range
        _today = _dc.fromisoformat(iso)
        _end   = _today + _td(days=6)
        _evs   = expand_local_events_for_range(_today.isoformat(), _end.isoformat())
        if not _evs:
            return "No events scheduled in the next 7 days."
        by_date = {}
        for e in _evs:
            _start    = e.get("start", "") or ""
            _date_str = _start[:10] if _start else ""
            if not _date_str:
                continue
            by_date.setdefault(_date_str, []).append(e)
        out_lines = []
        for offset in range(7):
            d  = _today + _td(days=offset)
            ds = d.isoformat()
            if ds not in by_date:
                continue
            if offset == 0:
                _label = "Today"
            elif offset == 1:
                _label = "Tomorrow"
            else:
                _label = d.strftime("%A")
            _date_label = d.strftime("%b %-d")
            out_lines.append(f"{_label} ({_date_label}, {ds}):")
            for e in by_date[ds]:
                title = (e.get("title") or "(untitled)").strip() or "(untitled)"
                st = (e.get("start_time") or "").strip()
                et = (e.get("end_time") or "").strip()
                if st and et:
                    _time_str = f"{st}-{et} "
                elif st:
                    _time_str = f"{st} "
                elif e.get("all_day"):
                    _time_str = "(all day) "
                else:
                    _time_str = ""
                _assigned = e.get("assigned_to") or []
                if isinstance(_assigned, list) and _assigned:
                    _who_join = ", ".join(str(x) for x in _assigned if str(x).strip())
                    _who_str  = f" — for {_who_join}" if _who_join else ""
                else:
                    _who_str = ""
                out_lines.append(f"  - {_time_str}{title}{_who_str}")
        return "\n".join(out_lines) if out_lines else "No events scheduled in the next 7 days."
    except Exception:
        return "Calendar unavailable."


def _get_easter(year: int) -> date:
    a = year % 19; b = year // 100; c = year % 100
    d = b // 4;    e = b % 4;       f = (b + 8) // 25
    g = (b - f + 1) // 3;           h = (19 * a + b - d - g + 15) % 30
    i = c // 4;    k = c % 4;       l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day   = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _get_planning_session_block() -> str:
    """Return the planning session section to inject into the system prompt when active."""
    try:
        from data_helpers import load_planning_session, PLAN_DAYS, PLAN_SLOTS
        session = load_planning_session()
        if not session.get("active"):
            return ""
        days  = session.get("days",  PLAN_DAYS)
        slots = session.get("slots", PLAN_SLOTS)
        di    = session.get("current_day_idx",  0)
        si    = session.get("current_slot_idx", 0)
        week_iso  = session.get("week_iso", "this week")
        cur_day   = days[di]  if di  < len(days)  else "?"
        cur_slot  = slots[si] if si  < len(slots) else "?"
        pos       = di * len(slots) + si
        total     = len(days) * len(slots)
        pct_done  = round(pos / total * 100)

        # What has already been planned this session?
        try:
            from render_meals import load_meal_plan, slot_display_text, slot_recipe_id
            plan  = load_meal_plan(week_iso)
            filled = []
            for d in days:
                for s in slots:
                    raw = plan.get("days", {}).get(d, {}).get(s, "")
                    val = slot_display_text(raw)
                    rid = slot_recipe_id(raw)
                    if val:
                        suffix = f"  [recipe {rid}]" if rid else ""
                        filled.append(f"  {d} {s}: {val}{suffix}")
            filled_text = "\n".join(filled) if filled else "  (nothing filled in yet)"
        except Exception:
            filled_text = "  (meal plan unavailable)"

        lines = [
            "",
            "== ACTIVE WEEKLY MEAL PLANNING SESSION ==",
            f"You and Lauren are planning meals for the week of {week_iso} together,",
            "one slot at a time, in a warm, conversational back-and-forth.",
            "",
            f"CURRENT SLOT: {cur_day} — {cur_slot.capitalize()}",
            f"Progress: {pos} of {total} slots planned ({pct_done}%)",
            "",
            "SLOTS ALREADY FILLED IN THIS WEEK:",
            filled_text,
            "",
            "HOW THE PLANNING SESSION WORKS:",
            f"1. Your immediate focus is {cur_day} {cur_slot.capitalize()}.",
            "2. Open with ONE focused question — anything to use up? Any cravings? Any ideas?",
            "3. Draw on the inventory, saved recipes, and her energy level.",
            "4. Make a concrete suggestion. Discuss until you agree.",
            f"5. When agreed, save it: [MEAL_UPDATE:{cur_day}:{cur_slot}]meal name[/MEAL_UPDATE]",
            "   Then say a brief transition line like 'Great — moving on to ...'",
            "   and ask your ONE opening question for the next slot.",
            "6. If Lauren wants to skip a slot ('we don't do breakfast' / 'JP handles that'),",
            "   save it as empty: [MEAL_UPDATE:{cur_day}:{cur_slot}][/MEAL_UPDATE]",
            "   and move on without making a fuss.",
            "7. After each full day, note it briefly: 'Sunday is set. On to Monday.'",
            "8. When the week is complete, give a warm one-paragraph summary of the week",
            "   and wish Lauren good cooking.",
            "",
            "TONE: This is two people who enjoy food, planning together. Be warm, efficient,",
            "and practical. Celebrate good choices. Don't repeat the rules to Lauren —",
            "just execute them naturally.",
            "CRITICAL: One question at a time. Move forward with purpose.",
        ]
        return "\n".join(lines)
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────

def build_lorenzo_context(iso: str, weekday: str, date_label: str) -> str:
    from datetime import datetime as _dt
    meal_plan   = _get_current_meal_plan(iso)
    inventory   = _get_inventory()
    constraints = _get_meal_constraints()
    capacity    = _get_lucy_capacity(iso)
    john_status = _get_john_status(iso)
    liturny     = _get_liturgical_note(iso)
    saved_recipes = _get_saved_recipes()
    calendar_week = _get_calendar_this_week(iso)

    # Current Eastern time — used for situational awareness
    _now_e = _dt.now(_EASTERN)
    _h     = _now_e.hour
    _time_str = _now_e.strftime("%-I:%M %p")   # e.g. "4:35 PM"

    if _h < 6:
        _phase = (f"It is {_time_str} — very early morning. The family is asleep. "
                  "If Lauren is up now, keep suggestions extremely simple or overnight-prep focused.")
    elif _h < 10:
        _phase = (f"It is {_time_str} — morning. Breakfast is the immediate priority. "
                  "Think ahead to lunch and whether any dinner prep can start today.")
    elif _h < 12:
        _phase = (f"It is {_time_str} — late morning. Breakfast is done. "
                  "Lunch planning is relevant; also a good time to think through the dinner plan.")
    elif _h < 14:
        _phase = (f"It is {_time_str} — midday / lunchtime. "
                  "Focus on what's for lunch right now, and start firming up the dinner plan.")
    elif _h < 17:
        _phase = (f"It is {_time_str} — afternoon. Dinner is the main focus. "
                  "Lauren needs a concrete dinner plan. JP could start prep in 1-2 hours.")
    elif _h < 19:
        _phase = (f"It is {_time_str} — dinner prep time. This is crunch hour. "
                  "Dinner needs to be executable RIGHT NOW. Give her the fastest viable path.")
    elif _h < 21:
        _phase = (f"It is {_time_str} — dinner is happening or just finished. "
                  "Focus on tomorrow's planning, leftovers, or overnight prep if relevant.")
    else:
        _phase = (f"It is {_time_str} — evening. Dinner is done. "
                  "Help with tomorrow's planning, overnight slow-cooker ideas, or shopping lists.")

    lines = [
        "You are Lorenzo — the McAdams family's personal AI chef.",
        "",
        "You are named after Saint Lawrence (San Lorenzo), the patron saint of cooks,",
        "who reportedly joked 'Turn me over — I'm done on this side' while being martyred",
        "on a gridiron. You carry his spirit: warmth, good humor, and calm under pressure.",
        "",
        f"CRITICAL — TODAY'S DATE: {weekday}, {date_label} ({iso}).",
        "This is authoritative. If any earlier messages in this conversation mention a different",
        "date, those messages are from a previous session. Always use the date above.",
        f"CURRENT TIME: {_phase}",
        "",
        "== THE McADAMS FAMILY ==",
        "Lauren (Mom) — the one you work for. A homeschooling Catholic wife and mother.",
        "  She manages the household, plans school days, and coordinates everything.",
        "  She is your partner in the kitchen — you plan, she executes (with the boys' help).",
        "John (Dad) — husband, works outside the home (or occasionally WFH).",
        "JP — 14 years old. Oldest son. Kitchen Role A: your best kitchen asset.",
        "  He can cook full meals, handle the stove unsupervised, and lead dinner prep.",
        "  Give him real ownership of meals. He rises to the challenge.",
        "Joseph — 12 years old. Kitchen Role B: excellent helper and sous chef.",
        "  Can prep, assemble, and run simple recipes with light guidance.",
        "Michael — 5 years old. Loves to help. Assign safe, simple tasks.",
        "  Stirring, washing vegetables, pouring measured ingredients — his specialty.",
        "James — 13 months old. In the high chair during meal prep. Not cooking.",
        "",
        "== KITCHEN CREW ==",
        "JP (14) — Role A: can lead full meals, unsupervised on stove. Give him real responsibility.",
        "Joseph (12) — Role B: skilled helper, can run simple recipes with light guidance.",
        "Michael (5) — one safe small job per meal. Stirring, washing, pouring.",
        "James (13 months) — high chair only.",
        "",
        "== TODAY'S HOUSEHOLD STATUS ==",
        f"Lauren's capacity today: {capacity}",
    ]

    if john_status:
        lines.append(john_status)

    if liturny:
        lines += ["", f"LITURGICAL NOTE: {liturny}"]

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
        "",
        "🍳 INFER MEAL CHANGES FROM CASUAL SPEECH:",
        "Lauren will rarely say 'please update the meal plan' in formal terms. She'll just",
        "make a statement about reality:",
        "  • 'No pizza tonight, we have catfish instead'",
        "  • 'We didn't make the soup'",
        "  • 'Skipping the roast — kids want grilled cheese'",
        "  • 'JP made tacos for lunch instead of the leftovers'",
        "  • 'The chili didn't happen, we ordered out'",
        "Treat every such statement as a meal-plan UPDATE INTENT. Do NOT ignore it, do NOT",
        "treat it as small talk, and NEVER make her repeat herself with formal syntax.",
        "",
        "PROCESS:",
        "1. Check the '== CURRENT MEAL PLAN ==' section above to find the most likely",
        "   day + slot the statement refers to. Use the current date/time, today's day-",
        "   of-week, the meal currently in each slot, and the time-of-day phase to pick",
        "   the best match. ('tonight' → today's dinner; 'lunch' → today's lunch; the",
        "   name of a meal already on the plan → that exact slot.)",
        "2. If you're CONFIDENT about the day and slot, propose the specific change as",
        "   a single yes/no question — and DO NOT emit a save tag until she says yes.",
        "   Example: 'Should I update Saturday lunch from pizza to leftover catfish?'",
        "   Example: 'Want me to clear Tuesday dinner since the soup didn't happen?'",
        "3. If you're NOT confident which slot she means (multiple matches, or the meal",
        "   she named isn't on the plan anywhere), ask ONE specific clarifying question",
        "   per the NEVER FAKE A SAVE rule above.",
        "4. When Lauren confirms ('yes', 'yep', 'do it', 'go ahead', 'sounds good',",
        "   'sure', a thumbs-up, or any clear assent), THEN emit the [MEAL_UPDATE:…]",
        "   tag in your next reply and confirm in plain English. Until then, no save.",
        "",
        "CRITICAL — NEVER tell Lauren you can't see her meal plan, can't access the file system,",
        "can't read other pages, that she needs to paste anything, or that 'Izzy needs to",
        "process' your changes. You write directly to the same files Izzy reads. When the",
        "user accepts your suggestions, just emit the tags above silently in your reply —",
        "the server parses them. Don't show the raw tag syntax as 'code' or explain it as",
        "something that needs to be added to the codebase. Confirm what you did in plain English.",
        "If you genuinely don't see meal data in the section below, say 'No meal plan exists for",
        "this week yet — want me to draft one?' — but never claim you lack the ability to read it.",
        "",
        "== CURRENT MEAL PLAN ==",
        meal_plan,
        "",
        "== PANTRY / FRIDGE / FREEZER ==",
        inventory,
        "",
        "== STANDING MEAL RULES & CONSTRAINTS ==",
        constraints,
        "",
        "== CALENDAR THIS WEEK ==",
        calendar_week,
        "",
        "USE THE CALENDAR TO SHAPE MEAL SUGGESTIONS:",
        "Look at the events above and let them drive your meal recommendations:",
        "  • Busy evening (event after 4 PM, kid practice, late return) → suggest slow-cooker,",
        "    sheet-pan, or fully prep-ahead meals so dinner is hands-off when she gets home.",
        "  • Special occasion or celebration (birthday, feast day, anniversary, guests over)",
        "    → suggest a more festive meal — anchor protein, dessert, sides — and offer to",
        "    add helpers and serve_time so the timeline lines up with the event.",
        "  • Party / potluck / gathering Lauren is attending → proactively suggest what to",
        "    bring (an appetizer, a dessert, a side that travels well) and add it to that",
        "    day's slot if she agrees.",
        "  • Early morning commitment (Mass, appointment, drop-off before 9 AM) → keep that",
        "    day's breakfast and lunch simple and grab-and-go; no involved cooking before noon.",
        "  • Day with NO events → fine to suggest a more involved cook day, batch cooking,",
        "    or recipe testing.",
        "Mention the relevant event by name when you make a suggestion ('Since JP has soccer",
        "at 5 on Thursday, want to do the slow-cooker beef stew that day?') so Lauren knows",
        "you're paying attention to her week.",
        "",
        "== DISTINGUISHING TEMPORARY ADJUSTMENTS FROM PERMANENT RULES ==",
        "This is CRITICAL. You must listen for cues about whether Lauren means something",
        "just for now, or as a new permanent household rule.",
        "",
        "TEMPORARY adjustments (handle in conversation only, do NOT save):",
        '- "Just for tonight", "this week", "I don\'t have X today", "skip it this time"',
        '- "Something easy today", "I forgot to defrost", "we\'re out of Y"',
        '- "Can we do something lighter?", "I\'m too tired for that today"",',
        "- Respond naturally: 'Got it — just for tonight, let's do...' or 'Easy week it is.'",
        "- Do NOT output a [RULE] tag for these. They live only in the conversation.",
        "",
        "PERMANENT rules (save with [RULE] tag and ask Lauren to confirm):",
        '- "Always", "never again", "from now on", "add this to our rules", "we never eat X"',
        '- "Joseph won\'t touch Y", "make a rule that...", "can you remember that..."',
        '- "This is a hard rule", "permanently", "going forward always"',
        "- When you detect a permanent rule, output it as: [RULE:add]the rule text[/RULE]",
        "  A button will appear for Lauren to save it with one tap.",
        "- If Lauren asks to REMOVE a rule: [RULE:remove]the rule text[/RULE]",
        "",
        "GRAY AREA: When unclear, ask: 'Is this just for now, or should I add it as a",
        "permanent rule?' Then act on her answer.",
        "",
        "VIEWING MEAL RULES: When Lauren asks 'What are my meal rules?' or 'Show me my",
        "standing constraints', read the STANDING MEAL RULES section above and repeat them",
        "clearly to her in a friendly, readable format. Do NOT say you cannot access them.",
        "",
        "REPLACING THE STANDING MEAL RULES TEXT: If Lauren says 'Rewrite my meal rules' or",
        "'Set my constraints to...' or asks to replace the whole constraints block, use:",
        "<meal_constraint_update>",
        "Whole Foods or Trader Joe's preferred for produce and meat.",
        "Meatless Fridays — fish, eggs, and legumes are fine.",
        "No added sugar in school-day lunches.",
        "</meal_constraint_update>",
        "This REPLACES the entire constraints text. Use [RULE:add] for individual new rules.",
        "",
        "FRIDGE CARD / PRINT: When Lauren asks to 'print the plan', 'give me the fridge card',",
        "'send me the card', 'I want to print this', or says 'we're done planning', include",
        "[PRINT_CARD] in your response. This renders as a clickable 'Print Fridge Card' button.",
        "The card is always available at /meal-print. You can also just tell her to tap",
        "'Fridge Card' at the top of this page. Never say you can't provide a printable copy.",
        "",
        "MEAL PLAN UPDATES: When Lauren tells you what to put in specific slots,",
        "you can output: [MEAL_UPDATE:DayName:slot]meal name[/MEAL_UPDATE]",
        "This will save directly to the meal plan. Example:",
        "[MEAL_UPDATE:Monday:dinner]Sheet pan chicken thighs with roasted broccoli[/MEAL_UPDATE]",
        "Slots are: breakfast, lunch, dinner, dessert, snacks, dad_lunch.",
        "",
        "LINKING A MEAL TO A SAVED RECIPE CARD: When the dish you're putting in a slot",
        "matches one of the recipe cards in the SAVED RECIPE CARDS section above, append",
        "|recipe=<id> to the slot name so the cook timer can pull prep & cook times from",
        "the card and Lauren can tap through to the full recipe. Example:",
        "[MEAL_UPDATE:Tuesday:dinner|recipe=r004]Chicken Chili[/MEAL_UPDATE]",
        "Only the food slots accept |recipe= (breakfast, lunch, dinner, dessert, snacks,",
        "dad_lunch). Never put |recipe= on prep_time, cook_time, serve_time, or helpers.",
        "Never invent a recipe id — only use ids you can see in the SAVED RECIPE CARDS",
        "section. If the meal is freestyle and isn't in the library, just omit |recipe=.",
        "",
        "HELPER JOB ASSIGNMENTS: To save kitchen helper roles for a day (who leads, who assists,",
        "who does simple tasks), use the 'helpers' slot:",
        "[MEAL_UPDATE:Tuesday:helpers]JP leads prep & cooking — Joseph assists — Michael: simple tasks[/MEAL_UPDATE]",
        "This adds a 'Helpers' row to the fridge card. Use one tag per day.",
        "",
        "COOKING TIMELINE (START-COOKING REMINDER): Lauren's Day-of-Plan (POD) automatically",
        "calculates when she needs to start cooking dinner and inserts a '🍳 Start cooking' reminder",
        "into her daily timeline. It does this by subtracting prep time + cook time from the serve time.",
        "You can set these three fields for any day using MEAL_UPDATE tags:",
        "  prep_time  — active hands-on prep time (e.g. '20 minutes')",
        "  cook_time  — oven/stove time (e.g. '1 hour 30 minutes')",
        "  serve_time — target time to eat, in HH:MM or '6:00 PM' format (default: 18:00)",
        "Examples:",
        "[MEAL_UPDATE:Monday:prep_time]20 minutes[/MEAL_UPDATE]",
        "[MEAL_UPDATE:Monday:cook_time]3 hours[/MEAL_UPDATE]",
        "[MEAL_UPDATE:Monday:serve_time]18:00[/MEAL_UPDATE]",
        "With these three set, Lauren's POD will show: '🍳 Start cooking: Beef stew (20 min prep + 3 hr cook)' at 2:40 PM.",
        "When Lauren agrees on a dinner meal, proactively ask or suggest the prep/cook time so the",
        "POD reminder is set. You can also pull these from saved recipe cards automatically.",
        "If she wants dinner at a different time, use serve_time to adjust. Default serve time is 6:00 PM.",
        "",
        "RECIPE CARDS: Lauren can ask you to save any recipe as a card. When she does",
        '("Can you save that?", "Add that to my recipe cards", "Save this recipe", etc.),',
        "output a [RECIPE_CARD:add] tag containing a JSON object with these fields:",
        "  name        — recipe name (string)",
        "  servings    — number of servings (number or string like '6-8')",
        "  prep_time   — prep time string (e.g. '15 minutes')",
        "  cook_time   — cook time string (e.g. '45 minutes')",
        "  ingredients — array of strings, each with quantity and item (e.g. '2 lbs chicken thighs')",
        "  instructions — array of step strings",
        "  kid_steps   — optional array of {step, age_min, age_max?} objects, each describing one cooking task a child can lead. age_min is the youngest age that can do it; age_max is optional and omitting it means no upper bound (use 99 for 'any age can do this').",
        "  notes       — any family-specific notes, substitutions, or tips (string, can be '')",
        "  tags        — array of short tag strings for searching (e.g. ['chicken','one-pan','JP'])",
        "Example:",
        '[RECIPE_CARD:add]{"name":"Sheet Pan Chicken Thighs","servings":6,"prep_time":"10 minutes",',
        '"cook_time":"40 minutes","ingredients":["6 bone-in chicken thighs","2 cups broccoli florets"],',
        '"instructions":["Preheat oven to 425F","Season chicken and arrange on pan","Roast 40 min"],',
        '"kid_steps":[{"step":"wash the broccoli","age_min":5,"age_max":99},{"step":"pat the chicken thighs dry and season","age_min":12},{"step":"slide the sheet pan in and out of the oven with mitts","age_min":14}],',
        '"notes":"JP can handle this solo. Double the broccoli for leftovers.","tags":["chicken","JP","sheet pan"]}[/RECIPE_CARD]',
        "The card is saved automatically — no button needed. Then tell Lauren it is saved.",
        "When Lauren asks about saved recipes ('What recipes do I have?', 'Show me the curry'),",
        "refer to the SAVED RECIPE CARDS section below and quote the details back to her.",
        "",
        "== SAVED RECIPE CARDS ==",
        saved_recipes,
        "",
        "== YOUR CORE MEAL PLANNING PHILOSOPHY ==",
        "SIMPLICITY FIRST:",
        "- Every meal must be achievable by a tired homeschool mom.",
        "- LOW capacity: 20 min or less hands-on, or a kid can lead. No multi-component meals.",
        "- MEDIUM: solid home cooking, 30-45 min prep, one main + simple sides.",
        "- HIGH: Lauren can handle something more ambitious. Still be reasonable.",
        "",
        "HARD RULES — NOT SUGGESTIONS:",
        "These five rules are enforced. Re-read them before every reply that assigns,",
        "moves, or clears a meal. Breaking any one of them is a wrong answer.",
        "",
        "1) LEFTOVER RULE — never invent leftovers.",
        "   Never assign 'leftovers' (or 'leftover X', 'last night's Y', etc.) to any",
        "   slot unless the source meal explicitly appears in an EARLIER slot in the",
        "   == CURRENT MEAL PLAN == block above for THIS SAME WEEK. 'Earlier' means an",
        "   earlier day, or an earlier slot on the same day (breakfast < lunch <",
        "   dinner). If the source meal is not visible up there, leftovers do not",
        "   exist — propose a real meal instead. The == CURRENT MEAL PLAN == block is",
        "   the only source of truth for what's already cooked this week.",
        "",
        "2) DATE RANGE RULE — use exactly the days Lauren names.",
        "   Before generating anything, re-read Lauren's most recent message for an",
        "   explicit date range ('plan Wednesday through Saturday', 'just do Tue/Wed',",
        "   'fill in the rest of the week'). If she names a range, plan EXACTLY those",
        "   days — no more, no fewer. Never default to Monday-Sunday unless she asked",
        "   for a full week. If her message is ambiguous, ask which days before",
        "   emitting any [MEAL_UPDATE] tags.",
        "",
        "3) KID-HELPER RULE — every dinner needs a helper assignment.",
        "   Every [MEAL_UPDATE:Day:dinner]…[/MEAL_UPDATE] you emit MUST be paired in",
        "   the SAME REPLY with a [MEAL_UPDATE:Day:helpers]…[/MEAL_UPDATE] for that",
        "   same day. The helper task must be age-appropriate. The boys (oldest to",
        "   youngest) are: JP (14, can lead full meals), Joseph (12, skilled sous",
        "   chef), Michael (5, one safe small job), James (13 months, HIGH CHAIR",
        "   ONLY — never a helper). On nights when only James and one older boy are",
        "   available, the older boy carries the helper task. If Lauren has not",
        "   specified which boys are available that night, assign the helper task to",
        "   all three older boys (JP, Joseph, Michael) with age-scaled jobs — JP",
        "   leads, Joseph assists, Michael does one safe small task. A dinner update",
        "   without a matching helpers update is incomplete and counts as a broken",
        "   reply. EXCEPTION: when the dinner is recipe-linked AND that recipe has a",
        "   non-empty 'kid_steps' field, the helper line auto-fills from those",
        "   structured steps — do NOT emit a separate helpers tag for that day, as",
        "   it would override the structured steps with on-the-fly invention.",
        "",
        "   ADDENDUM — when a recipe-linked dinner has NO kid_steps yet:",
        "   in your reply prose, suggest 1-2 age-appropriate helper tasks tied to",
        "   specific moments in the recipe (e.g. 'Michael could wash the broccoli;",
        "   JP could lead the stovetop work'). Then ask Lauren plainly whether to",
        "   save those onto the recipe permanently so the helper line fills in",
        "   automatically next time. If she says yes in her NEXT turn, emit",
        "   [RECIPE_CARD:add] with the recipe's id and the new kid_steps array —",
        "   the parser will merge them in. Do NOT save kid_steps without her",
        "   explicit confirmation, and do NOT save them in the same reply where",
        "   you proposed them.",
        "",
        "4) NO-CARRYOVER RULE — never copy meals from a previous week.",
        "   Never carry meals forward from a previous week's plan. Before suggesting",
        "   any meal for a new week, check the == CURRENT MEAL PLAN == block: if it's",
        "   a brand-new week, that block will be empty or contain only entries for",
        "   THIS week. Old meals you remember from prior conversations are not in the",
        "   plan unless they appear there now. Treat an empty block as a true blank",
        "   slate — propose fresh meals, do not silently re-use last week's lineup.",
        "",
        "5) UNSAVED-CHANGES RULE — there is no such thing.",
        "   Never tell Lauren you have 'unsaved changes', 'pending edits', or that",
        "   she should 'let me know if you want me to save'. Saves happen the instant",
        "   you emit a [MEAL_UPDATE:…] tag — there is no separate save step. If you",
        "   haven't emitted the tag, the change does not exist. Say that plainly:",
        "   'I haven't made that change yet — want me to?' rather than implying",
        "   something is queued.",
        "",
        "ONE FAMILY MEAL — no short-order cooking.",
        "If a component a child dislikes, suggest a simple modification (e.g., sauce on the side).",
        "",
        "BATCH COOKING & LEFTOVERS: If dinner works as next day's lunch, say so.",
        "Suggest doubling recipes. Flag 'cook once, eat twice' opportunities proactively.",
        "",
        "USE WHAT'S ON HAND: Build meals around existing inventory before suggesting shopping.",
        "Flag items that need to be used soon before they go bad.",
        "",
        "BOYS IN THE KITCHEN:",
        "JP leads 2-3 dinners per week. Joseph has regular tasks most dinners.",
        "Michael always has one small safe job. Note who leads or helps each step.",
        "",
        "GROCERIES: Feed 6 people (4 boys, one a teenager — volume matters).",
        "Economical proteins: chicken thighs, ground beef, eggs, beans, tuna.",
        "When suggesting a new dish, note ingredients needed for shopping.",
        "",
        "AUGUST 10 — Feast of Saint Lawrence: suggest something grilled. Obviously.",
        "",
        "== YOUR PERSONALITY ==",
        "- Warm, confident, a little Italian in spirit. You love food and this family.",
        "- Address Lauren directly and personally by name.",
        "- Practical, never fussy. No precious techniques or hard-to-find ingredients.",
        "- Dry sense of humor. Allowed to be funny about kitchen disasters, teenagers who",
        "  can suddenly cook, and the chaos of feeding a large family.",
        "- Never lecture. Offer alternatives gently — if she says no, help her execute her plan.",
        "- Celebrate small wins: a kid eating a new vegetable, a good batch-cook Sunday.",
        "- You are Saint Lawrence's namesake. You do not panic under pressure.",
        "- FORMATTING: Never use markdown. No ##, no **, no *. Plain text only.",
        "  Use simple dashes or numbers for lists. Keep responses focused and scannable.",
        "- CRITICAL: Ask only ONE question at a time. Never stack questions.",
    ]

    from data_helpers import get_memory_context_block as _gmcb
    lines += ["", _gmcb(), ""]
    try:
        from data_helpers import get_companion_seasonal_block as _gcsb
        lines += _gcsb("LORENZO", iso)
    except Exception:
        pass
    lines += [""] + frol_context_block(weekday) + frol_edit_instructions()
    lines += [""] + companion_system_block("LORENZO")

    # Planning session block — injected last so it takes precedence
    planning_block = _get_planning_session_block()
    if planning_block:
        lines.append(planning_block)

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Page renderer
# ─────────────────────────────────────────────────────────────────────────────

def _week_sunday(d: date) -> date:
    """Return the Sunday that starts the week containing d."""
    return d - timedelta(days=(d.weekday() + 1) % 7)

def render_lorenzo_page(q: str = "", from_: str = "") -> str:
    today      = _today_eastern()
    iso        = today.isoformat()
    weekday    = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")
    h          = _hour_eastern()
    from companion_handoffs import handoff_prefill as _hp
    q_safe, ho_banner = _hp("LORENZO", q, from_)

    # ── Planning session state ────────────────────────────────────────────────
    from data_helpers import (load_planning_session, planning_session_summary,
                               PLAN_DAYS, PLAN_SLOTS)
    _ps        = load_planning_session()
    _psinfo    = planning_session_summary(_ps)
    plan_active    = _psinfo.get("active", False)
    # Use Monday-based week key (matching meal file naming); if late in week, point to NEXT Monday
    _default_plan_mon = (today + timedelta(days=(7 - today.weekday()))) if today.weekday() >= 4 else (today - timedelta(days=today.weekday()))
    plan_week_iso  = _psinfo.get("week_iso", _default_plan_mon.isoformat())
    plan_day       = _psinfo.get("current_day",  "Sunday")
    plan_slot      = _psinfo.get("current_slot", "breakfast")
    plan_day_idx   = _psinfo.get("day_idx",  0)
    plan_slot_idx  = _psinfo.get("slot_idx", 0)
    plan_done      = _psinfo.get("slots_done",   0)
    plan_total     = _psinfo.get("total_slots",  21)
    plan_days_js   = json.dumps(_psinfo.get("days",  PLAN_DAYS))
    plan_slots_js  = json.dumps(_psinfo.get("slots", PLAN_SLOTS))

    if h < 11:
        greeting      = "Buongiorno."
        phase_label   = "Morning kitchen"
        phase_color   = "#c49020"
        opener_prompt = f"Good morning, Lorenzo! It's {date_label}. What should we cook this week?"
        quick_prompts = [
            ("Plan this week's dinners",   "Plan this week's dinners for the family."),
            ("What can JP cook tonight?",  "What's a good dinner for JP to lead tonight?"),
            ("Low-effort dinner ideas",    "I have low energy today. Give me the easiest possible dinner."),
            ("Use what's in my fridge",    "Look at my inventory and tell me what meals I can make without shopping."),
            ("Prep for the week",          "Help me think through Sunday meal prep for the week ahead."),
        ]
    elif h < 17:
        greeting      = "What's for dinner?"
        phase_label   = "Afternoon kitchen"
        phase_color   = "#1a6050"
        opener_prompt = f"Lorenzo, it's {date_label}. I need to figure out dinner. What are we making?"
        quick_prompts = [
            ("Quick dinner for tonight",   "I need dinner in 30 minutes or less. What do we make?"),
            ("JP leads tonight",           "JP is leading dinner tonight. What should he make?"),
            ("Use what's in the fridge",   "Plan dinner using what I already have in the fridge and pantry."),
            ("Grocery run list",           "What should I pick up today to fill out the week's meals?"),
            ("Something new",              "Suggest a new dish the whole family will probably enjoy."),
        ]
    else:
        greeting      = "Planning tomorrow's table."
        phase_label   = "Evening planning"
        phase_color   = "#4a3a8a"
        opener_prompt = f"Lorenzo, let's plan tomorrow's meals and any overnight prep needed."
        quick_prompts = [
            ("Tomorrow's meals",           "Walk me through tomorrow's breakfast, lunch, and dinner."),
            ("Overnight prep",             "What can I prep tonight to make tomorrow easier?"),
            ("Slow cooker idea",           "Suggest something I can put in the slow cooker tonight or early tomorrow."),
            ("Leftover plan",              "What leftovers do I have and how can I use them tomorrow?"),
            ("Shopping list",              "Build me a quick shopping list for tomorrow's meals."),
        ]

    history     = _load_lorenzo_history_safe()
    has_history = bool(history)
    history_js  = json.dumps([
        {"role": m["role"], "content": m.get("content", "")}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content", "")
    ])

    quick_buttons = "".join(
        f'<button onclick=\'lzQuick({_ej(prompt)})\' '
        f'style="background:#faf8f5;border:1px solid #e4dbd2;border-radius:20px;'
        f'padding:6px 14px;font-size:0.8em;cursor:pointer;color:#555;font-family:inherit;'
        f'white-space:nowrap;transition:background 0.15s;" '
        f'onmouseover="this.style.background=\'#f0ebe4\'" '
        f'onmouseout="this.style.background=\'#faf8f5\'">'
        f'{escape(label)}</button>'
        for label, prompt in quick_prompts
    )

    phase_dot = (
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'background:{phase_color};margin-right:6px;"></span>'
    )

    new_conv_btn = (
        '<form method="POST" action="/lorenzo-clear-history" style="display:inline;">'
        '<button type="submit" style="background:none;border:none;font-size:0.72em;'
        'color:#bbb;cursor:pointer;font-family:inherit;padding:0;">&#10005; New conversation</button>'
        '</form>'
    ) if has_history else ''

    # ── Plan Together button (hidden while planning session active) ───────────
    _next_sunday   = _week_sunday(today)
    _next_sun_iso  = _next_sunday.isoformat()
    _next_sun_lbl  = _next_sunday.strftime("%B %-d")
    plan_together_btn = (
        f'<div id="lz-plan-start-row" style="margin-bottom:16px;'
        f'{"display:none;" if plan_active else ""}">'
        f'<button onclick="lzStartPlan()" '
        f'style="width:100%;padding:11px 16px;background:#8b3a1a;color:white;border:none;'
        f'border-radius:10px;font-size:0.88em;font-weight:700;cursor:pointer;font-family:inherit;'
        f'display:flex;align-items:center;justify-content:center;gap:8px;">'
        f'&#128197; Plan this week with me &rarr;'
        f'</button>'
        f'<div style="text-align:center;font-size:0.74em;color:#aaa;margin-top:5px;">'
        f'Walk through every meal of the week together, one at a time</div>'
        f'</div>'
    )

    # ── Planning session banner ───────────────────────────────────────────────
    _pct      = round(plan_done / plan_total * 100) if plan_total else 0
    _day_dots = "".join(
        f'<span title="{d}" style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'margin:0 2px;background:{"#8b3a1a" if i < plan_day_idx else ("#e4a87a" if i == plan_day_idx else "#e4dbd2")};"></span>'
        for i, d in enumerate(PLAN_DAYS)
    )
    plan_banner_html = (
        f'<div id="lz-plan-banner" style="background:#fff4ee;border:1.5px solid #8b3a1a;'
        f'border-radius:10px;padding:12px 16px;margin-bottom:16px;'
        f'{"" if plan_active else "display:none;"}">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
        f'<strong style="color:#8b3a1a;font-size:0.88em;">&#128197; Planning together</strong>'
        f'<button onclick="lzEndPlan()" style="background:none;border:none;font-size:0.75em;'
        f'color:#aaa;cursor:pointer;font-family:inherit;padding:0;">&#10005; End session</button>'
        f'</div>'
        f'<div style="font-size:0.78em;color:#777;margin-bottom:8px;">'
        f'Week of <span id="lz-plan-week-lbl">{escape(plan_week_iso)}</span></div>'
        f'<div style="margin-bottom:8px;">{_day_dots}</div>'
        f'<div style="background:#e4dbd2;border-radius:6px;height:5px;overflow:hidden;margin-bottom:8px;">'
        f'<div id="lz-plan-progress-bar" style="background:#8b3a1a;height:100%;width:{_pct}%;'
        f'transition:width 0.4s;"></div></div>'
        f'<div style="font-size:0.88em;color:#1a1a1a;">'
        f'Now: <strong id="lz-plan-current-label">{escape(plan_day)} — {escape(plan_slot.capitalize())}</strong>'
        f' <span style="font-size:0.78em;color:#aaa;">({plan_done}/{plan_total} meals planned)</span>'
        f'</div>'
        f'</div>'
    )

    _ho_js = handoff_js("LORENZO")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Lorenzo &middot; McAdams Chef</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#faf8f5;color:#1a1a1a;min-height:100vh;}}
.lz-bubble-user{{
    background:#3b2a1a;color:white;padding:10px 14px;border-radius:16px 16px 4px 16px;
    font-size:0.9em;line-height:1.55;max-width:75%;align-self:flex-end;margin-left:auto;
}}
.lz-bubble-lz{{
    background:white;border:1px solid #e4dbd2;padding:12px 16px;
    border-radius:4px 16px 16px 16px;font-size:0.9em;line-height:1.65;
    max-width:85%;white-space:pre-wrap;color:#1a1a1a;
}}
.lz-bubble-wrap{{display:flex;flex-direction:column;gap:12px;}}
@keyframes lz-pulse{{
  0%,100%{{transform:scale(1);opacity:1;}}
  50%{{transform:scale(1.18);opacity:0.8;}}
}}
</style>
</head>
<body>

<div style="max-width:760px;margin:0 auto;padding:20px 16px 200px;">

    <!-- Back + phase label -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
        <a href="/" style="font-size:0.82em;color:#aaa;text-decoration:none;">&larr; Dashboard</a>
        <div style="display:flex;align-items:center;gap:14px;">
            {new_conv_btn}
            <a href="/meals" style="font-size:0.78em;color:#8b3a1a;text-decoration:none;">&#127869; Meal Planner</a>
            <a href="/meal-print?week={escape(plan_week_iso)}" target="_blank"
               style="font-size:0.78em;color:#8b3a1a;text-decoration:none;
                      background:#fff4ee;border:1px solid #e4a87a;border-radius:6px;
                      padding:3px 8px;white-space:nowrap;">
               &#128424; Fridge Card
            </a>
            <span style="font-size:0.78em;color:#aaa;">{phase_dot}{escape(phase_label)}</span>
        </div>
    </div>

    <!-- Lorenzo header -->
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:24px;">
        <div style="width:52px;height:52px;border-radius:50%;
                    background:linear-gradient(135deg,#8b3a1a,#c49020);
                    display:flex;align-items:center;justify-content:center;font-size:1.5em;
                    flex-shrink:0;box-shadow:0 2px 10px rgba(139,58,26,0.25);">
            &#127860;
        </div>
        <div>
            <div style="font-family:Georgia,serif;font-size:1.5em;font-weight:600;color:#1a1a1a;line-height:1.1;">
                {escape(greeting)}
            </div>
            <div style="font-size:0.85em;color:#888;margin-top:2px;">
                Lorenzo &middot; {escape(weekday)}, {escape(date_label)}
            </div>
        </div>
    </div>

    <!-- Quick prompts -->
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">
        {quick_buttons}
    </div>

    <!-- Plan Together button -->
    {plan_together_btn}

    <!-- Planning banner (shown when session active) -->
    {plan_banner_html}

    <!-- Capacity selector -->
    <div style="background:#fdfaf7;border:1px solid #ede7e0;border-radius:10px;
                padding:10px 14px;margin-bottom:20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-size:0.8em;color:#888;font-weight:600;white-space:nowrap;">My energy today:</span>
        <div style="display:flex;gap:6px;">
            <button id="cap-high"   onclick="setCapacity('high')"
                    style="padding:4px 12px;border-radius:20px;font-size:0.78em;font-weight:600;
                           border:1.5px solid #2d5016;background:white;color:#2d5016;cursor:pointer;font-family:inherit;">
                High
            </button>
            <button id="cap-medium" onclick="setCapacity('medium')"
                    style="padding:4px 12px;border-radius:20px;font-size:0.78em;font-weight:600;
                           border:1.5px solid #c49020;background:white;color:#c49020;cursor:pointer;font-family:inherit;">
                Medium
            </button>
            <button id="cap-low"    onclick="setCapacity('low')"
                    style="padding:4px 12px;border-radius:20px;font-size:0.78em;font-weight:600;
                           border:1.5px solid #c0392b;background:white;color:#c0392b;cursor:pointer;font-family:inherit;">
                Low
            </button>
        </div>
        <span id="cap-note" style="font-size:0.78em;color:#aaa;font-style:italic;"></span>
    </div>

    {ho_banner}

    <!-- Chat history -->
    <div id="lz-history" class="lz-bubble-wrap" style="min-height:40px;margin-bottom:20px;"></div>

    <!-- Thinking indicator -->
    <div id="lz-thinking" style="display:none;font-size:0.82em;color:#aaa;font-style:italic;padding:4px 0;margin-bottom:12px;">
        Lorenzo is thinking&hellip;
    </div>

</div>

<!-- Attachment preview -->
<div id="lz-attach-preview"
     style="display:none;position:fixed;bottom:152px;left:0;right:0;
            background:#fffbf5;border-top:1px solid #e4dbd2;padding:8px 14px;z-index:498;">
    <div style="display:flex;align-items:center;gap:10px;">
        <img id="lz-attach-img" src="" alt="attachment"
             style="max-height:60px;max-width:72px;border-radius:8px;object-fit:cover;border:1px solid #e4dbd2;">
        <span style="font-size:0.82em;color:#888;flex:1;">Image ready to send</span>
        <button onclick="lzClearAttach()"
                style="background:#fee2e2;border:none;color:#ef4444;border-radius:8px;
                       padding:4px 10px;cursor:pointer;font-size:0.8em;font-family:inherit;">
            &#10005; Remove
        </button>
    </div>
</div>

<!-- Listening overlay -->
<div id="lz-listening-overlay"
     style="display:none;position:fixed;bottom:170px;left:0;right:0;z-index:499;
            flex-direction:column;align-items:center;justify-content:center;gap:4px;
            background:rgba(255,255,255,0.97);border-top:1px solid #f0ebe4;padding:10px 0;">
    <div style="width:52px;height:52px;border-radius:50%;background:#ef4444;
                display:flex;align-items:center;justify-content:center;
                font-size:1.5em;animation:lz-pulse 1.2s ease-in-out infinite;">&#127908;</div>
    <div style="font-size:0.82em;color:#ef4444;font-weight:600;">Listening&hellip;</div>
    <div style="font-size:0.72em;color:#aaa;">Tap mic to stop</div>
</div>

<!-- Input bar -->
<div id="lz-input-bar"
     style="position:fixed;bottom:64px;left:0;right:0;
            background:white;border-top:1px solid #e4dbd2;
            padding:6px 14px 10px;z-index:500;display:flex;flex-direction:column;gap:6px;">
    <!-- Voice toggle strip -->
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <button id="lz-voice-btn" onclick="lzToggleVoice()" title="Toggle read-aloud"
                style="padding:4px 12px;border-radius:20px;font-size:0.76em;font-weight:600;
                       border:1.5px solid #e4dbd2;background:white;color:#888;cursor:pointer;
                       font-family:inherit;transition:all 0.2s;white-space:nowrap;">
            &#128266; Read aloud: OFF
        </button>
        <button id="lz-wake-btn" onclick="lzToggleWake()" title="Toggle Hey Lorenzo wake word"
                style="padding:4px 12px;border-radius:20px;font-size:0.76em;font-weight:600;
                       border:1.5px solid #e4dbd2;background:white;color:#888;cursor:pointer;
                       font-family:inherit;transition:all 0.2s;white-space:nowrap;">
            &#127908; Hey Lorenzo: OFF
        </button>
        <button id="lz-voice-pick-btn" onclick="lzOpenVoicePanel()" title="Choose Lorenzo's voice"
                style="padding:4px 12px;border-radius:20px;font-size:0.76em;font-weight:600;
                       border:1.5px solid #e4dbd2;background:white;color:#888;cursor:pointer;
                       font-family:inherit;transition:all 0.2s;white-space:nowrap;">
            &#127897; Voice
        </button>
        <a id="lz-fridge-card-btn" href="/meal-print?week={escape(plan_week_iso)}" target="_blank"
           title="Open printable fridge card"
           style="padding:4px 12px;border-radius:20px;font-size:0.76em;font-weight:700;
                  border:1.5px solid #8b3a1a;background:#fff4ee;color:#8b3a1a;
                  text-decoration:none;white-space:nowrap;flex-shrink:0;">
            &#128424; Fridge Card
        </a>
    </div>
    <!-- Voice picker panel -->
    <div id="lz-voice-panel"
         style="display:none;position:fixed;inset:0;z-index:900;
                flex-direction:column;justify-content:flex-end;
                background:rgba(0,0,0,0.45);"
         onclick="if(event.target===this)lzCloseVoicePanel()">
        <div style="background:white;border-radius:18px 18px 0 0;
                    max-height:72vh;display:flex;flex-direction:column;
                    padding:0 0 env(safe-area-inset-bottom) 0;">
            <div style="display:flex;align-items:center;justify-content:space-between;
                        padding:14px 18px 10px;border-bottom:1px solid #f0ebe4;">
                <span style="font-weight:700;font-size:1em;color:#3d2b1f;">Choose Lorenzo's Voice</span>
                <button onclick="lzCloseVoicePanel()"
                        style="background:none;border:none;font-size:1.4em;cursor:pointer;
                               color:#888;line-height:1;padding:0 4px;">&#10005;</button>
            </div>
            <p style="font-size:0.75em;color:#999;margin:6px 18px 4px;line-height:1.4;">
                AI voices from OpenAI. Hit <b>&#9654; Sample</b> to hear, then <b>Use</b> to select.
            </p>
            <div id="lz-voice-list" style="overflow-y:auto;padding:4px 18px 20px;flex:1;"></div>
        </div>
    </div>
    <!-- Text / mic / send row -->
    <div style="display:flex;gap:8px;align-items:flex-end;">
        <input type="file" id="lz-file-input" accept="image/*"
               style="display:none;" onchange="lzAttachChange(this)">
        <button onclick="document.getElementById('lz-file-input').click()" title="Attach a photo"
                style="padding:9px 11px;background:#faf8f5;border:1.5px solid #e4dbd2;
                       border-radius:12px;cursor:pointer;font-size:1.05em;flex-shrink:0;
                       align-self:flex-end;line-height:1;">
            &#128206;
        </button>
        <button onclick="lzMicToggle()" title="Voice input" id="lz-mic-btn"
                style="padding:9px 11px;background:#faf8f5;border:1.5px solid #e4dbd2;
                       border-radius:12px;cursor:pointer;font-size:1.05em;flex-shrink:0;
                       align-self:flex-end;line-height:1;transition:all 0.15s;">
            &#127908;
        </button>
        <button id="lz-stop-btn" onclick="lzStop()" title="Stop Lorenzo talking"
                style="display:none;padding:9px 13px;background:#fee2e2;border:1.5px solid #ef4444;
                       border-radius:12px;cursor:pointer;font-size:1em;font-weight:700;flex-shrink:0;
                       align-self:flex-end;line-height:1;color:#dc2626;">
            &#9209;
        </button>
        <textarea id="lz-input" rows="1"
                  placeholder="Ask Lorenzo about meals, cooking, groceries&hellip;"
                  onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();lzSend();}}"
                  oninput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight,120)+'px';"
                  style="flex:1;resize:none;overflow:hidden;font-family:inherit;font-size:16px;
                         padding:10px 14px;border:1.5px solid #e4dbd2;border-radius:12px;
                         outline:none;line-height:1.5;max-height:120px;background:white;">{q_safe}</textarea>
        <button onclick="lzSend()"
                style="padding:10px 18px;background:#8b3a1a;color:white;border:none;
                       border-radius:12px;cursor:pointer;font-size:0.88em;font-weight:600;
                       font-family:inherit;flex-shrink:0;align-self:flex-end;">
            Send
        </button>
    </div>
</div>

<script>
var _lzIso       = {_ej(iso)};
var _lzHistory   = {history_js};
var _lzCapacity  = '';
{_ho_js}
var _lzAttached  = null;

// ── Voice state ──────────────────────────────────────────────────────────────
var _lzVoiceEnabled = localStorage.getItem('lz_voice') === 'true';
var _lzWakeEnabled  = localStorage.getItem('lz_wake')  === 'true';
var _lzIsRecording  = false;
var _lzLastWasVoice = false;
var _lzMainRecog    = null;
var _lzWakeRecog    = null;
var _lzTtsFirstFired  = false;
var _lzTtsFull        = null;
var _lzTtsFirstEndPos = 0;
var _lzAudioEl = new Audio();
var _lzVoiceName = localStorage.getItem('lz_voice_name') || 'onyx';
var _lzInFlight = false;

// ── Planning session state ────────────────────────────────────────────────────
var _lzPlanActive  = {json.dumps(plan_active)};
var _lzPlanWeekIso = {_ej(plan_week_iso)};
var _lzPlanDay     = {_ej(plan_day)};
var _lzPlanSlot    = {_ej(plan_slot)};
var _lzPlanDone    = {plan_done};
var _lzPlanTotal   = {plan_total};
var _lzPlanDays    = {plan_days_js};
var _lzPlanSlots   = {plan_slots_js};

var _LZ_VOICES = [
    {{id:'alloy',   label:'Alloy',   desc:'Neutral, balanced'}},
    {{id:'echo',    label:'Echo',    desc:'Warm, conversational'}},
    {{id:'fable',   label:'Fable',   desc:'Expressive storyteller'}},
    {{id:'onyx',    label:'Onyx',    desc:'Deep, authoritative (default)'}},
    {{id:'nova',    label:'Nova',    desc:'Bright, friendly'}},
    {{id:'shimmer', label:'Shimmer', desc:'Clear, warm'}},
    {{id:'coral',   label:'Coral',   desc:'Warm, natural'}},
    {{id:'sage',    label:'Sage',    desc:'Calm, measured'}},
    {{id:'ash',     label:'Ash',     desc:'Gentle, steady'}},
];

// ── Capacity ─────────────────────────────────────────────────────────────────
function setCapacity(level) {{
    _lzCapacity = level;
    ['high','medium','low'].forEach(function(l) {{
        var btn = document.getElementById('cap-' + l);
        btn.style.opacity = (l === level) ? '1' : '0.5';
        btn.style.fontWeight = (l === level) ? '800' : '600';
    }});
    var notes = {{
        high:   'Full energy \u2014 Lorenzo will plan accordingly.',
        medium: 'Moderate energy \u2014 straightforward meals.',
        low:    'Low energy \u2014 keeping it simple and easy.'
    }};
    document.getElementById('cap-note').textContent = notes[level] || '';
}}

// ── Image attachment ─────────────────────────────────────────────────────────
function lzAttachChange(input) {{
    if (!input.files || !input.files[0]) return;
    var file = input.files[0];
    var reader = new FileReader();
    reader.onload = function(e) {{
        var img = new Image();
        img.onload = function() {{
            var MAX = 1024;
            var w = img.width, h = img.height;
            if (w > MAX || h > MAX) {{
                if (w > h) {{ h = Math.round(h * MAX / w); w = MAX; }}
                else {{ w = Math.round(w * MAX / h); h = MAX; }}
            }}
            var canvas = document.createElement('canvas');
            canvas.width = w; canvas.height = h;
            canvas.getContext('2d').drawImage(img, 0, 0, w, h);
            var dataUrl = canvas.toDataURL('image/jpeg', 0.82);
            _lzAttached = {{b64: dataUrl.split(',')[1], mediaType: 'image/jpeg', dataUrl: dataUrl}};
            document.getElementById('lz-attach-img').src = dataUrl;
            document.getElementById('lz-attach-preview').style.display = '';
            input.value = '';
        }};
        img.src = e.target.result;
    }};
    reader.readAsDataURL(file);
}}

function lzClearAttach() {{
    _lzAttached = null;
    document.getElementById('lz-attach-preview').style.display = 'none';
    document.getElementById('lz-attach-img').src = '';
}}

// ── Bubble rendering ─────────────────────────────────────────────────────────
function _lzRenderUserBubble(text, imageDataUrl) {{
    var hist = document.getElementById('lz-history');
    var wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;align-items:flex-end;margin-bottom:0;';
    if (imageDataUrl) {{
        var imgEl = document.createElement('img');
        imgEl.src = imageDataUrl;
        imgEl.style.cssText = 'max-width:200px;max-height:140px;border-radius:10px;margin-bottom:4px;border:1px solid #ddd;';
        wrap.appendChild(imgEl);
    }}
    if (text) {{
        var div = document.createElement('div');
        div.className = 'lz-bubble-user';
        div.textContent = text;
        wrap.appendChild(div);
    }}
    hist.appendChild(wrap);
}}

function _lzRenderBubble(role, text) {{
    var hist = document.getElementById('lz-history');
    var wrap = document.createElement('div');
    var div  = document.createElement('div');
    div.className = (role === 'user') ? 'lz-bubble-user' : 'lz-bubble-lz';
    if (role === 'user') {{ div.textContent = text; }} else {{ div.innerHTML = _linkify(_lzStrip(text)); }}
    div._wrap = wrap;
    wrap.appendChild(div);
    if (role !== 'user') _renderHandoffBtns(text, wrap);
    hist.appendChild(wrap);
    return div;
}}

// ── Strip hidden tags from display text ──────────────────────────────────────
function _lzStrip(text) {{
    return _stripHandoffTags(text)
        .replace(/\[RULE:(add|remove)\][\s\S]*?\[\/RULE\]/g, '')
        .replace(/\[MEAL_UPDATE:[^\]]+\][\s\S]*?\[\/MEAL_UPDATE\]/g, '')
        .replace(/\[PRINT_CARD\]/g, '')
        .replace(/\s+$/, '');
}}

// ── TTS helpers ───────────────────────────────────────────────────────────────
function _lzUnlockAudio() {{
    try {{
        if (_lzAudioEl.src) return;
        _lzAudioEl.volume = 0;
        _lzAudioEl.play().catch(function(){{}});
        _lzAudioEl.pause();
        _lzAudioEl.volume = 1;
    }} catch(e) {{}}
}}

function _lzCleanForTts(t) {{
    return t.replace(/\\*/g,'').replace(/^[-•]\\s/gm,'').replace(/\\n+/g,' ').trim();
}}

function _lzFetchAndPlay(text, onEnd) {{
    fetch('/lucy-tts', {{
        method:'POST',
        headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
        body:'text=' + encodeURIComponent(text.substring(0,4096))
           + '&voice=' + encodeURIComponent(_lzVoiceName)
    }})
    .then(function(r) {{ return r.ok ? r.blob() : null; }})
    .then(function(blob) {{
        if (!blob) {{ if (onEnd) onEnd(); return; }}
        var url = URL.createObjectURL(blob);
        _lzAudioEl.src = url;
        _lzAudioEl.onended = function() {{
            URL.revokeObjectURL(url);
            _lzUpdateStopBtn(false);
            if (onEnd) onEnd();
        }};
        _lzAudioEl.play().then(function() {{
            _lzUpdateStopBtn(true);
        }}).catch(function() {{ if (onEnd) onEnd(); }});
    }}).catch(function() {{ if (onEnd) onEnd(); }});
}}

function _lzAfterSpeak() {{
    var wasVoice = _lzLastWasVoice;
    _lzLastWasVoice = false;
    if (_lzVoiceEnabled || wasVoice) {{
        setTimeout(lzStartListening, 400);
    }}
}}

function lzSpeak(text) {{
    if (!_lzVoiceEnabled && !_lzLastWasVoice) return;
    var clean = _lzCleanForTts(text);
    if (clean.length < 5) return;
    _lzFetchAndPlay(clean.substring(0,3000), _lzAfterSpeak);
}}

function lzSpeakTap(text, btn) {{
    if (btn) btn.disabled = true;
    var clean = _lzCleanForTts(text);
    _lzFetchAndPlay(clean.substring(0,3000), function() {{
        if (btn) btn.disabled = false;
    }});
}}

function _lzUpdateStopBtn(show) {{
    var sb = document.getElementById('lz-stop-btn');
    if (sb) sb.style.display = show ? '' : 'none';
}}

function lzStop() {{
    _lzAudioEl.pause();
    _lzAudioEl.src = '';
    _lzUpdateStopBtn(false);
    _lzTtsFull = null;
    if (_lzVoiceEnabled || _lzLastWasVoice) {{
        _lzLastWasVoice = false;
        _lzUnlockAudio();
        lzStartListening();
    }}
}}

// ── Voice read-aloud toggle ───────────────────────────────────────────────────
function _lzUpdateVoiceBtn() {{
    var btn = document.getElementById('lz-voice-btn');
    if (!btn) return;
    if (_lzVoiceEnabled) {{
        btn.textContent = '\U0001F50A Read aloud: ON';
        btn.style.background  = '#f0f8e8';
        btn.style.borderColor = '#8ab870';
        btn.style.color       = '#2d5016';
    }} else {{
        btn.textContent = '\U0001F50A Read aloud: OFF';
        btn.style.background  = 'white';
        btn.style.borderColor = '#e4dbd2';
        btn.style.color       = '#888';
    }}
}}

function lzToggleVoice() {{
    _lzVoiceEnabled = !_lzVoiceEnabled;
    localStorage.setItem('lz_voice', _lzVoiceEnabled);
    _lzUpdateVoiceBtn();
}}

// ── Wake word ─────────────────────────────────────────────────────────────────
function _lzUpdateWakeBtn() {{
    var btn = document.getElementById('lz-wake-btn');
    if (!btn) return;
    if (_lzWakeEnabled) {{
        btn.textContent = '\U0001F3A4 Hey Lorenzo: ON';
        btn.style.background  = '#fef9e8';
        btn.style.borderColor = '#d4af37';
        btn.style.color       = '#7a5c00';
    }} else {{
        btn.textContent = '\U0001F3A4 Hey Lorenzo: OFF';
        btn.style.background  = 'white';
        btn.style.borderColor = '#e4dbd2';
        btn.style.color       = '#888';
    }}
}}

function lzToggleWake() {{
    _lzWakeEnabled = !_lzWakeEnabled;
    localStorage.setItem('lz_wake', _lzWakeEnabled);
    _lzUpdateWakeBtn();
    if (_lzWakeEnabled) {{ lzStartWakeWord(); }}
    else {{ lzStopWakeWord(); }}
}}

function _lzSetMicState(active) {{
    _lzIsRecording = active;
    var btn = document.getElementById('lz-mic-btn');
    var ol  = document.getElementById('lz-listening-overlay');
    if (btn) {{
        btn.textContent       = active ? '\u23F9' : '\U0001F3A4';
        btn.style.background  = active ? '#fee2e2' : '#faf8f5';
        btn.style.borderColor = active ? '#ef4444' : '#e4dbd2';
        btn.style.color       = active ? '#ef4444' : 'inherit';
    }}
    if (ol) ol.style.display = active ? 'flex' : 'none';
}}

function lzMicToggle() {{
    if (!_lzAudioEl.paused) {{
        _lzAudioEl.pause(); _lzAudioEl.src = ''; _lzTtsFull = null;
        _lzUpdateStopBtn(false);
        _lzUnlockAudio();
        lzStartListening();
        return;
    }}
    if (window.speechSynthesis && window.speechSynthesis.speaking) {{
        window.speechSynthesis.cancel();
        lzStartListening();
        return;
    }}
    _lzUnlockAudio();
    if ('speechSynthesis' in window && !_lzIsRecording) {{
        var unlock = new SpeechSynthesisUtterance(' ');
        unlock.volume = 0; unlock.rate = 10;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(unlock);
    }}
    if (_lzIsRecording) {{ lzStopListening(); }}
    else {{ lzStartListening(); }}
}}

function lzStartListening() {{
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {{ alert('Voice input not supported on this browser.'); return; }}
    lzStopWakeWord();
    if (_lzMainRecog) {{ try {{ _lzMainRecog.stop(); }} catch(e) {{}} _lzMainRecog = null; }}
    _lzMainRecog = new SR();
    _lzMainRecog.continuous = false;
    _lzMainRecog.interimResults = true;
    _lzMainRecog.lang = 'en-US';
    _lzSetMicState(true);
    var input = document.getElementById('lz-input');
    var _sentFromResult = false;
    _lzMainRecog.onresult = function(e) {{
        var transcript = '';
        for (var i = 0; i < e.results.length; i++) transcript += e.results[i][0].transcript;
        if (input) input.value = transcript;
        if (e.results[e.results.length - 1].isFinal) {{
            _sentFromResult = true;
            _lzSetMicState(false);
            if (_lzWakeEnabled) setTimeout(lzStartWakeWord, 1200);
            _lzLastWasVoice = true;
            lzSend();
        }}
    }};
    _lzMainRecog.onerror = function(e) {{
        _lzSetMicState(false);
        if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 1500);
    }};
    _lzMainRecog.onend = function() {{
        if (_lzIsRecording && !_sentFromResult) {{
            _lzSetMicState(false);
            var pending = document.getElementById('lz-input');
            if (pending && pending.value.trim()) {{ _lzLastWasVoice = true; lzSend(); return; }}
        }} else if (_lzIsRecording) {{ _lzSetMicState(false); }}
        if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 1000);
    }};
    try {{ _lzMainRecog.start(); }} catch(e) {{ _lzSetMicState(false); }}
}}

function lzStopListening() {{
    if (_lzMainRecog) {{ try {{ _lzMainRecog.stop(); }} catch(e) {{}} _lzMainRecog = null; }}
    _lzSetMicState(false);
    if (_lzWakeEnabled) setTimeout(lzStartWakeWord, 800);
}}

function lzStartWakeWord() {{
    if (!_lzWakeEnabled || _lzIsRecording) return;
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    lzStopWakeWord();
    _lzWakeRecog = new SR();
    _lzWakeRecog.continuous = false;
    _lzWakeRecog.interimResults = false;
    _lzWakeRecog.lang = 'en-US';
    _lzWakeRecog.onresult = function(e) {{
        var raw = e.results[0][0].transcript.toLowerCase().replace(/[^a-z ]/g, ' ');
        var detected = (raw.indexOf('hey lorenzo') >= 0 || raw.indexOf('hey lorenso') >= 0 ||
                        raw.indexOf('hey lorenz')  >= 0 || raw.indexOf('a lorenzo')   >= 0);
        if (detected) {{
            _lzPlayBeep();
            setTimeout(lzStartListening, 450);
        }} else {{
            if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 250);
        }}
    }};
    _lzWakeRecog.onerror = function() {{
        if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 2000);
    }};
    _lzWakeRecog.onend = function() {{
        if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 350);
    }};
    try {{ _lzWakeRecog.start(); }} catch(e) {{}}
}}

function lzStopWakeWord() {{
    if (_lzWakeRecog) {{ try {{ _lzWakeRecog.stop(); }} catch(e) {{}} _lzWakeRecog = null; }}
}}

function _lzPlayBeep() {{
    try {{
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.type = 'sine'; osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
        osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.3);
    }} catch(e) {{}}
}}

// ── Voice picker panel ────────────────────────────────────────────────────────
function lzOpenVoicePanel() {{
    var panel = document.getElementById('lz-voice-panel');
    panel.style.display = 'flex';
    var list = document.getElementById('lz-voice-list');
    list.innerHTML = '';
    _LZ_VOICES.forEach(function(v) {{
        var row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #f0ebe4;';
        var info = document.createElement('div');
        info.style.cssText = 'flex:1;';
        info.innerHTML = '<div style="font-weight:700;font-size:0.9em;color:#3d2b1f;">' + v.label + '</div>'
            + '<div style="font-size:0.75em;color:#999;">' + v.desc + '</div>';
        var sampleBtn = document.createElement('button');
        sampleBtn.textContent = '\u25B6 Sample';
        sampleBtn.style.cssText = 'padding:5px 10px;font-size:0.78em;border-radius:7px;border:1px solid #e4dbd2;'
            + 'background:#faf8f5;cursor:pointer;font-family:inherit;color:#555;white-space:nowrap;';
        (function(vid) {{
            sampleBtn.onclick = function() {{
                fetch('/lucy-tts', {{
                    method:'POST',
                    headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
                    body:'text=' + encodeURIComponent('Buongiorno! I am Lorenzo, your personal chef.') + '&voice=' + encodeURIComponent(vid)
                }}).then(function(r) {{ return r.blob(); }}).then(function(blob) {{
                    var url = URL.createObjectURL(blob);
                    var a = new Audio(url);
                    a.play();
                    a.onended = function() {{ URL.revokeObjectURL(url); }};
                }});
            }};
        }})(v.id);
        var useBtn = document.createElement('button');
        useBtn.textContent = (v.id === _lzVoiceName) ? '\u2713 Selected' : 'Use';
        useBtn.style.cssText = 'padding:5px 12px;font-size:0.78em;border-radius:7px;border:none;cursor:pointer;'
            + 'font-family:inherit;font-weight:700;white-space:nowrap;'
            + (v.id === _lzVoiceName ? 'background:#8b3a1a;color:white;' : 'background:#3b2a1a;color:white;');
        (function(vid, vLabel, btn) {{
            btn.onclick = function() {{
                _lzVoiceName = vid;
                localStorage.setItem('lz_voice_name', vid);
                var pb = document.getElementById('lz-voice-pick-btn');
                if (pb) pb.textContent = '\U0001F3A4 ' + vLabel;
                lzCloseVoicePanel();
            }};
        }})(v.id, v.label, useBtn);
        row.appendChild(info);
        row.appendChild(sampleBtn);
        row.appendChild(useBtn);
        list.appendChild(row);
    }});
}}

function lzCloseVoicePanel() {{
    document.getElementById('lz-voice-panel').style.display = 'none';
}}

// ── Quick prompt ──────────────────────────────────────────────────────────────
function lzQuick(prompt) {{
    var input = document.getElementById('lz-input');
    input.value = prompt;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    input.focus();
}}

// ── Send ──────────────────────────────────────────────────────────────────────
function lzSend() {{
    var input = document.getElementById('lz-input');
    var msg   = input.value.trim();
    var img   = _lzAttached;
    if (!msg && !img) return;
    if (_lzInFlight) return;
    _lzInFlight = true;
    _lzUnlockAudio();
    _lzTtsFirstFired  = false;
    _lzTtsFull        = null;
    _lzTtsFirstEndPos = 0;
    _lzAudioEl.pause();
    _lzUpdateStopBtn(false);
    input.value = '';
    input.style.height = 'auto';

    _lzHistory.push({{role:'user', content: msg || '(image)'}});
    _lzRenderUserBubble(msg, img ? img.dataUrl : null);
    lzClearAttach();

    document.getElementById('lz-thinking').style.display = '';
    window.scrollTo(0, document.body.scrollHeight);

    var params = 'iso=' + encodeURIComponent(_lzIso)
        + '&capacity='   + encodeURIComponent(_lzCapacity)
        + '&message='    + encodeURIComponent(msg)
        + '&image_b64='  + encodeURIComponent(img ? img.b64 : '')
        + '&image_type=' + encodeURIComponent(img ? img.mediaType : '');

    fetch('/lorenzo-chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: params
    }}).then(function(r) {{
        document.getElementById('lz-thinking').style.display = 'none';
        if (!r.ok) {{
            _lzInFlight = false;
            _lzRenderBubble('lz', 'Lorenzo stepped away. Check that your API key is set in Settings.');
            return;
        }}
        var bubble  = _lzRenderBubble('lz', '');
        var full    = '';
        var reader  = r.body.getReader();
        var decoder = new TextDecoder();
        function read() {{
            return reader.read().then(function(res) {{
                if (res.done) {{
                    _lzInFlight = false;
                    var clean = _lzStrip(full);
                    bubble.innerHTML = _linkify(clean);
                    _lzHistory.push({{role:'assistant', content: clean}});
                    _lzTtsFull = clean;
                    _renderHandoffBtns(full, bubble._wrap);
                    if (!_lzTtsFirstFired) {{
                        lzSpeak(clean);
                    }}

                    // ── Tap-to-hear button ────────────────────────────────
                    if ('speechSynthesis' in window && bubble._wrap) {{
                        var spkRow = document.createElement('div');
                        spkRow.style.cssText = 'display:flex;justify-content:flex-start;margin-top:2px;';
                        var spkBtn = document.createElement('button');
                        spkBtn.textContent = '\U0001F50A Hear Lorenzo';
                        spkBtn.style.cssText = 'background:none;border:none;color:#8b3a1a;'
                            + 'font-size:0.75em;cursor:pointer;padding:2px 0;font-family:inherit;'
                            + 'text-decoration:underline;text-underline-offset:2px;opacity:0.8;';
                        (function(btn, txt) {{
                            btn.onclick = function() {{ lzSpeakTap(txt, btn); }};
                        }})(spkBtn, clean);
                        spkRow.appendChild(spkBtn);
                        if (bubble._wrap.firstChild && bubble._wrap.firstChild.nextSibling) {{
                            bubble._wrap.insertBefore(spkRow, bubble._wrap.firstChild.nextSibling);
                        }} else {{
                            bubble._wrap.appendChild(spkRow);
                        }}
                    }}

                    // ── Parse [RULE:add/remove]...[/RULE] — permanent rule buttons ──
                    var ruleRx = /\[RULE:(add|remove)\]([\s\S]*?)\[\/RULE\]/g;
                    var m;
                    while ((m = ruleRx.exec(full)) !== null) {{
                        (function(action, ruleText) {{
                            ruleText = ruleText.trim();
                            var ruleRow = document.createElement('div');
                            ruleRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:8px;'
                                + 'padding:8px 12px;background:#fff8f0;border:1px solid #e6b870;border-radius:8px;';
                            var ruleIcon = document.createElement('span');
                            ruleIcon.textContent = action === 'add' ? '\U0001F4CB' : '\U0001F5D1';
                            ruleIcon.style.cssText = 'font-size:1em;flex-shrink:0;';
                            var ruleMsg = document.createElement('span');
                            var preview = ruleText.length > 60 ? ruleText.substring(0,60)+'\u2026' : ruleText;
                            ruleMsg.textContent = (action === 'add' ? 'Permanent rule: ' : 'Remove rule: ') + preview;
                            ruleMsg.style.cssText = 'font-size:0.82em;color:#7a4500;flex:1;';
                            var ruleBtn = document.createElement('button');
                            ruleBtn.textContent = action === 'add' ? '\u2713 Save to meal rules' : '\u2713 Remove rule';
                            ruleBtn.style.cssText = 'padding:5px 12px;background:#8b3a1a;color:white;'
                                + 'border:none;border-radius:6px;font-size:0.78em;cursor:pointer;'
                                + 'font-family:inherit;font-weight:700;white-space:nowrap;flex-shrink:0;';
                            ruleBtn.onclick = function() {{
                                fetch('/lorenzo-rule-save', {{
                                    method: 'POST',
                                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                                    body: 'action=' + encodeURIComponent(action)
                                        + '&rule=' + encodeURIComponent(ruleText)
                                }}).then(function(r) {{
                                    if (r.ok) {{
                                        ruleBtn.textContent = '\u2713 Saved';
                                        ruleBtn.style.background = '#2d5016';
                                        ruleBtn.disabled = true;
                                    }}
                                }});
                            }};
                            ruleRow.appendChild(ruleIcon);
                            ruleRow.appendChild(ruleMsg);
                            ruleRow.appendChild(ruleBtn);
                            if (bubble._wrap) bubble._wrap.appendChild(ruleRow);
                        }})(m[1], m[2]);
                    }}

                    // ── Parse [MEAL_UPDATE:Day:slot[|recipe=ID]]meal[/MEAL_UPDATE] ─
                    // Slot may carry an optional "|recipe=<id>" — strip it out
                    // of the displayed slot name and surface the recipe id as
                    // a small badge after the meal.
                    var mealRx = /\[MEAL_UPDATE:([^:]+):([^|\]]+)(?:\|recipe=([^\]]+))?\]([\s\S]*?)\[\/MEAL_UPDATE\]/g;
                    while ((m = mealRx.exec(full)) !== null) {{
                        (function(mDay, mSlot, mRid, mMeal) {{
                            mMeal = mMeal.trim();
                            mRid  = (mRid || '').trim();
                            var mRow = document.createElement('div');
                            mRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:6px;'
                                + 'padding:7px 10px;background:#fffbea;border:1px solid #e6c84a;border-radius:8px;';
                            var mIcon = document.createElement('span');
                            mIcon.textContent = '\U0001F37D\uFE0F';
                            mIcon.style.cssText = 'font-size:1em;flex-shrink:0;';
                            var mMsg = document.createElement('span');
                            mMsg.textContent = mDay + ' ' + mSlot + ': ' + mMeal
                                + (mRid ? '  (recipe ' + mRid + ')' : '');
                            mMsg.style.cssText = 'font-size:0.82em;color:#7a5a00;flex:1;';
                            var mBtn = document.createElement('a');
                            mBtn.textContent = '\U0001F35D Meal Plan';
                            mBtn.href = '/meals';
                            mBtn.target = '_blank';
                            mBtn.style.cssText = 'padding:4px 12px;background:#b07d10;color:white;'
                                + 'text-decoration:none;border-radius:6px;font-size:0.8em;font-weight:700;'
                                + 'font-family:inherit;flex-shrink:0;';
                            mRow.appendChild(mIcon); mRow.appendChild(mMsg); mRow.appendChild(mBtn);
                            if (bubble._wrap) bubble._wrap.appendChild(mRow);
                        }})(m[1], m[2], m[3], m[4]);
                    }}

                    // ── Print Fridge Card link after any meal updates ─────────
                    var _hasMealUpdates = /\[MEAL_UPDATE:[^\]]+\]/.test(full)
                                       || /\[PRINT_CARD\]/.test(full);
                    if (_hasMealUpdates && bubble._wrap) {{
                        var _printRow = document.createElement('div');
                        _printRow.style.cssText = 'margin-top:10px;';
                        var _printLink = document.createElement('a');
                        _printLink.href = '/meal-print?week=' + encodeURIComponent(_lzPlanWeekIso || _lzIso.slice(0,10));
                        _printLink.target = '_blank';
                        _printLink.textContent = '\U0001F5A8 Print Fridge Card';
                        _printLink.style.cssText = 'display:inline-block;padding:7px 16px;'
                            + 'background:#8b3a1a;color:white;text-decoration:none;'
                            + 'border-radius:8px;font-size:0.82em;font-weight:700;'
                            + 'font-family:inherit;letter-spacing:0.01em;';
                        _printRow.appendChild(_printLink);
                        bubble._wrap.appendChild(_printRow);
                    }}

                    // ── Parse [RECIPE_CARD:add]JSON[/RECIPE_CARD] ────────────
                    var rcRx = /\[RECIPE_CARD:add\]([\s\S]*?)\[\/RECIPE_CARD\]/g;
                    while ((m = rcRx.exec(full)) !== null) {{
                        (function(rawJson) {{
                            var rc;
                            try {{ rc = JSON.parse(rawJson.trim()); }} catch(e) {{ return; }}
                            var name  = rc.name || 'Recipe';
                            var ingrs = Array.isArray(rc.ingredients) ? rc.ingredients : [];
                            var steps = Array.isArray(rc.instructions) ? rc.instructions : [];
                            var tags  = Array.isArray(rc.tags) ? rc.tags : [];
                            var timing = [
                                rc.servings ? 'Serves ' + rc.servings : '',
                                rc.prep_time ? 'Prep ' + rc.prep_time : '',
                                rc.cook_time ? 'Cook ' + rc.cook_time : ''
                            ].filter(Boolean).join(' \u00b7 ');

                            var card = document.createElement('div');
                            card.style.cssText = 'margin-top:10px;border:1.5px solid #8b3a1a;border-radius:10px;'
                                + 'overflow:hidden;font-size:0.83em;';

                            var hdr = document.createElement('div');
                            hdr.style.cssText = 'background:#8b3a1a;color:white;padding:8px 12px;display:flex;'
                                + 'align-items:center;gap:8px;';
                            var hIcon = document.createElement('span');
                            hIcon.textContent = '\U0001F4D6';
                            var hTitle = document.createElement('strong');
                            hTitle.textContent = name;
                            hTitle.style.flex = '1';
                            var hBadge = document.createElement('span');
                            hBadge.textContent = '\u2713 Saved to recipe cards';
                            hBadge.style.cssText = 'font-size:0.78em;opacity:0.85;white-space:nowrap;';
                            hdr.appendChild(hIcon);
                            hdr.appendChild(hTitle);
                            hdr.appendChild(hBadge);
                            card.appendChild(hdr);

                            var body = document.createElement('div');
                            body.style.cssText = 'padding:10px 12px;background:#fdf8f5;display:flex;'
                                + 'flex-direction:column;gap:8px;';

                            if (timing) {{
                                var tRow = document.createElement('div');
                                tRow.style.cssText = 'color:#8b3a1a;font-size:0.82em;font-weight:600;';
                                tRow.textContent = timing;
                                body.appendChild(tRow);
                            }}

                            if (ingrs.length) {{
                                var iSec = document.createElement('div');
                                var iHdr = document.createElement('div');
                                iHdr.style.cssText = 'font-weight:700;color:#1a1a1a;margin-bottom:3px;';
                                iHdr.textContent = 'Ingredients';
                                iSec.appendChild(iHdr);
                                ingrs.forEach(function(ing) {{
                                    var li = document.createElement('div');
                                    li.style.cssText = 'color:#444;padding-left:10px;line-height:1.5;';
                                    li.textContent = '\u2022 ' + ing;
                                    iSec.appendChild(li);
                                }});
                                body.appendChild(iSec);
                            }}

                            if (steps.length) {{
                                var sSec = document.createElement('div');
                                var sHdr = document.createElement('div');
                                sHdr.style.cssText = 'font-weight:700;color:#1a1a1a;margin-bottom:3px;';
                                sHdr.textContent = 'Instructions';
                                sSec.appendChild(sHdr);
                                steps.forEach(function(step, idx) {{
                                    var li = document.createElement('div');
                                    li.style.cssText = 'color:#444;padding-left:10px;line-height:1.5;';
                                    li.textContent = (idx+1) + '. ' + step;
                                    sSec.appendChild(li);
                                }});
                                body.appendChild(sSec);
                            }}

                            if (rc.notes) {{
                                var nSec = document.createElement('div');
                                nSec.style.cssText = 'background:#fff8f0;border:1px solid #e6b870;'
                                    + 'border-radius:6px;padding:6px 10px;color:#7a4500;font-style:italic;';
                                nSec.textContent = rc.notes;
                                body.appendChild(nSec);
                            }}

                            if (tags.length) {{
                                var tSec = document.createElement('div');
                                tSec.style.cssText = 'display:flex;flex-wrap:wrap;gap:4px;';
                                tags.forEach(function(tag) {{
                                    var t = document.createElement('span');
                                    t.style.cssText = 'background:#f0ebe4;border:1px solid #d4c5b0;'
                                        + 'border-radius:12px;padding:2px 8px;font-size:0.78em;color:#5a3a1a;';
                                    t.textContent = tag;
                                    tSec.appendChild(t);
                                }});
                                body.appendChild(tSec);
                            }}

                            card.appendChild(body);
                            if (bubble._wrap) bubble._wrap.appendChild(card);
                        }})(m[1]);
                    }}

                    // Refresh planning banner if session is active
                    if (_lzPlanActive) lzRefreshPlanBanner();

                    window.scrollTo(0, document.body.scrollHeight);
                    return;
                }}
                full += decoder.decode(res.value, {{stream:true}});
                bubble.innerHTML = _linkify(_lzStrip(full));
                // Early TTS on first complete sentence
                if (!_lzTtsFirstFired && (_lzVoiceEnabled || _lzLastWasVoice)) {{
                    var s2 = _lzStrip(full);
                    var si = s2.search(/[.!?](?:\s|$)/);
                    if (si > 40) {{
                        _lzTtsFirstFired  = true;
                        _lzTtsFirstEndPos = si + 1;
                        var fc = _lzCleanForTts(s2.substring(0, si + 1));
                        if (fc.length > 20) {{
                            _lzFetchAndPlay(fc, function() {{
                                function _playRest() {{
                                    if (!_lzTtsFull) {{ setTimeout(_playRest, 150); return; }}
                                    if (_lzAudioEl.paused) {{
                                        var rt = _lzCleanForTts(_lzTtsFull.substring(_lzTtsFirstEndPos));
                                        if (rt.length > 20) {{
                                            _lzFetchAndPlay(rt.substring(0,3000), _lzAfterSpeak);
                                        }} else {{
                                            _lzAfterSpeak();
                                        }}
                                    }}
                                }}
                                _playRest();
                            }});
                        }}
                    }}
                }}
                window.scrollTo(0, document.body.scrollHeight);
                return read();
            }});
        }}
        read().catch(function(e) {{ _lzInFlight = false; bubble.textContent = 'Stream error: ' + e.message; }});
    }}).catch(function(e) {{
        _lzInFlight = false;
        document.getElementById('lz-thinking').style.display = 'none';
        _lzRenderBubble('lz', 'Network error: ' + e.message);
    }});
}}

// ── Planning session ─────────────────────────────────────────────────────────
function lzStartPlan() {{
    fetch('/lorenzo-plan-start', {{
        method: 'POST',
        headers: {{'Content-Type':'application/x-www-form-urlencoded'}},
        body: 'iso=' + encodeURIComponent(_lzPlanWeekIso || _lzIso)
    }}).then(function(r) {{ return r.json(); }})
    .then(function(info) {{
        _lzPlanActive = true;
        _lzUpdatePlanUI(info);
        // Clear chat history display
        var feed = document.getElementById('lz-history');
        if (feed) feed.innerHTML = '';
        _lzHistory = [];
        // Send the opener message automatically
        var day   = info.current_day  || 'Sunday';
        var slot  = info.current_slot || 'breakfast';
        var slotLabel = slot.charAt(0).toUpperCase() + slot.slice(1);
        var input = document.getElementById('lz-input');
        if (input) {{
            input.value = "Lorenzo, let's plan this week together. Start with " + day + " and walk me through the meals one at a time.";
            lzSend();
        }}
    }}).catch(function(e) {{ console.error('Plan start error:', e); }});
}}

function lzEndPlan() {{
    fetch('/lorenzo-plan-end', {{method:'POST'}}).then(function() {{
        _lzPlanActive = false;
        var banner = document.getElementById('lz-plan-banner');
        if (banner) banner.style.display = 'none';
        var startRow = document.getElementById('lz-plan-start-row');
        if (startRow) startRow.style.display = '';
    }});
}}

function lzRefreshPlanBanner() {{
    fetch('/lorenzo-plan-state')
    .then(function(r) {{ return r.json(); }})
    .then(function(info) {{ _lzUpdatePlanUI(info); }})
    .catch(function() {{}});
}}

function _lzUpdatePlanUI(info) {{
    if (!info || !info.active) {{
        _lzPlanActive = false;
        var banner = document.getElementById('lz-plan-banner');
        if (banner) banner.style.display = 'none';
        var startRow = document.getElementById('lz-plan-start-row');
        if (startRow) startRow.style.display = '';
        return;
    }}
    _lzPlanActive = true;
    _lzPlanDay    = info.current_day  || _lzPlanDay;
    _lzPlanSlot   = info.current_slot || _lzPlanSlot;
    _lzPlanDone   = info.slots_done   || 0;
    _lzPlanTotal  = info.total_slots  || 21;
    var banner = document.getElementById('lz-plan-banner');
    if (banner) banner.style.display = '';
    var startRow = document.getElementById('lz-plan-start-row');
    if (startRow) startRow.style.display = 'none';
    var lbl = document.getElementById('lz-plan-current-label');
    var slotCap = _lzPlanSlot.charAt(0).toUpperCase() + _lzPlanSlot.slice(1);
    if (lbl) lbl.textContent = _lzPlanDay + ' \u2014 ' + slotCap;
    var bar = document.getElementById('lz-plan-progress-bar');
    if (bar && _lzPlanTotal > 0) bar.style.width = Math.round(_lzPlanDone / _lzPlanTotal * 100) + '%';
    var weekLbl = document.getElementById('lz-plan-week-lbl');
    if (weekLbl && info.week_iso) weekLbl.textContent = info.week_iso;
    // Keep fridge card buttons pointing at the planning week
    if (info.week_iso) {{
        var _wkParam = '?week=' + encodeURIComponent(info.week_iso);
        ['lz-fridge-card-btn'].forEach(function(id) {{
            var el = document.getElementById(id);
            if (el) el.href = '/meal-print' + _wkParam;
        }});
    }}
    var countEl = document.querySelector('#lz-plan-banner span[style*="color:#aaa"]');
    if (countEl) countEl.textContent = '(' + _lzPlanDone + '/' + _lzPlanTotal + ' meals planned)';
}}

// ── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener('load', function() {{
    _lzUpdateVoiceBtn();
    _lzUpdateWakeBtn();
    if (_lzWakeEnabled) {{ lzStartWakeWord(); }}
    // Show saved voice name on picker button
    var pb = document.getElementById('lz-voice-pick-btn');
    if (pb) {{
        _LZ_VOICES.forEach(function(v) {{
            if (v.id === _lzVoiceName) pb.textContent = '\U0001F3A4 ' + v.label;
        }});
    }}
    // Restore history or send opener
    var input = document.getElementById('lz-input');
    if ({json.dumps(has_history)}) {{
        for (var i = 0; i < _lzHistory.length; i++) {{
            var role = _lzHistory[i].role;
            var content = _lzHistory[i].content;
            if (role === 'user') {{
                _lzRenderUserBubble(content, null);
            }} else {{
                _lzRenderBubble('lz', content);
            }}
        }}
        window.scrollTo(0, document.body.scrollHeight);
    }} else {{
        input.value = {_ej(opener_prompt)};
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    }}
}});
</script>
</body>
</html>"""
