"""Static byte-parser checks, with no numerical imports, fits or DAT serialization."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import struct
import sys

assert sys.flags.isolated
ROOT=Path(__file__).resolve().parents[2];LOCAL=Path(__file__).resolve().parent/'local'
UNITS=('a12-50','a12-28','mount-a12')
if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):
    p=LOCAL/p;assert p.resolve().is_relative_to(LOCAL)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')


def main():
    parser=ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src/gxr_studio/camdata/datcodec.py'
    spec=importlib.util.spec_from_file_location('film_contract_static_parser',parser)
    D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
    source=LOCAL/'frozen/firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT'
    raw=source.read_bytes();dat=D.parse(raw)
    shared=struct.unpack_from('>I',raw,192)[0];pools=[]
    for k in range(4):
        count,size,offset,crc=struct.unpack_from('>HHII',raw,shared+16+12*k)
        pools.append((count,size,shared+offset))
    control=D._parse_looks(dat,raw,pools)
    assert len(control)==18
    probes=[]
    for ui,unit in enumerate(UNITS):
        for slot in (3,5):
            modified=copy.deepcopy(dat)
            base=bytearray(modified.entry_of(ui,slot));base[1]=7;base[445:447]=bytes(2)
            # Create a fully valid independent-curve row, not an invalid flags-only dummy.
            base[379:412]=base[82:115];base[412:445]=base[82:115]
            assert all(D._valid_look_row(bytes(base[o:o+n]),j,7)
                for j,(o,n) in enumerate(zip(D.OFFSETS,D.ROW_BYTES)))
            modified.modules[ui].entries[modified.modules[ui].refs[slot-1]]=bytes(base)
            rejected=False;message=None
            try:D._parse_looks(modified,raw,pools)
            except D.DatError as error:
                message=str(error);rejected=message=='效果与单元基底不一致'
            assert rejected,(unit,slot,message)
            probes.append(dict(unit=unit,changed_base_slot=slot,new_full_flags=7,
                independent_rows_valid=True,actual_parser_rejected=True,reason=message,
                no_DAT_bytes_rebuilt_or_written=True))
    layouts=read(LOCAL/'g157_layouts/release/manifest.json')
    official={r['unit']:r for r in read(LOCAL/'acros_official_handoff.json')['profiles']}
    units=[]
    for unit in UNITS:
        lookrows=[r for r in layouts['records'] if r['unit']==unit and r['kind']=='look']
        dependencies={}
        for row in lookrows:
            if row['name']=='Acros':
                row=dict(row,record_file=official[unit]['record_file'],sha256=official[unit]['record_sha256'])
            b=Path(row['record_file']).read_bytes()
            dependencies.setdefault(str(b[0]),[]).append(dict(name=row['name'],flags=b[1],sha256=row['sha256']))
        anchors={int(s) for s in dependencies}
        unrestricted=[s for s in (1,2,3,5,6,7,8) if s not in anchors]
        assert anchors=={3,5} and unrestricted==[1,2,6,7,8]
        units.append(dict(unit=unit,existing_Look_dependencies=dependencies,
            freely_replaceable_with_flags7_slots=unrestricted,
            flags1_anchor_slots=sorted(anchors),current_free_L1_slots=5,
            seven_free_L1_slots_with_unchanged_locked_Looks_possible=False))
    cfile=ROOT/'firmware/engine_v69_g157/candidate/containers/product/fx_pool.c'
    copied=LOCAL/'contract_sources/fx_pool.c';copied.parent.mkdir(exist_ok=True);copied.write_bytes(cfile.read_bytes())
    related=[]
    for name in ('ui_v2_data.c','kv2/kv_data.c','kv2/kv_math.c','kv2/kv_math.h','src/firmware/engine/core/eng_core.c'):
        source=cfile.parent/name;dest=LOCAL/'contract_sources'/Path(name).name
        dest.write_bytes(source.read_bytes());related.append(dict(source=str(source),snapshot=str(dest),sha256=sha(dest)))
    rule=dict(schema='gxr-studio-film-installation-contract/2',
        compatible_with_current_GXFX=True,
        standalone_record=dict(bytes=552,allowed_full_flags=[1,7],
            shared=dict(flags=1,type26_control=2,curves=1),
            independent=dict(flags=7,type26_control=0,curves=3),
            immutable_stock04=True,installable_slots=[1,2,3,5,6,7,8],
            canonical_library_slot=6,canonical_slot_is_not_an_arbitrary_slot_install_permission=True,
            exact_unit_binding_required=True,native_C040_required=True,
            target_engine_format_and_link_layout_binding_required=True,
            row_CRCs_and_domains_required=True,all_10_row_references_rebuilt=True,
            matrix_Y_abs_max=2047,matrix_chroma_abs_max=1279,
            matrix_Y_row_sum_positive_for_active_knob_math=True,
            declared_control_ranges_must_be_checked_with_native_C_application=True,
            curves_monotonic=True,independent_R_B_last_code_min=128),
        application_mode=dict(required_S_mode='04 Standard',
            physical_zero_chroma_required_for_grayscale_not_native_BW_shortcut=True,
            metadata_selector_and_parameter_bytes_must_match_modeled_standard_chain=True,
            current_slot03_control_visibility_has_slot_specific_rules=True,
            native_grain_or_BW_capabilities_must_not_be_blindly_inherited_from_destination_slot=True,
            relocating_color_recipe_to03_requires_control_metadata_and_UI_policy_review=True),
        dependency=dict(Look_flags_must_equal_actual_referenced_base=True,
            Look_flags_must_also_equal_unit_slot05_for_this_product_layout=True,
            parser_checks_actual_base_while_slot05_alignment_is_additional_product_policy=True,
            matching_flags_is_necessary_not_sufficient=True,
            Look_also_uses_base_metadata_selector_parameter_bytes_WB_knob_dose_and_native_spatial_capabilities=True,
            base_application_metadata_fingerprint_must_be_preserved_or_revalidated=True,
            typical_color_Look_base=5,legacy_Acros_and_TriX_base=3,
            recheck_all_Looks_for_every_base_replacement=True,
            cross_unit_descriptor_mask_requires_all_covered_bases_compatible=True,
            atomic_base_Look_companion_update_or_reject=True,
            identical_three_curves_can_be_canonicalized_to_flags1_only_with_full_byte_and_forward_checks=True),
        shared_Look_encoding=dict(semantic_curve_parameters=33,
            flags1=dict(control=2,one_active_shared_curve=True),
            flags7=dict(control=0,R_G_B_must_reference_one_identical_shared_curve=True,
                additional_curve_pool_rows=0,additional_fitted_curve_parameters=0,
                shared_curve_endpoint_min=128),
            atomic_flags_rows_mask_content_CRC_update_required=True,
            forward_and_knob_equivalence_required=True,
            existing_parser_positive_probe='promote_shared_parser_probe.json'),
        descriptors=dict(GXFX_maximum_physical_Looks=48,unit_mask_min=1,unit_mask_max=7,
            Look_wire_name_bytes_min=1,Look_wire_name_bytes_max=12,
            Look_wire_name_encoding='ASCII printable; reject asterisk and backslash; pad remaining bytes with zero',
            display_name_is_not_a_wire_descriptor_name=True,
            current_visible_menu_rule='9 + per-unit Look count + saved user entry count <= 49',
            full_record_metadata_must_match_slot_and_content_identity=True),
        state=dict(rebuild_parameter_bank_and_descriptor_binding=True,
            invalidate_or_migrate_saved_tweaks_by_content_identity=True,
            old_GXTS_state_must_not_be_silently_rebound=True,
            recompute_row_pool_and_allocation_after_replacement=True,
            preserve_slot04_pin_and_recovery=True,
            acceptance_requires_parse_semantic_apply_restore_menu_and_power_cycle=True),
        user_edit_policy=dict(replaceable_full_slots=[1,2,3,5,6,7,8],
            slot04_is_immutable=True,locked_Look_names_and_color_payloads_are_release_owned=True,
            user_cannot_replace_or_refit_locked_Looks=True,
            approved_shared_format_transcoding_requires_release_payload_hash_and_forward_knob_equivalence=True,
            locked_payload_manifest='locked_shared_flags7_handoff.json'),
        product_constraint=dict(current_locked_anchors=[3,5],current_unrestricted_L1_count=5,
            single_anchor_after_proven_atomic_rebase_unrestricted_L1_count=6,
            target_unrestricted_L1_count=7,
            seven_requires_Look_anchor_ownership_independent_of_user_slots=False,
            seven_data_only_candidate='All full recipes flags7; shared Looks flags7 withR=G=B row alias; preserve base application metadata',
            independent_anchor_needed_if_base_application_metadata_can_change_freely=True,
            Studio_validator_alone_can_not_remove_engine_coupling=True,
            Studio_atomic_transcoding_and_metadata_contract_can_satisfy_flags_without_engine_expansion=True,
            no_Look_L1_engine_expansion_proposed=True),
        units=units,negative_probes=probes,source=dict(c_file=str(copied),sha256=sha(copied),
            Python_parser_sha256=sha(Path(D.__file__)),unchanged_control_Looks=18,related_C_sources=related,
            dependency_map_overlays_delivered_official_Acros=True),
        tested_layer='Existing Python parser and C source control flow; no engine build or device mutation')
    dump('studio_installation_contract.json',rule)
    print('CONTRACT PASS: 6 actual parser rejections; current anchors03/05 leave 5 unrestricted L1 slots per unit',flush=True)


if __name__=='__main__':main()
