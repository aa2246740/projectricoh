"""Repeat a full-start exact compatible fit under a fresh, non-overwriting tag."""
import argparse
from pathlib import Path
import signal
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import compat_g155c as compat
import fit_one as fit
import runtime as rt


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--family',required=True,choices=compat.FAMILIES)
    ap.add_argument('--unit',required=True,choices=tuple(compat.TARGETS));ap.add_argument('--index',type=int,required=True)
    ap.add_argument('--tag',required=True);ap.add_argument('--nfev',type=int,default=500)
    args=ap.parse_args();assert args.index in compat.TARGETS[args.unit]
    assert Path(args.tag).name==args.tag and '.' not in args.tag
    root=compat.activate(args.family);meta=rt.read(root/'targets'/args.unit/f'{args.index:02d}.json')
    compat.configure(args.family,bytes.fromhex(meta['template_hex']),compat.UNITS.index(args.unit))
    compat.full_confirm_support.gate=compat.gate_with_natural
    source,doc=compat.selected(root,args.unit,args.index);assert doc
    fit.run(args.unit,args.index,0,args.nfev,args.tag,True,'fast',str(source.relative_to(rt.HERE)),True)
    path=root/'fits'/args.unit/f'{args.index:02d}'/('L0_'+args.tag+'.json')
    value=rt.read(path);value.update(baseline_g155c=True,compat_family=args.family,
        expected_base05_flags=1,model_context=str(root.relative_to(rt.HERE)),
        new7_in_additional_exact_gate=args.unit=='mount-a12')
    rt.dump(path,value)
    print('Repeat full-start exact saved',str(path.relative_to(rt.HERE)),flush=True)


if __name__=='__main__':
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Repeat fit exceeded25 minutes')))
    signal.alarm(1500)
    main()
