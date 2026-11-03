"""Read-only probe: print the new-design label sets the old UI suites assert on (no assertions)."""
from pathlib import Path
import json
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'review_g126'))
from ui_test_support import *

def main():
    out = {}
    s = Session('50mm', 'probe')
    out['l1'] = s.state()['labels']
    s.press('DOWN'); s.match(5, [0] * 11)
    out['l1_after_down_match'] = s.state()['labels']
    s.press('DISP'); st = s.state(); out['card5'] = [st['labels'], st['screen'], st['cur'], st['count']]
    s.press('DISP'); st = s.state(); out['items5'] = [st['labels'], st['screen'], st['cur'], st['count'], st['top']]
    s.press('DISP'); st = s.state(); out['value5_first'] = [st['labels'], st['screen'], st['cur'], st['count'], st['levels']]
    s.press('DISP'); s.goto(2, 0); s.press('DISP'); s.goto(1, 0); s.press('DISP')
    s.goto(0, 2); s.press('DISP'); st = s.state(); out['card3'] = [st['labels'], st['screen'], st['cur'], st['count']]
    s.press('DISP'); st = s.state(); out['items3'] = [st['labels'], st['screen'], st['cur'], st['count']]
    print(json.dumps(out), flush=True)
    save('local/probe-ui.json', out)

if __name__ == '__main__':
    main()
