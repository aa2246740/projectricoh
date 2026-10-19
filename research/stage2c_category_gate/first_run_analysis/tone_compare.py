import sys, importlib.util, numpy as np
from pathlib import Path
from PIL import Image
spec=importlib.util.spec_from_file_location('ac','research/color_calibration/analyze_capture.py')
ac=importlib.util.module_from_spec(spec); spec.loader.exec_module(ac)
D={'1144':'captures/a12-50/2026-10-19/stage2c-first-run','1145':'captures/a12-50/2026-10-19/stage2c-first-run',
   '1146':'captures/a12-50/2026-10-19/stage2c-first-run','1147':'captures/a12-50/2026-10-19/stage2c-first-run'}
N=16
out={}
for n,d in D.items():
    t=ac.Tiff(Path(f"{d}/R805{n}.DNG").read_bytes())
    m=ac.decode_raw(t); m=m[0] if isinstance(m,tuple) else m
    m=np.asarray(m,dtype=np.float64)
    root=t.ifd(t.root); sub=[t.ifd(o) for o in root[330]['value']]
    raw=next(x for x in sub if x.get(262,{}).get('value')==[32803])
    # crop to JPEG frame: origin (8,7) -> 4288x2848 ; CFA after crop starts G/B/R/G
    m=m.reshape(2848,4288)
    neutral=[x for x in (root.get(50728,{}).get('value') or [])]
    g1=m[0::2,0::2]; b=m[0::2,1::2]; r=m[1::2,0::2]; g2=m[1::2,1::2]
    an=np.array([float(v) for v in neutral]) if neutral else np.array([0.6,1,0.6])
    R=r/an[0]; G=(g1+g2)/2/an[1]; B=b/an[2]
    lum=(R+2*G+B)/4/4095.0                                   # WB'd sensor luminance proxy, half-res 1424x2144
    j=np.asarray(Image.open(f"{d}/R805{n}.JPG").convert('RGB'),dtype=np.float64)[0::2,0::2][:lum.shape[0],:lum.shape[1]]
    Y=0.2126*j[...,0]+0.7152*j[...,1]+0.0722*j[...,2]
    lb=ac.mean_blocks(lum[:lum.shape[0]//N*N,:lum.shape[1]//N*N],N).ravel()
    yb=ac.mean_blocks(Y[:Y.shape[0]//N*N,:Y.shape[1]//N*N],N).ravel()
    ok=(lb>0.002)&(lb<0.95)
    out[n]=(lb[ok],yb[ok])
# common log-spaced sensor levels, median JPEG Y per bin
edges=np.geomspace(0.01,0.8,12)
print("sensor lvl " + " ".join(f"{(a*b)**.5:6.3f}" for a,b in zip(edges[:-1],edges[1:])))
for n,(l,y) in out.items():
    row=[]
    for a,b in zip(edges[:-1],edges[1:]):
        s=(l>=a)&(l<b); row.append(f"{np.median(y[s]):6.1f}" if s.sum()>=30 else "     -")
    print(f"R805{n}   "+" ".join(row))

import json
ref=json.load(open('research/color_calibration/reference_analysis.json'))['relative_mappings']
std=np.array(ref['ricoh_gr3_positive']['tone_input_encoded_luma'])*255
gp=np.array(ref['ricoh_gr3_positive']['tone_output_encoded_luma'])*255
gn=np.array(ref['ricoh_gr3_negative']['tone_output_encoded_luma'])*255
# smooth curves per shot on a fine log grid
grid=np.geomspace(0.008,0.6,60)
def curve(n):
    l,y=out[n]; c=[]
    for g in grid:
        s=(l>=g/1.12)&(l<g*1.12); c.append(np.median(y[s]) if s.sum()>=30 else np.nan)
    return np.array(c)
cs={n:curve(n) for n in out}
base=np.nanmean([cs['1144'],cs['1147']],axis=0)   # GXR stock (two shots agree)
ok=~np.isnan(base)
def at_std(n,v):
    # sensor level where GXR stock outputs v, then that shot's output there
    gb=base[ok]; gg=np.log(grid[ok]); c=cs[n][ok]
    i=np.argsort(gb); x=np.interp(v,gb[i],gg[i]); m=~np.isnan(c)
    return np.interp(x,gg[m],c[m])
print("\nGR III Standard gray level (8-bit):      "+" ".join(f"{v:6.1f}" for v in std))
print("GR III Positive  - Standard            :  "+" ".join(f"{v:+6.1f}" for v in gp-std))
print("GR III Negative  - Standard            :  "+" ".join(f"{v:+6.1f}" for v in gn-std))
for n in ('1145','1146','1147'):
    print(f"GXR R805{n} - GXR stock at same level:  "+" ".join(f"{at_std(n,v)-v:+6.1f}" for v in std))
