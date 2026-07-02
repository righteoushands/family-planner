# PROJECT_STATE.md — Full Regeneration (2026-07-02 rev 2)

## How the rescan was done

All line counts derived from `wc -l` run live against the working tree.
No number carried forward from a prior session.
Three specific areas verified against the today's changed code:
- `render_meal_wizard_step4.py` — confirmed `revert_dishes` parameter
- `app.py` — confirmed `/meal-wizard-step4-remove` handler with `_s4r_prior_dishes` capture
- `data/verify_meal_wizard_step4_remove.py` — confirmed present in §9

## What changed from the prior version (rev 1 → rev 2)

| Item | Rev 1 | Rev 2 |
|---|---|---|
| `app.py` lines | 12,379 | **12,386** (+7) |
| `render_meal_wizard_step4.py` lines | 782 | **792** (+10) |
| `render_meal_wizard_step4.py` description | no mention of `revert_dishes` | added `render_step4_slot_and_lock(date_iso, slot_key, revert_dishes=None)` |
| `/meal-wizard-step4-remove` handler | not separately documented | new sub-section in §8 documents `_s4r_prior_dishes` capture and mixed-origin behaviour |
| `data/verify_meal_wizard_step4_remove.py` | **not present** | **new — 276 lines** in §9 |
| `data/verify_task_42.py` lines | 141 | **145** |
| §9 intro text | "offline (no network, no live writes)" | updated to describe Rule 10a mechanical `ImportError` enforcement |
| `verify_meal_wizard_g1a.py` description | "G1a: generation session contract" | clarified as confirm/remove/protein logic, snapshot+restore pattern (predates mw_test_isolation) |

## Confirmed-current facts for the three areas called out

### render_meal_wizard_step4.py (792 lines)
`render_step4_slot_and_lock` signature confirmed at line 612:
```python
def render_step4_slot_and_lock(date_iso: str, slot_key: str,
                               revert_dishes=None) -> dict:
```
When `revert_dishes` is provided and non-empty, the entry affordance
pre-fills from those dishes; otherwise falls back to `suggested_meals`.

### app.py /meal-wizard-step4-remove handler (line 10878)
Confirmed the two capture lines added before the pop:
```python
_s4r_prior_entry  = _s4r_meals.get(_s4r_date + "::" + _s4r_slot) or {}
_s4r_prior_dishes = (_s4r_prior_entry.get("dishes")
                     if isinstance(_s4r_prior_entry, dict) else None)
```
And the updated render call:
```python
_s4r_frag = render_step4_slot_and_lock(_s4r_date, _s4r_slot,
                                       revert_dishes=_s4r_prior_dishes)
```

### data/verify_meal_wizard_step4_remove.py (276 lines)
Present in §9. `import mw_test_isolation` is the literal first project import.
10 checks: bad-date 400, bad-slot 400, absent-slot idempotent 200,
fixture proof (side absent from suggested_meals), mixed-origin 200,
no-reload contract, session slot cleared, main dish in HTML, Lauren-only
side in HTML, sha256 before==after.
