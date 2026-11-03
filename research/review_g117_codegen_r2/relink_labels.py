"""Reproduce the accepted final engine while retaining anonymous-object labels.

All inputs are read-only. Every compiler temporary and output is in this folder.
Run with /usr/bin/python3 -I -B.
"""
from pathlib import Path
import hashlib, json, os, subprocess, sys, time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
OLD = ROOT / 'research/review_g117_codegen'
sys.path.insert(0, str(OLD))
from audit import Elf


def main(g):
    src = OLD / ('compiler116' if g == 116 else 'compiler')
    dest = OUT / ('labels' + str(g))
    dest.mkdir(exist_ok=True)
    (dest / 'tmp').mkdir(exist_ok=True)
    command = json.loads((src / 'command.json').read_text())['argv']
    command = [x.replace(str(src), str(dest)) for x in command]
    (dest / 'engine.ld').write_bytes((src / 'engine.ld').read_bytes())
    command[1:1] = ['-save-temps=obj', '-Wa,-L', '-Wl,--discard-none']
    env = dict(os.environ, TMPDIR=str(dest / 'tmp'))
    start = time.time()
    with (dest / 'stdout').open('w') as so, (dest / 'stderr').open('w') as se:
        result = subprocess.run(command, cwd=dest, env=env, stdout=so, stderr=se)
    record = dict(argv=command, returncode=result.returncode, seconds=time.time()-start)
    if result.returncode == 0:
        actual = Elf(dest / 'engine.elf')
        original = Elf(OLD / ('engine' + str(g) + '.elf'))
        record.update(engine_equal=actual.engine['data'] == original.engine['data'],
                      engine_sha256=hashlib.sha256(actual.engine['data']).hexdigest(),
                      symbols=len(actual.symbols), locals=[n for n in actual.symbols if n.startswith('.LC')])
    (dest / 'command.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record | {'argv': 'see command.json', 'locals': len(record.get('locals', []))}), flush=True)
    assert result.returncode == 0 and record['engine_equal'], record


if __name__ == '__main__':
    main(int(sys.argv[1]))
