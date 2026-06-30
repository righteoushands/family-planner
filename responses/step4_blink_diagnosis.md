# Step 4 "blink" — DIAGNOSIS ONLY (no code changed)

## claud.md rules that apply today
- **Rule 15** — read-back done (all 20 rules + non-numbered guidance pasted in chat).
- **Rule 14 (pre-flight) #4** — root cause was a *hypothesis*, so this is diagnosis, not a fix.
- **Rule 20** — the same-page `window.location.href` reload (with `s4RestoreScroll`) is exactly what's suspected; any fix interacts with it.
- **Rules 7 & 12** — a no-reload fix means *more* embedded JS; backslash-n discipline will matter.
- **Rule 16** — a blinking UI is friction against calm/presence; Generate must stay a *draft to edit*, never auto-confirmed.
- **Rule 19** — any DOM helper must still route persistence through existing endpoints / data_helpers.
- **Rules 17 & 18, 9 & 10** — apply once we move to a fix (one fix per instruction; Aug-15 filter; smoke + harness on temp data). Not triggered by diagnosis.
- Not applicable: Rules 1–3, 5, 6, 8, 11, 13.

---

## 1. Any flash cause beyond the full-page navigation?
**No — the full-page reload is the sole cause.**
- No CSS transitions / `@keyframes` / animation / fade on the page or body (only a static `opacity:0.5` on the *disabled* Generate button).
- No loading spinner/overlay during reload.
- Minimal FOUC risk: one server-rendered document with **inline** `style="…"` + inline `<script>` — no external stylesheet race.

The "blink" is the inherent blank/white frame the browser paints between **unload and the reloaded document's first paint**, caused by `window.location.href = '/meal-wizard-step4'` on every button's success path (lines 222, 234, 244, 257). It is **separate from** the scroll fix: `s4RestoreScroll` (lines 263–264) restores `scrollY` *after* load — it cures the scroll jump, not the white frame (and on a slow paint can add a second small jump).

Per-button nuance: **Generate** waits up to a minute (button shows "Generating…") *then* flashes; **Keep / Change / Set this plan** are fast fetch → immediate flash.

## 2. Reference pattern — `toggleDashTask` (`render_schedule.py` line 1953)
No-reload optimistic update:
1. **Mutate DOM first** (optimistic): set `data-done`, dim label, show undo snack.
2. **POST** `fetch('/toggle-task', …)` urlencoded (`task_id`, `new_value`, `return_url`).
3. **`.then`:** `!r.ok` → **roll back**; else reconcile **locally from the DOM** — `_dashUpdateProgress` recomputes bar % and "N left" by *counting `data-done` attributes already in the DOM* (no refetch, line 2041), `_dashAdvance` reveals next task, `_dashMaybeHideChoreHeader` tidies.
4. **`.catch`** → roll back.

Key: success path **never reloads, never refetches markup**, doesn't read the response body for content (only `r.ok`). Server = persistence truth; visible update derived client-side; explicit rollback on failure.

## 3. No-reload requirements per Step 4 button
Each slot renders (via `_s4_slot_block`) as an **entry** affordance (name textarea + ingredients `<details>` + protein input + "Keep this meal") or a **confirmed** display (collapsed name + recipe label + source tag + optional "off shopping list" + "Change").

| Button | On success, update in DOM | Difficulty / flag |
|---|---|---|
| **Set this plan** (`s4Lock`) | Reveal "Your plan is set…" banner at top; meals stay editable (no per-slot change). | **Easiest** — single element show. |
| **Keep** (`s4Keep`) | Swap that one slot row: entry → confirmed display; re-evaluate lock control (first lockable meal flips hint → "Set this plan" button). | Moderate. Confirmed string is server-computed (`format_dish_list` collapsing `dishes[]` into "lead with rest" + recipe-label + source-tag logic). **Flag:** don't rebuild that in JS — have the endpoint **return the rendered row fragment** to inject. |
| **Change** (`s4Change`) | Swap that one slot row: confirmed → entry affordance (rebuild textarea/details/protein/Keep); re-evaluate lock control. | Moderate. Verbose to reconstruct in JS; prefer returned fragment. |
| **Generate** (`s4Generate`) | Patch **every** empty slot across the whole week with its prefilled editable suggestion (details opened). | **NOT straightforward** — multi-slot, all content from server; effectively re-render the meals section. Best done by endpoint returning the re-rendered grid/fragments. Reload flash is dwarfed by the up-to-a-minute wait, so weakest conversion candidate. |

### Cross-cutting flags
- Current design states an invariant (lines 200–202): "on success the page RELOADS so the session stays the single source of truth — no client-side state to drift." Any partial update reintroduces that drift risk. Lowest-risk, most faithful approach: endpoints **return authoritative server-rendered fragments** for the client to inject (no JS markup reconstruction). Where adopted, Rule 20 scroll-restore becomes unnecessary for those buttons (no navigation).
- Rule 16: a no-reload Generate must keep suggestions as **entry** affordances (editable draft), never auto-confirmed.

**Conversion-ease ranking:** Set this plan → Keep ≈ Change (one-row swap via returned fragment) → Generate (whole-week re-render).

*No fix proposed; findings only.*
