"""Meal Wizard — Lorenzo week-generation data contract (G1c-1a).

Pure, deterministic logic for two things:
  1. wizard_target_slot_keys  — which empty "YYYY-MM-DD::slot" keys the
     generator should fill, never touching an already-confirmed meal (Rule 4).
  2. parse_wizard_meal_response — map a model's JSON week into clean suggestion
     entries, restricted to the target keys.

No network call, no prompt, no UI, no file writes, and NO family specifics
(Rule 19) — everything is driven off the wizard session's window / slot kinds /
confirmed data. The endpoint, prompt and live Sonnet call arrive in G1c-1b.
"""

from datetime import date, timedelta
import json
import re


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
