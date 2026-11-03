"""Walk all eleven Looks rows through native keys and inspect eight visible rows."""
from pathlib import Path
import json
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_support import Camera, H
from apply_checks import ui_audit
from dat_format import strict_effects, sha


def main():
    started = time.monotonic()
    cam = Camera('50mm')
    cam.open_menu()
    cam.open_looks()
    frames, counts = [], []
    def publication(backend):
        if backend.core.r[0] == 10 and backend.core.r[1] in (1, 3):
            buffer = cam.h.u(backend.core.r[2] + 48)
            count = cam.h.u(buffer + 20)
            counts.append(count)
            assert count == 8
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'), publication)
    for row in range(11):
        cam.goto(row)
        frame = cam.check_frame()
        assert frame['screen'] == 7 and frame['count'] == 11
        assert len(frame['labels']) == 8 and all(len(text) <= 13 for text in frame['labels'])
        frames.append(frame)
    cam.press('DOWN')
    assert cam.ui('cur') == 0
    cam.press('UP')
    assert cam.ui('cur') == 10
    assert counts and all(count == 8 for count in counts)
    result = dict(status='PASS', dat_sha256=sha(H.DAT.read_bytes()), frames=frames,
                  native_publication_counts=counts, native_UI_audit=ui_audit(cam), seconds=time.monotonic()-started)
    (H.WORK / 'evidence/looks8.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status='PASS', frames=len(frames), physical_rows=8, seconds=result['seconds'])))


if __name__ == '__main__':
    main()
