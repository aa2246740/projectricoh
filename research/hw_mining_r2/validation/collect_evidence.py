#!/usr/bin/env python3
"""从独立提取的官方成员重新生成重点窗口。"""
import runpy
from pathlib import Path

ctx = runpy.run_path(str(Path(__file__).with_name("audit.py")))
Image, raw, save = ctx["Image"], ctx["raw"], ctx["save"]
im = Image()
windows = [
    (0x20105678, 0x20105E80, "k1-debug-dump"),
    (0x2010EE40, 0x2010F180, "k1-enable-fields"),
    (0x2010C248, 0x2010C3F4, "k1-isp-apply"),
    (0x2011A774, 0x2011A880, "k1-isp-slots"),
    (0x201130F4, 0x201131C4, "k2-front-slots"),
    (0x20118398, 0x201188B4, "k1-three-curve-packer"),
    (0x201188B4, 0x20119540, "k1-inp-packer"),
    (0x2010C3F4, 0x2010C630, "k2-front-apply"),
    (0x20112394, 0x20112474, "k2-mcr-packer"),
    (0x201130B0, 0x201130F4, "k2-vk-wrapper"),
    (0x2010D4C0, 0x2010D59C, "k2-mcr-builder"),
    (0x20255600, 0x20255880, "k2-type-dispatch"),
    (0x20256988, 0x202569C8, "k2-generic-writer"),
    (0x2011820C, 0x20118398, "k4-exip-packer"),
    (0x20257394, 0x20257430, "k4-exip-writer"),
    (0x2018A728, 0x2018A7E0, "k4-exip-gain-update"),
    (0x201153DC, 0x2011564C, "k3-known-matrix-packer"),
    (0x20065CA0, 0x20065D54, "k4-template-copy"),
    (0x200A7F24, 0x200A7F40, "k4-copy-loop"),
    (0x2011A558, 0x2011A774, "k1-ispreg-packer"),
    (0x2010BEA4, 0x2010C248, "k1-isp-build"),
    (0x20105388, 0x20105480, "k2-front-controller"),
    (0x20255A78, 0x20255B88, "k2-register-read"),
    (0x20255740, 0x20255850, "k2-register-write"),
    (0x20105480, 0x201055E0, "k1-isp-controller"),
]
for a, b, label in windows:
    im.disasm(a, b, "evidence/" + label)
for a, b, label in [
    (0x20129EC8, 0x2012A05C, "k1-debug-names"),
    (0x20141584, 0x20141594, "k2-mcr-initial"),
    (0x200B81D4, 0x200B81F4, "k4-default-template-start"),
    (0x200BB264, 0x200BB2D4, "k4-default-exip-fields"),
    (0x2012D0C0, 0x2012D1A0, "k3-known-matrix-rows"),
]:
    raw(a, b, label)
descs = sorted(set(im.u32(0x2029DA8C + 4 * t) for t in range(39)))
rows = []
for t in range(39):
    d = im.u32(0x2029DA8C + 4 * t)
    end = next((x for x in descs if x > d), d + 12)
    rows.append({"type": t, "writer": hex(im.u32(0x2029C194 + 4 * t)),
                 "descriptor": hex(d), "file_offset": hex(im.offset(d)),
                 "words": [hex(im.u32(a)) for a in range(d, end, 4)]})
save("evidence/type-descriptors.json", rows)
print(f"{len(windows)} code windows, 5 data windows, 39 type descriptors")
