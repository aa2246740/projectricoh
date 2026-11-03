"""Rebind the existing acceptance scripts without changing their assertions."""
import hashlib,json,os
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=ROOT/'research/emulator_fast_r1'
DEST=HERE/'acceptance'
FAST=ROOT/'tools/gxr_emulator_fast/fix_r1'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-fast-fix-r1')


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    assert not DEST.exists()
    (DEST/'scripts').mkdir(parents=True)
    (DEST/'runs').mkdir();(DEST/'local').mkdir()
    sources=[SOURCE/name for name in ('cumulative.py','scope_guard.py','m2d_regression.py',
             'm2d_acceptance.py','m2d_file_regression.py','m2d_restart_run.py',
             'g145_replay.py','g145_compare.py')]
    sources += [SOURCE/'scripts'/name for name in ('safety.py','bootstrap.py','workload.py',
                'benchmark.py','suite.py','suite_case.py','limit.py','snapshot_check.py',
                'snapshot_edges.py','native_corrections.py','mutation_check.py','codec_check.py')]
    rows=[]
    for source in sources:
        target=DEST/source.relative_to(SOURCE)
        text=source.read_text()
        text=text.replace('tools/gxr_emulator_fast','tools/gxr_emulator_fast/fix_r1')
        text=text.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-fast-r1',str(TEMP))
        for expression in ('ROOT = HERE.parents[1]','ROOT = Path(__file__).resolve().parents[2]',
                           'ROOT = Path(__file__).resolve().parents[3]'):
            text=text.replace(expression,'ROOT = Path('+repr(str(ROOT))+')')
        text=text.replace("HERE = ROOT / 'research/emulator_fast_r1'","HERE = Path("+repr(str(DEST))+")")
        compile(text,str(target),'exec')
        target.write_text(text)
        rows.append(dict(source=str(source.relative_to(ROOT)),
                         source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                         adapter=str(target.relative_to(ROOT)),
                         adapter_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    (HERE/'runs/acceptance-adapters.json').write_text(json.dumps(dict(
        policy='Only tool paths, output paths, project roots and TMPDIR are rebound; assertions retained.',
        files=rows),indent=2)+'\n')
    print(json.dumps(dict(adapters=len(rows),destination=str(DEST))))


if __name__=='__main__':main()
