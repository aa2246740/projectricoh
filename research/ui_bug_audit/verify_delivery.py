#!/usr/bin/env python3
"""Verify final research artifacts and copied photos. Never access the SD card."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CAP = ROOT/'captures/a12-50/2026-10-16/macbook-screen-chart'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024): h.update(block)
    return h.hexdigest()


def load(path):
    def reject(value): raise ValueError('Non-finite JSON constant: '+value)
    return json.loads(path.read_text(),parse_constant=reject)


def main():
    required=[OUT/'REPORT.md',OUT/'MACBOOK_CAPTURES_REPORT.md',OUT/'iso_trace.md',OUT/'iso_trace.json',
              OUT/'capture_verification.json',OUT/'firmware_audit.json',OUT/'fix_verification.json',
              OUT/'dispatch_replay.json',CAP/'measurements.json',CAP/'copy_manifest.json']
    assert all(p.is_file() for p in required),[str(p) for p in required if not p.is_file()]
    copy=load(CAP/'copy_manifest.json')
    expected={f'R805{n}.{ext}' for n in range(1138,1144) for ext in ('DNG','JPG')}
    assert copy['count'] == 12 and {r['name'] for r in copy['files']} == expected
    assert copy['source_mutations'] == [] and copy['eject_called'] is False
    for row in copy['files']:
        p=Path(row['copy'])
        assert p.resolve().parent == CAP.resolve()
        assert row['source_sha256_before_copy'] == row['source_sha256_after_copy'] == row['copy_sha256'] == digest(p)
        assert p.stat().st_size == row['bytes']
    measurement=load(CAP/'measurements.json')
    assert len(measurement['captures']) == 6
    pages={c['shot']:c['page'] for c in measurement['captures']}
    assert pages == {f'R805{n}':p for n,p in [(1138,'T1'),(1139,'T1'),(1140,'T1'),(1141,'T2'),(1142,'T3'),(1143,'T4')]}
    patch_count=0
    for c in measurement['captures']:
        assert c['raw']['stored_wh'] == [4304,2862]
        assert c['raw']['crop_xywh'] == [8,7,4288,2848]
        assert c['raw']['bits'] == 12 and c['raw']['cropped_CFA'] == 'GBRG'
        assert len(c['patches']) == 48
        assert c['metadata_dng']['iso'] == [800]
        assert c['metadata_dng']['image_mode'] == 4
        matched_fields=['datetime','iso','exposure','f_number','image_mode','raw13',
                        'display13','wb_mode_byte','iso_setting_byte']
        assert c['paired_metadata_fields_match'] == matched_fields
        assert all(c['metadata_dng'][k] == c['metadata_jpeg'][k] for k in matched_fields)
        for p in c['patches']:
            assert set(p['raw_channels']) == {'R','G','B'}
            assert sum(q['count'] for q in p['raw_channels'].values()) == p['pixels_jpeg']
            H=np.array(p['patch_homography_unit_patch_to_jpeg'])
            unit=np.array([[.3,.3,1],[.7,.3,1],[.7,.7,1],[.3,.7,1]])
            projected=unit@H.T
            projected=projected[:,:2]/projected[:,2:]
            np.testing.assert_allclose(projected,np.array(p['roi_jpeg_polygon_xy']),rtol=0,atol=1e-8)
            np.testing.assert_allclose(np.array(p['roi_raw_polygon_xy']),projected+[8,7],rtol=0,atol=1e-8)
            maskrow=p['roi_binary_mask']
            maskfile=Path(maskrow['path'])
            assert maskfile.resolve().is_relative_to(CAP.resolve())
            assert digest(maskfile) == maskrow['sha256']
            mask=np.array(Image.open(maskfile))
            x0,y0,x1,y1=p['roi_jpeg_bbox_xyxy']
            assert mask.shape == (y1-y0,x1-x0)
            assert set(np.unique(mask)) <= {0,255}
            assert np.count_nonzero(mask) == p['pixels_jpeg']
            patch_count += 1
    assert patch_count == 288
    capture_verification=load(OUT/'capture_verification.json')
    for name,record in capture_verification['outputs'].items():
        p=Path(name)
        assert digest(p) == record['sha256'] and p.stat().st_size == record['bytes'],name
    firmware=load(OUT/'firmware_audit.json')
    fix=load(OUT/'fix_verification.json')
    replay=load(OUT/'dispatch_replay.json')
    iso=load(OUT/'iso_trace.json')
    assert iso['verification']['result'] == 'PASS_STATIC_EVIDENCE'
    assert iso['verification']['disassembly_lines_checked_against_official_bytes'] == 2398
    assert len(firmware['actual_hooks']) == 9
    assert all(h['verified'] for h in firmware['actual_hooks'])
    assert not any(h['modified'] for h in firmware['requested_addresses'])
    assert fix['passed'] and fix['isolated_manifest_hooks'] == 8
    assert fix['payload_rebuilt_identically'] and fix['fixed_image_recomposed_identically']
    assert replay['passed'] and replay['stock_fixed_identical'] and replay['stage1b_failure_reproduced']
    assert digest(ROOT/firmware['fix']['path']) == firmware['fix']['sha256'] == fix['fixed_image_sha256']
    spec=importlib.util.spec_from_file_location('audit',OUT/'audit_firmware.py')
    audit=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    assert audit.protected_inputs() == firmware['protected_inputs']
    # Hash the concrete research deliverables, not this self-referential record.
    artifacts={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=digest(p))
               for p in sorted(set(required+[OUT/n for n in ('audit_firmware.py','replay_dispatch.py',
                  'verify_fix.py','verify_delivery.py','capture_analysis.py')]+[
                      OUT/'fix_candidate/source_fix.patch',OUT/'fix_candidate/ilaunch3.host-only',
                      OUT/'fix_candidate/rebuild/hooks.json',CAP/'cross_sensor_bridge.json']))}
    result=dict(schema='gxr.urgent-dual-mission-verification.v1',
                generated_at_utc=datetime.now(timezone.utc).isoformat(),
                status='RESEARCH_DELIVERED_HOST_FIX_VERIFIED_CAMERA_ACCEPTANCE_PENDING',
                copy=dict(files=12,pairs=6,bytes=copy['total_bytes'],all_sha256_match=True,
                          sd_writes=False,sd_deletes=False,sd_eject=False,verification_reads_only_local_copies=True),
                measurement=dict(pages=pages,raw_jpeg_patch_pairs=patch_count,
                                 canonical_four_page_patch_pairs=192,
                                 all_center_40_percent_polygons_and_raw_offsets_verified=True,
                                 all_288_saved_binary_roi_masks_rehashed=True,
                                 capture_status=capture_verification['calibration_status'],
                                 full_GR_or_16_recipe_acceptance=False),
                firmware=dict(stock_sha256=firmware['stock']['sha256'],
                              installed_candidate_sha256=firmware['stage1b']['sha256'],
                              nine_actual_hooks_verified=True,requested_va_sites_unmodified=True,
                              protected_input_files=len(firmware['protected_inputs']),protected_inputs_unchanged=True,
                              root_cause='Unconditional force_adj_image overwrites selected activity with 8 and jumps to Image Settings',
                              user_fault_clarification='本应打开 ISO，却打开了配方列表',
                              iso_trace_evidence='research/ui_bug_audit/iso_trace.json',
                              independent_static_byte_checked_disassembly_lines=2398,
                              isolated_fix=firmware['fix'],dispatch_replay_cases=replay['cases'],
                              host_checks=fix['host'],abi_cases=fix['abi_cases'],
                              production_sources_modified=False,upgrade_package_generated=False,
                              real_camera_fix_test=False),
                remaining_gaps=[
                    'Physical ISO entry/commit, all ADJ slots, P/A/S/M, Fn bindings, reopen and power-cycle acceptance of the fixed candidate',
                    'A separate conventional Shooting Menu ISO model exists; its complete event chain is not established by this audit',
                    'GR III/GR IV ColorMatrix bridge is a model with exposure/spectral assumptions, not a measured sensor match',
                    'GRD IV sensor bridge and full target JPEG pipeline are unavailable',
                    'One Setting1 midpoint state cannot identify sixteen control/recipe responses'],
                artifacts=artifacts)
    (OUT/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps(dict(status=result['status'],copies=12,patch_pairs=patch_count,
                          actual_hooks=9,fixed_hooks=8,dispatch_cases=replay['cases'],
                          protected_input_files=len(firmware['protected_inputs'])),ensure_ascii=False))


if __name__ == '__main__': main()
