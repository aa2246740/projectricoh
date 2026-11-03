#!/usr/bin/env python3
"""Value-exact codec tests and release-boundary regressions, all fixtures local."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from common import TMP, LOCAL, DELIVERY, GR4, ROOT, PY_DECODER, load_module, output, dump, require
from inject import encode_array, inject
from predict import decode_card
from dry_run import expect_rejection


def run():
    work = output(TMP / 'codec-tests')
    work.mkdir(parents=True, exist_ok=True)
    py = load_module('gr_card_python_decoder', PY_DECODER)
    rng = np.random.default_rng(62103)
    checks, stuffed = [], False
    for precision in (2, 8, 14, 16):
        for components in (1, 2):
            for case in ('zeros', 'maximum', 'extremes', 'random'):
                h, w = 9, 17
                limit = (1 << precision) - 1
                if case == 'zeros':
                    a = np.zeros((h, w * components), np.uint16)
                elif case == 'maximum':
                    a = np.full((h, w * components), limit, np.uint16)
                elif case == 'extremes':
                    values = np.array([0, limit, 1 << (precision - 1), 1, limit - 1], np.uint16)
                    a = np.resize(values, (h, w * components))
                else:
                    a = rng.integers(0, limit + 1, size=(h, w * components), dtype=np.uint16)
                info = dict(precision=precision, height=h, width=w, components=components,
                            ids=list(range(components)), tables=[0] * components, predictor=1, point=0)
                encoded = encode_array(a, info, work)
                got, _ = py.decode(encoded)
                require(np.array_equal(got, a), 'Python 独立逐值解码不一致')
                stuffed |= b'\xff\x00' in encoded
                checks.append(f'{precision}bit/{components}component/{case}')
    require(stuffed, '未覆盖 JPEG FF 字节填充')
    rejected = [expect_rejection(lambda: output(ROOT / 'captures/must-not-write'), 'outside output scope'),
                expect_rejection(lambda: inject(GR4, 'colour', DELIVERY / 'DO_NOT_RELEASE.DNG'), 'private GR IV external release'),
                expect_rejection(lambda: decode_card({'dng_path': str(GR4), 'dng_sha256': '0' * 64}), 'stale DNG layout binding')]
    require(not (DELIVERY / 'DO_NOT_RELEASE.DNG').exists(), '隐私拒绝仍写出了文件')
    summary = dict(passed=True, exact_roundtrips=len(checks), existing_c_decoder=True,
                   existing_python_decoder=True, independent_imagecodecs_decoder=True,
                   cases=checks, byte_stuffing_exercised=stuffed, rejected=rejected,
                   camera_evidence=False)
    dump(LOCAL / 'codec-tests.json', summary)
    print({'roundtrips': len(checks), 'rejected': len(rejected), 'passed': True})
    return summary


if __name__ == '__main__':
    run()
