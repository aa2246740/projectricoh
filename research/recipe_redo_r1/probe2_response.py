"""Versioned local Y/Cb/Cr derivative transfer; no full-colour acceptance claim."""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from entry_codec import predict as original_predict
from fast_backend import load
import fit_one

OUT=rt.LOCAL/'probe2_local_response'
EVIDENCE=OUT/'evidence'
NODES=(8,16,19)
TRAIN=('R8051935','R8051936','R8051937','R8051947','R8051948','R8051949')
YCC=np.array([[.299,.587,.114],[-.168736,-.331264,.5],[.5,-.418688,-.081312]])
RGB=np.linalg.inv(YCC)


def freeze():
    source=rt.ROOT/'research/probe_pack_r2/local/field_probe2_20261103'
    EVIDENCE.mkdir(parents=True,exist_ok=False)
    names=('recipe_redo_handoff.json','measure-0.35.json','measure-0.5.json','measure-0.65.json',
        'model.json','inputs.json','metadata.json','acceptance.json','primary-components.json',
        'primary-colors.json','independent-color-check.json','shape_sensitivity_summary.json','symmetry.json')
    manifest=[]
    for name in names:
        p=source/name;shutil.copyfile(p,EVIDENCE/name)
        manifest.append(dict(source=str(p.relative_to(rt.ROOT)),file=str((EVIDENCE/name).relative_to(rt.HERE)),sha256=rt.sha(p)))
    for p in (rt.ROOT/'research/probe_pack_r2/FIELD_PROBE2.md',rt.ROOT/'research/probe_pack_r2/probe2_field.py',
              rt.ROOT/'research/probe_pack_r2/probe2_field_report.py'):
        shutil.copyfile(p,EVIDENCE/p.name);manifest.append(dict(source=str(p.relative_to(rt.ROOT)),file=str((EVIDENCE/p.name).relative_to(rt.HERE)),sha256=rt.sha(p)))
    handoff=rt.read(EVIDENCE/'recipe_redo_handoff.json')
    assert not handoff['quantitative_L1_full_color_accepted']
    inputs=rt.read(EVIDENCE/'inputs.json')
    for item in inputs['files']:assert rt.sha(rt.ROOT/item['file'])==item['sha256']
    dat=rt.ROOT/'firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT'
    assert rt.sha(dat)==handoff['probe_dat_sha256']
    from g155c_baseline import decoder
    D=decoder();raw=dat.read_bytes()
    entries={key:D.expand_effect(raw,8+i).hex() for i,key in enumerate(('A','RN','GN','BN','RD','GD','BD'))}
    rt.dump(OUT/'probe_records.json',entries)
    rt.dump(OUT/'source_manifest.json',dict(files=manifest,photo_inputs=inputs['files'],
        no_probe_frame_used_as_04_training=True,unknown_frames_remain_unknown=['R8051944','R8051945','R8051946']))
    rt.dump(OUT/'policy.json',dict(created_utc=rt.utc(),training_frames=TRAIN,
        local_nodes=NODES,allowed_increment_by_node={'8':[0,2],'16':[-2,0],'19':[0,2]},
        anchor='Each previously selected MOUNT L1 record; every other curve node, matrix and sector is frozen',
        calibration='Separate regularized Y/Cb/Cr ratios local in input brightness, hue, node and signed step',
        hue_bandwidth=.06,brightness_bandwidth='half of the node support width',ridge=.01,
        no_global_RGB_gain=True,no_fixed_chroma_matrix=True,
        transfer_to_nonStandard_recipe_is_a_model_hypothesis=True,
        full_colour_quantitative_acceptance=False,unknown_directions_not_symmetrised=True,
        exact_protocol='All declared current/grey/parent starts projected into the signed local domain; feasible integer candidates retained; iteration candidate added as start and kept'))
    print('PROBE2 FROZEN',len(manifest),'evidence files;',len(inputs['files']),'photo hashes',flush=True)


def coordinates(x):
    x=np.asarray(x);den=np.maximum(np.sum(x,axis=1),1.)
    return np.stack(((x[:,0]-x[:,1])/den,(x[:,2]-x[:,1])/den),axis=1)


class Calibration:
    def __init__(self,branch='0.5'):
        self.branch=branch
        self.data=rt.read(OUT/'calibration.json')['branches'][branch]
        self.xs=np.array(rt.read(EVIDENCE/'model.json')['xs'])

    def gains(self,x,ch,node):
        data=self.data[f'{ch}/{node}'];query=np.asarray(x);color=coordinates(query)
        if not data['x']:return np.ones((len(x),3))
        measured=np.array(data['x']);pred=np.array(data['pred']);obs=np.array(data['obs'])
        width=(self.xs[node+1]-self.xs[node-1])/2
        distance=((query[:,ch,None]-measured[None,:,ch])/width)**2
        distance+=np.sum((color[:,None,:]-coordinates(measured)[None,:,:])**2,axis=2)/(.06**2)
        weights=np.exp(-.5*np.minimum(distance,1500))
        out=np.ones((len(x),3))
        for k in range(3):
            active=np.abs(pred[:,k])>=.08
            if not active.any():continue
            a,b=pred[active,k],obs[active,k]
            w=weights[:,active]
            out[:,k]=(w@(a*b)+.01)/(w@(a*a)+.01)
        return out


def calibrate():
    entries={key:bytes.fromhex(value) for key,value in rt.read(OUT/'probe_records.json').items()}
    branches={};evaluations=[];mismatch=[]
    for branch in ('0.35','0.5','0.65','nearest_A'):
        original='0.5' if branch=='nearest_A' else branch
        points=rt.read(EVIDENCE/f'measure-{original}.json')['points']
        cells={f'{ch}/{node}':dict(x=[],pred=[],obs=[],frames=[]) for ch in range(3) for node in NODES}
        for row in points:
            if row['frame'] not in TRAIN or row['excluded']:continue
            ch='RGB'.index(row['channel'])
            for node in row['input_nodes']:
                if abs(row['node_contributions'][str(node)])<=.2:continue
                x=np.array([row['x_B']]);a=original_predict(entries['A'],x,2,round_output=False)
                b=original_predict(entries[row['label']],x,2,round_output=False)
                pred=((b-a)@YCC.T)[0]
                obs=row['nearest_observed_ycc'] if branch=='nearest_A' else row['observed_ycc']
                cell=cells[f'{ch}/{node}'];cell['x'].append(row['x_B']);cell['pred'].append(pred.tolist())
                cell['obs'].append(obs);cell['frames'].append(row['frame'])
                if branch=='0.5':mismatch.append((pred-np.array(row['predicted_ycc'])).tolist())
        branches[branch]=cells
    rt.dump(OUT/'calibration.json',dict(branches=branches,policy_sha256=rt.sha(OUT/'policy.json'),
        source_manifest_sha256=rt.sha(OUT/'source_manifest.json'),
        model='Conditional local output derivative ratios; no accepted continuous colour range'))
    nominal=Calibration()
    points=rt.read(EVIDENCE/'measure-0.5.json')['points']
    for role in ('calibration','heldout_repeat','extra_negative_diagnostic'):
        rows=[r for r in points if (r['frame'] in TRAIN if role=='calibration' else
            r['frame'] in ('R8051951','R8051952','R8051953') if role=='heldout_repeat' else
            r['frame'] in ('R8051940','R8051941','R8051942')) and not r['excluded'] and abs(r['q_nominal'])>.2]
        for color in ('gray','coloured'):
            use=[r for r in rows if r['gray']==(color=='gray')]
            old=[];new=[]
            for row in use:
                ch='RGB'.index(row['channel']);x=np.array([row['x_B']])
                a=original_predict(entries['A'],x,2,round_output=False);b=original_predict(entries[row['label']],x,2,round_output=False)
                pred=((b-a)@YCC.T)[0]
                node=max(row['input_nodes'],key=lambda k:abs(row['node_contributions'][str(k)]))
                gain=nominal.gains(x,ch,node)[0]
                old.append(pred-np.array(row['observed_ycc']));new.append(pred*gain-np.array(row['observed_ycc']))
            if use:evaluations.append(dict(role=role,colour=color,points=len(use),
                original_component_RMSE=np.sqrt(np.mean(np.array(old)**2,axis=0)),
                calibrated_component_RMSE=np.sqrt(np.mean(np.array(new)**2,axis=0))))
    rt.dump(OUT/'calibration_validation.json',dict(evaluations=evaluations,
        task_vs_field_nominal_component_RMSE=np.sqrt(np.mean(np.array(mismatch)**2,axis=0)),
        original_counterexamples=rt.read(EVIDENCE/'recipe_redo_handoff.json')['color_failures'],
        negative_validation_is_different_page_not_same_scene_repeat=True,
        full_colour_quantitative_acceptance=False,quantization_phase_identified=False))
    print('PROBE2 LOCAL CALIBRATION',evaluations,flush=True)


def curves(entry):
    q=np.array([list(entry[379:412]),list(entry[82:115]),list(entry[412:445])],float)
    if not entry[1]&4:q[:]=list(entry[82:115])
    return q


class LocalResponse:
    def __init__(self,anchor,gray=False):
        self.anchor=anchor;self.gray=gray;self.q=curves(anchor)
        self.xs=np.array([0,*struct.unpack_from('>31H',anchor,20),4095])
        self.engine,_=load();self.camera=rt.Camera(2)
        self.camera.row=rt.mm.MatrixRow.from_bytes(anchor[216:244]);self.camera.curve=rt.mm.Curve(self.xs,self.camera.curve.ys)
        self.calibrations={k:Calibration(k) for k in ('0.35','0.5','0.65','nearest_A')}
        self.columns=[(ch,node) for ch in range(3) for node in NODES]
        self.cache={}

    def problem(self,x,want,sw):
        return self.engine.Problem(self.camera,x,want,sw,dict(level=1,key='probe2_signed_local',
            other_parameters_frozen=True,quantitative_full_colour_accepted=False))

    def correction_jac(self,x,branch='0.5'):
        key=(id(x),branch)
        if key in self.cache and self.cache[key][0] is x:return self.cache[key][1]
        want=np.zeros_like(x) if self.gray else np.tile([1.,2.,3.],(len(x),1))
        problem=self.problem(x,want,np.ones(len(x)));theta=fit_one.seed(problem,self.anchor)
        problem.evaluate(theta);raw,jac=problem.raw_state[1:]
        indices=[problem.qstart+ch*33+node for ch,node in self.columns]
        jac=jac[:,:,indices]*((raw>0)&(raw<255))[:,:,None]
        comp=np.einsum('oc,ncp->nop',YCC,jac)
        for j,(ch,node) in enumerate(self.columns):comp[:,:,j]*=self.calibrations[branch].gains(x,ch,node)-1
        if self.gray:comp[:,1:]=0
        result=np.einsum('co,nop->ncp',RGB,comp)
        self.cache[key]=(x,result)
        return result

    def delta(self,entry):return np.array([curves(entry)[ch,node]-self.q[ch,node] for ch,node in self.columns])

    def predict(self,entry,x,branch='0.5',round_output=True):
        base=original_predict(entry,x,2,round_output=False)
        difference=self.delta(entry)
        result=np.clip(base+np.einsum('ncp,p->nc',self.correction_jac(x,branch),difference),0,255)
        return np.rint(result) if round_output else result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=('freeze','calibrate'));args=ap.parse_args()
    freeze() if args.stage=='freeze' else calibrate()
