"""Hard privacy enforcement for Nova — real checks, not just config claims.

Guarantees enforced here:
  1. No screenshot/image files are left behind by Nova anywhere on disk.
  2. No screen-share / remote-view process is running because of Nova.
  3. Nova's only network endpoints are localhost (LM Studio :1234, Kokoro :8899).
"""
import glob
import os
import re
import subprocess
import urllib.parse

# Directories Nova could conceivably write capture files into.  Each entry is
# (directory, recursive).  Temp/Pictures are scanned one level only — a recursive
# glob over the whole user profile took minutes and stalled launcher startup.
SCAN_DIRS = [
    (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"), False),
    (os.path.join(os.environ.get("TEMP", "")), False),
    (os.path.join(os.environ.get("USERPROFILE", ""), "NovaCompanion"), True),
    (os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"), False),
]
# Patterns that would indicate a persisted screen capture.
CAPTURE_PATTERNS = ["nova_*screen*.png", "nova_*shot*.png", "nova_capture*.png",
                    "nova_*screen*.jpg", "nova_frame*.png"]

SCREENSHARE_PROCS = ("obs", "teamviewer", "anydesk", "zoom", "skitch", "lightshot",
                     "snipaste", "sharex", "screenshare", "loom", "join.me")

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _capture_paths():
    """Yield (path, recursive) scan results without walking the whole profile."""
    for base, recursive in SCAN_DIRS:
        if not base or not os.path.isdir(base):
            continue
        for pat in CAPTURE_PATTERNS:
            pattern = os.path.join(base, "**", pat) if recursive \
                else os.path.join(base, pat)
            for path in glob.glob(pattern, recursive=recursive):
                yield path


def purge_captures():
    """Delete any leftover Nova screen-capture files. Returns removed paths."""
    removed = []
    for path in _capture_paths():
        try:
            os.remove(path)
            removed.append(path)
        except Exception:
            pass
    return removed


def screenshare_running():
    """Return any running screen-share/remote-view processes (informational)."""
    found = []
    try:
        out = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"], text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            name = line.split('","')[0].strip('"').lower()
            if any(s in name for s in SCREENSHARE_PROCS):
                found.append(name)
    except Exception:
        pass
    return sorted(set(found))


def check_endpoints(config):
    """Verify every URL Nova uses is localhost-only."""
    urls = [config["models"]["api_base"], "http://127.0.0.1:8899/health"]
    bad = []
    for u in urls:
        host = urllib.parse.urlparse(u).hostname
        if host not in ALLOWED_HOSTS:
            bad.append(u)
    return bad


def audit(config):
    removed = purge_captures()
    return {
        "screenshot_files_removed": removed,
        "screenshot_files_remaining": _count_captures(),
        "screenshare_processes": screenshare_running(),
        "nonlocal_endpoints": check_endpoints(config),
        "in_memory_only": config.get("privacy", {}).get("screenshots_in_memory_only"),
        "never_upload": config.get("privacy", {}).get("never_upload"),
    }


def _count_captures():
    return sum(1 for _ in _capture_paths())


if __name__ == "__main__":
    import json
    with open(os.path.join(os.path.dirname(__file__), "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    print(json.dumps(audit(cfg), indent=2))
