"""Nova's VOICES — two spoken Kokoro voices + switching/adding, all local.

The warm GPU service at C:\\Users\\HP\\.config\\opencode\\tts (port 8899) does the
synthesis. This module:
  - keeps TWO named voice slots ("Impulse" = fast/dramatic, "Reason" = calm),
  - speaks chat through the ACTIVE slot,
  - speaks inner-thought exchanges with both voices, one after the other,
  - lets the owner change a slot's voice or add a brand-new voice, persisted
    in voices.json.

Kokoro's KPipeline lazily loads a voice on first use, so a new valid voice id
is warmed with a tiny test utterance before it is saved.
"""
import json
import os
import subprocess
import threading
import time
import urllib.request

TTS_DIR = r"C:\Users\HP\.config\opencode\tts"
HEALTH = "http://127.0.0.1:8899/health"
VOICES_URL = "http://127.0.0.1:8899/voices"
TTS_URL = "http://127.0.0.1:8899/tts"
SPEAK = os.path.join(TTS_DIR, "speak.py")
STARTER = os.path.join(TTS_DIR, "start-kokoro.cmd")
PYTHON = r"C:\Users\HP\AppData\Local\Programs\Python\Python312\python.exe"
REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices.json")

# Default two voices: a warm/energetic one and a calmer contrasting one.
DEFAULT_REGISTRY = {
    "active": "Impulse",
    "slots": {
        "Impulse": {"kokoro": "af_heart", "label": "Nova — bright & impulsive",
                    "style": "fast, dramatic, feeling-first"},
        "Reason": {"kokoro": "af_bella", "label": "Nova — calm & thoughtful",
                   "style": "soft, steady, reflective"},
    },
}

# Common Kokoro voice ids offered by `list voices` (server reports the cached ones).
KNOWN_KOKORO = (
    "af_heart", "af_bella", "af_sarah", "af_nicole", "af_sky", "af_aoede", "af_jessica",
    "af_kore", "af_nova", "af_river", "am_adam", "am_michael", "am_echo", "am_eric",
    "am_fenrir", "am_liam", "am_onyx", "am_puck", "am_santa", "bf_emma", "bf_isabella",
    "bm_george", "bm_lewis", "bm_daniel", "bm_fable", "bm_joyce",
)

_queue = None                  # created lazily; replaced with a real Queue
_speaker_thread = None
SPEAK_HOOK = None               # optional on/off callback for the 3D avatar's mouth


def set_speak_hook(fn):
    """Register a callback invoked with True before speech and False after."""
    global SPEAK_HOOK
    SPEAK_HOOK = fn


def _load():
    try:
        with open(REGISTRY, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("slots"):
            return data
    except Exception:
        pass
    _save(DEFAULT_REGISTRY)
    return json.loads(json.dumps(DEFAULT_REGISTRY))


def _save(data):
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, REGISTRY)


def registry():
    return _load()


def slots():
    return _load().get("slots", {})


def active_slot():
    data = _load()
    name = data.get("active", "Impulse")
    return name, data.get("slots", {}).get(name, {})


# ---------- server ----------
def healthy():
    try:
        with urllib.request.urlopen(HEALTH, timeout=3) as r:
            return "ok" in r.read().decode("utf-8").lower()
    except Exception:
        return False


def ensure_server():
    """Start the GPU TTS service if needed (cold boot ~65-90s)."""
    if healthy():
        return True
    if os.path.exists(STARTER):
        subprocess.Popen(["cmd", "/c", STARTER], cwd=TTS_DIR, shell=False)
    for _ in range(30):
        time.sleep(3)
        if healthy():
            return True
    return False


def cached_voices():
    try:
        with urllib.request.urlopen(VOICES_URL, timeout=3) as r:
            return json.loads(r.read().decode("utf-8")).get("cached", [])
    except Exception:
        return []


# ---------- voice management ----------
def list_voices():
    """Human-readable summary of Nova's two slots + what the server can do."""
    data = _load()
    lines = []
    for name, spec in data.get("slots", {}).items():
        marker = " <-- active" if name == data.get("active") else ""
        lines.append("%s: %s (%s)%s" % (
            name, spec.get("kokoro"), spec.get("label", spec.get("style", "")), marker))
    cached = cached_voices()
    if cached:
        lines.append("loaded on server: " + ", ".join(cached))
    lines.append("known Kokoro ids: " + ", ".join(KNOWN_KOKORO[:14]) + ", ...")
    return "\n".join(lines)


def set_voice(target=None, kokoro_id=None):
    """Switch the active slot, or set a slot's Kokoro id.

    set_voice("Reason")            -> make Reason the speaking voice
    set_voice("Impulse", "af_bella")-> change Impulse's Kokoro voice
    set_voice(kokoro_id="am_michael") -> change the active slot's Kokoro voice
    """
    data = _load()
    target = str(target or "").strip()
    if kokoro_id and not target:
        target = data.get("active", "Impulse")
    # Switching by bare voice id: find a slot already using it, else set active.
    if target and not kokoro_id and target not in data["slots"]:
        found = next((n for n, s in data["slots"].items()
                      if s.get("kokoro", "").lower() == target.lower()), None)
        if found:
            data["active"] = found
            _save(data)
            return "Voice switched to %s (%s)." % (found, data["slots"][found]["kokoro"])
        kokoro_id, target = target, data.get("active", "Impulse")
    if target in data["slots"] and kokoro_id:
        warm = _warm(kokoro_id)
        if not warm.get("ok"):
            return "That voice failed to load: " + str(warm.get("error"))[:90]
        data["slots"][target]["kokoro"] = kokoro_id
        data["active"] = target
        _save(data)
        return "Changed %s to %s — saying hi in my new voice~" % (target, kokoro_id)
    if target in data["slots"]:
        data["active"] = target
        _save(data)
        return "Voice switched to %s (%s)." % (target, data["slots"][target]["kokoro"])
    return "I don't know that voice slot. Say 'list voices' to see them."


def add_voice(name, kokoro_id=None, label=None):
    """Add/register a new voice. If only an id is given, the name is the id.
    Warms it with a tiny utterance first so we never save a broken voice.
    """
    name = " ".join(str(name or "").split())
    if not name:
        return "Give the voice a name, e.g. 'add voice am_michael'."
    if not kokoro_id:
        kokoro_id = name if name in KNOWN_KOKORO or name.startswith(("af_", "am_", "bf_", "bm_")) else None
    if not kokoro_id:
        return "I need a Kokoro voice id too, e.g. 'add voice Robo am_michael'."
    warm = _warm(kokoro_id)
    if not warm.get("ok"):
        return "That voice didn't work: " + str(warm.get("error"))[:90]
    data = _load()
    data["slots"][name] = {"kokoro": kokoro_id, "label": label or "custom voice",
                           "style": "custom — added by owner"}
    data["active"] = name
    _save(data)
    return "Added voice '%s' (%s). Now speaking with it~" % (name, kokoro_id)


def _warm(kokoro_id):
    """Synthesize 'Hi.' to validate + cache a voice id on the server."""
    import urllib.error
    body = json.dumps({"text": "Hi.", "voice": kokoro_id, "speed": 1.0}).encode("utf-8")
    try:
        req = urllib.request.Request(TTS_URL, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            r.read(64)
        return {"ok": True}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": "HTTP %s" % exc.code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


# ---------- speaking (serialised so two voices never overlap) ----------
def _enqueue(text, slot=None, kokoro_id=None, speed=1.0):
    global _queue, _speaker_thread
    if _queue is None:
        import queue as _q
        _queue = _q.Queue()
    _queue.put((str(text), slot, kokoro_id, speed))
    if _speaker_thread is None or not _speaker_thread.is_alive():
        _speaker_thread = threading.Thread(target=_speaker_worker, daemon=True)
        _speaker_thread.start()


def _speaker_worker():
    while True:
        text, slot, kokoro_id, speed = _queue.get()
        try:
            if not ensure_server():
                continue
            if not kokoro_id:
                spec = slots().get(slot) if slot else None
                if not spec and slot in KNOWN_KOKORO:
                    kokoro_id = slot
                elif not spec:
                    _, spec = active_slot()
                kokoro_id = kokoro_id or (spec or {}).get("kokoro", "af_heart")
            clean = " ".join(text.split())[:240]
            hook = SPEAK_HOOK
            if callable(hook):
                try:
                    hook(True)
                except Exception:
                    pass
            try:
                subprocess.run(
                    [PYTHON, SPEAK, "--voice", kokoro_id, "--speed", str(speed), clean],
                    cwd=TTS_DIR, shell=False,
                    creationflags=0x08000000,   # CREATE_NO_WINDOW
                    timeout=120,
                )
            finally:
                if callable(hook):
                    try:
                        hook(False)
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            _queue.task_done()


def speak_async(text, slot=None, kokoro_id=None, speed=1.0):
    """Fire-and-forget speech through the active slot (or a named slot)."""
    _enqueue(text, slot=slot, kokoro_id=kokoro_id, speed=speed)


def speak_exchange(lines, delay=0.35):
    """Speak a two-voice inner exchange: each line uses its own voice, in order."""
    for item in lines or []:
        _enqueue(item.get("text", ""), slot=item.get("voice"),
                 kokoro_id=item.get("kokoro_id"), speed=item.get("speed", 1.0))
        if delay:
            time.sleep(delay)


if __name__ == "__main__":
    print(list_voices())
