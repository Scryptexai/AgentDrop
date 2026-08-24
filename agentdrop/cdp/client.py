"""Minimal Chrome DevTools Protocol (CDP) client.

Talks raw JSON-RPC over the CDP WebSocket for ONE target (tab).

We do not launch browsers here. Browsers are started separately (see
scripts/start-browser.sh) with ``--remote-debugging-port`` so the same
persistent profile keeps living across agent sessions.
"""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import websocket  # websocket-client


class CDPError(Exception):
    """A CDP method returned an error or the connection dropped."""

    def __init__(self, method: str, error: Any):
        self.method = method
        self.error = error
        super().__init__(f"CDP error on {method}: {error}")


class CDPClient:
    """One WebSocket connection to one CDP target.

    Thread model: a daemon reader thread fans messages out to
    (a) pending ``send()`` futures matched by message id, and
    (b) per-event waiters / listeners registered for CDP events.
    """

    def __init__(self, ws_url: str, connect_timeout: float = 15.0):
        self._ws_url = ws_url
        self._connect_timeout = connect_timeout
        self._ws: Optional[websocket.WebSocket] = None
        self._closed = False
        self._lock = threading.Lock()
        self._pending: Dict[str, queue.Queue] = {}
        self._event_waiters: Dict[str, queue.Queue] = {}
        self._listeners: Dict[str, List[Callable[[dict], None]]] = {}
        self._reader: Optional[threading.Thread] = None
        self.connected = False

    # ------------------------------------------------------------------ connect
    def connect(self) -> "CDPClient":
        self._ws = websocket.create_connection(
            self._ws_url, timeout=self._connect_timeout
        )
        self.connected = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        return self

    def close(self) -> None:
        self._closed = True
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass
        self.connected = False

    # ------------------------------------------------------------------ internals
    def _read_loop(self) -> None:
        assert self._ws is not None
        while not self._closed:
            try:
                raw = self._ws.recv()
            except Exception:
                self._fail_all("connection closed")
                break
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if "id" in msg:  # response to a command
                q = self._pending.pop(str(msg["id"]), None)
                if q is not None:
                    q.put(msg)
            elif "method" in msg:  # event
                method = msg["method"]
                params = msg.get("params", {})
                q = self._event_waiters.get(method)
                if q is not None:
                    q.put(params)
                for cb in self._listeners.get(method, []):
                    try:
                        cb(params)
                    except Exception:
                        pass

    def _fail_all(self, reason: str) -> None:
        with self._lock:
            for q in self._pending.values():
                q.put({"error": {"message": reason}})
            self._pending.clear()
            for q in self._event_waiters.values():
                q.put({"_dropped": True})

    # ------------------------------------------------------------------ commands
    def send(self, method: str, params: Optional[dict] = None, timeout: float = 30.0) -> dict:
        """Send a CDP command and block for its response (params dict)."""
        if self._ws is None or not self.connected:
            raise CDPError(method, "not connected")
        mid = str(uuid.uuid4())
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._pending[mid] = q
        try:
            self._ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
            try:
                msg = q.get(timeout=timeout)
            except queue.Empty:
                raise CDPError(method, f"timed out after {timeout}s")
        finally:
            with self._lock:
                self._pending.pop(mid, None)
        if "error" in msg:
            raise CDPError(method, msg["error"])
        return msg.get("result", {})

    def enable(self, domain: str) -> None:
        try:
            self.send(f"{domain}.enable")
        except CDPError:
            pass

    # ------------------------------------------------------------------ events
    def wait_event(self, method: str, timeout: float = 30.0) -> Optional[dict]:
        """Block until a CDP event fires. Returns params or None on timeout."""
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._event_waiters[method] = q
        try:
            try:
                params = q.get(timeout=timeout)
            except queue.Empty:
                return None
        finally:
            with self._lock:
                self._event_waiters.pop(method, None)
        return None if isinstance(params, dict) and params.get("_dropped") else params

    def on_event(self, method: str, callback: Callable[[dict], None]) -> None:
        with self._lock:
            self._listeners.setdefault(method, []).append(callback)

    def wait_ms(self, ms: float) -> None:
        time.sleep(max(0.0, ms) / 1000.0)
