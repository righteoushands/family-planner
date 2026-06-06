---
name: JS-in-f-string brace & quote handling (render_*.py)
description: How to safely embed JS containing { } object literals into the big triple-double-quoted f-strings used by render_*.py companion pages.
---

# Embedding JS object literals into render_*.py f-strings

The companion chat pages (e.g. `render_lucy.py`) build their entire `<script>`
block as one big `f"""..."""` (triple double-quote). Two distinct contexts need
different treatment when the JS contains `{ }` (e.g. `scrollIntoView({behavior:'smooth'})`):

- **In the f-string BODY** (plain JS lines): literal braces must be DOUBLED
  `{{ ... }}`, and real source newlines are fine. Single quotes are fine
  (delimiter is `"""`). Rule 7's `\\n` concern only applies to `\n` INSIDE a JS
  *string literal*, not to source-line breaks.
- **Inside an f-string REPLACEMENT FIELD** `{ 'js...' if cond else (...) }`:
  the inner Python string is a normal (non-f) literal, so its braces stay SINGLE
  (literal). To satisfy Python 3.11 you must keep the Python string single-quoted
  (can't reuse `"` — same as the `"""` delimiter; Rule 2) and CANNOT use
  backslashes (Rule 1). So write the embedded JS with DOUBLE quotes and put it on
  ONE line (statements joined by `;`, no newline needed).

**Why:** Python 3.11 forbids same-quote nesting and backslashes in f-string
expressions; undoubled `{ }` in an f-string body are parsed as replacement fields.
**How to apply:** when editing JS scroll/DOM snippets in any `render_*.py` page,
check whether the edit site is f-string body (double the braces) or a `{...}`
replacement field (single braces, double-quoted JS, single-quoted Python string,
one line). Always `py_compile` + an in-process render smoke test afterward.
