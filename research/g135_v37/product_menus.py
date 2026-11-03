"""Menu and Splt checks on a normally published first open (no ownership scenario beforehand)."""
from pathlib import Path
import argparse
import runpy
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'review_g126'))
from support import *

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--generation', type=int, choices=(121, 124, 126), default=126)
    parser.add_argument('--unit', choices=('50mm', '28mm', 'mount'), default='50mm')
    args = parser.parse_args()
    ux, m, fr, pe, v = setup(args.generation, args.unit, 'product-menus')
    h, p, w = m.boot(args.unit)
    h.b.core.psw |= 0x40
    h.parent()
    result, _, error = fr.publish(h, p, w)
    ux.need(result)
    assert error is None, error
    block = h.u(pe.ROOT_ADDR + 56)
    p.image_base = h.u(block + 312)
    assert p.image_base, 'engine image is not installed after the first publication'
    runpy.run_path(str(HERE / 'product_checks.py'))['run']((ux, m, fr, pe, v), ['--unit', args.unit], OUT, [(h, p, w)])

if __name__ == '__main__':
    main()
