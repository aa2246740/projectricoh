"""Extract and disassemble only the named firmware ranges, in the review folder."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import HERE, ROOT, save
from image_loader import Image, Elf
import subprocess

objdump = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
body = Image(ROOT / "firmware/image_v35/local/package/SD_ROOT/ilaunch3", "6e9ea05868b2bb56fb60de0e8506aad7b952715c061009b2acc891b45d220b20")
official = Image(ROOT / "artifacts/firmware/gxr-1.51/ilaunch3", "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7")
regions = [("early", body, 0x20053fc0, 0x4c), ("hooks", body, 0x2005276c, 0x500), ("load", body, 0x200534b4, 0x650),
           ("native_h07", official, 0x202871d8, 0x120), ("native_h08", official, 0x202bb8f0, 0x110),
           ("native_ready", official, 0x20093570, 0x80), ("native_lens_task", official, 0x200938e0, 0x300),
           ("native_close_caller", official, 0x202c2d40, 0x60)]
for name, image, addr, length in regions:
    raw = HERE / (name + ".bin")
    raw.write_bytes(image.bytes_at(addr, length))
    p = subprocess.run([str(objdump), "-D", "-b", "binary", "-m", "m32r", "-EB", "--adjust-vma=" + hex(addr), str(raw)], text=True, capture_output=True, check=True)
    (HERE / (name + ".asm")).write_text(p.stdout)
save("symbols.json", Elf(ROOT / "firmware/resident_v35/local/resident/build/resident.elf").symbols)
