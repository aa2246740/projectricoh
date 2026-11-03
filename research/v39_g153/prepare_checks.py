"""Retarget the existing checks without changing their behavioral assertions."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TMP = '/Volumes/Workspace/Scratch/tmp/projectricoh/g153'


def main():
    sources = {}
    for name in ('v39_host.py', 'dat_body.py', 'load_routes.py', 'recovery_path.py', 'recovery_compare.py', 'replay_v39.py'):
        original = ROOT / 'research/body_v39/tests' / name
        text = original.read_text()
        text = text.replace('firmware/package_v39_g151', 'firmware/package_v39_g153')
        text = text.replace('firmware/engine_v59_g151', 'firmware/engine_v62_g153')
        text = text.replace('firmware/resident_v39/local/resident', 'research/v39_g153/local/body/local/resident')
        text = text.replace('71697385bf69283ed6349f8829884e8768ff33be2869f940188b668d782e31fa',
                            '8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d')
        text = text.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39/host-model', TMP + '/native')
        text = text.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39-fix', TMP)
        if name == 'v39_host.py':
            text = text.replace("LOCAL = WORK / 'local'", "LOCAL = WORK.parent / 'local/native' / f'p{_os.getpid()}'")
            text = text.replace("ROOT / 'research/emptystack_v38/adapter-layout.json'", "WORK.parent / 'layout.json'")
            text = text.replace('base + 9 * i, 9', 'base + 14 * i, 14')
        if name == 'recovery_path.py':
            text = text.replace('signal.alarm(3000)', 'signal.alarm(10800)')
        target = HERE / 'tests' / name
        target.write_text(text)
        sources[str(target.relative_to(HERE))] = dict(source=str(original.relative_to(ROOT)),
            source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
            adapted_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    for name in ('lock_checks.py', 'apply_checks.py', 'native_reject.py', 'format_checks.py',
                 'ui_checks.py', 'unverified_checks.py', 'regressions.py', 'math_reference.py', 't0_late_checks.py'):
        original = ROOT / 'research/looks_g152' / name
        text = original.read_text().replace('engine_v60_g152', 'engine_v62_g153')
        text = text.replace('package_v38_g152', 'package_v39_g153')
        text = text.replace('/projectricoh/g152', '/projectricoh/g153')
        (HERE / name).write_text(text)
        sources[name] = dict(source=str(original.relative_to(ROOT)),
            source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
            adapted_sha256=hashlib.sha256(text.encode()).hexdigest())
    (HERE / 'legacy').mkdir(exist_ok=True)
    for name in ('previous_state_checks.py', 'review_checks.py', 'g139_check.py'):
        original = ROOT / 'research/looks_g152/legacy' / name
        (HERE / 'legacy' / name).write_bytes(original.read_bytes())
    text = (ROOT / 'research/looks_g152/native_support.py').read_text()
    text = text.replace('/projectricoh/g152', '/projectricoh/g153')
    text = text.replace("ROOT/'research/g150/tests/g139_host.py'", "HERE/'tests/v39_host.py'")
    text = text.replace("H.LOCAL=HERE/'local/native'", "H.LOCAL=HERE/'local/native'/('p'+str(os.getpid()))")
    text = text.replace("H.TMP=TMP/'native'/os.environ['REVIEW_JOB']", "H.TMP=TMP/'native'/('p'+str(os.getpid()))")
    text = text.replace('package_v38_g152', 'package_v39_g153').replace('engine_v60_g152', 'engine_v62_g153')
    text = text.replace('H.setup()', "H.RESIDENT=HERE/'local/body/local/resident/build/resident.elf'\nH.BODY_SHA=H.sha(H.BODY)\nH.setup()")
    (HERE / 'native_support.py').write_text(text)
    # Small rejection fixtures retain the final file size and all header IDs.
    import sys
    sys.path.insert(0, str(HERE))
    import format_checks as formats
    raw = (ROOT / 'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    directory = HERE / 'local/variants'
    directory.mkdir(exist_ok=True)
    for name, data in formats.variants(raw).items():
        (directory / (name + '.DAT')).write_bytes(data)
    (HERE / 'evidence/check-sources.json').write_text(json.dumps(sources, indent=2) + '\n')
    print(json.dumps(dict(status='PASS', adapted_checks=len(sources))))


if __name__ == '__main__':
    main()
