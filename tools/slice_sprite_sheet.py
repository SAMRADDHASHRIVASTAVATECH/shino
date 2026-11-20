"""Slice Nova's 4x4 pixel-art state sheet into individual transparent sprites.

Source: the 1024x1024 sheet the user supplied (opaque background).
State order is the user-confirmed 4x4 reading order.
"""
import os
from PIL import Image
from rembg import remove, new_session

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"C:\Users\HP\Desktop\7b74e973-ab14-47dc-8131-85bd42f230a1.webp"
OUT = os.path.join(ROOT, "assets", "sprites", "states")

NAMES = [
    "idle", "talking", "blink", "happy",
    "sad", "angry", "surprised", "thinking",
    "waving", "dancing", "sleeping", "shy",
    "listening", "working", "explaining", "shrugging",
]


def main():
    os.makedirs(OUT, exist_ok=True)
    sheet = Image.open(SRC).convert("RGBA")
    w, h = sheet.size
    cw, ch = w // 4, h // 4
    session = new_session("u2netp")  # small model, cached locally

    for i, name in enumerate(NAMES):
        row, col = divmod(i, 4)
        cell = sheet.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
        cut = remove(cell, session=session).convert("RGBA")
        alpha = cut.getchannel("A")
        bbox = alpha.point(lambda v: 255 if v > 25 else 0).getbbox()
        if bbox:
            pad = 4
            bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                    min(cw, bbox[2] + pad), min(ch, bbox[3] + pad))
            cut = cut.crop(bbox)
        path = os.path.join(OUT, name + ".png")
        cut.save(path)
        a = cut.getchannel("A")
        import numpy as np
        arr = np.array(a)
        print("%-11s %-14s opaque=%4.1f%%" %
              (name, str(cut.size), 100 * (arr > 245).mean()))


if __name__ == "__main__":
    main()
