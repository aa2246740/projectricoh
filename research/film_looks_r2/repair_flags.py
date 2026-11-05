"""Repair the C100 enable bit without changing fitted numbers; preserve and prove every byte."""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib

assert sys.flags.isolated
HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    processes=subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines()
    for line in processes:
        if 'film_looks_r2/' in line and any('/'+s+' ' in line or 'film_looks_r2/'+s+' ' in line
                for s in ('master.py','library.py','styles.py','analyze.py','analyze_style.py')):
            raise RuntimeError('Drain numerical queues before repair: '+line)
    sys.path.insert(0,str(HERE))
    import common as C
    import library as L
    np=C.np;local=C.LOCAL
    archive=local/'history'/args.tag
    assert not archive.exists(),'Use a new audit tag; never overwrite the first failure'
    plans={};hashes={}
    for root in ('targets','fits'):
        for path in sorted((local/root).glob('*/*/*.record552')):
            old=path.read_bytes()
            if old[1] not in (0,6):continue
            unit=path.parts[-3];ui=C.UNITS.index(unit)
            new=bytearray(old);new[1]|=1
            if old[1]==0:
                content=bytes(new[:2])+bytes(new[445:447])+bytes((1<<ui,))
                content+=b''.join(new[o:o+n] for o,n in zip(C.codec.OFFSETS,C.codec.ROW_BYTES))
                new[4:8]=struct.pack('>I',zlib.crc32(content)&0xffffffff)
            new=bytes(new)
            permitted={1,*range(4,8)} if old[1]==0 else {1}
            assert all(a==b or i in permitted for i,(a,b) in enumerate(zip(old,new)))
            assert old[20:]==new[20:],'All rows, controls and row CRCs must remain byte-identical'
            a,b=L.parameters_of(old),L.parameters_of(new)
            assert a.keys()==b.keys() and all(np.array_equal(a[k],b[k]) for k in a)
            checks=C.codec.record_checks(new)
            assert checks['row_crcs_valid'] and checks['existing_row_domain_checks_pass']
            if new[1]==1:assert C.codec.look_identity_valid(new,1<<ui)
            before,after=hashlib.sha256(old).hexdigest(),hashlib.sha256(new).hexdigest()
            hashes[before]=after;plans[path]=dict(old=old,new=new,before=before,after=after,unit=unit)
    assert plans,'No affected records found'
    points=0;maximum=0.;tested=set();fit_proofs=[]
    for path in sorted((local/'fits').glob('*/*/*.json')):
        doc=C.read(path);record=Path(doc['record_file'])
        if record not in plans:continue
        row=plans[record];assert doc['record_sha256']==row['before']
        if row['before'] not in tested:
            count=0;local_max=0.
            for group,source in doc['meta']['groups'].items():
                values=C.arrays(source)
                a=C.predict(row['old'],values['x'],C.UNITS.index(row['unit']))
                b=C.predict(row['new'],values['x'],C.UNITS.index(row['unit']))
                difference=float(np.max(abs(a-b)));assert difference==0.
                local_max=max(local_max,difference);count+=len(a)
            points+=count;maximum=max(maximum,local_max);tested.add(row['before'])
            fit_proofs.append(dict(original_sha256=row['before'],corrected_sha256=row['after'],
                                  unit=row['unit'],points=count,maximum_RGB_difference=local_max))
    def replace(value):
        if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
        if isinstance(value,list):return [replace(v) for v in value]
        return hashes.get(value,value) if isinstance(value,str) else value
    documents={}
    paths=[p for folder in ('targets','fits') for p in (local/folder).glob('*/*/*.json')]
    paths+=[local/'styles.json']
    for path in paths:
        old=C.read(path);new=replace(old)
        if new==old:continue
        if 'record_file' in new and Path(new['record_file']) in plans:
            current=Path(new['meta']['current_record'])
            original=current.read_bytes();template=plans[current]['new'] if current in plans else original
            selected=plans[Path(new['record_file'])]['new']
            new['payload_bytes_changed']=sum(a!=b for a,b in zip(template,selected))
            new['encoding_repair']=dict(reason='Enable fitted C100 and match flags1/7 base contract',
                original_record_sha256=old['record_sha256'],new_record_sha256=new['record_sha256'],
                unchanged_all_fitted_rows=True,unchanged_parameters_and_start_vectors=True,
                original_exact_solver_receipts_preserved=True,
                forward_bit0_invariance_verified_on_all_saved_groups=True)
        documents[path]=new
    receipt=dict(status='PROVED_NO_NUMERICAL_CHANGE',record_files=len(plans),unique_record_transforms=len(hashes),
        changed_json_documents=len(documents),points_compared=points,maximum_RGB_difference=maximum,
        fitted_parameters_start_vectors_rows_and_row_CRCS_unchanged=True,
        only_flags_and_shared_Look_content_identity_changed=True,
        corrected_flags=[1,7],proofs=fit_proofs,
        mathematical_exact_receipts_reused_because_the_parameterization_and_forward_function_are_unchanged=True,
        actual_C100_enable_semantics_source='contract_sources/kv_math.c',
        source_before='library.template inherited stock04 flags0; encode preserved C100 bit0',
        source_after='library.template explicitly enables bit0 before shared/full encoding',
        official_Acros_handoff_untouched=True,apply_requested=args.apply)
    if not args.apply:
        C.dump(local/'flags_repair_audit.json',receipt);print('AUDIT',receipt['record_files'],points,maximum);return
    archive.mkdir(parents=True)
    for path in (*plans,*documents):
        dest=archive/path.relative_to(local);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    snapshot=archive/'library-before-template-fix.py'
    snapshot.write_text((HERE/'library.py').read_text().replace('    b[1]|=1  # The fitted C100 must stay enabled through kv_apply_work.\n',''))
    C.dump(archive/'repair-plan.json',dict(records=[dict(path=str(p),archive=str(archive/p.relative_to(local)),
        original_sha256=v['before'],corrected_sha256=v['after']) for p,v in plans.items()],proof=receipt))
    for path,row in plans.items():path.write_bytes(row['new'])
    for path,doc in documents.items():C.dump(path,doc)
    # The master refreshes film results by signature; style results need an
    # explicit invalidation because the original scheduler uses existence.
    for index in (50,51,52):
        for path in (local/'style_analysis'/f'{index:02d}').glob('*.json'):
            dest=archive/path.relative_to(local);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,dest);path.unlink()
    C.dump(local/'flags_repair.json',dict(receipt,status='APPLIED_AND_PROVED',archive=str(archive)))
    print('FLAGS REPAIR',len(plans),'record files;',points,'RGB points unchanged; max',maximum,flush=True)


if __name__=='__main__':main()
