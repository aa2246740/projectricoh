"""Read the four generated fits through the existing GXFX builder, in memory."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,ROOT,HERE,BUILD_DATA,digest,dump,result_path
setup()
import hashlib
import importlib.util
import json
import struct
from dataclasses import replace
import numpy as np
from data import camera_model
from gxr_studio.camdata import datcodec

def main():
    model,dat,provenance=camera_model()
    raw=(ROOT/provenance['dat']).read_bytes()
    definitions=json.loads((BUILD_DATA/'local/effects.json').read_text())
    params=json.loads(result_path('lumix_fit_parameters.json').read_text())['parameters']
    assert len(definitions)==len(params)==4
    src=ROOT/'firmware/engine_v62_g153/candidate/containers/product/looks_data.py'
    spec=importlib.util.spec_from_file_location('vla_existing_builder',src)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.WORK=BUILD_DATA
    p=struct.unpack_from('>I',raw,192)[0]
    pools=[]
    buckets=[]
    for k,size in enumerate((62,33,96,56)):
        count=struct.unpack_from('>H',raw,p+16+12*k)[0]
        at=p+struct.unpack_from('>I',raw,p+20+12*k)[0]
        pools.append((count,size,at))
        buckets.append([raw[at+i*size:at+(i+1)*size] for i in range(count)])
    area=module.effect_area(buckets)
    parsed=datcodec._parse_looks(replace(dat,effect_area=area),raw,pools)
    assert len(parsed)==4
    rows=[]
    for rec,par,look in zip(definitions,params,parsed):
        original=bytes.fromhex(rec['entry_hex'])
        assert look.name==rec['name'] and look.base==rec['base'] and look.unit_mask==7
        assert look.entry[82:115].hex()==par['curve_hex']
        assert look.entry[115:211].hex()==par['colour_hex']
        assert look.entry[216:272].hex()==par['matrix_hex']
        for kind,off in zip(module.KINDS,module.OFFSETS):
            assert original[off:off+module.LENGTHS[kind]]==look.entry[off:off+module.LENGTHS[kind]]
        x=np.array([[8,8,8],[100,200,400],[409,500,256],[1200,2400,1800],[3500,3500,3500]])
        before=model.predict(original,x,bw_chroma='zero')
        after=model.predict(look.entry,x,bw_chroma='zero')
        err=float(np.max(abs(before-after)))
        assert err==0
        rows.append({'name':look.name,'all_ten_rows_identical':True,
                     'prediction_max_difference':err,'unit_mask':look.unit_mask,
                     'materialized_entry_sha256':hashlib.sha256(original).hexdigest()})
    merged=[{'name':r.name,'base':r.base,'mask':r.unit_mask,'entry_hex':r.entry.hex(),
             'license':'existing local research data'} for r in dat.looks]+definitions
    (BUILD_DATA/'effects_with_existing_14.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2)+'\n')
    hashes=''.join(digest(p)+'  '+p.relative_to(BUILD_DATA).as_posix()+'\n'
                   for p in sorted(BUILD_DATA.rglob('*')) if p.is_file() and p.name!='SHA256SUMS')
    (BUILD_DATA/'SHA256SUMS').write_text(hashes)
    dump('build_parameter_checks.json',{'status':'PASS','builder':str(src.relative_to(ROOT)),
        'builder_sha256':digest(src),'input':str((BUILD_DATA/'local/effects.json').relative_to(ROOT)),
        'input_sha256':digest(BUILD_DATA/'local/effects.json'),'effects':rows,
        'effect_area_bytes':len(area),'full_dat_written':False,'firmware_files_written':False,
        'four_only_note':'现有读取函数已验证这4个条目；当前构建器容量固定10，不能直接把14项清单当成已接入成品',
        'merged_input':str((BUILD_DATA/'effects_with_existing_14.json').relative_to(ROOT)),
        'merged_count':14,'current_user_cap':30,'user_cap_if_four_added':26})
    print('PASS four entries, ten rows each, zero prediction difference; no DAT created',flush=True)

if __name__=='__main__':
    main()
