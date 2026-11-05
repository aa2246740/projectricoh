"""Re-read Acros records, verify the literal chain, and account for planned g157 pools."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from common import np,rt,ROOT,LOCAL,UNITS,read,dump,sha,predict,arrays
import hashlib
import itertools
import struct
import zlib


def layout(profile):
    source=ROOT/'research/model_c040_r1/local/layouts'/profile/'manifest.json'
    data=read(source)
    dest=LOCAL/'g157_layouts'/profile
    dest.mkdir(parents=True,exist_ok=True)
    rows=[]
    for row in data['records']:
        p=Path(row['record_file']);b=p.read_bytes();assert sha(p)==row['sha256']
        q=dest/p.name
        if q.exists():assert q.read_bytes()==b
        else:q.write_bytes(b)
        rows.append(dict(row,record_file=str(q),source_record_file=str(p)))
    result=dict(data,records=rows,source_manifest=str(source),source_sha256=sha(source))
    dump(dest/'manifest.json',result)
    return result


def pools(layout,replacements):
    from gxr_studio.camdata.datcodec import OFFSETS,ROW_BYTES
    kinds=(0,1,2,3,0,1,1,1,0,1);sizes=(62,33,96,56)
    base=[set() for _ in sizes];extra=[set() for _ in sizes]
    looks={}
    for r in layout['records']:
        b=Path(r['record_file']).read_bytes()
        if r['kind']=='builtin':
            for k,o,n in zip(kinds,OFFSETS,ROW_BYTES):base[k].add(b[o:o+n])
        else:
            b=replacements.get((r['unit'],r['name']),b)
            semantic=b[:4]+b[8:]
            looks.setdefault((r['name'],semantic),b)
    for b in looks.values():
        for k,o,n in zip(kinds,OFFSETS,ROW_BYTES):
            row=b[o:o+n]
            if row not in base[k]:extra[k].add(row)
    align=lambda n:(n+3)&~3
    size=80+3*176+sum(align(len(p)*s) for p,s in zip(base,sizes))
    size+=32+32*len(looks)+sum(align(len(p)*s) for p,s in zip(extra,sizes))
    return dict(table_bytes=size,descriptors=len(looks),base_rows=list(map(len,base)),
        extra_rows=list(map(len,extra)),no_DAT_serialized=True)


def main():
    literal=C.module('film_r2_literal',C.frozen('research/bluecyan_r1/verify.py')).predict_literal
    fit=C.load_fit();assessment=C.load_assess()
    layouts={p:layout(p) for p in ('release','test')}
    records={};handoff=[];verification=[]
    for ui,unit in enumerate(UNITS):
        meta=read(LOCAL/'targets'/unit/'14/profile.json')
        exact=read(LOCAL/'fits'/unit/'14/exact.json')
        result=read(LOCAL/'assessment'/unit/'14.json')
        b=Path(exact['record_file']).read_bytes()
        assert sha(exact['record_file'])==exact['record_sha256']==result['record_sha256']
        checks=C.codec.record_checks(b)
        assert checks['row_crcs_valid'] and checks['existing_row_domain_checks_pass']
        assert C.codec.look_identity_valid(b,1<<ui)
        parameters=exact['parameters']
        if parameters is None:
            iterate=read(LOCAL/'fits'/unit/'14/iterate.json')
            assert iterate['record_sha256']==exact['record_sha256'] and iterate['parameters'] is not None
            parameters=iterate['parameters']
        rebuilt=C.codec.encode(Path(meta['current_record']).read_bytes(),parameters,
            level=0,gray=True,look_unit_mask=1<<ui)
        assert rebuilt==b
        assert b[0]==3 and b[1]==1 and struct.unpack_from('>H',b,445)[0]==2
        assert not rt.mm.MatrixRow.from_bytes(b[216:244]).coef[1:].any()
        assert not rt.mm.MatrixRow.from_bytes(b[244:272]).coef[1:].any()
        bank={key:arrays(path) for key,path in meta['groups'].items()}
        after={key:predict(b,v['x'],ui) for key,v in bank.items()}
        maxdiff=0.;points=0;scores={}
        ordinary=bytearray(b);ordinary[0]=1
        for key,v in bank.items():
            assert np.array_equal(v['x'],C.input_codes(v['raw_codes'],unit))
            ref=literal(C.model(ui),bytes(ordinary),v['x'])
            difference=float(abs(ref-after[key]).max());maxdiff=max(maxdiff,difference)
            assert difference<1e-8 and np.array_equal(np.rint(ref),np.rint(after[key]))
            score=rt.score(v['base_new'],np.rint(ref),v['want'])
            saved=result['scores'][key]['candidate_native_model']
            assert abs(score['de00']['median']-saved['de00']['median'])<1e-10
            scores[key]=score;points+=len(ref)
        gate=assessment.Gate(meta,bank,None)
        comparisons={}
        required={}
        for profile,data in layouts.items():
            rows=[r for r in data['records'] if r['unit']==unit]
            base03=next(r for r in rows if r['kind']=='builtin' and r['slot']==3)
            base05=next(r for r in rows if r['kind']=='builtin' and r['slot']==5)
            tri=next(r for r in rows if r['kind']=='look' and r['name']=='Tri-X 400')
            assert Path(base03['record_file']).read_bytes()[1]==b[1]
            assert Path(base05['record_file']).read_bytes()[1]==b[1]
            assert Path(tri['record_file']).read_bytes()[1]==b[1]
            required[profile]=dict(actual_referenced_base_slot=3,required_flags=1,
                base03_sha256=base03['sha256'],base03_file=base03['record_file'],
                slot05_flags=1,slot05_sha256=base05['sha256'],
                compatible_TriX_sha256=tri['sha256'],compatible_TriX_file=tri['record_file'],
                rule='All or keep the existing compatible HC BW/Tri-X pair. Never use a flags=7 slot03 with this flags=1 Acros.')
            oldrow=next(r for r in rows if r['kind']=='look' and r['name']=='Acros')
            old=Path(oldrow['record_file']).read_bytes()
            before={k:predict(old,v['x'],ui) for k,v in bank.items()}
            nominal=gate.assess({k:np.rint(v) for k,v in before.items()},
                                {k:np.rint(v) for k,v in after.items()},True)
            quant=[]
            for order in ('YCbCr8_then_RGB8','RGB8_then_YCbCr8'):
                for phase in itertools.product((0.,.25,.5,.75),repeat=3):
                    a={k:C.ba.phase_output(v,np.asarray(phase),order,rt.mm) for k,v in before.items() if k in gate.rows}
                    c={k:C.ba.phase_output(v,np.asarray(phase),order,rt.mm) for k,v in after.items() if k in gate.rows}
                    q=gate.assess(a,c)
                    quant.append(dict(order=order,phase=phase,passes=q['passes'],failures=q['failures']))
            assert nominal['passes'] and all(q['passes'] for q in quant),(unit,profile,nominal['failures'])
            primary=bank['photo_iso200']
            oldscore=rt.score(primary['base_new'],np.rint(before['photo_iso200']),primary['want'])
            newscore=scores['photo_iso200']
            assert newscore['de00']['median']<oldscore['de00']['median']
            assert newscore['de00']['p95']<=oldscore['de00']['p95']+.25
            train=bank['train'];err=rt.delta_e00(rt.lab_from_codes(np.rint(before['train'])),rt.lab_from_codes(train['want']))
            assert exact['objective']<float(np.average(err*err,weights=train['sw']))
            comparisons[profile]=dict(current_record_sha256=oldrow['sha256'],current=oldscore,
                official=scores['photo_iso200'],nominal=nominal,quantization_passes=128,
                quantization_branches=128,quantization=quant)
        records[unit,'Acros']=b
        dest=LOCAL/'acros_official'/unit/'Acros.record552';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
        v=dict(unit=unit,record_sha256=sha(dest),literal_maximum_RGB_difference=maxdiff,
            points_replayed=points,all_552_bytes_rebuilt=True,checks=checks,
            exact_attempts=len(exact['attempts']),exact_starts=len(exact['starts']),
            exact_all_starts_converged=all(r['receipt']['success'] for r in exact['attempts']),
            final_scores_recomputed=True,source_iso200_photo_count=result['nominal']['groups']['photo_iso200']['photos'])
        verification.append(v)
        handoff.append(dict(unit=unit,name='Acros',display_name='Acros official',record_file=str(dest),
            record_sha256=sha(dest),record_bytes=552,flags=b[1],look_base_slot=b[0],look_unit_mask=1<<ui,
            slot05_flags_equal=True,base_dependencies=required,
            reference_exact_checked=True,reference_exact_all_declared_starts=True,
            quality_passes=exact['quality']['passes'],quantization_passes=128,quantization_branches=128,
            scores=scores,comparisons=comparisons,admitted_for_g157_data_swap=True,
            permission='Local private research artifact. Do not redistribute the manufacturer LUT or this derived record without an applicable permission.',
            actual_candidate_camera_exposures=0))
    capacity={}
    for profile,data in layouts.items():
        before=pools(data,{});after=pools(data,records)
        individual={}
        for unit in UNITS:
            one=pools(data,{(unit,'Acros'):records[unit,'Acros']})
            individual[unit]=one['table_bytes']-before['table_bytes']
        capacity[profile]=dict(before=before,after=after,
            net_bytes=after['table_bytes']-before['table_bytes'],individual_net_bytes=individual,
            accounting_scope='Replace Acros in frozen model_c040 planned g157 layout; row removal, sharing, descriptor coalescing and alignment included. Other g157 code/BSS is excluded.')
        for row in handoff:row.setdefault('net_bytes_if_replaced_alone',{})[profile]=individual[row['unit']]
    doc=dict(schema='g157-acros-official-handoff/1',created_utc=C.utc(),target=C.FREEZE['sources'][0],
        target_input='Scene XYZ -> F-Gamut/Rec2020 -> F-Log2 -> official ACROS 65^3; direct BT709 output codes',
        c040_geometry='native',profiles=handoff,capacity=capacity,
        required_g157_layout='model_c040 release/test design with compatible flags=1 HC BW/Tri-X pair',
        original_g156_release_50mm_is_incompatible=True,
        invalid_without_companion_base_flags=True,no_engine_changes=True,no_DAT_built=True,
        no_camera_or_card_acceptance=True)
    dump('acros_official_handoff.json',doc)
    dump('acros_verification.json',dict(status='PASS',records=verification,total_points=sum(v['points_replayed'] for v in verification),
        literal_maximum_RGB_difference=max(v['literal_maximum_RGB_difference'] for v in verification),
        no_DAT_built=True,no_camera_exposures=True,capacity=capacity))
    for row in handoff:
        s=row['scores']['photo_iso200'];print(row['unit'],row['record_sha256'],s['de00']['median'],s['similarity_percent'],row['net_bytes_if_replaced_alone'],flush=True)
    print('COMBINED_NET', {k:r['net_bytes'] for k,r in capacity.items()},flush=True)


if __name__=='__main__':main()
