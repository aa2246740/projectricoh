"""Audit seven owner-supplied natural-scene pairs, excluding the screen probes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from inventory import metadata
from raw_identity import raw_identity
from calibrate import sample
from classify_new import classify, replay
from gxr_studio.camdata import datcodec, knob_table
from gxr_studio.engine import menu, knobs
import collections
import hashlib


def candidate_bank():
    dat = rt.release_dat()
    entries = {f'{s:02d}':dat.entry_of(2,s) for s in range(1,9)}
    entries.update({look.name:look.entry for look in dat.looks if look.unit_mask&4})
    table = knob_table.read(dat.kv2_block, menu.load(),
        mount_knobs_from_50mm=datcodec.PROFILES[dat.generation].mount_knobs_from_50mm)
    fields = ('contrast','highlight','shadow','saturation','fade','warmth','tint','split','filter','tone','amount')
    for name,user in zip(dat.user_names,dat.users):
        rec = table['recipes'][16+user['base']-1]
        items = table['items'][rec['first_item']:rec['first_item']+rec['item_count']]
        chosen = dict(zip(fields,user['levels']))
        levels = [chosen[table['controls'][item['control']]['name']] for item in items]
        req = menu.request(table,2,user['base'],levels)
        entries[name],_ = knobs.apply(dat.entry_of(2,4),dat.entry_of(2,user['base']),req)
    signatures = collections.defaultdict(list)
    for name,e in entries.items():
        signature = bytes((e[1],))+e[445:447]+b''.join(e[o:o+n] for o,n in zip(datcodec.OFFSETS,datcodec.ROW_BYTES))
        signatures[hashlib.sha256(signature).hexdigest()].append(name)
    rt.dump(rt.LOCAL/'new7/candidate_bank.json',dict(entries={k:v.hex() for k,v in entries.items()},
        source='frozen g154 looks18 plus its user entries', probe_bank_not_assumed_equivalent=True))
    return entries,list(signatures.values())


def main():
    folder = rt.ROOT/'captures/mount-probe-20261103'
    expected = {}
    for line in (folder/'SHA256SUMS').read_text().splitlines():
        digest,name = line.split(None,1)
        expected[Path(name.strip().lstrip('*')).name] = digest
    records = []
    old = {r['sensor_payload_sha256'] for r in rt.read(rt.LOCAL/'materials.json')
           if r.get('sensor_payload_sha256') and not Path(r['path']).is_relative_to(folder)}
    for n in range(1894,1901):
        raw,jpg = (folder/f'R805{n}.{ext}' for ext in ('DNG','JPG'))
        a,b = metadata(raw),metadata(jpg)
        for key in ('when','iso','exposure','selector','color_raw13','orientation','wb_mode','wb_exif'):
            assert a.get(key)==b.get(key), (raw.name,key)
        assert a['unit']=='mount-a12' and b['color_space']==1
        hashes = rt.sha(raw),rt.sha(jpg)
        assert expected[raw.name]==hashes[0] and expected[jpg.name]==hashes[1]
        payload,layout = raw_identity(raw)
        row = dict(path=str(raw),sha256=hashes[0],bytes=raw.stat().st_size,**a,
            jpeg_pairs=[dict(path=str(jpg),sha256=hashes[1],color_space=b['color_space'],metadata=b,same_directory=True)],
            camera_jpeg_pair_confirmed=True,sensor_payload_sha256=payload,sensor_payload_layout=layout,
            duplicate_prior_sensor_payload=payload in old,
            stock04_status='owner_tentative04_not_independently_confirmed',
            stock04_reason='Owner says should have selected 04 Std; per-frame deep-row state is not encoded in EXIF',
            identity_evidence='2026-11-03 user supplied R8051894-R8051900 and tentative 04/no-adjustment/AWB statement',
            calibration_role='pending_identity_audit',light_group='office fluorescent plus window light; exterior view; owner description',
            date_group=a['when'][:10],scene_group='mount_natural_20261103_whole_collection',
            unknown_chart_treated_as_ordinary_scene=True,known_colour_references_used=False,
            probes_1878_1893_excluded=True)
        records.append(row)
        print('metadata',raw.stem,a['selector_name'],a['iso'],'WB',a['wb_mode'],a['wb_exif'],flush=True)
    rt.dump(rt.LOCAL/'new7/materials.json',records)
    entries,aliases = candidate_bank()
    coefficients = np.asarray(rt.read(rt.LOCAL/'calibration/mount-a12/mount_screen_20261101_degree1.json')['coefficients'])
    results = []
    for record in records:
        values,info = sample(record)
        use = values['valid']
        actual = values['observed'][use]
        assert len(actual)>=24
        raw = values['raw_wb'][use]
        x = rt.calibration_apply(raw,coefficients)
        centers = values['centers'][use]
        cells = (centers[:,1].astype(int)//712)*4+centers[:,0].astype(int)//1072
        model = rt.camera_model(2,iso=record['iso'])
        errors = {name:rt.delta_e00(rt.lab_from_codes(replay(model,e,x)),rt.lab_from_codes(actual)) for name,e in entries.items()}
        controls = {name:rt.delta_e00(rt.lab_from_codes(replay(rt.camera_model(2),e,raw*4095)),rt.lab_from_codes(actual)) for name,e in entries.items()}
        main = classify(errors,aliases,cells)
        control = classify(controls,aliases,cells)
        agree = main['best_aliases']==control['best_aliases']
        row = dict(frame=Path(record['path']).stem,iso=record['iso'],when=record['when'],points=len(actual),
            raw_sha256=record['sha256'],jpeg_sha256=record['jpeg_pairs'][0]['sha256'],
            input_calibration_frozen=True,no_jpeg_fit_for_identity=True,
            calibrated=main,uncorrected_iso200_control=control,model_consensus=agree,
            candidate04=main['best_aliases']==['04'] and main['model_supported'] and agree,
            native04_error=rt.stats(errors['04']),
            independent_04_confirmation=False, admitted_to_calibration=False,
            unknown_card_not_used_as_reference=True,probes_not_used=True)
        results.append(row)
        rt.dump(rt.LOCAL/'new7/response.json',results)
        print(row['frame'],main['best_aliases'],'04 DE',row['native04_error']['median'],
              'best gap',main['gap_de00'],'candidate04',row['candidate04'],flush=True)
    summary = dict(label='电脑预测，拍摄身份核对',created_utc=rt.utc(),pairs=7,
        all_raw_jpeg_metadata_match=True,all_jpegs_srgb=True,unit='mount-a12',
        isos=dict(collections.Counter(r['iso'] for r in records)),
        selectors=dict(collections.Counter(r['selector_name'] for r in records)),
        model_supported_04_frames=[r['frame'] for r in results if r['candidate04']],
        results=[{k:v for k,v in r.items() if k not in ('calibrated','uncorrected_iso200_control')} for r in results],
        stock04_admission='Pending definite owner selection confirmation; model support and EXIF alone are not deep-row truth',
        calibration_or_main_inputs_changed=False,new_natural_collection_is_one_holdout_group=True,
        unknown_card_used_as_colour_reference=False,screen_probe_frames_excluded=True,
        frozen_model_bank_entries=len(entries),probe_residual_models_not_assumed_verified=True)
    rt.dump('new7_identity_summary.json',summary)


if __name__=='__main__':
    main()
