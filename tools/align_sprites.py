"""Normalise all 16 state sprites to one shared scale + baseline.

Pixel-art safe: nearest-neighbour scaling only. Every state is cropped to its
alpha bbox, scaled to a common height, then pasted centred with its feet on
the same baseline so switching states never makes Nova 'jump'.
"""
import os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "sprites", "states")
OUT = os.path.join(ROOT, "assets", "sprites", "ready")
NAMES = ["idle", "talking", "blink", "happy", "sad", "angry", "surprised",
         "thinking", "waving", "dancing", "sleeping", "shy", "listening",
         "working", "explaining", "shrugging"]

TARGET_H = 240           # shared body height in pixels
BASELINE = 252           # feet sit on this row inside the canvas
CANVAS_W, CANVAS_H = 220, 264


def main():
    os.makedirs(OUT, exist_ok=True)
    for name in NAMES:
        im = Image.open(os.path.join(SRC, name + ".png")).convert("RGBA")
        a = np.array(im.getchannel("A"))
        ys, xs = np.where(a > 25)
        if not len(xs):
            print(name, "EMPTY - skipped")
            continue
        crop = im.crop((int(xs.min()), int(ys.min()),
                        int(xs.max()) + 1, int(ys.max()) + 1))
        scale = TARGET_H / crop.height
        nw = max(1, round(crop.width * scale))
        crop = crop.resize((nw, TARGET_H), Image.NEAREST)

        canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        x = (CANVAS_W - nw) // 2
        y = BASELINE - TARGET_H
        canvas.paste(crop, (x, y), crop)
        canvas.save(os.path.join(OUT, name + ".png"))
        print("%-11s %sx%s -> x=%s y=%s" % (name, nw, TARGET_H, x, y))


if __name__ == "__main__":
    main()
