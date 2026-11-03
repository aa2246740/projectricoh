"""Published hardware fields and neutral-axis properties of the declared targets."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import struct
import runtime as rt
from runtime import np,ROOT,LOCAL
from prepare_builtin import DenseTarget,hc_target

def main():
    inputs=[]
    for group in ('train','synthetic','a12-50','mount-a12'):
        with np.load(LOCAL/('samples_'+group+'.npz'),allow_pickle=False) as z:x=z['x']
        inputs.append(dict(group=group,n=len(x),
            any_channel_above_4095_share=float((x>4095).any(axis=1).mean()),
            above_4095_share_by_channel=(x>4095).mean(axis=0).tolist(),
            any_negative_share=float((x<0).any(axis=1).mean()),maximum_code=float(x.max()),
            physical_input_bit_depth_verified=False,
            meaning='The declared u12 interpolation model clips at 4095. This does not independently prove where real ISP clipping occurs.'))
    rt.dump('input_diagnostics.json',inputs)
    from gxr_studio.camdata.datcodec import parse
    from gxr_studio.engine.knobs import dec
    dat=parse((ROOT/'firmware/package_v310_g155/local/SD_ROOT/GXRCE.DAT').read_bytes())
    fields=[]
    for ui,unit in enumerate(('a12-50','a12-28','mount-a12')):
        base=dat.entry_of(ui,4);row0=rt.mm.MatrixRow.from_bytes(base[216:244])
        for slot in range(1,9):
            entry=dat.entry_of(ui,slot);row=rt.mm.MatrixRow.from_bytes(entry[216:244])
            coeff=np.array([[dec(v,128) for v in entry[k:k+4]] for k in range(115,211,4)])
            asymmetric=np.flatnonzero((coeff[:,0]!=coeff[:,3])|(coeff[:,1]!=-coeff[:,2]))
            fields.append(dict(unit=unit,slot=slot,flags=int(entry[1]),type26_independent=bool(entry[1]&4),
                control_halfword=int.from_bytes(entry[445:447],'big'),
                R_differs_from_G=entry[379:412]!=entry[82:115],B_differs_from_G=entry[412:445]!=entry[82:115],
                curve_input_nodes_changed=entry[20:82]!=base[20:82],
                Y_coefficients_changed=int(np.sum(row.coef[0]!=row0.coef[0])),
                chroma_coefficients_changed=int(np.sum(row.coef[1:]!=row0.coef[1:])),
                offset_fields_changed=[i for i,(a,b) in enumerate(zip(row.tail,row0.tail)) if a!=b],
                chroma_row_sums=row.row_sums()[1:].tolist(),
                asymmetric_sector_indices=asymmetric.tolist(),native_BW_discards_chroma=slot==3,
                C120_in_current_552=False,C004_in_current_552=False,RLUT_in_current_552=False,
                evidence='Published DAT byte differences, not current camera runtime readback'))
    rt.dump('published_fields.json',fields)
    camera=rt.Camera();model,dat152,_=rt.upstream.camera_model()
    protocol=rt.read(LOCAL/'protocol_private.json');ref=protocol['scene_inventory'][0]
    raw=np.repeat(camera.curve.inverse(np.linspace(0,255,1025))[:,None],3,axis=1)
    base=camera.stock(raw);xyz=camera.xyz(raw,np.asarray(ref['neutral']),np.asarray(ref['matrix']))
    base_lab=rt.lab_from_codes(base)
    palette=rt.lab_from_codes(np.repeat(np.arange(256)[:,None],3,axis=1))
    measure=rt.module('ceiling_axis_fuji',ROOT/'research/vlog_alchemy_eval/measure.py')
    official=measure.official_cubes();dense={1:DenseTarget(1),2:DenseTarget(2)}
    inv_module=rt.module('ceiling_axis_inverse',ROOT/'research/huzi_luts/panasonic.py')
    inverse=inv_module.StandardInverse(rt.upstream.Cube.read(ROOT/'research/huzi_luts/local/artifacts/downloads/vlog-alchemy-20261024/Luts/Panasonic-Standard/Conversion/S1RIIS2V.cube'))
    s1,_=inverse.invert(rt.upstream.xyz_to_encoded(xyz,'vlog'));s1*=255
    rows=[];private={}
    for index in list(range(27))+list(range(27,35)):
        meta=rt.read(LOCAL/f'target_{index:02d}.json');support=np.ones(len(raw),bool)
        if index<27:
            target=rt.fit_adapter.target_of(dict(path=ROOT/meta['source'],input=meta['input'],output=meta['output'],interpretation=meta.get('interpretation','declared')))
            want=target.render(base,xyz)
        else:
            slot=meta['builtin_slot']
            if slot in (1,2):want,support,_=dense[slot](raw,xyz,base)
            elif slot==3:want,_,_=hc_target(raw,xyz,base)
            elif slot==4:want=base.copy()
            elif slot in (5,6):
                name='CLASSIC-CHROME' if slot==5 else 'CLASSIC-Neg.'
                want=official['flog2c',name][0].apply(measure.fg_input(xyz,'flog2c'))*255
            else:
                name='Leica Chrome' if slot==7 else 'Leica VIVID'
                cube=rt.upstream.Cube.read(ROOT/'artifacts/downloads/huzi-panasonic-std-luts-20261024/original'/(name+'.cube'))
                want=np.clip(.3*s1+.7*cube.apply(s1/255)*255,0,255)
        lab=rt.lab_from_codes(want);chroma=np.linalg.norm(lab[:,1:],axis=1)
        errors=rt.delta_e00(lab[support,None,:],palette[None,:,:]).min(axis=1)
        shadow=support&(base_lab[:,0]>=5)&(base_lab[:,0]<25)
        highlight=support&(base_lab[:,0]>=75)&(base_lab[:,0]<=95)
        tint=lambda mask:np.median(lab[mask,1:],axis=0).tolist() if mask.any() else None
        rows.append(dict(label='电脑预测',index=index,name=meta['name'],supported=int(support.sum()),
            target_gray_chroma=rt.stats(chroma[support]),neutral_only_best_8bit_floor_de00=rt.stats(errors),
            shadow_ab=tint(shadow),highlight_ab=tint(highlight),
            target_gray_RGB_negative_steps=(np.diff(want,axis=0)<-1e-4).sum(axis=0).tolist(),
            meaning='A neutral-only L0 cannot beat the grey-output floor on exact neutral inputs. This is not a photo-wide additive bound.'))
        private['target_'+str(index)]=want
    np.savez_compressed(LOCAL/'target_gray_axes.npz',raw=raw,base=base,**private)
    rt.dump('target_gray_axes.json',rows)
    rt.finish('target_diagnostics')
    print('Published fields',len(fields),'neutral-axis targets',len(rows),flush=True)

if __name__=='__main__':main()
