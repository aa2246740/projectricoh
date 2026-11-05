"""Export private installable-record candidates and exact row-pool costs. No DAT writer."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import sys
import zlib

assert sys.flags.isolated
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;LOCAL=HERE/'local'
UNITS=('a12-50','a12-28','mount-a12')
KINDS=(0,1,2,3,0,1,1,1,0,1)
OFFSETS=(20,82,115,216,284,346,379,412,456,518)
WIDTHS=(62,33,96,56)
ROW_BYTES=(62,33,96,56,62,33,33,33,62,33)
CRCS=((20,62,8),(82,33,12),(115,96,16),(216,56,212),(284,62,272),(346,33,276),(379,66,280),(456,62,448),(518,33,452))


def read(p):return json.loads(Path(p).read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,d):
    p=LOCAL/p;assert p.resolve().is_relative_to(LOCAL)
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')


def layout(profile):
    d=read(LOCAL/'g157_layouts'/profile/'manifest.json')
    slots={u:{} for u in UNITS};looks={u:{} for u in UNITS}
    for r in d['records']:
        b=Path(r['record_file']).read_bytes();assert sha(b)==r['sha256']
        (slots[r['unit']] if r['kind']=='builtin' else looks[r['unit']])[r.get('slot') if r['kind']=='builtin' else r['name']]=b
    # Delivery 2 starts after the separately handed-off official Acros swap.
    # Preserve the original manifests for the delivery-1 Alchemy comparison.
    handoff=read(LOCAL/'acros_official_handoff.json')
    for row in handoff['profiles']:
        unit=row['unit'];b=Path(row['record_file']).read_bytes()
        assert sha(b)==row['record_sha256']
        assert row['base_dependencies'][profile]['base03_sha256']==sha(slots[unit][3])
        looks[unit]['Acros']=b
    return slots,looks


def count(slots,looks):
    base=[set() for _ in WIDTHS];extra=[set() for _ in WIDTHS]
    for rows in slots.values():
        for b in rows.values():
            for k,o,n in zip(KINDS,OFFSETS,ROW_BYTES):base[k].add(b[o:o+n])
    groups={};conflicts=[]
    for unit,rows in looks.items():
        for name,b in rows.items():
            if b[1]!=slots[unit][b[0]][1]:conflicts.append(dict(unit=unit,name=name,base=b[0],Look_flags=b[1],base_flags=slots[unit][b[0]][1]))
            groups.setdefault((name,b[:4]+b[8:]),b)
    for b in groups.values():
        for k,o,n in zip(KINDS,OFFSETS,ROW_BYTES):
            if b[o:o+n] not in base[k]:extra[k].add(b[o:o+n])
    align=lambda n:(n+3)&~3
    total=80+3*176+sum(align(len(p)*n) for p,n in zip(base,WIDTHS))
    total+=32+32*len(groups)+sum(align(len(p)*n) for p,n in zip(extra,WIDTHS))
    return dict(row_pool_bytes=total,physical_Look_descriptors=len(groups),logical_Looks_per_unit={u:len(x) for u,x in looks.items()},
        base_rows=list(map(len,base)),Look_extra_rows=list(map(len,extra)),flags_conflicts=conflicts,
        pool_limits_pass=all(len(p)<=n for p,n in zip(base,(144,240,48,48))) and all(len(p)<=127 for p in extra),
        descriptor_limit_pass=len(groups)<=48,layout_flags_pass=not conflicts,no_DAT_serialized=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--require-complete',action='store_true');a=p.parse_args()
    parser=ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src/gxr_studio/camdata/datcodec.py'
    spec=importlib.util.spec_from_file_location('film_export_static_parser',parser)
    D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
    catalog=read(LOCAL/'catalog.json');manifest=[];costs=[]
    layouts={k:layout(k) for k in ('release','test')}
    base_cost={k:count(*v) for k,v in layouts.items()}
    for film in catalog['films']:
        for unit in UNITS:
            path=LOCAL/'analysis'/f'{film["ordinal"]:02d}'/unit/'final.json'
            if not path.exists():
                assert not a.require_complete,'Missing '+str(path)
                continue
            data=read(path);selected=data['routes'][data['selected_route']]
            assert data['analysis_revision']=='r3_unweighted_primary_weighted_control'
            assert data['selected_route'] in ('scene_rgb_matrix','scene_structure')
            fit_receipt=read(Path(selected['record_file']).with_suffix('.json'))
            b=Path(selected['record_file']).read_bytes()
            assert sha(b)==selected['record_sha256'] and len(b)==552 and b[0]==6 and b[1]==7
            assert all(struct.unpack_from('>I',b,c)[0]==zlib.crc32(b[o:o+n])&0xffffffff for o,n,c in CRCS)
            assert all(D._valid_look_row(b[o:o+n],j,b[1]) for j,(o,n) in enumerate(zip(OFFSETS,ROW_BYTES)))
            assert selected['reference_exact_checked'] and selected['quality']['passes']
            dest=LOCAL/'full_library/unweighted_primary_v1'/film['id']/unit/'recipe.record552';dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert dest.read_bytes()==b,'Preserve exported records; use a versioned library folder'
            else:dest.write_bytes(b)
            increment={};look_increment={}
            look= data['routes'][data['selected_Look_route']]
            look_bytes=Path(look['record_file']).read_bytes()
            assert sha(look_bytes)==look['record_sha256'] and look_bytes[1]==1 and look['reference_exact_checked']
            for profile,(slots,looks) in layouts.items():
                updated={u:dict(rows) for u,rows in slots.items()};updated[unit][6]=b
                value=count(updated,looks)
                increment[profile]=value['row_pool_bytes']-base_cost[profile]['row_pool_bytes']
                assert value['layout_flags_pass'] and value['pool_limits_pass'] and value['descriptor_limit_pass']
                updated_looks={u:dict(rows) for u,rows in looks.items()}
                updated_looks[unit][film['name']]=look_bytes
                looked=count(slots,updated_looks)
                look_increment[profile]=looked['row_pool_bytes']-base_cost[profile]['row_pool_bytes']
                assert looked['layout_flags_pass'] and looked['pool_limits_pass'] and looked['descriptor_limit_pass']
            training=data.get('training_improved_vs_stock04',False)
            photos=data.get('primary_photo_improved_vs_baseline',False)
            robust=training and photos and data['quantization_passes']==128
            shape=data['tone'].get('gray_shape')
            gray_warning=bool(shape and shape['maximum_Lstar_drawdown'] is not None and
                shape['maximum_Lstar_drawdown']>shape['target_maximum_Lstar_drawdown']+.5)
            entry=dict(id=film['id'],name=film['name'],unit=unit,provider=film['provider'],
                source_sha256=film['scene']['sha256'],source_url=film['source_url'],author=film['author'],license=film['license'],
                print_step=film['print_step'],scene_exposure_gain=1.,
                record_file=str(dest),record_sha256=sha(b),record_bytes=552,flags=7,type26_control=0,
                canonical_owner_slot=6,relocatable_after_slot_dependency_and_metadata_validation=True,
                stock04_immutable=True,Look_anchor_collision_check_required=True,
                dependent_base=None,standalone_builtin_not_a_GXFX_Look=True,
                source_geometry='native C040',solver=selected['fit_phase'],all_starts_converged=selected['all_solver_starts_converged'],
                model_source_freeze_sha256=sha((LOCAL/'freeze.json').read_bytes()),
                input_calibration_sha256=fit_receipt['calibration_sha256'],
                primary_model_ISO=200,other_ISO_scope='Other-ISO photos replayed with the primary ISO200 model; transfer diagnostics only, not validation of each ISO response branch',
                matrix_half_scope='Primary C100 half fitted; secondary half retains template values for color, or physical zero chroma for BW. ISO100 curve mirroring is not a separate ISO100 color calibration.',
                target_reference='Scene XYZ, D65 Y0.18 atEV0, fixed gain1, default combined film and print/scan, sRGB output',
                true_layer_density_data_used=False,grain_or_spatial_effects_included=False,
                encoding_repair_applied='encoding_repair' in fit_receipt,
                application_mode='04 Standard',
                application_metadata_requirement='Match the frozen Standard selector, native parameter bytes, neutral WB offsets and calibrated input assumptions; record552 alone does not carry the entire application contract.',
                reference_exact_checked=True,quality_pass=True,
                integer_training_improved=training,primary_photo_improved=photos,
                quantization_passes=data['quantization_passes'],quantization_branches=128,
                robust_model_data_candidate=bool(robust),record_format_valid=True,
                gray_shape=shape,gray_shape_warning=gray_warning,
                default_shortlist_eligible=bool(robust and shape is not None and not gray_warning),
                install_admitted_by_current_engine=False,host_and_device_acceptance_pending=True,
                selected_route=data['selected_route'],scores=selected['scores'],
                primary_selection_rule=data['primary_selection_rule'],
                Look_classification_complete=data.get('placement_classification_complete',False),
                net_row_pool_bytes_if_replacing_only_slot06=increment,
                no_public_redistribution_of_embedded_Ricoh_rows=True,
                modifications='Default fixed-exposure film/print target fitted to native-C040 GXR curves, C100 and symmetric sectors; integer quantization. No grain or spatial effects.',
                analysis_file=str(path))
            manifest.append(entry)
            costs.append(dict(film=film['name'],unit=unit,record_bytes=552,
                Look_replace_same_named_or_add_net_bytes=look_increment,**increment))
    if a.require_complete:assert len(manifest)==60
    dump('full_library_manifest.json',dict(schema='gxr-full-slot-film-library/1',records=manifest,
        primary_selection='Unweighted training winner of black-box and structure routes; weighted control is not implicitly admitted',
        films=20,units=3,complete_records=len(manifest),expanded_bytes=sum(r['record_bytes'] for r in manifest),
        authorization_scope='Private local candidate library; not a DAT or a Studio installation',
        installation_contract='studio_installation_contract.json',no_network=True,no_camera_or_card=True))
    dump('record_costs.json',dict(baseline=base_cost,individual=costs,
        baseline_official_Acros_handoff_sha256=sha((LOCAL/'acros_official_handoff.json').read_bytes()),
        meaning='Full: one unit slot06 replaced. Look: one unit same named Look replaced, otherwise added. Compact used-row pool increments in frozen g157 layouts include old row removal, sharing, Look descriptors and alignment; exclude code/BSS and spare reserved capacity. The two operations have different ownership and are not a 552-byte storage comparison. Combined replacements and actual allocator reserves must be recounted.'))
    print('EXPORTED',len(manifest),'full-slot records;',sum(r['robust_model_data_candidate'] for r in manifest),'robust model data candidates')


if __name__=='__main__':main()
