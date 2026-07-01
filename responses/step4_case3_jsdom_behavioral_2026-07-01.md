# Step 4 Phase B — Case 3 behavioral test (jsdom) (2026-07-01)

Previous report used a source-string check (`"Pick a category for" in _S4_JS`).
This replaces it with a real DOM/JS behavioral test.

---

## Test method

**Runtime:** Node.js v20 + jsdom (installed to `/tmp/s4test/`)

**Setup:**
1. Python renders `_s4_slot_block(D, "dinner", "Dinner", None, None)` and the
   `#s4-dish-template` HTML, and extracts `_S4_JS` (script tags stripped), all
   written to `/tmp/s4test/fixtures.json`.
2. jsdom builds a document from that HTML (`runScripts: 'dangerously'`).
3. `window.fetch` is replaced with a spy that records any call and its payload.
4. The extracted JS is injected via `document.createElement('script')`.
5. **Scenario:** `nameEl.value = 'Chicken Parm'` — name filled. `catEl.value`
   stays `''` (the `<option value="">` placeholder remains selected).
6. `window.s4Keep(D, SLOT)` is invoked.
7. After a 50 ms tick (to let any accidental async fetch settle): read
   `fetchCalled` and `#s4-msg--{key}.textContent`.

**Assertions:**
- **(a)** `fetchCalled === false` — no HTTP request was sent.
- **(b)** `msgEl.textContent` contains `"Pick a category for"` AND `"Chicken Parm"`.

---

## Output

```
Pre-call state:
  name textarea value : "Chicken Parm"
  cat select value    : ""

--- Case 3: name filled, category unselected ---
(a) fetch() NOT called       : PASS
(b) blocking msg in #s4-msg  : PASS
    msg content              : "Pick a category for \u201cChicken Parm\u201d."

CASE 3: PASS
EXIT=0
```

*(The `SecurityError: sessionStorage is not available for opaque origins` line
is from the scroll-restore code that runs on DOMContentLoaded — after the
blocking check, unrelated to this test.)*

---

## Test script

`/tmp/s4test/case3_test.js` — not committed to the repo (lives in /tmp).
Source reproduced here for the record:

```js
const { JSDOM } = require('/tmp/s4test/node_modules/jsdom');
const fs = require('fs');
const fix = JSON.parse(fs.readFileSync('/tmp/s4test/fixtures.json', 'utf8'));

const D = '2026-07-01', SLOT = 'dinner', KEY = D + '--' + SLOT;
const dom = new JSDOM(
  `<!DOCTYPE html><html><body>${fix.slot_html}${fix.tmpl_html}</body></html>`,
  { runScripts: 'dangerously' }
);
const { window } = dom;

let fetchCalled = false, fetchBody = null;
window.fetch = function(url, opts) {
  fetchCalled = true;
  fetchBody = opts ? JSON.parse(opts.body) : null;
  return Promise.resolve({ json: () => Promise.resolve({ ok: true }) });
};

const script = window.document.createElement('script');
script.textContent = fix.js;
window.document.body.appendChild(script);

const container = window.document.getElementById('s4-dishes--' + KEY);
container.querySelector('[data-role="name"]').value = 'Chicken Parm';
// [data-role="cat"].value stays '' (placeholder selected)

window.s4Keep(D, SLOT);

setTimeout(function() {
  const msgTxt = window.document.getElementById('s4-msg--' + KEY).textContent;
  const pass = !fetchCalled &&
               msgTxt.includes('Pick a category for') &&
               msgTxt.includes('Chicken Parm');
  console.log('CASE 3:', pass ? 'PASS' : 'FAIL');
  process.exit(pass ? 0 : 1);
}, 50);
```
