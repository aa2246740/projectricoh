"""Offline rerun, or one-command ingestion of another genuine ColorChecker RAW.

Downloads are an explicit separate action. Nothing is built, installed or sent to a camera.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
import argparse
import json
import subprocess


def step(name):
    log=c.LOCAL/(name+'.log')
    with log.open('w') as f:
        subprocess.run([sys.executable,'-I','-B',str(c.HERE/(name+'.py'))],cwd=c.ROOT,
                       stdout=f,stderr=subprocess.STDOUT,check=True)
    print(name,'OK',flush=True)


def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='action',required=True)
    sub.add_parser('run');sub.add_parser('fetch-public')
    add=sub.add_parser('add-chart');add.add_argument('--camera',choices=['gxr','griv'],required=True)
    add.add_argument('--dng',required=True);add.add_argument('--preview',required=True)
    add.add_argument('--corners',required=True,help='JSON TL,TR,BR,BL corners of six-by-four patch grid in preview pixels')
    add.add_argument('--formulation',choices=['pre2014','post2014'],required=True)
    args=ap.parse_args()
    if args.action=='fetch-public':
        for name in ('acquire','acquire_extra'):step(name)
        return
    c.verify()
    if args.action=='run':
        for name in ('prepare_data','extract','extract_griv'):step(name)
    else:
        from extract_griv import extract_chart
        corners=json.loads(args.corners)
        assert len(corners)==4 and all(len(v)==2 for v in corners)
        prefix=args.camera+'_added'
        extract_chart(args.dng,args.preview,corners,prefix)
        c.dump('chart_override_'+args.camera+'.json',dict(
            matrix_source=str(c.inp(args.dng).relative_to(c.ROOT)),
            patch_file=str((c.LOCAL/('patches_'+prefix+'.json')).relative_to(c.ROOT)),
            reference='cc_modern' if args.formulation=='post2014' else 'cc',
            user_provided_chart_formulation=args.formulation,corner_geometry=corners))
    for name in ('estimate','bridge','propagate','diagnostics','report','verify','seal'):step(name)


if __name__=='__main__':main()
