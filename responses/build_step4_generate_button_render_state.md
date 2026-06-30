# BUILD complete — Step 4 Generate button render-time state

**File changed:** `render_meal_wizard_step4.py` only. Additive. No JS click-time behavior changed, no new form handling, no data-shape change.

## What was added

### 1. Import + cap constant (circular-import note)
`wizard_target_slot_keys` is imported from `render_meal_wizard_gen.py` (clean — that module only pulls stdlib + `render_lorenzo`, no cycle with Step 4).

The cap **cannot** be imported from `app.py` (app.py imports this module → circular), so the value is duplicated locally with a loud flag:
```python
from render_meal_wizard_gen import wizard_target_slot_keys

# MUST stay in lockstep with app.py's _WIZARD_GEN_SLOT_CAP (the server-side cap
# enforced by /meal-wizard-generate). It is duplicated here rather than imported
# because app.py imports this module, so importing the constant back would be a
# circular import. FLAG: if these two values drift apart, this button could
# enable a request the server then refuses (or disable one the server allows).
# Change both together. Added 2026-06-30.
_WIZARD_GEN_SLOT_CAP = 14
```

### ⚠️ Flag for your sign-off
The cap value `14` now lives in **two** places (`app.py` and this file). I followed the spec's guidance ("define the same constant value here … pick whichever avoids a circular import") because the only clean alternative — moving the constant into `render_meal_wizard_gen.py` and importing it from both — would require editing a **second** file, which this one-file build forbids. The smoke test below includes an automated drift-guard that fails if the two values ever differ. **If you'd prefer a single source of truth, say so and I'll move the constant into the shared gen module as a follow-up.**

### 2. Target count computed at render time
Right where the session is already loaded:
```python
    session = load_meal_wizard_session() or {}
    _s4_targets = wizard_target_slot_keys(session)
    _s4_target_count = len(_s4_targets)
```
This uses the **same** function the server uses, so the render-time count matches the server's count exactly.

### 3. Button reflects the count (three states)
- **0 slots** → unchanged behavior (existing button, no extra line).
- **1…cap slots** → button **enabled**, label unchanged, with a line: `Will generate {n} meal(s).`
- **> cap slots** → button rendered with the real `disabled` **attribute** (plus a muted `opacity/cursor` style), with the line: `Too many meals selected ({n}) — Lorenzo plans best a couple of meal types at a time. Go back to Step 3 and select fewer, or shorten the window.`

The button keeps its `id="s4-gen-btn"` and the `s4-gen-msg` div, so the existing `s4Generate()` click-time JS (label swap, disable-on-click) is untouched — this is purely additive render state. The interpolated count is escaped once via `escape(str(_s4_target_count))`, and the em dash uses `\u2014` in the f-string literal, matching the file's existing convention.

---

## Validation results (all three pass)

### 1. `py_compile render_meal_wizard_step4.py`
```
py_compile OK
```

### 2. In-process smoke test (render at 5 / 20 / 0 slots)
```
step4 cap constant: 14
app.py cap constant: 14            <- drift-guard: caps match

[5 slots]:  id="s4-gen-btn" style="...cursor:pointer;" onclick="s4Generate(this)">Generate my week with Lorenzo</button> ...
  -> ENABLED, 'Will generate 5 meal(s).' present

[20 slots]: id="s4-gen-btn" disabled style="...;opacity:0.5;cursor:not-allowed" onclick="s4Generate(this)">Generate my week with Lorenzo</button> ...
  -> DISABLED (attribute), warning '(20)' present, points to Step 3

[0 slots] -> unchanged (no count line, not disabled)

SMOKE OK: 5->enabled+count; 20->disabled+warning; 0->unchanged; caps match
```

### 3. Verify harnesses (Phase G meal-wizard area)
```
verify_meal_wizard_step4.py           → PASS all G1b-1 read-only screen checks passed     (exit 0)
verify_meal_wizard_step4_lock.py      → PASS all G1 lock checks passed                    (exit 0)
verify_meal_wizard_step4_writeloop.py → PASS all G1b-2a write-loop + guard checks passed  (exit 0)
verify_meal_wizard_gen.py             → PASS all G1c-1a generation-contract checks passed (exit 0)
```

### Extra safety check
`import app` succeeds with no circular-import error, confirming the new import is safe in the live load path.

## Scope confirmation
Only `render_meal_wizard_step4.py` was changed. No other files touched.
