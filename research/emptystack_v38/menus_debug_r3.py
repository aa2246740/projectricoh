"""Diagnostic wrapper (round 3): run product_menus through run_existing and log every layout.json read."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_existing as r

LOG = HERE / 'local/layout-reads-r3.log'
_orig = r.aligned_read


def traced(original, file, mode='r', *arguments, **keywords):
    text = str(file)
    if text.endswith('layout/layout.json'):
        with LOG.open('a') as handle:
            handle.write(repr((text, mode, original.__name__)) + '\n')
    stream = _orig(original, file, mode, *arguments, **keywords)
    if text.endswith('layout/layout.json'):
        with LOG.open('a') as handle:
            handle.write('  type=' + type(stream).__name__ + '\n')
    return stream


r.aligned_read = traced
sys.argv = [str(HERE / 'run_existing.py'), 'research/g135_v37/product_menus.py', '--unit', '50mm']
r.main()
