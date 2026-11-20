"""Make sure Nova's two local LM Studio models are loaded.

Only touches the loopback LM Studio server on 127.0.0.1:1234. If a model is
already loaded, it is skipped immediately — this is what used to hang the old
launcher (`lms load ... -y` blocks forever when the model is resident).
"""
import json
import subprocess
import urllib.request

LMS = r"C:\Program Files\LM Studio\resources\app\.webpack\lms.exe"
BASE = "http://127.0.0.1:1234"
MODELS = [
    ("nvidia/nemotron-3-nano-4b", 8192),   # chat brain
    ("qwen3.5-0.8b", 8192),                # eyes / vision
]


def _urlopen(path, timeout=3):
    return urllib.request.urlopen(BASE + path, timeout=timeout)


def server_up():
    try:
        _urlopen("/v1/models").close()
        return True
    except Exception:
        return False


def loaded_keys():
    """Keys of models with at least one loaded instance on the local server."""
    try:
        with _urlopen("/api/v1/models") as response:
            data = json.load(response)
        return {m.get("key") for m in data.get("models", [])
                if m.get("loaded_instances")}
    except Exception:
        return set()


def ensure(key, ctx):
    if key in loaded_keys():
        print("[ok]     %s already loaded" % key)
        return
    print("[loading] %s ..." % key)
    try:
        subprocess.run(
            [LMS, "load", key, "--gpu", "max",
             "--context-length", str(ctx), "--parallel", "1", "-y"],
            timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("[ok]     %s loaded" % key)
    except subprocess.TimeoutExpired:
        # A slow first load must not block Nova from starting forever.
        print("[warn]   %s load timed out — continuing anyway" % key)
    except Exception as exc:
        print("[warn]   %s load failed (%s) — continuing" % (key, exc))


def main():
    if not server_up():
        print("[start] LM Studio server")
        try:
            subprocess.run(
                [LMS, "server", "start", "--port", "1234", "--bind", "127.0.0.1"],
                timeout=45, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            print("[warn] server start: %s" % exc)
    else:
        print("[ok]     LM Studio server already running")
    for key, ctx in MODELS:
        ensure(key, ctx)


if __name__ == "__main__":
    main()
