"""Seal all actual outputs and read-only inputs using repository-root paths."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import datetime
import json
import platform
import subprocess
import support as s


def manifest_inputs():
    result={}
    for name in ('protected_inputs.json','model_inputs.json','model_inputs_calibration.json',
                 'model_inputs_verification.json','model_inputs_previews.json','model_inputs_interactions.json'):
        data=json.loads((s.LOCAL/name).read_text())
        for rel,h in data.items():
            if rel in result and result[rel]!=h:raise ValueError('conflicting input hash: '+rel)
            result[rel]=h
    for rel,h in result.items():
        if s.sha(s.ROOT/rel)!=h:raise ValueError('input changed: '+rel)
    return result


def check():
    sums=s.HERE/'SHA256SUMS';recorded={}
    for line in sums.read_text().splitlines():
        h,rel=line.split('  ',1)
        p=(s.ROOT/rel).resolve()
        if not p.is_relative_to(s.ROOT):raise ValueError('manifest path outside repository')
        if rel in recorded:raise ValueError('duplicate manifest path')
        if not p.is_file() or s.sha(p)!=h:raise ValueError('checksum mismatch: '+rel)
        recorded[rel]=h
    outputs={str(p.relative_to(s.ROOT)) for p in s.HERE.rglob('*') if p.is_file() and p!=sums}
    if not outputs.issubset(recorded):raise ValueError('unsealed task files: '+str(outputs-set(recorded)))
    if any(p.suffix.upper()=='.DAT' for p in s.HERE.rglob('*') if p.is_file()):raise ValueError('unexpected generated DAT')
    s.verify_inputs()
    print('PASS SHA256SUMS:',len(recorded),'files;',len(outputs),'task outputs; no generated DAT',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    s.guard()
    if args.check:check();return
    s.dependencies()
    import numpy,scipy,PIL
    environment=dict(python=sys.version,executable='/usr/bin/python3',platform=platform.platform(),
                     numpy=numpy.__version__,scipy=scipy.__version__,pillow=PIL.__version__,
                     package_path='/Users/wu/Library/Python/3.9/lib/python/site-packages',
                     font_path='/System/Library/Fonts/Supplemental/Songti.ttc',
                     font_sha256=s.sha('/System/Library/Fonts/Supplemental/Songti.ttc'),
                     compiler=subprocess.check_output(['/usr/bin/clang','--version'],text=True),
                     task_process_policy='serial, BLAS threads=1; no subprocess fan-out',
                     worktree=str(s.ROOT),output_fence=str(s.HERE),
                     finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    s.dump(s.LOCAL/'environment.json',environment)
    inputs=manifest_inputs();s.dump(s.LOCAL/'all_inputs.json',inputs)
    import generate_report
    generate_report.main()
    outputs={str(q.relative_to(s.ROOT)):s.sha(q) for q in sorted(s.HERE.rglob('*')) if q.is_file() and q.name!='SHA256SUMS'}
    source={name:h for name,h in outputs.items() if '/src/' in name}
    s.dump(s.LOCAL/'algorithm_manifest.json',dict(schema='knobs-v2-r1/sealed-host-research/1',sources=source,
             calibration_sha256=s.sha(s.LOCAL/'calibration.json'),variants_sha256=s.sha(s.LOCAL/'variants.bin'),
             verification_sha256=s.sha(s.LOCAL/'verification.json'),preview_verification_sha256=s.sha(s.LOCAL/'preview_verification.json'),
             interactions_sha256=s.sha(s.LOCAL/'interaction_verification.json'),amount_fit_sha256=s.sha(s.LOCAL/'amount_curve_fit.json')))
    outputs={str(q.relative_to(s.ROOT)):s.sha(q) for q in sorted(s.HERE.rglob('*')) if q.is_file() and q.name!='SHA256SUMS'}
    merged=dict(inputs);merged.update(outputs)
    (s.HERE/'SHA256SUMS').write_text(''.join(f'{merged[rel]}  {rel}\n' for rel in sorted(merged)))
    check()


if __name__=='__main__':main()
