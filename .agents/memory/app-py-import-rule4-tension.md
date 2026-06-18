---
name: app.py Rule 4 vs. inline-import convention
description: When adding handler code in app.py, prefer module-top imports even though the file is full of inline imports.
---

# app.py imports: Rule 4 wins over the existing inline-import habit

`app.py`'s `do_GET`/`do_POST` are full of inline imports inside handler
branches (e.g. `import json as _json`, `from datetime import date as _x`).
This looks like the house style, but claud.md **Rule 4** ("never put import
statements inside if blocks or functions") forbids it, and code review will
flag any new inline import you add by copying that habit.

**Rule:** add new dependencies as module-top imports. `date`/`datetime` are
already imported at the top; `json` now is too (it historically was NOT, which
is why the inline `import json as _json` pattern proliferated).

**Why:** the inline-import convention predates strict Rule 4 enforcement;
matching surrounding code here produces a rule violation, not consistency.

**How to apply:** before writing `import ...` inside a `do_GET`/`do_POST`
branch, add it to the top of `app.py` instead (and reuse the already-imported
`date`, `datetime`, `timedelta`, `json`).
