"""Nova's LOCAL environment senses — read-only, no network, no screenshots saved.

Feeds the life loop with:
  - Windows activity detector (GetLastInputInfo) -> is the owner actually there?
  - CPU / per-core load, CPU temp (best effort), GPU temp/memory/util (nvidia-smi)
  - Active window + process -> coding / gaming detection
  - Active audio sessions -> "music is playing" (so Nova can dance)

Every probe degrades gracefully: a missing sensor returns None/[] and never raises.
"""
import ctypes
import subprocess
import time
from ctypes import wintypes

try:
    import psutil
except Exception:                                    # pragma: no cover
    psutil = None

CREATE_NO_WINDOW = 0x08000000

CODING_HINTS = (
    "visual studio code", "pycharm", "intellij", "cursor", "sublime", "notepad++",
    "windows terminal", "powershell", "cmd.exe", "python", "jupyter", "android studio",
    "webstorm", "jetbrains", "git bash", "code.exe", "python.exe", "py.exe",
)
GAMING_HINTS = (
    "minecraft", "steam", "epic games", "fortnite", "gta", "valorant", "league of legends",
    "counter-strike", "cyberpunk", "balatro", "stardew", "roblox", "game",
)
MEDIA_PROCS = (
    "spotify", "itunes", "vlc", "foobar2000", "musicbee", "aimp", "groove music",
    "wmplayer", "brave", "chrome", "msedge",
)


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds():
    """Seconds since the last real mouse/keyboard input (Windows activity detector)."""
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        get_tick64 = ctypes.windll.kernel32.GetTickCount64
        get_tick64.restype = ctypes.c_ulonglong
        delta = (get_tick64() - lii.dwTime) & 0xFFFFFFFF
        return max(0.0, delta / 1000.0)
    except Exception:
        return 0.0


def foreground_window():
    """Return (window title, process name) for the active window."""
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        length = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        u32.GetWindowTextW(hwnd, buf, length + 1)
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc = ""
        if psutil:
            try:
                proc = psutil.Process(pid.value).name()
            except Exception:
                pass
        return buf.value or "(unknown)", proc
    except Exception:
        return "(unknown)", ""


def _num(value):
    try:
        return float(str(value).strip())
    except Exception:
        return None


_GPU_CACHE = {"t": 0.0, "data": {}}


def gpu_stats(ttl=5.0):
    """NVIDIA GPU temp / memory / utilisation via nvidia-smi (cached)."""
    now = time.time()
    if now - _GPU_CACHE["t"] < ttl:
        return _GPU_CACHE["data"]
    data = {}
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, creationflags=CREATE_NO_WINDOW,
        )
        parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
        if len(parts) >= 5:
            data = {"name": parts[0], "temp": _num(parts[1]), "mem_used": _num(parts[2]),
                    "mem_total": _num(parts[3]), "util": _num(parts[4])}
    except Exception:
        pass
    _GPU_CACHE["t"], _GPU_CACHE["data"] = now, data
    return data


_TEMP_CACHE = {"t": 0.0, "value": None}


def cpu_temp(ttl=30.0):
    """CPU temperature in Celsius if the firmware exposes it, else None."""
    now = time.time()
    if now - _TEMP_CACHE["t"] < ttl:
        return _TEMP_CACHE["value"]
    value = None
    try:
        out = subprocess.run(
            ["wmic", r"/namespace:\\root\wmi", "PATH", "MSAcpi_ThermalZoneTemperature",
             "get", "CurrentTemperature", "/value"],
            capture_output=True, text=True, timeout=2, creationflags=CREATE_NO_WINDOW,
        )
        for line in out.stdout.splitlines():
            if "=" in line and "CurrentTemperature" in line:
                raw = _num(line.split("=", 1)[1])
                if raw and raw > 1000:
                    value = round(raw / 10.0 - 273.15, 1)
                    break
    except Exception:
        pass
    _TEMP_CACHE["t"], _TEMP_CACHE["value"] = now, value
    return value


def audio_activity():
    """Names of processes currently producing audio (pycaw), best effort."""
    try:
        from pycaw.pycaw import AudioUtilities
        active = []
        for session in AudioUtilities.GetAllSessions():
            try:
                if int(getattr(session, "State", 0) or 0) != 2:      # 2 = ACTIVE
                    continue
                name = ""
                proc = getattr(session, "Process", None)
                if isinstance(proc, dict):
                    name = str(proc.get("name", ""))
                elif proc is not None:
                    name = getattr(proc, "name", "")
                    if callable(name):
                        name = name()
                peak = float(getattr(session, "PeakValue", 0) or 0)
                if name or peak > 0.0003:
                    active.append(str(name or "audio"))
            except Exception:
                continue
        return active
    except Exception:
        return []


class SystemSenses:
    """Pollable snapshot of the machine + owner state."""

    def __init__(self, thresholds=None):
        self.thresholds = dict(thresholds or {})
        self._music_flag_until = 0.0
        if psutil:
            psutil.cpu_percent(interval=None)            # seed the rolling calculation

    def note_music(self, playing=True, seconds=900):
        """Nova's own playback sets this so she knows she's the one making music."""
        self._music_flag_until = time.time() + seconds if playing else 0.0

    def poll(self):
        idle = idle_seconds()
        window, proc = foreground_window()
        hay = (window + " " + proc).lower()

        cpu = psutil.cpu_percent(interval=None) if psutil else None
        cores = psutil.cpu_percent(interval=None, percpu=True) if psutil else []
        gpu = gpu_stats()
        temp_cpu = cpu_temp()
        audio = audio_activity()
        media_running = [p for p in MEDIA_PROCS if p in hay]
        music = (time.time() < self._music_flag_until) or bool(audio) or bool(media_running)

        th = self.thresholds
        high_cpu = cpu is not None and cpu >= float(th.get("cpu_high_pct", 88))
        hot_gpu = gpu.get("temp") is not None and gpu["temp"] >= float(th.get("gpu_temp_high_c", 78))
        mem_pct = (100.0 * gpu["mem_used"] / gpu["mem_total"]) if gpu.get("mem_total") else None
        high_mem = mem_pct is not None and mem_pct >= float(th.get("gpu_mem_high_pct", 92))
        hot_cpu = temp_cpu is not None and temp_cpu >= 85
        strained = high_cpu or hot_gpu or high_mem or hot_cpu

        return {
            "ts": time.time(),
            "idle_s": round(idle, 1),
            "present": idle < float(th.get("afk_seconds", 40)),
            "cpu": round(cpu, 1) if cpu is not None else None,
            "cpu_cores": [round(c, 1) for c in cores] if cores else [],
            "cpu_temp": temp_cpu,
            "gpu_name": gpu.get("name"),
            "gpu_temp": gpu.get("temp"),
            "gpu_mem_used": gpu.get("mem_used"),
            "gpu_mem_total": gpu.get("mem_total"),
            "gpu_mem_pct": round(mem_pct, 1) if mem_pct is not None else None,
            "gpu_util": gpu.get("util"),
            "window": window,
            "process": proc,
            "coding": any(h in hay for h in CODING_HINTS),
            "gaming": any(h in hay for h in GAMING_HINTS),
            "audio_sessions": audio,
            "music_playing": music,
            "strained": strained,
            "strain_reasons": [r for r, on in (
                ("CPU load", high_cpu), ("GPU heat", hot_gpu),
                ("GPU memory", high_mem), ("CPU heat", hot_cpu)) if on],
        }


if __name__ == "__main__":
    import json
    s = SystemSenses()
    print(json.dumps(s.poll(), indent=2))
