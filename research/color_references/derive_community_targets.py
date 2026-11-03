#!/usr/bin/env python3
"""Sparse, conditional probes of two explicitly non-authoritative Ricoh LUTs."""
import hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import numpy as np
from colour_math import lab_rgb,rgb_lab
from derive_dcp_targets import probes

def load_cube(path):
    n=None;rows=[];title=None
    for line in path.read_text().splitlines():
        line=line.split('#')[0].strip()
        if not line:continue
        if line.startswith('TITLE'):title=line[6:].strip('"');continue
        if line.startswith('LUT_3D_SIZE'):n=int(line.split()[1]);continue
        if line.startswith('DOMAIN_'):continue
        a=line.split()
        if len(a)==3:rows.append(list(map(float,a)))
    if n is None or len(rows)!=n**3:raise ValueError('Invalid cube size')
    return np.array(rows).reshape(n,n,n,3),title

def apply_cube(rgb,grid):
    n=grid.shape[0];v=np.clip(rgb,0,1)*(n-1);lo=np.floor(v).astype(int);f=v-lo;out=np.zeros_like(rgb)
    for dr in [0,1]:
        for dg in [0,1]:
            for db in [0,1]:
                x=np.minimum(lo+[dr,dg,db],n-1)
                w=np.prod(np.where([dr,dg,db],f,1-f),axis=1)
                out+=grid[x[:,2],x[:,1],x[:,0]]*w[:,None]
    return out

def main():
    pp=probes();input_rgb=lab_rgb(np.array([p['Lab_D50'] for p in pp]));results=[]
    for mode in ['positive','negative']:
        p=Path('/tmp/gxr_color_refs/downloads')/('colorreps_'+mode)/(mode+'.cube')
        grid,title=load_cube(p);out=apply_cube(input_rgb,grid)
        results.append({'mode':mode,'path_scratch':str(p),'title':title,'bytes':p.stat().st_size,
            'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'grid_size':len(grid),
            'golden_reference':False,'credibility':'LOW, community inspired implementation',
            'claimed_camera':'GR IV on Positive landing page; Negative page only says Ricoh, exact model unknown',
            'firmware':None,'sliders':None,'source_raw_jpeg_pairs_published_and_verified':False,
            'input_assumption':'display-encoded sRGB -> display-encoded sRGB; domain [0,1] verified, transfer/gamut not documented by cube header',
            'expected_error_de00_vs_actual_GR':None,'license':'free download, reuse/redistribution license unspecified; originals stay in scratch',
            'derived_targets_status':'推断 under the stated sRGB assumption, not a measured GR target',
            'input_gamut_clipped_probes':int(np.any((input_rgb<0)|(input_rgb>1),axis=1).sum()),
            'derived_probes':[{**p,'output_srgb':q.tolist(),'output_Lab_D50':l.tolist()} for p,q,l in zip(pp,out,rgb_lab(out))]})
    (HERE/'community_gr_probes.json').write_text(json.dumps({'schema':'community-conditional-probes-v1','sources':results},ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('Two low-credibility conditional probe tables written; neither is an acceptance reference')

if __name__=='__main__':main()
