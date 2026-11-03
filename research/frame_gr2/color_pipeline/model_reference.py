#!/usr/bin/env python3
"""Portable reference math transcribed from static evidence, not camera code.

This does not execute FRAME or its firmware. It models the inspected App's
balanced-profile preview and two recovered firmware tone operations. Neither
function constitutes a GXR ISP port or real-camera colour validation.
"""
import json
import math
from pathlib import Path

H=Path(__file__).resolve().parent
PROJECTION=(-43,-85,128,128,-107,-21)
THRESHOLDS=((1298,750,0,0),(1448,843,0,0),(1298,750,0,0),(1205,843,0,0))

def clip(x,lo=0,hi=1):
    return max(lo,min(hi,x))

def bank(rgb,selectors):
    r,g,b=rgb
    u=PROJECTION[0]*(r-b)+PROJECTION[1]*(g-b)
    v=PROJECTION[3]*(r-b)+PROJECTION[4]*(g-b)
    q=1 if u<=0 and v>0 else 2 if u<0 and v<=0 else 3 if u>=0 and v<0 else 0
    a=(u,v,-u,-v)[q]
    z=(v,-u,-v,u)[q]
    t=2048 if a+z==0 else 2048*a/(a+z)
    sector=q*5+sum(t<=x for x in THRESHOLDS[q])
    return selectors[sector]

def matrix(rgb,coeff,scale):
    return [clip(sum(coeff[3*i+j]*rgb[j] for j in range(3))/scale) for i in range(3)]

def balanced_sample(profile,rgb):
    z=matrix(rgb,profile['input_matrix_q8'],256)
    z=matrix(z,profile['local_matrices_q10'][bank(z,profile['selectors'])],1024)
    return [profile['rgb_curves_u8'][i][math.floor(v*1023+0.5)]/255 for i,v in enumerate(z)]

def trunc_div(a,b):
    return a//b if a>=0 else -((-a)//b)

def tone_adjust(y,high_low=0,highlight=0,shadow=0):
    """Recovered A079E1A0 integer operation. No intermediate clipping."""
    if y<=127:
        y-=trunc_div(shadow*y*(128-y),512)
    else:
        y+=trunc_div(highlight*(255-y)*(y-128),512)
    y+=trunc_div(high_low*y*(255-y),2048)
    return clip(y,0,255)

def negative_curve(contrast=0):
    """Recovered delta curve plus the observed contrast gain around code 128."""
    d=json.loads((H/'evidence/negative-tables.json').read_text())['curve_u8']
    gain=16+contrast
    def rounded(v):
        return (v+8)//16 if v>=0 else -((-v+8)//16)
    return [clip(128+rounded((v-128)*gain),0,255) for v in d]

def main():
    probes={}
    for p in sorted((H/'assets/apk/assets/flutter_assets/assets/profiles').glob('*.json')):
        profile=json.loads(p.read_text())
        tests=[(0,0,0),(0.25,0.25,0.25),(0.5,0.5,0.5),(0.75,0.75,0.75),(1,1,1),(1,0,0),(0,1,0),(0,0,1)]
        output=[dict(input_rgb=x,bank=bank(x,profile['selectors']),output_rgb=balanced_sample(profile,x)) for x in tests]
        # The row-sum constraints force each neutral to stay neutral before RGB curves.
        for row,x in zip(output,tests):
            if x[0]==x[1]==x[2]:
                idx=math.floor(x[0]*1023+0.5)
                assert row['output_rgb']==[c[idx]/255 for c in profile['rgb_curves_u8']]
        probes[p.stem]=output
    assert all(tone_adjust(i)==i for i in range(256))
    assert negative_curve()==json.loads((H/'evidence/negative-tables.json').read_text())['curve_u8']
    result=dict(verification='Own reference arithmetic checked against literal asset tables; no target execution.',
                limits='No camera, ISP colour domain or fitted visual match is validated.',probes=probes)
    (H/'evidence/reference-probes.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: neutral row sums, asset curve lookups, neutral tone controls and default contrast reconstruction.')

if __name__=='__main__':main()
