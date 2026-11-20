"""Use the local Qwen vision model to verify + advise on the sprite states.

Never sends anything off this PC: lm_client posts to the loopback LM Studio
server on 127.0.0.1:1234.
"""
import os
import sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lm_client

STATES = os.path.join(ROOT, "assets", "sprites", "states")
NAMES = ["idle", "talking", "blink", "happy", "sad", "angry", "surprised",
         "thinking", "waving", "dancing", "sleeping", "shy", "listening",
         "working", "explaining", "shrugging"]


def montage(cell=180, cols=4):
    rows = (len(NAMES) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 16)), (245, 245, 245))
    d = ImageDraw.Draw(sheet)
    for i, name in enumerate(NAMES):
        im = Image.open(os.path.join(STATES, name + ".png")).convert("RGBA")
        im.thumbnail((cell - 8, cell - 8), Image.NEAREST)
        x = (i % cols) * cell + (cell - im.width) // 2
        y = (i // cols) * (cell + 16)
        sheet.paste(im, (x, y), im)
        d.text(((i % cols) * cell + 4, y + cell - 2), name, fill=(0, 0, 0))
    return sheet


def main():
    question = (
        "16 pixel-art sprites of the same anime girl, in a 4x4 grid. "
        "Labels are under each sprite, reading order:\n"
        "idle, talking, blink, happy / sad, angry, surprised, thinking / "
        "waving, dancing, sleeping, shy / listening, working, explaining, shrugging.\n\n"
        "Reply with ONLY four short numbered lines, no thinking, no preamble:\n"
        "1. MISMATCHES: <list label numbers whose pose does not match, or none>\n"
        "2. SCALE/OFF-CENTER: <list worst label numbers, or none>\n"
        "3. CROPPED (head/feet cut off): <list label numbers, or none>\n"
        "4. HALOS/GRAY BITS: <list label numbers, or none>"
    )
    ans = lm_client.describe_image(montage(), question, max_tokens=2600)
    print(ans)


if __name__ == "__main__":
    main()
