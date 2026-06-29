"""Meal Wizard — Lorenzo week-generation data contract (G1c-1a / G1c-1b).

Pure, deterministic logic plus the generation prompt builder:
  1. wizard_target_slot_keys  — which empty "YYYY-MM-DD::slot" keys the
     generator should fill, never touching an already-confirmed meal (Rule 4).
  2. parse_wizard_meal_response — map a model's JSON week into clean suggestion
     entries, restricted to the target keys.
  3. build_wizard_meal_prompt — assemble the one-pass generation prompt from the
     wizard session (G1c-1b). Built as a list of lines joined with newline
     (Rule 1/2/7). Family facts come from app_settings / the meal rules via the
     Lorenzo helpers — NEVER hardcoded here (Rule 19).

This module makes no network call and no file writes; the live Sonnet call and
the session write live in app.py's /meal-wizard-generate route (G1c-1b).
"""

from datetime import date, timedelta
import json
import re

from render_lorenzo import (
    _get_meal_constraints,
    _get_calendar_this_week,
    _get_saved_recipes,
)


def wizard_target_slot_keys(session: dict) -> list:
    """Return the "YYYY-MM-DD::slot" keys the generator should fill:
    every date in the planning window x every slot kind being planned,
    MINUS any key already present in confirmed_meals (never overwrite a
    confirmed/locked meal — Rule 4). Returns a sorted list; [] if the
    window or slot kinds are missing."""
    win = session.get("planning_window") or {}
    start = win.get("start_iso")
    end = win.get("end_iso")
    slots = session.get("confirmed_what_to_plan") or []
    confirmed = session.get("confirmed_meals") or {}
    if not (start and end and slots):
        return []
    try:
        d0 = date.fromisoformat(start)
        d1 = date.fromisoformat(end)
    except Exception:
        return []
    if d1 < d0:
        return []
    keys = set()
    d = d0
    while d <= d1:
        for slot in slots:
            k = d.isoformat() + "::" + str(slot)
            if k not in confirmed:
                keys.add(k)
        d = d + timedelta(days=1)
    return sorted(keys)


def parse_wizard_meal_response(text: str, target_keys) -> dict:
    """Parse the model's JSON week and map it into suggestion entries,
    keyed "YYYY-MM-DD::slot". Includes ONLY keys in target_keys (never a
    confirmed slot, never an out-of-window date, never an unrequested slot
    kind). Returns {} if nothing parses. Each entry mirrors a confirmed
    entry minus the lock, tagged source 'lorenzo'."""
    candidates = []
    fence = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if fence:
        candidates.append(fence.group(1))
    brace = re.search(r'\{[\s\S]*\}', text)
    if brace:
        candidates.append(brace.group())
    parsed = {}
    for cand in candidates:
        try:
            parsed = json.loads(cand)
            break
        except json.JSONDecodeError:
            cleaned = re.sub(r',\s*([}\]])', r'\1', cand)
            try:
                parsed = json.loads(cleaned)
                break
            except Exception:
                pass
    if not isinstance(parsed, dict) or not parsed:
        return {}
    meals = parsed.get("meals") if isinstance(parsed.get("meals"), dict) else parsed
    target = set(target_keys or [])
    out = {}
    for day_key, slots in meals.items():
        if not isinstance(slots, dict):
            continue
        for slot_key, val in slots.items():
            key = str(day_key) + "::" + str(slot_key)
            if key not in target:
                continue
            if isinstance(val, dict):
                name = str(val.get("name", "") or "").strip()
                protein = str(val.get("protein", "") or "").strip()
                ingredients = str(val.get("ingredients", "") or "").strip()
                note = str(val.get("note", "") or "").strip()
            else:
                name = str(val or "").strip()
                protein = ""
                ingredients = ""
                note = ""
            if not name:
                continue
            out[key] = {
                "name": name,
                "protein": protein,
                "ingredients": ingredients,
                "note": note,
                "source": "lorenzo",
                "recipe_id": "",
                "recipe_on_request": True,
                "skip_shopping": False,
            }
    return out


def build_wizard_meal_prompt(session: dict, target_keys: list) -> str:
    """Assemble the one-pass generation prompt from the wizard session.
    Returns a single string. Built as a list of lines joined with newline
    (Rule 1/2/7 — no f-string backslash/quote hazards). Family-agnostic: any
    family facts come from app_settings / the meal rules via the Lorenzo
    helpers, never hardcoded (Rule 19). All inputs are fail-soft."""
    session = session or {}
    keys = list(target_keys or [])

    # Grouped "YYYY-MM-DD — slot" list. Keep the slot token RAW (not humanized)
    # so the model echoes the exact slot key the parser matches against.
    slot_lines = []
    for k in keys:
        if "::" in k:
            d_part, s_part = k.split("::", 1)
        else:
            d_part, s_part = k, ""
        slot_lines.append("  - " + d_part + " — " + s_part)
    targets_block = "\n".join(slot_lines) if slot_lines else "  (none)"

    inventory = str(session.get("confirmed_inventory", "") or "").strip()
    use_soon = str(session.get("use_soon_items", "") or "").strip()
    used = session.get("used_proteins", []) or []
    if isinstance(used, list):
        used_str = ", ".join(str(p) for p in used if str(p).strip())
    else:
        used_str = str(used).strip()
    complexity = str(session.get("confirmed_complexity", "normal") or "normal").strip()

    # In-window confirmed meals — already decided by the mother; the model must
    # plan a coherent week AROUND them, never fill or change them.
    win = session.get("planning_window") or {}
    start = win.get("start_iso")
    end = win.get("end_iso")
    confirmed = session.get("confirmed_meals") or {}
    confirmed_lines = []
    if isinstance(confirmed, dict):
        for ck in sorted(confirmed.keys()):
            cv = confirmed[ck]
            if "::" in ck:
                c_date, c_slot = ck.split("::", 1)
            else:
                c_date, c_slot = ck, ""
            if start and end and not (start <= c_date <= end):
                continue
            if isinstance(cv, dict):
                c_name = str(cv.get("name", "") or "").strip()
            else:
                c_name = str(cv or "").strip()
            if c_name:
                confirmed_lines.append("  - " + c_date + " — " + c_slot + ": " + c_name)
    confirmed_block = "\n".join(confirmed_lines) if confirmed_lines else "  (none yet)"

    # Family-aware context, pulled (never hardcoded) via the Lorenzo helpers.
    rules_str = _get_meal_constraints()
    if keys:
        win_start = start or keys[0].split("::", 1)[0]
    else:
        win_start = start or date.today().isoformat()
    calendar_str = _get_calendar_this_week(win_start)
    recipes_str = _get_saved_recipes()

    has_dad_lunch = any(k.endswith("::dad_lunch") for k in keys)

    lines = []
    lines.append("You are the meal planner for a Catholic homeschool family.")
    lines.append("You are producing a DRAFT week of meals that the mother will review and edit. These are suggestions, not decisions — she has the final say.")
    lines.append("")
    lines.append("Fill EXACTLY these meal cells, and ONLY these:")
    lines.append(targets_block)
    lines.append("Do not add any day or meal type that is not in this list.")
    lines.append("")
    lines.append("These meals are ALREADY decided — do NOT propose or change them; plan a coherent week around them:")
    lines.append(confirmed_block)
    lines.append("")
    lines.append("USE-SOON items — each MUST be used in at least one meal this week:")
    lines.append("  " + (use_soon if use_soon else "(none)"))
    lines.append("Do not ignore them.")
    lines.append("")
    lines.append("On-hand inventory (note the FORM — fresh / canned / frozen / dried):")
    lines.append("  " + (inventory if inventory else "(none recorded)"))
    lines.append("Respect the form exactly: if an item is canned, do not plan a dish that needs it fresh, and vice versa; treat the canned/frozen form as usable as-is.")
    lines.append("")
    lines.append("Do NOT repeat a main protein already used this week:")
    lines.append("  " + (used_str if used_str else "(none yet)"))
    lines.append("Rotate proteins across the days you plan (no protein twice unless unavoidable).")
    lines.append("")
    lines.append("Standing meal rules — follow exactly, including any meatless-Friday / liturgical rules:")
    lines.append(rules_str)
    lines.append("")
    lines.append("Calendar for the week (keep meals quick on busy days):")
    lines.append(calendar_str)
    lines.append("")
    lines.append("Effort level for this week: " + complexity + " — match it.")
    if recipes_str:
        lines.append("")
        lines.append("Recipes already on hand (prefer dishes the family already has a recipe for):")
        lines.append(recipes_str)
    if has_dad_lunch:
        lines.append("")
        lines.append("The dad-lunch slot must NEVER be the same as that day's family dinner; he prefers meat over salad or rice.")
    lines.append("")
    lines.append("Suggest real, makeable dishes. You may include meals that need a few shopping items, but never claim an ingredient is on hand unless it is in the inventory above.")
    lines.append("")
    lines.append("Return ONLY a JSON object, no prose before or after, in EXACTLY this shape:")
    lines.append('{"meals": {"YYYY-MM-DD": {"slot": {"name": "...", "protein": "...", "ingredients": "...", "note": "..."}}}}')
    lines.append("Include only the date/slot cells listed above. protein = the single main protein, or empty string if meatless. ingredients = brief comma-separated list. note = optional, <= 8 words.")
    return "\n".join(lines)
