"""Minimal dependency-free Discord Rich Presence client (local IPC)."""
import json
import os
import socket
import struct
import sys
import threading
import time
import uuid

OP_HANDSHAKE, OP_FRAME, OP_CLOSE = 0, 1, 2
MIN_INTERVAL = 15.0  # Discord rate limit: one presence update per 15s


class DiscordIPC(object):
    def __init__(self, client_id):
        self.client_id = str(client_id)
        self._pipe = None
        self._sock = None

    # -- transport ---------------------------------------------------------
    def _candidates(self):
        for i in range(10):
            if sys.platform == "win32":
                yield r"\\.\pipe\discord-ipc-%d" % i
            else:
                base = (os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR")
                        or os.environ.get("TMP") or os.environ.get("TEMP") or "/tmp")
                yield os.path.join(base, "discord-ipc-%d" % i)

    def connect(self):
        last = None
        for path in self._candidates():
            try:
                if sys.platform == "win32":
                    self._pipe = open(path, "r+b", buffering=0)
                else:
                    self._sock = socket.socket(socket.AF_UNIX)
                    self._sock.connect(path)
                break
            except (IOError, OSError) as e:
                last = e
                self._sock = None
        else:
            raise IOError("Discord is not running (%s)" % last)
        self._send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
        op, data = self._recv()
        if data.get("evt") != "READY":
            self.close()
            raise IOError("Discord handshake failed: %s" % data)

    def close(self):
        for h in (self._pipe, self._sock):
            try:
                if h:
                    h.close()
            except Exception:
                pass
        self._pipe = self._sock = None

    def _write(self, b):
        if self._pipe:
            self._pipe.write(b)
        else:
            self._sock.sendall(b)

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self._pipe.read(n - len(buf)) if self._pipe else self._sock.recv(n - len(buf))
            if not chunk:
                raise IOError("Discord closed the connection")
            buf += chunk
        return buf

    def _send(self, op, payload):
        raw = json.dumps(payload).encode("utf-8")
        self._write(struct.pack("<II", op, len(raw)) + raw)

    def _recv(self):
        op, length = struct.unpack("<II", self._read(8))
        return op, json.loads(self._read(length).decode("utf-8"))

    # -- api ---------------------------------------------------------------
    def set_activity(self, activity):
        self._send(OP_FRAME, {
            "cmd": "SET_ACTIVITY",
            "args": {"pid": os.getpid(), "activity": activity},
            "nonce": str(uuid.uuid4()),
        })
        op, data = self._recv()
        if data.get("evt") == "ERROR":
            raise IOError("Discord rejected activity: %s" % data.get("data"))


class PresenceWorker(object):
    """Background thread: keeps the connection alive, sends the latest
    activity at most once per MIN_INTERVAL, reconnects if Discord restarts."""

    def __init__(self, client_id):
        self.client_id = client_id
        self._pending = None
        self._has_pending = False
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = False
        self._thread = threading.Thread(target=self._run, name="nuke-discord-rpc")
        self._thread.daemon = True
        self.status = "starting"

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop = True
        self.push(None)
        self._thread.join(2.0)

    def push(self, activity):
        with self._lock:
            self._pending, self._has_pending = activity, True
        self._wake.set()

    def _run(self):
        ipc, last_sent = None, 0.0
        while not self._stop:
            self._wake.wait(1.0)
            with self._lock:
                has, act = self._has_pending, self._pending
            if not has:
                continue
            if not self._stop and time.time() - last_sent < MIN_INTERVAL:
                self._wake.clear()
                time.sleep(0.5)
                self._wake.set()
                continue
            try:
                if ipc is None:
                    ipc = DiscordIPC(self.client_id)
                    ipc.connect()
                ipc.set_activity(act)
                last_sent = time.time()
                with self._lock:
                    if self._pending is act:
                        self._has_pending = False
                self._wake.clear()
                self.status = "connected"
            except Exception as e:
                self.status = "error: %s" % e
                if ipc:
                    ipc.close()
                ipc = None
                last_sent = time.time()  # back off one interval before retrying
        if ipc:
            ipc.close()
