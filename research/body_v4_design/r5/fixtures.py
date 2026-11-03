"""Independent reviewed positives, raw synthetic observations and prior cases."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(BASE/'r3'))
import diag_gate as gate


def encode(value):return gate.canonical(value)
def sha(value):return hashlib.sha256(encode(value)).hexdigest()


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def apply_patches(base,patches):
    doc=copy.deepcopy(base)
    for patch in patches:
        target=doc
        for key in patch['path'][:-1]:target=target[key]
        if patch['op']=='delete':del target[patch['path'][-1]]
        else:target[patch['path'][-1]]=copy.deepcopy(patch['value'])
    return doc


def reviewed_cases():
    base=json.loads((BASE/'r4/complete-records.json').read_text())
    report=json.loads((ROOT/'research/review_v4_design_r3/independent-records.json').read_text())
    result=[]
    for row in report['cases']:
        doc=apply_patches(base,row['patches'])
        assert sha(doc)==row['input_sha256'],row['name']
        result.append((row,doc))
    return result


def synthetic_observations(doc):
    """Fixture-only source model. The public reader never calls this factory.

    Sizes, file pattern and allocation cursor are literal fixture observations,
    not values copied from candidate summary fields.
    """
    osd=[];scans=[];bw=[]
    for record in doc['records']:
        if record['scene'] in gate.OSD_SCENES:
            for layer in record['layers']:
                raw_size=layer['width']*480//2
                for i in range(2):
                    osd.append(dict(scene=record['scene'],layer=layer['index'],sequence=i+1,
                                    source=layer['front'],segments=[dict(pattern='00',repeats=raw_size)]))
        if record['scene'] in ('JPEG_L','RAW_L'):
            categories={c['id']:c for c in record['categories']}
            rows=[]
            for index in range(99):
                if index in categories:
                    c=categories[index]
                    entries=list(c['addresses'])
                    rows.append(dict(index=index,count_raw=len(entries),stride_raw=c['stride_raw'],
                                     base_raw=c['base'],matrix_words=entries+[0]*(18-len(entries))))
                else:rows.append(dict(index=index,count_raw=0,stride_raw=0,base_raw=0,matrix_words=[0]*18))
            scans.append(dict(scene=record['scene'],pool_cursor=0x87f7bb30,rows=rows))
        if record['scene']=='BW':
            for kind in ('read','control','crc'):
                for i in range(32):
                    source=0x8733c000 if kind=='read' else 0x20710000
                    segments=[dict(pattern='00',repeats=262144)] if kind=='read' else [dict(pattern=bytes(range(256)).hex(),repeats=256)]
                    bw.append(dict(kind=kind,sequence=i+1,source=source,segments=segments))
    return dict(file_segments=[dict(pattern='00',repeats=20480)],
                bss_spans=[[0x2070d4cc,0x207204cc]],fixed_spans=[[0x1000,0x2dcc]],
                session_spans=[[0x3000,0x34cc]],osd_reads=osd,slot_scans=scans,bw_reads=bw)


def make_capture(doc,observations=None):
    return dict(version=5,kind='synthetic_fixture',record_sha256=sha(doc),
                observations=synthetic_observations(doc) if observations is None else observations)


def loaded_capture(doc,observations):
    raw=make_capture(doc,observations)
    return gate.load_capture(raw,sha(raw))


def complete_cases():
    profile=json.loads((BASE/'r4/reference-profile.json').read_text())
    positives=[];seen=set()
    for row,doc in reviewed_cases():
        if row['expected_complete'] and sha(doc) not in seen:
            positives.append(dict(name='review_'+row['name'],doc=doc,profile=profile,
                                  origin='review_v4_design_r3',original_sha256=row['input_sha256']))
            seen.add(sha(doc))
    assert len(positives)==47
    factory=load_module('r5_old_factory',BASE/'r4/record_cases.py')
    base=json.loads((BASE/'r4/complete-records.json').read_text())
    for unit in ('28mm','mount'):
        p=copy.deepcopy(profile);p['unit']=unit
        doc=factory.complete_records(p)
        def set_unit(value):
            if type(value) is dict:
                for key,item in value.items():
                    if key=='unit':value[key]=unit
                    else:set_unit(item)
            elif type(value) is list:
                for item in value:set_unit(item)
        set_unit(doc)
        positives.append(dict(name='prior_complete_'+unit,doc=doc,profile=p,origin='r4',original_sha256=sha(doc)))
    doc=copy.deepcopy(base)
    for record in doc['records']:
        if record['scene'] in ('JPEG_L','RAW_L'):record['categories'].reverse()
    positives.append(dict(name='prior_complete_both_category_orders',doc=doc,profile=profile,
                          origin='r4',original_sha256=sha(doc)))
    for scene in gate.OSD_SCENES:
        doc=copy.deepcopy(base)
        next(r for r in doc['records'] if r['scene']==scene)['layers'].reverse()
        positives.append(dict(name='p2_single_layer_order_'+scene,doc=doc,profile=profile,
                              origin='r5_p2',original_sha256=sha(doc)))
    assert len({sha(p['doc']) for p in positives})==len(positives)==54
    return positives


def write_positive_files():
    directory=HERE/'positive';directory.mkdir(exist_ok=True)
    rows=[]
    for index,case in enumerate(complete_cases()):
        stem=f'{index:02d}'
        capture=make_capture(case['doc'])
        for name,value in (('record',case['doc']),('profile',case['profile']),('capture',capture)):
            (directory/(stem+'-'+name+'.json')).write_bytes(encode(value))
        rows.append(dict(name=case['name'],stem=stem,origin=case['origin'],record_sha256=sha(case['doc']),
                         profile_sha256=sha(case['profile']),capture_sha256=sha(capture)))
    (HERE/'positive-index.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return rows


if __name__=='__main__':
    for row in write_positive_files():
        stem=row['stem'];directory=HERE/'positive'
        profile=gate.load_profile(gate.read_json(directory/(stem+'-profile.json')),row['profile_sha256'])
        capture=gate.load_capture(gate.read_json(directory/(stem+'-capture.json')),row['capture_sha256'])
        actual=gate.classify(gate.read_json(directory/(stem+'-record.json')),profile,capture)
        assert actual['records_complete'],(row['name'],actual)
    print(json.dumps(dict(positive_cases=54,original_review_cases=47,all_accepted=True)))
