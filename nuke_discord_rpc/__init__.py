"""Discord Rich Presence for Nuke (The Foundry).

Add to menu.py:
    import nuke_discord_rpc; nuke_discord_rpc.start()
"""
import json
import os
import time

import nuke

from .ipc import PresenceWorker

__all__ = ["start", "stop"]

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".nuke", "discord_rpc.json")
DEFAULTS = {
    "client_id": "1555867282520014858",  # Discord application ID (override via menu or NUKE_DISCORD_CLIENT_ID)
    "enabled": True,
    "show_script_name": True,
    "show_node_count": True,
    "show_frame": True,
    "idle_minutes": 5,
}
POLL_MS = 5000

_cfg = dict(DEFAULTS)
_worker = None
_timer = None
_started_at = time.time()
_last_activity = time.time()
_last_sig = None
_rendering = False


# -- config ----------------------------------------------------------------
def _load():
    _cfg.update(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            _cfg.update(json.load(f))
    except (IOError, OSError, ValueError):
        pass
    env = os.environ.get("NUKE_DISCORD_CLIENT_ID")
    if env:
        _cfg["client_id"] = env


def _save():
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(_cfg, f, indent=2)
    except (IOError, OSError):
        pass


# -- presence --------------------------------------------------------------
def _edition():
    env = nuke.env
    for key, name in (("indie", "Indie"), ("studio", "Studio"), ("nukex", "NukeX"), ("nc", "Non-Commercial")):
        try:
            if env.get(key):
                return name
        except Exception:
            pass
    return ""


def _touch(*_):
    global _last_activity
    _last_activity = time.time()


def _build():
    """Runs on the main thread; returns (signature, activity-dict)."""
    global _last_sig
    name = nuke.root().name()
    saved = name not in ("Root", "")
    script = os.path.basename(name) if saved else "Untitled script"
    try:
        nodes = len(nuke.root().nodes())
        frame = int(nuke.frame())
    except Exception:
        nodes, frame = 0, 0
    modified = nuke.root().modified()

    sig = (name, nodes, frame, modified, _rendering)
    if sig != _last_sig:
        _last_sig = sig
        _touch()

    idle = (time.time() - _last_activity) > _cfg["idle_minutes"] * 60
    if _rendering:
        small, small_text = "rendering", "Rendering"
    elif idle:
        small, small_text = "idle", "Idle"
    else:
        small, small_text = "editing", "Editing"

    details = ("%s %s" % ("Rendering" if _rendering else ("Idle in" if idle else "Editing"), script)
               if _cfg["show_script_name"] else
               ("Rendering a comp" if _rendering else ("Idle" if idle else "Compositing")))
    bits = []
    if _cfg["show_node_count"]:
        bits.append("%d node%s" % (nodes, "" if nodes == 1 else "s"))
    if _cfg["show_frame"]:
        bits.append("Frame %d" % frame)
    version = "Nuke %s" % nuke.NUKE_VERSION_STRING
    ed = _edition()

    activity = {
        "details": details[:128],
        "timestamps": {"start": int(_started_at)},
        "assets": {
            "large_image": "nuke",
            "large_text": ("%s %s" % (version, ed)).strip(),
            "small_image": small,
            "small_text": small_text,
        },
    }
    if bits:
        activity["state"] = u" · ".join(bits)
    return (sig, idle), activity


def _tick():
    if _worker is None or not _cfg["enabled"]:
        return
    try:
        key, activity = _build()
    except Exception:
        return
    if key != getattr(_tick, "last", None):
        _tick.last = key
        _worker.push(activity)


# -- render / event hooks --------------------------------------------------
def _before_render():
    global _rendering
    _rendering = True
    _touch()
    _tick()


def _after_render():
    global _rendering
    _rendering = False
    _touch()
    _tick()


# -- lifecycle -------------------------------------------------------------
def start():
    global _worker, _timer, _started_at
    if not nuke.GUI:
        return
    if _worker is not None:
        return
    _load()
    if not _cfg["enabled"]:
        _install_menu()
        return
    if not _cfg["client_id"]:
        _install_menu()
        nuke.tprint("[discord-rpc] No client_id set. Use Discord RPC > Set Application ID.")
        return

    _started_at = time.time()
    _worker = PresenceWorker(_cfg["client_id"])
    _worker.start()

    try:
        from PySide2 import QtCore
    except ImportError:
        from PySide6 import QtCore
    _timer = QtCore.QTimer()
    _timer.timeout.connect(_tick)
    _timer.start(POLL_MS)

    nuke.addKnobChanged(_touch)
    nuke.addOnUserCreate(_touch)
    nuke.addOnDestroy(_touch)
    nuke.addBeforeRender(_before_render)
    nuke.addAfterRender(_after_render)
    nuke.addOnScriptLoad(_tick)
    nuke.addOnScriptSave(_tick)
    _install_menu()
    _tick()


def stop():
    global _worker, _timer
    if _timer is not None:
        _timer.stop()
        _timer = None
    if _worker is not None:
        _worker.stop()
        _worker = None
    _tick.last = None


def restart():
    stop()
    start()


# -- menu ------------------------------------------------------------------
def _toggle(key):
    _cfg[key] = not _cfg[key]
    _save()
    if key == "enabled":
        restart()
    else:
        _tick.last = None
        _tick()


def _set_id():
    v = nuke.getInput("Discord Application (Client) ID:", _cfg["client_id"])
    if v is not None:
        _cfg["client_id"] = v.strip()
        _save()
        restart()


def _status():
    nuke.message("Discord RPC status: %s" % (_worker.status if _worker else "not running"))


_menu_done = False


def _install_menu():
    global _menu_done
    if _menu_done:
        return
    _menu_done = True
    m = nuke.menu("Nuke").addMenu("Discord RPC")
    m.addCommand("Enabled", lambda: _toggle("enabled"), "")
    m.addCommand("Show script name", lambda: _toggle("show_script_name"), "")
    m.addCommand("Show node count", lambda: _toggle("show_node_count"), "")
    m.addCommand("Show frame", lambda: _toggle("show_frame"), "")
    m.addSeparator()
    m.addCommand("Set Application ID...", _set_id)
    m.addCommand("Reconnect", restart)
    m.addCommand("Status", _status)
