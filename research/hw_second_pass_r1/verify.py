"""Replay packed integer fields independently of the optimizer and its state()."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from pipeline import *
import json

NATIVE=None


def native_codes():
    global NATIVE
    if NATIVE is None:
        blob=rt.inp(rt.s.FW/'jlaunch3').read_bytes()
        NATIVE=np.frombuffer(blob[0xE12F4:0xE12F4+48],np.uint8)[::2].astype(int)
    return NATIVE


def first_from_codes(m,d,doc):
    c=doc['packed'];features=doc['features']
    pre=np.column_stack([np.interp(np.clip(d['x'][:,i],0,4095),c['curve_x'],c['curve_y'][i]) for i in range(3)])
    if 'rlut' in features:
        curves=np.array(c['rlut_outputs_u12'])*255/4095
        nodes=np.array(c.get('rlut_inputs_u12',np.linspace(0,4095,33)))*255/4095
        pre=np.column_stack([np.interp(pre[:,i],nodes,curves[i]) for i in range(3)])
    off=np.array(c['output_input_offset_delta'])
    z=(pre+V@off[3:])@(np.array(c['matrix'])/1024).T+np.array(d['current']['tail'])[:3]+off[:3]
    ci=z[:,1]-128+1j*(z[:,2]-128)
    native=native_codes()
    original=m.table.nodes.copy()
    nodes=original+(np.array(c['c040_codes'])-native)*360/256
    m.table.nodes=nodes
    try:
        ratio=m.effective(np.array(c['A']),np.array(c['B']))/m.stock_effective
        co=m.table.forward(ci,ratio)[0]
    finally:m.table.nodes=original
    if 'four' in features:
        W=f.weights_cyclic(m.mm.hue_deg(ci),nodes)[:,[0,11,17,23]]
        v=np.array(c['c080_extra_cd'])
        co+=1j/32*((W@v[:4])*ci.real+(W@v[4:])*ci.imag)
    for key in ('gain_Y','gain_C','gain_C2'):
        if key in features:
            axis=z[:,0]/255 if key=='gain_Y' else abs(ci)/(128*np.sqrt(2))
            if key=='gain_C2':axis=axis**2
            co*=np.interp(axis,np.r_[0,c['c120_nodes_u14'],16383]/16383,np.array(c['c120_gain_u8'])/64)
    tint=np.array(c['c004_signed_magnitude_delta'])
    if 'tint_add' in features:co+=tint[0]+1j*tint[1]
    if 'tint_Y' in features:co+=(tint[0]+1j*tint[1])*np.clip(z[:,0]/255,0,1)
    return np.clip(m.mm.rgb_from_ycc(z[:,0],co)+d['bias'],0,255)


def body_from_codes(m,x,c):
    stages=('rlut','mcm','tone') if c['order']=='a' else ('tone','rlut','mcm')
    original=m.table.nodes.copy()
    native=native_codes()
    out=x.copy()
    for stage in stages:
        if stage!='mcm':
            if not c['curves_enabled']:continue
            nodes=np.array(c[stage+'_x_u12'])*255/4095
            values=np.array(c['rlut_y_u12'])*255/4095 if stage=='rlut' else np.array(c['tone_y_u8'])
            out=np.column_stack([np.interp(out[:,i],nodes,values[i]) for i in range(3)])
            continue
        if not c['mcm_enabled']:continue
        off=np.array(c['offsets_8bit_units'])*c.get('offset_unit',1.)
        z=(out+V@off[3:])@(np.array(c['matrix_q10'])/1024).T+[0,128,128]+off[:3]
        ci=z[:,1]-128+1j*(z[:,2]-128)
        nodes=original+(np.array(c['c040_codes'])-native)*360/256
        m.table.nodes=nodes
        try:W=m.table.kernel_weights(m.mm.hue_deg(ci),abs(ci))
        finally:m.table.nodes=original
        zsec=(np.array(c['A'])-1j*np.array(c['B']))/32
        effective=abs(zsec)*np.exp(1j*m.table.k*np.angle(zsec))
        co=ci*(1+(W*m.table.gain)@(effective-1))
        P=f.weights_cyclic(m.mm.hue_deg(ci),nodes)[:,[0,11,17,23]]
        v=np.array(c['c080_cd'])
        co+=1j/32*((P@v[:4])*ci.real+(P@v[4:])*ci.imag)
        if c['c120_axis']:
            axis=z[:,0]/255 if c['c120_axis']=='Y' else abs(ci)/c.get('c120_radius',128*np.sqrt(2))
            co*=np.interp(axis,np.r_[0,c['c120_nodes_u14'],16383]/16383,np.array(c['c120_gains_u8'])/64)
        tint=np.array(c['c004'])*c.get('tint_unit',1.);co+=tint[0]+1j*tint[1]
        out=m.mm.rgb_from_ycc(z[:,0],co)
    return np.clip(out,0,255)


def fields_valid(c):
    def integer_range(value,low,high):
        a=np.asarray(value);return bool(np.all(a==np.rint(a)) and np.min(a)>=low and np.max(a)<=high)
    nodes=np.array(c['c040_codes'])
    return dict(matrix=integer_range(c['matrix_q10'],-2047,2047),
       offsets=integer_range(c['offsets_8bit_units'],-2047,2047),
       A=integer_range(c['A'],-127,127),B=integer_range(c['B'],-127,127),
       four=integer_range(c['c080_cd'],-127,127),tint=integer_range(c['c004'],-127,127),
       rlut=integer_range(c['rlut_y_u12'],0,4095),tone=integer_range(c['tone_y_u8'],0,255),
       rlut_input=integer_range(c['rlut_x_u12'],0,4095),tone_input=integer_range(c['tone_x_u12'],0,4095),
       node_order=bool(np.min(np.diff(np.r_[nodes,nodes[0]+256]))>=2),
       gain=integer_range(c['c120_gains_u8'],0,255),gain_nodes=integer_range(c['c120_nodes_u14'],0,16383),
       gain_node_order=bool(np.min(np.diff(np.r_[0,c['c120_nodes_u14'],16383]))>0),
       curves_monotone=bool(np.min(np.diff(c['rlut_y_u12'],axis=1))>=0 and np.min(np.diff(c['tone_y_u8'],axis=1))>=0))


def independent_lut(table,x,strict=False):
    """Scalar simplex replay, separate from lut_control's vector implementation."""
    xx=np.floor(np.clip(x,0,255)+.5) if strict else np.clip(x,0,255)
    n=table.shape[0];result=[]
    for rgb in xx:
        position=np.floor(rgb*(n-1)/255*256+.5)/256
        index=np.minimum(np.floor(position).astype(int),n-2)
        frac=position-index
        order=sorted(range(3),key=lambda k:-frac[k])
        a,b,c=order
        vertices=[index.copy()]
        q=index.copy();q[a]+=1;vertices.append(q.copy())
        q[b]+=1;vertices.append(q.copy());vertices.append(index+1)
        weights=np.rint(np.array([1-frac[a],frac[a]-frac[b],frac[b]-frac[c],frac[c]])*256).astype(int)
        numerator=sum(table[tuple(v)].astype(np.int64)*w for v,w in zip(vertices,weights))
        value=numerator/65536
        result.append(np.floor(value+.5) if strict else value)
    return np.array(result)


def lut_checks(m,data):
    from scipy.spatial.distance import cdist
    checked=0;max_rgb=0.;tables=0;seen=set()
    for path in sorted((rt.LOCAL/'lut').glob('*/*/*.json')):
        doc=rt.read(path);a=rt.arrays(path.with_suffix('.npz'))
        key=(doc['slot'],doc['source'],doc['fold'])
        assert key not in seen;seen.add(key)
        d=data[doc['slot'],doc['fold']]
        x=a['input'];target=a['target'];train=a['train'];held=a['held']
        assert np.array_equal(train,d['train']) and np.array_equal(target,d['target'])
        assert not doc['heldout_used_for_choice']
        if doc['fold']!='full':assert not np.any(train&held)
        reference=d['first_published'] if doc['source']=='current' else m.predict('04',d['x'])
        assert np.max(abs(reference-x))<1e-8
        xyz=m.fs.lab_to_xyz(target[train],m.fs.D65)
        y=np.clip(m.fs.linear_to_srgb(xyz@np.linalg.inv(m.fs.M709).T)*255,0,255)
        width,ridge=doc['choice']['width'],doc['choice']['ridge']
        assert width in (24.,48.,96.) and ridge in (.01,.1,1.)
        K=np.exp(-cdist(x[train],x[train],'sqeuclidean')/(2*width**2))
        alpha=np.linalg.solve(K+ridge*np.eye(train.sum()),y-x[train])
        for n in (17,33):
            table=a[f'nodes_{n}_q8_8'];assert table.shape==(n,n,n,3) and table.dtype==np.uint16
            nodes=np.stack(np.meshgrid(*([np.linspace(0,255,n)]*3),indexing='ij'),axis=-1).reshape(-1,3)
            rebuilt=np.empty_like(nodes)
            for start in range(0,len(nodes),2048):
                q=nodes[start:start+2048]
                transformed=q+np.exp(-cdist(q,x[train],'sqeuclidean')/(2*width**2))@alpha
                rebuilt[start:start+2048]=np.floor(np.clip(transformed,0,255)*256+.5)
            assert np.array_equal(rebuilt.reshape(table.shape).astype(np.uint16),table),(str(path),n)
            tables+=1
            for strict in (False,True):
                key=f'{n}_'+('u8means' if strict else 'main')
                pred=independent_lut(table,x,strict)
                diff=float(np.max(abs(pred-a['prediction_'+key])))
                assert diff<1e-8,(str(path),key,diff)
                error=m.fs.delta_e00(m.fs.lab_from_codes(pred),target)
                assert np.max(abs(error-a['error_'+key]))<1e-8
                stored=next(r for r in doc['rows'] if r['n']==n and r['strict_u8means']==strict)['score']
                assert abs(old.score(error[held],d['baseline'][held])['similarity']-stored['similarity'])<1e-10
                max_rgb=max(max_rgb,diff);checked+=1
    expected={(slot,source,fold) for slot in SLOTS for source in ('current','04model') for fold in FOLDS}
    assert seen==expected,(expected-seen,seen-expected)
    return dict(fold_sources=checked//4,tables=tables,prediction_variants=checked,max_rgb=max_rgb,
                all_nodes_rebuilt_from_training_only=True)


def published_rows(m):
    parser=rt.module('second_pass_published_table_parser','firmware/stage2l_switch/tools/deep_sources.py')
    rt.inp(parser.HERE/'tools/make_recipes.py')
    _,surface=parser.surface_bank()
    paths={True:'research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL',
           False:'research/gr4_nega_returns_r1/local/candidate/DEEPTBL_50mm_gr4_posi_nega_r1.DAT'}
    banks={k:parser.parse(rt.inp(path).read_bytes(),surface) for k,path in paths.items()}
    rows=[]
    for slot in SLOTS:
        current=rt.read(rt.LOCAL/f'data/{slot}/full.json')['current']
        entry=next(e for e in banks[slot in ('05','06')] if e['slot']==int(slot))
        matrix=m.mm.MatrixRow.from_bytes(entry['written'][3][:28])
        assert np.array_equal(matrix.coef,current['matrix']) and np.array_equal(matrix.tail,current['tail'])
        ab=np.array([m.fs.decode_word(entry['written'][2][i*4:i*4+4]) for i in range(24)])
        assert np.array_equal(ab[:,0],current['A']) and np.array_equal(ab[:,1],current['B'])
        inputs,outputs=parser.unpack_tone(*entry['written'][:2])
        nodes=np.r_[0,inputs,4095] if len(inputs)==31 else np.array(inputs)
        assert np.array_equal(nodes,current['curve_x'])
        curves=[outputs]*3
        if slot=='06':curves=[list(entry['written'][6][:33]),outputs,list(entry['written'][6][33:])]
        assert np.array_equal(curves,current['curve_y'])
        rows.append(dict(slot=slot,published_bytes_match_full_start=True,table_entries_validated=len(banks[slot in ('05','06')])))
    return rows


def main():
    m=rt.model();published=published_rows(m);data={};rows=[];seen=set();max_rgb=max_error=max_score=0.
    for path in sorted((rt.LOCAL/'fits').glob('*/*/*.json')):
        doc=rt.read(path);slot,fold=doc['slot'],doc['fold'];key=(slot,fold)
        fit_key=(slot,doc['route'],fold)
        assert fit_key not in seen;seen.add(fit_key)
        if key not in data:
            a=rt.arrays(rt.LOCAL/f'data/{slot}/{fold}.npz')
            meta=rt.read(rt.LOCAL/f'data/{slot}/{fold}.json')
            a['current']=meta['current'];data[key]=a
        d=data[key];a=rt.arrays(path.with_suffix('.npz'))
        first=first_from_codes(m,d,doc['packed']['first'])
        pred=body_from_codes(m,first,doc['packed']['body'])
        error=m.fs.delta_e00(m.fs.lab_from_codes(pred),d['target'])
        held=a['held'];sc=old.score(error[held],d['baseline'][held])
        rgb_diff=float(np.max(abs(pred-a['prediction_integer'])))
        error_diff=float(np.max(abs(error-a['error_integer'])))
        score_diff=abs(sc['similarity']-doc['scores']['integer']['similarity'])
        checks=fields_valid(doc['packed']['body'])
        first_codes=doc['packed']['first']['packed']
        def within(value,lower,upper):
            value=np.asarray(value);return bool(np.all(value==np.rint(value)) and np.min(value)>=lower and np.max(value)<=upper)
        assert within(first_codes['matrix'],-2047,2047)
        assert within(first_codes['A'],-127,127) and within(first_codes['B'],-127,127)
        assert within(first_codes['curve_y'],0,255) and np.min(np.diff(first_codes['curve_y'],axis=1))>=0
        assert within(first_codes['curve_x'],0,4095) and np.min(np.diff(first_codes['curve_x']))>0
        assert within(first_codes['output_input_offset_delta'],-2047,2047)
        assert within(first_codes['c004_signed_magnitude_delta'],-127,127)
        assert within(first_codes['c080_extra_cd'],-127,127)
        assert within(first_codes['c120_nodes_u14'],0,16383) and np.min(np.diff(np.r_[0,first_codes['c120_nodes_u14'],16383]))>0
        assert within(first_codes['c120_gain_u8'],0,255)
        codes=np.asarray(first_codes['c040_codes'])
        assert within(codes,0,255) and np.min(np.diff(np.r_[codes,codes[0]+256]))>=2
        assert rgb_diff<1e-8 and error_diff<1e-8 and score_diff<1e-10,(str(path),rgb_diff,error_diff)
        assert all(checks.values()),(str(path),checks)
        assert not doc['integer_refinement']['heldout_used']
        assert doc['integer_refinement']['final_objective']<=doc['integer_refinement']['start_objective']+1e-7
        assert np.array_equal(a['train'],d['train'])
        if fold!='full':assert not np.any(a['train']&a['held'])
        assert doc['model_sha256']==rt.sha(rt.HERE/'pipeline.py')
        max_rgb=max(max_rgb,rgb_diff);max_error=max(max_error,error_diff);max_score=max(max_score,score_diff)
        rows.append(dict(slot=slot,fold=fold,route=doc['route'],max_rgb=rgb_diff,max_error=error_diff,all_fields_valid=True,
                         converged=doc['solver']['success']))
    expected={(slot,f'{mode}_{order}_{tier}',fold) for slot in SLOTS for mode in ('fixed','joint') for order in ('a','b') for tier in TIERS for fold in FOLDS}
    assert seen==expected,(expected-seen,seen-expected)
    pre=rt.read(rt.LOCAL/'verification/preflight.json')
    lut=lut_checks(m,data)
    assert lut['fold_sources']==80 and lut['tables']==160 and lut['prediction_variants']==320
    result=dict(fits=len(rows),expected_fits=800,all_expected_fits_present=seen==expected,
      converged=sum(r['converged'] for r in rows),nonconverged=sum(not r['converged'] for r in rows),
      independent_packed_max_rgb=max_rgb,independent_packed_max_de00=max_error,independent_score_max_error=max_score,
      all_fields_valid=True,jacobian_max_relative=max(r['relative_error'] for r in pre['jacobians']),rows=rows,
      camera_access=False,firmware_build=False,prediction_label='电脑预测',lut=lut,published_rows=published)
    rt.dump('verification/final.json',result);rt.finish('verification_final')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)


if __name__=='__main__':main()
