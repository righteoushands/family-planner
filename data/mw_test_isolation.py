"""Test-only isolation for the Meal Wizard live data files (Rule 10).

Importing this module BEFORE `config` redirects BOTH of the live stores the
meal-wizard harnesses touch to private temp locations for the ENTIRE process:

  * MEAL_WIZARD_SESSION_FILE -> a private temp file
  * MEAL_PLAN_DIR            -> a private temp directory (the meal_plan store the
                               lock harness writes week files into)

so the standing harnesses (and any in-process server they spin up) never read or
write the live data/meal_wizard_session.json OR data/meal_plan/* -- not even to
snapshot and restore them.

How it works
------------
- `config` and `render_meals` both read these env vars (see config.py and
  render_meals.py). Because `data_helpers`/`render_meals` bind those names at
  import, setting the env vars before either is imported points every session
  and week-file read/write in this process at the temp locations.
- The HTTP harnesses spin up an in-process server via `start_server()`, which
  runs `app.Handler` in THIS process. Sharing the process means the server's
  writes also land in the temp locations -- no live server is contacted.

Usage (must be the FIRST project import in a harness, before `config`):
    import mw_test_isolation                      # noqa: F401  (sets overrides)
    import config                                 # noqa: E402
    ...
    mw_test_isolation.assert_isolated()           # hard guard before any work
"""
import atexit
import os
import shutil
import tempfile
import threading
from http.server import HTTPServer

_LIVE_SESSION = "data/meal_wizard_session.json"
_LIVE_SESSION_REAL = os.path.realpath(_LIVE_SESSION)
_LIVE_MEALS_DIR = "data/meal_plan"
_LIVE_MEALS_REAL = os.path.realpath(_LIVE_MEALS_DIR)

# ── Session file: redirect unless an isolated override is already active. Any
# override that resolves to the live file (empty, the literal default, or a path
# that normalizes to it) is treated as "no override" and replaced.
_env = os.environ.get("MEAL_WIZARD_SESSION_FILE", "")
if _env == "" or os.path.realpath(_env) == _LIVE_SESSION_REAL:
    _fd, _tmp = tempfile.mkstemp(prefix="mw_session_test_", suffix=".json")
    os.close(_fd)
    os.environ["MEAL_WIZARD_SESSION_FILE"] = _tmp
    atexit.register(lambda p=_tmp: os.path.exists(p) and os.remove(p))

# ── meal_plan directory: same rule. A temp DIR (its own .backups rotation stays
# inside it and is cleaned up wholesale on exit).
_env_dir = os.environ.get("MEAL_PLAN_DIR", "")
if _env_dir == "" or os.path.realpath(_env_dir) == _LIVE_MEALS_REAL:
    _tmpdir = tempfile.mkdtemp(prefix="mw_mealplan_test_")
    os.environ["MEAL_PLAN_DIR"] = _tmpdir
    atexit.register(lambda d=_tmpdir: shutil.rmtree(d, ignore_errors=True))

SESSION_PATH = os.environ["MEAL_WIZARD_SESSION_FILE"]
MEALS_DIR = os.environ["MEAL_PLAN_DIR"]


def assert_isolated():
    """Refuse to proceed unless BOTH live stores are the isolated temp paths.

    This is the safety net that makes the harnesses incapable of touching live
    data: if either override did not take (e.g. this module was imported after
    `config`), we raise instead of writing the real files.
    """
    import config
    import render_meals
    if os.path.realpath(SESSION_PATH) == _LIVE_SESSION_REAL or config.MEAL_WIZARD_SESSION_FILE != SESSION_PATH:
        raise RuntimeError(
            "Meal-wizard session isolation FAILED: config points at "
            + repr(config.MEAL_WIZARD_SESSION_FILE)
            + " (import mw_test_isolation before config)."
        )
    _meals_real = os.path.realpath(MEALS_DIR)
    if (_meals_real == _LIVE_MEALS_REAL
            or os.path.realpath(render_meals.MEALS_DIR) != _meals_real
            or os.path.realpath(config.MEALS_DIR) != _meals_real):
        raise RuntimeError(
            "Meal-plan dir isolation FAILED: render_meals="
            + repr(render_meals.MEALS_DIR) + " config=" + repr(config.MEALS_DIR)
            + " (import mw_test_isolation before render_meals/config)."
        )


def start_server():
    """Start an in-process HTTP server using the live `app.Handler` on an
    ephemeral loopback port.

    Because it runs in THIS process, it shares the same (redirected) session
    path, so its writes also land in the temp file -- the live :5000 server is
    never contacted. Returns ``(base_url, shutdown)``; call ``shutdown()`` in a
    finally block.
    """
    import app
    httpd = HTTPServer(("127.0.0.1", 0), app.Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:" + str(port)

    def shutdown():
        try:
            httpd.shutdown()
        finally:
            httpd.server_close()

    return base, shutdown
