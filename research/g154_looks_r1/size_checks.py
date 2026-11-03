"""从真实 resident 装载调用中读取三项尺寸，堆本身仍是主机模型。"""
from pathlib import Path
import json
import os
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, PACKAGE, save, sha
import native_support
assert Path(native_support.__file__).resolve() == HERE / 'native_support.py'
Camera, H = native_support.Camera, native_support.H
assert H.DAT == PACKAGE / 'local/SD_ROOT/GXRCE.DAT'


def main():
    started = time.monotonic()
    sizes = json.loads((HERE / 'evidence/build-size.json').read_text())
    raw = (PACKAGE / 'local/SD_ROOT/GXRCE.DAT').read_bytes()
    cases = []
    for unit in ('50mm', '28mm', 'mount'):
        cam = Camera(unit)
        requested = []
        cam.h.b.add_breakpoint(cam.h.symbols['rv_native_alloc'],
                               lambda b: requested.append(b.get_reg('r0')) or False)
        cam.open_menu()
        root = H.R
        block = cam.h.u(root + 56)
        main_request = cam.h.u(root + 104)
        code_bytes = cam.h.u(root + 116)
        image = cam.h.u(block + 312)
        file_bytes = cam.h.u(block + 316)
        bss_bytes = cam.h.u(block + 320)
        print(json.dumps(dict(unit=unit, main_request=main_request, requested=requested,
              file_bytes=file_bytes, bss_bytes=bss_bytes, code_bytes=code_bytes,
              allocator_symbol=hex(cam.h.symbols['rv_native_alloc']))), flush=True)
        assert main_request == sizes['main_request'] == 103644 and main_request in requested, (main_request, requested)
        assert file_bytes == len(raw) == sizes['file_bytes'] == 86736
        assert code_bytes == sizes['code_bytes'] == 64728 and bss_bytes == 9280
        assert main_request <= 107612 and file_bytes <= 98304 and code_bytes <= 65536
        assert image == cam.p.image_base
        cases.append(dict(unit=unit, allocation_requests=requested, main_request=main_request,
            allocator_header_bytes=cam.h.u(block - 4), DAT_bytes=file_bytes,
            code_bytes=code_bytes, bss_bytes=bss_bytes, frame=cam.check_frame(),
            scope='Resident M32R loader request observed; host heap/device models.'))
    save(HERE / 'evidence/runtime-sizes.json', dict(status='PASS', dat_sha256=sha(raw),
        backend=os.environ['GXR_HARNESS_BACKEND'], cases=cases,
        seconds=time.monotonic() - started))
    print('PASS: three units, native resident main request 103644 B, DAT 86736 B, code 64728 B')


if __name__ == '__main__':
    main()
