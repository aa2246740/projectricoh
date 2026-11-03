"""Original targets for 01-08, with fixed support masks and three unit row baselines."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np,ROOT,LOCAL,upstream
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree

def arrays(path):
    with np.load(path,allow_pickle=False) as z:return dict(z)

def lab_to_rgb(lab):
    lab=np.asarray(lab)
    fy=(lab[:,0]+16)/116
    f=np.c_[fy+lab[:,1]/500,fy,fy-lab[:,2]/200]
    d=6/29
    xyz=np.where(f>d,f**3,3*d*d*(f-4/29))*np.array([.95047,1.,1.08883])
    from gxr_studio.engine.colour import M709
    lin=xyz@np.linalg.inv(M709).T
    return np.clip(upstream.encode(lin,'srgb'),0,1)*255

def relative(base,standard,styled):
    cs,cm,cb=[np.hypot(v[:,1],v[:,2]) for v in (standard,styled,base)]
    active=(cs>=8)&(cm>=8)&(cb>=8)
    quotient=np.ones(len(base),complex)
    np.divide(styled[:,1]+1j*styled[:,2],standard[:,1]+1j*standard[:,2]+1e-20,
              out=quotient,where=active)
    ab=(base[:,1]+1j*base[:,2])*quotient
    return np.c_[base[:,0]+styled[:,0]-standard[:,0],ab.real,ab.imag]

class DenseTarget:
    def __init__(self,slot):
        folder=ROOT/('research/gr4_dense_returns_r1/local/target' if slot==1 else 'research/gr4_nega_returns_r1/local/target')
        a=arrays(folder/'paired_measurements.npz');info=rt.read(folder/'manifest.json')
        key='positive' if slot==1 else 'negative'
        f,inv=np.unique(np.round(a['feature'],9),axis=0,return_inverse=True)
        y=np.c_[a['standard'],a[key]]
        count=np.bincount(inv)
        values=np.column_stack([np.bincount(inv,weights=y[:,j])/count for j in range(6)])
        self.function=LinearNDInterpolator(f,values)
        self.tree=cKDTree(f)
        self.T=np.asarray(info['bridge']['T_white_balanced_neutral_normalized'])
        self.anchor=info['u118_raw_wb_without_BE']
        self.source=folder/'paired_measurements.npz'
        self.info=info

    def __call__(self,x,xyz,base):
        raw=np.asarray(x)@self.T.T*(self.anchor/320)
        uc=np.maximum(raw,1e-7)
        f=np.c_[np.log2(uc@np.array([.25,.5,.25])),np.log2(uc[:,0]/uc[:,1]),np.log2(uc[:,2]/uc[:,1])]
        pred=self.function(f)
        valid=np.isfinite(pred).all(1)&(raw>0).all(1)&(self.tree.query(f)[0]<=1.)
        target=lab_to_rgb(relative(rt.lab_from_codes(base),np.nan_to_num(pred[:,:3]),np.nan_to_num(pred[:,3:])))
        return target,valid,{}

def hc_target(x,xyz,base):
    doc=rt.read(ROOT/'research/bw03_round3/local/target_definitions.json')['pooled']
    lin=xyz@np.linalg.inv(upstream.matrix('rec709')).T
    intensity=lin@np.asarray(doc['mix'])/.18
    nodes=np.asarray(doc['tone']['q']);values=np.asarray(doc['tone']['j'])
    out=np.interp(np.log(np.maximum(intensity,1e-15)),np.log(nodes),values)
    low=intensity<nodes[0];high=intensity>nodes[-1]
    out[low]=values[0]*np.maximum(intensity[low],0)/nodes[0]
    out[high]=np.interp(intensity[high],[nodes[-1],max(4095/320,nodes[-1]*1.01)],[values[-1],255])
    valid=(intensity>=nodes[0])&(intensity<=nodes[-1])
    # Unsupported endpoint tails remain scored, and are identified separately.
    return np.repeat(np.clip(out,0,255)[:,None],3,axis=1),np.ones(len(x),bool),{'empirical_tone_supported_share':float(valid.mean())}

def main():
    from gxr_studio.camdata.datcodec import parse
    datpath=ROOT/'firmware/package_v310_g155/local/SD_ROOT/GXRCE.DAT'
    dat=parse(datpath.read_bytes())
    model,_,_=upstream.camera_model()
    groups={key:arrays(LOCAL/('samples_'+key+'.npz')) for key in ('train','synthetic','a12-50','a12-28','mount-a12')}
    measure=rt.module('ceiling_measure_sources',ROOT/'research/vlog_alchemy_eval/measure.py')
    official=measure.official_cubes()
    dense={slot:DenseTarget(slot) for slot in (1,2)}
    inverse_mod=rt.module('ceiling_s1rii_inverse',ROOT/'research/huzi_luts/panasonic.py')
    adapterpath=ROOT/'research/huzi_luts/local/artifacts/downloads/vlog-alchemy-20261024/Luts/Panasonic-Standard/Conversion/S1RIIS2V.cube'
    inverse=inverse_mod.StandardInverse(upstream.Cube.read(adapterpath))
    inverse_cache={}
    for key,g in groups.items():
        if not len(g['x']):continue
        result,residual=inverse.invert(upstream.xyz_to_encoded(g['xyz'],'vlog'))
        inverse_cache[key]=(result*255,residual)
        np.savez_compressed(LOCAL/('builtin_s1rii_'+key+'.npz'),rgb=result*255,residual=residual)
        print('S1RII',key,len(result),'unmatched',float((residual>1e-3).mean()),flush=True)
    names={1:'GRPos',2:'GRNeg',3:'HC BW',4:'Std',5:'F-CC',6:'F-CN',7:'L-Chr',8:'L-Viv'}
    original=ROOT/'artifacts/downloads/huzi-panasonic-std-luts-20261024/original'
    leica={7:upstream.Cube.read(original/'Leica Chrome.cube'),8:upstream.Cube.read(original/'Leica VIVID.cube')}
    sources={1:dense[1].source,2:dense[2].source,3:ROOT/'research/bw03_round3/local/target_definitions.json',
             4:datpath,5:ROOT/official['flog2c','CLASSIC-CHROME'][1]['archive'],
             6:ROOT/official['flog2c','CLASSIC-Neg.'][1]['archive'],
             7:original/'Leica Chrome.cube',8:original/'Leica VIVID.cube'}
    rows=[]
    for ui,unit in enumerate(('a12-50','a12-28','mount-a12')):
        for slot in range(1,9):
            index=27+ui*8+slot-1
            entry=dat.entry_of(ui,slot)
            result={};scores={};group_files={};coverage={}
            for key,g in groups.items():
                if not len(g['x']):scores[key]=None;continue
                gui=2 if key=='mount-a12' else 1 if key=='a12-28' else ui
                base=model.predict(dat.entry_of(gui,4),g['x'],bw_chroma='zero')
                details={}
                if slot in (1,2):want,valid,details=dense[slot](g['x'],g['xyz'],base)
                elif slot==3:want,valid,details=hc_target(g['x'],g['xyz'],base)
                elif slot==4:want,valid=base.copy(),np.ones(len(base),bool)
                elif slot in (5,6):
                    style='CLASSIC-CHROME' if slot==5 else 'CLASSIC-Neg.'
                    want=official['flog2c',style][0].apply(measure.fg_input(g['xyz'],'flog2c'))*255
                    valid=np.ones(len(base),bool)
                else:
                    ib,err=inverse_cache[key]
                    want=np.clip(.3*ib+.7*leica[slot].apply(ib/255)*255,0,255)
                    valid=np.ones(len(base),bool)
                    details={'inverse_residual':rt.stats(err),'inverse_unmatched_share':float((err>1e-3).mean())}
                pred=np.rint(model.predict(entry,g['x'],bw_chroma='zero'))
                coverage[key]=dict(total=len(base),supported=int(valid.sum()),supported_share=float(valid.mean()),**details)
                scores[key]=rt.score(base[valid],pred[valid],want[valid])
                result[key+'_base']=base[valid];result[key+'_target']=want[valid];result[key+'_published']=pred[valid]
                filename=f'samples_builtin_{index:02d}_{key}.npz'
                group_files[key]=filename
                np.savez_compressed(LOCAL/filename,**{k:v[valid] for k,v in g.items()})
            np.savez_compressed(LOCAL/f'target_{index:02d}.npz',**result)
            row=dict(index=index,name=f'{slot:02d} {names[slot]} [{unit}]',family='builtin',builtin_slot=slot,
                camera_ui=ui,unit=unit,source=str(sources[slot].relative_to(ROOT)),source_sha256=rt.sha(sources[slot]),
                entry_hex=entry.hex(),scores=scores,group_files=group_files,coverage=coverage,
                target_scope='GR IV measured relative LCh bridge' if slot in (1,2) else
                    'GR IV HC empirical linear-sRGB mixture and measured tone' if slot==3 else
                    'exact original Standard identity' if slot==4 else
                    'official F-Log2C / F-Gamut C, direct display-code convention' if slot in (5,6) else
                    'S1RII numerical inverse, original creator LUT at original 70% concentration',
                unit_scope='50mm ISO200 kernel' if ui==0 else 'unit-specific original rows; transferred 50mm kernel, not calibrated',
                published_dat=str(datpath.relative_to(ROOT)),published_dat_sha256=rt.sha(datpath),
                current_curve_control=bool(entry[1]&4),current_flags=int(entry[1]),input='scene',output='srgb')
            rt.dump(LOCAL/f'target_{index:02d}.json',row)
            rows.append(row)
            print(row['name'],'training',coverage['train']['supported'],'holdout',scores[unit] if unit=='a12-28' else scores[unit]['similarity_percent'],flush=True)
    rt.dump(LOCAL/'builtin_sources.json',rows)
    rt.finish('prepare_builtin')

if __name__=='__main__':main()
