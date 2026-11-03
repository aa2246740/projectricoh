#!/usr/bin/env python3
"""Fit each quarantined official Leica cube once, using a shared 50mm input set."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import json
import traceback
from guard import HERE, LOCAL, DOWNLOADS, mount_guard, install_write_fence, dump


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',default='local/leica-complete')
    p.add_argument('--download-name',default='20261023-official')
    p.add_argument('--max-nfev',type=int,default=60)
    args=p.parse_args()
    mount_guard();install_write_fence()
    from camera import Camera
    from convert import parser,run,prepare,DEFAULT_SCENES
    camera=Camera()
    scenes=prepare(camera,DEFAULT_SCENES,280)
    cubes=sorted((DOWNLOADS/args.download_name).rglob('*.cube'))
    if not cubes:
        raise ValueError('没有官方 cube')
    results=[]
    for i,cube in enumerate(cubes,1):
        label=f'{i:02d}-'+cube.stem.replace(' ','_')
        out=HERE/args.out/label
        argv=[str(cube),'--input-space','llog','--output-space','gamma24',
              '--out',str(out),'--variants','safe,t1,t2-hypothesis','--max-nfev',str(args.max_nfev)]
        if 'Rec2020' in cube.stem and 'to_Rec709' not in cube.stem:
            argv+=['--output-gamut','rec2020']
        print('LUT',i,'/',len(cubes),cube.name,flush=True)
        try:
            result=run(parser().parse_args(argv),camera,scenes)
            results.append({'name':cube.name,'path':str(out.relative_to(HERE)),
                            'scores':result['scores'],'seconds':result['total_seconds'],'success':True})
        except Exception as exc:
            row={'name':cube.name,'path':str(out.relative_to(HERE)),'success':False,
                 'error':str(exc),'traceback':traceback.format_exc()}
            results.append(row);dump(out/'FAILED.json',row)
            print('FAILED',str(exc),flush=True)
        dump(HERE/args.out/'batch.json',results)
    return 0 if all(r['success'] for r in results) else 1


if __name__=='__main__':
    raise SystemExit(main())
