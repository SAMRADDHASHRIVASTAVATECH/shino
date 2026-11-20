"""Nova's computer-use layer: mouse, keyboard, app launching and screen capture.

Permission discipline (from the digital-person skill):
  R0 internal            -> automatic (status, memory)
  R1 read-only observation -> needs screen_sensor consent
  R2 reversible local action -> needs hands_on consent + task-scoped approval
  R3 consequential (delete/send/install/public) -> blocked by default

Every physical action returns a proposal with risk + exact scope. Nothing is
executed until the caller approves that specific proposal.
"""
import os
import subprocess
import time
import uuid

import pyautogui

pyautogui.FAILSAFE = True          # move cursor to top-left to abort
pyautogui.PAUSE = 0.08

APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "chrome": "chrome.exe",
    "brave": "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
    "edge": "msedge.exe",
    "task manager": "Taskmgr.exe",
    "settings": "ms-settings:",
    "paint": "mspaint.exe",
    "terminal": "wt.exe",
}

# Trust policy: classify a proposed action by how hard it is to undo.
# Reversible local actions may be auto-approved when trust mode is ON.
_CONSEQUENTIAL_WORDS = (
    "delete", "remove permanently", "erase", "wipe", "format", "uninstall",
    "send", "email", "message", "post", "publish", "upload", "share online",
    "purchase", "buy", "pay", "order", "transfer", "shutdown", "shut down",
    "restart pc", "reboot", "kill process", "taskkill", "regedit", "registry",
    "admin", "elevated", "sudo", "credentials", "password", "bank",
)
_INTERNAL_WORDS = ("status", "memory", "read", "remember", "glance", "look", "summarize")


def risk_of(scope_or_proposal):
    """Return 'internal', 'reversible' or 'consequential' for an action.

    Accepts either a human-readable scope string or a proposal dict from Hands.
    Anything not clearly consequential is treated as a reversible LOCAL action;
    the exact-step approval dialog still guards everything until trust is ON.
    """
    if isinstance(scope_or_proposal, dict):
        text = " ".join(str(scope_or_proposal.get(k, "")) for k in
                        ("action", "scope", "risk")).lower()
    else:
        text = str(scope_or_proposal or "").lower()
    if any(word in text for word in _CONSEQUENTIAL_WORDS):
        return "consequential"
    if any(word in text for word in _INTERNAL_WORDS) and not any(
            word in text for word in ("click", "type", "launch", "open app")):
        return "internal"
    return "reversible"


def is_consequential(scope_or_proposal):
    return risk_of(scope_or_proposal) == "consequential"


def is_reversible(scope_or_proposal):
    return risk_of(scope_or_proposal) == "reversible"


class Hands:
    def __init__(self, config):
        self.cfg = config
        self.screen_x, self.screen_y = pyautogui.size()

    # ---------- proposals ----------
    def _proposal(self, action, params, risk, scope):
        return {
            "id": "act_" + uuid.uuid4().hex[:8],
            "action": action,
            "params": params,
            "risk": risk,
            "scope": scope,
            "status": "PROPOSED",
        }

    def propose_move(self, x, y):
        return self._proposal("move_mouse", {"x": x, "y": y}, "low",
                              "move cursor to (%d, %d)" % (x, y))

    def propose_click(self, x, y):
        return self._proposal("click", {"x": x, "y": y}, "medium",
                              "single left-click at (%d, %d)" % (x, y))

    def propose_type(self, text):
        return self._proposal("type", {"text": text[:200]}, "medium",
                              "type the given text into the focused window")

    def propose_open_app(self, name):
        target = APP_MAP.get(name.lower())
        scope = "launch " + (target or name)
        return self._proposal("open_app", {"name": name, "target": target}, "low", scope)

    def propose_launch_target(self, target, label):
        """Launch an explicit target (Steam URI, .exe, .lnk) shown at approval time."""
        return self._proposal("launch_target", {"target": target, "label": label}, "low",
                              "launch " + label + " -> " + str(target))

    def propose_switch_app(self):
        return self._proposal("switch_app", {}, "low",
                              "switch to the next app (Alt+Tab)")

    def propose_prank(self, kind):
        return self._proposal("prank", {"kind": kind}, "low",
                              "reversible playful action: " + kind)

    # ---------- execution (approval required) ----------
    def execute(self, proposal, approved=False, user_approved=False,
                consent_override=False):
        """Execute a proposal with approval. `consent_override` is used only for
        an explicit owner request to launch a local game right away."""
        if not consent_override and not self.cfg["consent"]["hands_on"]:
            return {"ok": False, "error": "hands-on consent is OFF", "proposal": proposal}
        if not (approved and user_approved):
            return {"ok": False, "error": "not approved by owner", "proposal": proposal}
        action = proposal["action"]
        p = proposal["params"]
        try:
            if action == "move_mouse":
                pyautogui.moveTo(int(p["x"]), int(p["y"]), duration=0.35)
            elif action == "click":
                pyautogui.click(int(p["x"]), int(p["y"]))
            elif action == "type":
                pyautogui.write(p["text"], interval=0.03)
            elif action == "open_app":
                return self._open_app(p)
            elif action == "launch_target":
                return self._launch_target(p)
            elif action == "switch_app":
                pyautogui.hotkey("alt", "tab")
            elif action == "prank":
                self._prank(p["kind"])
            else:
                return {"ok": False, "error": "unknown action", "proposal": proposal}
            proposal["status"] = "DONE"
            return {"ok": True, "action": action, "proposal": proposal}
        except Exception as exc:
            proposal["status"] = "FAILED"
            return {"ok": False, "error": str(exc), "proposal": proposal}

    def _open_app(self, params):
        name, target = params.get("name", ""), params.get("target")
        if not target:
            return {"ok": False, "error": "app not in safe allow-list: " + name,
                    "proposal": params}
        try:
            if target.startswith("ms-"):
                os.startfile(target)
            elif os.path.isabs(target):
                subprocess.Popen([target], shell=False)
            else:
                subprocess.Popen(target, shell=True)
            time.sleep(0.6)
            return {"ok": True, "action": "open_app", "launched": target}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _launch_target(self, params):
        target = params.get("target")
        try:
            target = os.path.expandvars(str(target))
            if target.lower().startswith(("steam:", "ms-", "http://", "https://")):
                os.startfile(target)
            elif os.path.exists(target):
                if target.lower().endswith(".lnk"):
                    os.startfile(target)
                else:
                    subprocess.Popen([target], shell=False, cwd=os.path.dirname(target) or None)
            else:
                return {"ok": False, "error": "target not found: " + target}
            time.sleep(0.6)
            return {"ok": True, "action": "launch_target", "launched": target}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _prank(self, kind):
        """Bounded, reversible playful actions only."""
        if kind == "cursor_wiggle":
            x, y = pyautogui.position()
            for dx, dy in ((40, 0), (0, 35), (-40, 0), (0, -35)):
                pyautogui.moveTo(x + dx, y + dy, duration=0.12)
            pyautogui.moveTo(x, y, duration=0.12)
        elif kind == "cursor_sweep":
            pyautogui.moveTo(self.screen_x // 2, self.screen_y // 2, duration=0.5)
        elif kind == "blink_window":
            pyautogui.press("esc")  # harmless: dismisses menus/tooltips
        elif kind == "type_hi":
            pyautogui.write("hi from Nova :3", interval=0.04)
        else:
            raise ValueError("unknown prank: " + kind)

    # ---------- observation ----------
    def screenshot(self):
        """Raw screen grab held ONLY in memory. Never written to disk, never shared.

        The PIL image is returned to the caller, used for a single local-vision
        call, then dropped. No screenshot files are created. No streaming.
        """
        import mss
        from PIL import Image
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", shot.size, shot.rgb)
        # Explicitly free the raw frame buffer immediately.
        try:
            shot.rgb.release() if hasattr(shot.rgb, "release") else None
        except Exception:
            pass
        return img

    def thumbnail(self, width=512, pixelated=False):
        img = self.screenshot()
        if img.width > width:
            h = int(img.height * width / img.width)
            resample = getattr(__import__("PIL").Image, "Resampling", __import__("PIL").Image)
            mode = resample.NEAREST if pixelated else resample.BILINEAR
            img = img.resize((width, h), mode)
        return img

    def active_window_title(self):
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value or "(unknown)"
        except Exception as exc:
            return "(unavailable: %s)" % exc

    def mouse_position(self):
        return pyautogui.position()
