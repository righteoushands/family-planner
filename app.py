"""
app.py — HTTP server and router only.
All rendering lives in render_*.py modules.
All data I/O lives in data_helpers.py.
"""
import os, uuid, time as _time, sys, threading

# ── Tee stderr → data/server.log so Felix can see runtime errors ──────────────
os.makedirs("data", exist_ok=True)
class _TeeWriter:
    """Writes to both the original stream and data/server.log."""
    _lock = threading.Lock()
    _log_path = "data/server.log"
    _max_bytes = 300_000   # ~300 KB; trimmed to half when exceeded
    def __init__(self, original):
        self._orig = original
        # Trim log file to last 150 KB on startup
        try:
            if os.path.getsize(self._log_path) > self._max_bytes:
                with open(self._log_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                keep = content[-(self._max_bytes // 2):]
                nl = keep.find("\n")
                if nl >= 0:
                    keep = keep[nl + 1:]
                with open(self._log_path, "w", encoding="utf-8", errors="replace") as f:
                    f.write(keep)
        except Exception:
            pass
    def write(self, data):
        if data:
            try: self._orig.write(data)
            except Exception: pass
            try:
                with _TeeWriter._lock:
                    with open(self._log_path, "a", encoding="utf-8", errors="replace") as f:
                        f.write(data)
                    if os.path.getsize(self._log_path) > self._max_bytes:
                        with open(self._log_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        keep = content[-(self._max_bytes // 2):]
                        nl = keep.find("\n")
                        if nl >= 0: keep = keep[nl + 1:]
                        with open(self._log_path, "w", encoding="utf-8", errors="replace") as f:
                            f.write(keep)
            except Exception:
                pass
    def flush(self):
        try: self._orig.flush()
        except Exception: pass
    def __getattr__(self, name):
        return getattr(self._orig, name)

if not isinstance(sys.stderr, _TeeWriter):
    sys.stderr = _TeeWriter(sys.stderr)
if not isinstance(sys.stdout, _TeeWriter):
    sys.stdout = _TeeWriter(sys.stdout)


# ── Izzy session state — guards against stale edits ──────────────────────────
# Tracks the last read and write timestamps per file in the current process
# lifetime. Used by /dev-write and /dev-apply to enforce the rule:
#   "Once you have written to a file, you must re-READ it before writing again."
# This kills the #1 cause of file corruption — Izzy editing using stale line
# numbers from before his own previous edit.  Resets on every app restart,
# which is the right granularity (each restart starts a fresh session).
_izzy_file_state: dict = {}   # {filename: {"last_read": float, "last_write": float}}


def _izzy_check_stale(filename: str) -> str:
    """Return error message if a write to `filename` would be stale, else ''."""
    st = _izzy_file_state.get(filename)
    if not st: return ""
    lw = st.get("last_write", 0.0)
    lr = st.get("last_read", 0.0)
    if lw and lr <= lw:
        return (f"STALE EDIT BLOCKED — you wrote to {filename} earlier in this session "
                f"and have not re-READ it since. Your line numbers are stale. "
                f"Issue [READ: {filename}:start-end] for the affected range, then "
                f"propose your edit again with fresh line numbers.")
    return ""


def _izzy_mark_read(filename: str) -> None:
    st = _izzy_file_state.setdefault(filename, {})
    st["last_read"] = _time.time()


def _izzy_mark_write(filename: str) -> None:
    st = _izzy_file_state.setdefault(filename, {})
    st["last_write"] = _time.time()


def _izzy_diff(old: str, new: str, filename: str, ctx: int = 3) -> str:
    """Return a short unified diff so Izzy can see what actually landed."""
    import difflib as _dl
    diff = list(_dl.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{filename}", tofile=f"b/{filename}",
        n=ctx,
    ))
    if not diff: return "(no textual change)"
    out = "".join(diff)
    # Cap the diff size sent back so we don't blow up the response
    return out if len(out) < 8000 else out[:8000] + "\n… [diff truncated]"


def _izzy_syntax_ok(filename: str, new_text: str) -> tuple[bool, str]:
    """Validate proposed file content.  Returns (ok, error_message)."""
    suffix = os.path.splitext(filename)[1]
    if suffix == ".py":
        import ast as _ast
        try:
            _ast.parse(new_text, filename=filename)
            return True, ""
        except SyntaxError as ex:
            line = ex.lineno or "?"; col = ex.offset or "?"
            return False, f"SyntaxError at {filename} line {line}, col {col}: {ex.msg}"
    if suffix == ".json":
        import json as _jc
        try:
            _jc.loads(new_text)
            return True, ""
        except Exception as ex:
            return False, f"Invalid JSON in {filename}: {ex}"
    return True, ""


def _izzy_size_ok(new_text: str, old_span_lines: int = 0) -> tuple[bool, str]:
    """Reject edits larger than ~120 lines of NEW content or ~120 lines of OLD span."""
    nlines = new_text.count("\n") + 1
    if nlines > 120:
        return False, (f"EDIT TOO LARGE — {nlines} lines proposed (cap is 120). "
                       f"Split this into smaller, focused edits. The 'rewrite the "
                       f"whole file' pattern is exactly what causes the corruption "
                       f"you are trying to avoid.")
    if old_span_lines > 120:
        return False, (f"REPLACEMENT SPAN TOO WIDE — {old_span_lines} lines targeted "
                       f"(cap is 120). Edit a narrower range.")
    return True, ""

# ── Pin the process timezone to Eastern so date.today() / datetime.now()
# ── always reflect the McAdams family's local time, not UTC.
os.environ.setdefault("TZ", "America/New_York")
_time.tzset()

from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from urllib.parse import parse_qs, urlparse

import auth as _auth

from daily_schedule_engine import CHILDREN, set_task_done
from notes_router import add_note, archive_note, load_notes, save_notes
from school_pdf_engine import (
    approve_school_preview, extract_pdf_text,
    load_school_preview, parse_school_pdf_text, save_school_preview,
)
import gdrive as _gdrive
from safe_utils import safe_save_json, begin_companion_turn, finish_companion_turn
from companion_handoffs import undo_instructions as _undo_instructions
_UNDO_BLOCK = "\n" + "\n".join(_undo_instructions())


def _shrink_image_for_anthropic(raw_bytes: bytes, mime: str):
    """Anthropic enforces a 5 MB cap on the BASE64 representation of each
    image (~3.7 MB raw). iPhone JPEGs routinely exceed that. This shrinks
    the image (resizing + JPEG re-encoding with progressively lower quality)
    until it fits, returning (bytes, mime). Falls back to the original bytes
    if Pillow isn't available — caller will get a clearer error from the API.
    """
    _CAP_RAW = 3 * 1024 * 1024  # ~4 MB base64; safe margin under 5 MB cap
    if len(raw_bytes) <= _CAP_RAW:
        return raw_bytes, mime
    try:
        from PIL import Image
        import io
    except Exception:
        return raw_bytes, mime
    try:
        im = Image.open(io.BytesIO(raw_bytes))
        # Honor EXIF orientation so portrait photos don't end up sideways
        try:
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        # Iteratively shrink the long edge and lower JPEG quality.
        long_edge = max(im.size)
        for max_dim, qual in [(2200, 88), (1800, 85), (1400, 82), (1100, 78), (900, 75)]:
            if long_edge > max_dim:
                ratio = max_dim / float(long_edge)
                new_w = int(im.size[0] * ratio)
                new_h = int(im.size[1] * ratio)
                im2 = im.resize((new_w, new_h), Image.LANCZOS)
            else:
                im2 = im
            buf = io.BytesIO()
            im2.save(buf, format="JPEG", quality=qual, optimize=True)
            data = buf.getvalue()
            if len(data) <= _CAP_RAW:
                return data, "image/jpeg"
        # Last resort: return whatever the smallest pass produced
        return data, "image/jpeg"
    except Exception:
        return raw_bytes, mime

from config import HOST, PORT, ROADMAP_STATUSES, WEEKDAYS
from data_helpers import (
    safe_int, clean_text, clean_child, clean_weekday, clean_priority,
    lines_to_list, sort_school_days, is_math_subject, is_math_test_text,
    load_manual_tasks, save_manual_tasks, active_manual_tasks,
    load_chores_data, save_chores_data,
    load_roadmap, save_roadmap,
    load_mom_notes, save_mom_notes,
    load_calendar_config, save_calendar_config,
    load_calendar_rules, save_calendar_rules,
    load_subscribed_calendars, save_subscribed_calendars,
    load_liturgical_custom, save_liturgical_custom,
    advance_recurring_task,
    load_thankyou_reminders, save_thankyou_reminders,
    list_snapshots, restore_snapshot, load_snapshot_data,
)
from ui_helpers import parse_urlencoded_body, parse_multipart_form
from render_schedule import render_child_schedule, render_today_all, render_week, render_print_day, render_print_week, render_print_child_day_list
from render_week_view import render_week_view
from render_schedule_support import generate_half_hour_times
from render_calendar import render_calendar_page, refresh_calendar
from render_liturgical import render_liturgical_page, render_liturgical_edit_page
from render_readings import render_readings_page
from render_lucy import render_lucy_page, build_lucy_context
from render_lorenzo import render_lorenzo_page, build_lorenzo_context
from render_gregory import render_gregory_page, build_gregory_context
from render_week_school import render_week_school_page
from render_coach import render_coach_page, build_coach_context
from render_monica import render_monica_page, build_monica_context
from render_plan_importer import (
    render_plan_import_page, build_analysis_system_prompt,
    _load_upcoming_events, _format_events_summary,
)
from render_curriculum import render_curriculum_page, parse_modg_paste
from render_subject import (
    render_subject_page, render_grades_summary_page,
    add_image_entry, add_manual_entry, delete_entry,
    add_link, delete_link, add_document, delete_document,
    GRADE_IMG_DIR, GRADE_DOC_DIR,
)
import plan_history as _plan_history
from render_memory_book import render_memory_book_page, add_memory_entry, delete_memory_entry
from render_chores import render_chores_page, render_van_roles_page, apply_laundry_defaults, apply_van_rotation
from render_misc import (
    render_dashboard, render_mom_page, render_notes, render_tasks,
    render_roadmap_page, render_planner_page, render_history_page,
    render_school_page, render_school_edit_page, render_now_page,
    render_thankyou_page,
)
from render_settings import render_settings_page, load_app_settings, save_app_settings
from render_signup import render_signup_page, render_waitlist_admin, save_signup
from render_ai_planner import build_context_packet, render_ai_panel
from render_morning_anchor import save_anchor_state
from render_meals import (
    render_meal_planner_page, render_meal_print_page,
    load_meal_plan, save_meal_plan, load_inventory, save_inventory,
    load_recipes, save_recipe, _build_meal_prompt, _week_key, _planning_week_key,
)
from render_daily_plan import (
    get_or_seed_plan, add_item_to_plan, toggle_plan_item,
    delete_plan_item, reorder_plan_items, update_item_time,
    publish_plan, reset_plan, render_plan_fragment_html,
    sort_plan_chronologically,
    save_day_template, load_day_grid, save_day_grid,
    get_or_seed_grid, publish_day_grid, render_grid_print_page,
)

# Lock protecting the load → modify → save cycle for manual_tasks.json.
# The server is ThreadingMixIn so concurrent toggle-task requests would otherwise
# race and overwrite each other's deletions.
_MANUAL_TASKS_LOCK = threading.Lock()


def _apply_coach_program_saves(text: str) -> int:
    """
    Parse <save_program person="X" title="Y">...body...</save_program> tags from
    Coach's response and persist each one via data_helpers.save_coach_program.
    Returns the count of programs saved.  Silently ignores malformed tags so a
    bad Coach response never breaks the chat reply.
    """
    import re as _re
    _VALID = {"Lauren", "Mom", "JP", "Joseph", "Michael", "James", "John", "Family"}
    rx = _re.compile(
        r'<save_program\b([^>]*)>([\s\S]*?)</save_program>',
        _re.IGNORECASE,
    )
    saved = 0
    try:
        from data_helpers import save_coach_program as _scp
    except Exception:
        return 0
    for m in rx.finditer(text or ""):
        attrs_raw = m.group(1) or ""
        body = (m.group(2) or "").strip()
        if not body:
            continue
        # Accept either single- or double-quoted attribute values
        person_m = _re.search(r'''person\s*=\s*["']([^"']+)["']''', attrs_raw, _re.IGNORECASE)
        title_m  = _re.search(r'''title\s*=\s*["']([^"']+)["']''',  attrs_raw, _re.IGNORECASE)
        person = (person_m.group(1).strip() if person_m else "")
        # Normalize Mom → Lauren so all entries land in one bucket
        if person.lower() == "mom":
            person = "Lauren"
        if person not in _VALID:
            continue
        title = (title_m.group(1).strip() if title_m else "Untitled program")
        try:
            _scp(person, title, body)
            saved += 1
        except Exception:
            continue
    return saved


_AI_GUARDRAILS = """

== UNIVERSAL OUTPUT RULES (apply on EVERY reply) ==
🚫 NEVER emit Anthropic tool-use markup. This app does NOT use it. The following
   patterns are FORBIDDEN — if you write them, the server ignores them, nothing
   saves, and you will have lied to Lauren about what you did:
     <function_calls>…</function_calls>
     <invoke name="…">…</invoke>
     <parameter name="…">…</parameter>
     update_X({…}), function_call({…}), or any JSON-RPC-looking call.
   These come from your training. Forget them here.

✅ The ONLY real action tags are the explicit ones documented in the section(s)
   above for your role (e.g. [MEAL_UPDATE:…], <plan_update>, <schedule_update>,
   <frol_update>, <cycle_log>, etc.). Use those EXACT formats — character-for-
   character — and nothing else.

🔇 The server strips your action tags out of the message Lauren sees. Do NOT
   show the raw tag syntax as "code" or explain it as "something Replit needs
   to add to the codebase." Just emit the tag and confirm in plain English.

🚫 NEVER claim you can't see her data, can't read other pages, that she needs
   to paste anything, or that some other companion "needs to process" your
   changes. You write directly to the same files everyone reads.
"""


_TOOL_USE_RX = __import__('re').compile(
    r'<function_calls>[\s\S]*?</function_calls>|<invoke\b[^>]*>[\s\S]*?</invoke>',
    __import__('re').IGNORECASE
)

def _strip_hallucinated_tool_use(text: str) -> str:
    """Remove fake Anthropic tool-use markup that companions sometimes emit.
    These never get parsed by anything in this app — they're hallucinations
    from training data — and they look like ugly code in chat."""
    if not text:
        return text
    cleaned = _TOOL_USE_RX.sub('', text)
    # Collapse the blank lines we left behind, but keep paragraph breaks.
    import re as _r
    cleaned = _r.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned


def _apply_frol_updates(text: str, weekday: str) -> str:
    """
    Parse any <frol_update> action tags in `text` and apply them to the
    Family Rule of Life data files.  Returns a status-marker string
    (empty if no tags found) to be appended to the saved history message.

    Tag format:
        <frol_update weekday="Monday" person="Family">
        9:00 AM: Morning Prayer
        10:00 AM: Morning Jobs
        </frol_update>

    person="Family" (or omitted) → writes to family_schedule.json
    person="JP" (etc.)           → writes to data/day_templates/{Weekday}.json
    """
    import re as _fre
    import json as _fj
    from pathlib import Path as _fPath

    _VALID_DAYS    = {"Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"}
    _VALID_PERSONS = {"JP","Joseph","Michael","Lauren","John","Family","Mom"}

    _rx = _fre.compile(r'<frol_update\b([^>]*)>([\s\S]*?)</frol_update>', _fre.IGNORECASE)
    markers = ""

    for _m in _rx.finditer(text):
        _attrs = _m.group(1)
        _body  = _m.group(2)

        _wd_m = _fre.search(r'weekday=["\']([^"\']+)["\']', _attrs, _fre.I)
        _pe_m = _fre.search(r'person=["\']([^"\']+)["\']',  _attrs, _fre.I)
        _wday  = _wd_m.group(1).strip().title() if _wd_m else weekday
        _per   = _pe_m.group(1).strip()          if _pe_m else "Family"
        if _per == "Mom":
            _per = "Lauren"

        if _wday not in _VALID_DAYS:
            markers += f"\n(frol_update: unrecognised weekday '{_wday}')"
            continue

        # Parse "H:MM AM/PM: Value" lines
        _slots = {}
        for _ln in _body.strip().splitlines():
            _lm = _fre.match(r'^(\d+:\d+\s*(?:AM|PM))\s*:\s*(.*)$', _ln.strip(), _fre.I)
            if _lm:
                _slots[_lm.group(1).strip()] = _lm.group(2).strip()

        if not _slots:
            continue

        try:
            if _per in ("Family", ""):
                # ── Family-wide → day template (Mom column) ───────────────────
                # family_schedule.json is retired; "Family" slots go to Mom's
                # FROL day template so all consumers read from one source.
                _per = "Mom"
                _tp2 = _fPath(f"data/day_templates/{_wday}.json")
                if _tp2.exists():
                    _td2 = _fj.loads(_tp2.read_text(encoding="utf-8"))
                else:
                    _td2 = {"weekday": _wday, "grid": {}}
                _mom_col = _td2.setdefault("grid", {}).setdefault("Mom", {})
                for _t, _v in _slots.items():
                    if _v:
                        _mom_col[_t] = _v
                    else:
                        _mom_col.pop(_t, None)
                safe_save_json(str(_tp2), _td2)
                markers += f"\n[FROL_UPDATED:Mom:{_wday}:{len(_slots)} slots]"
            else:
                # ── Person-specific → day_templates/{Weekday}.json ────────────
                _tp = _fPath(f"data/day_templates/{_wday}.json")
                if _tp.exists():
                    _td = _fj.loads(_tp.read_text(encoding="utf-8"))
                else:
                    _td = {"weekday": _wday, "grid": {}}
                _grid = _td.setdefault("grid", {})
                _pg   = _grid.setdefault(_per, {})
                for _t, _v in _slots.items():
                    if _v:
                        _pg[_t] = _v
                    else:
                        _pg.pop(_t, None)
                safe_save_json(str(_tp), _td)
                markers += f"\n[FROL_UPDATED:{_per}:{_wday}:{len(_slots)} slots]"
        except Exception as _fe:
            markers += f"\n(frol_update error: {_fe})"

    return markers


def _render_change_pin_page(viewer: str, error: str = "", ok: str = "") -> str:
    """Simple PIN-change page for children (and admins redirected to settings)."""
    from html import escape as _esc
    from ui_helpers import html_page, page_header
    u = _auth.USERS.get(viewer, {})
    color = u.get("color", "#1f2937")
    name  = u.get("name", viewer.title())
    no_pin = not u.get("pin_required", True)

    if no_pin:
        body = (
            f'{page_header("Change PIN")}'
            f'<div class="card" style="text-align:center;padding:32px 24px;">'
            f'<p style="font-size:1.1em;color:var(--ink-muted);">'
            f'{_esc(name)} logs in by tapping the avatar — no PIN needed.</p>'
            f'</div>'
        )
        return html_page("Change PIN", body)

    alert = ""
    if ok:
        alert = ('<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;'
                 'padding:12px 16px;color:#15803d;font-weight:600;margin-bottom:18px;">'
                 '&#10003; PIN changed successfully!</div>')
    elif error:
        alert = (f'<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:12px;'
                 f'padding:12px 16px;color:#b91c1c;font-weight:600;margin-bottom:18px;">'
                 f'{_esc(error)}</div>')

    back = f"/schedule/{viewer}" if not _auth.is_admin(viewer) else "/"

    body = f"""
{page_header("Change PIN")}
<div class="card" style="max-width:400px;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;">
    <div style="width:44px;height:44px;border-radius:50%;background:{color};
                display:flex;align-items:center;justify-content:center;
                color:white;font-size:1.1em;font-weight:800;">
      {_esc(u.get('emoji', name[0]))}
    </div>
    <div>
      <div style="font-weight:700;color:var(--ink);">{_esc(name)}</div>
      <div style="font-size:0.78em;color:var(--ink-muted);">Change your 4-digit login PIN</div>
    </div>
  </div>

  {alert}

  <form method="POST" action="/change-pin" style="display:flex;flex-direction:column;gap:14px;">
    <div>
      <label style="font-size:0.82em;font-weight:600;color:var(--ink-muted);
                    display:block;margin-bottom:6px;">Current PIN</label>
      <input type="password" name="current_pin" inputmode="numeric" maxlength="4"
        pattern="[0-9]{{4}}" placeholder="&#9679;&#9679;&#9679;&#9679;" required
        style="width:100%;padding:12px 14px;border:1.5px solid var(--border-light);
               border-radius:12px;font-size:1.1em;letter-spacing:.2em;
               font-family:inherit;text-align:center;">
    </div>
    <div>
      <label style="font-size:0.82em;font-weight:600;color:var(--ink-muted);
                    display:block;margin-bottom:6px;">New PIN</label>
      <input type="password" name="new_pin" inputmode="numeric" maxlength="4"
        pattern="[0-9]{{4}}" placeholder="&#9679;&#9679;&#9679;&#9679;" required
        style="width:100%;padding:12px 14px;border:1.5px solid var(--border-light);
               border-radius:12px;font-size:1.1em;letter-spacing:.2em;
               font-family:inherit;text-align:center;">
    </div>
    <div>
      <label style="font-size:0.82em;font-weight:600;color:var(--ink-muted);
                    display:block;margin-bottom:6px;">Confirm new PIN</label>
      <input type="password" name="confirm_pin" inputmode="numeric" maxlength="4"
        pattern="[0-9]{{4}}" placeholder="&#9679;&#9679;&#9679;&#9679;" required
        style="width:100%;padding:12px 14px;border:1.5px solid var(--border-light);
               border-radius:12px;font-size:1.1em;letter-spacing:.2em;
               font-family:inherit;text-align:center;">
    </div>
    <div style="display:flex;gap:10px;margin-top:4px;">
      <button type="submit"
        style="flex:1;background:{color};color:white;border:none;border-radius:12px;
               padding:14px;font-weight:700;font-size:0.95em;cursor:pointer;
               font-family:inherit;">
        Save new PIN
      </button>
      <a href="{back}"
        style="flex:1;background:#f3f4f6;color:#374151;border-radius:12px;
               padding:14px;font-weight:700;font-size:0.95em;cursor:pointer;
               font-family:inherit;text-align:center;text-decoration:none;
               display:flex;align-items:center;justify-content:center;">
        Cancel
      </a>
    </div>
  </form>
</div>
"""
    return html_page("Change PIN", body)


class Handler(BaseHTTPRequestHandler):

    # ── Auth helpers ──────────────────────────────────────────────────────────

    def _parse_cookie(self) -> dict:
        raw = self.headers.get("Cookie", "")
        result = {}
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                result[k.strip()] = v.strip()
        return result

    def _get_viewer(self):
        """Return the logged-in username or None."""
        token = self._parse_cookie().get("session", "")
        return _auth.get_session_user(token) if token else None

    def _set_session_cookie(self, token: str):
        """Set a session cookie (no max-age = browser-close expiry)."""
        self.send_header("Set-Cookie", f"session={token}; Path=/; HttpOnly; SameSite=None; Secure")

    def _clear_session_cookie(self):
        self.send_header("Set-Cookie", "session=deleted; Path=/; HttpOnly; SameSite=None; Secure; Max-Age=0")

    def _redirect(self, location: str, code: int = 302):
        self.send_response(code)
        self.send_header("Location", location)
        self.end_headers()

    def _require_auth(self, path: str) -> str | None:
        """
        Check auth for a GET request.
        Sets the viewer context and returns the username if allowed.
        Returns None and sends the redirect itself if NOT allowed.
        """
        user = self._get_viewer()
        _auth.set_viewer(user)

        # Public paths that never need auth
        if path in ("/login", "/logout") or path.startswith("/static/"):
            return user  # pass through

        if not user:
            # Preserve full URL (including query string) so the user lands
            # back on the exact page they wanted after logging in.
            from urllib.parse import quote as _quote
            full = _quote(self.path, safe="/:@!$&'()*+,;=?%#")
            self._redirect(f"/login?next={full}")
            return None

        if not _auth.can_get(user, path):
            self._redirect("/login?denied=1")
            return None

        return user

    def _require_post_auth(self, path: str) -> str | None:
        """
        Check auth for a POST request.
        Returns username if allowed, None (and redirect) if not.
        """
        user = self._get_viewer()
        _auth.set_viewer(user)

        if not user:
            from urllib.parse import quote as _q
            referer = self.headers.get("Referer", "/")
            safe = referer if referer.startswith("/") else "/"
            self._redirect(f"/login?next={_q(safe)}")
            return None

        if not _auth.can_post(user, path):
            self._redirect("/")
            return None

        return user

    def do_GET(self):
        route = urlparse(self.path)
        path  = route.path
        query = parse_qs(route.query)
        body  = None

        # ── Family Quest — served on same port via bridge ─────────────────────
        if path.startswith("/quest"):
            import sys as _fqsys, os as _fqos
            _fqdir = _fqos.path.join(_fqos.path.dirname(_fqos.path.abspath(__file__)), "family_quest")
            if _fqdir not in _fqsys.path:
                _fqsys.path.insert(0, _fqdir)
            from fq_bridge import handle_get as _fq_handle_get
            _fq_handle_get(self); return

        # ── Login page (public) ───────────────────────────────────────────────
        if path == "/login":
            from render_login import render_login_page
            existing = self._get_viewer()
            _auth.set_viewer(existing)
            if existing:
                dest = "/" if _auth.is_admin(existing) else f"/schedule/{existing}"
                self._redirect(dest); return
            denied = query.get("denied", [""])[0]
            redir  = query.get("next", ["/"])[0]
            err_msg = "You don't have permission to view that page." if denied == "1" else ""
            pg = render_login_page(error=err_msg, redirect_to=redir)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(pg.encode())
            except BrokenPipeError: pass
            return

        # ── Logout ────────────────────────────────────────────────────────────
        if path == "/logout":
            token = self._parse_cookie().get("session", "")
            if token: _auth.destroy_session(token)
            _auth.set_viewer(None)
            self.send_response(302)
            self._clear_session_cookie()
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # ── Family Quest SSO ─────────────────────────────────────────────────
        # Already logged into main app → auto-create FQ session → no second login
        if path == "/quest-sso":
            _sso_user = self._get_viewer()
            _FQ_CHILD_KEYS = {"jp", "joseph", "michael", "james"}
            _sso_key = _sso_user.lower() if _sso_user else ""
            if _sso_key in _FQ_CHILD_KEYS:
                try:
                    import sys as _ssys, os as _sos
                    _fq_root2 = _sos.path.join(_sos.path.dirname(_sos.path.abspath(__file__)), "family_quest")
                    if _fq_root2 not in _ssys.path:
                        _ssys.path.insert(0, _fq_root2)
                    from fq_api import create_session as _fq_create_session
                    _fq_tok = _fq_create_session(_sso_key)
                    self.send_response(302)
                    self.send_header("Set-Cookie",
                        f"fq_session={_fq_tok}; Path=/quest; HttpOnly; SameSite=None; Secure")
                    self.send_header("Location", f"/quest/board/{_sso_key}")
                    self.end_headers()
                except Exception:
                    self.send_response(302)
                    self.send_header("Location", f"/quest/board/{_sso_key}")
                    self.end_headers()
            else:
                # Parent or unknown — send to FQ login
                self.send_response(302)
                self.send_header("Location", "/quest/")
                self.end_headers()
            return

        # ── Static files (/static/*) ─────────────────────────────────────────
        if path.startswith("/static/"):
            import os, mimetypes
            filename = path[8:]  # strip "/static/"
            filename = filename.replace("..", "").replace("/", "").strip()
            static_path = os.path.join("static", filename)
            try:
                with open(static_path, "rb") as f:
                    content = f.read()
                mime, _ = mimetypes.guess_type(filename)
                mime = mime or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                try: self.wfile.write(content)
                except BrokenPipeError: pass
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
            return

        # ── Auth gate ─────────────────────────────────────────────────────────
        viewer = self._require_auth(path)
        if viewer is None:
            return  # _require_auth already sent the redirect

        # ── Change PIN (child self-service) ──────────────────────────────────
        if path == "/change-pin":
            body = _render_change_pin_page(viewer, query.get("error",[""])[0], query.get("ok",[""])[0])
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(body.encode())
            except BrokenPipeError: pass
            return

        if   path == "/":                body = render_dashboard()
        elif path == "/today":           body = render_today_all(query.get("date",[""])[0])
        elif path == "/programs":
            from render_programs import render_programs_page
            body = render_programs_page(
                focus = clean_text(query.get("focus",[""])[0]),
                flash = clean_text(query.get("msg",[""])[0]),
            )
        elif path == "/set-school-mode":
            # Quick toggle: /set-school-mode?mode=normal|light_week|custom_pause
            _sm = clean_text(query.get("mode",["normal"])[0])
            if _sm in ("normal","light_week","custom_pause"):
                _ss = load_app_settings()
                _ss.setdefault("family_constraints",{})["school_mode"] = _sm
                save_app_settings(_ss)
            self.send_response(302)
            self.send_header("Location", query.get("next",["/today"])[0])
            self.end_headers()
            return
        elif path == "/now":             body = render_now_page()
        elif path == "/week":
            _wk = clean_text(query.get("week", [""])[0]) or None
            body = render_week_view(_wk)
        elif path == "/week-school":     body = render_week_school_page(iso=clean_text(query.get("date",[""])[0]) or None)
        elif path == "/school":          body = render_school_page(status_message=clean_text(query.get("msg",[""])[0]))
        elif path == "/api/today-progress":
            # Lightweight progress-sync endpoint used by homepage polling.
            # Returns {task_id: bool} for all tasks whose key contains today's ISO date.
            _tp_date = clean_text(query.get("date", [""])[0]) or normalize_date_query("")
            try:
                from daily_schedule_engine import load_progress
                _prog = load_progress()
                # Filter to only keys that contain this date string so the payload is small
                self._send_json({k: bool(v) for k, v in _prog.items()
                                 if _tp_date in k and v})
            except Exception as _tpe:
                self._send_json({"error": str(_tpe)}, 500)
            return
        elif path == "/api/boys-tasks":
            if not _auth.is_admin(user):
                self._send_json({"error": "unauthorized"}, 403); return
            _bt_date = clean_text(query.get("date", [""])[0])
            try:
                from daily_schedule_engine import boys_task_snapshot
                self._send_json(boys_task_snapshot(_bt_date))
            except Exception as _bte:
                self._send_json({"error": str(_bte)}, 500)
            return
        elif path == "/api/child-tasks":
            # Per-child task snapshot: ?child=JP&date=2026-04-06
            if not _auth.is_admin(user):
                self._send_json({"error": "unauthorized"}, 403); return
            _ct_child = clean_text(query.get("child", [""])[0])
            _ct_date  = clean_text(query.get("date",  [""])[0])
            try:
                from daily_schedule_engine import boys_task_snapshot
                _ct_child = _ct_child.strip()
                if _ct_child and _ct_child not in CHILDREN:
                    self._send_json({"error": f"Unknown child: {_ct_child}"}, 400); return
                snap = boys_task_snapshot(_ct_date)
                if _ct_child:
                    child_data = snap["children"].get(_ct_child, {})
                    self._send_json({
                        "child":      _ct_child,
                        "iso":        snap["iso"],
                        "weekday":    snap["weekday"],
                        "date_label": snap["date_label"],
                        **child_data,
                    })
                else:
                    self._send_json(snap)
            except Exception as _cte:
                self._send_json({"error": str(_cte)}, 500)
            return
        elif path == "/gdrive-files":
            if not _auth.is_admin(user):
                self._send_json({"error": "unauthorized"}, 403); return
            folder_id = clean_text(query.get("folder", ["root"])[0]) or "root"
            try:
                files = _gdrive.list_files(folder_id)
                self._send_json({"files": files, "folder": folder_id})
            except Exception as _ge:
                self._send_json({"error": str(_ge)}, 500)
            return
        elif path == "/kids-week":
            from render_kids_week import render_kids_week_page
            wk = clean_text(query.get("week",[""])[0])
            body = render_kids_week_page(week_key=wk or None)
        elif path == "/plan-tomorrow":
            from render_plan_tomorrow import render_plan_tomorrow_page
            body = render_plan_tomorrow_page()
        elif path == "/plan-today":
            from render_plan_tomorrow import render_plan_tomorrow_page
            body = render_plan_tomorrow_page(for_date=date.today())
        elif path == "/plan-week":
            from render_plan_week import render_plan_week_page
            wk = clean_text(query.get("week",[""])[0])
            body = render_plan_week_page(week_key=wk or None)
        elif path == "/plan-month":
            from render_plan_month import render_plan_month_page
            mk = clean_text(query.get("month",[""])[0])
            body = render_plan_month_page(month_key=mk or None)
        elif path == "/plan-year":
            from render_plan_year import render_plan_year_page
            yr = clean_text(query.get("year",[""])[0])
            body = render_plan_year_page(year=yr or None)
        elif path == "/plan-quarter":
            from render_plan_quarter import render_plan_quarter_page
            qk = clean_text(query.get("quarter",[""])[0])
            body = render_plan_quarter_page(quarter_key=qk or None)
        elif path == "/virtues":
            from render_virtues import render_virtues_dashboard
            body = render_virtues_dashboard()
        elif path == "/5am":
            from render_5am import render_5am_page
            ds = clean_text(query.get("date",[""])[0])
            body = render_5am_page(date_str=ds or None)
        elif path == "/liturgy-hours":
            from render_liturgy_hours import render_liturgy_hours_page
            ds = clean_text(query.get("date",[""])[0])
            body = render_liturgy_hours_page(date_str=ds or None)
        elif path == "/prayer-intentions":
            from render_prayer import render_prayer_page
            status = clean_text(query.get("msg",[""])[0]).replace("+"," ")
            body = render_prayer_page(status)
        elif path.startswith("/prayer-photo/"):
            filename = path[len("/prayer-photo/"):]
            # Sanitise — no path traversal
            filename = filename.replace("/","").replace("\\","").replace("..","")
            photo_path = f"data/prayer/photos/{filename}"
            try:
                with open(photo_path, "rb") as f:
                    photo_data = f.read()
                ext = filename.rsplit(".",1)[-1].lower() if "." in filename else "jpg"
                mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png",
                        "gif":"image/gif","webp":"image/webp"}.get(ext,"image/jpeg")
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(photo_data)))
                self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                try: self.wfile.write(photo_data)
                except BrokenPipeError: pass
            except Exception:
                self.send_response(404)
                self.end_headers()
            return
        elif path.startswith("/prayer-intention/share/"):
            from render_prayer import render_share_page
            token = path[len("/prayer-intention/share/"):]
            body = render_share_page(clean_text(token))
        elif path == "/virtues/me":
            from render_virtues import render_virtue_me_page
            vp = clean_text(query.get("virtue",[""])[0])
            body = render_virtue_me_page(virtue_pick=vp or None)
        elif path == "/virtues/family":
            from render_virtues import render_virtue_family_page
            vp = clean_text(query.get("virtue",[""])[0])
            body = render_virtue_family_page(virtue_pick=vp or None)
        elif path.startswith("/virtues/child/"):
            from render_virtues import render_virtue_child_page
            child_id = path[len("/virtues/child/"):]
            vp = clean_text(query.get("virtue",[""])[0])
            body = render_virtue_child_page(child_id, virtue_pick=vp or None)
        elif path == "/school/edit":     body = render_school_edit_page(clean_child(query.get("child",[""])[0]))
        elif path == "/chores":          body = render_chores_page(status_message=query.get("msg",[""])[0])
        elif path == "/van-roles":       body = render_van_roles_page()
        elif path.startswith("/print/day/"):
            child_slug = path.split("/print/day/", 1)[1].strip("/")
            _print_date = query.get("date",[""])[0]
            if child_slug.lower() == "lauren":
                from render_misc import render_print_lauren_day
                body = render_print_lauren_day(_print_date)
            else:
                # Map slug back to canonical child name
                _slug_map = {c.lower(): c for c in ["Lauren", "John", "JP", "Joseph", "Michael", "James"]}
                canonical = _slug_map.get(child_slug.lower(), child_slug.capitalize())
                # Auto-sync quests for this child when printing their day list
                _quest_children = {"JP", "Joseph", "Michael", "James"}
                if canonical in _quest_children:
                    try:
                        import sys as _sys
                        _fq_path = os.path.join(os.path.dirname(__file__), "family_quest")
                        if _fq_path not in _sys.path:
                            _sys.path.insert(0, _fq_path)
                        from fq_data import sync_all_quests_for_child
                        sync_all_quests_for_child(canonical, _print_date)
                    except Exception:
                        pass
                body = render_print_child_day_list(canonical, _print_date)
        elif path == "/print/day":
            _print_date = query.get("date",[""])[0]
            # Auto-sync all children's quests when printing the full family day
            try:
                import sys as _sys
                _fq_path = os.path.join(os.path.dirname(__file__), "family_quest")
                if _fq_path not in _sys.path:
                    _sys.path.insert(0, _fq_path)
                from fq_data import sync_chores_from_daily_schedule
                sync_chores_from_daily_schedule(_print_date)
            except Exception:
                pass
            body = render_print_day(_print_date)
        elif path == "/print/week":      body = render_print_week()
        elif path == "/notes":           body = render_notes()
        elif path == "/tasks":           body = render_tasks()
        elif path == "/thankyou-reminders": body = render_thankyou_page()
        elif path == "/mom":             body = render_mom_page(target_date_str=query.get("date",[""])[0])
        elif path == "/mom-profile":
            from render_mom_profile import render_mom_profile_page
            body = render_mom_profile_page(target_date_str=query.get("date",[""])[0])
        elif path == "/john":
            from render_john import render_john_page
            body = render_john_page()
        elif path == "/friends":
            from render_friends import render_friends_page
            body = render_friends_page()
        elif path == "/roadmap":         body = render_roadmap_page()
        elif path == "/signup":           body = render_signup_page()
        elif path == "/waitlist":         body = render_waitlist_admin(False)
        elif path == "/family-schedule":
            self.send_response(302)
            self.send_header("Location", "/settings#s-systems")
            self.end_headers()
            return
        elif path == "/calendar":        body = render_calendar_page()
        elif path == "/planner":         body = render_planner_page()
        elif path == "/readings":         body = render_readings_page(date_str=query.get("date",[""])[0])
        elif path == "/lucy":
            html = render_lucy_page(iso=query.get("date",[""])[0], q=query.get("q",[""])[0], from_=query.get("from",[""])[0])
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/lorenzo-plan-state":
            import json as _pjg
            from data_helpers import load_planning_session, planning_session_summary
            _sess = load_planning_session()
            _info = planning_session_summary(_sess)
            self.send_response(200)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            try: self.wfile.write(_pjg.dumps(_info).encode("utf-8"))
            except BrokenPipeError: pass
            return
        elif path == "/lorenzo":
            html = render_lorenzo_page(q=query.get("q",[""])[0], from_=query.get("from",[""])[0])
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/headmaster":
            html = render_gregory_page(q=query.get("q",[""])[0], from_=query.get("from",[""])[0])
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/coach":
            html = render_coach_page(q=query.get("q",[""])[0], from_=query.get("from",[""])[0])
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/dr-monica":
            html = render_monica_page(q=query.get("q",[""])[0], from_=query.get("from",[""])[0])
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/plan-import-history":
            _ph_v = self._get_viewer()
            if not (_ph_v and _auth.is_admin(_ph_v)):
                self.send_response(302); self.send_header("Location","/"); self.end_headers(); return
            entry_id = (query.get("id",[""])[0] or "").strip()
            html = (_plan_history.render_history_entry(entry_id)
                    if entry_id else _plan_history.render_history_index())
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/grades":
            _gv = self._get_viewer()
            if not (_gv and _auth.is_admin(_gv)):
                self.send_response(302); self.send_header("Location","/"); self.end_headers(); return
            html = render_grades_summary_page()
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/subject":
            _sv = self._get_viewer()
            child   = (query.get("child",[""])[0] or "").strip()
            subject = (query.get("subject",[""])[0] or "").strip()
            is_admin = bool(_sv and _auth.is_admin(_sv))
            allowed = is_admin or (_sv and child and _sv.lower() == child.lower())
            if not allowed:
                self.send_response(302); self.send_header("Location","/"); self.end_headers(); return
            html = render_subject_page(child, subject, viewer_is_admin=is_admin)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path.startswith("/uploads/recipes/"):
            import mimetypes as _mt
            rel = "data" + path  # actual file lives at data/uploads/recipes/<file>
            if ".." in rel.split("/"):
                self.send_response(403); self.end_headers(); return
            try:
                with open(rel, "rb") as f:
                    data = f.read()
                mime, _ = _mt.guess_type(rel)
                self.send_response(200)
                self.send_header("Content-Type", mime or "application/octet-stream")
                self.send_header("Cache-Control", "private, max-age=86400")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                try: self.wfile.write(data)
                except BrokenPipeError: pass
            except FileNotFoundError:
                self.send_response(404); self.end_headers()
            return
        elif path.startswith("/uploads/grades/") or path.startswith("/uploads/grade_docs/"):
            import mimetypes as _mt
            from render_subject import safe_slug as _ss
            rel = path[1:]  # strip leading /
            # Block traversal
            if ".." in rel.split("/"):
                self.send_response(403); self.end_headers(); return
            # Ownership: admin OR file's child segment matches viewer
            _uv = self._get_viewer() or ""
            parts = rel.split("/")
            child_seg = parts[2] if len(parts) >= 3 else ""
            if not _auth.is_admin(_uv) and _ss(_uv).lower() != child_seg.lower():
                self.send_response(403); self.end_headers(); return
            try:
                with open(rel, "rb") as f:
                    data = f.read()
                mime, _ = _mt.guess_type(rel)
                self.send_response(200)
                self.send_header("Content-Type", mime or "application/octet-stream")
                self.send_header("Cache-Control", "private, max-age=3600")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                try: self.wfile.write(data)
                except BrokenPipeError: pass
            except FileNotFoundError:
                self.send_response(404); self.end_headers()
            return
        elif path == "/curriculum":
            _cur_viewer = self._get_viewer()
            if not (_cur_viewer and _auth.is_admin(_cur_viewer)):
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            html = render_curriculum_page()
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return

        elif path == "/gradebook":
            _cur_viewer = self._get_viewer()
            if not (_cur_viewer and _auth.is_admin(_cur_viewer)):
                self.send_response(302); self.send_header("Location", "/"); self.end_headers(); return
            from render_gradebook import render_gradebook_page
            _child = (query.get("child",[""])[0] or "").strip()
            _year  = (query.get("year",[""])[0] or "").strip()
            html = render_gradebook_page(child=_child, year=_year)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return

        elif path == "/assignment-analyzer":
            _cur_viewer = self._get_viewer()
            if not (_cur_viewer and _auth.is_admin(_cur_viewer)):
                self.send_response(302); self.send_header("Location", "/"); self.end_headers(); return
            from render_assignment_analyzer import render_assignment_analyzer_page
            html = render_assignment_analyzer_page()
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return

        elif path == "/assignment-image":
            # Serve the original uploaded scan/photo for an analysis card.
            _cur_viewer = self._get_viewer()
            if not (_cur_viewer and _auth.is_admin(_cur_viewer)):
                self.send_response(302); self.send_header("Location", "/"); self.end_headers(); return
            import os as _os
            from data_helpers import load_assignment_analyses
            wanted = clean_text(query.get("id",[""])[0])
            try:    n_idx = int(query.get("n",["0"])[0])
            except Exception: n_idx = 0
            rec = next((r for r in load_assignment_analyses() if r.get("id") == wanted), None)
            up_list = (rec or {}).get("upload_paths") or []
            if up_list and 0 <= n_idx < len(up_list):
                up_path = up_list[n_idx].get("path", "")
                mime    = up_list[n_idx].get("mime") or "application/octet-stream"
            else:
                # back-compat: old records have only upload_path / source_mime
                up_path = (rec or {}).get("upload_path", "")
                mime    = (rec or {}).get("source_mime") or "application/octet-stream"
            if not rec or not up_path or not _os.path.exists(up_path):
                self.send_response(404); self.send_header("Content-Type","text/plain"); self.end_headers()
                try: self.wfile.write(b"Not found")
                except BrokenPipeError: pass
                return
            try:
                with open(up_path, "rb") as f: blob = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(blob)))
                self.send_header("Cache-Control","private, max-age=300")
                self.end_headers()
                try: self.wfile.write(blob)
                except BrokenPipeError: pass
            except Exception as _e:
                self.send_response(500); self.send_header("Content-Type","text/plain"); self.end_headers()
                try: self.wfile.write(str(_e).encode())
                except BrokenPipeError: pass
            return
        elif path == "/plan-import":
            _pi_viewer = self._get_viewer()
            if not (_pi_viewer and _auth.is_admin(_pi_viewer)):
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            html = render_plan_import_page()
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/dev":
            _dv = self._get_viewer()
            if not (_dv and _auth.is_admin(_dv)):
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            from render_dev import render_dev_page
            from data_helpers import load_dev_history
            _dv_q    = query.get("q",    [""])[0]
            _dv_from = query.get("from", [""])[0]
            html = render_dev_page(load_dev_history(), q=_dv_q, from_=_dv_from)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return

        # ── Felix: server error log ────────────────────────────────────────────
        elif path == "/dev-logs":
            # Server log tail. Query params:
            #   n=N         → last N lines (default 300, max 2000)
            #   grep=PAT    → only lines matching regex PAT
            # Used both by the live-errors panel and by Izzy's [LOGS:] tag.
            import pathlib as _pl, re as _rl
            _dv = self._get_viewer()
            if not (_dv and _auth.is_admin(_dv)):
                self.send_response(403); self.end_headers(); return
            try: _n = max(1, min(2000, int(query.get("n", ["300"])[0])))
            except (ValueError, IndexError): _n = 300
            _grep_pat = query.get("grep", [""])[0].strip()
            log_path = _pl.Path("data/server.log")
            if log_path.exists():
                raw = log_path.read_text(encoding="utf-8", errors="replace")
                lines = raw.splitlines()
                if _grep_pat:
                    try:
                        rx = _rl.compile(_grep_pat, _rl.IGNORECASE)
                        lines = [ln for ln in lines if rx.search(ln)]
                    except _rl.error as ex:
                        lines = [f"(invalid regex: {ex})"]
                text = "\n".join(lines[-_n:])
            else:
                text = "No log file yet. Errors will appear here once the server logs something."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try: self.wfile.write(text.encode("utf-8", errors="replace"))
            except BrokenPipeError: pass
            return

        elif path == "/dev-health":
            # Tiny liveness probe. The Apply UI polls this for ~12 seconds after
            # restartServer() to detect a startup crash and auto-rollback the
            # undo stack. Returns 200 + the process pid+startup-time so the JS
            # can confirm the new process actually came up (different pid than
            # the one it talked to before).
            import os as _ohp
            pid = _ohp.getpid()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try: self.wfile.write(f"OK pid={pid}".encode())
            except BrokenPipeError: pass
            return

        elif path == "/dev-diag":
            # Static analysis for one source file. Reports syntax errors,
            # undefined names referenced at module scope, and obvious unused
            # imports. Pure-Python — no external linter required.
            import pathlib as _pdg, ast as _adg, builtins as _bdg
            _dv = self._get_viewer()
            if not (_dv and _auth.is_admin(_dv)):
                self.send_response(403); self.end_headers(); return
            fname = query.get("file", [""])[0].strip()
            fp = _pdg.Path(fname)
            if (not fname or fp.parent != _pdg.Path(".")
                    or fp.suffix != ".py" or not fp.exists()):
                self.send_response(404); self.send_header("Content-Type","text/plain"); self.end_headers()
                try: self.wfile.write(b"Diag: only existing project-root .py files allowed.")
                except BrokenPipeError: pass
                return
            src = fp.read_text(encoding="utf-8", errors="replace")
            findings: list[str] = []
            try:
                tree = _adg.parse(src, filename=fname)
            except SyntaxError as ex:
                txt = f"SYNTAX ERROR at {fname}:{ex.lineno}:{ex.offset}: {ex.msg}\n"
                self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
                try: self.wfile.write(txt.encode())
                except BrokenPipeError: pass
                return
            # Collect module-level defined names + imported names
            defined: set = set(dir(_bdg))
            imports: dict = {}    # name -> line
            used_names: set = set()
            for node in tree.body:
                if isinstance(node, (_adg.Import, _adg.ImportFrom)):
                    for n in node.names:
                        nm = n.asname or n.name.split(".")[0]
                        defined.add(nm); imports[nm] = node.lineno
                elif isinstance(node, (_adg.FunctionDef, _adg.AsyncFunctionDef, _adg.ClassDef)):
                    defined.add(node.name)
                elif isinstance(node, _adg.Assign):
                    for tgt in node.targets:
                        if isinstance(tgt, _adg.Name): defined.add(tgt.id)
            for node in _adg.walk(tree):
                if isinstance(node, _adg.Name) and isinstance(node.ctx, _adg.Load):
                    used_names.add(node.id)
                elif isinstance(node, _adg.Attribute) and isinstance(node.value, _adg.Name):
                    used_names.add(node.value.id)
            # Check for "from config import X" style — report missing X if config exists
            for node in tree.body:
                if isinstance(node, _adg.ImportFrom) and node.module:
                    mod_path = _pdg.Path(node.module.replace(".", "/") + ".py")
                    if mod_path.exists():
                        try:
                            mod_src = mod_path.read_text(encoding="utf-8", errors="replace")
                            mod_tree = _adg.parse(mod_src, filename=str(mod_path))
                            mod_defined: set = set()
                            for mn in mod_tree.body:
                                if isinstance(mn, _adg.Assign):
                                    for tgt in mn.targets:
                                        if isinstance(tgt, _adg.Name): mod_defined.add(tgt.id)
                                elif isinstance(mn, (_adg.FunctionDef, _adg.AsyncFunctionDef, _adg.ClassDef)):
                                    mod_defined.add(mn.name)
                                elif isinstance(mn, (_adg.Import, _adg.ImportFrom)):
                                    for n2 in mn.names:
                                        mod_defined.add(n2.asname or n2.name.split(".")[0])
                            for n in node.names:
                                if n.name != "*" and n.name not in mod_defined:
                                    findings.append(
                                        f"line {node.lineno}: 'from {node.module} import {n.name}' "
                                        f"— '{n.name}' is NOT defined in {mod_path}. "
                                        f"This will crash on startup."
                                    )
                        except SyntaxError: pass
            # Unused imports (lightweight check — module-level only)
            for nm, ln in imports.items():
                if nm not in used_names and nm not in ("annotations",):
                    findings.append(f"line {ln}: import '{nm}' appears unused.")
            if not findings:
                msg = f"DIAG OK — {fname} parses cleanly, no obvious issues."
            else:
                msg = f"DIAG {fname} — {len(findings)} finding(s):\n" + "\n".join("  • " + f for f in findings)
            self.send_response(200); self.send_header("Content-Type","text/plain; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(msg.encode())
            except BrokenPipeError: pass
            return

        # ── Felix: read a file or line range ──────────────────────────────────
        elif path == "/dev-read-file":
            import pathlib as _pl
            _dv = self._get_viewer()
            if not (_dv and _auth.is_admin(_dv)):
                self.send_response(403); self.end_headers(); return
            fname = query.get("file", [""])[0].strip()
            fpath = _pl.Path(fname)
            # Safety: only project-root files with allowed extensions
            allowed_exts = {".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt"}
            if (not fname or fpath.parent != _pl.Path(".")
                    or fpath.suffix not in allowed_exts
                    or not fpath.exists()):
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                try: self.wfile.write(b"File not found or not allowed.")
                except BrokenPipeError: pass
                return
            content = fpath.read_text(encoding="utf-8", errors="replace")
            all_lines = content.splitlines()
            total = len(all_lines)
            try:
                start = max(1, int(query.get("start", ["1"])[0])) - 1   # 0-indexed
            except (ValueError, IndexError):
                start = 0
            try:
                end = min(total, int(query.get("end", ["0"])[0]))
            except (ValueError, IndexError):
                end = 0
            if end == 0 or end > total:
                end = total
            selected = "\n".join(all_lines[start:end])
            # Mark this file as freshly read for stale-edit guarding
            _izzy_mark_read(fname)
            result = (f"=== {fname}  (lines {start+1}–{end} of {total}) ===\n\n"
                      + selected)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try: self.wfile.write(result.encode("utf-8", errors="replace"))
            except BrokenPipeError: pass
            return

        elif path == "/dev-grep-files":
            # Izzy's GREP tool — search for a pattern across project source files.
            # Query params: pattern (required), path (optional glob, default *.py)
            import pathlib as _pg
            import re as _rg
            _dv = self._get_viewer()
            if not (_dv and _auth.is_admin(_dv)):
                self.send_response(403); self.end_headers(); return
            _grep_pat  = query.get("pattern", [""])[0].strip()
            _grep_glob = query.get("path",    ["*.py"])[0].strip() or "*.py"
            if not _grep_pat:
                self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                try:
                    self.wfile.write(b"pattern required")
                except BrokenPipeError:
                    pass
                return
            try:
                _rx_grep = _rg.compile(_grep_pat, _rg.IGNORECASE)
            except _rg.error as _rge:
                self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                try:
                    self.wfile.write(f"Invalid regex: {_rge}".encode())
                except BrokenPipeError:
                    pass
                return
            _allowed = {".py",".js",".ts",".html",".css",".json",".md",".txt"}
            _root = _pg.Path(".")
            try:
                _files = sorted(_root.glob(_grep_glob))
            except Exception:
                _files = []
            _lines_out: list[str] = []
            _MATCH_LIMIT = 80
            for _fp in _files:
                if _fp.suffix not in _allowed or not _fp.is_file():
                    continue
                try:
                    _txt = _fp.read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    continue
                for _ln_i, _ln_txt in enumerate(_txt, 1):
                    if _rx_grep.search(_ln_txt):
                        _lines_out.append(f"{_fp.name}:{_ln_i}: {_ln_txt}")
                        if len(_lines_out) >= _MATCH_LIMIT:
                            _lines_out.append(f"... (capped at {_MATCH_LIMIT} matches)")
                            break
                if len(_lines_out) >= _MATCH_LIMIT:
                    break
            _grep_result = (f"=== GREP: {_grep_pat!r} in {_grep_glob} ===\n\n" +
                            ("\n".join(_lines_out) if _lines_out else "(no matches)"))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try: self.wfile.write(_grep_result.encode("utf-8", errors="replace"))
            except BrokenPipeError: pass
            return

        elif path == "/dev-git-log":
            # Izzy's git history tool — returns recent commits
            import subprocess as _sp
            _dv = self._get_viewer()
            if not (_dv and _auth.is_admin(_dv)):
                self.send_response(403); self.end_headers(); return
            try:
                _log = _sp.run(
                    ["git", "log", "--oneline", "--format=%h  %ad  %s", "--date=short", "-25"],
                    capture_output=True, text=True, timeout=10
                )
                _result = ("=== GIT LOG (last 25 commits) ===\n\n" +
                           (_log.stdout.strip() or "(no commits yet)"))
            except Exception as _e:
                _result = f"git log failed: {_e}"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try: self.wfile.write(_result.encode("utf-8", errors="replace"))
            except BrokenPipeError: pass
            return

        elif path == "/dev-git-diff":
            # Izzy's git diff tool — shows changes for a commit or range
            import subprocess as _sp
            _dv = self._get_viewer()
            if not (_dv and _auth.is_admin(_dv)):
                self.send_response(403); self.end_headers(); return
            _ref = query.get("ref", ["HEAD~1"])[0].strip() or "HEAD~1"
            # Safety: only allow safe ref characters (hashes, ~, ^, HEAD, digits, dots)
            import re as _re_git
            if not _re_git.match(r'^[a-zA-Z0-9~^._\-/]{1,80}$', _ref):
                self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                try: self.wfile.write(b"Invalid ref.")
                except BrokenPipeError: pass
                return
            try:
                _diff = _sp.run(
                    ["git", "show", _ref, "--stat", "--unified=4",
                     "--no-color", "--format=commit %H%nauthor %an%ndate %ad%n%n%s%n"],
                    capture_output=True, text=True, timeout=15
                )
                _raw = _diff.stdout.strip()
                # Cap to ~400 lines so it doesn't overflow context
                _lines = _raw.splitlines()
                if len(_lines) > 400:
                    _raw = "\n".join(_lines[:400]) + f"\n\n... (truncated at 400 lines)"
                _result = f"=== GIT DIFF: {_ref} ===\n\n" + (_raw or "(empty diff)")
            except Exception as _e:
                _result = f"git show failed: {_e}"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try: self.wfile.write(_result.encode("utf-8", errors="replace"))
            except BrokenPipeError: pass
            return

        elif path == "/memory-book":      body = render_memory_book_page()
        elif path == "/liturgical":      body = render_liturgical_page()
        elif path == "/prayer":           body = render_liturgical_page()
        elif path == "/liturgical/edit": body = render_liturgical_edit_page(query.get("date",[""])[0])
        elif path == "/settings":        body = render_settings_page(status_message=query.get("msg",[""])[0])
        elif path == "/history":         body = render_history_page(status_message=query.get("msg",[""])[0])
        elif path == "/history/preview":
            key = (query.get("key",[""])[0] or query.get("file",[""])[0]).strip()
            data_obj = load_snapshot_data(key) if key else None
            import json as _json
            from html import escape as _esc
            if data_obj is None:
                body_html = f"<p class='muted'>Snapshot not found: {_esc(key)}</p>"
            else:
                pretty = _json.dumps(data_obj, indent=2, ensure_ascii=False)
                body_html = f"<h2>Snapshot Preview</h2><p class='small'>{_esc(key)}</p><pre style='white-space:pre-wrap;'>{_esc(pretty)}</pre><p><a href='/history'>← Back to History</a></p>"
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(f"<html><body style='font-family:system-ui;padding:20px;'>{body_html}</body></html>".encode())
            except BrokenPipeError: pass
            return
        elif path == "/plan-fragment":
            iso  = clean_text(query.get("iso",[""])[0]) or date.today().isoformat()
            frag = render_plan_fragment_html(iso)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(frag.encode())
            except BrokenPipeError: pass
            return

        elif path == "/grid-print":
            iso  = clean_text(query.get("iso",[""])[0]) or date.today().isoformat()
            html = render_grid_print_page(iso)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/mom-step":
            step_id = clean_text(query.get("step",["morning"])[0])
            iso_q   = clean_text(query.get("iso",[""])[0]) or date.today().isoformat()
            from render_misc import render_mom_step_fragment
            html = render_mom_step_fragment(step_id, iso_q)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/meals":
            # Accept ?date=YYYY-MM-DD (exact start) or ?week=YYYY-WNN (legacy)
            wk = clean_text(query.get("date",[""])[0])
            if not wk:
                old_wk = clean_text(query.get("week",[""])[0])
                if old_wk:
                    # Convert legacy week-number key to its Monday ISO date
                    try:
                        from datetime import datetime as _dtp
                        _mon = _dtp.strptime(old_wk + "-1", "%Y-W%W-%w").date()
                        wk = _mon.isoformat()
                    except Exception:
                        wk = old_wk  # pass through as-is
            body = render_meal_planner_page(week_key=wk or None)
        elif path == "/meal-print":
            wk   = clean_text(query.get("week",[""])[0])
            html = render_meal_print_page(week_key=wk or None)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/recipes":
            from render_meals import render_recipes_page
            body = render_recipes_page()
        elif path == "/api-key":
            settings = load_app_settings()
            key = settings.get("anthropic_api_key","")
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.end_headers()
            import json as _json
            try: self.wfile.write(_json.dumps({"key": key}).encode())
            except BrokenPipeError: pass
            return
        elif path.startswith("/schedule/"):
            child = path[len("/schedule/"):]
            # URL-decode and match against CHILDREN (case-insensitive)
            child = child.replace("%20"," ").replace("+"," ").split("?")[0]
            matched = next((c for c in CHILDREN if c.lower() == child.lower() or c.replace(" ","_") == child), None)
            if not matched:
                self.send_response(404); self.end_headers(); return
            body = render_child_schedule(matched, query.get("date",[""])[0])
        elif path == "/calendar/refresh":
            refresh_calendar(force=True)
            self.send_response(303); self.send_header("Location","/calendar"); self.end_headers(); return
        elif path.startswith("/lucy-child-brief/"):
            import json as _json
            child_slug = path[len("/lucy-child-brief/"):].strip().lower()

            # ── helper: current Eastern HH:MM and upcoming-event filter ──────
            def _current_hhmm_eastern():
                try:
                    import pytz as _pytz
                    from datetime import datetime as _dtnow
                    _tz = _pytz.timezone("America/New_York")
                    _n = _dtnow.now(_tz)
                    return _n.strftime("%H:%M"), _n.strftime("%-I:%M %p")
                except Exception:
                    from datetime import datetime as _dtnow
                    _n = _dtnow.now()
                    return _n.strftime("%H:%M"), _n.strftime("%-I:%M %p")

            def _upcoming_events(cal_items, current_hhmm):
                """Return calendar events that haven't ended yet."""
                out = []
                for ev in cal_items:
                    if ev.get("all_day"):
                        out.append(ev)
                        continue
                    t = ev.get("end_time") or ev.get("time")
                    if t and t >= current_hhmm:
                        out.append(ev)
                    elif not t:
                        out.append(ev)
                return out

            def _fmt_ev(ev):
                from daily_schedule_engine import fmt_time_12h
                t = fmt_time_12h(ev.get("time")) if ev.get("time") else ""
                title = ev.get("title", "")
                return f"📅 {t} {title}".strip() if t else f"📅 {title}"

            # Support Lauren's schedule page
            if child_slug == "lauren":
                try:
                    from render_lucy import get_mom_lucy_brief
                    from daily_schedule_engine import build_schedule_payload, generate_day_packet
                    from datetime import date as _date2
                    _today = _date2.today()
                    _pkt = generate_day_packet(_today.isoformat())
                    _payload = build_schedule_payload("Mom", _pkt["weekday"], _pkt["date_label"], _pkt["iso"])
                    _cur_hhmm, _cur_label = _current_hhmm_eastern()
                    _tasks = [i.get("text","") for i in (_payload.get("manual_task_items",[]) + _payload.get("chore_items",[]))]
                    _upcoming = _upcoming_events(_payload.get("calendar_items", []), _cur_hhmm)
                    if _upcoming:
                        _tasks += [_fmt_ev(e) for e in _upcoming]
                    if _tasks:
                        _tasks.insert(0, f"[Current time: {_cur_label} — focus on what's still ahead today]")
                    import re as _re
                    _brief = get_mom_lucy_brief(_tasks)
                    _text = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', _brief.strip())
                    _html = _text.replace("\n\n","</p><p>").replace("\n"," ")
                    _html = f"<p>{_html}</p>" if _html else ""
                except Exception:
                    _html = ""
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Cache-Control","no-store")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"html":_html}).encode())
                except BrokenPipeError: pass
                return
            matched_child = next((c for c in CHILDREN if c.lower() == child_slug), None)
            if not matched_child:
                self.send_response(404); self.end_headers(); return
            try:
                from render_lucy import get_child_lucy_brief
                from render_child_goals import load_child_goals
                from daily_schedule_engine import build_schedule_payload, generate_day_packet
                from datetime import date as _date2
                _today = _date2.today()
                _pkt = generate_day_packet(_today.isoformat())
                _payload = build_schedule_payload(matched_child, _pkt["weekday"], _pkt["date_label"], _pkt["iso"])
                _cur_hhmm, _cur_label = _current_hhmm_eastern()
                _tasks = []
                for _item in (_payload.get("manual_task_items", []) + _payload.get("chore_items", [])):
                    _tasks.append(_item.get("label", _item.get("text", "")))
                for _blk in _payload.get("school_blocks", []):
                    for _si in _blk.get("items", []):
                        _tasks.append(_si.get("label", _si.get("text", "")))
                _upcoming = _upcoming_events(_payload.get("calendar_items", []), _cur_hhmm)
                if _upcoming:
                    _tasks += [_fmt_ev(e) for e in _upcoming]
                if _tasks:
                    _tasks.insert(0, f"[Current time: {_cur_label} — focus on what's still ahead today]")
                _goals = [g for g in load_child_goals(matched_child) if not g.get("archived")]
                _brief = get_child_lucy_brief(matched_child, _tasks, _goals)
                import re as _re2
                _text = _brief.strip()
                _text = _re2.sub(r'^#{1,3}\s+.*\n?', '', _text, flags=_re2.MULTILINE).strip()
                _text = _re2.sub(r'^\*{0,2}[Ff]or [Mm]om:?\*{0,2}\s*', '', _text).strip()
                _text = _re2.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', _text)
                _html = _text.replace("\n\n", "</p><p>").replace("\n", " ")
                _html = f"<p>{_html}</p>" if _html else ""
            except Exception as _e:
                _html = ""
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try: self.wfile.write(_json.dumps({"html": _html}).encode())
            except BrokenPipeError: pass
            return
        elif path.startswith("/lucy-prayer-brief/"):
            import json as _pjson2
            _person_slug = path[len("/lucy-prayer-brief/"):].strip().lower()
            _PRAYER_PEOPLE = {"lauren", "john", "jp", "joseph", "michael", "james", "friends"}
            if _person_slug not in _PRAYER_PEOPLE:
                self.send_response(404); self.end_headers(); return
            try:
                from render_lucy import get_prayer_lucy_brief
                from render_prayer import load_intentions
                _p_intentions = []
                if _person_slug == "friends":
                    _all_int = load_intentions()
                    _p_intentions = [i for i in _all_int if i.get("active", True) and not i.get("answered")]
                _p_brief = get_prayer_lucy_brief(_person_slug, _p_intentions)
                import re as _pre
                _p_text = _p_brief.strip()
                _p_text = _pre.sub(r'^#{1,3}\s+.*\n?', '', _p_text, flags=_pre.MULTILINE).strip()
                _p_text = _pre.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', _p_text)
                _p_html = _p_text.replace("\n\n", "</p><p>").replace("\n", " ")
                _p_html = f"<p>{_p_html}</p>" if _p_html else ""
            except Exception:
                _p_html = ""
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try: self.wfile.write(_pjson2.dumps({"html": _p_html}).encode())
            except BrokenPipeError: pass
            return
        else:
            self.send_response(404); self.end_headers(); return

        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma","no-cache")
        self.end_headers()
        try:
            self.wfile.write(body.encode())
        except BrokenPipeError:
            pass

    def _send_html(self, body: str):
        """Helper for POST handlers that return HTML directly."""
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.end_headers()
        try:
            self.wfile.write(body.encode())
        except BrokenPipeError:
            pass

    def _send_json(self, data: dict, status: int = 200):
        """Helper to send a JSON response."""
        import json as _sj
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(_sj.dumps(data).encode())
        except BrokenPipeError:
            pass

    def do_POST(self):
        path     = urlparse(self.path).path
        redirect = "/"

        # ── Family Quest POST — served on same port via bridge ────────────────
        if path.startswith("/quest"):
            import sys as _fqsys, os as _fqos
            _fqdir = _fqos.path.join(_fqos.path.dirname(_fqos.path.abspath(__file__)), "family_quest")
            if _fqdir not in _fqsys.path:
                _fqsys.path.insert(0, _fqdir)
            from fq_bridge import handle_post as _fq_handle_post
            _fq_handle_post(self); return

        # ── Login POST (public) ───────────────────────────────────────────────
        if path == "/login":
            from render_login import render_login_page
            cl   = int(self.headers.get("Content-Length", 0))
            raw  = self.rfile.read(cl).decode("utf-8", errors="ignore")
            form = dict(pair.split("=", 1) for pair in raw.split("&") if "=" in pair)
            from urllib.parse import unquote_plus
            uid  = unquote_plus(form.get("user", "")).lower().strip()
            pin  = unquote_plus(form.get("pin",  "")).strip()
            nxt  = unquote_plus(form.get("next", "/")).strip() or "/"

            if _auth.check_pin(uid, pin):
                token = _auth.create_session(uid)
                # Where to land after login
                if _auth.is_admin(uid):
                    safe = nxt and not nxt.startswith("/login") and nxt != ""
                    dest = nxt if safe else "/"
                else:
                    dest = f"/schedule/{uid}"
                self.send_response(303)
                self._set_session_cookie(token)
                self.send_header("Location", dest)
                self.end_headers()
            else:
                pg = render_login_page(
                    error="Wrong PIN — try again.",
                    redirect_to=nxt,
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                try: self.wfile.write(pg.encode())
                except BrokenPipeError: pass
            return

        # ── Message Mom (children allowed) ───────────────────────────────────
        if path == "/message-mom":
            user = self._get_viewer()
            _auth.set_viewer(user)
            if not user:
                self._redirect("/login"); return
            cl  = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(cl).decode("utf-8", errors="ignore")
            frm = dict(pair.split("=", 1) for pair in raw.split("&") if "=" in pair)
            from urllib.parse import unquote_plus as _uqp
            txt = _uqp(frm.get("text", "")).strip()
            if txt:
                _auth.save_message(user, txt)
            self._redirect(f"/schedule/{user}" if not _auth.is_admin(user) else "/")
            return

        # ── Change PIN (child self-service) ──────────────────────────────────
        if path == "/change-pin":
            user = self._get_viewer()
            _auth.set_viewer(user)
            if not user:
                self._redirect("/login"); return
            if _auth.is_admin(user):
                self._redirect("/settings#group-app"); return
            cl  = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(cl).decode("utf-8", errors="ignore")
            from urllib.parse import parse_qs as _pqs2, unquote_plus as _uqp3
            prm = _pqs2(raw)
            cur = _uqp3(prm.get("current_pin", [""])[0]).strip()
            new1 = _uqp3(prm.get("new_pin",     [""])[0]).strip()
            new2 = _uqp3(prm.get("confirm_pin", [""])[0]).strip()
            if not _auth.check_pin(user, cur):
                self._redirect("/change-pin?error=Wrong+current+PIN"); return
            if len(new1) != 4 or not new1.isdigit():
                self._redirect("/change-pin?error=PIN+must+be+4+digits"); return
            if new1 != new2:
                self._redirect("/change-pin?error=PINs+don%27t+match"); return
            _auth.save_pins({user: new1})
            self._redirect("/change-pin?ok=1")
            return

        # ── Mark messages read ────────────────────────────────────────────────
        if path == "/messages-read":
            user = self._get_viewer()
            if user and _auth.is_admin(user):
                _auth.mark_messages_read()
            self._redirect("/")
            return

        # ── Save PINs (admin only, returns JSON for AJAX caller) ─────────────
        if path == "/save-pins":
            import json as _json
            user = self._get_viewer()
            _auth.set_viewer(user)
            if not (user and _auth.is_admin(user)):
                out = _json.dumps({"ok": False, "error": "Not authorized"}).encode()
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return
            cl  = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(cl).decode("utf-8", errors="ignore")
            from urllib.parse import parse_qs as _pqs, unquote_plus as _uqp2
            params = _pqs(raw)
            new_pins = {}
            for uid in ("lauren", "john", "jp", "joseph", "michael", "james"):
                val = _uqp2(params.get(f"pin_{uid}", [""])[0]).strip()
                if val and len(val) == 4 and val.isdigit():
                    new_pins[uid] = val
            if new_pins:
                _auth.save_pins(new_pins)
            out = _json.dumps({"ok": True, "saved": list(new_pins.keys())}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try: self.wfile.write(out)
            except BrokenPipeError: pass
            return

        # ── Auth gate for all other POST routes ───────────────────────────────
        _post_user = self._require_post_auth(path)
        if _post_user is None:
            return

        if path == "/plan-import-save-session":
            import json as _phj
            _phv = self._get_viewer() or ""
            if not _auth.is_admin(_phv):
                self.send_response(403); self.end_headers(); return
            try:
                length = int(self.headers.get("Content-Length","0"))
                raw = self.rfile.read(length).decode("utf-8", errors="replace")
                payload = _phj.loads(raw) if raw.strip() else {}
            except Exception:
                payload = {}
            res = _plan_history.append_entry(
                payload.get("plan_text","") or "",
                payload.get("analysis"),
                viewer=_phv,
                source=str(payload.get("source") or "recovered"),
            )
            self.send_response(200 if res.get("ok") else 400)
            self.send_header("Content-Type","application/json")
            self.end_headers()
            try: self.wfile.write(_phj.dumps(res).encode())
            except BrokenPipeError: pass
            return

        if path == "/plan-import-history-delete":
            _phv = self._get_viewer() or ""
            if not _auth.is_admin(_phv):
                self.send_response(403); self.end_headers(); return
            form = parse_urlencoded_body(self)
            entry_id = (form.get("id",[""])[0] or "").strip()
            _plan_history.delete_entry(entry_id)
            self.send_response(303)
            self.send_header("Location", "/plan-import-history")
            self.end_headers(); return

        if path in ("/subject-upload-image", "/subject-doc-upload"):
            from urllib.parse import quote as _url_q
            form = parse_multipart_form(self)
            child = (form.getfirst("child","") or "").strip()
            subject = (form.getfirst("subject","") or "").strip()
            viewer = self._get_viewer() or ""
            if not (_auth.is_admin(viewer) or viewer.lower() == child.lower()):
                self.send_response(403); self.end_headers(); return
            uploaded = form["file"] if "file" in form else None
            file_bytes = b""; original_name = ""; mime = ""
            if uploaded is not None and getattr(uploaded, "filename", ""):
                file_bytes = uploaded.file.read()
                original_name = uploaded.filename
                mime = (uploaded.type or "").strip()

            if path == "/subject-upload-image":
                week = form.getfirst("week","")
                kind = (form.getfirst("kind","test") or "test").strip()
                lesson = (form.getfirst("lesson","") or "").strip()
                do_ai = bool(form.getfirst("ai_grade",""))
                try:
                    wk = int(week) if str(week).strip() else None
                except Exception:
                    wk = None
                result = add_image_entry(child, subject, wk, kind, lesson,
                                          file_bytes, mime, original_name, do_ai=do_ai)
                self.send_response(303)
                self.send_header("Location",
                    f"/subject?child={_url_q(child)}&subject={_url_q(subject)}")
                self.end_headers(); return
            else:
                label = (form.getfirst("label","") or "").strip()
                add_document(child, subject, label, file_bytes, original_name)
                self.send_response(303)
                self.send_header("Location",
                    f"/subject?child={_url_q(child)}&subject={_url_q(subject)}")
                self.end_headers(); return

        if path in ("/subject-grade-add", "/subject-grade-delete",
                    "/subject-link-add", "/subject-link-delete",
                    "/subject-doc-delete"):
            from urllib.parse import quote as _url_q
            form = parse_urlencoded_body(self)
            def _f(key, default=""):
                vals = form.get(key) or [default]
                return vals[0] if vals else default
            child = _f("child").strip()
            subject = _f("subject").strip()
            viewer = self._get_viewer() or ""
            child_owner = viewer.lower() == child.lower()
            is_adm = _auth.is_admin(viewer)
            # Only admins can delete or manually grade
            if path in ("/subject-grade-delete","/subject-link-delete",
                        "/subject-doc-delete","/subject-grade-add") and not is_adm:
                self.send_response(403); self.end_headers(); return
            if path == "/subject-link-add" and not (is_adm or child_owner):
                self.send_response(403); self.end_headers(); return

            if path == "/subject-grade-add":
                add_manual_entry(child, subject, _f("week"), _f("kind","assignment"),
                                  _f("lesson"), _f("grade","0"), _f("feedback"))
            elif path == "/subject-grade-delete":
                delete_entry(child, subject, _f("id"))
            elif path == "/subject-link-add":
                add_link(child, subject, _f("label"), _f("url"))
            elif path == "/subject-link-delete":
                try: idx = int(_f("idx","-1"))
                except: idx = -1
                delete_link(child, subject, idx)
            elif path == "/subject-doc-delete":
                delete_document(child, subject, _f("path"))
            self.send_response(303)
            self.send_header("Location",
                f"/subject?child={_url_q(child)}&subject={_url_q(subject)}")
            self.end_headers(); return

        if path in ("/school-upload", "/prayer-intention-add", "/recipe-import",
                    "/recipe-save",
                    "/assignment-analyze", "/assignment-update", "/assignment-delete",
                    "/gradebook-add", "/gradebook-update", "/gradebook-delete"):
            form = parse_multipart_form(self)

            if path == "/assignment-analyze":
                # AI-analyze an uploaded assignment (image, PDF, or pasted text)
                # and stash the structured result for later curriculum placement.
                import os as _os, json as _aj, base64 as _ab64, uuid as _auuid
                import urllib.request as _aur
                from data_helpers import (
                    add_assignment_analysis, ASSIGNMENT_UPLOADS_DIR
                )
                _os.makedirs(ASSIGNMENT_UPLOADS_DIR, exist_ok=True)

                raw_text     = clean_text(form.getfirst("raw_text",""))
                child_hint   = clean_text(form.getfirst("child_hint",""))
                subject_hint = clean_text(form.getfirst("subject_hint",""))
                description  = clean_text(form.getfirst("description",""))

                # Collect ALL uploaded files (FieldStorage gives a list when there
                # are multiple items with the same name, single object otherwise).
                _raw_uploaded = form["file"] if "file" in form else None
                if _raw_uploaded is None:
                    _file_list = []
                elif isinstance(_raw_uploaded, list):
                    _file_list = _raw_uploaded
                else:
                    _file_list = [_raw_uploaded]

                _MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB per file
                _MAX_TOTAL_BYTES  = 40 * 1024 * 1024  # 40 MB combined safety cap

                # files = list of {bytes, name, mime, ext_lc, kind}
                files = []
                _total = 0
                for _u in _file_list:
                    _fn = getattr(_u, "filename", "") or ""
                    if not _fn: continue
                    try:    _b = _u.file.read(_MAX_UPLOAD_BYTES + 1) if _u.file else b""
                    except Exception: _b = b""
                    if not _b: continue
                    if len(_b) > _MAX_UPLOAD_BYTES:
                        self.send_response(413); self.send_header("Content-Type","application/json"); self.end_headers()
                        try: self.wfile.write((f'{{"error":"\\"{_fn}\\" is over 15 MB. Try a smaller photo or PDF."}}').encode())
                        except BrokenPipeError: pass
                        return
                    _total += len(_b)
                    if _total > _MAX_TOTAL_BYTES:
                        self.send_response(413); self.send_header("Content-Type","application/json"); self.end_headers()
                        try: self.wfile.write(b'{"error":"Combined uploads are over 40 MB. Please pick fewer or smaller files."}')
                        except BrokenPipeError: pass
                        return
                    _mime = (getattr(_u, "type", "") or "").strip()
                    _ext_lc = ("." + _fn.rsplit(".",1)[-1].lower()) if "." in _fn else ""
                    _is_pdf = (_b[:4] == b"%PDF") or _ext_lc == ".pdf" or "pdf" in _mime.lower()
                    _is_img = ((_mime.startswith("image/") if _mime else False)
                               or _ext_lc in (".jpg",".jpeg",".png",".webp",".heic",".gif"))
                    _kind = "pdf" if _is_pdf else ("image" if _is_img else "other")
                    files.append({"bytes": _b, "name": _fn, "mime": _mime,
                                  "ext_lc": _ext_lc, "kind": _kind})

                if not files and not raw_text.strip():
                    self.send_response(400); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"error":"Please choose a file or paste text."}')
                    except BrokenPipeError: pass
                    return

                # Persist each file + extract PDF text. Build per-file metadata
                # for storage and a content-array for the AI request.
                _save_warning_parts = []
                upload_paths = []   # list of {path, kind, mime, filename}
                pdf_text_chunks = []
                image_payload_blocks = []  # for Anthropic content array
                for _f in files:
                    _kind = _f["kind"]
                    _b    = _f["bytes"]
                    _ext  = _f["ext_lc"]
                    _path = ""
                    _mime = _f["mime"]

                    if _kind == "pdf":
                        _txt = (extract_pdf_text(_b) or "").strip()
                        if _txt:
                            pdf_text_chunks.append(f"--- {_f['name']} ---\n{_txt}")
                        else:
                            _save_warning_parts.append(f"\"{_f['name']}\" had no extractable text (probably a scan)")
                        _mime = "application/pdf"
                        _path = f"{ASSIGNMENT_UPLOADS_DIR}/up-{_auuid.uuid4().hex[:10]}.pdf"
                        try:
                            with open(_path, "wb") as _wf: _wf.write(_b)
                        except Exception:
                            _path = ""
                            _save_warning_parts.append(f"couldn't save \"{_f['name']}\"")
                    elif _kind == "image":
                        _mime = _mime if _mime.startswith("image/") else {
                            ".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",
                            ".webp":"image/webp",".gif":"image/gif",".heic":"image/jpeg",
                        }.get(_ext, "image/jpeg")
                        # Anthropic does not accept HEIC; fall back to JPEG label
                        if _mime == "image/heic": _mime = "image/jpeg"
                        _path = f"{ASSIGNMENT_UPLOADS_DIR}/up-{_auuid.uuid4().hex[:10]}{_ext or '.jpg'}"
                        try:
                            with open(_path, "wb") as _wf: _wf.write(_b)
                        except Exception:
                            _path = ""
                            _save_warning_parts.append(f"couldn't save \"{_f['name']}\"")
                        # Anthropic enforces a 5 MB BASE64 cap per image
                        # (~3.7 MB raw). iPhone photos blow past this, so
                        # downscale before encoding. Original is preserved on disk.
                        _api_bytes, _api_mime = _shrink_image_for_anthropic(_b, _mime)
                        image_payload_blocks.append({
                            "type":"image",
                            "source":{"type":"base64","media_type":_api_mime,
                                      "data": _ab64.b64encode(_api_bytes).decode("ascii")},
                        })
                    else:
                        _save_warning_parts.append(f"\"{_f['name']}\" is an unsupported file type — skipped")
                        continue

                    upload_paths.append({
                        "path":     _path,
                        "kind":     _kind,
                        "mime":     _mime,
                        "filename": _f["name"],
                    })

                # If there were files but none yielded anything analyzable + no text
                _has_pdf_text = bool(pdf_text_chunks)
                _has_images   = bool(image_payload_blocks)
                _has_pasted   = bool(raw_text.strip())
                if not (_has_pdf_text or _has_images or _has_pasted):
                    self.send_response(400); self.send_header("Content-Type","application/json"); self.end_headers()
                    _msg = "No analyzable content. " + ("; ".join(_save_warning_parts) if _save_warning_parts else "Try a clearer photo or paste the text.")
                    try: self.wfile.write(_aj.dumps({"error": _msg}).encode())
                    except BrokenPipeError: pass
                    return

                # Back-compat fields (first file = primary)
                source_kind     = upload_paths[0]["kind"] if upload_paths else "text"
                source_mime     = upload_paths[0]["mime"] if upload_paths else ""
                source_filename = upload_paths[0]["filename"] if upload_paths else ""
                upload_path     = upload_paths[0]["path"] if upload_paths else ""
                extracted_text  = "\n\n".join(pdf_text_chunks) if pdf_text_chunks else raw_text.strip()
                _save_warning   = "; ".join(_save_warning_parts)

                # Build the AI prompt and call Anthropic Claude
                _settings = load_app_settings()
                _api_key = (
                    _settings.get("family_constraints",{}).get("anthropic_api_key","")
                    or _settings.get("anthropic_api_key","")
                ).strip()
                if not _api_key:
                    self.send_response(400); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"error":"No Anthropic API key. Add one in Settings."}')
                    except BrokenPipeError: pass
                    return

                _instructions = (
                    "You are FATHER GREGORY — the academic director and headmaster of the McAdams "
                    "family homeschool. You are a wise, warm scholar in the tradition of Benedictine "
                    "and Jesuit education, formed by the classical Trivium (Grammar, Logic, Rhetoric) "
                    "and Charlotte Mason's living-books philosophy. Lauren is the mom and primary "
                    "teacher. You are reviewing a piece of student work she has uploaded.\n"
                    "\n"
                    "== THE McADAMS BOYS ==\n"
                    "JP — 14, 9th-grade equivalent. Most advanced. Ready for formal logic, "
                    "advanced composition, rhetoric, dialectic-level argument. Hold him to substance, "
                    "structure, citations, and clarity of thesis. Push him.\n"
                    "Joseph — 12, 7th-grade equivalent. Logic stage. Ready for structured argument, "
                    "cause-and-effect, mastery of grammar. Encourage neat work, complete sentences, "
                    "and one clear next step at a time.\n"
                    "Michael — 5, kindergarten / early Grammar stage. Wonder years. Praise effort, "
                    "neat letters, and oral narration. Suggestions must be tiny and concrete "
                    "(\"trace the o all the way around\"). Never overwhelm; one or two gentle nudges.\n"
                    "James — 13 months. Not in school yet. Skip feedback if the work is his.\n"
                    "\n"
                    "== HOW TO REVIEW ==\n"
                    "If the upload contains the student's actual WORK (handwritten answers, an essay, "
                    "a math sheet with solutions, a drawing, a worksheet with their writing on it), "
                    "give Father Gregory's feedback. If it is only the assignment instructions with no "
                    "student work yet, set gregory_feedback to a brief one-sentence note that the work "
                    "hasn't been done yet, and leave strengths/growth_edges empty.\n"
                    "Always tailor depth and vocabulary to the named/guessed child's age. For JP use "
                    "scholarly directness; for Joseph use clear and warm coaching; for Michael use "
                    "tender, celebratory praise plus one tiny next step.\n"
                    "Be specific: cite what you actually see (\"your second paragraph opens with a "
                    "strong topic sentence — 'Greek myths gave us…'\"). Avoid generic praise.\n"
                    "Growth edges should be LEADING — not the answer, but a question or nudge that "
                    "guides the student to discover the improvement themselves.\n"
                    "\n"
                    "Return ONE JSON object — no markdown, no commentary, just raw JSON — with these "
                    "exact keys:\n"
                    '  "title": short descriptive title of the assignment (string)\n'
                    '  "subject": best-guess from: Math, Latin, Greek, Religion, History, Science, '
                    "Reading, Writing, Grammar, Literature, Art, Music, Logic, PE, Other (string)\n"
                    '  "child_guess": JP / Joseph / Michael, or empty string if unclear (string)\n'
                    '  "assignment_type": e.g. worksheet, reading, test, quiz, project, practice, '
                    "essay, copywork, oral recitation, problem set, other (string)\n"
                    '  "estimated_minutes": realistic time-on-task for that child (integer)\n'
                    '  "due_date_hint": any due-date language inferable ("today", "Friday", a date, '
                    "or empty string) (string)\n"
                    '  "instructions_summary": 1-3 sentences in plain English summarizing what the '
                    "child needs to do (string)\n"
                    '  "sub_items": list of individual sub-tasks if multi-part (up to 30 strings); '
                    "empty list otherwise (array of strings)\n"
                    '  "materials_needed": list of supplies; empty list if none obvious (array of strings)\n'
                    '  "notes_for_mom": anything Mom should know — pitfalls, prep needed, context — '
                    "or empty string (string)\n"
                    '  "work_present": true if the upload shows the student has actually done work '
                    "on the assignment; false if it is only the assignment prompt/instructions (boolean)\n"
                    '  "gregory_feedback": Father Gregory speaking in first person to the child by '
                    "name, 2-5 sentences, age-appropriate, warm and specific. Empty string if no work "
                    "is present yet. (string)\n"
                    '  "strengths": 1-4 short bullet phrases naming specific things the child did '
                    "well — must reference what you actually see in the work. Empty list if no work. "
                    "(array of strings)\n"
                    '  "growth_edges": 1-3 short LEADING suggestions for improvement, age-appropriate '
                    "in tone and difficulty. Phrase as a gentle nudge or question, not a correction "
                    "(\"What if you tried…\", \"Could you find one place where…\"). Empty list if no "
                    "work or if the work is essentially perfect for the child's level. "
                    "(array of strings)\n"
                    '  "suggested_grade": Father Gregory\'s suggested letter grade for the work as it '
                    "stands, age-normed for the child (A+, A, A-, B+, B, B-, C+, C, C-, D, F). For "
                    "Michael (5) prefer encouragement marks instead of letters: \"✦ Excellent\", "
                    "\"✓ Good work\", \"↻ Try again\". Empty string if no work is present. (string)\n"
                    '  "grade_rationale": 1-3 sentences in Father Gregory\'s voice explaining WHY he '
                    "gave that grade — what it reflects about completeness, accuracy, effort, and "
                    "craftsmanship for the child's age. No rubric is set up yet, so use sound "
                    "headmaster judgement. Empty string if no work. (string)\n"
                )
                if child_hint:
                    _instructions += f"\nMom hinted this is for: {child_hint}.\n"
                if subject_hint:
                    _instructions += f"Mom hinted the subject is: {subject_hint}.\n"
                if description:
                    _instructions += (
                        "\nMom provided this description of what was assigned — "
                        "use it as authoritative context for what the student was "
                        "asked to do, and judge the work against it:\n"
                        f"\"\"\"\n{description[:4000]}\n\"\"\"\n"
                    )

                if image_payload_blocks:
                    # Vision call — Claude Opus 4.5 (matches the working
                    # recipe-import flow). One assignment may include several
                    # photos (e.g. front + back of a worksheet); send them all.
                    _content_blocks = list(image_payload_blocks)
                    _text_part = _instructions
                    if pdf_text_chunks or raw_text.strip():
                        _text_part += "\n\nADDITIONAL TEXT FROM PDFs / PASTED:\n" + (
                            (extracted_text or raw_text)[:12000]
                        )
                    if len(image_payload_blocks) > 1:
                        _text_part += (
                            f"\n\nNOTE: {len(image_payload_blocks)} images were "
                            "uploaded for ONE assignment — synthesize them together."
                        )
                    _content_blocks.append({"type":"text","text": _text_part})
                    _payload = {
                        "model": "claude-opus-4-5",
                        "max_tokens": 1500,
                        "messages": [{"role":"user","content": _content_blocks}],
                    }
                else:
                    snippet = (extracted_text or raw_text)[:18000]
                    _payload = {
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 1500,
                        "messages": [{
                            "role": "user",
                            "content": _instructions + "\n\nASSIGNMENT TEXT:\n" + snippet,
                        }],
                    }

                parsed = {}
                ai_text = ""
                ai_error = ""
                try:
                    _req = _aur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=_aj.dumps(_payload).encode(),
                        headers={
                            "Content-Type": "application/json",
                            "x-api-key": _api_key,
                            "anthropic-version": "2023-06-01",
                        },
                        method="POST",
                    )
                    with _aur.urlopen(_req, timeout=60) as _r:
                        _resp = _aj.loads(_r.read().decode())
                    ai_text = _resp.get("content",[{}])[0].get("text","").strip()
                    # Strip ```json fences if the model added them
                    _t = ai_text
                    if _t.startswith("```"):
                        _t = _t.strip("`")
                        if _t.lower().startswith("json"):
                            _t = _t[4:].lstrip()
                    try:
                        parsed = _aj.loads(_t)
                    except Exception:
                        # Try to find a JSON object inside the response
                        import re as _are
                        _m = _are.search(r'\{[\s\S]*\}', ai_text)
                        if _m:
                            try: parsed = _aj.loads(_m.group(0))
                            except Exception as _je: ai_error = f"could not parse AI JSON: {_je}"
                        else:
                            ai_error = "AI response was not JSON"
                except _aur.HTTPError as _ahe:
                    # Anthropic returns the real error in the response body —
                    # urllib hides it inside the HTTPError object. Capture it.
                    try:
                        _body = _ahe.read().decode("utf-8", errors="ignore")
                    except Exception:
                        _body = ""
                    ai_error = f"HTTP {_ahe.code}: {_body[:600]}"
                except Exception as _ae:
                    ai_error = str(_ae)[:300]

                if not isinstance(parsed, dict):
                    parsed = {}
                if ai_error:
                    parsed["error"] = ai_error
                    parsed["raw_response"] = ai_text[:2000]
                # Coerce a couple of fields to expected types
                try: parsed["estimated_minutes"] = int(parsed.get("estimated_minutes") or 0) or ""
                except Exception: parsed["estimated_minutes"] = ""
                for _lk in ("sub_items","materials_needed","strengths","growth_edges"):
                    if _lk in parsed and not isinstance(parsed[_lk], list):
                        parsed[_lk] = [str(parsed[_lk])] if parsed[_lk] else []
                if "work_present" in parsed and not isinstance(parsed["work_present"], bool):
                    parsed["work_present"] = str(parsed["work_present"]).strip().lower() in ("true","yes","1")

                _record = {
                    "source_kind":     source_kind,
                    "source_filename": source_filename,
                    "source_mime":     source_mime,
                    "upload_path":     upload_path,        # back-compat: first file
                    "upload_paths":    upload_paths,        # full list (NEW)
                    "raw_text":        extracted_text[:8000],
                    "child_hint":      child_hint,
                    "subject_hint":    subject_hint,
                    "description":     description,
                    "parsed":          parsed,
                }
                _saved = add_assignment_analysis(_record)
                _resp_obj = {"ok": True, "id": _saved["id"], "parsed": parsed}
                if _save_warning:
                    _resp_obj["warning"] = _save_warning
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_aj.dumps(_resp_obj).encode())
                except BrokenPipeError: pass
                return

            elif path == "/assignment-update":
                import json as _aj
                from data_helpers import update_assignment_analysis
                _id    = clean_text(form.getfirst("id",""))
                _edits_raw = form.getfirst("edits","") or "{}"
                try:    _edits = _aj.loads(_edits_raw)
                except Exception: _edits = {}
                if not isinstance(_edits, dict): _edits = {}
                ok = update_assignment_analysis(_id, _edits) if _id else False
                self.send_response(200 if ok else 404)
                self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_aj.dumps({"ok": ok}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/assignment-delete":
                import json as _aj
                from data_helpers import delete_assignment_analysis
                _id = clean_text(form.getfirst("id",""))
                ok = delete_assignment_analysis(_id) if _id else False
                self.send_response(200 if ok else 404)
                self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_aj.dumps({"ok": ok}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/gradebook-add":
                import json as _aj
                from data_helpers import (
                    add_gradebook_entry, percent_to_letter, update_assignment_analysis,
                )
                def _f(name, default=""):
                    v = form.getfirst(name, default)
                    return clean_text(v) if isinstance(v, str) else default
                _entry = {
                    "child":               _f("child"),
                    "subject":             _f("subject") or "Other",
                    "title":               _f("title"),
                    "date":                _f("date"),
                    "raw_score":           _f("raw_score"),
                    "total":               _f("total"),
                    "percentage":          _f("percentage"),
                    "letter":              _f("letter"),
                    "note":                _f("note"),
                    "source_analysis_id":  _f("source_analysis_id"),
                }
                # Auto-compute percentage if score+total provided but pct missing
                try:
                    if _entry["raw_score"] not in ("", None) and _entry["total"] not in ("", None):
                        _r = float(_entry["raw_score"]); _t = float(_entry["total"])
                        if _t > 0 and _entry["percentage"] in ("", None):
                            _entry["percentage"] = round((_r / _t) * 100, 1)
                except Exception: pass
                # Auto-letter from pct if missing
                if not _entry["letter"] and _entry["percentage"] not in ("", None):
                    _entry["letter"] = percent_to_letter(_entry["percentage"])
                # Validate child + title
                if not _entry["child"] or not _entry["title"]:
                    self.send_response(400)
                    self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(_aj.dumps({"ok": False, "error": "child and title required"}).encode())
                    except BrokenPipeError: pass
                    return
                _saved = add_gradebook_entry(_entry)
                # Mark the source analysis as recorded so the card can show it
                if _entry["source_analysis_id"]:
                    update_assignment_analysis(_entry["source_analysis_id"], {
                        "_gradebook_id": _saved["id"],
                        "_gradebook_pct": _entry.get("percentage", ""),
                        "_gradebook_letter": _entry.get("letter", ""),
                    })
                self.send_response(200)
                self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_aj.dumps({"ok": True, "id": _saved["id"], "entry": _saved}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/gradebook-update":
                import json as _aj
                from data_helpers import update_gradebook_entry, percent_to_letter
                _id = clean_text(form.getfirst("id",""))
                _edits_raw = form.getfirst("edits","") or "{}"
                try:    _edits = _aj.loads(_edits_raw)
                except Exception: _edits = {}
                if not isinstance(_edits, dict): _edits = {}
                # If raw_score+total provided, recompute pct + letter
                try:
                    if _edits.get("raw_score") not in (None, "") and _edits.get("total") not in (None, ""):
                        _r = float(_edits["raw_score"]); _t = float(_edits["total"])
                        if _t > 0:
                            _edits["percentage"] = round((_r / _t) * 100, 1)
                            if not _edits.get("letter"):
                                _edits["letter"] = percent_to_letter(_edits["percentage"])
                except Exception: pass
                ok = update_gradebook_entry(_id, _edits) if _id else False
                self.send_response(200 if ok else 404)
                self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_aj.dumps({"ok": ok}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/gradebook-delete":
                import json as _aj
                from data_helpers import delete_gradebook_entry
                _id = clean_text(form.getfirst("id",""))
                ok = delete_gradebook_entry(_id) if _id else False
                self.send_response(200 if ok else 404)
                self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_aj.dumps({"ok": ok}).encode())
                except BrokenPipeError: pass
                return

            if path == "/school-upload":
                import urllib.parse as _up, urllib.request as _ur, re as _re
                child = clean_child(form.getfirst("child",""))
                raw_text = clean_text(form.getfirst("raw_text",""))
                gdrive_url = clean_text(form.getfirst("gdrive_url",""))
                gdrive_file_id = clean_text(form.getfirst("gdrive_file_id",""))
                gdrive_file_mime = clean_text(form.getfirst("gdrive_file_mime",""))
                gdrive_file_name = clean_text(form.getfirst("gdrive_file_name",""))
                filename = "pasted_text"
                uploaded = form["file"] if "file" in form else None
                file_bytes = b""; uploaded_name = ""
                # --- Google Drive authenticated download (via connector) ---
                if not raw_text and gdrive_file_id:
                    try:
                        file_bytes = _gdrive.download_file(gdrive_file_id, gdrive_file_mime)
                        uploaded_name = gdrive_file_name or "gdrive_file.pdf"
                        filename = uploaded_name
                    except Exception as _ge:
                        uploaded_name = "_gdrive_error:" + str(_ge)[:120]
                # --- Google Drive URL fetch (public link fallback) ---
                elif not raw_text and gdrive_url and "drive.google.com" in gdrive_url:
                    try:
                        m = _re.search(r'/d/([a-zA-Z0-9_-]+)', gdrive_url) or \
                            _re.search(r'[?&]id=([a-zA-Z0-9_-]+)', gdrive_url)
                        if m:
                            fid = m.group(1)
                            dl_url = f"https://drive.google.com/uc?export=download&id={fid}"
                            req = _ur.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
                            with _ur.urlopen(req, timeout=20) as resp:
                                ct = resp.headers.get("Content-Type","")
                                body = resp.read(8*1024*1024)
                            # Handle virus-scan confirmation page
                            if b"virus scan warning" in body.lower() or b"confirm" in body[:2000].lower():
                                conf = _re.search(rb'confirm=([a-zA-Z0-9_-]+)', body)
                                if conf:
                                    dl_url2 = dl_url + "&confirm=" + conf.group(1).decode()
                                    req2 = _ur.Request(dl_url2, headers={"User-Agent":"Mozilla/5.0"})
                                    with _ur.urlopen(req2, timeout=20) as resp2:
                                        body = resp2.read(8*1024*1024)
                            if body[:4] == b'%PDF' or b'%PDF' in body[:20]:
                                file_bytes = body
                                uploaded_name = "google_drive.pdf"
                                filename = "google_drive.pdf"
                            else:
                                raw_text = body.decode("utf-8", errors="ignore")
                                filename = "google_drive_text"
                        else:
                            raw_text = ""; file_bytes = b""
                    except Exception as _e:
                        raw_text = ""
                        file_bytes = b""
                        uploaded_name = "_gdrive_error:" + str(_e)[:120]
                # --- Local file upload ---
                if not file_bytes and not raw_text:
                    if uploaded is not None and getattr(uploaded,"filename",""):
                        uploaded_name = uploaded.filename
                        file_bytes = uploaded.file.read() if uploaded.file else b""
                    if uploaded_name and not uploaded_name.startswith("_"): filename = uploaded_name
                upload_msg = ""
                if not raw_text and file_bytes:
                    if filename.lower().endswith(".pdf") or file_bytes[:4] == b'%PDF':
                        raw_text = extract_pdf_text(file_bytes)
                        if not raw_text:
                            upload_msg = "error:PDF was received but no text could be extracted — it may be image-based/scanned. Try opening the PDF in Google Drive on your phone, copying all the text, and pasting it in the text box below."
                    else:
                        try:    raw_text = file_bytes.decode("utf-8")
                        except: raw_text = file_bytes.decode("latin-1", errors="ignore")
                if not child:
                    upload_msg = "error:Please select a child before uploading."
                elif uploaded_name.startswith("_gdrive_error:"):
                    upload_msg = "error:Could not fetch from Google Drive — make sure the link is set to 'Anyone with the link can view'. Error: " + uploaded_name[14:]
                elif not gdrive_url and not raw_text and not file_bytes:
                    upload_msg = "error:No file or text received. Paste a Google Drive link or the school list text directly."
                elif not raw_text:
                    upload_msg = upload_msg or "error:Could not read text from the file."
                else:
                    save_school_preview(child, filename, raw_text, parse_school_pdf_text(raw_text, child))
                    upload_msg = "ok:School list imported and preview created for " + child + "!"
                redirect = "/school?msg=" + _up.quote(upload_msg) + "#top"

            elif path == "/prayer-intention-add":
                import json as _pj
                title_in = clean_text(form.getfirst("title", ""))
                desc_in  = clean_text(form.getfirst("description", ""))
                photo_bytes = None
                photo_ext   = "jpg"
                photo_error = ""
                try:
                    photo_field = form["photo"] if "photo" in form else None
                    if photo_field:
                        fname = getattr(photo_field, "filename", "") or ""
                        if fname:
                            photo_ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "jpg"
                            raw_bytes = photo_field.file.read() if photo_field.file else b""
                            if raw_bytes and len(raw_bytes) > 100:
                                photo_bytes = raw_bytes
                            elif raw_bytes:
                                photo_error = f"Photo too small ({len(raw_bytes)} bytes) — skipped"
                except Exception as _pe:
                    photo_error = str(_pe)
                    print(f"[PRAYER] Photo error: {_pe}")
                if title_in:
                    from render_prayer import add_intention
                    add_intention(title_in, desc_in, photo_bytes, photo_ext)
                    out = _pj.dumps({"ok": True, "photo_error": photo_error}).encode()
                else:
                    out = _pj.dumps({"ok": False, "error": "Title required"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path in ("/recipe-import", "/recipe-save"):
                import json as _rj, base64 as _b64, re as _rre, os as _ros, uuid as _ruuid
                # Common helper: read an uploaded image field (dish_photo or recipe_photo)
                # and write it to data/uploads/recipes/. Returns ("/uploads/recipes/<file>", bytes, mime, name).
                def _read_upload(field_name):
                    try:
                        pf = form[field_name] if field_name in form else None
                        if not pf or not getattr(pf, "filename", ""):
                            return None, b"", "", ""
                        raw = pf.file.read() if pf.file else b""
                        if len(raw) <= 500:
                            return None, b"", "", ""
                        return None, raw, (getattr(pf, "type", "") or "").lower(), (pf.filename or "").lower()
                    except Exception:
                        return None, b"", "", ""
                def _save_dish_photo(raw, name_hint):
                    if not raw: return ""
                    ext = ""
                    nl = (name_hint or "").lower()
                    for e in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"):
                        if nl.endswith(e): ext = e; break
                    if not ext: ext = ".jpg"
                    _ros.makedirs("data/uploads/recipes", exist_ok=True)
                    fname = f"dish-{_ruuid.uuid4().hex[:10]}{ext}"
                    fpath = f"data/uploads/recipes/{fname}"
                    with open(fpath, "wb") as fh:
                        fh.write(raw)
                    return f"/uploads/recipes/{fname}"

            if path == "/recipe-save":
                # Manual create OR inline edit (now multipart so dish_photo can be uploaded)
                rid_edit = clean_text(form.getfirst("id", ""))
                name     = clean_text(form.getfirst("name", ""))
                ingr     = clean_text(form.getfirst("ingredients", ""))
                instr    = clean_text(form.getfirst("instructions", ""))
                tags_raw = clean_text(form.getfirst("tags", ""))
                tags     = [t.strip() for t in tags_raw.split(",") if t.strip()]
                prep     = clean_text(form.getfirst("prep_time", ""))
                remove_image  = clean_text(form.getfirst("remove_image", "")) == "1"
                hidden_image  = clean_text(form.getfirst("image_url", ""))  # from import-preview flow
                _, dish_raw, _dm, _dn = _read_upload("dish_photo")
                new_image_url = _save_dish_photo(dish_raw, _dn) if dish_raw else ""
                # Effective image: newly uploaded > hidden carry-over > none
                effective_image = new_image_url or hidden_image
                if name:
                    if rid_edit:
                        recipes = load_recipes()
                        for r in recipes:
                            if isinstance(r, dict) and r.get("id") == rid_edit:
                                r["name"] = name; r["ingredients"] = ingr
                                r["instructions"] = instr; r["tags"] = tags
                                r["prep_time"] = prep
                                if new_image_url:
                                    r["image"] = new_image_url
                                elif remove_image:
                                    r["image"] = ""
                        from render_meals import save_recipes
                        save_recipes(recipes)
                    else:
                        save_recipe(name, ingr, instr, tags, prep, image=effective_image)
                self.send_response(302)
                self.send_header("Location", "/recipes?msg=Recipe+saved")
                self.end_headers(); return

            if path == "/recipe-import":
                name_in    = clean_text(form.getfirst("name", ""))
                url_in     = clean_text(form.getfirst("url", ""))
                text_in    = clean_text(form.getfirst("text", ""))
                _, photo_bytes_tmp, photo_mime, photo_name = _read_upload("recipe_photo")
                photo_bytes = photo_bytes_tmp if photo_bytes_tmp else None
                # Optional separate "dish photo" for the card
                _, dish_raw, _dpm, _dpn = _read_upload("dish_photo")
                dish_image_url = _save_dish_photo(dish_raw, _dpn) if dish_raw else ""
                # ── If upload is a PDF, extract text and treat as text_in ────
                _is_pdf = ("pdf" in photo_mime) or photo_name.endswith(".pdf") or (
                    photo_bytes and photo_bytes[:4] == b"%PDF")
                _pdf_no_text = False  # flag: PDF was uploaded but yielded no extractable text
                if photo_bytes and _is_pdf:
                    try:
                        import io as _io2, PyPDF2 as _ppdf
                        reader = _ppdf.PdfReader(_io2.BytesIO(photo_bytes))
                        _pdf_text = []
                        for _pg in reader.pages[:10]:
                            try: _pdf_text.append(_pg.extract_text() or "")
                            except Exception: pass
                        _joined = "\n".join(t for t in _pdf_text if t.strip())
                        if _joined.strip():
                            text_in = (text_in + "\n\n" + _joined).strip() if text_in else _joined
                            photo_bytes = None  # don't ALSO send to vision
                        else:
                            # No extractable text (likely a scanned/image PDF). Mark so we
                            # can surface a useful note and skip the unreadable bytes.
                            _pdf_no_text = True
                            photo_bytes = None
                            print(f"[recipe-import] PDF {photo_name} had no extractable text "
                                  f"(likely scanned image); falling back.")
                    except Exception as _pdf_err:
                        _pdf_no_text = True
                        photo_bytes = None
                        print(f"[recipe-import] PDF parse error for {photo_name}: {_pdf_err}")
                # ── Fetch URL if provided and no text/photo ──────────────────
                if url_in and not text_in and not photo_bytes:
                    try:
                        import urllib.request as _ur2
                        req_url = _ur2.Request(url_in, headers={
                            "User-Agent": "Mozilla/5.0 (compatible; SanctaFamiliaBot/1.0)",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        })
                        with _ur2.urlopen(req_url, timeout=15) as _resp:
                            raw_html = _resp.read().decode("utf-8", errors="ignore")
                        # 1) Look for JSON-LD <script type="application/ld+json"> with @type "Recipe"
                        _ld_blocks = _rre.findall(
                            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
                            raw_html, _rre.IGNORECASE)
                        _recipe_obj = None
                        def _walk_for_recipe(node):
                            if isinstance(node, dict):
                                t = node.get("@type")
                                if (isinstance(t, str) and t == "Recipe") or (
                                    isinstance(t, list) and "Recipe" in t):
                                    return node
                                for v in node.values():
                                    found = _walk_for_recipe(v)
                                    if found: return found
                            elif isinstance(node, list):
                                for v in node:
                                    found = _walk_for_recipe(v)
                                    if found: return found
                            return None
                        for _b in _ld_blocks:
                            try: _data = _rj.loads(_b.strip())
                            except Exception:
                                # Some sites embed multiple comma-separated objects
                                try: _data = _rj.loads("[" + _b.strip().rstrip(",") + "]")
                                except Exception: continue
                            _recipe_obj = _walk_for_recipe(_data)
                            if _recipe_obj: break
                        if _recipe_obj:
                            # Direct extraction — no LLM needed for the basics
                            def _flatten(v):
                                if isinstance(v, list):
                                    return "\n".join(_flatten(x) for x in v)
                                if isinstance(v, dict):
                                    return v.get("text") or v.get("name") or ""
                                return str(v) if v else ""
                            _ldn   = _recipe_obj.get("name") or ""
                            _ldi   = _flatten(_recipe_obj.get("recipeIngredient") or
                                              _recipe_obj.get("ingredients") or [])
                            _ldins = _flatten(_recipe_obj.get("recipeInstructions") or [])
                            _ldp   = (_recipe_obj.get("totalTime") or
                                      _recipe_obj.get("cookTime") or
                                      _recipe_obj.get("prepTime") or "")
                            # ISO 8601 duration → human (e.g. PT45M → "45 min")
                            _dm = _rre.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", str(_ldp))
                            if _dm:
                                _h, _m = _dm.group(1), _dm.group(2)
                                _parts = []
                                if _h: _parts.append(f"{_h} hr")
                                if _m: _parts.append(f"{_m} min")
                                _ldp = " ".join(_parts) if _parts else ""
                            _kw = _recipe_obj.get("keywords") or _recipe_obj.get("recipeCategory") or ""
                            if isinstance(_kw, list): _kw = ", ".join(str(k) for k in _kw)
                            text_in = (
                                f"Recipe: {_ldn}\n\n"
                                f"Ingredients:\n{_ldi}\n\n"
                                f"Instructions:\n{_ldins}\n\n"
                                f"Total time: {_ldp}\n"
                                f"Tags/keywords: {_kw}"
                            ).strip()
                            # If the form didn't get a name, use the one from the page
                            if not name_in and _ldn:
                                name_in = _ldn[:120]
                        else:
                            # 2) Fallback — strip HTML tags for plain text approximation
                            _no_script = _rre.sub(
                                r'<(script|style|nav|header|footer|aside)[^>]*>[\s\S]*?</\1>',
                                ' ', raw_html, flags=_rre.IGNORECASE)
                            text_in = _rre.sub(r'<[^>]+>', ' ', _no_script)
                            text_in = _rre.sub(r'\s{2,}', ' ', text_in).strip()[:6000]
                    except Exception:
                        text_in = url_in  # fallback: pass the URL itself

                ingr = ""; instr = ""; tags = []; prep = ""; ai_name = ""
                _ai_error = ""
                try:
                    _settings_r = load_app_settings()
                    api_key = (
                        _settings_r.get("family_constraints", {}).get("anthropic_api_key", "")
                        or _settings_r.get("anthropic_api_key", "")
                    ).strip()
                    if api_key:
                        import urllib.request as _ur3
                        if photo_bytes:
                            # Vision: read recipe from photo
                            img_b64 = _b64.b64encode(photo_bytes).decode()
                            media_type = "image/jpeg"
                            _vision_payload = _rj.dumps({
                                "model": "claude-opus-4-5",
                                "max_tokens": 4000,
                                "messages": [{
                                    "role": "user",
                                    "content": [
                                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                                        {"type": "text", "text": (
                                            "Read this recipe and return ONLY valid JSON (no markdown fences) with keys: "
                                            "name (string, the recipe title), "
                                            "ingredients (string, one item per line — ONLY ingredient amounts and items), "
                                            "instructions (string, the COMPLETE numbered/step-by-step cooking directions — every step, verbatim, do NOT summarize), "
                                            "tags (array of strings), prep_time (string). "
                                            "Critical: ingredients and instructions MUST be split correctly. Anything that describes a cooking action (heat, mix, bake, stir, simmer, season) belongs in instructions, NOT ingredients."
                                        )},
                                    ]
                                }]
                            }).encode()
                        else:
                            content = text_in or url_in
                            _vision_payload = _rj.dumps({
                                "model": "claude-sonnet-4-20250514",
                                "max_tokens": 4000,
                                "messages": [{"role": "user", "content": (
                                    "Parse this recipe into structured JSON. "
                                    "Return ONLY valid JSON (no markdown fences) with keys: "
                                    "name (string, the recipe title from the source), "
                                    "ingredients (string, one item per line — ONLY ingredient amounts and items, e.g. \"2 cups flour\"), "
                                    "instructions (string, the COMPLETE step-by-step cooking directions — copy every step verbatim from the source, do NOT abbreviate or summarize), "
                                    "tags (array of strings), prep_time (string).\n\n"
                                    "Critical: ingredients and instructions MUST be split correctly. Anything that describes a cooking action "
                                    "(preheat, heat, mix, combine, whisk, bake, stir, simmer, season, fold, knead, etc.) belongs in instructions, NOT ingredients. "
                                    "If the source does not clearly separate them, you must infer the split from context.\n\n"
                                    f"Recipe source:\n{content[:12000]}"
                                )}]
                            }).encode()
                        _rq = _ur3.Request(
                            "https://api.anthropic.com/v1/messages",
                            data=_vision_payload,
                            headers={"Content-Type": "application/json", "x-api-key": api_key,
                                     "anthropic-version": "2023-06-01"},
                        )
                        try:
                            with _ur3.urlopen(_rq, timeout=60) as _resp2:
                                _res = _rj.loads(_resp2.read())
                        except Exception as _http_err:
                            # Pull the actual error body from Anthropic so we can see what's wrong
                            _err_body = ""
                            try:
                                _err_body = getattr(_http_err, "read", lambda: b"")().decode("utf-8", "ignore")[:500]
                            except Exception: pass
                            print(f"[recipe-import] Anthropic HTTP error: {_http_err} — body: {_err_body}")
                            raise
                        raw_text_out = (_res.get("content", [{}])[0].get("text", "") or "").strip()
                        if not raw_text_out:
                            print(f"[recipe-import] Empty response body. _res keys: {list(_res.keys())} stop_reason: {_res.get('stop_reason')}")
                        # Strip markdown fences properly
                        raw_text_out = _rre.sub(r'^```(?:json)?\s*\n?', '', raw_text_out)
                        raw_text_out = _rre.sub(r'\n?```\s*$', '', raw_text_out).strip()
                        parsed_r = _rj.loads(raw_text_out)
                        ingr    = parsed_r.get("ingredients", "")
                        instr   = parsed_r.get("instructions", "")
                        tags    = parsed_r.get("tags", [])
                        prep    = parsed_r.get("prep_time", "")
                        ai_name = (parsed_r.get("name") or "").strip()
                except Exception as _re_err:
                    import traceback as _tb
                    _ai_error = str(_re_err)[:200]
                    print(f"[recipe-import] AI parse failed: {_ai_error}")
                    print("[recipe-import] traceback:\n" + _tb.format_exc())
                    # Fallback: drop the raw extracted text into instructions so the user
                    # can at least see/edit something rather than getting a blank form.
                    if text_in and not instr:
                        instr = text_in[:8000]
                # Pick a name: form input wins, then AI-detected, then a sensible fallback
                final_name = name_in or ai_name or (
                    "Imported recipe " + date.today().isoformat()
                )
                # Render preview/approval page instead of saving immediately
                from render_meals import render_recipe_import_preview
                _src_note_parts = []
                if url_in:
                    _src_note_parts.append(f"Imported from {url_in[:120]}")
                elif photo_name and photo_name.endswith(".pdf"):
                    _src_note_parts.append(f"Imported from PDF: {photo_name}")
                elif photo_bytes is None and dish_image_url:
                    _src_note_parts.append("Imported from photo")
                if _pdf_no_text:
                    _src_note_parts.append(
                        "⚠ This PDF appears to be a scan/image with no extractable text. "
                        "Try uploading the recipe as a JPEG/PNG photo instead — the AI can read images directly."
                    )
                if _ai_error and not ingr and not instr:
                    _src_note_parts.append(
                        f"⚠ AI extraction failed: {_ai_error}. "
                        "You can paste the recipe text manually into the fields below."
                    )
                _src_note = " · ".join(_src_note_parts)
                _preview_html = render_recipe_import_preview(
                    final_name, ingr, instr, tags or [], prep,
                    image_url=dish_image_url, source_note=_src_note,
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                try: self.wfile.write(_preview_html.encode())
                except BrokenPipeError: pass
                return

        else:
            # /plan-import-apply reads its own raw JSON body — don't consume it with URL form parse
            _JSON_PATHS = {"/plan-import-apply", "/curriculum-save", "/curriculum-minutes", "/poetry-passage-save"}
            data = {} if path in _JSON_PATHS else parse_urlencoded_body(self)

            if path == "/toggle-task":
                _tid  = data.get("task_id",[""])[0]
                _done = data.get("new_value",["false"])[0] == "true"
                set_task_done(_tid, _done)
                # When a MANUAL one-time task is checked off on a plan page,
                # permanently delete it (or advance if recurring) in manual_tasks.json
                # so it never reappears.
                if _done:
                    # Detect task type from ID and permanently remove from source
                    # Format A (plan page): MANUAL::{child}::{iso}::{text}  ← actual format
                    # Format B (legacy):   {iso}::{child}::MANUAL::{pri}::{text}
                    _tc = _tt = None
                    _raw_parts = _tid.split("::", 3)
                    if len(_raw_parts) >= 4 and _raw_parts[0] == "MANUAL":
                        # Format A — plan page manual task
                        _tc = _raw_parts[1]
                        _tt = _raw_parts[3]
                    else:
                        _p5 = _tid.split("::", 4)
                        if len(_p5) == 5 and _p5[2] == "MANUAL":
                            # Format B — legacy
                            _tc, _tt = _p5[1], _p5[4]
                    if _tc is not None and _tt is not None:
                        with _MANUAL_TASKS_LOCK:
                            _ml = load_manual_tasks()
                            _changed = False
                            _to_remove = None
                            # "Mom" and "Lauren" are the same person
                            _LAUREN_ALIASES = {"Lauren", "Mom"}
                            _tc_norm = "Lauren" if _tc in _LAUREN_ALIASES else _tc
                            for _mi, _mt in enumerate(_ml):
                                if not isinstance(_mt, dict): continue
                                if str(_mt.get("status","active")).strip().upper() != "ACTIVE": continue
                                # match by child (empty assigned_to means "anyone" — matches any child)
                                _at = str(_mt.get("assigned_to","")).strip()
                                _at_norm = "Lauren" if _at in _LAUREN_ALIASES else _at
                                if _at_norm and _at_norm != _tc_norm: continue
                                if str(_mt.get("text","")).strip().lower() != _tt.lower(): continue
                                if _mt.get("recurring"):
                                    _ml[_mi] = advance_recurring_task(_mt)
                                    _changed = True
                                else:
                                    _to_remove = _mi
                                break
                            if _to_remove is not None:
                                _ml.pop(_to_remove)
                                _changed = True
                                # ── Purge from task_registry for all future dates ──────────
                                # Prevents the task from re-surfacing via carryover because
                                # it was pre-registered on future day list builds.
                                try:
                                    from daily_schedule_engine import (
                                        load_task_registry, save_task_registry)
                                    from datetime import date as _dt2
                                    _today_iso = _dt2.today().isoformat()
                                    _reg = load_task_registry()
                                    _reg_changed = False
                                    _needle_lower = _tt.lower()
                                    for _rd, _rentries in _reg.items():
                                        if _rd < _today_iso:
                                            continue  # don't touch historical
                                        if not isinstance(_rentries, dict):
                                            continue
                                        _child_tasks = _rentries.get(_tc, [])
                                        if not isinstance(_child_tasks, list):
                                            continue
                                        _new_list = []
                                        for _rt in _child_tasks:
                                            import re as _re2
                                            _m = _re2.match(
                                                r'^MANUAL::(?:HIGH|MEDIUM|LOW)::(.+)$',
                                                _rt, _re2.IGNORECASE)
                                            _rt_text = _m.group(1) if _m else _rt
                                            if _rt_text.strip().lower() == _needle_lower:
                                                _reg_changed = True  # drop it
                                            else:
                                                _new_list.append(_rt)
                                        _rentries[_tc] = _new_list
                                    if _reg_changed:
                                        save_task_registry(_reg)
                                except Exception:
                                    pass
                            # Auto-refill: keep at least 5 active tasks for the boys only.
                            # Lauren manages her own task list — refill does not apply to her.
                            _BOY_NAMES = {"JP", "Joseph", "Michael", "James"}
                            _REFILL_MIN = 5
                            _active_count = sum(
                                1 for t in _ml
                                if isinstance(t, dict)
                                and str(t.get("assigned_to","")).strip() == _tc
                                and str(t.get("status","active")).strip().upper() == "ACTIVE"
                            )
                            if _tc in _BOY_NAMES and _active_count < _REFILL_MIN:
                                _need = _REFILL_MIN - _active_count
                                # Trivial/routine phrases to skip during refill
                                _skip_phrases = {"wake up","eat breakfast","eat lunch","eat dinner","get dressed","brush teeth","go to bed","bedtime"}
                                for _ri, _rt in enumerate(_ml):
                                    if _need <= 0: break
                                    if not isinstance(_rt, dict): continue
                                    if str(_rt.get("assigned_to","")).strip() != _tc: continue
                                    if str(_rt.get("status","active")).strip().upper() != "INACTIVE": continue
                                    if _rt.get("recurring"): continue
                                    _rtxt = str(_rt.get("text","")).strip().lower()
                                    if any(_rtxt.startswith(p) for p in _skip_phrases): continue
                                    _ml[_ri] = {**_rt, "status": "active"}
                                    _changed = True
                                    _need -= 1
                            if _changed:
                                save_manual_tasks(_ml)
                # ── Family Quest bridge: award XP when task checked off ────────
                if _done:
                    try:
                        _FQ_CK = {"JP":"jp","Joseph":"joseph",
                                  "Michael":"michael","James":"james"}
                        _p = _tid.split("::")
                        # Two task_id formats:
                        #   NEW: SCHOOL::{child}::{iso}::{subject}::{step}
                        #   OLD: {iso}::{child}::SCHOOL::{subject}::{step}
                        _t_kind = _t_child = _t_iso = _t_label = None
                        if len(_p) >= 5 and _p[0] in ("SCHOOL","CHORE"):
                            # NEW format
                            _t_kind, _t_child, _t_iso, _t_label = (
                                _p[0], _p[1], _p[2], _p[3])
                        elif len(_p) >= 4 and _p[2] in ("SCHOOL","CHORE"):
                            # OLD format
                            _t_iso, _t_child, _t_kind, _t_label = (
                                _p[0], _p[1], _p[2], _p[3])
                        _t_ckey = _FQ_CK.get(_t_child) if _t_child else None
                        if _t_ckey and _t_kind in ("SCHOOL", "CHORE"):
                            import sys as _fqs2, os as _fqo2
                            _fq_root3 = _fqo2.path.join(
                                _fqo2.path.dirname(_fqo2.path.abspath(__file__)),
                                "family_quest")
                            if _fq_root3 not in _fqs2.path:
                                _fqs2.path.insert(0, _fq_root3)
                            from fq_data import (get_quests_for_child,
                                                 complete_quest as _fq_complete,
                                                 is_completed as _fq_done,
                                                 award_school_step as _fq_school_step,
                                                 finalize_quest_no_reward as _fq_finalize)
                            _fq_quests = get_quests_for_child(_t_ckey, _t_iso)

                            if _t_kind == "CHORE":
                                # Chore = single step → full XP via complete_quest
                                _mq = next(
                                    (q for q in _fq_quests
                                     if q.get("title","").lower() == _t_label.lower()),
                                    None)
                                if _mq and not _fq_done(_mq, _t_ckey):
                                    _fq_complete(_mq["id"], _t_ckey)

                            elif _t_kind == "SCHOOL":
                                # School = proportional energy/rc/gc per step
                                _subj_low = _t_label.lower()
                                _mq = next(
                                    (q for q in _fq_quests
                                     if q.get("title","").lower().startswith(
                                         _subj_low + " —") or
                                        q.get("title","").lower() == _subj_low),
                                    None)
                                if _mq and not _fq_done(_mq, _t_ckey):
                                    # Count total checkable steps for this subject
                                    _subj_prefix = (
                                        f"SCHOOL::{_t_child}::{_t_iso}::{_t_label}::")
                                    from daily_schedule_engine import (
                                        build_day_list as _bdl,
                                        load_progress as _lpr)
                                    _dl = _bdl(_t_child, __import__('datetime').date
                                               .fromisoformat(_t_iso).strftime('%A'),
                                               _t_iso)
                                    _step_tids = [
                                        sub["task_id"]
                                        for block in _dl
                                        for sub in block.get("sub_items", [])
                                        if sub.get("checkable") and
                                           sub.get("task_id","").startswith(_subj_prefix)
                                    ]
                                    _n_steps = len(_step_tids) or 1
                                    # Award proportional share using actual v2 quest values
                                    _fq_school_step(
                                        _t_ckey, _mq, _n_steps,
                                        f"{_t_label} (step)", _t_iso)
                                    # If all steps now done → finalize quest (streak + bonus,
                                    # no double-award since partial coins already given)
                                    _prog = _lpr()
                                    _all_done = all(
                                        _prog.get(tid, False) for tid in _step_tids)
                                    if _all_done:
                                        _fq_finalize(_mq["id"], _t_ckey)
                    except Exception:
                        pass  # never block a task toggle due to FQ errors
                # ───────────────────────────────────────────────────────────────
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(b'{"ok":true}'); return

            elif path == "/schedule-template-save":
                import json as _json
                from pathlib import Path as _Path
                _child   = clean_child(data.get("child",[""])[0])
                _weekday = clean_weekday(data.get("weekday",[""])[0])
                _n       = safe_int(data.get("slot_count",["0"])[0], 0)
                if _child and _weekday:
                    _tmpl_path = _Path(f"data/day_templates/{_weekday}.json")
                    try:
                        _tmpl = _json.loads(_tmpl_path.read_text(encoding="utf-8"))
                    except Exception:
                        _tmpl = {"weekday": _weekday, "grid": {}}
                    _new_slots = {}
                    for _i in range(_n):
                        _ts  = clean_text(data.get(f"slot_time_{_i}",[""])[0]).strip()
                        _lbl = clean_text(data.get(f"slot_label_{_i}",[""])[0]).strip()
                        if _ts and _lbl:
                            _new_slots[_ts] = _lbl
                    _tmpl.setdefault("grid", {})[_child] = _new_slots
                    safe_save_json(str(_tmpl_path), _tmpl)
                redirect = f"/schedule/{_child}?date={date.today().isoformat()}&msg=saved"

            elif path == "/add-note":
                text = clean_text(data.get("text",[""])[0])
                if text: add_note(text)
                redirect = "/notes#top"

            elif path == "/archive-note":
                archive_note(data.get("id",[""])[0]); redirect = "/notes#top"

            elif path == "/convert-note":
                note_id=data.get("id",[""])[0]; assigned_to=clean_text(data.get("assigned_to",[""])[0])
                due_date=clean_text(data.get("due_date",[""])[0]); priority=clean_priority(data.get("priority",["MEDIUM"])[0])
                notes=load_notes(); tasks=load_manual_tasks()
                for note in notes:
                    if note.get("id")==note_id:
                        tasks.append({"text":clean_text(note.get("text","")),"assigned_to":assigned_to,"due_date":due_date,"priority":priority,"status":"active"})
                        note["status"]="archived"; break
                save_manual_tasks(tasks); save_notes(notes); redirect="/notes"

            elif path == "/add-task":
                text=clean_text(data.get("text",[""])[0])
                assigned_to_list=[clean_text(v) for v in data.get("assigned_to",[]) if clean_text(v)]
                due_date=clean_text(data.get("due_date",[""])[0]); priority=clean_priority(data.get("priority",["MEDIUM"])[0])
                is_recurring=data.get("recurring",[""])[0]=="true"
                iv=safe_int(data.get("interval_value",["1"])[0],1); iu=clean_text(data.get("interval_unit",["weeks"])[0])
                _legacy_units = {"monthly_last_sat","monthly_last_sun","monthly_first_sat","monthly_first_sun","monthly_last_fri","monthly_first_fri"}
                _allowed_units = {"days","weeks","months","years","weekdays","specific_weekdays","monthly_day","monthly_nth_weekday"} | _legacy_units
                if iu not in _allowed_units: iu="weeks"
                # Cap interval_value to a sane max so degenerate inputs can't drive expensive loops
                if iv<1: iv=1
                if iv>366: iv=366
                # Mode-specific fields
                _wdmask=[]
                if iu=="specific_weekdays":
                    for v in data.get("weekdays_mask",[]):
                        n=safe_int(v,-1)
                        if 0<=n<=6 and n not in _wdmask: _wdmask.append(n)
                    # Required: at least one weekday must be selected
                    if not _wdmask:
                        iu="weeks"  # graceful fallback rather than hard reject
                _mday=safe_int(data.get("month_day",["1"])[0],1)
                if _mday!=-1: _mday=max(1, min(31, _mday))
                _mnth=safe_int(data.get("month_nth",["1"])[0],1)
                if _mnth not in (1,2,3,4,5,-1): _mnth=1
                _mwd =safe_int(data.get("month_weekday",["0"])[0],0)
                if not (0<=_mwd<=6): _mwd=0
                # Strict ISO validation for end_date — reject silently if malformed
                _end_date=clean_text(data.get("end_date",[""])[0])
                if _end_date:
                    try:
                        from datetime import date as _vdate
                        _vdate.fromisoformat(_end_date)
                    except Exception:
                        _end_date=""
                _max_occ_raw=clean_text(data.get("max_occurrences",[""])[0])
                _max_occ=safe_int(_max_occ_raw,0) if _max_occ_raw else 0
                if _max_occ<0: _max_occ=0
                if _max_occ>9999: _max_occ=9999
                if text:
                    tasks=load_manual_tasks()
                    targets = assigned_to_list if assigned_to_list else [""]
                    for _who in targets:
                        t={"text":text,"assigned_to":_who,"due_date":due_date,"priority":priority,"status":"active","recurring":is_recurring}
                        if is_recurring:
                            t["interval_value"]=iv; t["interval_unit"]=iu
                            if iu=="specific_weekdays" and _wdmask: t["weekdays_mask"]=_wdmask
                            if iu=="monthly_day": t["month_day"]=_mday
                            if iu=="monthly_nth_weekday":
                                t["month_nth"]=_mnth; t["month_weekday"]=_mwd
                            if _end_date: t["end_date"]=_end_date
                            if _max_occ>0: t["occurrences_remaining"]=_max_occ
                        tasks.append(t)
                    save_manual_tasks(tasks)
                ru=data.get("return_url",["/tasks"])[0]
                import re as _reu
                _pod_pat = _reu.compile(r'^/schedule/[A-Za-z]{1,30}$')
                if ru in ("/tasks","/mom","/mom-profile") or _pod_pat.match(ru):
                    redirect = ru + "#tasks"
                else:
                    redirect = "/tasks#top"

            elif path == "/task-done":
                # Permanently delete one-time tasks; advance recurring ones to next due date
                idx=safe_int(data.get("index",["0"])[0],0); tasks=load_manual_tasks()
                if 0<=idx<len(tasks) and isinstance(tasks[idx],dict):
                    t=tasks[idx]
                    if t.get("recurring"):
                        tasks[idx]=advance_recurring_task(t)
                    else:
                        tasks.pop(idx)
                    save_manual_tasks(tasks)
                redirect=data.get("return_url",["/tasks"])[0] + "#top"

            elif path == "/task-delete":
                idx=safe_int(data.get("index",["0"])[0],0); tasks=load_manual_tasks()
                if 0<=idx<len(tasks) and isinstance(tasks[idx],dict):
                    tasks[idx]["status"]="inactive"; save_manual_tasks(tasks)
                redirect="/tasks#top"

            elif path == "/task-hard-delete":
                # Permanently remove a single task by index (regardless of status)
                idx=safe_int(data.get("index",["0"])[0],0); tasks=load_manual_tasks()
                if 0<=idx<len(tasks) and isinstance(tasks[idx],dict):
                    tasks.pop(idx); save_manual_tasks(tasks)
                redirect="/tasks#top"

            elif path == "/task-purge-inactive":
                # Permanently delete ALL inactive/archived tasks
                tasks=load_manual_tasks()
                tasks=[t for t in tasks if not (isinstance(t,dict) and t.get("status")=="inactive")]
                save_manual_tasks(tasks)
                redirect="/tasks#top"

            elif path == "/task-override":
                # dismiss / postpone / timed override for a POD task
                import json as _toj
                _to_id    = data.get("task_id", [""])[0].strip()
                _to_child = data.get("child",   [""])[0].strip()
                # Normalize child to canonical name:
                #   "jp" → "JP", "joseph" → "Joseph", etc.
                #   "lauren" / "mom" → "Lauren"
                if _to_child.lower() in ("lauren", "mom"):
                    _to_child = "Lauren"
                else:
                    _to_child = next((c for c in CHILDREN if c.lower() == _to_child.lower()), _to_child)
                _to_iso   = data.get("iso",     [""])[0].strip()
                _to_act   = data.get("action",  [""])[0].strip()  # dismiss|postpone|timed|clear
                _to_time  = data.get("time",    [""])[0].strip()  # HH:MM for timed
                _to_pdate = data.get("postpone_to", [""])[0].strip()  # YYYY-MM-DD
                _to_label = data.get("label",   [""])[0].strip()
                _to_ret   = data.get("return_url", ["/mom-profile"])[0].strip()
                _json_resp = False
                if data.get("json", [""])[0] == "1":
                    _json_resp = True
                try:
                    from data_helpers import set_task_override, clear_task_override
                    if _to_id and _to_child and _to_iso and _to_act:
                        if _to_act == "clear":
                            clear_task_override(_to_child, _to_iso, _to_id)
                        elif _to_act == "postpone":
                            from datetime import date as _tod, timedelta as _totd
                            _pdate = _to_pdate or (_tod.fromisoformat(_to_iso) + _totd(days=1)).isoformat()
                            set_task_override(_to_child, _to_iso, _to_id, {
                                "action": "postpone",
                                "postpone_to": _pdate,
                                "label": _to_label,
                            })
                        elif _to_act == "timed":
                            set_task_override(_to_child, _to_iso, _to_id, {
                                "action": "timed",
                                "time": _to_time,
                                "label": _to_label,
                            })
                        elif _to_act == "dismiss":
                            set_task_override(_to_child, _to_iso, _to_id, {
                                "action": "dismiss",
                                "label": _to_label,
                            })
                            # Permanent side-effects for CARRY and MANUAL tasks:
                            # 1. Mark done in progress.json so it won't carry over tomorrow
                            # 2. Delete from manual_tasks.json so it never reappears
                            try:
                                from daily_schedule_engine import set_task_done as _std
                                _std(_to_id, True)
                            except Exception:
                                pass
                            # Identify task text for manual_tasks.json deletion
                            _dm_child = _dm_text = None
                            _dm_parts = _to_id.split("::", 3)
                            if len(_dm_parts) >= 4 and _dm_parts[0] == "CARRY":
                                # CARRY::child::iso::display_text — strip [PRIORITY] prefix
                                _dm_child = _dm_parts[1]
                                _dm_raw   = _dm_parts[3]
                                import re as _re
                                _dm_text  = _re.sub(r"^\[(HIGH|MEDIUM|LOW)\]\s*", "", _dm_raw)
                            elif len(_dm_parts) >= 4 and _dm_parts[0] == "MANUAL":
                                # MANUAL::child::iso::text (old format)
                                _dm_child = _dm_parts[1]
                                _dm_text  = _dm_parts[3]
                            else:
                                _dm5 = _to_id.split("::", 4)
                                if len(_dm5) == 5 and _dm5[2] == "MANUAL":
                                    # make_task_id format: iso::child::MANUAL::priority::text
                                    _dm_child = _dm5[1]
                                    _dm_text  = _dm5[4]
                            if _dm_child and _dm_text:
                                _LAUREN_ALIASES = {"Lauren", "Mom"}
                                _dm_child_n = "Lauren" if _dm_child in _LAUREN_ALIASES else _dm_child
                                with _MANUAL_TASKS_LOCK:
                                    _dml = load_manual_tasks()
                                    _dm_changed = False
                                    _dm_remove = None
                                    for _dmi, _dmt in enumerate(_dml):
                                        if not isinstance(_dmt, dict): continue
                                        _dat = str(_dmt.get("assigned_to", "")).strip()
                                        _dat_n = "Lauren" if _dat in _LAUREN_ALIASES else _dat
                                        if _dat_n and _dat_n != _dm_child_n: continue
                                        if str(_dmt.get("text", "")).strip().lower() != _dm_text.strip().lower(): continue
                                        _dm_remove = _dmi
                                        break
                                    if _dm_remove is not None:
                                        _dml.pop(_dm_remove)
                                        _dm_changed = True
                                        # Also purge from task_registry for all future dates
                                        try:
                                            from daily_schedule_engine import (
                                                load_task_registry, save_task_registry)
                                            from datetime import date as _ddt2
                                            _dtoday = _ddt2.today().isoformat()
                                            _dreg = load_task_registry()
                                            _dreg_changed = False
                                            _dneedle = _dm_text.strip().lower()
                                            for _drd, _dre in _dreg.items():
                                                if _drd < _dtoday:
                                                    continue
                                                if not isinstance(_dre, dict):
                                                    continue
                                                _dct = _dre.get(_dm_child, [])
                                                if not isinstance(_dct, list):
                                                    continue
                                                _dnl = []
                                                for _drt in _dct:
                                                    import re as _dre2
                                                    _dm2 = _dre2.match(
                                                        r'^MANUAL::(?:HIGH|MEDIUM|LOW)::(.+)$',
                                                        _drt, _dre2.IGNORECASE)
                                                    _drt_txt = _dm2.group(1) if _dm2 else _drt
                                                    if _drt_txt.strip().lower() == _dneedle:
                                                        _dreg_changed = True
                                                    else:
                                                        _dnl.append(_drt)
                                                _dre[_dm_child] = _dnl
                                            if _dreg_changed:
                                                save_task_registry(_dreg)
                                        except Exception:
                                            pass
                                    if _dm_changed:
                                        save_manual_tasks(_dml)
                        elif _to_act == "recurring":
                            # Convert this task to a recurring manual task in manual_tasks.json
                            _freq = data.get("frequency", ["daily"])[0].strip().lower()
                            _freq_map = {
                                "daily":    ("days",     1),
                                "weekdays": ("weekdays", 1),
                                "weekly":   ("weeks",    1),
                            }
                            _r_unit, _r_val = _freq_map.get(_freq, ("days", 1))
                            _r_task_text = _to_label
                            _r_LAUREN = {"Lauren", "Mom"}
                            _r_child_n = "Lauren" if _to_child in _r_LAUREN else _to_child
                            with _MANUAL_TASKS_LOCK:
                                _rml = load_manual_tasks()
                                _r_found = False
                                for _rmi, _rmt in enumerate(_rml):
                                    if not isinstance(_rmt, dict): continue
                                    if str(_rmt.get("status", "active")).upper() != "ACTIVE": continue
                                    _rat = str(_rmt.get("assigned_to", "")).strip()
                                    _rat_n = "Lauren" if _rat in _r_LAUREN else _rat
                                    if _rat_n and _rat_n != _r_child_n: continue
                                    if str(_rmt.get("text", "")).strip().lower() != _r_task_text.lower(): continue
                                    _rml[_rmi]["recurring"] = True
                                    _rml[_rmi]["interval_unit"] = _r_unit
                                    _rml[_rmi]["interval_value"] = _r_val
                                    _r_found = True
                                    break
                                if not _r_found:
                                    _rml.append({
                                        "text": _r_task_text,
                                        "assigned_to": _to_child,
                                        "due_date": _to_iso,
                                        "priority": "MEDIUM",
                                        "status": "active",
                                        "recurring": True,
                                        "interval_unit": _r_unit,
                                        "interval_value": _r_val,
                                    })
                                save_manual_tasks(_rml)
                    if _json_resp:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        try: self.wfile.write(_toj.dumps({"ok": True}).encode())
                        except BrokenPipeError: pass
                        return
                except Exception as _toe:
                    if _json_resp:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        try: self.wfile.write(_toj.dumps({"ok": False, "error": str(_toe)}).encode())
                        except BrokenPipeError: pass
                        return
                redirect = _to_ret

            # ── Thank-you card reminder routes ────────────────────────────────
            elif path == "/thankyou-add":
                import uuid as _uuid2
                from datetime import date as _tyd
                _ename     = clean_text(data.get("event_name",[""])[0])
                _ppl       = clean_text(data.get("people",[""])[0])
                _assignee  = data.get("assigned_to",["Family"])[0].strip() or "Family"
                _edate     = data.get("event_date",[""])[0].strip()
                _rdate     = data.get("reminder_date",[""])[0].strip()
                _note      = clean_text(data.get("note",[""])[0])
                if not _rdate:
                    from datetime import timedelta as _tytd
                    _rdate = str(_tyd.today() + _tytd(days=2))
                if _ename:
                    _reminders = load_thankyou_reminders()
                    _reminders.append({
                        "id":            "ty_" + _uuid2.uuid4().hex[:8],
                        "event_name":    _ename,
                        "people":        _ppl,
                        "assigned_to":   _assignee,
                        "event_date":    _edate,
                        "reminder_date": _rdate,
                        "note":          _note,
                        "status":        "pending",
                    })
                    save_thankyou_reminders(_reminders)
                redirect = "/thankyou-reminders#top"

            elif path == "/exercise-log":
                _ALLOWED_PEOPLE = {"Lauren","John","JP","Joseph","Michael","James"}
                _person = data.get("person",[""])[0].strip()
                _iso    = data.get("iso",[""])[0].strip()
                _dur    = (data.get("duration",[""])[0] or "")[:80]
                _reps   = (data.get("reps",[""])[0] or "")[:500]
                _felt   = (data.get("felt",[""])[0] or "")[:500]
                # Validate person whitelist
                if _person == "Mom":
                    _person = "Lauren"
                _ok_person = _person in _ALLOWED_PEOPLE
                # Validate ISO date
                _ok_iso = False
                try:
                    import datetime as _ddt
                    _ddt.date.fromisoformat(_iso)
                    _ok_iso = True
                except Exception:
                    _ok_iso = False
                if _ok_person and _ok_iso:
                    try:
                        from data_helpers import save_exercise_log as _sxl
                        _sxl(_person, _iso, _dur, _reps, _felt)
                    except Exception:
                        pass
                _r = data.get("return_url",[f"/schedule/{_person}" if _ok_person else "/today"])[0]
                # Restrict redirect to in-app schedule pages
                if not _r.startswith("/schedule/") and _r not in ("/today",):
                    _r = f"/schedule/{_person}" if _ok_person else "/today"
                redirect = _r

            elif path == "/thankyou-done":
                _tid = data.get("id",[""])[0].strip()
                if _tid:
                    _reminders = load_thankyou_reminders()
                    for _r in _reminders:
                        if isinstance(_r, dict) and _r.get("id") == _tid:
                            _r["status"] = "done"; break
                    save_thankyou_reminders(_reminders)
                redirect = data.get("return_url",["/thankyou-reminders"])[0]
                _ty_allowed = ("/thankyou-reminders", "/tasks", "/today", "/mom-profile",
                               "/schedule/JP", "/schedule/Joseph", "/schedule/Michael",
                               "/schedule/John")
                if redirect not in _ty_allowed:
                    redirect = "/thankyou-reminders"

            elif path == "/thankyou-dismiss":
                _tid = data.get("id",[""])[0].strip()
                if _tid:
                    _reminders = load_thankyou_reminders()
                    for _r in _reminders:
                        if isinstance(_r, dict) and _r.get("id") == _tid:
                            _r["status"] = "dismissed"; break
                    save_thankyou_reminders(_reminders)
                redirect = data.get("return_url",["/thankyou-reminders"])[0]
                _ty_allowed = ("/thankyou-reminders", "/tasks", "/today", "/mom-profile",
                               "/schedule/JP", "/schedule/Joseph", "/schedule/Michael",
                               "/schedule/John")
                if redirect not in _ty_allowed:
                    redirect = "/thankyou-reminders"

            elif path == "/thankyou-suggest":
                # Lauren's POD suggested-task widget
                # action = "add"  → create manual task(s) for chosen people
                # action = "sent" → mark the reminder as done (already sent)
                # action = "skip" → do nothing (card stays due for next visit)
                _action    = data.get("action", ["skip"])[0].strip()
                _rid       = data.get("reminder_id", [""])[0].strip()
                _task_text = clean_text(data.get("task_text", [""])[0])
                _assignees = [clean_text(v) for v in data.get("assign_to", []) if clean_text(v)]
                _ret       = data.get("return_url", ["/today"])[0]
                if _ret not in ("/today", "/tasks", "/mom-profile", "/thankyou-reminders",
                                "/schedule/JP", "/schedule/Joseph", "/schedule/Michael",
                                "/schedule/John"):
                    _ret = "/today"

                if _action == "add" and _task_text:
                    # Create one manual task per selected person (or unassigned if none checked)
                    _tasks = load_manual_tasks()
                    _targets = _assignees if _assignees else [""]
                    for _who in _targets:
                        _tasks.append({"text": _task_text, "assigned_to": _who,
                                       "due_date": "", "priority": "HIGH",
                                       "status": "active", "recurring": False})
                    save_manual_tasks(_tasks)

                elif _action == "sent" and _rid:
                    # Mark the thank-you card reminder as done
                    _reminders = load_thankyou_reminders()
                    for _r in _reminders:
                        if isinstance(_r, dict) and _r.get("id") == _rid:
                            _r["status"] = "done"; break
                    save_thankyou_reminders(_reminders)

                # "skip" → fall through with no data changes
                redirect = _ret

            elif path == "/approve-school-preview":
                child=clean_child(data.get("child",[""])[0])
                if child: approve_school_preview(child)
                redirect="/school#top"

            elif path == "/reparse-school-preview":
                child=clean_child(data.get("child",[""])[0]); raw_text=clean_text(data.get("raw_text",[""])[0])
                preview=load_school_preview(child)
                if child and raw_text and preview:
                    save_school_preview(child, preview.get("filename","edited_preview"), raw_text, parse_school_pdf_text(raw_text,child))
                redirect=f"/school/edit?child={child}"

            elif path == "/save-school-preview-edits":
                child=clean_child(data.get("child",[""])[0]); preview=load_school_preview(child)
                if child and preview:
                    dc=safe_int(data.get("day_count",["0"])[0],0); parsed_days=[]
                    for di in range(dc):
                        wd=clean_weekday(data.get(f"weekday__{di}",[""])[0]); dl=clean_text(data.get(f"day_label__{di}",[""])[0])
                        bc=safe_int(data.get(f"block_count__{di}",["0"])[0],0); bwo=[]
                        for bi in range(bc):
                            s=clean_text(data.get(f"subject__{di}__{bi}",[""])[0]); a=clean_text(data.get(f"assignment__{di}__{bi}",[""])[0])
                            o=safe_int(data.get(f"order__{di}__{bi}",["0"])[0],bi+1)
                            if data.get(f"delete__{di}__{bi}",[""])[0]=="yes": continue
                            if not s and not a: continue
                            bwo.append({"order":o,"subject":s or "Unsorted","assignment_text":a})
                        bwo.sort(key=lambda b:(b["order"],b["subject"].lower()))
                        blocks=[{"subject":b["subject"],"assignment_text":b["assignment_text"],"is_math":is_math_subject(b["subject"]),"is_math_test":is_math_test_text(b["subject"],b["assignment_text"])} for b in bwo]
                        parsed_days.append({"weekday":wd,"day_label":dl,"blocks":blocks})
                    parsed_days=sort_school_days(parsed_days)
                    save_school_preview(child,preview.get("filename","edited_preview"),preview.get("raw_text",""),{"child":child,"parsed_days":parsed_days,"raw_text":preview.get("raw_text","")})
                redirect=f"/school/edit?child={child}"

            elif path == "/save-chores":
                import json as _json
                _is_ajax = data.get("_ajax",[""])[0] == "1"
                def _split_lines(text):
                    return [line for line in str(text).splitlines() if line.strip()]
                _expected_fields = {f"daily__{c}" for c in CHILDREN} | {"daily__Lauren"}
                _received_fields  = set(data.keys()) - {"_ajax"}
                if not (_expected_fields & _received_fields):
                    _err = "form data was empty"
                    if _is_ajax:
                        _out = _json.dumps({"ok": False, "error": _err}).encode()
                        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                        try: self.wfile.write(_out)
                        except BrokenPipeError: pass
                        return
                    redirect = "/chores?msg=error:Save+failed+%E2%80%94+form+data+was+empty.+Please+try+again.#top"
                else:
                    chores={"boys":{},"lauren":{}}
                    for child in CHILDREN:
                        chores["boys"][child]={"daily":_split_lines(data.get(f"daily__{child}",[""])[0]),"weekly":{wd:_split_lines(data.get(f"weekly__{child}__{wd}",[""])[0]) for wd in WEEKDAYS}}
                    chores["lauren"]={"daily":_split_lines(data.get("daily__Lauren",[""])[0]),"weekly":{wd:_split_lines(data.get(f"weekly__Lauren__{wd}",[""])[0]) for wd in WEEKDAYS}}
                    _ok = save_chores_data(chores)
                    if _is_ajax:
                        _out = _json.dumps({"ok": bool(_ok)}).encode()
                        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                        try: self.wfile.write(_out)
                        except BrokenPipeError: pass
                        return
                    if _ok:
                        redirect="/chores?msg=Chores+saved#top"
                    else:
                        redirect="/chores?msg=error:Save+failed+%E2%80%94+could+not+write+to+disk.+Please+try+again.#top"

            elif path == "/apply-laundry":
                save_chores_data(apply_laundry_defaults(load_chores_data()))
                redirect="/chores?msg=Laundry+schedule+applied+to+weekly+chores#top"

            elif path == "/signup-submit":
                import urllib.parse as _up
                name       = clean_text(data.get("name",[""])[0])
                email      = clean_text(data.get("email",[""])[0])
                if not name or not email:
                    body = render_signup_page(error="Please enter your name and email address.")
                    self._send_html(body); return
                entry = {
                    "submitted_at":      datetime.now().isoformat(timespec="seconds"),
                    "name":              name,
                    "email":             email,
                    "num_children":      clean_text(data.get("num_children",[""])[0]),
                    "child_ages":        clean_text(data.get("child_ages",[""])[0]),
                    "hs_years":          clean_text(data.get("hs_years",[""])[0]),
                    "family_type":       clean_text(data.get("family_type",[""])[0]),
                    "device":            clean_text(data.get("device",[""])[0]),
                    "willingness_to_pay":clean_text(data.get("willingness_to_pay",[""])[0]),
                    "price_range":       clean_text(data.get("price_range",[""])[0]),
                    "biggest_challenge": clean_text(data.get("biggest_challenge",[""])[0]),
                    "other_notes":       clean_text(data.get("other_notes",[""])[0]),
                    "notify":            clean_text(data.get("notify",["Yes"])[0]),
                    "current_tools":     [clean_text(v) for v in data.get("current_tools",[])],
                    "features":          [clean_text(v) for v in data.get("features",[])],
                }
                save_signup(entry)
                body = render_signup_page(submitted=True)
                self._send_html(body); return

            elif path == "/waitlist":
                pw = clean_text(data.get("pw",[""])[0])
                from render_settings import load_app_settings as _las
                _s  = _las()
                ok  = (pw == _s.get("waitlist_password","admin2026"))
                body = render_waitlist_admin(ok)
                self._send_html(body); return

            elif path == "/apply-canonical-chores":
                from render_chores import apply_canonical_chores
                save_chores_data(apply_canonical_chores(load_chores_data()))
                redirect = "/chores?msg=Canonical+chore+defaults+applied#top"

            elif path == "/apply-kitchen-rotation":
                from render_chores import (
                    get_kitchen_roles,
                    KITCHEN_ROLE_A_MORNING, KITCHEN_ROLE_A_EVENING,
                    KITCHEN_ROLE_B_MORNING, KITCHEN_ROLE_B_EVENING,
                )
                chores = load_chores_data()
                boys   = chores.get("boys", {})
                roles  = get_kitchen_roles()
                for child in ("JP", "Joseph"):
                    role    = roles[child]
                    morning = KITCHEN_ROLE_A_MORNING if role == "A" else KITCHEN_ROLE_B_MORNING
                    evening = KITCHEN_ROLE_A_EVENING if role == "A" else KITCHEN_ROLE_B_EVENING
                    boys.setdefault(child, {"daily": [], "weekly": {}})
                    existing    = boys[child].get("daily", [])
                    non_kitchen = [l for l in existing if not l.startswith("KITCHEN")]
                    boys[child]["daily"] = non_kitchen + [""] + morning + [""] + evening
                chores["boys"] = boys
                save_chores_data(chores)
                redirect = "/chores?msg=Kitchen+rotation+applied+to+daily+chores#top"

            elif path == "/apply-van-rotation":
                save_chores_data(apply_van_rotation(load_chores_data())); redirect="/van-roles#top"

            elif path == "/mom-add-note":
                text=clean_text(data.get("text",[""])[0])
                if text:
                    notes=load_mom_notes(); notes.append({"id":str(uuid.uuid4()),"text":text,"status":"active"}); save_mom_notes(notes)
                redirect="/mom#top"

            elif path == "/mom-archive-note":
                note_id=data.get("id",[""])[0]; notes=load_mom_notes()
                for note in notes:
                    if str(note.get("id",""))==note_id: note["status"]="archived"; break
                save_mom_notes(notes); redirect="/mom#top"

            elif path == "/history-restore":
                key = (data.get("key",[""])[0] or data.get("filename",[""])[0]).strip()
                from urllib.parse import quote as _q
                if not key:
                    redirect = "/history?msg=" + _q("No snapshot specified.")
                else:
                    ok, msg = restore_snapshot(key)
                    redirect = "/history?msg=" + _q(msg if ok else f"Restore failed: {msg}")

            elif path == "/plan-add-item":
                iso    = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                text   = clean_text(data.get("text",[""])[0])
                source = clean_text(data.get("source",["manual"])[0])
                color  = clean_text(data.get("color",["#6b7280"])[0])
                itime  = clean_text(data.get("time",[""])[0])
                if text:
                    plan = add_item_to_plan(iso, text, source, color, itime)
                    count = len(plan.get("items",[]))
                else:
                    count = 0
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                import json as _json
                try: self.wfile.write(_json.dumps({"ok":True,"count":count}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/plan-toggle-item":
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                item_id = clean_text(data.get("id",[""])[0])
                done    = toggle_plan_item(iso, item_id)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                import json as _json
                try: self.wfile.write(_json.dumps({"ok":True,"done":done}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/plan-delete-item":
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                item_id = clean_text(data.get("id",[""])[0])
                delete_plan_item(iso, item_id)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-reorder":
                iso  = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                ids  = clean_text(data.get("ids",[""])[0]).split(",")
                ids  = [i.strip() for i in ids if i.strip()]
                reorder_plan_items(iso, ids)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-set-time":
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                item_id = clean_text(data.get("id",[""])[0])
                itime   = clean_text(data.get("time",[""])[0])
                update_item_time(iso, item_id, itime)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-publish":
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                publish_plan(iso)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-reset":
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                reset_plan(iso)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/anchor-save":
                import json as _json
                iso      = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                raw_data = clean_text(data.get("data",["{}"])[0])
                try:
                    updates_flat = _json.loads(raw_data)
                    # Support dot-notation keys like "evening.dinner_cleanup"
                    from render_daily_plan import load_daily_plan, save_daily_plan
                    plan   = load_daily_plan(iso)
                    anchor = plan.get("anchor", {})
                    for k, v in updates_flat.items():
                        if "." in k:
                            section, sub = k.split(".", 1)
                            anchor.setdefault(section, {})[sub] = v
                        else:
                            anchor[k] = v
                    plan["anchor"] = anchor
                    save_daily_plan(plan)
                except Exception as e:
                    print("[anchor-save error]", str(e))
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-sort":
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                sort_plan_chronologically(iso)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/grid-save-template":
                import json as _json
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                weekday = clean_text(data.get("weekday",[""])[0])
                if weekday:
                    grid = load_day_grid(iso)
                    save_day_template(weekday, {"weekday": weekday, "grid": grid})
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/grid-push-weekly":
                import json as _json
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                weekday = clean_text(data.get("weekday",[""])[0])
                if weekday:
                    grid = load_day_grid(iso)
                    # Push Mom's column to the FROL day template
                    if grid:
                        save_day_template(weekday, {"weekday": weekday, "grid": grid})
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/grid-cell-save":
                import json as _json
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                raw     = clean_text(data.get("changes",["{}"])[0])
                try:
                    changes = _json.loads(raw)
                    grid    = load_day_grid(iso)
                    for person, slots in changes.items():
                        grid.setdefault(person, {}).update(slots)
                    save_day_grid(iso, grid)
                    # Also propagate to the weekly template so day lists update immediately
                    try:
                        _weekday = date.fromisoformat(iso).strftime("%A")
                        save_day_template(_weekday, {"weekday": _weekday, "grid": grid})
                    except Exception:
                        pass
                except Exception as e:
                    print("[grid-cell-save error]", str(e))
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/rol-cell-save":
                import json as _json
                _day = clean_text(data.get("day", [""])[0])
                _ts  = clean_text(data.get("ts",  [""])[0])
                _val = clean_text(data.get("value",[""])[0])
                if _day and _ts:
                    try:
                        import json as _rj
                        from pathlib import Path as _rp
                        _tp = _rp(f"data/day_templates/{_day}.json")
                        _td = _rj.loads(_tp.read_text("utf-8")) if _tp.exists() else {"weekday": _day, "grid": {}}
                        _td.setdefault("grid", {}).setdefault("Mom", {})[_ts] = _val
                        save_day_template(_day, _td)
                    except Exception as _e:
                        print("[rol-cell-save error]", str(_e))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/grid-publish":
                from datetime import datetime as _dt
                from render_schedule_support import get_eastern_now
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                publish_day_grid(iso)
                try:
                    now_et = get_eastern_now()
                    ts = now_et.strftime("%B %d at %-I:%M %p")
                except Exception:
                    ts = _dt.now().strftime("%B %d at %I:%M %p")
                import json as _json
                payload = _json.dumps({"ok": True, "published_at": ts}).encode()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(payload)
                except BrokenPipeError: pass
                return

            elif path == "/grid-reset":
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                try:
                    from render_daily_plan import _get_plan_column_people
                    d       = date.fromisoformat(iso)
                    weekday = d.strftime("%A")
                    people  = _get_plan_column_people() or list(CHILDREN)
                    people_with_mom = ["Mom"] + [p for p in people if p != "Mom"]
                    from render_daily_plan import seed_day_grid
                    grid = seed_day_grid(iso, weekday, people_with_mom)
                    save_day_grid(iso, grid)
                except Exception as e:
                    print("[grid-reset error]", str(e))
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-ai-suggest":
                import json as _json, urllib.request as _req
                iso      = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                mode     = clean_text(data.get("mode",["ask"])[0])
                question = clean_text(data.get("question",[""])[0])
                # Load API key from settings
                settings_data = load_app_settings()
                api_key = settings_data.get("family_constraints",{}).get("anthropic_api_key","").strip()
                if not api_key:
                    self.send_response(400)
                    self.send_header("Content-Type","text/plain")
                    self.end_headers()
                    try: self.wfile.write(b"No API key set. Go to Settings -> Family & AI to add your Anthropic API key.")
                    except BrokenPipeError: pass
                    return
                try:
                    d = date.fromisoformat(iso)
                    weekday    = d.strftime("%A")
                    date_label = d.strftime("%B %d, %Y")
                except Exception:
                    weekday = date_label = iso
                context = build_context_packet(iso, weekday, date_label)
                # Build the user message based on mode
                if mode == "review":
                    user_msg = (
                        "Please review today's full schedule. Look at the family grid, each child's assignments, "
                        "and the current plan. Flag: (1) any time where James has no supervisor, "
                        "(2) any child who is overloaded or has unexplained gaps, "
                        "(3) any conflicts with calendar events, "
                        "(4) any sequencing problems. Be specific about time slots. "
                        "Format as a short bulleted list, then a 1-2 sentence summary."
                    )
                elif mode == "generate":
                    extra = f" Additional constraints for today: {question}" if question else ""
                    user_msg = (
                        f"Build an optimal schedule for today ({weekday}).{extra} "
                        "Show a time-slot schedule for each person. Format it as a simple table: "
                        "Time | Mom | JP | Joseph | Michael | James. "
                        "Make sure James always has a supervisor. "
                        "Fit school, chores, meals, and any calendar events. "
                        "Keep it practical and achievable."
                    )
                else:
                    user_msg = question if question else "What should I be thinking about for today's schedule?"
                # Call Anthropic API (non-streaming for simplicity — streams as one chunk)
                payload = _json.dumps({
                    "model":      "claude-sonnet-4-20250514",
                    "max_tokens": 1200,
                    "system":     context,
                    "messages":   [{"role":"user","content":user_msg}]
                }).encode()
                req = _req.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type":      "application/json",
                        "x-api-key":         api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST"
                )
                try:
                    with _req.urlopen(req, timeout=45) as resp:
                        result = _json.loads(resp.read().decode())
                    text = result.get("content",[{}])[0].get("text","(No response)")
                except Exception as e:
                    text = f"API error: {e}"
                self.send_response(200)
                self.send_header("Content-Type","text/plain; charset=utf-8")
                self.end_headers()
                try: self.wfile.write(text.encode("utf-8"))
                except BrokenPipeError: pass
                return

            elif path == "/memory-book-save":
                text     = clean_text(data.get("text",[""])[0])
                date_iso = clean_text(data.get("date",[""])[0])
                if text:
                    add_memory_entry(text, date_iso)
                self.send_response(200)
                self.send_header("Content-Type","text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
                return

            elif path == "/memory-book-delete":
                entry_id = clean_text(data.get("id",[""])[0])
                delete_memory_entry(entry_id)
                self.send_response(200)
                self.send_header("Content-Type","text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
                return

            elif path == "/lucy-tts":
                # OpenAI TTS — fetches MP3 from OpenAI and streams it back
                import os as _os, json as _json, ssl as _ssl, socket as _sock
                text  = clean_text(data.get("text",[""])[0]).strip()
                voice = clean_text(data.get("voice",["nova"])[0]).strip() or "nova"
                if voice not in ("alloy","echo","fable","onyx","nova","shimmer","coral","sage","ash"):
                    voice = "nova"
                oai_key = _os.environ.get("OPENAI_API_KEY","").strip()
                if not oai_key or not text:
                    self.send_response(400)
                    self.send_header("Content-Type","text/plain")
                    self.end_headers()
                    try: self.wfile.write(b"Missing API key or text")
                    except BrokenPipeError: pass
                    return
                # Use http.client directly to avoid latin-1 header encoding issues
                import http.client as _hc
                text = text[:4096]
                body = _json.dumps({"model":"tts-1","voice":voice,
                                    "input":text,"response_format":"mp3"}).encode("utf-8")
                ctx = _ssl.create_default_context()
                try:
                    conn = _hc.HTTPSConnection("api.openai.com", context=ctx, timeout=30)
                    conn.request("POST", "/v1/audio/speech", body=body, headers={
                        "Authorization": "Bearer " + oai_key,
                        "Content-Type": "application/json",
                        "Content-Length": str(len(body)),
                    })
                    resp = conn.getresponse()
                    if resp.status == 200:
                        self.send_response(200)
                        self.send_header("Content-Type","audio/mpeg")
                        self.send_header("Cache-Control","no-store")
                        self.end_headers()
                        while True:
                            chunk = resp.read(4096)
                            if not chunk: break
                            try: self.wfile.write(chunk)
                            except BrokenPipeError: break
                    else:
                        err_body = resp.read(512)
                        conn.close()
                        status_code = resp.status
                        if status_code == 429:
                            msg = b"OpenAI quota exceeded. Add billing at platform.openai.com/account/billing."
                        elif status_code == 401:
                            msg = b"OpenAI API key is invalid. Check Settings."
                        else:
                            msg = b"OpenAI TTS error " + str(status_code).encode()
                        try:
                            self.send_response(502)
                            self.send_header("Content-Type","text/plain")
                            self.end_headers()
                            self.wfile.write(msg)
                        except BrokenPipeError: pass
                        return
                    conn.close()
                except BrokenPipeError:
                    pass
                except Exception as e:
                    try:
                        self.send_response(500)
                        self.send_header("Content-Type","text/plain")
                        self.end_headers()
                        self.wfile.write(str(e).encode("utf-8","replace"))
                    except Exception: pass
                return

            elif path == "/lucy-rule-save":
                import json as _json
                action    = clean_text(data.get("action",[""])[0]).strip()
                rule_text = clean_text(data.get("rule",[""])[0]).strip()
                if rule_text and action in ("add", "remove"):
                    _s = load_app_settings()
                    fc = _s.setdefault("family_constraints", {})
                    rules = fc.get("lucy_rules", [])
                    if not isinstance(rules, list):
                        rules = []
                    if action == "add" and rule_text not in rules:
                        rules.append(rule_text)
                    elif action == "remove":
                        rules = [r for r in rules if r != rule_text]
                    fc["lucy_rules"] = rules
                    _s["family_constraints"] = fc
                    save_app_settings(_s)
                self.send_response(200)
                self.send_header("Content-Type","text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
                return

            elif path == "/lucy-chat":
                import json as _json, urllib.request as _req
                from data_helpers import (
                    load_lucy_history, append_lucy_messages, LUCY_CONTEXT_MAX
                )
                from datetime import datetime as _dt
                from web_fetch import extract_urls, fetch_urls, build_url_context
                iso        = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                capacity   = clean_text(data.get("capacity",[""])[0])
                message    = clean_text(data.get("message",[""])[0])
                image_b64  = data.get("image_b64",[""])[0].strip()
                image_type = clean_text(data.get("image_type",["image/jpeg"])[0]) or "image/jpeg"
                settings_data = load_app_settings()
                api_key = (settings_data.get("family_constraints",{}).get("anthropic_api_key","")
                           or settings_data.get("anthropic_api_key","")).strip()
                if not api_key:
                    self.send_response(400)
                    self.send_header("Content-Type","text/plain")
                    self.end_headers()
                    try: self.wfile.write(b"No API key. Add your Anthropic key in Settings \u2192 Family & AI.")
                    except BrokenPipeError: pass
                    return
                # Use Eastern datetime (TZ set to America/New_York at server startup)
                _now_et    = datetime.now()
                iso        = _now_et.date().isoformat()
                weekday    = _now_et.strftime("%A")
                date_label = _now_et.strftime("%B %d, %Y")
                _time_et   = _now_et.strftime("%-I:%M %p")
                lucy_context = build_lucy_context(iso, weekday, date_label, capacity) + _UNDO_BLOCK
                begin_companion_turn("lucy")
                # ── Fetch any URLs in the user's message ──────────────────────
                _urls = extract_urls(message)
                if _urls:
                    _fetched = fetch_urls(_urls)
                    _web_ctx = build_url_context(_fetched)
                    if _web_ctx:
                        lucy_context += _web_ctx
                # ── Save user message to server-side history ──────────────────
                ts_now = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                append_lucy_messages([{"role": "user", "content": message, "ts": ts_now}])
                # ── Build Claude message list from server history ─────────────
                server_history = load_lucy_history()
                messages = []
                for h in server_history[-LUCY_CONTEXT_MAX:]:
                    role    = h.get("role","user")
                    content = h.get("content","")
                    if role in ("user","assistant") and content:
                        messages.append({"role": role, "content": content})
                # Ensure conversation ends with user message
                if not messages or messages[-1].get("role") != "user":
                    messages.append({"role": "user", "content": message or "(image attached)"})
                # If an image was attached, convert the last user message to a vision block
                if image_b64 and len(image_b64) > 10:
                    last_text = messages[-1].get("content","") if messages else (message or "")
                    messages[-1] = {"role": "user", "content": [
                        {"type": "image", "source": {
                            "type": "base64",
                            "media_type": image_type,
                            "data": image_b64
                        }},
                        {"type": "text", "text": last_text or "What do you see in this image?"}
                    ]}
                # Stamp current date+time into the last user message so stale history can't override it
                _date_stamp = f"[Today: {weekday}, {date_label}, {_time_et} ET]"
                if messages and messages[-1].get("role") == "user":
                    _lc = messages[-1]["content"]
                    if isinstance(_lc, str):
                        messages[-1]["content"] = f"{_date_stamp}\n{_lc}"
                    elif isinstance(_lc, list):
                        for _part in _lc:
                            if isinstance(_part, dict) and _part.get("type") == "text":
                                _part["text"] = f"{_date_stamp}\n{_part['text']}"
                                break
                payload = _json.dumps({
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "system":     lucy_context + _AI_GUARDRAILS,
                    "messages":   messages,
                }).encode()
                req = _req.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type":      "application/json",
                        "x-api-key":         api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST"
                )
                try:
                    with _req.urlopen(req, timeout=45) as resp:
                        result = _json.loads(resp.read().decode())
                    text = result.get("content",[{}])[0].get("text","(No response)")
                except Exception as e:
                    text = f"I ran into an issue: {e}"
                # ── Parse and execute <plan_update> action tags ──────────────
                import re as _re
                _plan_markers = ""
                _plan_rx = _re.compile(
                    r'<plan_update\b([^>]+)>([\s\S]*?)</plan_update>',
                    _re.IGNORECASE
                )
                def _attr(attrs, name):
                    m2 = _re.search(r'\b' + name + r'\s*=\s*["\']([^"\']*)["\']', attrs, _re.I)
                    return m2.group(1).strip() if m2 else ""

                # ── Agentic query loop: <get_tasks> lets Lucy see current data ─
                _query_rx = _re.compile(
                    r'<get_tasks\b([^/>/]*?)(?:/>|>.*?</get_tasks>)',
                    _re.IGNORECASE | _re.DOTALL
                )
                _query_matches = list(_query_rx.finditer(text))
                if _query_matches:
                    from daily_schedule_engine import boys_task_snapshot as _bts
                    _task_parts = []
                    for _qm in _query_matches:
                        _qchild = _attr(_qm.group(1), "child")
                        _qdate  = _attr(_qm.group(1), "date") or iso
                        if not _qchild:
                            continue
                        try:
                            _snap   = _bts(_qdate)
                            _cdata  = _snap["children"].get(_qchild)
                            if not _cdata or "error" in _cdata:
                                _task_parts.append(f"[No task data found for {_qchild} on {_qdate}]")
                                continue
                            _ql = [f"CURRENT TASK STATE — {_qchild} on {_qdate}",
                                   f"  Summary: {_cdata['done']}/{_cdata['total']} complete, {_cdata['pending']} remaining"]
                            for _ci in _cdata.get("carryover", []):
                                _ql.append(f"  [Carryover] {'✓' if _ci['done'] else '○'} {_ci['text']}")
                            for _sb in _cdata.get("school", []):
                                _ql.append(f"  [School — {_sb['subject']}]")
                                for _si in _sb["items"]:
                                    _ql.append(f"    {'✓' if _si['done'] else '○'} {_si['text']}")
                            for _ch in _cdata.get("chores", []):
                                _ql.append(f"  [Chore] {'✓' if _ch['done'] else '○'} {_ch['text']}")
                            for _mt in _cdata.get("manual", []):
                                _ql.append(f"  [Task/{_mt['priority']}] {'✓' if _mt['done'] else '○'} {_mt['text']}")
                            _task_parts.append("\n".join(_ql))
                        except Exception as _qe:
                            _task_parts.append(f"[Error fetching {_qchild}: {_qe}]")
                    if _task_parts:
                        _inject = (
                            "[SYSTEM: You requested current task data. Here it is — now use it to "
                            "make informed edits with <plan_update>.]\n\n"
                            + "\n\n".join(_task_parts)
                        )
                        _msgs2 = messages + [
                            {"role": "assistant", "content": text},
                            {"role": "user",      "content": _inject},
                        ]
                        _pay2 = _json.dumps({
                            "model":      "claude-haiku-4-5-20251001",
                            "max_tokens": 1500,
                            "system":     lucy_context + _AI_GUARDRAILS,
                            "messages":   _msgs2,
                        }).encode()
                        try:
                            _req2 = _req.Request(
                                "https://api.anthropic.com/v1/messages",
                                data=_pay2,
                                headers={"Content-Type": "application/json",
                                         "x-api-key": api_key,
                                         "anthropic-version": "2023-06-01"},
                                method="POST"
                            )
                            with _req.urlopen(_req2, timeout=45) as _r2:
                                text = _json.loads(_r2.read().decode()).get("content",[{}])[0].get("text", text)
                        except Exception:
                            pass  # keep original response if second call fails

                for _m in _plan_rx.finditer(text):
                    _child = _attr(_m.group(1), "child")
                    _date  = _attr(_m.group(1), "date")
                    _body  = _m.group(2)
                    _new_tasks = [ln.strip() for ln in _body.splitlines() if ln.strip()]
                    if _child and _date and _new_tasks:
                        try:
                            _all = load_manual_tasks()
                            # Deactivate existing lucy-sourced tasks for this child+date
                            for _t in _all:
                                if (_t.get("source") == "lucy"
                                        and _t.get("assigned_to") == _child
                                        and _t.get("due_date") == _date):
                                    _t["status"] = "inactive"
                            # Build chore-text guard to avoid duplicating existing chores
                            _chore_guard: set = set()
                            try:
                                from daily_schedule_engine import weekday_chores_for_child as _wcc
                                import datetime as _dt2
                                _wday2 = _dt2.date.fromisoformat(_date).strftime('%A')
                                _chore_guard = set(str(_c).strip() for _c in _wcc(_child, _wday2) if str(_c).strip())
                            except Exception:
                                pass
                            # Append new tasks (skip any text already covered by chore system)
                            for _task_text in _new_tasks:
                                if _task_text in _chore_guard:
                                    continue
                                _all.append({
                                    "text": _task_text,
                                    "assigned_to": _child,
                                    "due_date": _date,
                                    "priority": "MEDIUM",
                                    "status": "active",
                                    "source": "lucy",
                                    "recurring": False,
                                })
                            save_manual_tasks(_all)
                            _plan_markers += f"\n[PLAN_UPDATED:{_child}:{_date}]"
                        except Exception as _pe:
                            _plan_markers += f"\n(Plan save error: {_pe})"
                # ── Parse and execute <carryover_update> action tags ─────────
                _carryover_rx = _re.compile(
                    r'<carryover_update\b([^>]*?)(?:/>|>([\s\S]*?)</carryover_update>)',
                    _re.IGNORECASE
                )
                _carryover_markers = ""
                for _cm in _carryover_rx.finditer(text):
                    _cattrs = _cm.group(1) or ""
                    _cbody  = (_cm.group(2) or "").strip()
                    _cchild = _attr(_cattrs, "child")
                    _cdate  = _attr(_cattrs, "date") or iso
                    if not _cchild:
                        continue
                    try:
                        from daily_schedule_engine import dismiss_carryover_items
                        from datetime import date as _date_cls
                        _target = _date_cls.fromisoformat(_cdate)
                        # If body has items, those are the ones to KEEP; else dismiss all
                        _keep = [ln.strip() for ln in _cbody.splitlines() if ln.strip()] if _cbody else None
                        _n = dismiss_carryover_items(_cchild, _target, _keep)
                        _carryover_markers += f"\n[CARRYOVER_UPDATED:{_cchild}:{_cdate}:{_n}]"
                    except Exception as _ce:
                        _carryover_markers += f"\n(Carryover update error: {_ce})"
                # ── Parse and execute <schedule_update> action tags ──────────
                _sched_rx = _re.compile(
                    r'<schedule_update\b([^>]*)>([\s\S]*?)</schedule_update>',
                    _re.IGNORECASE
                )
                _sched_markers = ""
                for _sm in _sched_rx.finditer(text):
                    _sattrs = _sm.group(1)
                    _sbody  = _sm.group(2)
                    _sdate_m = _re.search(r'date=["\']([^"\']+)["\']', _sattrs, _re.I)
                    _sdate = _sdate_m.group(1).strip() if _sdate_m else iso
                    # Parse lines like "2:00 PM: Activity text"
                    _slots = {}
                    for _line in _sbody.strip().splitlines():
                        _lm = _re.match(
                            r'^(\d+:\d+\s*(?:AM|PM))\s*:\s*(.+)$',
                            _line.strip(), _re.IGNORECASE
                        )
                        if _lm:
                            _slots[_lm.group(1).strip()] = _lm.group(2).strip()
                    if not _slots:
                        continue
                    try:
                        from render_daily_plan import get_or_seed_grid
                        from datetime import date as _date_cls2
                        _sd = _date_cls2.fromisoformat(_sdate)
                        _swd = _sd.strftime("%A")
                        _speople = load_app_settings().get("plan_columns", [])
                        if not _speople:
                            from daily_schedule_engine import CHILDREN as _SC
                            _speople = list(_SC)
                        _speople_all = ["Mom"] + [p for p in _speople if p != "Mom"]
                        _sgrid = get_or_seed_grid(_sdate, _swd, _speople_all)
                        _sperson_attr = _attr(_sattrs, "person").strip()
                        _stargets = ([_sperson_attr] if _sperson_attr and _sperson_attr in _speople_all
                                     else _speople_all)
                        for _sp in _stargets:
                            if _sp not in _sgrid:
                                _sgrid[_sp] = {}
                            for _st, _sv in _slots.items():
                                _sgrid[_sp][_st] = _sv
                        save_day_grid(_sdate, _sgrid)
                        _who_label = _sperson_attr or "all"
                        _sched_markers += f"\n[SCHEDULE_UPDATED:{_sdate}:{len(_slots)}:{_who_label}]"
                    except Exception as _se:
                        _sched_markers += f"\n(Schedule update error: {_se})"
                # ── Parse <cycle_log> action tags ────────────────────────────
                _cycl_rx = _re.compile(
                    r'<cycle_log\b([^>]*)(?:/>|>([\s\S]*?)</cycle_log>)',
                    _re.IGNORECASE
                )
                _cycl_markers = ""
                for _cyc in _cycl_rx.finditer(text):
                    _cycattrs = _cyc.group(1) or ""
                    _caction  = _attr(_cycattrs, "action").lower() or "add"
                    _cycdate  = _attr(_cycattrs, "date") or iso
                    _cycnote  = _attr(_cycattrs, "note")
                    try:
                        from datetime import date as _date_cls3
                        _date_cls3.fromisoformat(_cycdate)
                        import json as _json2
                        _CYCLE_LOG = "data/cycle_log.json"
                        try:
                            with open(_CYCLE_LOG) as _clf:
                                _clog = _json2.load(_clf)
                        except Exception:
                            _clog = []
                        if _caction == "remove":
                            _clog = [e for e in _clog if e.get("day1") != _cycdate]
                        else:
                            _clog = [e for e in _clog if e.get("day1") != _cycdate]
                            _clog.append({"day1": _cycdate, "note": _cycnote, "logged": iso})
                        _clog.sort(key=lambda e: e.get("day1", ""))
                        safe_save_json(_CYCLE_LOG, _clog)
                        _cycl_markers += f"\n[CYCLE_LOGGED:{_cycdate}:{_caction}]"
                    except Exception as _cyce:
                        _cycl_markers += f"\n(Cycle log error: {_cyce})"
                # ── Parse <settings_update> action tags ───────────────────────
                _su_rx = _re.compile(
                    r'<settings_update\b([^>]*)>([\s\S]*?)</settings_update>',
                    _re.IGNORECASE
                )
                _su_markers = ""
                for _su in _su_rx.finditer(text):
                    _suattrs = _su.group(1) or ""
                    _sufield = _attr(_suattrs, "field").strip()
                    _suval   = _su.group(2).strip()
                    if not _sufield:
                        continue
                    try:
                        _susettings = load_app_settings()
                        _suparts = _sufield.split(".", 1)
                        if (len(_suparts) == 2 and _suparts[0] in _susettings
                                and isinstance(_susettings[_suparts[0]], dict)):
                            _susettings[_suparts[0]][_suparts[1]] = _suval
                        elif _sufield in _susettings:
                            _susettings[_sufield] = _suval
                        else:
                            _su_markers += f"\n(Settings update: unknown field '{_sufield}')"
                            continue
                        from render_settings import save_app_settings as _sas
                        _sas(_susettings)
                        _su_markers += f"\n[SETTINGS_UPDATED:{_sufield}]"
                    except Exception as _sue:
                        _su_markers += f"\n(Settings error: {_sue})"
                # ── Parse <event_add> action tags ─────────────────────────────
                _ev_rx = _re.compile(
                    r'<event_add\b([^>]*)(?:/>|>([\s\S]*?)</event_add>)',
                    _re.IGNORECASE
                )
                _ev_markers = ""
                for _ev in _ev_rx.finditer(text):
                    _evattrs = _ev.group(1) or ""
                    _evbody  = (_ev.group(2) or "").strip()
                    _evtitle = _attr(_evattrs, "title")
                    _evdate  = _attr(_evattrs, "date") or iso
                    _evtime  = _attr(_evattrs, "time") or ""
                    _evend   = _attr(_evattrs, "end_time") or ""
                    _evwho   = _attr(_evattrs, "who") or "Mom"
                    _evnote  = _attr(_evattrs, "note") or _evbody
                    _evrec   = _attr(_evattrs, "recurring") or "none"
                    if not _evtitle:
                        continue
                    try:
                        import uuid as _uuid2, json as _json3
                        _EVENTS_FILE = "data/events.json"
                        try:
                            with open(_EVENTS_FILE) as _ef:
                                _edata = _json3.load(_ef)
                        except Exception:
                            _edata = {"version": 1, "updated_at": iso, "data": []}
                        _who_list = [w.strip() for w in _evwho.split(",") if w.strip()]
                        _rec_type = "none" if _evrec in ("no", "none", "") else _evrec
                        _new_ev = {
                            "id": "evt_" + _uuid2.uuid4().hex[:8],
                            "title": _evtitle,
                            "assigned_to": _who_list,
                            "start_date": _evdate,
                            "end_date": _evdate,
                            "start_time": _evtime,
                            "end_time": _evend,
                            "recurrence": {"type": _rec_type},
                            "notifications": {
                                "show_on_dashboard": True,
                                "show_on_daily_page": True,
                                "show_in_looking_ahead": True,
                                "lead_days": 1,
                            },
                            "prep": {"lead_days": 0},
                            "notes": _evnote,
                            "subtasks": [],
                            "archived": False,
                        }
                        _edata.setdefault("data", []).append(_new_ev)
                        _edata["updated_at"] = iso
                        safe_save_json(_EVENTS_FILE, _edata)
                        _ev_markers += f"\n[EVENT_ADDED:{_evtitle}:{_evdate}]"
                    except Exception as _eve:
                        _ev_markers += f"\n(Event add error: {_eve})"
                # ── Parse <note_add> action tags ──────────────────────────────
                _note_rx = _re.compile(
                    r'<note_add\b[^>]*>([\s\S]*?)</note_add>',
                    _re.IGNORECASE
                )
                _note_markers = ""
                for _na in _note_rx.finditer(text):
                    _natext = _na.group(1).strip()
                    if not _natext:
                        continue
                    try:
                        import uuid as _uuid3
                        _notes = load_mom_notes()
                        if isinstance(_notes, dict):
                            _notes = _notes.get("data", [])
                        _notes.append({
                            "id": "note_" + _uuid3.uuid4().hex[:6],
                            "text": _natext,
                            "created_at": iso,
                            "status": "active",
                            "tags": [],
                            "source": "lucy",
                            "archived_at": None,
                        })
                        save_mom_notes(_notes)
                        _note_markers += f"\n[NOTE_ADDED:{iso}]"
                    except Exception as _nae:
                        _note_markers += f"\n(Note add error: {_nae})"
                # ── Parse <memory_add> action tags ────────────────────────────
                _mem_rx = _re.compile(
                    r'<memory_add\b([^>]*)>([\s\S]*?)</memory_add>',
                    _re.IGNORECASE
                )
                _mem_markers = ""
                for _ma in _mem_rx.finditer(text):
                    _maattrs  = _ma.group(1) or ""
                    _matext   = _ma.group(2).strip()
                    _madate   = _attr(_maattrs, "date") or iso
                    _maperson = _attr(_maattrs, "person") or ""
                    if not _matext:
                        continue
                    try:
                        import uuid as _uuid4, json as _json4
                        _MB_FILE = "data/memory_book.json"
                        try:
                            with open(_MB_FILE) as _mbf:
                                _mbdata = _json4.load(_mbf)
                        except Exception:
                            _mbdata = {"entries": []}
                        _mbdata.setdefault("entries", [])
                        _mbdata["entries"].append({
                            "id": _uuid4.uuid4().hex[:8],
                            "date": _madate,
                            "text": _matext,
                            "person": _maperson,
                            "source": "lucy",
                            "created_at": iso,
                        })
                        safe_save_json(_MB_FILE, _mbdata)
                        _mem_markers += f"\n[MEMORY_ADDED:{_madate}]"
                    except Exception as _mae:
                        _mem_markers += f"\n(Memory add error: {_mae})"
                # ── Parse <friend_add> action tags ────────────────────────
                _fr_rx = _re.compile(
                    r'<friend_add\b([^>]*)>([\s\S]*?)</friend_add>',
                    _re.IGNORECASE
                )
                _fr_markers = ""
                for _fr in _fr_rx.finditer(text):
                    _frattrs = _fr.group(1) or ""
                    _frbody  = _fr.group(2)
                    _frname  = _attr(_frattrs, "family_name") or _attr(_frattrs, "name")
                    if not _frname:
                        continue
                    try:
                        from render_friends import load_friends, save_friends
                        import uuid as _uuid5
                        _frnds = load_friends()
                        _fr_members = []
                        _fr_allergies = []
                        _fr_favorites = []
                        _fr_plans = []
                        for _fl in _frbody.strip().splitlines():
                            _fl = _fl.strip()
                            if not _fl:
                                continue
                            _fll = _fl.lower()
                            if _fll.startswith("member:"):
                                _fparts = _fl.split(":", 1)[1].split("|")
                                _fparts = [p.strip() for p in _fparts]
                                _fmn = _fparts[0] if _fparts else ""
                                _fmr = _fparts[1] if len(_fparts) > 1 else ""
                                _fmb = _fparts[2] if len(_fparts) > 2 else ""
                                if _fmn:
                                    _fr_members.append({"name": _fmn, "role": _fmr, "birthday": _fmb})
                            elif _fll.startswith(("food_allergy:", "allergy:")):
                                _fr_allergies.append(_fl.split(":", 1)[1].strip())
                            elif _fll.startswith("favorite:"):
                                _fr_favorites.append(_fl.split(":", 1)[1].strip())
                            elif _fll.startswith("plan:"):
                                _fr_plans.append({"text": _fl.split(":", 1)[1].strip(), "done": False})
                        _fr_updated = False
                        for _fe in _frnds:
                            if _fe.get("family_name", "").lower() == _frname.lower():
                                if _fr_members:
                                    _fe.setdefault("members", []).extend(_fr_members)
                                if _fr_allergies:
                                    _fe.setdefault("food_allergies", []).extend(_fr_allergies)
                                if _fr_favorites:
                                    _fe.setdefault("favorite_things", []).extend(_fr_favorites)
                                if _fr_plans:
                                    _fe.setdefault("plans", []).extend(_fr_plans)
                                if _attr(_frattrs, "address"):
                                    _fe["address"] = _attr(_frattrs, "address")
                                if _attr(_frattrs, "note"):
                                    _fe["notes"] = _attr(_frattrs, "note")
                                _fr_updated = True
                                break
                        if not _fr_updated:
                            _frnds.append({
                                "id": "fam_" + _uuid5.uuid4().hex[:8],
                                "family_name": _frname,
                                "address": _attr(_frattrs, "address") or "",
                                "notes": _attr(_frattrs, "note") or "",
                                "members": _fr_members,
                                "gift_ideas": [],
                                "food_allergies": _fr_allergies,
                                "favorite_things": _fr_favorites,
                                "plans": _fr_plans,
                            })
                        save_friends(_frnds)
                        _fr_markers += f"\n[FRIEND_ADDED:{_frname}]"
                    except Exception as _fre2:
                        _fr_markers += f"\n(Friend error: {_fre2})"
                # ── Parse <meal_plan_update> action tags ───────────────────────
                _mp_rx = _re.compile(
                    r'<meal_plan_update\b([^>]*)>([\s\S]*?)</meal_plan_update>',
                    _re.IGNORECASE
                )
                _mp_markers = ""
                _MP_DAYS  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                _MP_MEALS = ["breakfast","lunch","dinner","dessert","snacks","dad_lunch"]
                for _mp in _mp_rx.finditer(text):
                    _mpattrs = _mp.group(1) or ""
                    _mpbody  = _mp.group(2)
                    _mpweek  = _attr(_mpattrs, "week").strip()
                    if not _mpweek:
                        from datetime import date as _dc4
                        _today2 = _dc4.fromisoformat(iso)
                        _mpweek = _today2.strftime("%Y-W%W")
                    try:
                        import json as _json5, os as _os5
                        _MP_DIR  = "data/meal_plan"
                        _os5.makedirs(_MP_DIR, exist_ok=True)
                        _MP_FILE = f"{_MP_DIR}/{_mpweek}.json"
                        try:
                            with open(_MP_FILE) as _mpf:
                                _mpdata = _json5.load(_mpf)
                        except Exception:
                            _mpdata = {"week": _mpweek, "generated": False, "days": {
                                d: {"breakfast":"","lunch":"","dinner":"","dessert":"","snacks":"","dad_lunch":""}
                                for d in _MP_DAYS
                            }}
                        _mpdata.setdefault("days", {})
                        _mp_n = 0
                        for _ml in _mpbody.strip().splitlines():
                            _ml = _ml.strip()
                            _mp_m = _re.match(
                                r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)'
                                r'\s+(\w+)\s*:\s*(.+)$', _ml, _re.IGNORECASE
                            )
                            if _mp_m:
                                _mpday  = _mp_m.group(1).capitalize()
                                _mpmeal = _mp_m.group(2).lower()
                                _mpval  = _mp_m.group(3).strip()
                                if _mpmeal in _MP_MEALS:
                                    _mpdata["days"].setdefault(_mpday, {})
                                    _mpdata["days"][_mpday][_mpmeal] = _mpval
                                    _mp_n += 1
                        if _mp_n > 0:
                            safe_save_json(_MP_FILE, _mpdata)
                            _mp_markers += f"\n[MEAL_UPDATED:{_mpweek}:{_mp_n}]"
                    except Exception as _mpe:
                        _mp_markers += f"\n(Meal plan error: {_mpe})"
                # ── Parse <prayer_add> action tags ─────────────────────────────
                _pr_rx = _re.compile(
                    r'<prayer_add\b([^>]*)(?:/>|>([\s\S]*?)</prayer_add>)',
                    _re.IGNORECASE
                )
                _pr_markers = ""
                for _pr in _pr_rx.finditer(text):
                    _prattrs = _pr.group(1) or ""
                    _prbody  = (_pr.group(2) or "").strip()
                    _prtitle = _attr(_prattrs, "title")
                    _prdesc  = _attr(_prattrs, "description") or _prbody
                    if not _prtitle:
                        continue
                    try:
                        import uuid as _uuid6, json as _json6
                        _PRAYER_FILE = "data/prayer/intentions.json"
                        try:
                            with open(_PRAYER_FILE) as _prf:
                                _prdata = _json6.load(_prf)
                        except Exception:
                            _prdata = []
                        _prdata.append({
                            "id": _uuid6.uuid4().hex[:8],
                            "title": _prtitle,
                            "description": _prdesc,
                            "photo": "",
                            "created": iso,
                            "active": True,
                            "answered": False,
                            "prayer_log": [],
                        })
                        safe_save_json(_PRAYER_FILE, _prdata)
                        _pr_markers += f"\n[PRAYER_ADDED:{_prtitle}]"
                    except Exception as _pre:
                        _pr_markers += f"\n(Prayer error: {_pre})"
                # ── Parse <recipe_add> action tags ─────────────────────────────
                _recx_rx = _re.compile(
                    r'<recipe_add\b([^>]*)>([\s\S]*?)</recipe_add>',
                    _re.IGNORECASE
                )
                _recx_markers = ""
                for _recx in _recx_rx.finditer(text):
                    _rxattrs = _recx.group(1) or ""
                    _rxbody  = _recx.group(2).strip()
                    _rxname  = _attr(_rxattrs, "name")
                    if not _rxname:
                        continue
                    try:
                        import uuid as _uuid7, json as _json7
                        _REC_FILE = "data/recipes.json"
                        try:
                            with open(_REC_FILE) as _recf:
                                _rxdata = _json7.load(_recf)
                        except Exception:
                            _rxdata = []
                        _rxdata.append({
                            "id": "r" + _uuid7.uuid4().hex[:6],
                            "name": _rxname,
                            "ingredients": _attr(_rxattrs, "ingredients") or "",
                            "instructions": _rxbody,
                            "tags": [t.strip() for t in (_attr(_rxattrs, "tags") or "").split(",") if t.strip()],
                            "source": "lucy",
                            "notes": _attr(_rxattrs, "notes") or "",
                        })
                        safe_save_json(_REC_FILE, _rxdata)
                        _recx_markers += f"\n[RECIPE_ADDED:{_rxname}]"
                    except Exception as _rxe:
                        _recx_markers += f"\n(Recipe error: {_rxe})"
                # ── Parse <profile_update> action tags ────────────────────
                _prof_rx = _re.compile(
                    r'<profile_update\b([^>]*)>([\s\S]*?)</profile_update>',
                    _re.IGNORECASE
                )
                _prof_markers = ""
                # Mapping person name → (profile_type, slug, profile_url, display_name)
                _PROF_MAP = {
                    "jp":        ("child", "jp",      "/schedule/JP",      "JP"),
                    "john paul": ("child", "jp",      "/schedule/JP",      "JP"),
                    "joseph":    ("child", "joseph",  "/schedule/Joseph",  "Joseph"),
                    "michael":   ("child", "michael", "/schedule/Michael", "Michael"),
                    "james":     ("child", "james",   "/schedule/James",   "James"),
                    "mom":       ("mom",   "mom",     "/mom-profile",      "Mom"),
                    "lauren":    ("mom",   "mom",     "/mom-profile",      "Mom"),
                    "john":      ("john",  "john",    "/john",             "John"),
                    "dad":       ("john",  "john",    "/john",             "Dad"),
                }
                _CHILD_LIST_FIELDS = {
                    "interests", "gift_ideas", "skills_to_learn",
                    "activities_requested", "favorite_foods",
                    "meal_requests", "dream_trips",
                }
                _CHILD_STR_FIELDS  = {"other_notes", "shoe_size"}
                _JOHN_LIST_FIELDS  = {
                    "gift_ideas", "favorite_foods", "favorite_restaurants",
                    "hobbies_interests", "couple_bucket_list",
                }
                _JOHN_STR_FIELDS   = {"love_notes", "other_notes"}
                _MOM_LIST_FIELDS   = {
                    "gift_ideas", "favorite_foods", "favorite_restaurants",
                    "just_for_me", "dream_trips", "bucket_list",
                }
                _MOM_STR_FIELDS    = {"notes_for_john", "other_notes"}
                for _pf in _prof_rx.finditer(text):
                    _pfattrs  = _pf.group(1) or ""
                    _pfval    = _pf.group(2).strip()
                    _pfperson = _attr(_pfattrs, "person").strip().lower()
                    _pffield  = _attr(_pfattrs, "field").strip().lower()
                    _pfaction = _attr(_pfattrs, "action").strip().lower() or "add"
                    if not _pfperson or not _pffield or not _pfval:
                        continue
                    _pft = _PROF_MAP.get(_pfperson)
                    if not _pft:
                        continue
                    _pf_type, _pf_slug, _pf_url, _pf_display = _pft
                    try:
                        if _pf_type == "child":
                            from render_child_profile import load_child_profile, save_child_profile
                            _pfdata = load_child_profile(_pf_slug)
                            if _pffield in _CHILD_LIST_FIELDS:
                                _pflist = _pfdata.get(_pffield, [])
                                if _pfaction == "remove":
                                    _pflist = [x for x in _pflist if x.lower() != _pfval.lower()]
                                elif _pfval not in _pflist:
                                    _pflist.append(_pfval)
                                _pfdata[_pffield] = _pflist
                            elif _pffield in _CHILD_STR_FIELDS:
                                if _pfaction == "set":
                                    _pfdata[_pffield] = _pfval
                                else:
                                    _existing = _pfdata.get(_pffield, "").strip()
                                    _pfdata[_pffield] = (_existing + "\n" + _pfval).strip()
                            else:
                                continue
                            save_child_profile(_pf_slug, _pfdata)
                        elif _pf_type == "john":
                            from render_john import load_john_profile, save_john_profile
                            _pfdata = load_john_profile()
                            if _pffield in _JOHN_LIST_FIELDS:
                                _pflist = _pfdata.get(_pffield, [])
                                if _pfaction == "remove":
                                    _pflist = [x for x in _pflist if x.lower() != _pfval.lower()]
                                elif _pfval not in _pflist:
                                    _pflist.append(_pfval)
                                _pfdata[_pffield] = _pflist
                            elif _pffield in _JOHN_STR_FIELDS:
                                if _pfaction == "set":
                                    _pfdata[_pffield] = _pfval
                                else:
                                    _existing = _pfdata.get(_pffield, "").strip()
                                    _pfdata[_pffield] = (_existing + "\n" + _pfval).strip()
                            else:
                                continue
                            save_john_profile(_pfdata)
                        elif _pf_type == "mom":
                            from render_mom_profile import load_mom_profile, save_mom_profile
                            _pfdata = load_mom_profile()
                            if _pffield in _MOM_LIST_FIELDS:
                                _pflist = _pfdata.get(_pffield, [])
                                if _pfaction == "remove":
                                    _pflist = [x for x in _pflist if x.lower() != _pfval.lower()]
                                elif _pfval not in _pflist:
                                    _pflist.append(_pfval)
                                _pfdata[_pffield] = _pflist
                            elif _pffield in _MOM_STR_FIELDS:
                                if _pfaction == "set":
                                    _pfdata[_pffield] = _pfval
                                else:
                                    _existing = _pfdata.get(_pffield, "").strip()
                                    _pfdata[_pffield] = (_existing + "\n" + _pfval).strip()
                            else:
                                continue
                            save_mom_profile(_pfdata)
                        _prof_label = _pffield.replace("_", " ").title()
                        _prof_markers += f"\n[PROFILE_UPDATED:{_pf_display}:{_pf_url}:{_pf_label}]"
                    except Exception as _pfe:
                        _prof_markers += f"\n(Profile error: {_pfe})"
                # Strip action tags from display text, append markers
                _all_markers = (_plan_markers + _carryover_markers + _sched_markers
                                + _cycl_markers + _su_markers + _ev_markers
                                + _note_markers + _mem_markers
                                + _fr_markers + _mp_markers + _pr_markers + _recx_markers
                                + _prof_markers)
                _display_text = _plan_rx.sub("", text)
                _display_text = _carryover_rx.sub("", _display_text)
                _display_text = _sched_rx.sub("", _display_text)
                _display_text = _cycl_rx.sub("", _display_text)
                _display_text = _su_rx.sub("", _display_text)
                _display_text = _ev_rx.sub("", _display_text)
                _display_text = _note_rx.sub("", _display_text)
                _display_text = _mem_rx.sub("", _display_text)
                _display_text = _fr_rx.sub("", _display_text)
                _display_text = _mp_rx.sub("", _display_text)
                _display_text = _pr_rx.sub("", _display_text)
                _display_text = _recx_rx.sub("", _display_text)
                _display_text = _prof_rx.sub("", _display_text).rstrip()
                if _all_markers:
                    _display_text = _display_text + _all_markers
                else:
                    _display_text = text
                # ── Apply any FRoL edits from this response ───────────────────
                _frol_markers = _apply_frol_updates(text, weekday)
                if _frol_markers:
                    _display_text = _display_text + _frol_markers
                # ── Save assistant response to server-side history ────────────
                _display_text = _strip_hallucinated_tool_use(_display_text)
                _display_text = finish_companion_turn("lucy", _display_text)
                ts_reply = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                append_lucy_messages([{"role": "assistant", "content": _display_text, "ts": ts_reply}])
                self.send_response(200)
                self.send_header("Content-Type","text/plain; charset=utf-8")
                self.end_headers()
                try: self.wfile.write(_display_text.encode("utf-8"))
                except BrokenPipeError: pass
                return

            elif path == "/lucy-clear-history":
                from data_helpers import clear_lucy_history
                clear_lucy_history()
                redirect = "/lucy"

            elif path == "/lorenzo-chat":
                import json as _json, urllib.request as _req, re as _re
                from data_helpers import (
                    load_lorenzo_history, append_lorenzo_messages, LORENZO_CONTEXT_MAX
                )
                from datetime import datetime as _dt
                iso        = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                capacity   = clean_text(data.get("capacity",[""])[0])
                message    = clean_text(data.get("message",[""])[0])
                image_b64  = data.get("image_b64",[""])[0].strip()
                image_type = clean_text(data.get("image_type",["image/jpeg"])[0]) or "image/jpeg"
                settings_data = load_app_settings()
                api_key = (settings_data.get("family_constraints",{}).get("anthropic_api_key","")
                           or settings_data.get("anthropic_api_key","")).strip()
                if not api_key:
                    self.send_response(400)
                    self.send_header("Content-Type","text/plain")
                    self.end_headers()
                    try: self.wfile.write(b"No API key. Add your Anthropic key in Settings.")
                    except BrokenPipeError: pass
                    return
                # Use Eastern datetime (TZ set to America/New_York at server startup)
                _now_et    = datetime.now()
                iso        = _now_et.date().isoformat()
                weekday    = _now_et.strftime("%A")
                date_label = _now_et.strftime("%B %d, %Y")
                _time_et   = _now_et.strftime("%-I:%M %p")
                # Inject capacity override into context if user set it in UI
                lorenzo_context = build_lorenzo_context(iso, weekday, date_label) + _UNDO_BLOCK
                begin_companion_turn("lorenzo")
                if capacity:
                    cap_note = {"high": "OVERRIDE: Lauren says her energy is HIGH today.",
                                "medium": "OVERRIDE: Lauren says her energy is MEDIUM today.",
                                "low": "OVERRIDE: Lauren says her energy is LOW today."}.get(capacity, "")
                    if cap_note:
                        lorenzo_context = cap_note + "\n" + lorenzo_context
                ts_now = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                append_lorenzo_messages([{"role": "user", "content": message, "ts": ts_now}])
                server_history = load_lorenzo_history()
                messages = []
                for h in server_history[-LORENZO_CONTEXT_MAX:]:
                    role    = h.get("role","user")
                    content = h.get("content","")
                    if role in ("user","assistant") and content:
                        messages.append({"role": role, "content": content})
                if not messages or messages[-1].get("role") != "user":
                    messages.append({"role": "user", "content": message or "(image attached)"})
                # Vision: attach image to last user message
                if image_b64 and len(image_b64) > 10:
                    last_text = messages[-1].get("content","") if messages else (message or "")
                    messages[-1] = {"role": "user", "content": [
                        {"type": "image", "source": {
                            "type": "base64",
                            "media_type": image_type,
                            "data": image_b64
                        }},
                        {"type": "text", "text": last_text or "What do you see in this image? Describe it as a chef would."}
                    ]}
                # Stamp current date+time into the last user message so stale history can't override it
                _date_stamp = f"[Today: {weekday}, {date_label}, {_time_et} ET]"
                if messages and messages[-1].get("role") == "user":
                    _lc = messages[-1]["content"]
                    if isinstance(_lc, str):
                        messages[-1]["content"] = f"{_date_stamp}\n{_lc}"
                    elif isinstance(_lc, list):
                        for _part in _lc:
                            if isinstance(_part, dict) and _part.get("type") == "text":
                                _part["text"] = f"{_date_stamp}\n{_part['text']}"
                                break
                payload = _json.dumps({
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "system":     lorenzo_context + _AI_GUARDRAILS,
                    "messages":   messages,
                }).encode()
                req = _req.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type":      "application/json",
                        "x-api-key":         api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST"
                )
                try:
                    with _req.urlopen(req, timeout=45) as resp:
                        result = _json.loads(resp.read().decode())
                    text = result.get("content",[{}])[0].get("text","").strip()
                except Exception as e:
                    text = f"Lorenzo is away from the stove. ({e})"
                # ── Parse [MEAL_UPDATE:Day:slot]meal[/MEAL_UPDATE] and save ──
                _meal_rx = _re.compile(
                    r'\[MEAL_UPDATE:([^:\]]+):([^\]]+)\]([\s\S]*?)\[\/MEAL_UPDATE\]',
                    _re.IGNORECASE
                )
                _meal_updates_found = []
                for _mm in _meal_rx.finditer(text):
                    _mday = _mm.group(1).strip()
                    _mslot = _mm.group(2).strip().lower()
                    _mmeal = _mm.group(3).strip()
                    if _mday and _mslot:
                        _save_ok = False
                        try:
                            _wk = _planning_week_key()
                            _plan = load_meal_plan(_wk)
                            if _mmeal:
                                _plan["days"].setdefault(_mday, {})[_mslot] = _mmeal
                            else:
                                _plan["days"].setdefault(_mday, {}).pop(_mslot, None)
                            _plan["start"] = _plan.get("start") or _wk
                            save_meal_plan(_plan)
                            _save_ok = True
                        except Exception as _se:
                            print(f"[lorenzo MEAL_UPDATE] save failed for {_mday}/{_mslot}: {_se}")
                        # Only count as "saved" if persistence actually succeeded —
                        # otherwise the false-confirmation guard would let lies through.
                        if _save_ok:
                            _meal_updates_found.append((_mday, _mslot))
                # ── Advance planning session for each saved slot ──────────────
                if _meal_updates_found:
                    try:
                        from data_helpers import load_planning_session, advance_planning_session
                        _ps = load_planning_session()
                        if _ps.get("active"):
                            for (_up_day, _up_slot) in _meal_updates_found:
                                advance_planning_session(_up_day, _up_slot)
                    except Exception:
                        pass
                # ── Parse [RECIPE_CARD:add]JSON[/RECIPE_CARD] and auto-save ──
                import json as _rj
                _rc_rx = _re.compile(
                    r'\[RECIPE_CARD:add\]([\s\S]*?)\[\/RECIPE_CARD\]',
                    _re.IGNORECASE
                )
                _recipe_saves_ok = 0
                for _rcm in _rc_rx.finditer(text):
                    _rc_raw = _rcm.group(1).strip()
                    try:
                        _rc_data = _rj.loads(_rc_raw)
                        if isinstance(_rc_data, dict) and _rc_data.get("name"):
                            from data_helpers import add_recipe
                            add_recipe(_rc_data)
                            _recipe_saves_ok += 1
                    except Exception:
                        pass
                # ── Parse <meal_constraint_update> and save to app_settings ──
                _mc_rx = _re.compile(
                    r'<meal_constraint_update>([\s\S]*?)</meal_constraint_update>',
                    _re.IGNORECASE
                )
                _constraint_saves_ok = 0
                for _mcm in _mc_rx.finditer(text):
                    _new_mc = _mcm.group(1).strip()
                    if _new_mc:
                        try:
                            _mcs = load_app_settings()
                            _mcs.setdefault("family_constraints", {})["meal_constraints"] = _new_mc
                            save_app_settings(_mcs)
                            _constraint_saves_ok += 1
                        except Exception:
                            pass
                ts_reply = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                _apply_frol_updates(text, weekday)
                # ── Strip all parsed action tags from the user-facing reply ──
                # (the server has already saved their effects; showing the raw
                # markup just confuses Lauren and looks like "code")
                _visible = text
                _visible = _re.sub(
                    r'\[MEAL_UPDATE:[^:\]]+:[^\]]+\][\s\S]*?\[\/MEAL_UPDATE\]',
                    '', _visible, flags=_re.IGNORECASE)
                _visible = _re.sub(
                    r'\[RECIPE_CARD:add\][\s\S]*?\[\/RECIPE_CARD\]',
                    '', _visible, flags=_re.IGNORECASE)
                # NOTE: do NOT strip [RULE:add]…[/RULE] — the frontend parses
                # those to render a "Save to meal rules" button.
                _visible = _re.sub(
                    r'<meal_constraint_update>[\s\S]*?</meal_constraint_update>',
                    '', _visible, flags=_re.IGNORECASE)
                _visible = _re.sub(
                    r'<frol_update\b[^>]*>[\s\S]*?</frol_update>',
                    '', _visible, flags=_re.IGNORECASE)
                # Also strip hallucinated Anthropic tool-use markup (Lorenzo
                # sometimes reaches for these from his training; they save
                # nothing and look terrible in chat).
                _visible = _re.sub(
                    r'<function_calls>[\s\S]*?</function_calls>',
                    '', _visible, flags=_re.IGNORECASE)
                _visible = _re.sub(
                    r'<invoke\b[^>]*>[\s\S]*?</invoke>',
                    '', _visible, flags=_re.IGNORECASE)
                # Collapse the blank lines left behind
                _visible = _re.sub(r'\n{3,}', '\n\n', _visible).strip()
                # ── False-confirmation guard ──────────────────────────────────
                # If the user asked Lorenzo to save/change something AND he
                # claims "Done!" / "Saved!" but emitted no actual save tag,
                # prepend an honest warning so Lauren knows the save did NOT
                # happen and her work isn't quietly lost.
                try:
                    _user_lc  = (message or "").lower()
                    _reply_lc = _visible.lower()
                    _save_intent_words = (
                        "save", "add ", "update", "change", " set ", "swap",
                        "replace", "put ", "write", "log ", "record", "lock",
                        "plan ", "schedule", "assign", "move ", "fix ",
                        "make it", "switch", "remove", "delete", "drop ",
                        "for monday", "for tuesday", "for wednesday",
                        "for thursday", "for friday", "for saturday",
                        "for sunday", "dinner", "breakfast", "lunch",
                        "snack", "dessert", "helper",
                    )
                    _confirm_words = (
                        "done", "saved", "added", "updated", "changed",
                        "got it", "all set", "i've added", "i have added",
                        "i've updated", "i have updated", "i've saved",
                        "i have saved", "is now", "are now",
                    )
                    _had_intent  = any(w in _user_lc  for w in _save_intent_words)
                    _had_confirm = any(w in _reply_lc for w in _confirm_words)
                    # OUTCOME-based — count only saves that actually persisted,
                    # not just tags that appeared in the text (Lorenzo can emit
                    # malformed JSON or unparseable bodies that look like saves
                    # but aren't). frol = presence-of-tag (no outcome signal
                    # plumbed through yet). RULE:add stays counted because the
                    # frontend renders a button for it (Lauren can still save).
                    _emitted_any_tag = bool(
                        _meal_updates_found            # only successful MEAL saves
                        or _recipe_saves_ok
                        or _constraint_saves_ok
                        or _re.search(r'<frol_update\b', text, _re.IGNORECASE)
                        or _re.search(r'\[RULE:(add|delete)\]', text, _re.IGNORECASE)
                    )
                    if _had_intent and _had_confirm and not _emitted_any_tag:
                        _warning = (
                            "⚠️ **Heads up — nothing was actually saved.** "
                            "I confirmed but didn't emit the proper save tag, "
                            "so your meal plan / rules were NOT updated. "
                            "Please re-ask and I'll do it correctly, or open "
                            "the Meal Planner to make the change directly.\n\n"
                        )
                        _visible = _warning + _visible
                        print(f"[lorenzo-guard] FALSE CONFIRMATION blocked. "
                              f"user={message[:80]!r} reply={_visible[:120]!r}")
                except Exception as _ge:
                    print(f"[lorenzo-guard] error: {_ge}")
                _visible = finish_companion_turn("lorenzo", _visible)
                append_lorenzo_messages([{"role": "assistant", "content": _visible, "ts": ts_reply}])
                self.send_response(200)
                self.send_header("Content-Type","text/plain; charset=utf-8")
                self.end_headers()
                try: self.wfile.write(_visible.encode("utf-8"))
                except BrokenPipeError: pass
                return

            elif path == "/lorenzo-rule-save":
                import json as _json
                action    = clean_text(data.get("action",[""])[0]).strip()
                rule_text = clean_text(data.get("rule",[""])[0]).strip()
                if rule_text and action in ("add", "remove"):
                    _s = load_app_settings()
                    fc = _s.setdefault("family_constraints", {})
                    rules = fc.get("lorenzo_rules", [])
                    if not isinstance(rules, list):
                        rules = []
                    if action == "add" and rule_text not in rules:
                        rules.append(rule_text)
                    elif action == "remove":
                        rules = [r for r in rules if r != rule_text]
                    fc["lorenzo_rules"] = rules
                    _s["family_constraints"] = fc
                    save_app_settings(_s)
                self.send_response(200)
                self.send_header("Content-Type","text/plain")
                self.end_headers()
                try: self.wfile.write(b"ok")
                except BrokenPipeError: pass
                return

            elif path == "/lorenzo-plan-start":
                import json as _pj
                from data_helpers import (start_planning_session, clear_lorenzo_history,
                                          planning_session_summary, PLAN_DAYS, PLAN_SLOTS)
                from datetime import date as _ddate, timedelta as _tdelta
                # Determine week ISO — default to Sunday of current week
                _iso_in = clean_text(data.get("iso",[""])[0]).strip()
                if not _iso_in:
                    _td = _ddate.today()
                    _iso_in = (_td - _tdelta(days=(_td.weekday()+1)%7)).isoformat()
                clear_lorenzo_history()
                _sess = start_planning_session(_iso_in)
                _info = planning_session_summary(_sess)
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.end_headers()
                try: self.wfile.write(_pj.dumps(_info).encode("utf-8"))
                except BrokenPipeError: pass
                return

            elif path == "/lorenzo-plan-end":
                from data_helpers import clear_planning_session
                clear_planning_session()
                self.send_response(200)
                self.send_header("Content-Type","text/plain")
                self.end_headers()
                try: self.wfile.write(b"ok")
                except BrokenPipeError: pass
                return

            elif path == "/lorenzo-clear-history":
                from data_helpers import clear_lorenzo_history
                clear_lorenzo_history()
                redirect = "/lorenzo"

            # ── Father Gregory ───────────────────────────────────────────────
            elif path == "/headmaster-chat":
                import json as _json, urllib.request as _req
                from data_helpers import (
                    load_gregory_history, append_gregory_messages, GREGORY_CONTEXT_MAX
                )
                from datetime import datetime as _dt
                # Use Eastern datetime (TZ set to America/New_York at server startup)
                _now_et    = datetime.now()
                iso        = _now_et.date().isoformat()
                weekday    = _now_et.strftime("%A")
                date_label = _now_et.strftime("%B %d, %Y")
                _time_et   = _now_et.strftime("%-I:%M %p")
                message    = clean_text(data.get("message",[""])[0])
                settings_data = load_app_settings()
                api_key = (settings_data.get("family_constraints",{}).get("anthropic_api_key","")
                           or settings_data.get("anthropic_api_key","")).strip()
                if not api_key:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"No API key configured.")
                    except BrokenPipeError: pass
                    return
                gregory_context = build_gregory_context(iso, weekday, date_label) + _UNDO_BLOCK
                begin_companion_turn("gregory")
                ts_now = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                append_gregory_messages([{"role": "user", "content": message, "ts": ts_now}])
                server_history = load_gregory_history()
                messages = []
                for h in server_history[-GREGORY_CONTEXT_MAX:]:
                    role = h.get("role","user"); content = h.get("content","")
                    if role in ("user","assistant") and content:
                        messages.append({"role": role, "content": content})
                if not messages or messages[-1].get("role") != "user":
                    messages.append({"role": "user", "content": message})
                # Stamp current date+time into the last user message so stale history can't override it
                _date_stamp = f"[Today: {weekday}, {date_label}, {_time_et} ET]"
                if messages and messages[-1].get("role") == "user" and isinstance(messages[-1]["content"], str):
                    messages[-1]["content"] = f"{_date_stamp}\n{messages[-1]['content']}"
                payload = _json.dumps({
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "system":     gregory_context + _AI_GUARDRAILS,
                    "messages":   messages,
                    "stream":     True,
                }).encode("utf-8")
                req = _req.Request("https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"})
                try:
                    resp = _req.urlopen(req, timeout=60)
                    self.send_response(200)
                    self.send_header("Content-Type","text/plain; charset=utf-8")
                    self.send_header("Transfer-Encoding","chunked")
                    self.send_header("Cache-Control","no-store")
                    self.end_headers()
                    text = ""
                    for raw in resp:
                        line = raw.decode("utf-8").strip()
                        if line.startswith("data:"):
                            chunk = line[5:].strip()
                            if chunk == "[DONE]": break
                            try:
                                obj = _json.loads(chunk)
                                delta = obj.get("delta",{})
                                piece = delta.get("text","") if delta.get("type") == "text_delta" else ""
                                if piece:
                                    text += piece
                                    try: self.wfile.write(piece.encode("utf-8")); self.wfile.flush()
                                    except BrokenPipeError: break
                            except Exception: pass
                    ts_reply = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                    _apply_frol_updates(text, weekday)
                    text = _strip_hallucinated_tool_use(text)
                    text = finish_companion_turn("gregory", text)
                    append_gregory_messages([{"role": "assistant", "content": text, "ts": ts_reply}])
                except Exception as e:
                    try: self.wfile.write(str(e).encode("utf-8"))
                    except BrokenPipeError: pass
                return

            elif path == "/headmaster-clear-history":
                from data_helpers import clear_gregory_history
                clear_gregory_history()
                redirect = "/headmaster"

            # ── Coach ────────────────────────────────────────────────────────
            elif path == "/coach-chat":
                import json as _json, urllib.request as _req
                from data_helpers import (
                    load_coach_history, append_coach_messages, COACH_CONTEXT_MAX
                )
                from datetime import datetime as _dt
                # Use Eastern datetime (TZ set to America/New_York at server startup)
                _now_et    = datetime.now()
                iso        = _now_et.date().isoformat()
                weekday    = _now_et.strftime("%A")
                date_label = _now_et.strftime("%B %d, %Y")
                _time_et   = _now_et.strftime("%-I:%M %p")
                message    = clean_text(data.get("message",[""])[0])
                settings_data = load_app_settings()
                api_key = (settings_data.get("family_constraints",{}).get("anthropic_api_key","")
                           or settings_data.get("anthropic_api_key","")).strip()
                if not api_key:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"No API key configured.")
                    except BrokenPipeError: pass
                    return
                coach_context = build_coach_context(iso, weekday, date_label) + _UNDO_BLOCK
                begin_companion_turn("coach")
                ts_now = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                append_coach_messages([{"role": "user", "content": message, "ts": ts_now}])
                server_history = load_coach_history()
                messages = []
                for h in server_history[-COACH_CONTEXT_MAX:]:
                    role = h.get("role","user"); content = h.get("content","")
                    if role in ("user","assistant") and content:
                        messages.append({"role": role, "content": content})
                if not messages or messages[-1].get("role") != "user":
                    messages.append({"role": "user", "content": message})
                # Stamp current date+time into the last user message so stale history can't override it
                _date_stamp = f"[Today: {weekday}, {date_label}, {_time_et} ET]"
                if messages and messages[-1].get("role") == "user" and isinstance(messages[-1]["content"], str):
                    messages[-1]["content"] = f"{_date_stamp}\n{messages[-1]['content']}"
                payload = _json.dumps({
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 1200,
                    "system":     coach_context + _AI_GUARDRAILS,
                    "messages":   messages,
                    "stream":     True,
                }).encode("utf-8")
                req = _req.Request("https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"})
                try:
                    resp = _req.urlopen(req, timeout=60)
                    self.send_response(200)
                    self.send_header("Content-Type","text/plain; charset=utf-8")
                    self.send_header("Transfer-Encoding","chunked")
                    self.send_header("Cache-Control","no-store")
                    self.end_headers()
                    text = ""
                    for raw in resp:
                        line = raw.decode("utf-8").strip()
                        if line.startswith("data:"):
                            chunk = line[5:].strip()
                            if chunk == "[DONE]": break
                            try:
                                obj = _json.loads(chunk)
                                delta = obj.get("delta",{})
                                piece = delta.get("text","") if delta.get("type") == "text_delta" else ""
                                if piece:
                                    text += piece
                                    try: self.wfile.write(piece.encode("utf-8")); self.wfile.flush()
                                    except BrokenPipeError: break
                            except Exception: pass
                    ts_reply = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                    _apply_frol_updates(text, weekday)
                    _apply_coach_program_saves(text)
                    text = _strip_hallucinated_tool_use(text)
                    text = finish_companion_turn("coach", text)
                    append_coach_messages([{"role": "assistant", "content": text, "ts": ts_reply}])
                except Exception as e:
                    try: self.wfile.write(str(e).encode("utf-8"))
                    except BrokenPipeError: pass
                return

            elif path == "/coach-clear-history":
                from data_helpers import clear_coach_history
                clear_coach_history()
                redirect = "/coach"

            elif path == "/programs-save":
                from data_helpers import save_coach_program as _scp
                from urllib.parse import quote as _q
                person = clean_text(data.get("person",[""])[0])
                title  = clean_text(data.get("title",[""])[0])
                body_t = (data.get("body",[""])[0] or "").strip()  # preserve newlines
                _scp(person, title, body_t)
                redirect = "/programs?focus=" + _q(person) + "&msg=" + _q(f"Saved \u201c{title}\u201d for {person}.")

            elif path == "/programs-delete":
                from data_helpers import delete_coach_program as _dcp
                from urllib.parse import quote as _q
                person = clean_text(data.get("person",[""])[0])
                pid    = clean_text(data.get("id",[""])[0])
                _dcp(person, pid)
                redirect = "/programs?focus=" + _q(person) + "&msg=" + _q("Deleted.")

            # ── Felix (Dev companion) ─────────────────────────────────────────
            elif path == "/dev-chat":
                import json as _json, urllib.request as _req
                from data_helpers import (
                    load_dev_history, append_dev_messages, DEV_CONTEXT_MAX
                )
                from render_dev import build_felix_context, _get_relevant_files
                from datetime import datetime as _dt

                _dv = self._get_viewer()
                if not (_dv and _auth.is_admin(_dv)):
                    self.send_response(403); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Admin only."); return

                message = clean_text(data.get("message",[""])[0])
                image_b64  = data.get("image_data",[""])[0]   # raw base64 from client
                image_type = clean_text(data.get("image_type",["image/jpeg"])[0]) or "image/jpeg"
                is_auto_read = data.get("is_auto_read",[""])[0] == "1"
                settings_data = load_app_settings()
                api_key = (settings_data.get("family_constraints",{}).get("anthropic_api_key","")
                           or settings_data.get("anthropic_api_key","")).strip()
                if not api_key:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"No API key configured.")
                    except BrokenPipeError: pass
                    return

                # Inject relevant source files into context
                relevant = _get_relevant_files(message)
                file_context = ""
                if relevant:
                    file_context = "\n\n════ RELEVANT SOURCE FILES (auto-detected) ════\n"
                    for fname, content in relevant:
                        file_context += f"\n── {fname} ──\n{content}\n"

                felix_context = build_felix_context() + _UNDO_BLOCK
                begin_companion_turn("dev")
                ts_now = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                _now_et_iz  = datetime.now()
                _date_stamp_iz = (f"[Today: {_now_et_iz.strftime('%A')}, "
                                  f"{_now_et_iz.strftime('%B %d, %Y')}, "
                                  f"{_now_et_iz.strftime('%-I:%M %p')} ET]")
                full_user_msg = f"{_date_stamp_iz}\n{message}" + file_context if file_context else f"{_date_stamp_iz}\n{message}"

                # Save to history.  For file reads, store the actual content
                # (truncated) so Izzy can reference it in future turns.
                import re as _re_save
                clean_msg = _re_save.sub(r'\n\n\[SERVER LOG.*?\n\]', '', message, flags=_re_save.DOTALL).strip()
                if is_auto_read:
                    # Store real content with a [FILE_READ] prefix so the UI
                    # can show a compact chip while Claude gets the full text.
                    history_content = "[FILE_READ]\n" + message[:2500]
                else:
                    history_content = clean_msg + ("\n[Lauren attached a screenshot]" if image_b64 else "")
                append_dev_messages([{"role": "user", "content": history_content, "ts": ts_now}])

                server_history = load_dev_history()
                messages = []
                # When is_auto_read the last entry is the current file read —
                # we'll add it via full_user_msg (with date stamp), so exclude it.
                _hist_slice = server_history[-DEV_CONTEXT_MAX:-1] if is_auto_read else server_history[-DEV_CONTEXT_MAX:]
                for h in _hist_slice:
                    role = h.get("role","user"); content = h.get("content","")
                    if content.startswith("[FILE_READ]\n"):
                        # Send file content to Claude, strip display prefix
                        _frc = content[len("[FILE_READ]\n"):]
                        if _frc and role in ("user","assistant"):
                            messages.append({"role": role, "content": _frc})
                    elif role in ("user","assistant") and content:
                        messages.append({"role": role, "content": content})

                # Build the current turn
                if is_auto_read:
                    # Full file content (with date stamp) for the current read
                    messages.append({"role": "user", "content": full_user_msg})
                elif image_b64:
                    current_content = [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": image_type, "data": image_b64}},
                        {"type": "text", "text": full_user_msg}
                    ]
                    if messages and messages[-1].get("role") == "user":
                        messages[-1]["content"] = current_content
                    else:
                        messages.append({"role": "user", "content": current_content})
                # else: regular text message already added via history loop above

                payload = _json.dumps({
                    "model":      "claude-sonnet-4-20250514",
                    "max_tokens": 3000,
                    "system":     felix_context,
                    "messages":   messages,
                    "stream":     True,
                }).encode("utf-8")
                req = _req.Request("https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"})
                import urllib.error as _uerr, time as _time_mod
                resp = None
                _iz_retry_wait = 30   # seconds to wait on first rate-limit hit
                for _iz_attempt in range(3):
                    try:
                        resp = _req.urlopen(req, timeout=90)
                        break  # success
                    except _uerr.HTTPError as e:
                        err_body = ""
                        try: err_body = e.read().decode("utf-8")
                        except Exception: pass
                        is_rate_limit = (e.code == 429 or "rate limit" in err_body.lower())
                        if is_rate_limit and _iz_attempt < 2:
                            _time_mod.sleep(_iz_retry_wait)
                            _iz_retry_wait *= 2   # 30s → 60s on second retry
                            continue
                        # Not a rate-limit, or retries exhausted — surface the error
                        try:
                            err_obj = _json.loads(err_body)
                            err_msg = err_obj.get("error", {}).get("message", "") or err_body
                        except Exception:
                            err_msg = err_body or str(e)
                        self.send_response(400)
                        self.send_header("Content-Type","text/plain; charset=utf-8")
                        self.end_headers()
                        try: self.wfile.write(f"Anthropic API error: {err_msg}".encode("utf-8"))
                        except BrokenPipeError: pass
                        return
                    except Exception as e:
                        self.send_response(500)
                        self.send_header("Content-Type","text/plain; charset=utf-8")
                        self.end_headers()
                        try: self.wfile.write(f"Server error: {e}".encode("utf-8"))
                        except BrokenPipeError: pass
                        return
                if resp is None:
                    self.send_response(503)
                    self.send_header("Content-Type","text/plain; charset=utf-8")
                    self.end_headers()
                    try: self.wfile.write(b"Rate limit retries exhausted - please try again in a minute.")
                    except BrokenPipeError: pass
                    return

                self.send_response(200)
                self.send_header("Content-Type","text/plain; charset=utf-8")
                self.send_header("Transfer-Encoding","chunked")
                self.send_header("Cache-Control","no-store")
                self.end_headers()
                text = ""
                api_error = ""
                for raw in resp:
                    line = raw.decode("utf-8").strip()
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                        if event_type == "error":
                            api_error = "stream_error"
                    elif line.startswith("data:"):
                        chunk = line[5:].strip()
                        if chunk == "[DONE]": break
                        try:
                            obj = _json.loads(chunk)
                            # Surface Anthropic stream errors
                            if obj.get("type") == "error":
                                api_error = obj.get("error", {}).get("message", "Unknown API error")
                                try: self.wfile.write(f"\n\n⚠️ API error: {api_error}".encode("utf-8")); self.wfile.flush()
                                except BrokenPipeError: pass
                                break
                            delta = obj.get("delta",{})
                            piece = delta.get("text","") if delta.get("type") == "text_delta" else ""
                            if piece:
                                text += piece
                                try: self.wfile.write(piece.encode("utf-8")); self.wfile.flush()
                                except BrokenPipeError: break
                        except Exception: pass
                ts_reply = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                if text:
                    _apply_frol_updates(text, _dt.now().strftime("%A"))
                    text = finish_companion_turn("dev", text)
                    append_dev_messages([{"role": "assistant", "content": text, "ts": ts_reply}])
                return

            elif path == "/dev-apply":
                import pathlib as _pathlib
                _dv = self._get_viewer()
                if not (_dv and _auth.is_admin(_dv)):
                    self.send_response(403); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Admin only."); return

                filename = clean_text(data.get("file",[""])[0]).strip()
                find_str = data.get("find",[""])[0]   # raw — don't strip whitespace
                repl_str = data.get("replace",[""])[0]

                # Safety: only allow .py files and known config files in project root
                allowed_exts = {".py", ".json", ".css", ".js", ".html", ".md"}
                fpath = _pathlib.Path(filename)
                if fpath.parent != _pathlib.Path(".") or fpath.suffix not in allowed_exts:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Only project-root .py/.json/.css/.js files allowed."); return
                if not fpath.exists():
                    self.send_response(404); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(f"File not found: {filename}".encode()); return

                content = fpath.read_text(encoding="utf-8")
                if find_str not in content:
                    self.send_response(422); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"FIND string not found in file - the code may have already been changed."); return

                # Stale-edit guard — if Izzy already edited this file in this
                # session and hasn't re-READ it since, his line numbers and
                # surrounding context are stale → reject.
                _stale = _izzy_check_stale(filename)
                if _stale:
                    self.send_response(409); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(_stale.encode())
                    except BrokenPipeError: pass
                    return

                new_content = content.replace(find_str, repl_str, 1)

                # Edit-size cap — block "let me regenerate the file" patterns
                _ok_sz, _sz_err = _izzy_size_ok(repl_str, old_span_lines=find_str.count("\n") + 1)
                if not _ok_sz:
                    self.send_response(413); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(_sz_err.encode())
                    except BrokenPipeError: pass
                    return

                # Syntax check BEFORE writing — reject if proposed file is broken
                _ok_syn, _syn_err = _izzy_syntax_ok(filename, new_content)
                if not _ok_syn:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(f"FIX REJECTED — file NOT saved:\n{_syn_err}".encode())
                    except BrokenPipeError: pass
                    return

                # Push backup onto the undo STACK (multi-level — keep last 30)
                # so Lauren / Izzy can roll back through several bad edits to
                # the file's state BEFORE Izzy began touching it.
                import json as _jundo, pathlib as _pupath
                from datetime import datetime as _dtu
                _undo_path = _pupath.Path("data/felix_undo.json")
                try:
                    _stack = []
                    if _undo_path.exists():
                        _raw = _jundo.loads(_undo_path.read_text(encoding="utf-8"))
                        _stack = _raw if isinstance(_raw, list) else [_raw]
                    _stack.append({"file": filename, "content": content,
                                   "ts": _dtu.now().strftime("%Y-%m-%dT%H:%M:%S"),
                                   "kind": "find/replace"})
                    _stack = _stack[-30:]
                    _undo_path.write_text(_jundo.dumps(_stack), encoding="utf-8")
                except Exception: pass

                fpath.write_text(new_content, encoding="utf-8")
                _izzy_mark_write(filename)

                # Return the unified diff so Izzy can see what actually landed
                _diff = _izzy_diff(content, new_content, filename)
                self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
                try: self.wfile.write(f"Applied to {filename}\n\n--- DIFF ---\n{_diff}".encode())
                except BrokenPipeError: pass
                return

            elif path == "/dev-write":
                # Line-range replacement: more reliable than find/replace for Izzy
                import pathlib as _wpathlib
                _wdv = self._get_viewer()
                if not (_wdv and _auth.is_admin(_wdv)):
                    self.send_response(403); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Admin only."); return

                w_filename = clean_text(data.get("file",[""])[0]).strip()
                try:
                    w_start = int(data.get("start",["0"])[0])
                    w_end   = int(data.get("end",["0"])[0])
                except (ValueError, IndexError):
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Invalid start/end line numbers."); return
                w_content = data.get("content",[""])[0]

                allowed_exts = {".py", ".json", ".css", ".js", ".html", ".md"}
                w_fpath = _wpathlib.Path(w_filename)
                if w_fpath.parent != _wpathlib.Path(".") or w_fpath.suffix not in allowed_exts:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Only project-root .py/.json/.css/.js files allowed."); return
                if not w_fpath.exists():
                    self.send_response(404); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(f"File not found: {w_filename}".encode()); return

                w_file_content = w_fpath.read_text(encoding="utf-8")
                w_lines = w_file_content.splitlines(keepends=True)
                total_lines = len(w_lines)
                if w_start < 1 or w_end < w_start or w_start > total_lines:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(f"Line range {w_start}-{w_end} is out of bounds (file has {total_lines} lines).".encode()); return

                # Stale-edit guard
                _wstale = _izzy_check_stale(w_filename)
                if _wstale:
                    self.send_response(409); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(_wstale.encode())
                    except BrokenPipeError: pass
                    return

                # Edit-size cap
                _wok_sz, _wsz_err = _izzy_size_ok(w_content, old_span_lines=(w_end - w_start + 1))
                if not _wok_sz:
                    self.send_response(413); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(_wsz_err.encode())
                    except BrokenPipeError: pass
                    return

                # Push backup onto the undo STACK (multi-level — keep last 30)
                import json as _wjundo, pathlib as _wpupath
                from datetime import datetime as _dtw
                _wundo_path = _wpupath.Path("data/felix_undo.json")
                try:
                    _wstack = []
                    if _wundo_path.exists():
                        _wraw = _wjundo.loads(_wundo_path.read_text(encoding="utf-8"))
                        _wstack = _wraw if isinstance(_wraw, list) else [_wraw]
                    _wstack.append({"file": w_filename, "content": w_file_content,
                                    "ts": _dtw.now().strftime("%Y-%m-%dT%H:%M:%S"),
                                    "kind": f"lines {w_start}-{w_end}"})
                    _wstack = _wstack[-30:]
                    _wundo_path.write_text(_wjundo.dumps(_wstack), encoding="utf-8")
                except Exception: pass

                # Replace lines w_start..w_end (1-indexed inclusive) with new content
                new_block = w_content if w_content.endswith("\n") else w_content + "\n"
                new_lines = w_lines[:w_start - 1] + [new_block] + w_lines[w_end:]
                new_text = "".join(new_lines)

                # Syntax-check .py files BEFORE writing — reject and report error if broken
                if w_fpath.suffix == ".py":
                    import subprocess as _wsp
                    import tempfile as _wtmp
                    with _wtmp.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as _tf:
                        _tf.write(new_text)
                        _tf_name = _tf.name
                    _syn = _wsp.run(
                        ["python3", "-m", "py_compile", _tf_name],
                        capture_output=True, text=True
                    )
                    import os as _wos2; _wos2.unlink(_tf_name)
                    if _syn.returncode != 0:
                        err_msg = (_syn.stderr or "syntax error").replace(_tf_name, w_filename)
                        self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                        try: self.wfile.write(f"SYNTAX ERROR — file NOT saved:\n{err_msg}".encode())
                        except BrokenPipeError: pass
                        return

                w_fpath.write_text(new_text, encoding="utf-8")
                _izzy_mark_write(w_filename)

                # Return the unified diff so Izzy can verify what landed
                _wdiff = _izzy_diff(w_file_content, new_text, w_filename)
                self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
                try: self.wfile.write(f"Written lines {w_start}-{w_end} of {w_filename}\n\n--- DIFF ---\n{_wdiff}".encode())
                except BrokenPipeError: pass
                return

            elif path == "/dev-undo":
                # Multi-level undo: pop the most recent backup off the stack and
                # restore that file. Optional ?file=NAME pops the most recent
                # backup that matches NAME (skipping unrelated files).
                # Optional ?all=1 reverts every backup in reverse order, taking
                # each affected file all the way back to its earliest captured state.
                import json as _jundo2, pathlib as _pupath2
                _dvu = self._get_viewer()
                if not (_dvu and _auth.is_admin(_dvu)):
                    self.send_response(403); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Admin only."); return
                _undo2 = _pupath2.Path("data/felix_undo.json")
                if not _undo2.exists():
                    self.send_response(404); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Nothing to undo."); return
                try:
                    _raw2 = _jundo2.loads(_undo2.read_text(encoding="utf-8"))
                    stack = _raw2 if isinstance(_raw2, list) else [_raw2]
                except Exception as ex:
                    self.send_response(500); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(f"Undo read error: {ex}".encode()); return
                if not stack:
                    self.send_response(404); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Undo stack is empty."); return

                _wanted_file = clean_text(data.get("file",[""])[0]).strip()
                _all_flag    = data.get("all",[""])[0] == "1"

                restored_msgs: list = []
                try:
                    if _all_flag:
                        # Walk backwards, restore each file to its EARLIEST
                        # captured backup (i.e. the state before Izzy first
                        # touched it in this run). Then clear the entire stack.
                        earliest_per_file: dict = {}
                        for entry in stack:
                            f = entry.get("file"); c = entry.get("content","")
                            if f and f not in earliest_per_file:
                                earliest_per_file[f] = c
                        for f, c in earliest_per_file.items():
                            _pupath2.Path(f).write_text(c, encoding="utf-8")
                            restored_msgs.append(f)
                        _undo2.unlink()
                        msg = f"Reverted {len(restored_msgs)} file(s) to pre-edit state: {', '.join(restored_msgs)}"
                    elif _wanted_file:
                        # Pop most recent backup whose file matches
                        idx = None
                        for i in range(len(stack) - 1, -1, -1):
                            if stack[i].get("file") == _wanted_file:
                                idx = i; break
                        if idx is None:
                            self.send_response(404); self.send_header("Content-Type","text/plain"); self.end_headers()
                            self.wfile.write(f"No undo entry for {_wanted_file}".encode()); return
                        entry = stack.pop(idx)
                        _pupath2.Path(entry["file"]).write_text(entry["content"], encoding="utf-8")
                        if stack:
                            _undo2.write_text(_jundo2.dumps(stack), encoding="utf-8")
                        else:
                            _undo2.unlink()
                        msg = f"Undone: {entry['file']} ({len(stack)} backup(s) remain)"
                    else:
                        # Pop the single most recent backup
                        entry = stack.pop()
                        _pupath2.Path(entry["file"]).write_text(entry["content"], encoding="utf-8")
                        if stack:
                            _undo2.write_text(_jundo2.dumps(stack), encoding="utf-8")
                        else:
                            _undo2.unlink()
                        msg = f"Undone: {entry['file']} ({len(stack)} backup(s) remain)"
                except Exception as ex:
                    self.send_response(500); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(f"Undo error: {ex}".encode()); return
                self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
                try: self.wfile.write(msg.encode())
                except BrokenPipeError: pass
                return

            elif path == "/dev-restart":
                _dv = self._get_viewer()
                if not (_dv and _auth.is_admin(_dv)):
                    self.send_response(403); self.send_header("Content-Type","text/plain"); self.end_headers()
                    self.wfile.write(b"Admin only."); return

                # ── Pre-flight import check — block restart if app will crash ──
                import subprocess as _sub, sys as _sys
                _check = _sub.run(
                    [_sys.executable, "-c", "import app"],
                    capture_output=True, text=True, timeout=30
                )
                if _check.returncode != 0:
                    _err = (_check.stderr or _check.stdout or "Unknown import error").strip()
                    self.send_response(409)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    try:
                        self.wfile.write(
                            f"RESTART BLOCKED — import check failed:\n\n{_err}\n\n"
                            f"Fix the error above before restarting.".encode("utf-8")
                        )
                    except BrokenPipeError: pass
                    return

                self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
                try: self.wfile.write(b"Restarting...")
                except BrokenPipeError: pass
                import signal as _sig, threading as _thr
                def _do_restart():
                    import time; time.sleep(0.8)
                    import os as _os; _os.kill(_os.getpid(), _sig.SIGTERM)
                _thr.Thread(target=_do_restart, daemon=True).start()
                return

            elif path == "/dev-clear":
                _dv = self._get_viewer()
                if not (_dv and _auth.is_admin(_dv)):
                    redirect = "/"
                else:
                    from data_helpers import clear_dev_history
                    clear_dev_history()
                    redirect = "/dev"

            # ── Dr. Monica ───────────────────────────────────────────────────
            elif path == "/dr-monica-chat":
                import json as _json, urllib.request as _req
                from data_helpers import (
                    load_monica_history, append_monica_messages, MONICA_CONTEXT_MAX
                )
                from datetime import datetime as _dt
                # Use Eastern datetime (TZ set to America/New_York at server startup)
                _now_et    = datetime.now()
                iso        = _now_et.date().isoformat()
                weekday    = _now_et.strftime("%A")
                date_label = _now_et.strftime("%B %d, %Y")
                _time_et   = _now_et.strftime("%-I:%M %p")
                message    = clean_text(data.get("message",[""])[0])
                settings_data = load_app_settings()
                api_key = (settings_data.get("family_constraints",{}).get("anthropic_api_key","")
                           or settings_data.get("anthropic_api_key","")).strip()
                if not api_key:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"No API key configured.")
                    except BrokenPipeError: pass
                    return
                monica_context = build_monica_context(iso, weekday, date_label) + _UNDO_BLOCK
                begin_companion_turn("monica")
                ts_now = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                append_monica_messages([{"role": "user", "content": message, "ts": ts_now}])
                server_history = load_monica_history()
                messages = []
                for h in server_history[-MONICA_CONTEXT_MAX:]:
                    role = h.get("role","user"); content = h.get("content","")
                    if role in ("user","assistant") and content:
                        messages.append({"role": role, "content": content})
                if not messages or messages[-1].get("role") != "user":
                    messages.append({"role": "user", "content": message})
                # Stamp current date+time into the last user message so stale history can't override it
                _date_stamp = f"[Today: {weekday}, {date_label}, {_time_et} ET]"
                if messages and messages[-1].get("role") == "user" and isinstance(messages[-1]["content"], str):
                    messages[-1]["content"] = f"{_date_stamp}\n{messages[-1]['content']}"
                payload = _json.dumps({
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "system":     monica_context + _AI_GUARDRAILS,
                    "messages":   messages,
                    "stream":     True,
                }).encode("utf-8")
                req = _req.Request("https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"})
                try:
                    resp = _req.urlopen(req, timeout=60)
                    self.send_response(200)
                    self.send_header("Content-Type","text/plain; charset=utf-8")
                    self.send_header("Transfer-Encoding","chunked")
                    self.send_header("Cache-Control","no-store")
                    self.end_headers()
                    text = ""
                    for raw in resp:
                        line = raw.decode("utf-8").strip()
                        if line.startswith("data:"):
                            chunk = line[5:].strip()
                            if chunk == "[DONE]": break
                            try:
                                obj = _json.loads(chunk)
                                delta = obj.get("delta",{})
                                piece = delta.get("text","") if delta.get("type") == "text_delta" else ""
                                if piece:
                                    text += piece
                                    try: self.wfile.write(piece.encode("utf-8")); self.wfile.flush()
                                    except BrokenPipeError: break
                            except Exception: pass
                    ts_reply = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                    _apply_frol_updates(text, weekday)
                    text = _strip_hallucinated_tool_use(text)
                    text = finish_companion_turn("monica", text)
                    append_monica_messages([{"role": "assistant", "content": text, "ts": ts_reply}])
                except Exception as e:
                    try: self.wfile.write(str(e).encode("utf-8"))
                    except BrokenPipeError: pass
                return

            elif path == "/dr-monica-clear-history":
                from data_helpers import clear_monica_history
                clear_monica_history()
                redirect = "/dr-monica"

            # ── Curriculum Importer ───────────────────────────────────────────
            elif path == "/curriculum-parse":
                import json as _curj
                _cur_v = self._get_viewer()
                if not (_cur_v and _auth.is_admin(_cur_v)):
                    self.send_response(403); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(_curj.dumps({"error":"Forbidden"}).encode())
                    except BrokenPipeError: pass
                    return
                _child   = clean_text(data.get("child",   [""])[0])
                _subject = clean_text(data.get("subject", [""])[0])
                _paste   = data.get("paste", [""])[0]
                if not _subject or not _paste.strip():
                    self.send_response(400); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(_curj.dumps({"error":"Missing subject or paste."}).encode())
                    except BrokenPipeError: pass
                    return
                try:
                    _weeks, _cur_err = parse_modg_paste(_subject, _paste)
                    if _cur_err or not _weeks:
                        resp_data = _curj.dumps({"error": _cur_err or "Could not extract any weeks — check the paste and try again."})
                    else:
                        resp_data = _curj.dumps({"weeks": _weeks})
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(resp_data.encode())
                    except BrokenPipeError: pass
                except Exception as _cure:
                    self.send_response(500); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(_curj.dumps({"error": str(_cure)}).encode())
                    except BrokenPipeError: pass
                return

            elif path == "/curriculum-save":
                import json as _curj2
                _cur_v2 = self._get_viewer()
                if not (_cur_v2 and _auth.is_admin(_cur_v2)):
                    self.send_response(403); self.end_headers(); return
                try:
                    _body_raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    _body = _curj2.loads(_body_raw)
                    _child2   = str(_body.get("child", "")).strip()
                    _subject2 = str(_body.get("subject", "")).strip()
                    _weeks2   = _body.get("weeks", {})
                    _mins2    = _body.get("minutes")
                    if not _child2 or not _subject2 or not _weeks2:
                        self.send_response(400); self.end_headers(); return
                    from data_helpers import load_curriculum, save_curriculum
                    _cur_data = load_curriculum()
                    if _child2 not in _cur_data:
                        _cur_data[_child2] = {}
                    # Preserve existing _minutes if not supplied
                    _existing_mins = (_cur_data.get(_child2, {})
                                      .get(_subject2, {}).get("_minutes"))
                    # Values may be plain strings (whole-week format) OR a
                    # {day_num: text} dict (per-day format). Preserve both.
                    _new_subj = {}
                    for _wk, _wv in _weeks2.items():
                        if isinstance(_wv, dict):
                            _new_subj[str(_wk)] = {
                                str(_d): str(_t) for _d, _t in _wv.items()
                            }
                        else:
                            _new_subj[str(_wk)] = str(_wv)
                    if _mins2 is not None:
                        try: _new_subj["_minutes"] = int(_mins2)
                        except (TypeError, ValueError): pass
                    elif _existing_mins is not None:
                        _new_subj["_minutes"] = _existing_mins
                    _cur_data[_child2][_subject2] = _new_subj
                    save_curriculum(_cur_data)
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(_curj2.dumps({"ok": True}).encode())
                    except BrokenPipeError: pass
                except Exception as _cure2:
                    self.send_response(500); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"error":"save failed"}')
                    except BrokenPipeError: pass
                return

            elif path == "/curriculum-minutes":
                import json as _cmj
                _cm_v = self._get_viewer()
                if not (_cm_v and _auth.is_admin(_cm_v)):
                    self.send_response(403); self.end_headers(); return
                try:
                    _cm_raw  = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    _cm_body = _cmj.loads(_cm_raw)
                    _cm_child   = str(_cm_body.get("child", "")).strip()
                    _cm_subject = str(_cm_body.get("subject", "")).strip()
                    _cm_mins    = int(_cm_body.get("minutes", 30))
                    if _cm_child and _cm_subject and _cm_mins >= 5:
                        from data_helpers import load_curriculum, save_curriculum
                        _cm_cur = load_curriculum()
                        if _cm_child in _cm_cur and _cm_subject in _cm_cur[_cm_child]:
                            _cm_cur[_cm_child][_cm_subject]["_minutes"] = _cm_mins
                            save_curriculum(_cm_cur)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/poetry-passage-save":
                import json as _ppj
                try:
                    _pp_raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    _pp_payload = _ppj.loads(_pp_raw)
                    from render_week_school import load_poetry_passages, save_poetry_passages
                    _pp_data = load_poetry_passages()
                    for _pp_child, _pp_fields in _pp_payload.items():
                        if not isinstance(_pp_fields, dict):
                            continue
                        _pp_data[_pp_child] = {
                            "title": str(_pp_fields.get("title", "")).strip(),
                            "text":  str(_pp_fields.get("text", "")).strip(),
                        }
                    save_poetry_passages(_pp_data)
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(_ppj.dumps({"ok": True}).encode())
                    except BrokenPipeError: pass
                except Exception as _ppe:
                    self.send_response(500); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"error":"save failed"}')
                    except BrokenPipeError: pass
                return

            elif path == "/curriculum-week":
                _cur_v3 = self._get_viewer()
                if not (_cur_v3 and _auth.is_admin(_cur_v3)):
                    self.send_response(403); self.end_headers(); return
                try:
                    _wk = int(data.get("week", [1])[0])
                    _wk = max(1, min(40, _wk))
                    from data_helpers import load_curriculum, save_curriculum
                    _cur_data3 = load_curriculum()
                    _cur_data3["current_week"] = _wk
                    save_curriculum(_cur_data3)
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":true}')
                    except BrokenPipeError: pass
                except Exception:
                    self.send_response(500); self.end_headers()
                return

            elif path == "/curriculum-subject-week":
                _csw_v = self._get_viewer()
                if not (_csw_v and _auth.is_admin(_csw_v)):
                    self.send_response(403); self.end_headers(); return
                try:
                    _csw_child   = clean_text(data.get("child",   [""])[0])
                    _csw_subject = clean_text(data.get("subject", [""])[0])
                    _csw_week    = int(data.get("week", [1])[0])
                    _csw_week    = max(1, min(40, _csw_week))
                    if _csw_child and _csw_subject:
                        from data_helpers import load_curriculum, save_curriculum
                        _csw_cur = load_curriculum()
                        if _csw_child in _csw_cur and _csw_subject in _csw_cur[_csw_child]:
                            _csw_cur[_csw_child][_csw_subject]["_current_week"] = _csw_week
                            save_curriculum(_csw_cur)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    try: self.wfile.write(b'{"ok":true}')
                    except BrokenPipeError: pass
                except Exception:
                    self.send_response(500); self.end_headers()
                return

            elif path == "/curriculum-subject-day":
                _csd_v = self._get_viewer()
                if not (_csd_v and _auth.is_admin(_csd_v)):
                    self.send_response(403); self.end_headers(); return
                try:
                    _csd_child   = clean_text(data.get("child",   [""])[0])
                    _csd_subject = clean_text(data.get("subject", [""])[0])
                    _csd_day     = int(data.get("day", [1])[0])
                    _csd_day     = max(1, min(7, _csd_day))
                    if _csd_child and _csd_subject:
                        from data_helpers import load_curriculum, save_curriculum
                        _csd_cur = load_curriculum()
                        if _csd_child in _csd_cur and _csd_subject in _csd_cur[_csd_child]:
                            _csd_cur[_csd_child][_csd_subject]["_current_day"] = _csd_day
                            save_curriculum(_csd_cur)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    try: self.wfile.write(b'{"ok":true}')
                    except BrokenPipeError: pass
                except Exception:
                    self.send_response(500); self.end_headers()
                return

            elif path == "/curriculum-delete":
                _cur_v4 = self._get_viewer()
                if not (_cur_v4 and _auth.is_admin(_cur_v4)):
                    self.send_response(403); self.end_headers(); return
                try:
                    _child4   = clean_text(data.get("child",   [""])[0])
                    _subject4 = clean_text(data.get("subject", [""])[0])
                    from data_helpers import load_curriculum, save_curriculum
                    _cur_data4 = load_curriculum()
                    if _child4 in _cur_data4 and _subject4 in _cur_data4[_child4]:
                        del _cur_data4[_child4][_subject4]
                        save_curriculum(_cur_data4)
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":true}')
                    except BrokenPipeError: pass
                except Exception:
                    self.send_response(500); self.end_headers()
                return

            # ── Plan Import — Analyze ─────────────────────────────────────────
            elif path == "/plan-import-analyze":
                import json as _pij, re as _pire, urllib.request as _pireq
                import base64 as _pib64
                from datetime import datetime as _pidt
                _pi_v = self._get_viewer()
                if not (_pi_v and _auth.is_admin(_pi_v)):
                    self.send_response(403); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"Forbidden")
                    except BrokenPipeError: pass
                    return
                # Detect multipart (image upload) vs urlencoded
                _pi_img_b64 = ""
                _pi_img_mime = ""
                _pi_ctype = (self.headers.get("Content-Type","") or "").lower()
                if _pi_ctype.startswith("multipart/form-data"):
                    try:
                        form = parse_multipart_form(self)
                        plan_text = clean_text(form.getfirst("plan_text","") or "")
                        answers_raw = form.getfirst("answers","") or ""
                        _img_field = form["plan_image"] if "plan_image" in form else None
                        if _img_field is not None and getattr(_img_field, "filename", ""):
                            _img_bytes = _img_field.file.read()
                            _pi_img_mime = (_img_field.type or "image/png").strip()
                            # Cap at 8 MB server-side too
                            if len(_img_bytes) <= 8 * 1024 * 1024 and _img_bytes:
                                _pi_img_b64 = _pib64.b64encode(_img_bytes).decode("ascii")
                    except Exception as _mpe:
                        self.send_response(400); self.send_header("Content-Type","application/json"); self.end_headers()
                        try: self.wfile.write(_pij.dumps({"error": f"Bad upload: {_mpe}"}).encode())
                        except BrokenPipeError: pass
                        return
                else:
                    plan_text = clean_text(data.get("plan_text",[""])[0])
                    answers_raw = data.get("answers",[""])[0]
                try: answers = _pij.loads(answers_raw) if answers_raw.strip() else {}
                except Exception: answers = {}
                if not plan_text and not _pi_img_b64:
                    self.send_response(400); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(_pij.dumps({"error":"No plan text or image"}).encode())
                    except BrokenPipeError: pass
                    return
                # API key
                _pi_settings = load_app_settings()
                _pi_key = (_pi_settings.get("family_constraints",{}).get("anthropic_api_key","")
                           or _pi_settings.get("anthropic_api_key","")).strip()
                if not _pi_key:
                    self.send_response(400); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(_pij.dumps({"error":"No API key configured in Settings."}).encode())
                    except BrokenPipeError: pass
                    return
                _today_real = date.today()
                _iso_pi  = _today_real.isoformat()
                _lbl_pi  = _today_real.strftime("%A, %B %d, %Y")
                # Build events summary for conflict context
                _upcoming = _load_upcoming_events(30)
                _ev_summary = _format_events_summary(_upcoming)
                # Build system prompt
                _pi_sys = build_analysis_system_prompt(_iso_pi, _lbl_pi, _ev_summary)
                # Build user message (plan + any answers)
                # Replace any double-quote chars in plan text so Claude can't
                # accidentally embed them unescaped in JSON string values.
                _pi_safe_text = (plan_text
                    .replace('\u201c', '\u2018').replace('\u201d', '\u2019')  # curly → single
                    .replace('"', "'"))                                        # straight → single
                if _pi_safe_text:
                    _pi_user = f"Here is the plan to parse:\n\n{_pi_safe_text}"
                else:
                    _pi_user = ("The plan is in the attached image. Read it carefully "
                                "(including any handwriting), extract every event/task, "
                                "and parse it according to the rules above.")
                if answers:
                    _pi_user += "\n\n== ANSWERS TO PREVIOUS QUESTIONS ==\n"
                    for qid, ans in answers.items():
                        if ans.strip():
                            _pi_user += f"- {qid}: {ans}\n"
                # Build message content: image first (if any), then text
                if _pi_img_b64:
                    _msg_content = [
                        {"type": "image", "source": {
                            "type": "base64",
                            "media_type": _pi_img_mime or "image/png",
                            "data": _pi_img_b64,
                        }},
                        {"type": "text", "text": _pi_user},
                    ]
                else:
                    _msg_content = _pi_user
                _pi_payload = _pij.dumps({
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4000,
                    "system": _pi_sys,
                    "messages": [{"role": "user", "content": _msg_content}],
                    "stream": False,
                }).encode("utf-8")
                _pi_req = _pireq.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=_pi_payload,
                    headers={"x-api-key": _pi_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                )
                import urllib.error as _pi_urlerr

                def _repair_and_parse_json(raw_str):
                    """Try to parse JSON, repairing common LLM mistakes."""
                    # Attempt 1: as-is
                    try: return _pij.loads(raw_str)
                    except Exception: pass
                    # Attempt 2: remove trailing commas before } or ]
                    import re as _re2
                    fixed = _re2.sub(r',(\s*[}\]])', r'\1', raw_str)
                    try: return _pij.loads(fixed)
                    except Exception: pass
                    # Attempt 3: escape literal newlines inside string values
                    def _fix_newlines(s):
                        result, in_str, i = [], False, 0
                        while i < len(s):
                            c = s[i]
                            if c == '"' and (i == 0 or s[i-1] != '\\'):
                                in_str = not in_str
                                result.append(c)
                            elif in_str and c == '\n':
                                result.append('\\n')
                            elif in_str and c == '\r':
                                result.append('\\r')
                            elif in_str and c == '\t':
                                result.append('\\t')
                            else:
                                result.append(c)
                            i += 1
                        return ''.join(result)
                    fixed2 = _fix_newlines(fixed)
                    try: return _pij.loads(fixed2)
                    except Exception: pass
                    # Attempt 4: strip trailing commas again after newline fix
                    fixed3 = _re2.sub(r',(\s*[}\]])', r'\1', fixed2)
                    try: return _pij.loads(fixed3)
                    except Exception: pass
                    # Attempt 5: add missing commas between adjacent string/object/array values
                    # e.g. "val1"\n    "val2" → "val1",\n    "val2"
                    fixed4 = _re2.sub(r'("|\d|true|false|null|}|])\s*\n(\s*)("|\{|\[)', r'\1,\n\2\3', fixed3)
                    try: return _pij.loads(fixed4)
                    except Exception: pass
                    # Attempt 6: combined
                    fixed5 = _re2.sub(r',(\s*[}\]])', r'\1', fixed4)
                    return _pij.loads(fixed5)  # raise if still broken

                try:
                    _pi_resp = _pireq.urlopen(_pi_req, timeout=90)
                    _pi_raw  = _pi_resp.read().decode("utf-8")
                    _pi_body = _pij.loads(_pi_raw)
                    _pi_text = ""
                    _pi_content = _pi_body.get("content", [])
                    for _blk in _pi_content:
                        if isinstance(_blk, dict) and _blk.get("type") == "text":
                            _pi_text = _blk.get("text", "")
                            break
                    if not _pi_text:
                        # Anthropic error object?
                        _pi_err = _pi_body.get("error", {})
                        raise ValueError(f"Empty response from Claude. API said: {_pi_err.get('message', _pi_raw[:200])}")
                    # Extract JSON from ```json ... ``` block
                    _pi_jm = _pire.search(r"```json\s*([\s\S]*?)```", _pi_text)
                    if _pi_jm:
                        _pi_parsed = _repair_and_parse_json(_pi_jm.group(1).strip())
                    else:
                        # Try bare JSON object/array
                        _pi_jm2 = _pire.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", _pi_text)
                        if _pi_jm2:
                            _pi_parsed = _repair_and_parse_json(_pi_jm2.group(1))
                        else:
                            raise ValueError(f"Claude did not return JSON. Response was: {_pi_text[:300]}")
                    # Detect relevant companions
                    from render_plan_importer import detect_relevant_companions, _COMPANION_KEYWORDS
                    _rel_keys = detect_relevant_companions(_pi_parsed)
                    _pi_parsed["_companions"] = [
                        {
                            "key":   k,
                            "label": _COMPANION_KEYWORDS[k]["label"],
                            "color": _COMPANION_KEYWORDS[k]["color"],
                            "emoji": _COMPANION_KEYWORDS[k]["emoji"],
                            "role":  _COMPANION_KEYWORDS[k]["role"],
                        }
                        for k in _rel_keys if k in _COMPANION_KEYWORDS
                    ]
                    # Always persist the full analysis to the server so it
                    # can be recovered even if the browser tab is closed.
                    try:
                        _hist_text = plan_text or "[image upload — no text]"
                        _plan_history.append_entry(_hist_text, _pi_parsed,
                                                   viewer=_pi_v, source="live")
                    except Exception:
                        pass
                    self.send_response(200)
                    self.send_header("Content-Type","application/json; charset=utf-8")
                    self.send_header("Cache-Control","no-store")
                    self.end_headers()
                    try: self.wfile.write(_pij.dumps(_pi_parsed).encode("utf-8"))
                    except BrokenPipeError: pass
                except _pi_urlerr.HTTPError as _pie_http:
                    _pi_err_body = ""
                    try: _pi_err_body = _pie_http.read().decode("utf-8")
                    except Exception: pass
                    try: _pi_err_msg = _pij.loads(_pi_err_body).get("error",{}).get("message", _pi_err_body[:300])
                    except Exception: _pi_err_msg = _pi_err_body[:300] or str(_pie_http)
                    self.send_response(500)
                    self.send_header("Content-Type","application/json; charset=utf-8")
                    self.end_headers()
                    try: self.wfile.write(_pij.dumps({"error": f"API error {_pie_http.code}: {_pi_err_msg}"}).encode())
                    except BrokenPipeError: pass
                except Exception as _pie:
                    self.send_response(500)
                    self.send_header("Content-Type","application/json; charset=utf-8")
                    self.end_headers()
                    try: self.wfile.write(_pij.dumps({"error": str(_pie)}).encode())
                    except BrokenPipeError: pass
                return

            # ── Plan Import — Apply ───────────────────────────────────────────
            elif path == "/plan-import-apply":
                import json as _aij
                _ai_v = self._get_viewer()
                if not (_ai_v and _auth.is_admin(_ai_v)):
                    self.send_response(403); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"Forbidden")
                    except BrokenPipeError: pass
                    return
                # Read raw JSON body
                _ai_cl = int(self.headers.get("Content-Length","0") or 0)
                _ai_raw = self.rfile.read(_ai_cl).decode("utf-8","ignore") if _ai_cl else ""
                try: _ai_payload = _aij.loads(_ai_raw)
                except Exception:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"Invalid JSON")
                    except BrokenPipeError: pass
                    return
                _ai_events = _ai_payload.get("events", [])
                _ai_tasks  = _ai_payload.get("tasks", [])
                _ai_proj   = (_ai_payload.get("project_label") or "").strip()[:60]
                _today_ai  = date.today().isoformat()
                events_added = 0
                tasks_added  = 0
                # Write events
                if _ai_events:
                    try:
                        import uuid as _aiuuid
                        try:
                            with open("data/events.json") as _aief:
                                _aievdata = _aij.load(_aief)
                        except Exception:
                            _aievdata = {"version": 1, "updated_at": _today_ai, "data": []}
                        for ev in _ai_events:
                            if not ev.get("title") or not ev.get("date"):
                                continue
                            _who = [w.strip() for w in (ev.get("who") or ["Lauren"]) if isinstance(w,str) and w.strip()]
                            if not _who:
                                _who = ["Lauren"]
                            _rec = ev.get("recurrence","none")
                            if _rec not in ("none","weekly","monthly","yearly"):
                                _rec = "none"
                            _new_ev = {
                                "id": "evt_" + _aiuuid.uuid4().hex[:8],
                                "title": ev["title"],
                                "assigned_to": _who,
                                "start_date": ev["date"],
                                "end_date": ev.get("end_date") or ev["date"],
                                "start_time": ev.get("time",""),
                                "end_time": ev.get("end_time",""),
                                "recurrence": {"type": _rec},
                                "notifications": {
                                    "show_on_dashboard": True,
                                    "show_on_daily_page": True,
                                    "show_in_looking_ahead": True,
                                    "lead_days": 1,
                                },
                                "prep": {"lead_days": 0},
                                "notes": ev.get("notes",""),
                                "subtasks": [],
                                "archived": False,
                                **({"project": _ai_proj} if _ai_proj else {}),
                            }
                            _aievdata.setdefault("data", []).append(_new_ev)
                            events_added += 1
                        _aievdata["updated_at"] = _today_ai
                        safe_save_json("data/events.json", _aievdata)
                    except Exception as _aieve:
                        pass
                # Write tasks
                if _ai_tasks:
                    try:
                        _all_tasks = load_manual_tasks()
                        for t in _ai_tasks:
                            person = (t.get("person") or "Lauren").strip()
                            text   = (t.get("text") or "").strip()
                            due    = (t.get("due_date") or _today_ai).strip()
                            notes  = (t.get("notes") or "").strip()
                            subtasks = t.get("subtasks") or []
                            if not text:
                                continue
                            _all_tasks.append({
                                "text": text,
                                "assigned_to": person,
                                "due_date": due,
                                "priority": "MEDIUM",
                                "status": "active",
                                "source": "plan_importer",
                                "recurring": False,
                                "notes": notes,
                                "subtasks": subtasks,
                                **({"project": _ai_proj} if _ai_proj else {}),
                            })
                            tasks_added += 1
                        save_manual_tasks(_all_tasks)
                    except Exception:
                        pass
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Cache-Control","no-store")
                self.end_headers()
                try: self.wfile.write(_aij.dumps({
                    "events_added": events_added,
                    "tasks_added": tasks_added,
                }).encode())
                except BrokenPipeError: pass
                return

            # ── Plan Import — Companion Consult (streaming) ───────────────────
            elif path == "/plan-import-consult":
                import json as _cj, urllib.request as _creq
                _cc_v = self._get_viewer()
                if not (_cc_v and _auth.is_admin(_cc_v)):
                    self.send_response(403); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"Forbidden")
                    except BrokenPipeError: pass
                    return
                _cc_companion = clean_text(data.get("companion",[""])[0])
                _cc_message   = clean_text(data.get("message",[""])[0])
                _cc_hist_raw  = data.get("history",["[]"])[0]
                _cc_plan_raw  = data.get("plan_json",["{}"])[0]
                try: _cc_history = _cj.loads(_cc_hist_raw)
                except Exception: _cc_history = []
                try: _cc_plan = _cj.loads(_cc_plan_raw)
                except Exception: _cc_plan = {}
                if not _cc_companion or not _cc_message:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"Missing companion or message")
                    except BrokenPipeError: pass
                    return
                _cc_settings = load_app_settings()
                _cc_key = (_cc_settings.get("family_constraints",{}).get("anthropic_api_key","")
                           or _cc_settings.get("anthropic_api_key","")).strip()
                if not _cc_key:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"No API key configured.")
                    except BrokenPipeError: pass
                    return
                _today_cc   = date.today()
                _iso_cc     = _today_cc.isoformat()
                _weekday_cc = _today_cc.strftime("%A")
                _label_cc   = _today_cc.strftime("%B %d, %Y")
                from render_plan_importer import build_consult_system_prompt
                _cc_sys = build_consult_system_prompt(_cc_companion, _cc_plan, _iso_cc, _weekday_cc, _label_cc)
                # Build messages from history + current message
                _cc_msgs = []
                for _h in _cc_history:
                    _r = _h.get("role","user")
                    _c = _h.get("content","")
                    if _r in ("user","assistant") and _c:
                        _cc_msgs.append({"role": _r, "content": _c})
                _cc_msgs.append({"role": "user", "content": _cc_message})
                _cc_payload = _cj.dumps({
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1200,
                    "system": _cc_sys,
                    "messages": _cc_msgs,
                    "stream": True,
                }).encode("utf-8")
                _cc_req = _creq.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=_cc_payload,
                    headers={"x-api-key": _cc_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                )
                _cc_full_reply = []
                try:
                    _cc_resp = _creq.urlopen(_cc_req, timeout=60)
                    self.send_response(200)
                    self.send_header("Content-Type","text/plain; charset=utf-8")
                    self.send_header("Transfer-Encoding","chunked")
                    self.send_header("Cache-Control","no-store")
                    self.end_headers()
                    for _raw in _cc_resp:
                        _line = _raw.decode("utf-8").strip()
                        if _line.startswith("data:"):
                            _chunk = _line[5:].strip()
                            if _chunk == "[DONE]": break
                            try:
                                _obj   = _cj.loads(_chunk)
                                _delta = _obj.get("delta",{})
                                _piece = _delta.get("text","") if _delta.get("type") == "text_delta" else ""
                                if _piece:
                                    _cc_full_reply.append(_piece)
                                    try: self.wfile.write(_piece.encode("utf-8")); self.wfile.flush()
                                    except BrokenPipeError: break
                            except Exception: pass
                except Exception as _cce:
                    try: self.wfile.write(str(_cce).encode("utf-8"))
                    except BrokenPipeError: pass
                # ── Persist this Plan-Importer chat into the companion's own
                #    history file so they "remember" it next time the user
                #    opens their normal chat page (Lucy, Coach, etc.).
                try:
                    _reply_text = "".join(_cc_full_reply).strip()
                    _reply_text = _strip_hallucinated_tool_use(_reply_text)
                    if _reply_text:
                        _ts_now = datetime.now().isoformat(timespec="seconds")
                        _user_tagged = f"[Plan Importer] {_cc_message}"
                        _appender_map = {
                            "lucy":    "append_lucy_messages",
                            "lorenzo": "append_lorenzo_messages",
                            "gregory": "append_gregory_messages",
                            "coach":   "append_coach_messages",
                            "monica":  "append_monica_messages",
                        }
                        _fn_name = _appender_map.get(_cc_companion.lower())
                        if _fn_name:
                            import data_helpers as _dh
                            _fn = getattr(_dh, _fn_name, None)
                            if _fn:
                                _fn([
                                    {"role": "user",      "content": _user_tagged, "ts": _ts_now},
                                    {"role": "assistant", "content": _reply_text,  "ts": _ts_now},
                                ])
                except Exception:
                    pass
                return

            # ── Plan Import — Group Council (streaming, single call) ───────────
            elif path == "/plan-import-group-consult":
                import json as _gcj, urllib.request as _gcreq
                _gc_v = self._get_viewer()
                if not (_gc_v and _auth.is_admin(_gc_v)):
                    self.send_response(403); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"Forbidden")
                    except BrokenPipeError: pass
                    return
                _gc_question    = clean_text(data.get("question",[""])[0])
                _gc_comp_raw    = data.get("companions",["[]"])[0]
                _gc_plan_raw    = data.get("plan_json",["{}"])[0]
                try: _gc_companions = _gcj.loads(_gc_comp_raw)
                except Exception: _gc_companions = []
                try: _gc_plan = _gcj.loads(_gc_plan_raw)
                except Exception: _gc_plan = {}
                if not _gc_question:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"Missing question")
                    except BrokenPipeError: pass
                    return
                _gc_settings = load_app_settings()
                _gc_key = (_gc_settings.get("family_constraints",{}).get("anthropic_api_key","")
                           or _gc_settings.get("anthropic_api_key","")).strip()
                if not _gc_key:
                    self.send_response(400); self.send_header("Content-Type","text/plain"); self.end_headers()
                    try: self.wfile.write(b"No API key configured.")
                    except BrokenPipeError: pass
                    return
                _today_gc   = date.today()
                _iso_gc     = _today_gc.isoformat()
                _weekday_gc = _today_gc.strftime("%A")
                _label_gc   = _today_gc.strftime("%B %d, %Y")
                from render_plan_importer import build_roundtable_prompt
                _gc_sys = build_roundtable_prompt(
                    _gc_companions, _gc_plan, _gc_question,
                    _iso_gc, _weekday_gc, _label_gc
                )
                _gc_payload = _gcj.dumps({
                    "model": "claude-opus-4-5",
                    "max_tokens": 1800,
                    "system": _gc_sys,
                    "messages": [{"role": "user", "content": f"Please conduct the roundtable on this question: {_gc_question}"}],
                    "stream": True,
                }).encode("utf-8")
                _gc_req = _gcreq.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=_gc_payload,
                    headers={"x-api-key": _gc_key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                )
                _gc_full_reply = []
                try:
                    _gc_resp = _gcreq.urlopen(_gc_req, timeout=90)
                    self.send_response(200)
                    self.send_header("Content-Type","text/plain; charset=utf-8")
                    self.send_header("Transfer-Encoding","chunked")
                    self.send_header("Cache-Control","no-store")
                    self.end_headers()
                    for _raw in _gc_resp:
                        _line = _raw.decode("utf-8").strip()
                        if _line.startswith("data:"):
                            _chunk = _line[5:].strip()
                            if _chunk == "[DONE]": break
                            try:
                                _obj   = _gcj.loads(_chunk)
                                _delta = _obj.get("delta",{})
                                _piece = _delta.get("text","") if _delta.get("type") == "text_delta" else ""
                                if _piece:
                                    _gc_full_reply.append(_piece)
                                    try: self.wfile.write(_piece.encode("utf-8")); self.wfile.flush()
                                    except BrokenPipeError: break
                            except Exception: pass
                except Exception as _gce:
                    try: self.wfile.write(str(_gce).encode("utf-8"))
                    except BrokenPipeError: pass
                # ── Persist roundtable into every participating companion's
                #    history file so each one remembers what was said.
                try:
                    _gc_reply_text = "".join(_gc_full_reply).strip()
                    _gc_reply_text = _strip_hallucinated_tool_use(_gc_reply_text)
                    if _gc_reply_text:
                        _gc_ts  = datetime.now().isoformat(timespec="seconds")
                        _gc_um  = f"[Plan Importer · Roundtable] {_gc_question}"
                        _gc_map = {
                            "lucy":    "append_lucy_messages",
                            "lorenzo": "append_lorenzo_messages",
                            "gregory": "append_gregory_messages",
                            "coach":   "append_coach_messages",
                            "monica":  "append_monica_messages",
                        }
                        # Always include Lucy (she always moderates) plus any
                        # explicit participants the client passed in.
                        _gc_keys = {str(_k).lower() for _k in _gc_companions if _k}
                        _gc_keys.add("lucy")
                        import data_helpers as _gc_dh
                        for _k in _gc_keys:
                            _fn_name = _gc_map.get(_k)
                            if not _fn_name: continue
                            _fn = getattr(_gc_dh, _fn_name, None)
                            if not _fn: continue
                            try:
                                _fn([
                                    {"role": "user",      "content": _gc_um,         "ts": _gc_ts},
                                    {"role": "assistant", "content": _gc_reply_text, "ts": _gc_ts},
                                ])
                            except Exception:
                                pass
                except Exception:
                    pass
                return

            elif path in ("/calendar-config-save","/calendar-save-config"):
                apple_id=clean_text(data.get("apple_id",[""])[0]); app_password=clean_text(data.get("app_password",[""])[0])
                cfg=load_calendar_config()
                if apple_id: cfg["apple_id"]=apple_id
                if app_password: cfg["app_password"]=app_password
                save_calendar_config(cfg)
                if path=="/calendar-config-save": refresh_calendar(force=True)
                redirect="/calendar#top"

            elif path == "/calendar-approve":
                tk=clean_text(data.get("title_key",[""])[0]).lower(); d=clean_text(data.get("decision",[""])[0])
                if tk and d in ("show_boys","mom_only","skip"):
                    rules=load_calendar_rules(); rules.setdefault("rules",{})[tk]=d; save_calendar_rules(rules)
                redirect="/calendar#top"

            elif path == "/planner-add-task":
                text=clean_text(data.get("text",[""])[0])
                if text:
                    tasks=load_manual_tasks(); tasks.append({"text":text,"assigned_to":"Mom","due_date":"","priority":"MEDIUM","status":"active","recurring":False}); save_manual_tasks(tasks)
                redirect="/planner#top"

            elif path == "/subscribed-cal-add":
                name=clean_text(data.get("name",[""])[0]); url=clean_text(data.get("url",[""])[0]); color=clean_text(data.get("color",["#9b59b6"])[0])
                if name and url:
                    cals=load_subscribed_calendars(); cals.append({"id":str(uuid.uuid4()),"name":name,"url":url,"color":color,"enabled":True}); save_subscribed_calendars(cals)
                redirect="/calendar#top"

            elif path == "/subscribed-cal-toggle":
                idx_in = safe_int(data.get("index",["0"])[0], 0)
                cals   = load_subscribed_calendars()
                if 0 <= idx_in < len(cals):
                    cals[idx_in]["enabled"] = not cals[idx_in].get("enabled", True)
                    save_subscribed_calendars(cals)
                redirect = "/settings#s-integrations"

            elif path == "/subscribed-cal-delete":
                idx=safe_int(data.get("index",["0"])[0],0); cals=load_subscribed_calendars()
                if 0<=idx<len(cals): cals.pop(idx)
                save_subscribed_calendars(cals); redirect="/calendar#top"

            elif path == "/calendar-refresh":
                refresh_calendar(force=True)
                from render_calendar import refresh_subscribed_calendars
                refresh_subscribed_calendars(force=True)
                redirect="/calendar#top"

            elif path in ("/family-schedule-save", "/settings-schedule-save"):
                # Write slot__{day}__{ts} updates into FROL day templates (Mom column)
                import json as _fsj
                from pathlib import Path as _fsp
                _day_changes: dict = {}
                for key, val_list in data.items():
                    if key.startswith("slot__"):
                        parts = key.split("__", 2)
                        if len(parts) == 3:
                            _, _fday, _fts = parts
                            _day_changes.setdefault(_fday, {})[_fts] = clean_text(val_list[0])
                for _fday, _slots in _day_changes.items():
                    _tp = _fsp(f"data/day_templates/{_fday}.json")
                    _td = _fsj.loads(_tp.read_text("utf-8")) if _tp.exists() else {"weekday": _fday, "grid": {}}
                    for _fts, _fval in _slots.items():
                        _td.setdefault("grid", {}).setdefault("Mom", {})[_fts] = _fval
                    save_day_template(_fday, _td)
                redirect="/settings?msg=Schedule+saved#s-systems"

            elif path == "/roadmap-add":
                title=clean_text(data.get("title",[""])[0]); nt=clean_text(data.get("notes",[""])[0]); status=clean_text(data.get("status",["Someday"])[0])
                if status not in ROADMAP_STATUSES: status="Someday"
                if title:
                    ideas=load_roadmap(); ideas.append({"id":str(uuid.uuid4()),"title":title,"notes":nt,"status":status}); save_roadmap(ideas)
                redirect="/roadmap#top"

            elif path == "/roadmap-update":
                idea_id=clean_text(data.get("id",[""])[0]); nt=clean_text(data.get("notes",[""])[0]); status=clean_text(data.get("status",["Someday"])[0])
                if status not in ROADMAP_STATUSES: status="Someday"
                ideas=load_roadmap()
                for idea in ideas:
                    if str(idea.get("id",""))==idea_id: idea["notes"]=nt; idea["status"]=status; break
                save_roadmap(ideas); redirect="/roadmap#top"

            elif path == "/roadmap-delete":
                idea_id=clean_text(data.get("id",[""])[0])
                save_roadmap([i for i in load_roadmap() if str(i.get("id",""))!=idea_id]); redirect="/roadmap#top"

            elif path == "/liturgical-save":
                ds=clean_text(data.get("date",[""])[0]); nm=clean_text(data.get("name",[""])[0]); nt=clean_text(data.get("notes",[""])[0]); col=clean_text(data.get("color",[""])[0])
                try: date.fromisoformat(ds); valid=True
                except: valid=False
                if valid and (nm or nt or col):
                    custom=load_liturgical_custom(); custom[ds]={"name":nm,"notes":nt,"color":col}; save_liturgical_custom(custom)
                redirect="/liturgical#top"

            elif path == "/liturgical-delete":
                ds=clean_text(data.get("date",[""])[0]); custom=load_liturgical_custom(); custom.pop(ds,None); save_liturgical_custom(custom); redirect="/liturgical#top"

            elif path == "/liturgical-note":
                ds=clean_text(data.get("date",[""])[0]); fn=clean_text(data.get("family_note",[""])[0])
                try: date.fromisoformat(ds); valid=True
                except: valid=False
                if valid:
                    custom=load_liturgical_custom(); custom.setdefault(ds,{})["family_note"]=fn; save_liturgical_custom(custom)
                redirect="/liturgical#top"

            elif path == "/settings-save-ajax":
                # AJAX autosave — accepts same form fields, returns JSON
                import json as _json
                from daily_schedule_engine import CHILDREN as _CHILDREN
                _settings = load_app_settings()
                fn = clean_text(data.get("family_name",[""])[0])
                if fn: _settings["family_name"] = fn
                tz = clean_text(data.get("timezone",[""])[0])
                if tz: _settings["timezone"] = tz
                loc = clean_text(data.get("location",[""])[0])
                _settings["location"] = loc
                sh = safe_int(data.get("schedule_start_hour",["6"])[0], 6)
                eh = safe_int(data.get("schedule_end_hour",["22"])[0], 22)
                _settings["schedule_start_hour"] = max(0, min(sh, 21))
                _settings["schedule_end_hour"]   = max(_settings["schedule_start_hour"]+1, min(eh, 24))
                ve = clean_text(data.get("van_epoch",[""])[0])
                try: date.fromisoformat(ve); _settings["van_epoch"] = ve
                except Exception: pass
                colors = _settings.get("child_colors", {})
                for _c in _CHILDREN:
                    ce = _c.replace(" ","_")
                    bg    = clean_text(data.get(f"color_bg_{ce}",   [""])[0])
                    txt   = clean_text(data.get(f"color_text_{ce}", [""])[0])
                    light = clean_text(data.get(f"color_light_{ce}",[""])[0])
                    if bg or txt or light:
                        colors[_c] = {
                            "bg":    bg    if bg    else colors.get(_c,{}).get("bg","#888"),
                            "text":  txt   if txt   else colors.get(_c,{}).get("text","#fff"),
                            "light": light if light else colors.get(_c,{}).get("light","#f5f5f5"),
                        }
                _settings["child_colors"] = colors
                fc_keys = ["anthropic_api_key","james_schedule","supervision_rules",
                           "independence_notes","school_durations","mom_supervision_subjects",
                           "meal_prep","other_notes","family_exercise",
                           "school_mode","core_subjects","paused_subjects"]
                constraints = _settings.get("family_constraints", {})
                for k in fc_keys:
                    val = clean_text(data.get(f"fc_{k}", [""])[0])
                    if val or f"fc_{k}" in data:
                        # Never blank out the API key — only update if a real value sent
                        if k == "anthropic_api_key" and not val:
                            pass
                        else:
                            constraints[k] = val
                _settings["family_constraints"] = constraints
                birthdays = _settings.get("child_birthdays", {})
                for _c in _CHILDREN:
                    ce  = _c.replace(" ","_")
                    dob = clean_text(data.get(f"birthday_{ce}", [""])[0])
                    if dob:
                        try: date.fromisoformat(dob); birthdays[_c] = dob
                        except Exception: pass
                _settings["child_birthdays"] = birthdays
                events = []
                for i in range(10):
                    lbl = clean_text(data.get(f"event_label_{i}", [""])[0])
                    edt = clean_text(data.get(f"event_date_{i}",  [""])[0])
                    if lbl: events.append({"label": lbl, "date": edt})
                _settings["special_events"] = events
                theme_val = clean_text(data.get("color_theme", ["ivory"])[0])
                if theme_val in {"ivory","parchment","night","minimal","liturgical"}:
                    _settings["color_theme"] = theme_val
                # Boolean toggles — only update if the sentinel field is present
                # (prevents autosave from wiping toggles when only other fields changed)
                if "cycle_fields_section" in data:
                    _settings["cycle_show_detail_fields"] = "cycle_show_detail_fields" in data
                if "liturgy_section" in data:
                    _settings["show_liturgy_hours_widget"] = "show_liturgy_hours_widget" in data
                    _settings["auto_fetch_hours"]           = "auto_fetch_hours" in data
                    uc = clean_text(data.get("universalis_country", ["United States"])[0])
                    _settings["universalis_country"] = uc
                # Meal rules passed as JSON string
                meal_rules_raw = data.get("meal_rules_json", [""])[0]
                if meal_rules_raw:
                    try:
                        import json as _mrj
                        _settings["meal_rules"] = _mrj.loads(meal_rules_raw)
                    except Exception: pass
                save_app_settings(_settings)
                # Schedule grid slots → write to FROL day templates (Mom column)
                import json as _saj; from pathlib import Path as _sap
                _saj_changes: dict = {}
                for key, val_list in data.items():
                    if key.startswith("slot__"):
                        parts = key.split("__", 2)
                        if len(parts) == 3:
                            _, _saday, _sats = parts
                            _saj_changes.setdefault(_saday, {})[_sats] = clean_text(val_list[0])
                for _saday, _saslots in _saj_changes.items():
                    _satp = _sap(f"data/day_templates/{_saday}.json")
                    _satd = _saj.loads(_satp.read_text("utf-8")) if _satp.exists() else {"weekday": _saday, "grid": {}}
                    for _sats, _saval in _saslots.items():
                        _satd.setdefault("grid", {}).setdefault("Mom", {})[_sats] = _saval
                    save_day_template(_saday, _satd)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/settings-save":
                from daily_schedule_engine import CHILDREN as _CHILDREN
                settings = load_app_settings()
                # General
                fn = clean_text(data.get("family_name",[""])[0])
                if fn: settings["family_name"] = fn
                tz = clean_text(data.get("timezone",[""])[0])
                if tz: settings["timezone"] = tz
                loc = clean_text(data.get("location",[""])[0])
                settings["location"] = loc
                # Schedule hours
                sh = safe_int(data.get("schedule_start_hour",["6"])[0], 6)
                eh = safe_int(data.get("schedule_end_hour",["22"])[0], 22)
                settings["schedule_start_hour"] = max(0, min(sh, 21))
                settings["schedule_end_hour"]   = max(settings["schedule_start_hour"]+1, min(eh, 24))
                # Van epoch
                ve = clean_text(data.get("van_epoch",[""])[0])
                try:
                    date.fromisoformat(ve)
                    settings["van_epoch"] = ve
                except Exception:
                    pass
                # Child colors
                colors = settings.get("child_colors", {})
                for child in _CHILDREN:
                    ce = child.replace(" ","_")
                    bg    = clean_text(data.get(f"color_bg_{ce}",   [""])[0])
                    text  = clean_text(data.get(f"color_text_{ce}", [""])[0])
                    light = clean_text(data.get(f"color_light_{ce}",[""])[0])
                    if bg or text or light:
                        colors[child] = {
                            "bg":    bg    if bg    else colors.get(child,{}).get("bg","#888"),
                            "text":  text  if text  else colors.get(child,{}).get("text","#fff"),
                            "light": light if light else colors.get(child,{}).get("light","#f5f5f5"),
                        }
                settings["child_colors"] = colors
                # Plan columns
                plan_cols = data.get("plan_columns", [])
                if isinstance(plan_cols, list):
                    settings["plan_columns"] = [clean_text(p) for p in plan_cols if clean_text(p)]
                # Family constraints (fc_ prefix)
                fc_keys = [
                    "anthropic_api_key", "james_schedule", "supervision_rules",
                    "independence_notes", "school_durations", "mom_supervision_subjects",
                    "meal_prep", "other_notes", "family_exercise",
                    "school_mode", "core_subjects", "paused_subjects",
                ]
                constraints = settings.get("family_constraints", {})
                for k in fc_keys:
                    val = clean_text(data.get(f"fc_{k}", [""])[0])
                    # Never overwrite API key with blank — only update if a value was sent
                    if k == "anthropic_api_key":
                        if val: constraints[k] = val
                    else:
                        constraints[k] = val
                settings["family_constraints"] = constraints
                # Child birthdays
                birthdays = settings.get("child_birthdays", {})
                for child in _CHILDREN:
                    ce  = child.replace(" ","_")
                    dob = clean_text(data.get(f"birthday_{ce}", [""])[0])
                    if dob:
                        try: date.fromisoformat(dob); birthdays[child] = dob
                        except Exception: pass
                    elif f"birthday_{ce}" in data:
                        birthdays.pop(child, None)
                settings["child_birthdays"] = birthdays
                # Special events
                events = []
                for i in range(10):
                    label = clean_text(data.get(f"event_label_{i}", [""])[0])
                    edate = clean_text(data.get(f"event_date_{i}",  [""])[0])
                    if label:
                        events.append({"label": label, "date": edate})
                settings["special_events"] = events
                # Color theme
                theme_val = clean_text(data.get("color_theme", ["ivory"])[0])
                valid_themes = {"ivory", "parchment", "night", "minimal", "liturgical"}
                if theme_val in valid_themes:
                    settings["color_theme"] = theme_val
                # Cycle detail fields toggle
                if "cycle_fields_section" in data:
                    settings["cycle_show_detail_fields"] = "cycle_show_detail_fields" in data
                # Liturgy of the Hours toggles
                if "liturgy_section" in data:
                    settings["show_liturgy_hours_widget"] = "show_liturgy_hours_widget" in data
                    settings["auto_fetch_hours"]           = "auto_fetch_hours" in data
                    uc2 = clean_text(data.get("universalis_country", ["United States"])[0])
                    settings["universalis_country"] = uc2
                save_app_settings(settings)
                print(f"[SETTINGS] Saved location={repr(settings.get('location'))}, keys={list(settings.keys())}")
                # Verify the file was written
                import json as _json
                try:
                    _verify = _json.load(open("data/app_settings.json"))
                    print(f"[SETTINGS] Verified on disk: location={repr(_verify.get('location'))}")
                except Exception as _ve:
                    print(f"[SETTINGS] WARNING: Could not verify file: {_ve}")
                # Also save schedule grid slots if included → write to FROL day templates
                import json as _ssj; from pathlib import Path as _ssp
                _ss_changes: dict = {}
                for key, val_list in data.items():
                    if key.startswith("slot__"):
                        parts = key.split("__", 2)
                        if len(parts) == 3:
                            _, _ssday, _ssts = parts
                            _ss_changes.setdefault(_ssday, {})[_ssts] = clean_text(val_list[0])
                for _ssday, _ssslots in _ss_changes.items():
                    _sstp = _ssp(f"data/day_templates/{_ssday}.json")
                    _sstd = _ssj.loads(_sstp.read_text("utf-8")) if _sstp.exists() else {"weekday": _ssday, "grid": {}}
                    for _ssts, _ssval in _ssslots.items():
                        _sstd.setdefault("grid", {}).setdefault("Mom", {})[_ssts] = _ssval
                    save_day_template(_ssday, _sstd)
                _ret_ss = clean_text(data.get("_return",[""])[0])
                redirect = _ret_ss if _ret_ss else "/settings?msg=Settings+saved#top"

            elif path == "/school-settings-save":
                import json as _json
                _ss = load_app_settings()
                _fc = _ss.setdefault("family_constraints", {})
                mode   = clean_text(data.get("fc_school_mode",   ["normal"])[0])
                core   = clean_text(data.get("fc_core_subjects",  [""])[0])
                paused = clean_text(data.get("fc_paused_subjects",[""])[0])
                if mode in ("normal", "light_week", "custom_pause"):
                    _fc["school_mode"] = mode
                _fc["core_subjects"]   = core
                _fc["paused_subjects"] = paused
                _ss["family_constraints"] = _fc
                save_app_settings(_ss)
                # Clear the school filter cache so schedule reflects change immediately
                try:
                    import daily_schedule_engine as _dse
                    _dse._SCHOOL_FILTER_CACHE = None
                    _dse._SCHOOL_FILTER_TIME  = 0.0
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-goal-add":
                import json as _json
                from render_child_goals import add_child_goal
                _child  = clean_text(data.get("child",[""])[0])
                _title  = clean_text(data.get("title",[""])[0])
                _cat    = clean_text(data.get("category",["Spiritual Formation"])[0])
                _why    = clean_text(data.get("why",[""])[0])
                _dl     = clean_text(data.get("deadline",[""])[0])
                _rev    = clean_text(data.get("review_frequency",["weekly"])[0])
                if _child and _title:
                    add_child_goal(_child, _title, _cat, _why, _dl, _rev)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-goal-archive":
                import json as _json
                from render_child_goals import update_child_goal
                _child  = clean_text(data.get("child",[""])[0])
                _gid    = clean_text(data.get("goal_id",[""])[0])
                if _child and _gid:
                    update_child_goal(_child, _gid, {"archived": True})
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-substep-add":
                import json as _json
                from render_child_goals import add_substep
                _child  = clean_text(data.get("child",[""])[0])
                _gid    = clean_text(data.get("goal_id",[""])[0])
                _text   = clean_text(data.get("text",[""])[0])
                step    = {}
                if _child and _gid and _text:
                    step = add_substep(_child, _gid, _text)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": bool(step), "step": step}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-substep-toggle":
                import json as _json
                from render_child_goals import toggle_substep
                _child  = clean_text(data.get("child",[""])[0])
                _gid    = clean_text(data.get("goal_id",[""])[0])
                _sid    = clean_text(data.get("step_id",[""])[0])
                _done   = False
                if _child and _gid and _sid:
                    _done = toggle_substep(_child, _gid, _sid)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True, "done": _done}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-substep-delete":
                import json as _json
                from render_child_goals import delete_substep
                _child  = clean_text(data.get("child",[""])[0])
                _gid    = clean_text(data.get("goal_id",[""])[0])
                _sid    = clean_text(data.get("step_id",[""])[0])
                if _child and _gid and _sid:
                    delete_substep(_child, _gid, _sid)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/calendar-add-event":
                import json as _json
                ev_date  = clean_text(data.get("date",[""])[0]) or date.today().isoformat()
                ev_title = clean_text(data.get("title",[""])[0])
                ev_start = clean_text(data.get("start_time",[""])[0])
                ev_end   = clean_text(data.get("end_time",[""])[0])
                ev_notes = clean_text(data.get("notes",[""])[0])
                if ev_title:
                    from data_helpers import load_calendar_cache, save_calendar_cache
                    cache  = load_calendar_cache()
                    events = cache.get("events", [])
                    start_iso = f"{ev_date}T{ev_start}:00" if ev_start else ev_date
                    end_iso   = f"{ev_date}T{ev_end}:00"   if ev_end   else ev_date
                    events.append({
                        "title":    ev_title,
                        "start":    start_iso,
                        "end":      end_iso,
                        "all_day":  not bool(ev_start),
                        "calendar": "Manual",
                        "color":    "#8b5a3c",
                        "location": ev_notes,
                        "id":       str(uuid.uuid4()),
                    })
                    save_calendar_cache({"events": events, "fetched_at": datetime.now().isoformat()})
                redirect = "/mom#calendar"

            elif path == "/calendar-event-delete":
                _ev_id = clean_text(data.get("id",[""])[0])
                if _ev_id:
                    from data_helpers import load_calendar_cache, save_calendar_cache
                    _cache  = load_calendar_cache()
                    _events = [e for e in _cache.get("events",[]) if e.get("id","") != _ev_id]
                    save_calendar_cache({"events": _events, "fetched_at": datetime.now().isoformat()})
                redirect = clean_text(data.get("return_url",["/"])[0]) or "/"

            elif path == "/cycle-log-add":
                import json as _json, os as _os
                from datetime import date as _date
                day1 = clean_text(data.get("day1",[""])[0])
                note = clean_text(data.get("note",[""])[0])
                if day1:
                    CYCLE_LOG = "data/cycle_log.json"
                    try:
                        with open(CYCLE_LOG) as f:
                            log = _json.load(f)
                    except Exception:
                        log = []
                    log = [e for e in log if e.get("day1") != day1]
                    log.append({"day1": day1, "note": note, "logged": _date.today().isoformat()})
                    safe_save_json(CYCLE_LOG, log)
                _ret = clean_text(data.get("_return",[""])[0]) or "/settings#s-cycle"
                redirect = _ret + ("&" if "?" in _ret else "?") + "msg=saved"

            elif path == "/cycle-log-delete":
                import json as _json
                day1 = clean_text(data.get("day1",[""])[0])
                CYCLE_LOG = "data/cycle_log.json"
                try:
                    with open(CYCLE_LOG) as f:
                        log = _json.load(f)
                    log = [e for e in log if e.get("day1") != day1]
                    safe_save_json(CYCLE_LOG, log)
                except Exception:
                    pass
                _ret2 = clean_text(data.get("_return",[""])[0]) or "/settings#s-cycle"
                redirect = _ret2 + ("&" if "?" in _ret2 else "?") + "msg=deleted"

            elif path == "/add-to-plan-quick":
                from datetime import date as _date
                from render_daily_plan import add_item_to_plan
                iso_q  = clean_text(data.get("iso",[""])[0]) or _date.today().isoformat()
                text_q = clean_text(data.get("text",[""])[0])
                src_q  = clean_text(data.get("source",["manual"])[0])
                if text_q:
                    add_item_to_plan(iso_q, text_q, source=src_q)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/cycle-ai-suggest":
                import json as _json
                raw  = data.get("data",["{}"])[0]
                try:    payload = _json.loads(raw)
                except: payload = {}

                phase     = clean_text(payload.get("phase","unknown"))
                cycle_day = clean_text(payload.get("cycle_day",""))
                energy    = clean_text(payload.get("energy",""))
                mood      = clean_text(payload.get("mood",""))
                symptoms  = clean_text(payload.get("symptoms",""))
                stress    = clean_text(payload.get("stress",""))

                settings  = load_app_settings()
                api_key   = (settings.get("anthropic_api_key","")
                             or settings.get("family_constraints",{}).get("anthropic_api_key","")
                             or settings.get("fc_anthropic_api_key",""))

                if not api_key:
                    resp_json = _json.dumps({"error": "No API key set in Settings."}).encode()
                else:
                    try:
                        import urllib.request as _ur
                        prompt = (
                            f"You are a supportive, practical assistant for a Catholic homeschool mother. "
                            f"She is on cycle day {cycle_day or 'unknown'}, in her {phase} phase. "
                            f"Energy: {energy or 'not specified'}. Mood: {mood or 'not specified'}. "
                            f"Symptoms: {symptoms or 'none noted'}. Stress: {stress or 'not specified'}.\n\n"
                            f"Give her 3-5 sentences of warm, practical, research-based guidance for today. "
                            f"Cover: (1) what her body needs today, (2) what kinds of tasks she's best suited for, "
                            f"(3) one specific suggestion for her home or school day. "
                            f"Be specific, warm, and brief. No bullet points — flowing prose. "
                            f"Do not mention cycle phases by clinical name unless relevant."
                        )
                        req_body = _json.dumps({
                            "model": "claude-haiku-4-5-20251001",
                            "max_tokens": 300,
                            "messages": [{"role": "user", "content": prompt}]
                        }).encode()
                        req = _ur.Request(
                            "https://api.anthropic.com/v1/messages",
                            data=req_body,
                            headers={"Content-Type":"application/json",
                                     "x-api-key": api_key,
                                     "anthropic-version":"2023-06-01"}
                        )
                        with _ur.urlopen(req, timeout=20) as r:
                            result = _json.loads(r.read())
                        suggestion = result["content"][0]["text"].strip()
                        resp_json  = _json.dumps({"suggestion": suggestion}).encode()
                    except Exception as ex:
                        resp_json = _json.dumps({"error": f"AI error: {str(ex)[:80]}"}).encode()

                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(resp_json)
                except BrokenPipeError: pass
                return
            elif path == "/cycle-save":
                import json as _json, os as _os
                from datetime import date as _date
                iso_c  = clean_text(data.get("iso",[""])[0]) or _date.today().isoformat()
                raw_c  = data.get("data",["{}"])[0]
                try:   entry = _json.loads(raw_c)
                except: entry = {}
                allowed = {"phase","cycle_day","energy","mood","symptoms","sleep","cravings","stress"}
                entry = {k: clean_text(str(v)) for k,v in entry.items() if k in allowed}
                month_key  = iso_c[:7]
                cycle_dir  = "data/cycle"
                _os.makedirs(cycle_dir, exist_ok=True)
                cycle_file = f"{cycle_dir}/{month_key}.json"
                try:
                    with open(cycle_file) as f:
                        month_data = _json.load(f)
                except Exception:
                    month_data = {}
                month_data[iso_c] = entry
                safe_save_json(cycle_file, month_data)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/meal-save-plan":
                import json as _json
                wk    = clean_text(data.get("week",[""])[0]) or _week_key()
                raw   = data.get("days",["{}"])[0]
                try:   days_in = _json.loads(raw)
                except: days_in = {}
                plan = load_meal_plan(wk)
                for day, slots in days_in.items():
                    if day not in plan["days"]: plan["days"][day] = {}
                    for slot, val in slots.items():
                        plan["days"][day][slot] = clean_text(val)
                plan["week"]  = wk
                plan["start"] = wk
                save_meal_plan(plan)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/kids-week-save":
                import json as _json
                wk_in   = clean_text(data.get("week",[""])[0])
                raw_in  = data.get("data",["{}"])[0]
                try:
                    plan_in = _json.loads(raw_in)
                    if not wk_in:
                        wk_in = plan_in.get("week","")
                    if wk_in:
                        from render_kids_week import save_week_plan
                        plan_in["week"] = wk_in
                        save_week_plan(plan_in)
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return
            elif path == "/meal-rule-add":
                import json as _json
                rule_text = clean_text(data.get("rule",[""])[0])
                RULES_FILE = "data/meal_rules.json"
                if rule_text:
                    try:
                        with open(RULES_FILE) as f:
                            rules = _json.load(f)
                    except Exception:
                        rules = []
                    rules.append({"rule": rule_text})
                    safe_save_json(RULES_FILE, rules)
                redirect = "/settings?msg=Rule+added#s-meals"

            elif path == "/meal-rule-delete":
                import json as _json
                RULES_FILE = "data/meal_rules.json"
                try:
                    idx = int(data.get("rule_index",["0"])[0])
                    with open(RULES_FILE) as f:
                        rules = _json.load(f)
                    if 0 <= idx < len(rules):
                        rules.pop(idx)
                    safe_save_json(RULES_FILE, rules)
                except Exception:
                    pass
                redirect = "/settings?msg=Rule+removed#s-meals"

            elif path == "/meal-save-inventory":
                import json as _json
                raw = data.get("data",["{}"])[0]
                try:   inv_in = _json.loads(raw)
                except: inv_in = {}
                inv = load_inventory()
                for k in ("fridge","freezer","pantry","use_soon"):
                    if k in inv_in: inv[k] = clean_text(inv_in[k])
                from datetime import date as _date
                inv["last_updated"] = _date.today().isoformat()
                save_inventory(inv)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/meal-generate":
                import json as _json, requests as _req
                wk     = clean_text(data.get("week",[""])[0]) or _week_key()
                raw_inv = data.get("inventory",["{}"])[0]
                try:   inv_in = _json.loads(raw_inv)
                except: inv_in = {}
                # Save inventory first
                inv = load_inventory()
                for k in ("fridge","freezer","pantry","use_soon"):
                    if k in inv_in: inv[k] = clean_text(inv_in[k])
                save_inventory(inv)
                # Get cycle phase and capacity from today's anchor
                from render_morning_anchor import _get_anchor_state
                from datetime import date as _date
                anchor = _get_anchor_state(_date.today().isoformat())
                cycle_phase = anchor.get("cycle_phase","")
                capacity    = anchor.get("capacity","")
                # Build prompt (include any saved constraints for this week)
                _plan_for_constraints = load_meal_plan(wk)
                _constraints_for_gen  = _plan_for_constraints.get("constraints","")
                prompt = _build_meal_prompt(inv, cycle_phase, capacity,
                                            constraints=_constraints_for_gen)
                # Call Anthropic API
                settings = load_app_settings()
                api_key  = (settings.get("anthropic_api_key","")
                            or settings.get("family_constraints",{}).get("anthropic_api_key",""))
                if not api_key:
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    self.end_headers()
                    try: self.wfile.write(_json.dumps({"error":"No API key set in Settings"}).encode())
                    except BrokenPipeError: pass
                    return
                try:
                    resp = _req.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-sonnet-4-20250514",
                            "max_tokens": 4096,
                            "messages": [{"role":"user","content": prompt}],
                        },
                        timeout=90,
                    )
                    resp.raise_for_status()
                    resp_json = resp.json()
                    text = "".join(
                        b.get("text","") for b in resp_json.get("content",[])
                        if b.get("type") == "text"
                    )
                    # Extract JSON from response — multi-strategy robust parse
                    import re as _re
                    parsed = {}
                    # Strategy 1: JSON inside ```json ... ``` fences
                    fence_m = _re.search(r'```json\s*([\s\S]*?)\s*```', text)
                    candidates = []
                    if fence_m:
                        candidates.append(fence_m.group(1))
                    # Strategy 2: outermost {...} block
                    brace_m = _re.search(r'\{[\s\S]*\}', text)
                    if brace_m:
                        candidates.append(brace_m.group())
                    for cand in candidates:
                        try:
                            parsed = _json.loads(cand)
                            break
                        except _json.JSONDecodeError:
                            # Strategy 3: strip trailing commas before } or ]
                            cleaned = _re.sub(r',\s*([}\]])', r'\1', cand)
                            try:
                                parsed = _json.loads(cleaned)
                                break
                            except Exception:
                                pass
                    # Extract the day plan (7 day keys) vs metadata
                    from render_meals import DAYS as _DAYS
                    if not parsed:
                        raise ValueError("Claude response could not be parsed as JSON. Raw: " + text[:400])
                    days_out = {d: parsed.get(d,{}) for d in _DAYS}
                    grocery_gaps  = parsed.get("grocery_gaps", [])
                    prep_notes    = parsed.get("prep_notes", {})
                    use_soon_used = parsed.get("use_soon_used", [])
                    # Save plan
                    plan = load_meal_plan(wk)
                    plan["days"]          = days_out
                    plan["grocery_gaps"]  = grocery_gaps
                    plan["prep_notes"]    = prep_notes
                    plan["use_soon_used"] = use_soon_used
                    plan["generated"]     = True
                    plan["week"]          = wk
                    plan["start"]         = wk
                    save_meal_plan(plan)
                    result = {
                        "ok": True,
                        "days": days_out,
                        "grocery_gaps": grocery_gaps,
                        "prep_notes": prep_notes,
                        "use_soon_used": use_soon_used,
                    }
                except Exception as e:
                    result = {"error": str(e)}
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/meal-save-constraints":
                import json as _json
                wk_c  = clean_text(data.get("week",[""])[0]) or _week_key()
                constr = data.get("constraints",[""])[0]
                plan_c = load_meal_plan(wk_c)
                plan_c["constraints"] = constr
                save_meal_plan(plan_c)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/meal-edit":
                import json as _json, re as _re, requests as _req
                wk_e    = clean_text(data.get("week",[""])[0]) or _week_key()
                message = clean_text(data.get("message",[""])[0])
                raw_days = data.get("days",["{}"])[0]
                constraints = data.get("constraints",[""])[0]
                try:    client_days = _json.loads(raw_days)
                except: client_days = {}
                # Load family rules for the prompt
                rules_e = load_meal_rules()
                # Get API key
                settings_e = load_app_settings()
                api_key_e  = (settings_e.get("anthropic_api_key","")
                              or settings_e.get("family_constraints",{}).get("anthropic_api_key",""))
                if not api_key_e:
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    self.end_headers()
                    try: self.wfile.write(_json.dumps({"error":"No API key set in Settings"}).encode())
                    except BrokenPipeError: pass
                    return
                # Build prompt
                current_plan_json = _json.dumps({"days": client_days}, indent=2)
                rules_summary = "\n".join(
                    f"- {k}: {v}" for k,v in rules_e.items()
                ) if isinstance(rules_e, dict) else str(rules_e)
                edit_prompt = (
                    "You are a meal planning assistant for the McAdams Catholic homeschool family "
                    "(Lauren/mom, John/dad, JP 14, Joseph 12, Michael 5, James 13mo).\n\n"
                    "CURRENT WEEK PLAN:\n" + current_plan_json + "\n\n"
                    "FAMILY RULES (fixed, do not violate):\n"
                    "- Tuesday: leftovers day\n"
                    "- Friday: meatless (fish or vegetarian)\n"
                    "- Sunday dinner: Ziplock Buffet (leftovers)\n"
                    "- Dad needs a packable lunch every weekday\n"
                    "- Each boy (JP, Joseph, Michael) gets a specific dinner-prep task daily\n"
                    + (rules_summary + "\n" if rules_summary else "") +
                    ("\nSTANDING CONSTRAINTS:\n" + constraints + "\n" if constraints.strip() else "") +
                    "\nUSER INSTRUCTION:\n" + message + "\n\n"
                    "Apply the instruction carefully. "
                    "If the instruction says 'move X to Y', swap the meal to the correct day and clear or reassign the original. "
                    "If an ingredient won't be available until a specific day, do not use it before that day. "
                    "If a prep step requires advance action (e.g., brining 24h ahead), add the prep note to the day BEFORE. "
                    "Return ONLY valid JSON in this exact format, no explanation:\n"
                    '{"days":{"Monday":{...},"Tuesday":{...},...,"Sunday":{...}},'
                    '"prep_notes":{"Monday":"...","Tuesday":"...",...},'
                    '"grocery_gaps":[],'
                    '"summary":"One sentence describing what changed"}'
                )
                result_e = {}
                try:
                    resp_e = _req.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key_e,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-sonnet-4-20250514",
                            "max_tokens": 4096,
                            "messages": [{"role":"user","content": edit_prompt}],
                        },
                        timeout=90,
                    )
                    resp_e.raise_for_status()
                    rj = resp_e.json()
                    text_e = "".join(
                        b.get("text","") for b in rj.get("content",[])
                        if b.get("type") == "text"
                    )
                    # Robust parse
                    parsed_e = {}
                    fence_m = _re.search(r'```json\s*([\s\S]*?)\s*```', text_e)
                    cands = []
                    if fence_m: cands.append(fence_m.group(1))
                    brace_m = _re.search(r'\{[\s\S]*\}', text_e)
                    if brace_m: cands.append(brace_m.group())
                    for cand in cands:
                        try:
                            parsed_e = _json.loads(cand); break
                        except _json.JSONDecodeError:
                            cleaned = _re.sub(r',\s*([}\]])', r'\1', cand)
                            try:
                                parsed_e = _json.loads(cleaned); break
                            except Exception: pass
                    if not parsed_e:
                        raise ValueError("Could not parse Claude response")
                    days_e = parsed_e.get("days", parsed_e)  # top-level may BE the days dict
                    # If "days" key missing but day names present, treat whole object as days
                    from render_meals import DAYS as _DAYS
                    if not any(d in days_e for d in _DAYS) and any(d in parsed_e for d in _DAYS):
                        days_e = {d: parsed_e.get(d, {}) for d in _DAYS}
                    else:
                        days_e = {d: days_e.get(d, {}) for d in _DAYS}
                    prep_e  = parsed_e.get("prep_notes", {})
                    groc_e  = parsed_e.get("grocery_gaps", [])
                    summ_e  = parsed_e.get("summary", "Plan updated.")
                    # Merge into saved plan
                    plan_e = load_meal_plan(wk_e)
                    for d in _DAYS:
                        if days_e.get(d):
                            plan_e.setdefault("days", {})[d] = days_e[d]
                    if prep_e:  plan_e["prep_notes"]  = prep_e
                    if groc_e:  plan_e["grocery_gaps"] = groc_e
                    save_meal_plan(plan_e)
                    result_e = {
                        "ok": True,
                        "days": days_e,
                        "prep_notes": prep_e,
                        "grocery_gaps": groc_e,
                        "summary": summ_e,
                    }
                except Exception as ex:
                    result_e = {"error": str(ex)[:300]}
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps(result_e).encode())
                except BrokenPipeError: pass
                return

            # NOTE: /recipe-save is handled in the multipart branch above so it
            # can accept a dish-photo upload. The previous urlencoded handler
            # was removed.

            elif path == "/recipe-delete":
                rid = clean_text(data.get("id",[""])[0])
                if rid:
                    recipes = load_recipes()
                    recipes = [r for r in recipes if r.get("id") != rid]
                    from render_meals import save_recipes
                    save_recipes(recipes)
                redirect = "/recipes"

            # ── Planning system JSON endpoints ──────────────────────────────
            elif path == "/plan-week-save":
                import json as _json
                wk_in  = clean_text(data.get("week",[""])[0])
                raw_in = data.get("data",["{}"])[0]
                try:
                    d_in = _json.loads(raw_in)
                    if wk_in:
                        d_in["week"] = wk_in
                    if d_in.get("week"):
                        from render_plan_week import save_intentions_data
                        save_intentions_data(d_in)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-month-save":
                import json as _json
                mk_in  = clean_text(data.get("month",[""])[0])
                raw_in = data.get("data",["{}"])[0]
                try:
                    d_in = _json.loads(raw_in)
                    if mk_in:
                        d_in["month"] = mk_in
                    if d_in.get("month"):
                        from render_plan_month import save_month_plan
                        save_month_plan(d_in)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/quarter-save-goals":
                import json as _json
                qk_in      = clean_text(data.get("quarter",[""])[0])
                ids_raw    = data.get("goal_ids",["[]"])[0]
                try:
                    goal_ids = _json.loads(ids_raw)
                    if qk_in and isinstance(goal_ids, list):
                        from render_goals import load_quarter_plan, save_quarter_plan
                        plan = load_quarter_plan(qk_in)
                        plan["active_goal_ids"] = goal_ids[:5]
                        save_quarter_plan(plan)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/save-mom-profile":
                import json as _json
                try:
                    profile_raw = clean_text(data.get("profile",["{}"])[0])
                    profile_in = _json.loads(profile_raw)
                    if isinstance(profile_in, dict):
                        from render_mom_profile import save_mom_profile
                        save_mom_profile(profile_in)
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":true}')
                    except BrokenPipeError: pass
                except Exception:
                    self.send_response(500); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":false}')
                    except BrokenPipeError: pass
                return

            elif path == "/save-john-profile":
                import json as _json
                try:
                    profile_raw = clean_text(data.get("profile",["{}"])[0])
                    profile_in = _json.loads(profile_raw)
                    if isinstance(profile_in, dict):
                        from render_john import save_john_profile
                        save_john_profile(profile_in)
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":true}')
                    except BrokenPipeError: pass
                except Exception:
                    self.send_response(500); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":false}')
                    except BrokenPipeError: pass
                return

            elif path == "/save-friend":
                import json as _json, uuid as _uuid
                try:
                    family_raw = clean_text(data.get("family",["{}"])[0])
                    family_in  = _json.loads(family_raw)
                    if isinstance(family_in, dict):
                        from render_friends import load_friends, save_friends
                        friends = load_friends()
                        fid = family_in.get("id","").strip()
                        if fid:
                            # Update existing
                            found = False
                            for i, f in enumerate(friends):
                                if f.get("id") == fid:
                                    family_in["id"] = fid
                                    friends[i] = family_in
                                    found = True
                                    break
                            if not found:
                                friends.append(family_in)
                        else:
                            # New family
                            fid = str(_uuid.uuid4())[:8]
                            family_in["id"] = fid
                            friends.append(family_in)
                        save_friends(friends)
                        out = _json.dumps({"ok": True, "id": fid}).encode()
                    else:
                        out = b'{"ok":false}'
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(out)
                    except BrokenPipeError: pass
                except Exception:
                    self.send_response(500); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":false}')
                    except BrokenPipeError: pass
                return

            elif path == "/delete-friend":
                import json as _json
                try:
                    fid = clean_text(data.get("id",[""])[0])
                    if fid:
                        from render_friends import load_friends, save_friends
                        friends = [f for f in load_friends() if f.get("id") != fid]
                        save_friends(friends)
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":true}')
                    except BrokenPipeError: pass
                except Exception:
                    self.send_response(500); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":false}')
                    except BrokenPipeError: pass
                return

            elif path == "/save-child-profile":
                import json as _json
                try:
                    child_slug = str(data.get("child",[""])[0]).lower().strip()
                    profile_raw = clean_text(data.get("profile",["{}"])[0])
                    profile_in = _json.loads(profile_raw)
                    if child_slug and isinstance(profile_in, dict):
                        from render_child_profile import save_child_profile
                        save_child_profile(child_slug, profile_in)
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":true}')
                    except BrokenPipeError: pass
                except Exception:
                    self.send_response(500); self.send_header("Content-Type","application/json"); self.end_headers()
                    try: self.wfile.write(b'{"ok":false}')
                    except BrokenPipeError: pass
                return

            elif path == "/quarter-journal-save":
                import json as _json
                qk_in  = clean_text(data.get("quarter",[""])[0])
                try:
                    if qk_in:
                        from render_goals import load_quarter_plan, save_quarter_plan
                        plan = load_quarter_plan(qk_in)
                        ld_raw   = data.get("life_domains",   ["{}"])[0]
                        pe_raw   = data.get("prayer_examination", ["{}"])[0]
                        disc_raw = data.get("seasonal_discernment", ["{}"])[0]
                        ld_in   = _json.loads(ld_raw)
                        pe_in   = _json.loads(pe_raw)
                        disc_in = _json.loads(disc_raw)
                        if isinstance(ld_in, dict):
                            plan["life_domains"] = ld_in
                        if isinstance(pe_in, dict):
                            plan["prayer_examination"] = pe_in
                        if isinstance(disc_in, dict):
                            plan["seasonal_discernment"] = disc_in
                        save_quarter_plan(plan)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/quarter-save-step":
                qk_in   = clean_text(data.get("quarter",[""])[0])
                gid_in  = clean_text(data.get("goal_id",[""])[0])
                wk_in   = safe_int(data.get("week",["1"])[0], 1)
                step_in = clean_text(data.get("step",[""])[0])
                if qk_in and gid_in:
                    from render_goals import update_weekly_step
                    update_weekly_step(qk_in, gid_in, wk_in, step_in)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/quarter-checkin":
                qk_in     = clean_text(data.get("quarter",[""])[0])
                gid_in    = clean_text(data.get("goal_id",[""])[0])
                wk_in     = safe_int(data.get("week",["1"])[0], 1)
                status_in = clean_text(data.get("status",[""])[0])
                if qk_in and gid_in and status_in in ("done","partial","skip"):
                    from render_goals import record_weekly_checkin
                    record_weekly_checkin(qk_in, gid_in, wk_in, status_in)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/goal-add":
                title_in  = clean_text(data.get("title",[""])[0])
                cat_in    = clean_text(data.get("category",["Wildcard"])[0])
                why_in    = clean_text(data.get("why",[""])[0])
                metric_in = clean_text(data.get("metric",[""])[0])
                qk_in     = clean_text(data.get("quarter",[""])[0])
                if title_in:
                    from render_goals import add_master_goal
                    add_master_goal(title_in, cat_in, why_in, metric_in)
                redirect = ("/plan-quarter?quarter=" + qk_in if qk_in else "/plan-quarter") + "&msg=Goal+added"

            elif path == "/virtue-checkin":
                import json as _json
                from datetime import date as _date
                who_in    = clean_text(data.get("who",[""])[0])
                rating_in = safe_int(data.get("rating",["0"])[0], 0)
                note_in   = clean_text(data.get("note",[""])[0])
                if who_in and 0 < rating_in <= 5:
                    checkin = {"date": _date.today().isoformat(),
                               "rating": rating_in, "note": note_in}
                    if who_in == "me":
                        from render_virtues import load_personal_virtue, save_personal_virtue
                        pv = load_personal_virtue()
                        if pv.get("current"):
                            pv["current"].setdefault("checkins",[]).append(checkin)
                            save_personal_virtue(pv)
                    elif who_in == "family":
                        from render_virtues import load_family_virtue, save_family_virtue
                        fv = load_family_virtue()
                        if fv.get("current"):
                            fv["current"].setdefault("checkins",[]).append(checkin)
                            save_family_virtue(fv)
                    else:
                        # child id
                        from render_virtues import load_child_virtue, save_child_virtue
                        child_name = who_in.replace("_"," ")
                        matched = next((c for c in CHILDREN if c.lower()==child_name.lower()), child_name)
                        cv = load_child_virtue(matched)
                        if cv.get("current"):
                            cv["current"].setdefault("checkins",[]).append(checkin)
                            save_child_virtue(matched, cv)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/prayer-intention-delete":
                iid_in = clean_text(data.get("id",[""])[0])
                if iid_in:
                    from render_prayer import load_intentions, save_intentions
                    intents = load_intentions()
                    intents = [i for i in intents if i.get("id") != iid_in]
                    save_intentions(intents)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/prayer-intention-log":
                import json as _json
                iid_in    = clean_text(data.get("id",[""])[0])
                ptype_in  = clean_text(data.get("type",["custom"])[0])
                clabel_in = clean_text(data.get("custom_label",[""])[0])
                count_in  = safe_int(data.get("count",["1"])[0], 1)
                note_in   = clean_text(data.get("note",[""])[0])
                if iid_in:
                    from render_prayer import log_prayer
                    log_prayer(iid_in, ptype_in, count_in, clabel_in, note_in)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/prayer-intention-complete":
                iid_in      = clean_text(data.get("id",[""])[0])
                answered_in = data.get("answered",["false"])[0].lower() == "true"
                if iid_in:
                    from render_prayer import _update_intention
                    _update_intention(iid_in, {"answered": answered_in})
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/liturgy-hours-save":
                raw_in = data.get("data",["{}"])[0]
                try:
                    d_in = _json.loads(raw_in)
                    if not ds_in:
                        ds_in = d_in.get("date","")
                    if ds_in:
                        d_in["date"] = ds_in
                        from render_liturgy_hours import save_day_hours
                        save_day_hours(d_in)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/liturgy-hours-fetch":
                import json as _json
                ds_in    = clean_text(data.get("date",[""])[0])
                force_in = "force" in data
                try:
                    from datetime import date as _date
                    from render_liturgy_hours import fetch_week, _week_monday, HOURS_DIR
                    import os as _os
                    target_d = _date.fromisoformat(ds_in) if ds_in else _date.today()
                    monday   = _week_monday(target_d)
                    if force_in:
                        # Delete stored files for this week so they get re-fetched
                        for i in range(7):
                            day = monday + __import__('datetime').timedelta(days=i)
                            fp  = _os.path.join(HOURS_DIR, f"{day.isoformat()}.json")
                            if _os.path.exists(fp):
                                _os.remove(fp)
                    fetch_week(monday)
                    out = _json.dumps({"ok": True}).encode()
                except Exception as e:
                    out = _json.dumps({"ok": False, "error": str(e)}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/5am-save":
                import json as _json
                ds_in  = clean_text(data.get("date",[""])[0])
                raw_in = data.get("data",["{}"])[0]
                try:
                    d_in = _json.loads(raw_in)
                    if not ds_in:
                        ds_in = d_in.get("date","")
                    if ds_in:
                        d_in["date"] = ds_in
                        from render_5am import save_day
                        from datetime import date as _date
                        save_day(d_in)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-tomorrow-questions":
                import json as _j
                from render_plan_tomorrow import _gather_tomorrow_data, ai_generate_questions
                iso_in  = clean_text(data.get("iso",[""])[0]) or (date.today()+timedelta(days=1)).isoformat()
                cap_in  = clean_text(data.get("capacity",[""])[0])
                wday_in = clean_text(data.get("weekday",[""])[0])
                try:
                    from datetime import date as _d2
                    tmrw = _d2.fromisoformat(iso_in)
                    d_data = _gather_tomorrow_data(tmrw)
                    d_data["selected_capacity"] = cap_in
                    questions = ai_generate_questions(d_data)
                    out = _j.dumps({"questions": questions}).encode()
                except Exception as e:
                    out = _j.dumps({"error": str(e)}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/plan-tomorrow-generate":
                import json as _j
                from render_plan_tomorrow import _gather_tomorrow_data, ai_generate_plan, _format_plan_html
                iso_in      = clean_text(data.get("iso",[""])[0]) or (date.today()+timedelta(days=1)).isoformat()
                cap_in      = clean_text(data.get("capacity",[""])[0])
                wday_in     = clean_text(data.get("weekday",[""])[0])
                answers_in  = clean_text(data.get("answers",[""])[0])
                questions_in= clean_text(data.get("questions",[""])[0])
                refine_in   = clean_text(data.get("refine",[""])[0])
                try:
                    from datetime import date as _d3
                    tmrw   = _d3.fromisoformat(iso_in)
                    d_data = _gather_tomorrow_data(tmrw)
                    # Include questions context in answers
                    full_answers = (f"Questions asked:\n{questions_in}\n\nAnswers:\n{answers_in}"
                                   if questions_in else answers_in)
                    plan_raw  = ai_generate_plan(d_data, cap_in, full_answers, refine_in)
                    plan_html = _format_plan_html(plan_raw)
                    out = _j.dumps({"plan_html": plan_html, "plan_raw": plan_raw}).encode()
                except Exception as e:
                    out = _j.dumps({"error": str(e)}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/plan-tomorrow-push":
                import json as _j
                iso_in   = clean_text(data.get("iso",[""])[0]) or (date.today()+timedelta(days=1)).isoformat()
                wday_in  = clean_text(data.get("weekday",[""])[0])
                plan_raw = data.get("plan",[""])[0]
                try:
                    # Parse the plan text into per-person time slots
                    from render_daily_plan import get_or_seed_grid
                    from render_schedule_support import generate_half_hour_times
                    import re as _re
                    times = generate_half_hour_times()
                    # Map person headers to grid column names
                    person_map = {"MOM":"Mom","JP":"JP","JOSEPH":"Joseph","MICHAEL":"Michael","JAMES":"James"}
                    grid = get_or_seed_grid(iso_in, wday_in, list(person_map.values()))
                    current_person = None
                    for line in plan_raw.splitlines():
                        if line.startswith("## "):
                            current_person = person_map.get(line[3:].strip().upper())
                        elif current_person and (" \u2014 " in line or " - " in line):
                            sep  = " \u2014 " if " \u2014 " in line else " - "
                            time_str, task = line.strip().split(sep, 1)
                            # Match time_str to nearest slot
                            time_str = time_str.strip()
                            _m = _re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", time_str, _re.IGNORECASE)
                            if _m:
                                h, m, ampm = int(_m.group(1)), int(_m.group(2)), (_m.group(3) or "").upper()
                                if ampm == "PM" and h != 12: h += 12
                                if ampm == "AM" and h == 12: h = 0
                                target_min = h * 60 + m
                                best_slot = min(times, key=lambda t: abs(
                                    (lambda p: int(p.split(":")[0]) * 60 + int(p.split(":")[1].split()[0]))(t)
                                    - target_min
                                ))
                                if current_person in grid:
                                    existing = grid[current_person].get(best_slot, "")
                                    grid[current_person][best_slot] = (existing + " / " + task.strip() if existing else task.strip())
                    save_day_grid(iso_in, grid)
                    publish_day_grid(iso_in)
                    out = _j.dumps({"ok": True}).encode()
                except Exception as e:
                    out = _j.dumps({"ok": False, "error": str(e)}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-daily-schedule":
                import json as _j
                from render_ai_daily import ai_daily_schedule
                iso_in  = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                cap_in  = clean_text(data.get("capacity",[""])[0])
                wday_in = clean_text(data.get("weekday",[""])[0])
                try:
                    result = ai_daily_schedule(iso_in, cap_in, wday_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-meal-plan":
                import json as _j
                from render_ai_daily import ai_meal_plan
                wk_in = clean_text(data.get("week_key",[""])[0])
                try:
                    result = ai_meal_plan(wk_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-school-plan":
                import json as _j
                from render_ai_daily import ai_school_plan
                iso_in  = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                cap_in  = clean_text(data.get("capacity",[""])[0])
                wday_in = clean_text(data.get("weekday",[""])[0])
                try:
                    result = ai_school_plan(iso_in, wday_in, cap_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-evening-examen":
                import json as _j
                from render_ai_daily import ai_evening_examen
                iso_in = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                try:
                    result = ai_evening_examen(iso_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-weekly-review":
                import json as _j
                from render_ai_daily import ai_weekly_review
                wk_in = clean_text(data.get("week_key",[""])[0])
                try:
                    result = ai_weekly_review(wk_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-chore-adjust":
                import json as _j
                from render_ai_daily import ai_chore_adjust
                iso_in = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                cap_in = clean_text(data.get("capacity",[""])[0])
                try:
                    result = ai_chore_adjust(iso_in, cap_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-intention-prayer":
                import json as _j
                from render_ai_daily import ai_intention_prayer
                iid_in = clean_text(data.get("id",[""])[0])
                try:
                    result = ai_intention_prayer(iid_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-capacity-preview":
                import json as _json, urllib.request as _ur
                iso_in  = clean_text(data.get("iso",[""])[0])
                cap_in  = clean_text(data.get("capacity",[""])[0])
                try:
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    # Get family constraints for context
                    fc = settings.get("family_constraints",{})
                    context = []
                    if fc.get("james_schedule"):    context.append(f"Baby schedule: {fc['james_schedule'][:100]}")
                    if fc.get("school_durations"):  context.append(f"School: {fc['school_durations'][:100]}")
                    if fc.get("mom_supervision_subjects"): context.append(f"Mom-needed: {fc['mom_supervision_subjects'][:100]}")
                    context_str = "\n".join(context) if context else "No specific constraints on file."
                    cap_desc = {
                        "High":   "full energy, full capacity — can handle normal school, chores, cooking, and all responsibilities",
                        "Medium": "moderate energy — can do essentials but may need to simplify or delegate",
                        "Low":    "low energy — need to scale back significantly, focus only on the most important things",
                    }.get(cap_in, cap_in)
                    prompt = (
                        f"You are a warm Catholic homeschool family assistant.\n"
                        f"Mom just set her capacity to: {cap_in} ({cap_desc})\n"
                        f"Family context:\n{context_str}\n\n"
                        f"In 2-3 warm, practical sentences, briefly tell her:\n"
                        f"1. What this means for her day (what she can let go or lean into)\n"
                        f"2. One specific encouragement tailored to this capacity level\n"
                        f"Be concise and encouraging. No bullet points."
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 200,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=15) as resp:
                        result = _json.loads(resp.read())
                    preview = result["content"][0]["text"].strip()
                    out = _json.dumps({"preview": preview}).encode()
                except Exception as e:
                    cap_msgs = {
                        "High":   "You're at full capacity today — take on the full rhythm.",
                        "Medium": "Moderate capacity today — focus on what matters most.",
                        "Low":    "Low capacity today — give yourself grace and simplify.",
                    }
                    out = _json.dumps({"preview": cap_msgs.get(cap_in, f"Capacity set to {cap_in}.")}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return
                import json as _json, urllib.request as _ur
                season_in = clean_text(data.get("season",["Ordinary Time"])[0])
                virtue_in = clean_text(data.get("virtue",[""])[0])
                try:
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    prompt = (
                        f"Write one deep, beautiful morning journal prompt for a Catholic "
                        f"homeschooling mom. Season: {season_in}. "
                        f"{'Virtue focus: ' + virtue_in + '. ' if virtue_in else ''}"
                        f"The prompt should invite honest self-reflection and openness to God. "
                        f"One sentence only. No quotation marks. Return JSON only: {{\"prompt\": \"...\"}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 150,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=15) as resp:
                        result = _json.loads(resp.read())
                    raw    = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out    = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"prompt": "What does God want to say to me this morning?"}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return
                import json as _json, urllib.request as _ur
                who_in      = clean_text(data.get("who",["me"])[0])
                child_id_in = clean_text(data.get("child_id",[""])[0])
                try:
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    try:
                        from render_liturgical import get_liturgical_season
                        from datetime import date as _date
                        season = get_liturgical_season(_date.today())
                    except Exception:
                        season = "Ordinary Time"
                    # Build recent history context
                    if who_in == "me":
                        from render_virtues import load_personal_virtue
                        pv = load_personal_virtue()
                        recent = [h.get("virtue","") for h in pv.get("history",[])][-4:]
                        current = pv.get("current",{}).get("virtue","")
                        who_desc = "a Catholic homeschooling mom"
                    elif who_in == "family":
                        from render_virtues import load_family_virtue
                        fv = load_family_virtue()
                        recent = [h.get("virtue","") for h in fv.get("history",[])][-4:]
                        current = fv.get("current",{}).get("virtue","")
                        who_desc = "a Catholic homeschooling family"
                    else:
                        from render_virtues import load_child_virtue, child_age, age_band
                        child_name = child_id_in.replace("_"," ")
                        matched = next((c for c in CHILDREN if c.lower()==child_name.lower()), child_name)
                        cv = load_child_virtue(matched)
                        age = child_age(matched)
                        ab  = age_band(age)
                        recent = [h.get("virtue","") for h in cv.get("history",[])][-4:]
                        current = cv.get("current",{}).get("virtue","")
                        who_desc = f"a {ab.replace('_',' ')} child named {matched}"
                    from render_virtues import VIRTUE_LIBRARY
                    exclude = set(recent + ([current] if current else []))
                    available = [v for v in VIRTUE_LIBRARY if v not in exclude]
                    prompt = (
                        f"Suggest 3 virtues for {who_desc} to work on next.\n"
                        f"Liturgical season: {season}\n"
                        f"Recently practiced: {', '.join(recent) or 'none'}\n"
                        f"Available virtues: {', '.join(available[:12])}\n\n"
                        f"Return JSON only:\n"
                        f"{{\"html\": \"<p>1-2 warm sentences of reasoning, then list the 3 suggestions as clickable links using the format <a href='/virtues/TYPE?virtue=VIRTUE_NAME'>VIRTUE_NAME</a> where TYPE is 'me', 'family', or 'child/CHILD_ID'</p>\"}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 400,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw    = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out    = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"html": f"<p>Error: {e}</p>"}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            # ── AI endpoints (return JSON) ───────────────────────────────────
            elif path == "/ai-week-brief":
                import json as _json, urllib.request as _ur
                raw_in = data.get("data",["{}"])[0]
                try:
                    payload    = _json.loads(raw_in)
                    settings   = load_app_settings()
                    api_key    = (settings.get("anthropic_api_key","") or
                                  settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    goals_list = payload.get("goals",[])
                    goal_lines = "\n".join(
                        f"- {g.get('title','')} (step this week: {g.get('step','—')})"
                        for g in goals_list
                    )
                    prompt = (
                        f"You are a warm Catholic family life coach. "
                        f"Week {payload.get('quarter_week','?')} of this quarter.\n"
                        f"Most important: {payload.get('important','—')}\n"
                        f"Protect: {payload.get('protect','—')}\n"
                        f"Let go: {payload.get('let_go','—')}\n"
                        f"Active goals this week:\n{goal_lines or '—'}\n\n"
                        f"Write 2-3 sentences of warm, practical encouragement for the week ahead. "
                        f"Then return a JSON array called 'items' with 4-6 specific, actionable items "
                        f"to help her succeed this week — each with a 'text' field (one sentence, concrete action) "
                        f"and a 'category' field (Goal/School/Home/Prayer/Self). "
                        f"Format response as JSON only: {{\"briefing\": \"...\", \"items\": [{{}}, ...]}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 700,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"briefing": f"Error: {e}", "items": []}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-month-brief":
                import json as _json, urllib.request as _ur
                raw_in = data.get("data",["{}"])[0]
                try:
                    payload  = _json.loads(raw_in)
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    goals_list = payload.get("goals",[])
                    goal_lines = "\n".join(f"- {g.get('title','')}" for g in goals_list)
                    prompt = (
                        f"You are a warm Catholic family life coach.\n"
                        f"Month: {payload.get('month','?')}\n"
                        f"Theme: {payload.get('theme','—')}\n"
                        f"Focus: {payload.get('focus','—')}\n"
                        f"Protect: {payload.get('protect','—')}\n"
                        f"Active goals:\n{goal_lines or '—'}\n\n"
                        f"Write 3-4 sentences of warm, practical monthly encouragement. "
                        f"Consider the liturgical season and how it can inspire her goals. "
                        f"Return JSON only: {{\"briefing\": \"...\"}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 400,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"briefing": f"Error: {e}"}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-year-brief":
                import json as _json, urllib.request as _ur
                raw_in = data.get("data",["{}"])[0]
                try:
                    payload  = _json.loads(raw_in)
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    goals_list = payload.get("goals",[])
                    goal_lines = "\n".join(f"- {g.get('title','')} ({g.get('category','')})" for g in goals_list)
                    prompt = (
                        f"You are a warm Catholic family life coach reviewing the year {payload.get('year','?')}.\n"
                        f"Goals in master list:\n{goal_lines or '—'}\n\n"
                        f"Write 3-4 sentences reflecting on the year's goals, what rhythms matter "
                        f"for a Catholic homeschooling family, and what to carry into the new year. "
                        f"Return JSON only: {{\"briefing\": \"...\"}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 400,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"briefing": f"Error: {e}"}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-suggest-goals":
                import json as _json, urllib.request as _ur
                raw_in = data.get("data",["{}"])[0]
                try:
                    payload    = _json.loads(raw_in)
                    settings   = load_app_settings()
                    api_key    = (settings.get("anthropic_api_key","") or
                                  settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    goals_list = payload.get("goals",[])
                    quarter    = payload.get("quarter","?")
                    goal_lines = "\n".join(
                        f"- [{g.get('id','')}] {g.get('title','')} ({g.get('category','')}) — {g.get('why','')}"
                        for g in goals_list
                    )
                    # Liturgical season for quarter start
                    try:
                        from render_goals import quarter_start
                        from render_liturgical import get_liturgical_season
                        qs = quarter_start(quarter)
                        season = get_liturgical_season(qs)
                    except Exception:
                        season = "Ordinary Time"
                    prompt = (
                        f"You are a wise Catholic family life coach helping plan the quarter {quarter}.\n"
                        f"Liturgical season: {season}\n"
                        f"Available goals:\n{goal_lines}\n\n"
                        f"Select 4-5 goals that are most suited to this quarter and season. "
                        f"Consider the spiritual rhythm of {season}, what's realistic for a homeschooling mom, "
                        f"and natural seasonal energy. Return JSON only:\n"
                        f"{{\"html\": \"<p>2-3 sentences of warm reasoning</p>\", "
                        f"\"suggested_ids\": [\"id1\", \"id2\", \"id3\", \"id4\"]}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 500,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"html": f"Error: {e}", "suggested_ids": []}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-generate-steps":
                import json as _json, urllib.request as _ur
                quarter_in  = clean_text(data.get("quarter",[""])[0])
                gid_in      = clean_text(data.get("goal_id",[""])[0])
                goal_raw    = data.get("goal_data",["{}"])[0]
                try:
                    goal_data = _json.loads(goal_raw)
                    settings  = load_app_settings()
                    api_key   = (settings.get("anthropic_api_key","") or
                                 settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    try:
                        from render_goals import quarter_start, quarter_label
                        from render_liturgical import get_liturgical_season
                        qs     = quarter_start(quarter_in)
                        season = get_liturgical_season(qs)
                        qlabel = quarter_label(quarter_in)
                    except Exception:
                        season = "Ordinary Time"; qlabel = quarter_in
                    prompt = (
                        f"You are a Catholic family life coach creating a 13-week action plan.\n"
                        f"Quarter: {qlabel} | Season: {season}\n"
                        f"Goal: {goal_data.get('title','')}\n"
                        f"Why it matters: {goal_data.get('why','')}\n"
                        f"Success metric: {goal_data.get('metric','')}\n\n"
                        f"Create a specific, realistic 13-week step plan for a homeschooling mom. "
                        f"Each week should build on the last. Steps should be concrete (5-12 words each). "
                        f"Return JSON only: {{\"steps\": {{\"1\": \"Step text\", \"2\": \"...\", ... \"13\": \"...\"}}}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 900,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=25) as resp:
                        result = _json.loads(resp.read())
                    raw    = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    steps  = parsed.get("steps", {})
                    # Save to quarter plan
                    if quarter_in and gid_in:
                        from render_goals import load_quarter_plan, save_quarter_plan
                        plan = load_quarter_plan(quarter_in)
                        plan.setdefault("goals", {}).setdefault(gid_in, {})["weekly_steps"] = steps
                        save_quarter_plan(plan)
                    # Build HTML for the step grid
                    rows_html = ""
                    for w in range(1, 14):
                        step_text = steps.get(str(w), "")
                        gid_esc = gid_in.replace("'", "\\'")
                        rows_html += (
                            f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;'
                            f'border-bottom:1px solid var(--border-light);">'
                            f'<div style="font-size:0.72em;font-weight:700;color:var(--ink-faint);'
                            f'width:28px;flex-shrink:0;">W{w}</div>'
                            f'<input type="text" id="step-{gid_in}-{w}" value="{step_text}" '
                            f'onblur="saveStepEdit(\'{gid_esc}\',{w})" '
                            f'style="flex:1;padding:5px 8px;font-size:0.82em;border-radius:6px;'
                            f'border:1px solid var(--border-light);font-family:inherit;">'
                            f'</div>'
                        )
                    out = _json.dumps({"html": rows_html, "steps": steps}).encode()
                except Exception as e:
                    out = _json.dumps({"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "steps": {}}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

        self.send_response(303); self.send_header("Location",redirect); self.end_headers()


def initialize_data_files():
    os.makedirs("data",exist_ok=True); os.makedirs("data/history",exist_ok=True); os.makedirs("data/daily_plans",exist_ok=True); os.makedirs("data/day_templates",exist_ok=True); os.makedirs("data/day_grids",exist_ok=True); os.makedirs("data/meal_plan",exist_ok=True); os.makedirs("data/saint_cache",exist_ok=True)
    defaults={
        "data/chores.json":{"boys":{}},"data/manual_tasks.json":[],"data/notes.json":[],"data/mom_notes.json":[],
        "data/progress.json":{},"data/task_registry.json":{},"data/school_previews.json":{},"data/school_weeks.json":{"approved":{}},
        "data/roadmap.json":[],"data/liturgical.json":{},
        "data/calendar_config.json":{},"data/calendar_cache.json":{"events":[],"fetched_at":""},
        "data/calendar_rules.json":{"rules":{}},"data/subscribed_calendars.json":[],"data/monthly_planner.json":{},
        "data/app_settings.json":{},
    }
    for fpath,default in defaults.items():
        if not os.path.exists(fpath): safe_save_json(fpath,default)


if __name__ == "__main__":
    import os as _os, signal as _signal, socket as _socket, time as _time2

    # ── PID file: kill any previous instance before binding ───────────────────
    _PID_FILE = "/tmp/family_dashboard.pid"
    if _os.path.exists(_PID_FILE):
        try:
            _old_pid = int(open(_PID_FILE).read().strip())
            _os.kill(_old_pid, _signal.SIGKILL)
            _time2.sleep(0.5)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    with open(_PID_FILE, "w") as _pf:
        _pf.write(str(_os.getpid()))

    initialize_data_files()
    # Pre-fetch saint data for the week in the background
    try:
        import threading
        from saint_data import prefetch_week
        threading.Thread(target=prefetch_week, daemon=True).start()
    except Exception:
        pass
    # Auto-fetch Liturgy of the Hours on Sundays if enabled
    try:
        from render_liturgy_hours import maybe_auto_fetch, cleanup_old_files, start_weekly_scheduler
        cleanup_old_files()
        maybe_auto_fetch()
        start_weekly_scheduler()
    except Exception:
        pass

    class _Server(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads      = True
        allow_reuse_address = True
        allow_reuse_port    = False   # ONE process owns port 5000 at a time

        def server_bind(self):
            self.socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            super().server_bind()

    # ── Graceful shutdown on SIGTERM / SIGINT ─────────────────────────────────
    _server = None

    def _shutdown(signum, frame):
        try:
            _os.remove(_PID_FILE)
        except Exception:
            pass
        if _server:
            threading.Thread(target=_server.shutdown, daemon=True).start()

    _signal.signal(_signal.SIGTERM, _shutdown)
    _signal.signal(_signal.SIGINT,  _shutdown)

    # Retry binding — give previous process up to 8 s to release the port
    for _attempt in range(8):
        try:
            _server = _Server((HOST, PORT), Handler)
            break
        except OSError:
            if _attempt < 7:
                _time2.sleep(1)
    if _server is None:
        raise RuntimeError(f"Could not bind to port {PORT} after 8 attempts")

    print(f"Running on http://{HOST}:{PORT}")
    _server.serve_forever()