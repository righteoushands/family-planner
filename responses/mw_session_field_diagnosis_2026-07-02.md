# Meal wizard session field list — diagnosis (2026-07-02)

## Function signatures (data_helpers.py lines 3293–3317)

```python
def load_meal_wizard_session() -> dict:
    """Load current meal wizard session state. Returns {} if no active session."""
    try:
        with open(MEAL_WIZARD_SESSION_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_meal_wizard_session(session: dict) -> None:
    """Persist meal wizard session state via safe_save_json."""
    safe_save_json(MEAL_WIZARD_SESSION_FILE, session)

def clear_meal_wizard_session() -> None:
    """Wipe the meal wizard session file (called when plan is locked or abandoned)."""
    safe_save_json(MEAL_WIZARD_SESSION_FILE, {})

def update_meal_wizard_session(updates: dict) -> dict:
    """Merge updates into current session state and save. Returns updated session."""
    session = load_meal_wizard_session()
    session.update(updates)
    save_meal_wizard_session(session)
    return session
```

update_meal_wizard_session is a top-level shallow dict.update — writing a nested
key replaces the entire nested dict wholesale.

## All 9 session-level keys

| Key | Type | Written by route | app.py line |
|---|---|---|---|
| `confirmed_inventory` | str | `/meal-wizard-step2-save` | 10679 |
| `use_soon_items` | str | `/meal-wizard-step2-save` | 10679 |
| `confirmed_what_to_plan` | list[str] | `/meal-wizard-step3-save` | 10755 |
| `confirmed_complexity` | str (`"full_effort"` / `"normal"` / `"simple"`) | `/meal-wizard-step3-save` | 10755 |
| `planning_window` | dict {start_iso, end_iso} | `/meal-wizard-step3-save` | 10755 |
| `confirmed_meals` | dict keyed "YYYY-MM-DD::slot" | step3-save (prefill), step4-confirm, step4-remove | 10755, 10856, 10909 |
| `suggested_meals` | dict keyed "YYYY-MM-DD::slot" | step4-confirm (mirrors back), /meal-wizard-generate | 10856, 11012 |
| `used_proteins` | list[str] | step4-confirm, step4-remove | 10856, 10909 |
| `plan_locked_at` | str (ISO date) | `/meal-wizard-step4-lock` | 10945 |

render_meal_wizard_gen.py reads a subset: planning_window, confirmed_what_to_plan,
confirmed_meals, confirmed_inventory, use_soon_items, used_proteins,
confirmed_complexity. No additional keys.

## confirmed_shopping_day / shopping-day equivalent

DOES NOT EXIST. No confirmed_shopping_day, shopping_day, or equivalent key
in any update_meal_wizard_session call or session.get() anywhere in the codebase.

"shopping" appears only as:
1. render_meals.py lines 990/1007/1010 — placeholder copy in old /meals page UI
2. render_lorenzo.py lines 514/995 — prose inside Lorenzo system prompt and quick-prompt label
3. render_meal_wizard_step4.py lines 471–472 — skip_shopping is a per-SLOT field
   inside confirmed_meals entries (not a session-level key)

## Calendar data in shopping context

No such route or helper exists. The only calendar-reading function near the meal
wizard is render_lorenzo.py:_get_calendar_this_week(iso), which is called from
build_lorenzo_context() for Lorenzo's chat companion only — not from any meal
wizard route, not gated on a shopping day, not connected to the session object.
build_wizard_meal_prompt (render_meal_wizard_gen.py) does NOT call it.
