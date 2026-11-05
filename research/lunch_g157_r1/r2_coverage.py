"""Coverage census at the existing failing input location; never estimate a correction."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from r2_common import C,R1
from collections import Counter


def main():
    while True:
        try:C.admit('r2-coverage');break
        except SystemExit as e:
            if e.code!=75:raise
            C.time.sleep(10)
    C.numerical();C.sys.addaudithook(C.fence);np=C.np
    blue=C.read(C.LOCAL/'blue.json')
    failed=next(r for r in blue['poster'] if r['id']=='R8052093')
    hlo,_,hhi=failed['input_hue_quantiles'];clo,_,chi=failed['input_chroma_quantiles']
    protected={}
    def read(p):
        protected[str(p)]=C.sha(p);return C.read(p)
    p=C.ROOT/'research/model_c040_r1/local/physical/noon-patches.json'
    noon=read(p)
    def inside(h,c):return (h>=hlo)&(h<=hhi)&(c>=clo)&(c<=chi)
    def nearby(h,c):return (h>=hlo-15)&(h<=hhi+15)&(c>=max(0,clo-2))&(c<=chi+2)
    coverage=[]
    for setting in sorted({r['setting'] for r in noon}):
        for split in ('T','V','card'):
            r=[v for v in noon if v['setting']==setting and v['split']==split]
            if not r:continue
            h=np.array([v['physical_input_hue'] for v in r]);c=np.array([v['physical_input_chroma'] for v in r])
            coverage.append(dict(setting=setting,split=split,total=len(r),
                                 exact_box=int(inside(h,c).sum()),nearby_box=int(nearby(h,c).sum())))
    points=read(C.ROOT/'research/model_c040_r1/local/physical/probe-points.json')
    entries=read(C.ROOT/'research/probe_pack_r3/local/expected.json')['M']
    meta=C.read(R1/'inventory.json')[2]['metadata'];model=C.camera_model(200,meta['color_raw13'])
    probes=[]
    for probe in ('probe2','probe3'):
        r=[v for v in points if v['probe']==probe and v['ROI']=='0.5']
        if probe=='probe2':
            D=C.module('r2_coverage_dat',C.ROOT/'research/v39_g153/dat_format.py')
            path=C.ROOT/'firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT'
            protected[str(path)]=C.sha(path);raw=path.read_bytes()
            es={k:D.expand_effect(raw,8+i) for i,k in enumerate(('A','RN','GN','BN','RD','GD','BD'))}
        else:es={k:bytes.fromhex(v['entry_hex']) for k,v in entries.items()}
        h=[];chroma=[];gray=[]
        for row in r:
            b=es[row['label']];x=np.asarray(row['physical']['x'])[None]
            y,ci=C.mm.MatrixRow.from_bytes(b[216:244]).apply(model.pre(b,x))
            h.append(float(np.angle(ci[0],deg=True)%360));chroma.append(float(abs(ci[0])));gray.append(row['gray'])
        h,c,g=np.asarray(h),np.asarray(chroma),np.asarray(gray)
        probes.append(dict(probe=probe,total=len(r),exact_box=int(inside(h,c).sum()),nearby_box=int(nearby(h,c).sum()),
                           exact_coloured=int((inside(h,c)&~g).sum()),nearby_coloured=int((nearby(h,c)&~g).sum()),
                           independent_colour_patches=len({v['patch'] for v in r if not v['gray']})))
    history_root=C.ROOT/'research/bluecyan_r1/local'
    identities=read(history_root/'history/identities.json')
    history=[]
    current=next(r for r in C.read(R1/'bank.json')['records'] if r['name']=='06 F-CN')
    current_bytes=Path(current['record']).read_bytes()
    for row in identities:
        if not row.get('identity',{}).get('accepted') or row['metadata']['unit']!='mount-a12' or row['metadata']['iso']!=200:
            continue
        p=Path(row['samples_file']);p=p if p.is_absolute() else history_root/p
        protected[str(p)]=C.sha(p)
        with np.load(p,allow_pickle=False) as z:
            use=z['cells'].sum(1)%2==1;raw=z['raw_codes'][use]
        rec=row['identity']['record'];p=Path(rec['record']);p=p if p.is_absolute() else history_root/p
        protected[str(p)]=C.sha(p);b=p.read_bytes()
        assert C.sha(p)==rec['sha256']
        x=C.input_codes(raw);y,ci=C.mm.MatrixRow.from_bytes(b[216:244]).apply(model.pre(b,x))
        h,c=np.angle(ci,deg=True)%360,abs(ci)
        history.append(dict(path=row['path'],labels=rec['labels'],points=len(h),
            exact_box=int(inside(h,c).sum()),nearby_box=int(nearby(h,c).sum()),
            same_C080_as_current06=b[115:211]==current_bytes[115:211],record_sha256=rec['sha256']))
    C.dump('coverage.json',dict(bounds=dict(hue=[hlo,hhi],chroma=[clo,chi]),
        nearby_expansion=dict(hue_degrees=15,chroma_codes=2),noon=coverage,probes=probes,history=history,
        no_parameter_estimation=True,box_used_only_to_count_existing_coverage=True,
        protected_sources=protected,created_utc=C.utc()))
    print('CURRENT INPUT BOX',hlo,hhi,clo,chi,flush=True)
    print('NOON COVERAGE',coverage,flush=True);print('PROBE COVERAGE',probes,flush=True)
    print('HISTORY COVERAGE',dict(exposures=len(history),exact_box_exposures=sum(r['exact_box']>0 for r in history),
        exact_box_points=sum(r['exact_box'] for r in history),nearby_exposures=sum(r['nearby_box']>0 for r in history),
        nearby_points=sum(r['nearby_box'] for r in history),
        exact_same_C080_exposures=sum(r['exact_box']>0 and r['same_C080_as_current06'] for r in history)),flush=True)


if __name__=='__main__':main()
