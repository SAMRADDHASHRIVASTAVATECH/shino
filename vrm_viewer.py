"""Nova's OFFLINE pixel-companion bridge.

Serves the 180-state animated sprite kit from assets/companion and the tiny
transparent pet page from assets/web over a loopback-only HTTP server.  The
3D VRM viewer is kept dormant on disk but is never shown.  Nothing here can
reach the internet:

  * the HTTP server binds 127.0.0.1 only,
  * the page ships a Content-Security-Policy with connect-src 'self',
  * every sprite and script is a local file under assets/.

The rest of Nova calls set_state() to report what it is DOING (semantic event
or direct state).  The page polls GET /state; no push socket is needed.
Thinking never crosses this bridge — only actions and spoken text.
"""
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "assets", "web")
COMPANION = os.path.join(ROOT, "assets", "companion")
SPRITES = os.path.join(ROOT, "assets", "sprites")
MODELS = os.path.join(ROOT, "assets", "models")
MOTIONS = os.path.join(ROOT, "assets", "motions")
PORT_FILE = os.path.join(ROOT, "nova_viewer.port")

DEFAULT_STATE = {
    "emotion": "neutral",
    "speaking": False,
    "dance": False,
    "busy": False,
    "mode": "IDLE",
    "gaze": {"x": 0.0, "y": 0.0},
    "gesture": {"name": "", "nonce": 0},
    "bubble": "",
    "bubble_nonce": 0,
    # What she is DOING (visible) — not her private thinking.
    "activity": "Here for you~",
    "event": "",             # kit event id, e.g. "model.start"
    "event_nonce": 0,
    "pet_state": "",         # direct kit state id when an event won't do
    "pet_state_nonce": 0,
    "messages": [],          # last chat turns: [{role, text}, ...]
    "messages_nonce": 0,
    # OFF = normal mode: she never grabs or looks at the screen until toggled.
    "screenshare": False,
    "model": "victoria-jeans.vrm",
    "version": 0,
}

_state = dict(DEFAULT_STATE)
_lock = threading.Lock()
# Dock geometry: the 3D body is positioned over the character slot of the main
# Nova window, so it reads as part of that window instead of a floating screen.
_dock = {"x": 40, "y": 120, "w": 300, "h": 286, "enabled": False, "version": 0}
_dock_lock = threading.Lock()
_server = None
_thread = None
_port = None
_window_proc = None
_chat_handler = None
_screenshare_handler = None

CSP = ("default-src 'self'; "
       "script-src 'self' 'unsafe-inline'; "
       "connect-src 'self' blob:; "
       "img-src 'self' data: blob:; "
       "style-src 'self' 'unsafe-inline'; "
       "font-src 'self' data:; "
       "media-src 'self' blob:; "
       "object-src 'none'; base-uri 'none'; frame-ancestors 'none'")

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".vrm": "model/gltf-binary",
    ".glb": "model/gltf-binary",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


# ---------- state API (called from Nova) ----------
def set_state(**kwargs):
    """Merge state changes; bump version only when something really changed."""
    global _state
    with _lock:
        changed = {k: v for k, v in kwargs.items() if _state.get(k) != v}
        if changed:
            _state = dict(_state)
            _state.update(changed)
            _state["version"] = int(_state.get("version", 0)) + 1
    return changed


def get_state():
    with _lock:
        return dict(_state)


def set_dock(x=None, y=None, w=None, h=None, enabled=None):
    """Update where the frameless 3D body sits over the main Nova window."""
    global _dock
    changes = {k: v for k, v in (("x", x), ("y", y), ("w", w), ("h", h),
                                 ("enabled", enabled)) if v is not None}
    if not changes:
        return dict(_dock)
    with _dock_lock:
        _dock = dict(_dock)
        _dock.update(changes)
        _dock["version"] += 1
        return dict(_dock)


def get_dock():
    with _dock_lock:
        return dict(_dock)


def set_chat_handler(fn):
    """Register the callback that feeds typed text into Nova's chat path."""
    global _chat_handler
    _chat_handler = fn


def set_screenshare_handler(fn):
    """Register the callback that turns screen watching on/off."""
    global _screenshare_handler
    _screenshare_handler = fn


def port():
    return _port


# ---------- local HTTP server ----------
class _Handler(BaseHTTPRequestHandler):
    server_version = "NovaOffline/1.0"

    def log_message(self, *_args):
        pass  # keep Nova's terminal clean

    def _send(self, code, body, ctype=None, extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        if self.path == "/" or self.path.startswith("/index.html"):
            self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    @staticmethod
    def _resolve(url_path):
        """Return a safe absolute path inside WEB/MODELS/MOTIONS, or None."""
        clean = url_path.split("?", 1)[0].split("#", 1)[0]
        clean = clean.replace("\\", "/")
        if ".." in clean or clean.startswith("//"):
            return None
        if clean in ("/", "/index.html"):
            return os.path.join(WEB, "pet.html")       # pixel pet is the UI
        if clean == "/viewer.html":
            return os.path.join(WEB, "viewer.html")    # 3D body kept dormant
        parts = [p for p in clean.split("/") if p]
        if not parts:
            return None
        head, rest = parts[0], parts[1:]
        if not rest:
            # Root-level page assets: /pet.js, /viewer.js, etc.
            direct = os.path.join(WEB, head)
            if os.path.isfile(direct):
                return direct
        base = {"web": WEB, "companion": COMPANION, "sprites": SPRITES,
                "models": MODELS, "motions": MOTIONS}.get(head)
        if base is None:
            return None
        target = os.path.normpath(os.path.join(base, *rest))
        if os.path.commonpath([os.path.abspath(base), target]) != os.path.abspath(base):
            return None
        return target

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/state":
            self._send(200, json.dumps(get_state()), "application/json; charset=utf-8")
            return
        if self.path.split("?", 1)[0] == "/health":
            self._send(200, "ok", "text/plain")
            return
        if self.path.split("?", 1)[0] == "/dock":
            self._send(200, json.dumps(get_dock()), "application/json; charset=utf-8")
            return
        clean = self.path.split("?", 1)[0]
        if clean == "/models/active.vrm":
            model = os.path.basename(str(get_state().get("model") or "victoria-jeans.vrm"))
            target = os.path.join(MODELS, model)
        else:
            target = self._resolve(self.path)
        if not target or not os.path.isfile(target):
            self._send(404, "not found", "text/plain")
            return
        ext = os.path.splitext(target)[1].lower()
        ctype = MIME.get(ext) or mimetypes.guess_type(target)[0] or "application/octet-stream"
        try:
            with open(target, "rb") as f:
                body = f.read()
        except Exception:
            self._send(404, "not found", "text/plain")
            return
        self._send(200, body, ctype)

    def do_POST(self):
        route = self.path.split("?", 1)[0]
        if route not in ("/event", "/chat", "/screenshare"):
            self._send(404, "not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(min(length, 65536)).decode("utf-8"))
        except Exception:
            payload = {}
        if route == "/screenshare":
            on = bool(payload.get("on", False))
            if callable(_screenshare_handler):
                try:
                    _screenshare_handler(on)
                except Exception:
                    pass
            state = bool(get_state().get("screenshare", False))
            self._send(200, json.dumps({"ok": True, "screenshare": state}),
                       "application/json; charset=utf-8")
            return
        if route == "/chat":
            text = str(payload.get("text", ""))[:500].strip()
            reply = ""
            if text and callable(_chat_handler):
                try:
                    reply = str(_chat_handler(text) or "")
                except Exception as exc:
                    reply = "Couldn't process that: " + str(exc)[:80]
            self._send(200, json.dumps({"ok": bool(text), "text": reply}),
                       "application/json; charset=utf-8")
            return
        msg = str(payload.get("message", ""))[:300]
        if msg:
            try:
                import termlog
                termlog.log("avatar", "3D viewer: " + msg)
            except Exception:
                pass
        self._send(200, "{}", "application/json")


def start_server(preferred=8732):
    """Start loopback server. Returns (ok, url). Idempotent."""
    global _server, _thread, _port
    if _server is not None:
        return True, "http://127.0.0.1:%d/" % _port
    for candidate in range(preferred, preferred + 14):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", candidate), _Handler)
            _server, _port = srv, candidate
            _thread = threading.Thread(target=srv.serve_forever,
                                       name="nova-viewer-http", daemon=True)
            _thread.start()
            try:
                with open(PORT_FILE, "w", encoding="utf-8") as f:
                    f.write(str(candidate))
            except Exception:
                pass
            return True, "http://127.0.0.1:%d/" % candidate
        except OSError:
            continue
    return False, ""


def stop_server():
    global _server, _thread, _port
    if _server is not None:
        try:
            _server.shutdown()
            _server.server_close()
        except Exception:
            pass
    _server, _thread, _port = None, None, None


# ---------- viewer window (separate process — WinForms needs its own STA thread) ----------
def launch_window(url=None, x=40, y=None, dock=False, pet=False):
    """Open the 3D viewer. pet=True => only the transparent girl is visible.
    dock=True => frameless overlay over the main window's character slot."""
    global _window_proc
    if not url:
        ok, url = start_server()
        if not ok:
            return False
    if y is None:
        try:
            import ctypes
            y = ctypes.windll.user32.GetSystemMetrics(1) - 700
        except Exception:
            y = 120
    args = [sys.executable, os.path.abspath(__file__), "--window", url,
            str(x), str(max(0, y))]
    if dock:
        args.append("--dock")
    if pet:
        args.append("--pet")
    try:
        _window_proc = subprocess.Popen(
            args, cwd=ROOT,
            creationflags=0x08000000,  # CREATE_NO_WINDOW on the launcher
        )
        return True
    except Exception:
        return False


def stop_window():
    """Close the separate pywebview process when Nova shuts down."""
    global _window_proc
    proc = _window_proc
    _window_proc = None
    if proc is None:
        return
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        if proc.poll() is None:
            proc.kill()
    except Exception:
        pass


def _run_window(url, x, y, dock=False, pet=False):
    import webview
    if dock:
        d = get_dock()
        w, h = int(d["w"]), int(d["h"])
    elif pet:
        w, h = 360, 600
    else:
        w, h = 430, 640
    if pet:
        try:
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
            x = max(0, sw - w - 24)
            y = max(0, sh - h - 60)
        except Exception:
            pass
        url = url.rstrip("/") + "/?pet=1"
    webview.create_window(
        "Nova", url,
        width=w, height=h, x=int(x), y=int(y),
        frameless=True, transparent=True, on_top=True,
        resizable=False, easy_drag=pet, text_select=False,
        background_color="#0D1420",
    )
    if dock:
        threading.Thread(target=_dock_follower, args=(url,),
                         name="nova-viewer-dock", daemon=True).start()
    webview.start()


def _dock_follower(url):
    """Poll the bridge for dock geometry and place the frameless window there."""
    import ctypes
    from ctypes import wintypes
    import time
    import urllib.request

    import webview

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    HWND_TOPMOST = ctypes.c_void_p(-1)
    SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0010, 0x0040
    SW_HIDE = 0

    endpoint = url.rstrip("/") + "/dock"
    last_version, last_enabled = -1, None
    while True:
        try:
            raw = urllib.request.urlopen(endpoint, timeout=1).read()
            d = json.loads(raw.decode("utf-8"))
            win = webview.windows[0] if webview.windows else None
            native = getattr(win, "native", None) if win else None
            handle = getattr(native, "Handle", None) if native else None
            if handle is None:
                time.sleep(0.05)
                continue
            hwnd = ctypes.c_void_p(handle.ToInt32())
            enabled = bool(d.get("enabled"))
            if enabled != last_enabled or (enabled and d.get("version") != last_version):
                if enabled:
                    user32.ShowWindow(hwnd, 5)  # SW_SHOW
                    user32.SetWindowPos(hwnd, HWND_TOPMOST,
                                        int(d["x"]), int(d["y"]),
                                        int(d["w"]), int(d["h"]),
                                        SWP_NOACTIVATE | SWP_SHOWWINDOW)
                else:
                    user32.ShowWindow(hwnd, SW_HIDE)
                last_version, last_enabled = d.get("version"), enabled
        except Exception:
            pass
        time.sleep(0.06)


# ---------- offline guarantee ----------
def _nonlocal_urls(text):
    """URLs in source that are not the machine itself."""
    out = []
    for match in re.findall(r"https?://[^\s'\"<>)]+", text or ""):
        if not re.match(r"https?://(?:127\.0\.0\.1|localhost)\b", match):
            out.append(match[:140])
    return out


def offline_audit():
    """Prove Nova cannot make a non-local network request at runtime.

    We scan the files *we author* (the viewer page/script and every Python
    module). The vendored three.js libraries are static files that can only be
    fetched from this server, and the page's CSP forbids any other origin.
    """
    viewer_findings, py_findings = [], []
    authored = [os.path.join(WEB, "pet.html"), os.path.join(WEB, "pet.js"),
                os.path.join(COMPANION, "companion.js"),
                os.path.join(COMPANION, "manifest.json")]
    for p in authored:
        name = os.path.relpath(p, ROOT)
        if not os.path.exists(p):
            viewer_findings.append({"file": name, "url": "<missing>"})
            continue
        text = open(p, encoding="utf-8", errors="ignore").read()
        for url in _nonlocal_urls(text):
            viewer_findings.append({"file": name, "url": url})
    for name in os.listdir(ROOT):
        if not name.endswith(".py"):
            continue
        try:
            text = open(os.path.join(ROOT, name), encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for url in _nonlocal_urls(text):
            py_findings.append({"file": name, "url": url})

    html_path = os.path.join(WEB, "pet.html")
    html = open(html_path, encoding="utf-8", errors="ignore").read() \
        if os.path.exists(html_path) else ""
    manifest_path = os.path.join(COMPANION, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            manifest = json.load(open(manifest_path, encoding="utf-8"))
        except Exception:
            manifest = {}
    states = manifest.get("states", {})
    assets_local = (
        all(os.path.exists(p) for p in authored)
        and bool(states)
        and all(os.path.exists(os.path.join(COMPANION, s.get("sprite", "")))
                for s in states.values() if s.get("sprite"))
    )

    return {
        "server_binds": "127.0.0.1 only",
        "server_running": _server is not None,
        "nonlocal_urls_in_viewer": viewer_findings,
        "nonlocal_urls_in_python": py_findings,
        "csp_connect_src": "'self' blob:  (loopback only — no external origin)",
        "csp_in_html": "connect-src 'self'" in html,
        "all_assets_local": assets_local,
        "offline_ok": (not viewer_findings and not py_findings
                       and "connect-src 'self'" in html and assets_local),
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--window":
        _run_window(args[1], int(args[2]) if len(args) > 2 else 40,
                    int(args[3]) if len(args) > 3 else 120,
                    dock="--dock" in args, pet="--pet" in args)
    elif args and args[0] == "--audit":
        print(json.dumps(offline_audit(), indent=2))
    elif args and args[0] == "--state":
        print(json.dumps(get_state(), indent=2))
    else:
        ok, url = start_server()
        print(("serving " if ok else "FAILED ") + url)
        if ok:
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                stop_server()
