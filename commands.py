"""Inbuilt command-search + learn-by-showing skill for Nova.

`search(query)` powers 'what can you do' / 'search command' over both the built-in
catalogue and commands the owner taught her. `learn()` saves a command she was
taught by seeing the screen; `match_learned()` recognises it later so she does
what the owner said. Everything is local (learned_commands.json).
"""
import json
import os
import re

LEARNED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learned_commands.json")

COMMANDS = [
    {"cmd": "chat", "action": "chat", "keywords": ["hi", "hello", "talk", "chat", "hey"],
     "desc": "Just type to talk to me — I remember our conversation."},
    {"cmd": "see screen", "action": "summarize", "keywords": ["see screen", "look", "what's on screen", "eyes"],
     "desc": "The SCREENSHARE panel always shows your screen; I read it every few seconds."},
    {"cmd": "read cursor", "action": "read_cursor", "keywords": ["where's my mouse", "what am i pointing", "read this",
                                        "hover", "under my cursor", "see where my mouse"],
     "desc": "I look where your mouse is hovering and read that line."},
    {"cmd": "summarize", "action": "summarize", "keywords": ["summarize", "summarise", "what is this paragraph",
                                      "explain this", "what does this say"],
     "desc": "I read the text on screen and give you a short summary."},
    {"cmd": "open app", "action": "open_app", "keywords": ["open", "launch", "start app", "notepad", "calculator", "brave"],
     "desc": "Say 'open notepad' etc. I ask approval, then launch it."},
    {"cmd": "switch app", "action": "switch_app", "keywords": ["alt tab", "switch app", "next window", "switch window"],
     "desc": "I can Alt+Tab to the next window (with your OK)."},
    {"cmd": "play music", "action": "play_music", "keywords": ["play music", "play a song", "some music", "track"],
     "desc": "I pick a real track from your local music index and play it in Brave."},
    {"cmd": "find games", "action": "game_search", "keywords": ["find games", "search games", "play a game", "list games"],
     "desc": "I search your installed Steam/GOG/Start Menu games and can launch one."},
    {"cmd": "play prank", "action": "prank", "keywords": ["prank", "mess around", "the hands", "cursor wiggle"],
     "desc": "Turn on ✋ Hands then I do a small reversible prank."},
    {"cmd": "voice", "action": "voice", "keywords": ["voice", "speak", "talk out loud", "audio"],
     "desc": "Toggle 🔊 and I speak my replies with Kokoro."},
    {"cmd": "remember", "action": "remember", "keywords": ["remember", "don't forget", "keep in mind"],
     "desc": "Say 'remember that ...' and I save it to memory."},
    {"cmd": "stop", "action": "stop", "keywords": ["stop", "pause", "shut up", "quiet", "resume"],
     "desc": "Type 'stop' to pause me; 'resume' to bring me back."},
]


def _load():
    try:
        with open(LEARNED_PATH, encoding="utf-8") as f:
            return json.load(f).get("commands", [])
    except Exception:
        return []


def _save(items):
    tmp = LEARNED_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"commands": items}, f, indent=2, ensure_ascii=False)
    os.replace(tmp, LEARNED_PATH)


def learn(phrase, action, target=None, context=None, note=None):
    """Save a command Nova was taught by seeing the screen. Dedupe by phrase."""
    items = _load()
    phrase = " ".join(str(phrase).split()).strip()
    if not phrase:
        return None
    entry = {"phrase": phrase, "action": action, "target": target,
             "context": (context or "")[:300], "note": note or "",
             "source": "taught-by-showing"}
    for i, c in enumerate(items):
        if c.get("phrase", "").lower() == phrase.lower():
            items[i] = entry
            _save(items)
            return entry
    items.append(entry)
    _save(items[-100:])
    return entry


def learned():
    return _load()


def match_learned(text):
    """Return the learned command whose phrase is spoken in `text`, else None."""
    low = " ".join(str(text).split()).lower()
    best, best_len = None, 0
    for c in _load():
        p = " ".join(str(c.get("phrase", "")).split()).lower()
        if p and p in low and len(p) > best_len:
            best, best_len = c, len(p)
    return best


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


def search(query):
    """Rank built-in + learned commands by keyword overlap with the query."""
    raw = " ".join(str(query).lower().split())
    learned = [
        {"cmd": c.get("phrase", "learned"), "action": c.get("action"),
         "keywords": [c.get("phrase", "")],
         "desc": "You taught me: " + (c.get("note") or c.get("action", "")),
         "learned": True}
        for c in _load()
    ]
    corpus = list(COMMANDS) + learned
    # "what can you do" / help -> show everything, not an empty result.
    if any(k in raw for k in ("what can you do", "what can u do", "help",
                              "commands", "list commands", "all commands")):
        return corpus
    q = _tokens(query)
    scored = []
    for c in corpus:
        terms = _tokens(c.get("cmd", ""))
        for kw in c.get("keywords", []):
            terms |= _tokens(kw)
        score = len(q & terms)                       # whole-token matches first
        if not score:                                # then singular/plural etc.
            score = sum(1 for t in q for w in terms
                        if len(t) >= 3 and len(w) >= 3 and (t in w or w in t))
        if score:
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored]


def describe_all():
    lines = ["- %s: %s" % (c["cmd"], c["desc"]) for c in COMMANDS]
    lines += ["- %s (you taught me): %s" % (c.get("phrase"), c.get("note") or c.get("action"))
              for c in _load()]
    return "\n".join(lines)


if __name__ == "__main__":
    for q in ("music", "what can you do", "mouse", "game"):
        print(q, "->", [c.get("cmd") or c.get("phrase") for c in search(q)])
