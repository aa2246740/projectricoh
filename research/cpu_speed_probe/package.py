"""Package gen 148: firmware/package_v38_cpuprobe/SD_ROOT/GXRCE.DAT and SHA256SUMS.

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/cpuprobe /usr/bin/python3 -I -B research/cpu_speed_probe/package.py

GXRCE.DAT is the built gen 148 DAT; static-cpuprobe.json must name the same SHA256 and PASS. SD_ROOT/ is git-ignored.
The body must already run v3.8; ilaunch3 is not in this package.
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

BUILD = ROOT / 'firmware/engine_cpuprobe_v38/candidate/local/full-r1'
PACKAGE = ROOT / 'firmware/package_v38_cpuprobe'
BODY = ROOT / 'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
BODY_SHA = 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'


def main():
    static = json.loads((HERE / 'static-cpuprobe.json').read_text())
    assert static['status'] == 'PASS' and static['dat_sha256'] == sha(BUILD / 'GXRCE.DAT')
    sd = PACKAGE / 'SD_ROOT'
    sd.mkdir(parents=True, exist_ok=True)
    for old in sd.iterdir():
        assert old.name == 'GXRCE.DAT', old
    shutil.copyfile(BUILD / 'GXRCE.DAT', sd / 'GXRCE.DAT')
    assert sha(sd / 'GXRCE.DAT') == static['dat_sha256']
    assert sha(BODY) == BODY_SHA
    rel = PACKAGE.relative_to(ROOT)
    (PACKAGE / 'SHA256SUMS').write_text(
        '%s  %s/SD_ROOT/GXRCE.DAT\n'
        '# camera body must already run v3.8 (ilaunch3 not in this package):\n%s  %s\n'
        % (sha(sd / 'GXRCE.DAT'), rel, BODY_SHA, BODY.relative_to(ROOT)))
    print((PACKAGE / 'SHA256SUMS').read_text())


if __name__ == '__main__':
    main()
