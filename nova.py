"""Nova Companion entry point: load config and launch the avatar."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import avatar


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
        config = json.load(f)
    # Hard rule: Nova never speaks aloud — she replies only in chat.
    # This cannot be overridden by config or by a "say" command.
    config.setdefault("consent", {})["voice"] = False

    # Default: just the anime girl on the desktop (no control panel).
    # --gui keeps the older full dashboard.
    avatar.run(config, pet="--gui" not in sys.argv)


if __name__ == "__main__":
    main()
