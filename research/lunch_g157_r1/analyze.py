"""Identify one real frame on parity-zero blocks; score only parity-one blocks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def patches(d, rgb, shift=-1):
    np = C.np
    cy, cx, h, w = d.crop_window()
    assert rgb.shape[:2] == (h, w), 'DNG/JPEG crop differs'
    xx, yy = np.meshgrid(np.linspace(18, w-20, 96).astype(int)//2*2,
                         np.linspace(18, h-20, 72).astype(int)//2*2)
    centers = np.c_[xx.ravel(), yy.ravel()]
    by, bx = np.meshgrid(np.arange(-6, 6), np.arange(-6, 6), indexing='ij')
    xs = centers[:, 0, None] + bx.ravel()
    ys = centers[:, 1, None] + by.ravel()
    block = rgb[ys, xs].astype(float)
    obs = block.mean(1)
    sd = block.std(1)
    raw = d.normalised_at(cy+ys, cx+xs+shift)
    cfa = d.cfa_at(cy+ys, cx+xs+shift)
    codes = np.column_stack([np.sum(np.where(cfa == c, raw, 0), 1) / np.sum(cfa == c, 1) for c in range(3)])
    rawsd = np.column_stack([np.sqrt(np.sum(np.where(cfa == c, (raw-codes[:, c, None])**2, 0), 1)
                                   / np.sum(cfa == c, 1)) for c in range(3)])
    legacy = (sd.max(1) <= 12) & (obs.min(1) > 3) & (obs.max(1) < 252) & (raw.max(1) < .985) & (rawsd.max(1) < .04)
    light = C.lab(obs)[:, 0]
    valid = legacy & (raw.max(1) < .98) & (raw.min(1) > .002) & (light >= 10) & (light <= 95)
    valid &= (block.max((1, 2)) < 254) & (block.min((1, 2)) > 1)
    cells = np.c_[centers[:, 0] // max(1, w//4), centers[:, 1] // max(1, h//4)]
    return dict(raw_codes=codes/d.as_shot_neutral*4095, observed=obs, centers=centers,
                cells=cells, sd=sd, rawsd=rawsd, legacy_mask=legacy, valid=valid,
                clipped_raw=raw.max(1) >= .98, dark=(raw.min(1) <= .002) | (light < 10),
                clipped_jpeg=(block.max((1, 2)) >= 254) | (block.min((1, 2)) <= 1))


def preview(d, rgb):
    np = C.np
    cy, cx, h, w = d.crop_window()
    pw = 256
    ph = round(pw*h/w)
    yy, xx = np.meshgrid(np.linspace(2, h-4, ph).astype(int)//2*2,
                         np.linspace(2, w-4, pw).astype(int)//2*2, indexing='ij')
    raw, counts = np.zeros((ph, pw, 3)), np.zeros((ph, pw, 3))
    for dy in (0, 1):
        for dx in (0, 1):
            v = d.normalised_at(cy+yy+dy, cx+xx-1+dx)
            cfa = d.cfa_at(cy+yy+dy, cx+xx-1+dx)
            for c in range(3):
                m = cfa == c
                raw[..., c] += v*m
                counts[..., c] += m
    raw /= counts
    actual = C.Image.fromarray(rgb).resize((pw, ph), C.Image.Resampling.LANCZOS)
    return raw/d.as_shot_neutral*4095, C.np.asarray(actual)


def main(pid):
    C.admit(pid)
    C.numerical()
    C.sys.addaudithook(C.fence)
    np = C.np
    row = next(r for r in C.read(C.LOCAL / 'inventory.json') if r['id'] == pid)
    assert row['group'] != 'previous_day'
    assert C.sha(row['path']) == row['raw_sha256'] and C.sha(row['jpeg']) == row['jpeg_sha256']
    assert C.sha(C.DAT) == C.DAT_SHA
    out = C.LOCAL / 'frames' / pid
    out.mkdir(parents=True, exist_ok=True)
    d = C.Dng(row['path'])
    with C.Image.open(row['jpeg']) as im:
        rgb = np.asarray(im.convert('RGB'))
    v = patches(d, rgb)
    colour = C.scene_colour(d)
    v['xyz'] = colour.xyz(v['raw_codes'])
    v['conditioned'] = C.input_codes(v['raw_codes'])
    bank = C.read(C.LOCAL / 'bank.json')['records']
    model = C.camera_model(row['metadata']['iso'], row['metadata']['color_raw13'])
    mask = v['valid']
    identity = mask & (v['cells'].sum(1) % 2 == 0)
    held = mask & ~identity
    assert identity.sum() >= 48 and held.sum() >= 48, 'Too few independent spatial halves'
    predictions, errors50, errors65 = [], [], []
    for rec in bank:
        entry = Path(rec['record']).read_bytes()
        assert C.sha(rec['record']) == rec['sha256']
        pred = C.predict(model, entry, v['conditioned'])
        predictions.append(pred)
        errors50.append(C.de(pred, v['observed']))
        errors65.append(C.de(pred, v['observed'], 'D65'))
    predictions, errors50, errors65 = map(np.asarray, (predictions, errors50, errors65))
    med = np.median(errors50[:, identity], axis=1)
    # Group response-equivalent byte records before ranking, keeping alias identities.
    groups = []
    for j in range(len(bank)):
        existing = next((g for g in groups if np.max(np.abs(predictions[g[0]]-predictions[j])) < 1e-9), None)
        if existing is None:
            groups.append([j])
        else:
            existing.append(j)
    rank = sorted(groups, key=lambda g: med[g[0]])
    best, second = rank[0][0], rank[1][0]
    gap = float(med[second]-med[best])
    blocks = [np.flatnonzero(identity & np.all(v['cells'] == cell, axis=1)) for cell in np.unique(v['cells'][identity], axis=0)]
    rng = np.random.default_rng(1571105)
    wins = 0
    boot_gaps = []
    for unused in range(240):
        ix = np.concatenate([blocks[j] for j in rng.integers(0, len(blocks), len(blocks))])
        bm = np.median(errors50[:, ix], axis=1)
        other = min(bm[g[0]] for g in rank[1:])
        wins += bm[best] < other
        boot_gaps.append(other-bm[best])
    stable = wins/240
    held_meds = np.median(errors50[:, held], axis=1)
    held_best = min(groups, key=lambda g: held_meds[g[0]])[0]
    accepted = bool(med[best] <= 5 and gap >= .75 and stable >= .95 and held_best == best)
    aliases = [bank[i]['name'] for i in rank[0]]
    result = dict(id=pid, group=row['group'], metadata=row['metadata'],
        best=bank[best]['name'], best_aliases=aliases, best_index=best,
        second=bank[second]['name'], second_index=second, gap_de00=gap,
        identity_median_de00=float(med[best]), spatial_win_fraction=stable,
        spatial_gap_p025=float(np.percentile(boot_gaps, 2.5)),
        spatial_gap_p975=float(np.percentile(boot_gaps, 97.5)), accepted=accepted,
        exact_record_ambiguous=len(aliases) > 1,
        held_best=bank[held_best]['name'], held_best_agrees=bool(best == held_best),
        prediction_D50=C.stats(errors50[best, held]), prediction_D65=C.stats(errors65[best, held]),
        legacy_mask_prediction_D50=C.stats(errors50[best, v['legacy_mask'] & (v['cells'].sum(1)%2 == 1)]),
        candidates=[dict(names=[bank[i]['name'] for i in g], index=g[0],
                         identity=C.stats(errors50[g[0], identity]), holdout=C.stats(errors50[g[0], held])) for g in rank],
        sample_counts=dict(grid=len(mask), valid=int(mask.sum()), identity=int(identity.sum()), holdout=int(held.sum()),
                           legacy_valid=int(v['legacy_mask'].sum()), raw_clipped=int(v['clipped_raw'].sum()),
                           dark=int(v['dark'].sum()), jpeg_extreme=int(v['clipped_jpeg'].sum())),
        registration=dict(shift_xy=[-1, 0], source='independently checked historical fixed carrier shift; no fit to recipe'),
        inference_uses_owner_sequence=False, per_photo_exposure_or_WB_fit=False,
        native_c040=True, iso_model=200 if row['metadata']['iso'] < 566 else 1600,
        iso_boundary_open=row['metadata']['iso'] != 200, created_utc=C.utc())
    np.savez_compressed(out / 'samples.npz', **v, identity=identity, held=held,
                        predictions=predictions, errors50=errors50, errors65=errors65)
    # Every candidate gets a local JPEG. These are coarse CFA colour previews,
    # not a demosaicer / JPEG ISP acceptance artifact and never used for metrics.
    smallraw, actual = preview(d, rgb)
    sp = C.input_codes(smallraw.reshape(-1, 3))
    np.savez_compressed(out / 'preview-input.npz', raw_codes=smallraw, actual=actual)
    C.save_jpeg(out / 'actual.jpg', actual)
    for j, rec in enumerate(bank):
        pred = C.predict(model, Path(rec['record']).read_bytes(), sp).reshape(smallraw.shape)
        C.save_jpeg(out / 'predictions' / f'{j:02d}.jpg', pred)
    C.dump(out / 'result.json', result)
    d.release()
    print(pid, result['best'], 'vs', result['second'], 'gap', round(gap, 3),
          'held', round(result['prediction_D50']['median'], 3),
          'accepted', accepted, 'samples', int(mask.sum()), flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
