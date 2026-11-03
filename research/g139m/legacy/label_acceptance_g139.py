"""Current-contract port of research/review_g124/label_acceptance.py (groups 124/126 labels).

Old contract (retired): three-item HC BW page, nonselectable padding that
stopped the cursor, eleven-byte levels. Current contract (g137 lists loop, g138
knob table and no end marks): HC BW card has C/H, S/F and G pairs plus Default;
the item page lists Cont, High, Shad, Fade, Filt; lists wrap through a
'--------' separator; Satu is never shown. Every original step is kept with its
current reading: label arrays, the Shad -1 edit with a full nine-row/T/S match,
Default arm -> move cancels -> Default applies, and the return cursor on L1.
Runs through research/review_g126's Session (native keys, M32R model).
"""
from pathlib import Path
import argparse
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'review_g126'))
from ui_test_support import *

ZERO = [100] + [0] * 9
CARD = ['<3 HC BW', 'C 0 H 0', 'S 0 F 0', 'G 0', 'Default', '--------', ' ', ' ']
ITEMS = ['<3 HC BW', 'Cont   0', 'High   0', 'Shad   0', 'Fade   0', 'Filt   0', '--------', ' ']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unit', default='50mm', choices=('50mm', '28mm', 'mount'))
    args = parser.parse_args()
    s = Session(args.unit, 'labels')
    s.press('UP'); s.match(3, ZERO); s.press('DISP')
    assert s.state()['labels'] == CARD, s.state()
    s.press('DISP')
    assert s.state()['labels'] == ITEMS, s.state()
    # Padding: the separator is not a row. Last row DOWN wraps to the title.
    s.goto(2, 5); s.press('DOWN'); assert s.state()['cur'] == 0 and s.state()['levels'] == ZERO
    s.press('UP'); assert s.state()['cur'] == 5
    s.goto(2, 3); s.press('DISP'); assert s.state()['screen'] == 3
    s.press('DOWN')
    shad = list(ZERO); shad[3] = -1
    assert s.state()['levels'] == shad, s.state()
    assert s.state()['labels'][s.state()['physical']] == 'Shad  -1', s.state()
    s.match(3, shad)
    s.press('DISP'); assert s.state()['screen'] == 2 and s.state()['labels'][3] == 'Shad  -1'
    s.goto(2, 0); s.press('DISP'); assert s.state()['screen'] == 1
    assert s.state()['labels'][0] == '<3*HC BW' and s.state()['labels'][2] == 'S-1 F 0', s.state()
    s.goto(1, 4); s.press('DISP'); assert s.state()['armed'] == 1 and s.state()['labels'][4] == 'Sure?'
    s.press('DOWN'); assert s.state()['cur'] == 0 and not s.state()['armed']
    s.press('UP'); assert s.state()['cur'] == 4 and s.state()['labels'][4] == 'Default'
    s.press('DISP'); s.press('DISP'); s.match(3, ZERO)
    assert s.state()['labels'] == CARD, s.state()
    s.goto(1, 0); s.press('DISP'); assert s.state()['screen'] == 0 and s.state()['cur'] == 2
    assert not any('Satu' in label for label in s.ascii)
    assert not any('!' in label for label in s.ascii if label.strip() and label.strip()[0] not in '<>!'), \
        'end marks are retired (g138 contract C)'
    result = s.report()
    result.update(status='PASS', contract='g139-current', black_white_saturation_hidden=True,
                  separator_not_selectable=True, list_wraps=True, no_end_marks=True,
                  maximum_ascii_characters=max(map(len, s.ascii)))
    save('local/labels-g139-' + args.unit + '.json', result)
    save('evidence/labels-g139-' + args.unit + '.json', {k: v for k, v in result.items() if k not in ('rpc_log', 'events')})
    print('PASS', args.unit, 'current HC BW labels, separator, wrap, Default arm/cancel/apply')


if __name__ == '__main__':
    main()
