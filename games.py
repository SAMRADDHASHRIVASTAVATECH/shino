"""Nova's game discovery + launch preparation.

Finds locally installed games (Steam / GOG / Epic / Start Menu) so Nova can
'search games and proceed'. Launching is never done here directly — this only
builds a target that hands.py executes AFTER the owner approves it.
"""
import glob
import os
import re


def _steam():
    out = []
    roots = [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]
    for root in roots:
        for acf in glob.glob(os.path.join(root, "steamapps", "appmanifest_*.acf")):
            try:
                txt = open(acf, encoding="utf-8", errors="ignore").read()
                name = re.search(r'"name"\s+"([^"]+)"', txt)
                appid = re.search(r'"appid"\s+"(\d+)"', txt)
                if name and appid:
                    out.append({"name": name.group(1), "target": "steam://rungameid/" + appid.group(1),
                                "source": "Steam"})
            except Exception:
                pass
    return out


def _gog():
    out = []
    for root in (r"C:\GOG Games",):
        if not os.path.isdir(root):
            continue
        for d in os.listdir(root):
            p = os.path.join(root, d)
            if os.path.isdir(p):
                exes = glob.glob(os.path.join(p, "*.exe"))
                out.append({"name": d, "target": exes[0] if exes else p, "source": "GOG"})
    return out


def _start_menu():
    out = []
    roots = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    ]
    skip = ("uninstall", "tools", "administrative", "accessories", "system")
    for root in roots:
        for lnk in glob.glob(os.path.join(root, "**", "*.lnk"), recursive=True):
            name = os.path.splitext(os.path.basename(lnk))[0]
            if any(s in name.lower() for s in skip):
                continue
            out.append({"name": name, "target": lnk, "source": "Start Menu"})
    return out


def installed():
    seen, out = set(), []
    for g in _steam() + _gog() + _start_menu():
        k = g["name"].lower()
        if k not in seen:
            seen.add(k)
            out.append(g)
    return out


def find(query=""):
    games = installed()
    toks = [t for t in query.lower().split() if t not in ("play", "game", "some", "a", "the", "me")]
    if not toks:
        return games[:12]
    return [g for g in games if all(t in g["name"].lower() for t in toks)][:12]


def prepare(query):
    """Return a launch proposal target for the best matching game, or None."""
    hits = find(query)
    return hits[0] if hits else None
