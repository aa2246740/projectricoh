#!/usr/bin/env python3
"""Reuse Positive's historical target protocol for the corresponding Negative sources."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from target import DenseTarget


def arrays(path):
    with np.load(path, allow_pickle=False) as z:
        return dict(z)


def main():
    m = rt.model()
    dense = DenseTarget()
    common = rt.module('common', rt.ROOT/'research/gr_pairs/common.py')
    common.TMP = rt.LOCAL/'tmp'
    rt.os.environ['TMPDIR'] = str(common.TMP)
    p = rt.module('negative_historical_pairs', rt.ROOT/'research/gr_pairs/refit.py')
    generator = p.G.GRGenerator(rt.ROOT/'artifacts/downloads/bastibe-gr3')
    hdf = p.Transfer('gr4_hdf', 'negative', p.G, generator)
    rows = []

    def compare(ident, x, base, oldtarget, valid, sources, generation):
        target, supported, distance = dense.target(x, base)
        use = valid & supported
        error = m.fs.delta_e00(target[use], oldtarget[use])
        row = dict(id=ident, generation=generation, old_valid=int(valid.sum()),
            new_supported_on_old_valid=int(use.sum()), unsupported_on_old_valid=int((valid & ~supported).sum()),
            target_difference_de00=rt.stats(error),
            delta_L_median=float(np.median(target[use, 0]-oldtarget[use, 0])) if use.any() else None,
            sources_sha256={str(q.relative_to(rt.ROOT)):rt.sha(q) for q in sources},
            independent_same_scene_Standard_available=ident.startswith('bastibe'),
            scope='same historical relative-target convention as Positive; older inferred Standard and sensor bridge retained')
        folder = rt.LOCAL/'target/historical'
        folder.mkdir(exist_ok=True)
        np.savez_compressed(folder/(ident+'.npz'), x=x, base=base, target=oldtarget, valid=valid,
            new_target=target, common_support=use, nearest_feature_distance=distance)
        rows.append(row)
        print(ident, int(use.sum()), rt.stats(error).get('median'), flush=True)

    for group, ident, generation in [('gr4_hdf','hdf_negative','GR IV HDF R0003006'),
                                    ('gr4_b','gr4b_negative','GR IV gr4_modes negative'),
                                    ('gr3','bastibe_negative','GR III')]:
        source = rt.ROOT/f'research/gr_pairs/local/targets/{group}_02_200.npz'
        old = arrays(source)
        x, base = old['input_x'], p.FS.lab_from_codes(old['rgb04'])
        if group == 'gr4_b':
            observed = p.samples(['gr4b_negative'])
            lookup = {(int(xx),int(yy)):i for i,(xx,yy) in enumerate(observed['xy'])}
            ix = np.array([lookup[int(xx),int(yy)] for xx,yy in old['source_xy']])
            standard, _, _, support, _ = hdf.labs(x)
            styled = p.CM.rgb_lab(observed['jpeg'][ix]/255)
            target = p.apply_relative(base, standard, styled)
            valid = support & old['mode_supported']
        else:
            transfer = hdf if group == 'gr4_hdf' else p.Transfer('gr3','negative',p.G,generator)
            target, valid = p.observed_targets(group,'02',old,transfer)
        compare(ident,x,base,target,valid,[source],generation)
    for ident in ('R0003039_roi','R0003039_whole_flat'):
        source = rt.ROOT/f'research/gr_hdfchart/local/{ident}_scores.npz'
        old = arrays(source)
        compare(ident,old['x'],old['base'],old['target'],old['valid'],[source],'GR IV HDF chart')
    # The existing web corpus has one Negative scene, GR IIIx London.
    source = rt.ROOT/'research/gr_webpairs/local/scores_London.npz'
    if source.exists():
        old = arrays(source)
        target = p.apply_relative(old['base'],old['standard'],old['style_observed'])
        assert np.max(abs(target-old['target'])) < 1e-9
        compare('gr_webpairs_London',old['x'],old['base'],target,old['valid'],[source],'GR IIIx')
    rt.dump('target/historical_consistency.json',rows)


if __name__ == '__main__':
    main()
