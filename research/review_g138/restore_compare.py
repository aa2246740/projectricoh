"""Compare full modeled S and nine unit rows after restore or native keys."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g138_host as H

parser = argparse.ArgumentParser()
parser.add_argument('--unit', choices=['50mm', '28mm', 'mount'], required=True)
args = parser.parse_args()
OUT = Path(__file__).resolve().parent
H.setup()
cam = H.Camera(args.unit)
levels = [100, 1] + [0] * 8
paths = {}
for mode in ['restore', 'keys']:
    path = OUT / 'local' / ('restore-compare-' + args.unit + '-' + mode + '.json')
    paths[mode] = path
    sys.stdout.flush()
    pid = os.fork()
    if not pid:
        code = 0
        try:
            if mode == 'restore':
                cam.put_s(0xfd4, H.record_bytes(H.DAT_BYTES[cam.dat_path], 5, H.UNITS[args.unit], levels))
                cam.open_menu()
            else:
                cam.open_menu()
                cam.press('DOWN')
                cam.press('DISP')
                cam.press('DISP')
                cam.goto(1)
                cam.press('DISP')
                cam.press('UP')
                cam.press('OK')
                cam.open_menu()
            state = cam.check_frame()
            assert state['slot'] == 5 and state['levels'] == levels and state['cur'] == 4
            rows, control = cam.unit_rows()
            result = dict(status='PASS', rows=[row.hex() for row in rows], T=control,
                          S=cam.s_bytes(0, 4096).hex(), state=state)
        except BaseException as error:
            result = dict(status='FAIL', error=type(error).__name__ + ': ' + str(error),
                          frames=[dict(file=f.filename, line=f.lineno, function=f.name)
                                  for f in traceback.extract_tb(error.__traceback__)])
            code = 1
        path.write_text(json.dumps(result, indent=2) + '\n')
        os._exit(code)
    _, status = os.waitpid(pid, 0)
    assert status == 0, (args.unit, mode, json.loads(path.read_text()))
a, b = [json.loads(paths[mode].read_text()) for mode in ['restore', 'keys']]
assert a['rows'] == b['rows'] and a['T'] == b['T']
left, right = bytes.fromhex(a['S']), bytes.fromhex(b['S'])
different = [index for index, (x, y) in enumerate(zip(left, right)) if x != y]
assert not different, ('S differences', different)
assert a['state'] == b['state'], (a['state'], b['state'])
result = dict(status='PASS_M32R', unit=args.unit, dat_sha256=H.sha(H.DAT),
              compared_S_bytes=len(left), S_differences=different,
              compared_rows=len(a['rows']), compared_row_bytes=sum(len(bytes.fromhex(row)) for row in a['rows']),
              S_sha256=hashlib.sha256(left).hexdigest(), T=a['T'], identical_display_state=True)
(OUT / 'evidence' / ('restore-compare-' + args.unit + '.json')).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
