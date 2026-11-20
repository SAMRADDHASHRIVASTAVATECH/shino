"""Turn Nova's full-body character cutout into a crisp pixel-art sprite.

Offline, stdlib + Pillow only. Keeps the alpha cutout and quantises to a small
palette so it reads as real pixel art rather than a blurry downscale.
"""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "processed_images", "full_body_front_normalized.png")
OUT = os.path.join(ROOT, "assets", "sprites", "nova_pixel.png")
OUT_DIR = os.path.dirname(OUT)

PIXEL_W = 56          # logical pixel-art width
PALETTE = 40          # colours (classic limited-palette look)
SCALE = 7             # on-screen size = PIXEL_W * SCALE (392 px tall-ish)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    im = Image.open(SRC).convert("RGBA")
    alpha = im.getchannel("A")

    # Tight crop around the character with a tiny margin.
    mask = alpha.point(lambda v: 255 if v > 18 else 0)
    bbox = mask.getbbox()
    pad = 6
    crop_box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad))
    im = im.crop(crop_box)

    # Downsample with NEAREST for hard pixel edges, then quantise the colours.
    h = max(1, round(im.height * PIXEL_W / im.width))
    small = im.resize((PIXEL_W, h), Image.NEAREST)
    a = small.getchannel("A")
    rgb = small.convert("RGB").quantize(colors=PALETTE,
                                        method=Image.Quantize.MEDIANCUT).convert("RGB")
    pixel = rgb.convert("RGBA")
    pixel.putalpha(a)

    # Scale back up with NEAREST so every logical pixel stays crisp.
    sprite = pixel.resize((PIXEL_W * SCALE, h * SCALE), Image.NEAREST)
    sprite.save(OUT)
    print("wrote %s  size=%s  logical=%sx%s" % (OUT, sprite.size, PIXEL_W, h))


if __name__ == "__main__":
    main()
