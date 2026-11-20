"""Nova's music control — 100% OFFLINE local-file playback.

No YouTube, no browser, no network, no downloads. Searches the local music
folders for an audio file matching the request and plays it with the machine's
own ffplay.  This is what keeps Nova's "no internet" guarantee honest while
still letting her play music.
"""
import os
import random
import subprocess
import threading
import time

# Prefer the real binary; the chocolatey\bin shim can spawn a second visible
# process path, which is how two copies of one track ended up playing at once.
FFPLAY = r"C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffplay.exe"
if not os.path.isfile(FFPLAY):
    FFPLAY = r"C:\ProgramData\chocolatey\bin\ffplay.exe"
AUDIO_EXT = (".mp3", ".wav", ".flac", ".m4a", ".opus", ".ogg", ".aac", ".wma")
LOCAL_DIRS = [r"D:\music"]
_proc = None
_lock = threading.RLock()   # start/stop are serialised: exactly one track at a time
_cache = {"at": 0.0, "files": []}


def _kill_all_ffplay():
    """Stop any ffplay started by another code path, not just our _proc."""
    try:
        subprocess.run(["taskkill", "/IM", "ffplay.exe", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=0x08000000, timeout=5)
    except Exception:
        pass


def _load_dirs():
    """Read optional local_dirs from config.json; never a network path."""
    global LOCAL_DIRS
    try:
        import json
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        with open(cfg_path, encoding="utf-8") as f:
            dirs = json.load(f).get("music", {}).get("local_dirs")
        if dirs:
            found = [d for d in dirs if os.path.isdir(d)]
            if found:
                LOCAL_DIRS = found
    except Exception:
        pass


_load_dirs()


def _library():
    """Cached local audio library (rescan at most every 5 minutes)."""
    if _cache["files"] and time.time() - _cache["at"] < 300:
        return _cache["files"]
    files = []
    for d in LOCAL_DIRS:
        if not os.path.isdir(d):
            continue
        for root, _dirs, names in os.walk(d):
            for name in names:
                if name.lower().endswith(AUDIO_EXT):
                    p = os.path.join(root, name)
                    try:
                        files.append({"path": p, "name": name,
                                      "size": os.path.getsize(p)})
                    except OSError:
                        pass
    files.sort(key=lambda x: x["name"].lower())
    _cache["files"] = files
    _cache["at"] = time.time()
    return files


def library_count():
    return len(_library())


def find_tracks(query=""):
    files = _library()
    stop_words = ("play", "some", "music", "a", "song", "me", "the",
                  "please", "on", "track", "for", "my")
    toks = [t for t in str(query).lower().split() if t not in stop_words]
    if not toks:
        return files
    return [f for f in files if all(t in f["name"].lower() for t in toks)]


def play(query="", shuffle=False):
    """Play a matching local file. Returns a result dict; never touches network."""
    global _proc
    hits = find_tracks(query)
    if not hits:
        return {"ok": False,
                "error": "no local track matched '%s'" % str(query).strip()[:40]}
    track = random.choice(hits) if shuffle else hits[0]
    if not os.path.isfile(FFPLAY):
        return {"ok": False, "error": "ffplay not found at " + FFPLAY}
    try:
        with _lock:
            stop()               # also kills any stray ffplay from another path
            _proc = subprocess.Popen(
                [FFPLAY, "-nodisp", "-autoexit", "-hide_banner", "-loglevel", "quiet",
                 track["path"]],
                shell=False, creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}
    return {"ok": True,
            "title": os.path.splitext(track["name"])[0],
            "creator": "local library",
            "genre": "offline",
            "path": track["path"]}


def stop():
    """Stop local playback (our process and any stray ffplay from a prior path)."""
    global _proc
    with _lock:
        proc, _proc = _proc, None
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
        _kill_all_ffplay()
        return proc is not None


if __name__ == "__main__":
    print("local tracks:", library_count())
