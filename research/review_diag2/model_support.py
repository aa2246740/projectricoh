"""Call the existing model support by path with review-local outputs."""
import importlib.util

import review_common as c


def load(baseline=False):
    path = c.ROOT / 'research/diag_dat_v2/legacy_call.py'
    spec = importlib.util.spec_from_file_location('review_path_call', path)
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    bridge.HERE = c.HERE
    bridge.OUTPUTS = (c.HERE,)
    bridge.MAPPINGS = (
        (c.ROOT / 'research/diag_dat_v1', c.LOCAL / 'legacy/v1'),
        (c.ROOT / 'research/review_diag', c.LOCAL / 'legacy/review'))
    if not baseline:
        bridge.MAPPINGS += (
        (c.ROOT / 'firmware/engine_diag_v1', c.ROOT / 'firmware/engine_diag_v2'),
        (c.ROOT / 'firmware/package_v36_diag1', c.ROOT / 'firmware/package_v36_diag2'))
    return bridge.load_path(c.ROOT / 'research/diag_dat_v1/native_support.py')
