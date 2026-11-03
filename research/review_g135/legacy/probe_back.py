"""Read-only probe: where does the cursor land when returning from the items view to the card view (new design)?"""
from pathlib import Path
import json
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'review_g126'))
from ui_test_support import *

def main():
    out = {}
    s = Session('50mm', 'probe-back')
    s.press('DOWN'); s.match(5, [0] * 11); s.press('OK'); s.reopen()
    def snap(tag):
        st = s.state(); out[tag] = dict(screen=st['screen'], cur=st['cur'], top=st['top'], labels=st['labels'], count=st['count'])
    snap('l1')
    s.press('DISP'); snap('card')
    s.press('DOWN'); snap('card_down')
    s.press('DISP'); snap('items_after_pair2')
    s.goto(2, 0); s.press('DISP'); snap('card_after_back')
    s.press('DISP'); snap('items_again')
    s.press('DOWN'); s.press('DOWN'); snap('items_cur3')
    s.goto(2, 0); s.press('DISP'); snap('card_after_back_from_3')
    save('local/probe-back.json', out)
    print(json.dumps(out), flush=True)

if __name__ == '__main__':
    main()
