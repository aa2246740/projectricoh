"""Run the complete offline sequence in foreground processes."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt


def main():
    # Keep the original experiment intact unless a complete repeat is requested.
    if '--full' not in sys.argv:
        subprocess.run([sys.executable, '-I', '-B', str(rt.HERE / 'verify.py'), '--checksums-only'], check=True)
        return
    steps = [('freeze_references.py', []), ('prepare.py', []),
        ('fit.py', ['P0']), ('fit.py', ['P1']), ('fit.py', ['P2']),
        ('new_samples.py', []), ('source_audit.py', []), ('evaluate.py', []),
        ('diagnose.py', []), ('renderer_check.py', []), ('verify.py', ['--isolation']),
        ('report.py', []), ('verify.py', ['--seal'])]
    for filename, arguments in steps:
        label = Path(filename).stem + ('_' + '_'.join(a.lstrip('-') for a in arguments) if arguments else '')
        with (rt.LOCAL / ('repeat_' + label + '.log')).open('w') as stream:
            stream.write('本文件误差与训练分数均为对真实 GR IV 照片的验证；参数值与检查计数另列。\n')
            stream.flush()
            subprocess.run([sys.executable, '-I', '-B', str(rt.HERE / filename), *arguments],
                cwd=rt.ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
        print('Completed', label, flush=True)


if __name__ == '__main__': main()
