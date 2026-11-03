"""Apply the owner's dated lens statement without overwriting recorded EXIF."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime_std as rt
from inventory import metadata, SELECTORS
import collections

DESCRIPTION='35mm f/2 七片式 Mandler 设计复刻版，手动 M 口镜头'


def apply(row):
    stem=Path(row['path']).stem
    if not stem.startswith('R805') or not stem[4:].isdigit():return False
    number=int(stem[4:])
    if not 1878<=number<=1933 or row['unit']!='mount-a12':return False
    screen=number<1894 or number>1900
    row.update(lens_owner_description=DESCRIPTION,lens_owner_focal_mm=35,
        lens_owner_max_aperture_f=2,lens_owner_mount='M',lens_manual=True,
        lens_identity_source='机主确认，由用户转达，2026-11-03',
        lens_confirmation_date='2026-11-03',capture_aperture_f_owner=5.6 if screen else None,
        capture_aperture_status='owner_confirmed' if screen else 'unknown',
        exif_zero_aperture_interpretation='manual M lens did not report the working aperture; never f/0',
        lens_confirmation_scope='identified 2026-11-03 probe and natural collections, not older MOUNT captures')
    if screen:
        phase='morning' if number<1894 else 'bracket' if number<=1917 else 'ramp_reference' if number<=1925 else 'ramp_formal'
        row.update(calibration_role='excluded_probe_only',exclude_from_recipe_photo_holdout=True,
            stock04_status='probe_frame_native04_not_asserted',
            stock04_reason='Screen test controls, not admitted as native04 calibration',
            date_group='2026:11:03',light_group='screen_daylight_wb_f5_6',
            scene_group='mount_screen_probe_20261103_'+phase,
            ramp_reference_only=1918<=number<=1925,ramp_formal=1926<=number<=1933)
    return True


def main():
    rows=rt.read(rt.LOCAL/'materials.json')
    existing={r['path'] for r in rows}
    for folder,numbers in [('mount-probe-20261103',range(1878,1894)),
                           ('mount-probe-bracket-20261103',range(1901,1918)),
                           ('mount-probe-ramp-20261103-take1-no-preset',range(1918,1926)),
                           ('mount-probe-ramp-20261103',range(1926,1934))]:
        for number in numbers:
            stem='R805'+str(number);raw=rt.ROOT/'captures'/folder/(stem+'.DNG');jpg=raw.with_suffix('.JPG')
            if str(raw) in existing:continue
            m,j=metadata(raw),metadata(jpg)
            assert m['unit']=='mount-a12' and m['when']==j['when'] and j['color_space']==1
            row=dict(m)
            row.update(path=str(raw),sha256=rt.sha(raw),bytes=raw.stat().st_size,
                jpeg_pairs=[dict(path=str(jpg),sha256=rt.sha(jpg),color_space=j['color_space'],metadata=j,same_directory=True)],
                camera_jpeg_pair_confirmed=True,source_collection=folder,
                selector_name=SELECTORS.get(m.get('selector'),'unknown'),
                identity_evidence='owner lens statement 2026-11-03; field probe analysis',
                duplicate_paths=[str(raw)],sensor_payload_status='not newly audited; probe-only frame with verified original file hash')
            rows.append(row)
    changed=[r for r in rows if apply(r)]
    rt.dump(rt.LOCAL/'materials.json',rows)
    new7=rt.read(rt.LOCAL/'new7/materials.json')
    assert all(apply(r) for r in new7)
    rt.dump(rt.LOCAL/'new7/materials.json',new7)
    rt.dump(rt.LOCAL/'lens_owner_confirmation_20261103.json',dict(
        source='机主确认，由用户转达',confirmation_date='2026-11-03',description=DESCRIPTION,
        screen_frames='R8051878-R8051893 and R8051901-R8051933',screen_aperture_f=5.6,
        ramp_owner_source='FIELD_20261103_RAMP.md:9, owner confirmed both ramp takes at f/5.6',
        natural_frames='R8051894-R8051900',natural_aperture='unknown',
        EXIF_values_preserved=True,no_older_lens_identity_backfill=True))
    from audit_inputs import materials
    materials()
    rt.dump('lens_identity_summary.json',dict(description=DESCRIPTION,source='机主确认，2026-11-03',
        admitted_lens_identity_frames=len(changed),screen_probe_frames=sum(r['capture_aperture_f_owner']==5.6 for r in changed),natural_scene_frames=7,
        ramp_formal_frames=8,ramp_reference_only_frames=8,
        screen_working_aperture_f=5.6,natural_working_aperture='unknown',
        EXIF_zero_is_missing_manual_aperture=True,original_EXIF_unchanged=True,
        older_MOUNT_lens_and_aperture_not_inferred=True,probe_frames_not_used_for_04_calibration=True))
    print('Lens identity recorded',len(changed),'frames; natural7 aperture unknown; historical lenses unchanged')


if __name__=='__main__':main()
