"""Round-4 host acceptance. Preserve earlier attempts; never alter product checks."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
import verify_round2 as prior_review

ROUND4 = c.HERE / 'local/round4'
ORIGINAL_LOCAL = c.HERE / 'local'
MUTABLE_PRIOR = {'REPORT.md', 'SHA256SUMS', 'host_round2.c', 'local/card_update/manifest.json'}
EXPECTED_SHA = prior_review.EXPECTED_SHA


def protected_unchanged():
    frozen = json.loads((ROUND4 / 'protected-inputs.json').read_text())
    current = {p: h for p, h in c.snapshot().items() if p != 'decisions.tsv'}
    differences = [dict(path=p, before=frozen.get(p), after=current.get(p))
                   for p in sorted(frozen.keys() | current.keys()) if frozen.get(p) != current.get(p)]
    assert len(frozen) == 480 and not differences, differences
    return len(frozen)


def preserved_prior():
    frozen = json.loads((ROUND4 / 'prior-files.json').read_text())
    retained = []
    for rel, digest in frozen.items():
        path = ROUND4 / 'prior' / rel if rel in MUTABLE_PRIOR else c.HERE / rel
        assert c.sha(path) == digest, rel
        retained.append(dict(original=rel, retained=str(path.relative_to(c.HERE)), sha256=digest))
    assert prior_review.round1_unchanged() == 298
    return retained


def compile_fixture(attempt):
    commands = [json.loads(line) for line in (ORIGINAL_LOCAL / 'commands.jsonl').read_text().splitlines()]
    out = attempt / 'host'
    out.mkdir()
    args = next(row['argv'][:] for row in commands if row['label'] == 'host-compile-28')
    old_object = args[args.index('-o') + 1]
    args[args.index('-c') + 1] = str(c.HERE / 'host_round2.c')
    args[args.index('-o') + 1] = str(out / 'host_round2.o')
    assert '-fsanitize=address,undefined' in args and '-Werror' in args
    c.run(args, 'round4-host-compile')
    link = next(row['argv'][:] for row in commands if row['label'] == 'host-link')
    link[link.index(old_object)] = str(out / 'host_round2.o')
    link[link.index('-o') + 1] = str(out / 'host_checks')
    objects = [Path(p) for p in link if p.endswith('.o') and p != str(out / 'host_round2.o')]
    frozen = json.loads((ROUND4 / 'prior-files.json').read_text())
    for path in objects:
        assert c.sha(path) == frozen[path.relative_to(c.HERE).as_posix()]
    c.run(link, 'round4-host-link')
    c.save(attempt / 'host-link-inputs.json', dict(
        product_and_resident_objects='unchanged round-1 objects',
        unchanged_objects={str(p.relative_to(c.HERE)): c.sha(p) for p in objects},
        fixture_sha256=c.sha(c.HERE / 'host_round2.c'), sanitizers=['ASan', 'UBSan']))
    return out / 'host_checks'


def validators(attempt):
    results = []
    for name in ('jlaunch', 'qlaunch', 'l08firm'):
        result = c.run([ORIGINAL_LOCAL / 'host/validate', c.OUT / 'GXRCE.DAT', c.OUT / 'trust.bin', name],
                       'round4-validate-' + name)
        assert 'OK build=106' in result.stdout and 'semantic=1' in result.stdout
        assert result.stdout == (ORIGINAL_LOCAL / 'logs' / ('validate-' + name + '.log')).read_text()
        results.append(dict(unit=name, status='PASS', output=result.stdout.strip()))
    expanded = {}
    for label, folder in (('full-r3', c.BASE), ('full-r4', c.OUT)):
        result = c.run([ORIGINAL_LOCAL / 'host/expand', folder / 'GXRCE.DAT', folder / 'trust.bin'],
                       'round4-expand-' + label)
        assert result.stdout == (ORIGINAL_LOCAL / 'logs' / ('expand-' + label + '.log')).read_text()
        rows = [line.split() for line in result.stdout.splitlines()]
        assert len(rows) == 48
        expanded[label] = {(int(r[0]), int(r[1])): [bytes.fromhex(x) for x in r[2:]] for r in rows}
    c.save(attempt / 'validation.json', dict(status='PASS', units=results, expanded_slots=48,
           expanded_entry_record_binding_default_bytes='identical to frozen round-1 vectors'))
    return expanded


def run_case(binary, attempt, expanded, scenario, unit):
    evidence = attempt / 'host-evidence' / f'{scenario}-{unit}'
    evidence.mkdir(parents=True)
    result = c.run([binary, scenario, unit, c.BASE / 'GXRCE.DAT', c.OUT / 'GXRCE.DAT',
                    c.OUT / 'trust.bin', c.BASE / 'effective-rows.bin', c.OUT / 'effective-rows.bin', evidence],
                   f'round4-flow-{scenario}-{unit}')
    lines = result.stdout.splitlines()
    assert lines[-1].startswith('OK ') and 'missing_open=-1' in lines[-1]
    assert result.stdout.count('IV_B_PASS ') == 1
    assert result.stdout.count('SAVE_PASS ') == (3 if unit == 0 else 1)
    if scenario == 'r2-gxts':
        assert result.stdout.count('D_PASS ') == 1
    else:
        assert result.stdout.count('IV_A_PASS ') == 1
        assert 'install=RV_CONFLICT rows=16 no_writes=1 SaveFail=0 disabled=0' in result.stdout
    gxts = prior_review.verify_gxts(evidence, unit, expanded)
    expected_a = c.OUT / 'GXRCE.DAT' if 'single' in scenario else c.BASE / 'GXRCE.DAT'
    assert (evidence / 'IROM-GXRCE0.DAT').read_bytes() == expected_a.read_bytes()
    if 'single' not in scenario:
        assert (evidence / 'IROM-GXRCE1.DAT').read_bytes() == (c.OUT / 'GXRCE.DAT').read_bytes()
    else:
        assert not (evidence / 'IROM-GXRCE1.DAT').exists()
    assert not (evidence / 'card-GXRCE.DAT').exists()
    if 'empty' in scenario:
        assert not (evidence / 'card-GXRCE.OK').exists()
    else:
        assert (evidence / 'card-GXRCE.OK').read_bytes() == (c.OUT / 'GXRCE.DAT').read_bytes()
    return dict(scenario=scenario, unit=unit, status='PASS', GXTS=gxts,
                assertions=int(re.search(r'assertions=(\d+)', lines[-1])[1]),
                evidence=str(evidence.relative_to(c.HERE)),
                log=str((attempt / 'logs' / f'round4-flow-{scenario}-{unit}.log').relative_to(c.HERE)),
                observations=[line for line in lines if line.startswith((
                    'IV_A_PASS', 'IV_B_PASS', 'READONLY_PASS', 'SAVE_PASS', 'GXTS_PASS', 'D_PASS'))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True, help='New evidence directory, for example attempt-01')
    args = parser.parse_args()
    assert re.fullmatch(r'attempt-[0-9]{2}', args.attempt)
    attempt = ROUND4 / args.attempt
    assert not attempt.exists(), 'Keep earlier evidence; choose a new attempt after a documented development fix'
    protected_unchanged()
    preserved = preserved_prior()
    c.LOCAL = attempt
    c.guard()
    stage = 'DEVELOPMENT_COMPILE'
    results = []
    try:
        assert not (ORIGINAL_LOCAL / 'card_update/GXRCE.DAT').exists()
        assert c.sha(c.BASE / 'GXRCE.DAT') == '0f49317ac8b2609cb268a7951ec263959e8a2fedef818c7d9dd8e530796c7885'
        assert c.sha(c.OUT / 'GXRCE.DAT') == EXPECTED_SHA and (c.OUT / 'GXRCE.DAT').stat().st_size == 59516
        assert c.sha(c.ROOT / 'firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3') == '05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c'
        assert c.sha(c.ROOT / 'firmware/resident_v32/local/resident/build/resident.elf') == 'f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58'
        c.write(attempt / 'host_round2.c', (c.HERE / 'host_round2.c').read_bytes())
        c.write(attempt / 'verify_round4.py', Path(__file__).read_bytes())
        binary = compile_fixture(attempt)
        stage = 'CONTAINER_VALIDATION'
        expanded = validators(attempt)
        cases = [(scenario, unit) for scenario in prior_review.SCENARIOS for unit in range(3)]
        cases += [('r2-gxts', 0), ('r2-gxts', 2)]
        for scenario, unit in cases:
            stage = f'BEHAVIOUR {scenario} unit={unit}'
            results.append(run_case(binary, attempt, expanded, scenario, unit))
            c.save(attempt / 'host-results.json', results)
            print(json.dumps(dict(scenario=scenario, unit=unit, status='PASS',
                                  GXTS=[r['outcome'] for r in results[-1]['GXTS']])), flush=True)
        protected_unchanged()
        assert preserved_prior() == preserved
        c.save(attempt / 'prior-preservation.json', dict(status='PASS', files=len(preserved), preserved=preserved))
        summary = dict(status='PASS', round=4, host_cases=len(results), conflict_cases=12,
                       cold106_cases=14, GXTS_update_cases=2, GXTS_update_slots=4,
                       units=['50mm', '28mm', 'Mount'], stage='READY_TO_STAGE_HOST_ONLY',
                       camera_acceptance=False, sha256=EXPECTED_SHA, preserved_prior_files=len(preserved),
                       protected_inputs=480, protected_inputs_unchanged=True,
                       completed_case_assertions=sum(r['assertions'] for r in results))
        c.save(attempt / 'verification.json', summary)
        print(json.dumps(summary), flush=True)
    except Exception as error:
        c.save(attempt / 'failure.json', dict(status='FAILED_REQUIRES_CLASSIFICATION', stage=stage,
               error=repr(error), completed_cases=len(results), card_files_staged=False,
               camera_acceptance=False))
        raise


if __name__ == '__main__':
    main()
