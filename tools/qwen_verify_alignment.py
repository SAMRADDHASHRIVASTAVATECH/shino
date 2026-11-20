"""Ask Qwen one simple yes/no question about the aligned sprite sheet."""
import os
import sys
from PIL import Image
from rembg import new_session  # noqa: F401  (ensures deps present)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lm_client

READY = os.path.join(ROOT, "assets", "sprites", "ready")
NAMES = ["idle", "talking", "blink", "happy", "sad", "angry", "surprised",
         "thinking", "waving", "dancing", "sleeping", "shy", "listening",
         "working", "explaining", "shrugging"]


def main():
    cell = 130
    sheet = Image.new("RGB", (cell * 4, cell * 4), (255, 255, 255))
    for i, name in enumerate(NAMES):
        im = Image.open(os.path.join(READY, name + ".png")).convert("RGBA")
        im.thumbnail((cell - 4, cell - 4), Image.NEAREST)
        x = (i % 4) * cell + (cell - im.width) // 2
        y = (i // 4) * cell + (cell - im.height) // 2
        sheet.paste(im, (x, y), im)

    ans = lm_client.describe_image(
        sheet,
        "All 16 images show the same pixel-art girl. Are they all about the SAME "
        "SIZE and standing on the SAME baseline? Answer with only YES or NO.",
        max_tokens=800,
    )
    print("Qwen alignment check:", ans.strip()[:400])


if __name__ == "__main__":
    main()
