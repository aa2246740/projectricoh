"""Check final artifacts and audit retained implementation evidence offline."""
from pathlib import Path
import collections
import hashlib
import importlib.util
import json
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def load(name):
    spec = importlib.util.spec_from_file_location('review_'+name, HERE/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def audit_records():
    base = ROOT/'research/g150'
    summary = read(base/'RESULTS.json')
    verified, problems, details = [], [], {}
    for path in sorted((base/'evidence/receipts').glob('*.json')):
        receipt = read(path)
        if 'outputs' not in receipt:
            continue
        log = base/'evidence'/(receipt['job']+'.log')
        assert sha(log) == receipt['log_sha256'], log
        rows = []
        for output in receipt['outputs']:
            result_path = ROOT/output['path']
            assert result_path.is_file() and sha(result_path) == output['sha256'], result_path
            stat = result_path.stat()
            assert output['fresh'] and output['mtime_ns'] == stat.st_mtime_ns
            assert receipt['started_ns'] <= stat.st_mtime_ns <= receipt['ended_ns']
            result = read(result_path)
            assert output['status'] == result['status']
            assert output['dat_sha256'] == result['dat_sha256']
            binding = 'runner target'
            if result['dat_sha256'] != receipt['dat_sha256']:
                name = result['case']
                if name == 'dat-test-release':
                    actual = ROOT/'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT'
                elif name in ('users-none','users-replaced'):
                    actual = result_path.parents[1]/'fixtures'/('users-'+name.removeprefix('users-')+'.DAT')
                    assert result['detail']['variant_sha256'] == result['dat_sha256']
                else:
                    raise AssertionError((str(result_path),result['dat_sha256'],receipt['dat_sha256']))
                assert sha(actual) == result['dat_sha256'], actual
                binding = str(actual.relative_to(ROOT))
            inner_times = all(k in result for k in ('started_ns','ended_ns'))
            if inner_times:
                assert receipt['started_ns'] <= result['started_ns'] <= result['ended_ns'] <= receipt['ended_ns']
            rows.append(dict(case=result_path.stem,status=result['status'],dat_sha256=result['dat_sha256'],
                             sha256=output['sha256'],seconds=result['seconds'],path=output['path'],
                             inner_times_available=inner_times,dat_binding=binding))
            details[(receipt['job'],result_path.stem)] = result
        verified.append(dict(job=receipt['job'],rows=rows,returncode=receipt['returncode']))
    flattened = [(job['job'],row) for job in verified for row in job['rows']]
    assert {(r['job'],r['case'],r['status']) for r in summary['cases']} == {
        (j,row['case'],row['status']) for j,row in flattened}
    failures = []
    for job,row in flattened:
        if row['status'] == 'FAIL':
            result = details[(job,row['case'])]
            failures.append(dict(job=job,**row,error=result['detail'].get('error'),
                                 traceback=result['detail'].get('traceback')))
    assert len(failures) == 10
    host = [r for j,r in flattened if j.startswith('h-')]
    assert len(host) == 82 and collections.Counter(r['status'] for r in host) == {'PASS':79,'FAIL':3}
    regressions = []
    covers = []
    for row in summary['regressions']:
        receipt = read(base/'evidence/receipts'/(row['name']+'.json'))
        if row['status'] == '留给发布复审':
            assert receipt['execution'] == 'NOT_RUN_LEFT_FOR_RELEASE_REVIEW'
            regressions.append(dict(name=row['name'],state='NOT_RUN',covers=row['covers']))
            continue
        log = ROOT/receipt['log']
        assert receipt['execution'] == 'FINISHED' and receipt['returncode'] == 0
        assert sha(log) == receipt['log_sha256']
        assert receipt['dat_sha256'] == sha(ROOT/'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT')
        work = base/'run/local/jobs'/row['name']
        result_files = []
        for f in sorted(work.rglob('*.json')):
            data = read(f)
            if isinstance(data,dict) and ('status' in data or 'failed' in data):
                result_files.append(dict(path=str(f.relative_to(ROOT)),status=data.get('status'),
                                         failed=data.get('failed'),sha256=sha(f)))
        regressions.append(dict(name=row['name'],state='PASS_RECEIPT',covers=row['covers'],
                                seconds=receipt['seconds'],result_files=result_files))
        covers += row['covers']
    return dict(status='PASS_RECORD_AUDIT',receipt_count=len(verified),case_count=len(flattened),
                host_82=collections.Counter(r['status'] for r in host),failures=failures,
                cases=verified,regressions=regressions,completed_groups=len(covers),
                completed_by_unit=collections.Counter('mount' if '-mount-' in c else '28mm' if '-28mm-' in c else '50mm' for c in covers))


def main():
    started = time.monotonic()
    artifact = load('artifact_check'); artifact.main()
    import decode as D
    new = ROOT/'firmware/package_v38_g150_test/local/SD_ROOT/GXRCE.DAT'
    previous = ROOT/'firmware/package_v38_g139_test/local/SD_ROOT/GXRCE.DAT'
    sys.argv = ['mount_vs_50mm.py',str(new),str(previous)]
    mount = load('mount_vs_50mm')
    try:
        mount.main()
    except SystemExit as error:
        assert error.code == 0
    sys.argv = ['mount_section_check.py',str(new),str(ROOT/'firmware/package_v38_g139m_test/local/SD_ROOT/GXRCE.DAT')]
    section = load('mount_section_check'); section.main()
    assert read(HERE/'diff/mount-section-vs-g139m.json')['PASS']
    sys.argv = ['service_proof.py']
    proof = load('service_proof')
    try:
        proof.main()
    except SystemExit as error:
        assert error.code == 0
    old_elf = artifact.load(ROOT/'firmware/stage2l_switch/tools/build.py','review_elf')
    elf = old_elf.Elf(ROOT/'firmware/engine_v58_g150/candidate/local/full-r13/engine.elf')
    engine = next(s for s in elf.sections if s['name'] == '.engine')
    raw = new.read_bytes(); at = int.from_bytes(raw[132:136],'big'); length = int.from_bytes(raw[136:140],'big')
    assert elf.content(engine) == raw[at:at+length]
    release = (ROOT/'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert raw[at:at+length] == release[at:at+length]
    records = audit_records()
    (HERE/'evidence/implementation-audit.json').write_text(json.dumps(records,ensure_ascii=False,indent=1)+'\n')
    modules = D.modules(raw)
    wbs = {m['name']:[list(r[49:51]) for r in m['records'][:8]] for m in modules}
    result = dict(status='PASS_STATIC_REVIEW',code_bound_to_final_dat=True,wb_offsets=wbs,
                  seconds=round(time.monotonic()-started,3),ten_FAIL_rows=len(records['failures']),
                  host_82=records['host_82'],completed_groups=records['completed_groups'],
                  completed_by_unit=records['completed_by_unit'])
    (HERE/'evidence/static-review.json').write_text(json.dumps(result,indent=1)+'\n')
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    sys.path.insert(0,str(HERE)); main()
