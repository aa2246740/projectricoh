"""Package gen 147: firmware/package_v38_diag147/SD_ROOT/{GXRCE.DAT, GXRFX.BIN} and SHA256SUMS.

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/diag147 /usr/bin/python3 -I -B research/diag147/package147.py

GXRCE.DAT is the built DAT (static-diag147.json must name the same SHA256 and PASS); GXRFX.BIN is the synthetic
25,152 B file from gxrfx.py (generated here, no camera data). SD_ROOT/ is git-ignored. The body must already
run v3.8; ilaunch3 is not in this package.
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
from scope import ROOT, sha
scope.enable_fence()
import gxrfx

BUILD = ROOT / 'firmware/engine_diag_v38_g147/candidate/local/full-r1'
PACKAGE = ROOT / 'firmware/package_v38_diag147'
BODY = ROOT / 'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
BODY_SHA = 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'


def main():
    static = json.loads((HERE / 'static-diag147.json').read_text())
    assert static['status'] == 'PASS' and static['dat_sha256'] == sha(BUILD / 'GXRCE.DAT')
    sd = PACKAGE / 'SD_ROOT'
    sd.mkdir(parents=True, exist_ok=True)
    for old in sd.iterdir():
        assert old.name in ('GXRCE.DAT', 'GXRFX.BIN'), old
    shutil.copyfile(BUILD / 'GXRCE.DAT', sd / 'GXRCE.DAT')
    raw = gxrfx.build()
    assert len(raw) == 25152 and gxrfx.check(raw, 32768) == 'OK'
    (sd / 'GXRFX.BIN').write_bytes(raw)
    assert sha(sd / 'GXRCE.DAT') == static['dat_sha256']
    assert sha(BODY) == BODY_SHA
    rel = PACKAGE.relative_to(ROOT)
    (PACKAGE / 'SHA256SUMS').write_text(
        '%s  %s/SD_ROOT/GXRCE.DAT\n%s  %s/SD_ROOT/GXRFX.BIN\n'
        '# camera body must already run v3.8 (ilaunch3 not in this package):\n%s  %s\n'
        % (sha(sd / 'GXRCE.DAT'), rel, sha(sd / 'GXRFX.BIN'), rel, BODY_SHA, BODY.relative_to(ROOT)))
    print((PACKAGE / 'SHA256SUMS').read_text())


if __name__ == '__main__':
    main()
