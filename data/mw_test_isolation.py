"""Test-only isolation for the Meal Wizard session file (Rule 10).

Importing this module BEFORE `config` redirects MEAL_WIZARD_SESSION_FILE to a
private temp path for the ENTIRE process, so the standing meal-wizard harnesses
(and any in-process server they spin up) never read or write the live
data/meal_wizard_session.json -- not even to snapshot and restore it.

How it works
------------
- `config.MEAL_WIZARD_SESSION_FILE` reads this env var (see config.py). Because
  `data_helpers` binds that name at import, setting the env var before either is
  imported points every session read/write in this process at the temp file.
- The HTTP harnesses spin up an in-process server via `start_server()`, which
  runs `app.Handler` in THIS process. Sharing the process means the server's
  session writes also land in the temp file -- no live server is contacted.

Usage (must be the FIRST project import in a harness, before `config`):
    import mw_test_isolation                      # noqa: F401  (sets override)
    import config                                 # noqa: E402
    ...
    mw_test_isolation.assert_isolated()           # hard guard before any work
"""
import atexit
import os
import tempfile
import threading
from http.server import HTTPServer

_LIVE_DEFAULT = "data/meal_wizard_session.json"
_LIVE_REAL = os.path.realpath(_LIVE_DEFAULT)

# Redirect to a private temp file unless an isolated override is already active.
# Any override that resolves to the live file (empty, the literal default, or a
# path that normalizes to it) is treated as "no override" and replaced.
_env = os.environ.get("MEAL_WIZARD_SESSION_FILE", "")
if _env == "" or os.path.realpath(_env) == _LIVE_REAL:
    _fd, _tmp = tempfile.mkstemp(prefix="mw_session_test_", suffix=".json")
    os.close(_fd)
    os.environ["MEAL_WIZARD_SESSION_FILE"] = _tmp
    atexit.register(lambda p=_tmp: os.path.exists(p) and os.remove(p))

SESSION_PATH = os.environ["MEAL_WIZARD_SESSION_FILE"]


def assert_isolated():
    """Refuse to proceed unless the session path is the isolated temp file.

    This is the safety net that makes the harnesses incapable of touching live
    data: if the override did not take (e.g. this module was imported after
    `config`), we raise instead of writing the real session file.
    """
    import config
    if os.path.realpath(SESSION_PATH) == _LIVE_REAL or config.MEAL_WIZARD_SESSION_FILE != SESSION_PATH:
        raise RuntimeError(
            "Meal-wizard session isolation FAILED: config points at "
            + repr(config.MEAL_WIZARD_SESSION_FILE)
            + " (import mw_test_isolation before config)."
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
