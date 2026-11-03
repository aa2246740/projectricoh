"""Contact sheets with frame labels (for visual recipe identification)."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from drift_common import *
from PIL import ImageDraw
inv = {r['file']: r for r in json.loads((LOCAL / 'inventory.json').read_text())}


def sheet(names, out, cols=4, w=480):
    ims = []
    for n in names:
        r = inv[n + '.JPG']; im = Image.open(ROOT / r['dir'] / (n + '.JPG')); im.draft('RGB', (w * 2, w * 2))
        im = im.convert('RGB'); im.thumbnail((w, w))
        d = ImageDraw.Draw(im); d.rectangle([0, 0, w, 18], fill=(0, 0, 0))
        d.text((4, 3), f"{n[-4:]} ISO{r['iso']} 1/{round(1/r['exp'])} {r['model'][4:16]}", fill=(255, 255, 0)); ims.append(im)
    h = max(i.height for i in ims); rows = (len(ims) + cols - 1) // cols
    S = Image.new('RGB', (cols * w, rows * h), (40, 40, 40))
    for k, im in enumerate(ims):
        S.paste(im, ((k % cols) * w, (k // cols) * h))
    S.save(LOCAL / out, quality=85)


a, b = int(sys.argv[1]), int(sys.argv[2])
sheet([f'R805{i}' for i in range(a, b + 1)], f'sheet_{a}_{b}.jpg', cols=int(sys.argv[3]) if len(sys.argv) > 3 else 4)
