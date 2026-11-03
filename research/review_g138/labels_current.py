"""Check current HC BW labels and nonselectable padding with native keys."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g138_host as H

parser = argparse.ArgumentParser()
parser.add_argument('--unit', choices=['50mm', '28mm', 'mount'], required=True)
args = parser.parse_args()
H.setup()
cam = H.Camera(args.unit)
cam.open_menu()
cam.press('UP')
assert cam.ui('slot') == 3
cam.press('DISP')
card = cam.check_frame()
assert card['labels'] == ['<3 HC BW', 'C 0 H 0', 'S 0 F 0', 'G 0', 'Default', '--------', ' ', ' '], card
cam.press('DISP')
items = cam.check_frame()
assert items['labels'] == ['<3 HC BW', 'Cont   0', 'High   0', 'Shad   0', 'Fade   0', 'Filt   0', '--------', ' '], items
before = cam.levels()
cam.goto(5)
cam.press('DOWN')
assert cam.ui('cur') == 0 and cam.levels() == before
cam.press('UP')
assert cam.ui('cur') == 5
cam.goto(0)
cam.press('DISP')
assert cam.ui('screen') == 1
cam.goto(4)
cam.press('DISP')
assert cam.ui('armed') == 1
cam.press('DOWN')
assert cam.ui('cur') == 0 and cam.ui('armed') == 0
cam.press('UP')
assert cam.ui('cur') == 4
cam.press('DISP')
cam.press('DISP')
assert cam.levels() == [100] + [0] * 9
assert not any('Satu' in label for label in card['labels'] + items['labels'])
result = dict(status='PASS_M32R', unit=args.unit, dat_sha256=H.sha(H.DAT),
              card=card, items=items, nonselectable_separator=True,
              default_arm_cancel_and_apply=True, actual_M32R=True)
path = Path(__file__).resolve().parent / 'evidence' / ('labels-current-' + args.unit + '.json')
path.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'unit': args.unit, 'dat_sha256': result['dat_sha256']}), flush=True)
