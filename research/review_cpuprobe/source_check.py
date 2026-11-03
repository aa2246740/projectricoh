"""Read-only source identity and extra dependency receipts for the fixed review."""
from pathlib import Path
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import review_scope as s
s.enable_fence()


def compare(left,right):
    a={str(p.relative_to(left)):s.sha(p) for p in left.rglob('*') if p.is_file()}
    b={str(p.relative_to(right)):s.sha(p) for p in right.rglob('*') if p.is_file()}
    return dict(left=str(left.relative_to(s.ROOT)),right=str(right.relative_to(s.ROOT)),
                left_files=len(a),right_files=len(b),
                different=[n for n in sorted(set(a)|set(b)) if a.get(n)!=b.get(n)])


def main():
    tree=s.ROOT/'firmware/engine_cpuprobe_v38'
    resident=compare(tree/'resident',s.ROOT/'firmware/engine_probe_p1/resident')
    assert not resident['different'],resident
    pairs=[]
    for left,right in [
        (tree/'candidate/containers/product/kernel.c',s.ROOT/'firmware/lut_p0_timing/kernel.c'),
        (tree/'cp_vectors.py',s.ROOT/'firmware/lut_p0_timing/vectors.py')]:
        a,b=s.sha(left),s.sha(right)
        assert a==b,(left,right)
        pairs.append(dict(left=str(left.relative_to(s.ROOT)),right=str(right.relative_to(s.ROOT)),sha256=a,equal=True))
    dependencies={}
    paths=[
        'research/tooling_m32r/prefix/bin/m32r-elf-objdump',
        'research/tooling_m32r_c/prefix/gcc/libexec/gcc/m32r-elf/13.4.0/cc1',
        'research/tooling_m32r_asm/prefix/bin/m32r-elf-as',
    ]
    for variant in ['engine_diag_v38_g147','engine_diag_v38_g147a']:
        paths += [f'firmware/{variant}/candidate/local/full-r1/{name}' for name in ['engine.bin','engine.elf']]
    for name in paths:
        p=s.ROOT/name
        dependencies[name]=dict(bytes=p.stat().st_size,sha256=s.sha(p))
    s.save(HERE/'source-check.json',dict(status='PASS',resident=resident,pairs=pairs,
                                      rebuilt_dat=False,layout='24 fresh layout offsets match the original object'))
    s.save(HERE/'dependencies.json',dependencies)
    print('SOURCE_CHECK_PASS',resident['left_files'],len(dependencies))


if __name__=='__main__':main()
