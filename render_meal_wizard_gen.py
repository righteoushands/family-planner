"""Meal Wizard — Lorenzo week-generation data contract (G1c-1a / G1c-1b / G1c-3a).

Pure, deterministic logic plus the generation prompt builder:
  1. wizard_target_slot_keys  — which empty "YYYY-MM-DD::slot" keys the
     generator should fill, never touching an already-confirmed meal (Rule 4).
  2. parse_wizard_meal_response — map a model's dishes[] JSON week into clean
     suggestion entries, restricted to the target keys (G1c-3a: new dishes[]
     schema; validates each dish category against _DISH_CATEGORIES; drops
     dishes with invalid/missing category; drops slots with zero valid dishes;
     enforces single-dish cap for non-multi slots).
  3. build_wizard_meal_prompt — assemble the one-pass generation prompt from
     the wizard session (G1c-1b / G1c-3a). Built as a list of lines joined
     with newline (Rule 1/2/7). Family facts come from app_settings / the meal
     rules via the Lorenzo helpers — NEVER hardcoded here (Rule 19).

This module makes no network call and no file writes; the live call and the
session write live in app.py's /meal-wizard-generate route (G1c-1b).
"""

from datetime import date, timedelta
import json
import re

from render_lorenzo import (
    _get_meal_constraints,
    _get_calendar_this_week,
    _get_saved_recipes,
)
from config import MEAL_DISH_CATEGORIES as _DISH_CATEGORIES
from data_helpers import slot_dishes


_WIZARD_GEN_SLOT_CAP = 14  # conservative placeholder (2 meal types x 7 days).
# NOT measured — the known-good point is ~7 slots (1 type/week), the known-bad
# point is 55. Tune this from the gen log once real stop_reason data exists.
# Single source of truth — also imported by app.py and
# render_meal_wizard_step4.py. Change once here. Added 2026-06-30.

# _DISH_CATEGORIES is imported from config (MEAL_DISH_CATEGORIES) — single
# canonical definition shared with render_meal_wizard_step4 via config.py.
# Circular-import issue resolved in G1c-3a cleanup: config imports nothing
# from render_meal_wizard_gen or render_meal_wizard_step4.

# Slot kinds that receive 2-3 dishes (one main + sides) from Lorenzo.
# All other slot kinds receive exactly 1 dish with category "main".
_MULTI_DISH_SLOTS = frozenset({"dinner", "feast_meal"})


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


def _parse_valid_dishes(raw_dishes, is_multi):
    """Validate a raw dishes list against _DISH_CATEGORIES.

    Rules (G1c-3a):
    - Each dish must be a dict with a 'category' value present in
      _DISH_CATEGORIES.  Invalid or missing category → dish dropped
      (no defaulting to 'main').
    - Each dish must have a non-empty 'name'.  Empty name → dish dropped.
    - Non-multi slots: stop after the first valid dish (single-dish cap).
      This enforces the cap in the parser itself, independent of the prompt.

    Returns a list of clean dish dicts (possibly empty).
    """
    valid = []
    for dish in (raw_dishes or []):
        if not isinstance(dish, dict):
            continue
        cat = str(dish.get("category") or "").strip()
        if cat not in _DISH_CATEGORIES:
            continue
        name = str(dish.get("name") or "").strip()
        if not name:
            continue
        valid.append({
            "category": cat,
            "name": name,
            "ingredients": str(dish.get("ingredients") or "").strip(),
            "protein": str(dish.get("protein") or "").strip(),
        })
        if not is_multi:
            break  # single-dish cap: stop after the first valid dish
    return valid


def parse_wizard_meal_response(text: str, target_keys) -> dict:
    """Parse the model's dishes[] JSON week and map it into suggestion
    entries, keyed "YYYY-MM-DD::slot". Includes ONLY keys in target_keys
    (never a confirmed slot, never an out-of-window date, never an
    unrequested slot kind). Returns {} if nothing parses.

    Schema (G1c-3a — dishes[] replaces the old flat name/protein/ingredients):
      {"meals": {"YYYY-MM-DD": {"slot": {
          "dishes": [{"category":"...", "name":"...",
                      "protein":"...", "ingredients":"..."}],
          "note": "..."
      }}}}

    Validation:
    - Each dish's 'category' must be in _DISH_CATEGORIES.  Invalid or missing
      → dish dropped.  NOT defaulted to 'main'.
    - Slots with zero valid dishes remaining are dropped entirely.
    - Non-multi slots (anything other than dinner / feast_meal) that return
      > 1 dish: first valid dish kept, rest discarded (enforced in parser,
      not only in the prompt).
    """
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
            slot_name = str(slot_key)
            is_multi = slot_name in _MULTI_DISH_SLOTS
            if isinstance(val, dict):
                raw_dishes = val.get("dishes")
                if not isinstance(raw_dishes, list):
                    raw_dishes = []
                top_note = str(val.get("note") or "").strip()
            else:
                raw_dishes = []
                top_note = ""
            valid_dishes = _parse_valid_dishes(raw_dishes, is_multi)
            if not valid_dishes:
                continue  # drop slot entirely — no valid dishes
            out[key] = {
                "dishes": valid_dishes,
                "note": top_note,
                "source": "lorenzo",
                "recipe_id": "",
                "recipe_on_request": True,
                "skip_shopping": False,
            }
    return out


def build_wizard_meal_prompt(session: dict, target_keys: list) -> str:
    """Assemble the one-pass generation prompt from the wizard session.
    Returns a single string. Built as a list of lines joined with newline
    (Rule 1/2/7 — no f-string backslash/quote hazards). Family-agnostic:
    any family facts come from app_settings / the meal rules via the Lorenzo
    helpers, never hardcoded (Rule 19). All inputs are fail-soft.

    G1c-3a changes:
    - Output schema updated to dishes[] (replacing flat name/protein/ingredients).
    - dinner / feast_meal target keys annotated as multi-dish (2-3 dishes).
    - All other target keys annotated as single-dish, category 'main'.
    - Valid category values listed from _DISH_CATEGORIES (not hardcoded inline).
    """
    session = session or {}
    keys = list(target_keys or [])

    # Grouped "YYYY-MM-DD — slot" list with dish-count annotation.
    # Keep the slot token RAW so the model echoes the exact key the parser
    # matches against.  The annotation in brackets is instructional only.
    slot_lines = []
    for k in keys:
        if "::" in k:
            d_part, s_part = k.split("::", 1)
        else:
            d_part, s_part = k, ""
        if s_part in _MULTI_DISH_SLOTS:
            slot_lines.append(
                "  - " + d_part + " — " + s_part
                + "  [multi-dish: 2-3 dishes, one main + sides]"
            )
        else:
            slot_lines.append(
                "  - " + d_part + " — " + s_part
                + "  [single dish, category: main]"
            )
    targets_block = "\n".join(slot_lines) if slot_lines else "  (none)"

    inventory = str(session.get("confirmed_inventory", "") or "").strip()
    use_soon = str(session.get("use_soon_items", "") or "").strip()
    used = session.get("used_proteins", []) or []
    if isinstance(used, list):
        used_str = ", ".join(str(p) for p in used if str(p).strip())
    else:
        used_str = str(used).strip()
    complexity = str(session.get("confirmed_complexity", "normal") or "normal").strip()

    # In-window confirmed meals — already decided by the mother; the model
    # must plan a coherent week AROUND them, never fill or change them.
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
            _cv_dishes = slot_dishes(cv)
            c_name = str(
                (_cv_dishes[0].get("name", "") if _cv_dishes else "") or ""
            ).strip()
            if c_name:
                confirmed_lines.append(
                    "  - " + c_date + " — " + c_slot + ": " + c_name
                )
    confirmed_block = (
        "\n".join(confirmed_lines) if confirmed_lines else "  (none yet)"
    )

    # Family-aware context pulled (never hardcoded) via the Lorenzo helpers.
    rules_str = _get_meal_constraints()
    if keys:
        win_start = start or keys[0].split("::", 1)[0]
    else:
        win_start = start or date.today().isoformat()
    calendar_str = _get_calendar_this_week(win_start)
    recipes_str = _get_saved_recipes()

    has_dad_lunch = any(k.endswith("::dad_lunch") for k in keys)
    categories_str = ", ".join(_DISH_CATEGORIES)

    lines = []
    lines.append("You are the meal planner for a Catholic homeschool family.")
    lines.append(
        "You are producing a DRAFT week of meals that the mother will review "
        "and edit. These are suggestions, not decisions — she has the final say."
    )
    lines.append("")
    lines.append(
        "Fill EXACTLY these meal cells, and ONLY these "
        "(the annotation in brackets is for you — do not echo it):"
    )
    lines.append(targets_block)
    lines.append("Do not add any day or meal type that is not in this list.")
    lines.append("")
    lines.append(
        "Dish count rules:"
    )
    lines.append(
        "  Multi-dish slots (dinner, feast_meal): provide 2 to 3 dishes — "
        "one main plus one or two sides. Cap at 3 dishes total."
    )
    lines.append(
        "  Single-dish slots (all others): provide exactly 1 dish "
        "with category 'main'."
    )
    lines.append("")
    lines.append(
        "Valid category values — use these exact lowercase strings, "
        "no others: " + categories_str
    )
    lines.append("Every dish must have a valid category from this list.")
    lines.append("")
    lines.append(
        "These meals are ALREADY decided — do NOT propose or change them; "
        "plan a coherent week around them:"
    )
    lines.append(confirmed_block)
    lines.append("")
    lines.append("USE-SOON items — each MUST be used in at least one meal this week:")
    lines.append("  " + (use_soon if use_soon else "(none)"))
    lines.append("Do not ignore them.")
    lines.append("")
    lines.append("On-hand inventory (note the FORM — fresh / canned / frozen / dried):")
    lines.append("  " + (inventory if inventory else "(none recorded)"))
    lines.append(
        "Respect the form exactly: if an item is canned, do not plan a dish "
        "that needs it fresh; treat the canned/frozen form as usable as-is."
    )
    # TEMPORARY soft-guard, prompt-only — no real inventory depletion yet.
    # Revisit/remove when structured inventory lands (TRACKER 40/44). Added 2026-06-30.
    lines.append(
        "The already-decided meals above draw from this same on-hand list."
    )
    lines.append(
        "Some on-hand items are a single package or a small fresh amount. "
        "Do not propose a new dish that relies on a limited fresh or perishable "
        "item that an already-decided meal already uses — treat that item as spent."
    )
    lines.append("")
    lines.append("Do NOT repeat a main protein already used this week:")
    lines.append("  " + (used_str if used_str else "(none yet)"))
    lines.append(
        "Rotate proteins across the days you plan "
        "(no protein twice unless unavoidable)."
    )
    lines.append("")
    lines.append(
        "Standing meal rules — follow exactly, "
        "including any meatless-Friday / liturgical rules:"
    )
    lines.append(rules_str)
    lines.append("")
    lines.append("Calendar for the week (keep meals quick on busy days):")
    lines.append(calendar_str)
    lines.append("")
    lines.append("Effort level for this week: " + complexity + " — match it.")
    if recipes_str:
        lines.append("")
        lines.append(
            "Recipes already on hand "
            "(prefer dishes the family already has a recipe for):"
        )
        lines.append(recipes_str)
    if has_dad_lunch:
        lines.append("")
        lines.append(
            "The dad-lunch slot must NEVER be the same as that day's family "
            "dinner; he prefers meat over salad or rice."
        )
    lines.append("")
    lines.append(
        "Suggest real, makeable dishes. You may include meals that need a few "
        "shopping items, but never claim an ingredient is on hand unless it is "
        "in the inventory above."
    )
    lines.append("")
    lines.append(
        "Return ONLY a JSON object, no prose before or after, "
        "in EXACTLY this shape:"
    )
    lines.append(
        '{"meals": {"YYYY-MM-DD": {"slot": {'
        '"dishes": [{"category": "...", "name": "...", '
        '"protein": "...", "ingredients": "..."}], '
        '"note": "..."}}}}'
    )
    lines.append(
        "dishes is a list. "
        "Multi-dish slots (dinner, feast_meal): 2-3 items. "
        "Single-dish slots: exactly 1 item with category 'main'. "
        "note is optional, top-level per slot, <= 8 words. "
        "protein = the single main protein for that dish, or empty string if "
        "meatless. ingredients = brief comma-separated list."
    )
    lines.append("Include only the date/slot cells listed above.")
    return "\n".join(lines)
