"""Nova's INNER THINKING, visible live in the terminal and in a log file.

Every thought, inner-voice exchange, reaction and reflection is printed to the
console the launcher opens ("Nova — Inner Thoughts") and appended to
nova_life.log. This is her private reasoning stream — computed state, not a
claim of consciousness.
"""
import os
import sys
import time

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_life.log")

ICONS = {
    "thought": "💭", "voice": "🗣", "impulse": "⚡", "reason": "🧠",
    "coach": "🎮", "reflect": "✦", "evolve": "🌱", "remark": "💬",
    "dance": "💃", "system": "⚙", "afk": "👀", "life": "♥",
}


def log(kind, text, voice=None):
    stamp = time.strftime("%H:%M:%S")
    icon = ICONS.get(kind, "•")
    who = (" [%s]" % voice) if voice else ""
    line = "[%s] %s%s %s" % (stamp, icon, who, " ".join(str(text).split()))
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    return line


def banner():
    line = "=" * 68
    log("life", line)
    log("life", "NOVA — inner thinking stream (computed state, not sentience)")
    log("life", "Two voices: Impulse / Reason  |  log file: " + LOG_PATH)
    log("life", line)


if __name__ == "__main__":
    banner()
    log("thought", "test thought")
