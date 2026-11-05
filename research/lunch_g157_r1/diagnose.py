"""Describe residuals without refitting: fixed registration controls and partial-row hypotheses."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    C.admit('diagnose')
    C.numerical()
    C.sys.addaudithook(C.fence)
    np = C.np
    summary = C.read(C.LOCAL / 'summary.json')
    rows = summary['rows']
    bank = C.read(C.LOCAL / 'bank.json')['records']
    entries = [Path(r['record']).read_bytes() for r in bank]
    i04 = next(i for i, r in enumerate(bank) if r['name'] == '04 Std')
    inventory = {r['id']:r for r in C.read(C.LOCAL / 'inventory.json')}
    k25 = [r for r in rows if r['best'] == 'Kodachrome25']
    chosen = {r['id'] for r in sorted(rows, key=lambda r:r['prediction_D50']['p95'], reverse=True)[:4]}
    chosen.update(r['id'] for r in sorted(k25, key=lambda r:r['prediction_D50']['median'], reverse=True)[:3])
    chosen.update(('R8052063', 'R8052052'))
    a = C.module('lunch_sampling_diagnostic', C.HERE / 'analyze.py')
    diagnoses = []
    spatial = []
    for row in rows:
        frame = C.LOCAL / 'frames' / row['id']
        with np.load(frame / 'samples.npz', allow_pickle=False) as z:
            v = dict(z)
        held = v['held']
        coords = v['centers'].astype(float)
        width, height = coords.max(0) + 20
        radius = np.sqrt(((coords[:, 0]-width/2)/(width/2))**2 + ((coords[:, 1]-height/2)/(height/2))**2)
        j = row['best_index']
        spatial.append(dict(id=row['id'], name=row['best'],
            centre=C.stats(v['errors50'][j, held & (radius < .5)]),
            outer=C.stats(v['errors50'][j, held & (radius >= .8)])))
        if row['id'] not in chosen:
            continue
        model = C.camera_model(row['metadata']['iso'], row['metadata']['color_raw13'])
        original = inventory[row['id']]
        d = C.Dng(original['path'])
        with C.Image.open(original['jpeg']) as im:
            rgb = np.asarray(im.convert('RGB'))
        other = {shift:a.patches(d, rgb, shift) for shift in (-2, 0)}
        common = held.copy()
        for value in other.values():
            common &= value['valid']
        registration = {}
        for shift, value in other.items():
            prediction = C.predict(model, entries[j], C.input_codes(value['raw_codes'][common]))
            registration[str(shift)] = C.stats(C.de(prediction, v['observed'][common]))
        registration['-1'] = C.stats(v['errors50'][j, common])
        # These are model-only diagnostic combinations, never new firmware records.
        b = entries[j]
        base = entries[i04]
        ablations = {}
        for component in ('curves', 'matrix', 'sectors'):
            hybrid = bytearray(b)
            if component == 'curves':
                for start, stop in ((20, 115), (379, 445)):
                    hybrid[start:stop] = base[start:stop]
                hybrid[1] = (hybrid[1] & ~4) | (base[1] & 4)
            elif component == 'matrix':
                hybrid[216:244] = base[216:244]
            else:
                hybrid[115:211] = base[115:211]
            pred = C.predict(model, bytes(hybrid), v['conditioned'][held])
            ablations['replace_' + component + '_with_04'] = C.stats(C.de(pred, v['observed'][held]))
        diagnoses.append(dict(id=row['id'], name=row['best'], full=row['prediction_D50'],
             registration_same_mask=registration, partial_row_hypotheses=ablations,
             no_diagnostic_used_to_change_identity_or_main_score=True))
        d.release()
    gross = [dict(id=r['id'], name=r['best'], errors=r['prediction_D50']) for r in rows
             if r['prediction_D50']['median'] > 5 or r['prediction_D50']['p95'] > 10]
    # Group by observed capture mode, retaining recipe composition as a confound.
    modes = {}
    for row in rows:
        group = modes.setdefault(str(row['metadata']['exposure_program']), [])
        group.append(dict(id=row['id'], recipe=row['best'], median=row['prediction_D50']['median'],
                          p95=row['prediction_D50']['p95']))
    C.dump('diagnosis.json', dict(gross_departures=gross, threshold='median>5 or p95>10 on held-out D50 DE00',
         detailed=diagnoses, spatial=spatial, morning_modes=modes,
         owner_observation='No ERR, Unsaved, or disappearing recipe list, per owner report; no camera log independently available',
         camera_issue_attribution='No unique camera-side attribution from paired image residuals alone', created_utc=C.utc()))
    C.decision('diagnosis', '保留固定配准结果，另查位移与不完整配方假设',
               '不靠逐照片拟合曝光或白平衡来掩盖预测偏差', 'local/diagnosis.json',
               f'{len(gross)} gross departures; {len(diagnoses)} detailed controls')
    print('DIAGNOSIS', len(gross), 'gross departures;', len(diagnoses), 'detailed controls', flush=True)


if __name__ == '__main__':
    main()
