"""Repeat the host-only build and acceptance, retaining each phase's raw streams."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PYTHON=['/usr/bin/python3','-I','-B']


def run(label,script,*args,capture=True):
    command=PYTHON+[str(HERE/script),*args]
    if capture:
        with (HERE/f'local/{label}.stdout').open('wb') as stdout, (HERE/f'local/{label}.stderr').open('wb') as stderr:
            subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr,check=True)
        print('PASS '+label,flush=True)
    else:
        subprocess.run(command,cwd=ROOT,check=True)


def main():
    run('protected115','finalize115.py','protected')
    run('native115','native_evidence.py')
    run('build115','candidate/build115.py')
    folder=HERE/'candidate/local/full-r13'
    names=('GXRCE.DAT','engine.bin','engine.elf','reloc.bin','trust.bin')
    (HERE/'local/rebuild115-first.json').write_text(json.dumps(
        {n:hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in names},indent=2)+'\n')
    run('rebuild115','candidate/build115.py')
    for label,script,args in [
        ('compile115','verify115.py',['compile']),
        ('vectors115','candidate/verify_v34c.py',['vectors']),
        ('historical115','verify_historical115.py',[]),
        ('delta115','verify115.py',['seed']),
        ('suites115','verify115.py',['suites']),
        ('history115','verify115.py',['history']),
        ('decode115','verify115.py',['decode']),
        ('machine115','machine115.py',[]),
        ('envelope115','verify_boundaries115.py',[]),
        ('heap115','candidate/heap34c.py',[]),
        ('stage115','finalize115.py',['stage'])]:
        run(label,script,*args)
    # Leave seal/verify stdout outside the sealed tree to avoid hashing a
    # receipt file while the command is still writing that same file.
    run('seal115','finalize115.py','seal',capture=False)
    run('verify115','finalize115.py','verify',capture=False)


if __name__=='__main__':main()
