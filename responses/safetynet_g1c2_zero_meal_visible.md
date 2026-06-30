# SAFETY NET — make a zero-meal generation visible (no silent empty reload)

**Scope:** ONE FILE, JS only, additive. `render_meal_wizard_step4.py`. `app.py`, the `/meal-wizard-generate` handler, and `window.s4Keep` were **not** touched.

---

## What changed
`window.s4Generate` (inside the `_S4_JS` IIFE) now reads the response instead of trusting `j.ok` alone:

```javascript
.then(function(j){ var n = (j && j.generated) ? j.generated : 0;
  if(j && j.ok && n > 0){ window.location.href = '/meal-wizard-step4'; return; }
  if(btn){ btn.disabled = false; }
  var em = (j && j.error) ? String(j.error) : 'Lorenzo could not generate this week - please try again.';
  if(msg){ msg.textContent = em; } })
.catch(function(){ if(btn){ btn.disabled = false; } if(msg){ msg.textContent = 'Lorenzo could not generate this week - please try again.'; } });
```

Behavior:
1. **`ok` is true AND `generated > 0`** -> reload `/meal-wizard-step4` (success unchanged).
2. **`generated` is 0 / missing, OR body has `error`, OR `ok` falsy** -> do NOT reload; re-enable the button and show a message in `s4-gen-msg`:
   - If the body has `error`, the **real error text** is shown (so the actual reason is visible).
   - Otherwise: `Lorenzo could not generate this week - please try again.`

The disable-on-click guard is unchanged. Nothing else in the function changed.

**Note on Rules 1/2/7/12:** the message text uses plain ASCII (`could not`, `-`) rather than an apostrophe/em-dash, so there are **no backslashes** (no `\u` escapes), no nested quotes, and no raw newlines in any JS string — matching the existing JS-in-string style in this file.

---

## Validation
- **py_compile** `render_meal_wizard_step4.py` -> **PASS**
- **node --check** on the emitted `_S4_JS` -> **JS SYNTAX: OK**
- **Step 4 harness** (`data/verify_meal_wizard_step4.py`) -> **PASS** (12/12 checks, incl. the `s4Keep`/`s4Change` write-loop script presence and back link)

App restarted so the change is live.
