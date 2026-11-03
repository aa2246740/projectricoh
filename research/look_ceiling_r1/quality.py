"""Fixed, reachable gradient and hue-ring diagnostics for integer models."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np

def longest_run(values):
    v=np.asarray(values)
    change=np.r_[True,np.any(np.diff(v,axis=0)!=0,axis=1),True]
    return int(np.diff(np.flatnonzero(change)).max()) if len(v) else 0

def fixtures(camera,n=2049):
    t=np.linspace(0,1,n)[:,None]
    colors={'gray':(np.zeros(3),np.full(3,255.)),
            'sky':(np.array([70.,115.,180.]),np.array([195.,224.,248.])),
            'skin':(np.array([70.,42.,30.]),np.array([236.,191.,157.]))}
    out={k:camera.curve.inverse(a+(b-a)*t) for k,(a,b) in colors.items()}
    rings=[]
    hue=np.linspace(0,360,721)
    for y in (64.,128.,192.):
        for radius in (5.,20.,40.):
            ci=radius*np.exp(1j*np.deg2rad(hue))
            pre=camera.row.invert(np.full(len(hue),y),ci)
            valid=np.all((pre>camera.curve.ys[0])&(pre<camera.curve.ys[-1]),axis=1)
            rings.append(dict(y=y,radius=radius,x=camera.curve.inverse(pre),valid=valid))
    return out,rings

def diagnostics(camera,predict,gradients,rings):
    gradients_out={}
    for key,x in gradients.items():
        continuous=predict(x,False)
        rounded=np.rint(continuous)
        lab=rt.lab_from_codes(continuous)
        qlab=rt.lab_from_codes(rounded)
        step=rt.delta_e00(lab[:-1],lab[1:])
        qstep=rt.delta_e00(qlab[:-1],qlab[1:])
        chroma=np.hypot(lab[:,1],lab[:,2])
        hue=np.unwrap(np.arctan2(lab[:,2],lab[:,1]))*180/np.pi
        huevalid=(chroma[:-1]>=5)&(chroma[1:]>=5)
        gradients_out[key]=dict(n=len(x),continuous_step_de00=rt.stats(step),integer_step_de00=rt.stats(qstep),
            adjacent_integer_code_jump_max=int(abs(np.diff(rounded,axis=0)).max()),
            longest_identical_output_run=longest_run(rounded),
            negative_lightness_steps=int((np.diff(lab[:,0])<-.001).sum()),
            hue_step_max_deg=float(abs(np.diff(hue)[huevalid]).max()) if huevalid.any() else None,
            quantization_de00=rt.stats(rt.delta_e00(lab,qlab)),
            jump_gt_1_de00=int((qstep>1).sum()),jump_gt_2_de00=int((qstep>2).sum()))
    rr=[]
    for r in rings:
        rgb=predict(r['x'],False)
        y,co=camera.mm.ycbcr(rgb)
        angle=np.unwrap(np.angle(co))*180/np.pi
        valid=r['valid'][:-1]&r['valid'][1:]&(abs(co[:-1])>=2)&(abs(co[1:])>=2)
        eligible=r['valid'][:-1]&r['valid'][1:]
        slope=np.diff(angle)/.5
        rr.append(dict(y=r['y'],radius=r['radius'],valid_intervals=int(valid.sum()),
            eligible_input_intervals=int(eligible.sum()),undefined_low_chroma_intervals=int((eligible&~valid).sum()),
            min_slope=float(slope[valid].min()) if valid.any() else None,
            reverse_intervals=int((slope[valid]<-.001).sum()),
            hue_step_max_deg=float(abs(np.diff(angle)[valid]).max()) if valid.any() else None))
    return dict(label='电脑预测',gradients=gradients_out,rings=rr,
        hue_monotone=all(r['reverse_intervals']==0 for r in rr) if sum(r['valid_intervals'] for r in rr)>0 else None,
        hue_defined_intervals=sum(r['valid_intervals'] for r in rr),
        hue_undefined_low_chroma_intervals=sum(r['undefined_low_chroma_intervals'] for r in rr),
        max_continuous_gradient_step_de00=max(v['continuous_step_de00']['max'] for v in gradients_out.values()),
        max_integer_gradient_step_de00=max(v['integer_step_de00']['max'] for v in gradients_out.values()),
        reverse_hue_intervals=sum(r['reverse_intervals'] for r in rr),
        interpretation='Fixed sparse fixtures, not a proof for all images; target may itself reverse hue.')
