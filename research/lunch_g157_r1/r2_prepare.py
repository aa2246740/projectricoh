"""Freeze exact planned records and input-only RAW samples; no optimization imports."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from r2_common import C, R1, FILM, PLANNED, STYLE_INDICES, tiny_score, decision


def main():
    C.admit('r2-prepare')
    C.numerical()
    C.sys.addaudithook(C.fence)
    np = C.np
    protected = {}
    def read(path):
        path = Path(path)
        protected[str(path)] = C.sha(path)
        return C.read(path)
    def copy_record(row, key):
        p = Path(row['record_file'])
        expected = row.get('record_sha256', row.get('sha256'))
        assert C.sha(p) == expected and len(p.read_bytes()) == 552
        protected[str(p)] = expected
        dest = C.LOCAL / 'records' / (key + '.record552')
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(p.read_bytes())
        return dict(file=str(dest), sha256=expected, source=str(p))
    initial = read(R1 / 'inputs.json')
    for row in initial['files']:
        assert C.sha(row['path']) == row['sha256'], 'R1 model/input drift'
        protected[row['path']] = row['sha256']
    # The only R1 record used here is the fixed original 04 model anchor, never a candidate.
    stock = R1 / 'records/04_Std.record552'
    out = C.LOCAL / 'records/04_Std.record552'
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(stock.read_bytes())
    protected[str(stock)] = C.sha(stock)
    catalog = read(FILM / 'catalog.json')
    full = read(FILM / 'full_library_manifest.json')
    acros = read(FILM / 'acros_official_handoff.json')
    locked = read(FILM / 'locked_shared_flags7_handoff.json')
    planned = {name:dict(placement=placement, slot=slot) for name, placement, slot in PLANNED}
    locked_by_name = {r['name']:r for r in locked['records'] if r['unit'] == 'mount-a12'}
    styles = []
    def variant(source, index, key, scoredata, override=None):
        result = copy_record(override or source, key)
        result.update(old_score=tiny_score(scoredata), fit_index=index,
                      reference_exact_checked=source.get('reference_exact_checked', True))
        return result
    for film in catalog['films']:
        ordinal, name = film['ordinal'], film['name']
        analysis_path = FILM / 'analysis' / f'{ordinal:02d}/mount-a12/final.json'
        d = read(analysis_path)
        exported = next(r for r in full['records'] if r['unit'] == 'mount-a12' and r['name'] == name)
        assert exported['record_sha256'] == d['routes'][d['selected_route']]['record_sha256']
        a, b = d['routes'][d['selected_Look_route']], d['routes'][d['selected_route']]
        sid = film['id']
        profile_path = FILM / 'targets/mount-a12' / str(film['indices'][d['selected_route']]) / 'profile.json'
        profile = read(profile_path)
        style = dict(id=sid, name=name, kind='film', planned=name in planned,
            planned_placement=planned.get(name, {}).get('placement'), planned_slot=planned.get(name, {}).get('slot'),
            target_definition=film, old_analysis=str(analysis_path), old_groups=profile['groups'],
            source_target_uses_04=False, original_Look_safe=d.get('provisional_Look_safe'),
            variants=dict(
                Look=variant(a, film['indices'][d['selected_Look_route']], sid+'-Look', a['scores']['photo_iso200'], locked_by_name.get(name)),
                full=variant(exported, film['indices'][d['selected_route']], sid+'-full', exported['scores']['photo_iso200'])))
        styles.append(style)
    for name, index in STYLE_INDICES.items():
        path = FILM / 'style_analysis' / f'{index:02d}/mount-a12.json'
        d = read(path)
        sid = 'style-' + str(index)
        if name == 'Acros official':
            i0, i1 = 14, 4053
            source = next(r for r in acros['profiles'] if r['unit'] == 'mount-a12')
            original = acros['target']
        else:
            i0, i1 = 3000+10*index, 3001+10*index
            source = d['Look']
            original = read(C.ROOT / 'research/look_ceiling_r1/local' / f'target_{index:02d}.json')
        profile_path = FILM / 'targets/mount-a12' / str(i0) / 'profile.json'
        profile = read(profile_path)
        override = locked_by_name.get(name)
        if name == 'Acros official' and override is None:
            override = locked_by_name.get('Acros')
        styles.append(dict(id=sid, name=name, kind='style', planned=True,
            planned_placement=planned[name]['placement'], planned_slot=planned[name]['slot'],
            target_definition=original, old_analysis=str(path), old_groups=profile['groups'],
            source_target_uses_04=original.get('interpretation') == 'after04',
            original_Look_safe=d['Look_safe'],
            variants=dict(Look=variant(source,i0,sid+'-Look',d['Look']['scores']['photo_iso200'],override),
                          full=variant(d['full'],i1,sid+'-full',d['full']['scores']['photo_iso200']))))
    assert len(styles) == 27 and sum(r['planned'] for r in styles) == 13
    # Freeze all old holdout banks and all target assets used by the evaluation.
    for style in styles:
        p = Path(style['old_groups']['photo_iso200'])
        protected[str(p)] = C.sha(p)
        t = style['target_definition']
        if style['kind'] == 'film':
            for k in ('scene', 'jpeg'):
                p = Path(t[k]['file']); assert C.sha(p) == t[k]['sha256']
                protected[str(p)] = t[k]['sha256']
        elif style['name'] == 'Acros official':
            protected[t['file']] = C.sha(t['file'])
        else:
            p = C.ROOT / t['source']; assert C.sha(p) == t['source_sha256']
            protected[str(p)] = t['source_sha256']
    C.dump('styles.json', styles)
    inventory = read(R1 / 'inventory.json')
    frames = [r for r in inventory if r['group'] != 'previous_day']
    arrays = {k:[] for k in ('raw_codes','xyz','x','base','observed','photo_id','bank','lunch','strict96')}
    receipts = []
    identities = {r['id']:r for r in read(R1/'summary.json')['rows']}
    assert all(r['metadata']['iso']==200 and r['metadata']['color_raw13']==frames[0]['metadata']['color_raw13'] for r in frames)
    model = C.camera_model(200, frames[0]['metadata']['color_raw13'])
    stock_bytes = out.read_bytes()
    for i, frame in enumerate(frames):
        p = Path(frame['path'])
        assert C.sha(p) == frame['raw_sha256']
        d = C.Dng(p)
        col = C.scene_colour(d)
        y0,x0,h,w = d.crop_window()
        width,height = 32,max(2,round(h*32/w))
        yy,xx = np.meshgrid(y0+2*np.linspace(0,(h-2)//2,height).astype(int),
                            x0+2*np.linspace(0,(w-2)//2,width).astype(int),indexing='ij')
        raw,count = np.zeros((height,width,3)),np.zeros((height,width,3))
        clipped = np.zeros((height,width),bool)
        for dy in (0,1):
            for dx in (0,1):
                v = d.normalised_at(yy+dy,xx+dx)
                channel = d.cfa_at(yy+dy,xx+dx)
                clipped |= v >= .98
                for c in range(3):
                    m = channel == c
                    raw[...,c] += v*m; count[...,c] += m
        raw /= count
        codes = (raw/d.as_shot_neutral*4095).reshape(-1,3)
        xyz = col.xyz(codes)
        valid = (~clipped).ravel() & np.isfinite(xyz).all(1)
        take = np.flatnonzero(valid)
        take = take[np.linspace(0,len(take)-1,min(96,len(take))).astype(int)]
        r96,x96 = codes[take],xyz[take]
        # A fixed sensitivity mask, never dependent on the candidate or target errors.
        scene_lab = C.lab(np.clip(C.xyz_to_encoded(x96,'srgb'),0,1)*255,'D65')
        strict = (raw.reshape(-1,3)[take].min(1)>.002)&(scene_lab[:,0]>=10)&(scene_lab[:,0]<=95)
        oldpath = R1 / 'frames' / frame['id'] / 'samples.npz'
        protected[str(oldpath)] = C.sha(oldpath)
        with np.load(oldpath,allow_pickle=False) as z:
            held = z['held']; rh,xh = z['raw_codes'][held],z['xyz'][held]
            observed = z['observed'][held]
        for bank,rc,xc,sm,obs in ((0,r96,x96,strict,np.zeros_like(r96)),(1,rh,xh,np.ones(len(rh),bool),observed)):
            conditioned = C.input_codes(rc)
            base = C.predict(model,stock_bytes,conditioned)
            for key,value in dict(raw_codes=rc,xyz=xc,x=conditioned,base=base,observed=obs,
                 photo_id=np.full(len(rc),i),bank=np.full(len(rc),bank),
                 lunch=np.full(len(rc),frame['group']=='lunch'),strict96=sm).items():
                arrays[key].append(value)
        receipts.append(dict(id=frame['id'],group=frame['group'],raw96=len(r96),r1held=len(rh),strict96=int(strict.sum()),
                             raw_sha256=frame['raw_sha256'],jpeg_sha256=frame['jpeg_sha256'],
                             g157_best=identities[frame['id']]['best'],g157_accepted=identities[frame['id']]['accepted']))
        d.release()
    np.savez_compressed(C.LOCAL/'inputs.npz',**{k:np.concatenate(v) for k,v in arrays.items()})
    C.dump('photos.json',receipts)
    for p in sorted(C.HERE.glob('r2_*.py')):
        protected[str(p)] = C.sha(p)
    C.dump('inputs.json',dict(status='FROZEN',created_utc=C.utc(),files=protected,photos=receipts,
        planned_styles=13,evaluated_styles=27,no_fit_or_tuning=True,
        primary_sampler='Exact existing film_r2 prepare_inputs RAW sampler: 32-wide 2x2 CFA grid, reject RAW clipping, <=96 fixed samples/photo',
        secondary_sampler='Unchanged strict R1 odd spatial half, for regional and sampling sensitivity checks',
        scene_target_policy='Owner chooses scene-light input. Three digital after04 targets are also replayed under their source convention to expose the baseline mismatch.'))
    decision('inputs','冻结 13 种显式候选及 14 种扩展胶片对照','按既定训练胜者读取记录，不在今日照片上选参数或路线',
             'local/r2/styles.json; local/r2/inputs.json','27 styles; 54 position records; 55 DNGs')
    print('PREPARED',len(styles),'styles;',sum(r['planned'] for r in styles),'planned; source target mismatches',
          [r['name'] for r in styles if r['source_target_uses_04']],flush=True)


if __name__=='__main__':
    main()
