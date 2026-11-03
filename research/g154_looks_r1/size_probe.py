"""不加分配断点，记录装载前后的 root 字段以定位尺寸观察断言。"""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, save
import native_support
assert Path(native_support.__file__).resolve() == HERE / 'native_support.py'
Camera, H = native_support.Camera, native_support.H


def main():
    cam = Camera('50mm')
    before = {str(off): cam.h.u(H.R + off) for off in (56, 104, 108, 112, 116)}
    cam.open_menu()
    block = cam.h.u(H.R + 56)
    observed = dict(status='OBSERVED', before=before,
        after={str(off): cam.h.u(H.R + off) for off in (56, 104, 108, 112, 116)},
        session={str(off): cam.h.u(block + off) for off in (312, 316, 320)},
        allocator_symbol=hex(cam.h.symbols['rv_native_alloc']),
        allocator_visits=cam.h.b.visits.get(cam.h.symbols['rv_native_alloc'], 0),
        native_allocator_visits=cam.h.b.visits.get(0x2005bf5c, 0),
        native_stats=getattr(cam.h.b, 'native_stats', {}), frame=cam.check_frame())
    save(HERE / 'evidence/size-probe.json', observed)
    print(json.dumps(observed), flush=True)


if __name__ == '__main__':
    main()
