# CATEGORIES allowlist — location report (2026-07-02)

## Short answer

Defined **exactly once**, in **`render_meal_wizard_step4.py` line 41**.
Variable name: `CATEGORIES` (a tuple).

---

## The definition

**`render_meal_wizard_step4.py`, line 41:**
```python
CATEGORIES = ("main", "side", "soup", "bread", "salad", "appetizer", "dessert", "snack")
```

---

## The one import (not a duplicate definition)

**`app.py`, line 257:**
```python
from render_meal_wizard_step4 import render_step4_slot_and_lock, CATEGORIES as _S4_CATEGORIES
```
Used at line 10823 to validate the `_dcat` field in the Step-4 confirm POST handler:
```python
if _dcat not in _S4_CATEGORIES:
```
This is not a separate definition — it is the same tuple imported under an alias.

---

## The unrelated `CATEGORIES` in `render_goals.py`

**`render_goals.py`, line 11** — completely different domain (quarterly goals / roadmap),
no overlap with meal categories:
```python
CATEGORIES = [
    "Spiritual Formation",
    "Marriage & Family Culture",
    "Classical Education / Homeschool",
    "Latin / Language",
    "Physical Health",
    "Home & Order",
    "Financial Stewardship",
    "Creative / Personal Growth",
    "CAP / Sea Cadets",
    "Service / Apostolate",
    "Seasonal / Liturgical Traditions",
    ...
]
```

---

## Summary

| Location | Variable | Is the meal allowlist? |
|---|---|---|
| `render_meal_wizard_step4.py:41` | `CATEGORIES` | ✅ Yes — single source of truth |
| `app.py:257` | `_S4_CATEGORIES` | Import alias of the above — not a duplicate |
| `render_goals.py:11` | `CATEGORIES` | ❌ No — goal/roadmap categories, unrelated |
