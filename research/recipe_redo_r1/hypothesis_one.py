"""Single unverified C120/C100 branch; outputs private model integers, never DAT."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
import signal
import struct
import time
from fit_one import model, quality, objective, seed, ring_masks
from entry_codec import predict


def run(args):
    code_snapshot = rt.freeze_task_code()
    ui = ('a12-50', 'a12-28', 'mount-a12').index(args.unit)
    backend = model
    if args.backend == 'fast':
        from fast_backend import load
        backend, _ = load()
        receipt = rt.read(rt.LOCAL/'fast_engine/adapter_receipt.json')
        acceptance = rt.read(rt.LOCAL/'fast_engine/equivalence_task.json')
        assert acceptance['status']=='PASS' and acceptance['backend_fingerprint']==receipt['backend_fingerprint']
    base = rt.LOCAL/'targets'/args.unit
    meta = rt.read(base/f'{args.index:02d}.json')
    for group, expected in meta['input_file_sha256'].items():
        assert rt.sha(rt.LOCAL/'inputs'/args.unit/(group+'.npz')) == expected
    current = bytes.fromhex(meta['template_hex'])
    parent_entry, parent_source = current, 'current published or evaluated reference row'
    candidates = list((rt.LOCAL/'fits'/args.unit/f'{args.index:02d}').glob('L1_*.json'))
    if not candidates and ui == 2:
        candidates = list((rt.LOCAL/'fits'/args.unit/f'{args.index:02d}').glob('L0_*.json'))
    if candidates:
        path = min(candidates, key=lambda p: rt.read(p)['objective'])
        doc = rt.read(path)
        assert doc['target_sha256'] == rt.sha(base/f'{args.index:02d}.json')
        parent_entry, parent_source = path.with_suffix('.record552').read_bytes(), str(path.relative_to(rt.HERE))
    camera, fixture = rt.Camera(ui), rt.Camera(ui)
    camera.row = rt.mm.MatrixRow.from_bytes(current[216:244])
    nodes = [0, *struct.unpack_from('>31H', parent_entry, 20), 4095]
    camera.curve = rt.mm.Curve(nodes, fixture.curve.ys)
    config = dict(level=args.level, axis=args.axis, tail_order=args.order,
        full_fields=True, key=f'L{args.level}_{args.axis}_{args.order}_{args.tint}_fullfields',
        tint=args.tint, hypothetical=True, no_hardware_equation_confirmation=True)
    groups = {group: rt.arrays(base/f'{args.index:02d}_{group}.npz') for group in meta['input_file_sha256']
              if (base/f'{args.index:02d}_{group}.npz').exists()}
    train = groups['train']
    P = backend.Problem(camera, train['x'], train['want'], train['sw'], config)
    parent = backend.Problem(camera, train['x'], train['want'], train['sw'], dict(level=1, key='L1_embedded_parent'))
    initial = P.promote_integer(parent, seed(parent, parent_entry))
    if args.parent:
        previous_doc = rt.read(rt.HERE/args.parent)
        assert previous_doc['unit']==args.unit and previous_doc['index']==args.index
        assert previous_doc['config']['axis']==args.axis and previous_doc['config']['tail_order']==args.order
        assert previous_doc['target_sha256']==rt.sha(base/f'{args.index:02d}.json')
        previous = backend.Problem(camera, train['x'], train['want'], train['sw'], previous_doc['config'])
        initial = P.promote_integer(previous, np.asarray(previous_doc['theta']))
        parent_source = args.parent
    output = rt.LOCAL/'hypotheses'/args.unit/f'{args.index:02d}'/(config['key']+'_'+args.tag)
    assert output.resolve().is_relative_to(rt.LOCAL/'hypotheses'/args.unit/f'{args.index:02d}')
    artifacts = [output.with_suffix('.json')]+[output.parent/(output.name+'_'+key+'.npz') for key in groups]
    assert not any(p.exists() for p in artifacts), 'A fresh branch tag is required; preserve partial outputs'
    start = time.monotonic()
    parent_state = P.state(initial, True)
    parent_prediction = P.predict_state(parent_state, train['x'])
    selected = dict(theta=initial, value=objective(parent_prediction, train['want'], train['sw']), origin='embedded_parent')
    parent_training_objective = selected['value']
    attempts = []
    if meta.get('builtin_slot') != 4:
        starts = [('embedded_parent', initial)]
        for name, theta in starts:
            theta, status = P.solve(theta, args.nfev)
            attempts.append(dict(start=name, **status))
            state = P.state(theta, True)
            value = objective(P.predict_state(state, train['x']), train['want'], train['sw'])
            if value < selected['value']:
                selected = dict(theta=theta, value=value, origin='hypothetical_refit')
    packed = rt.plain(P.packed(selected['theta']))
    state = P.unpack(packed)
    direct = P.state(selected['theta'], True)
    scores, gaps = {}, {}
    output.parent.mkdir(parents=True, exist_ok=True)
    for group, values in groups.items():
        if not len(values['x']):
            scores[group] = None
            continue
        a = P.predict_state(state, values['x'], round_output=False)
        b = P.predict_state(direct, values['x'], round_output=False)
        difference = float(abs(a-b).max())
        assert difference < 1e-7, ('Hypothesis packing changed predictions', difference)
        prediction = np.rint(a)
        parent_prediction = P.predict_state(parent_state, values['x'])
        scores[group] = dict(candidate=rt.score(values['base'], prediction, values['want']),
            current=rt.score(values['base'], values['current'], values['want']),
            embedded_parent=rt.score(values['base'], parent_prediction, values['want']))
        a, b = scores[group]['candidate']['similarity_percent'], scores[group]['current']['similarity_percent']
        gaps[group] = a-b if a is not None and b is not None else None
        np.savez_compressed(output.parent/(output.name+'_'+group+'.npz'), prediction=prediction.astype(np.uint8))
    gradients, rings = quality.fixtures(fixture)
    fn = lambda x, rounding: P.predict_state(state, x, round_output=rounding)
    q = quality.diagnostics(fixture, fn, gradients, rings)
    before = ring_masks(fixture, lambda x, rounding:predict(current, x, ui, round_output=rounding), rings)
    after = ring_masks(fixture, fn, rings)
    q.update(new_reverse_hue_intervals=sum(int((a & ~b).sum()) for a, b in zip(after, before)),
        main_candidate=False, interpretation='Unverified equations; quality failure flags are retained, never promoted')
    training_improved = selected['value'] < parent_training_objective-1e-9
    overfit = {group:bool(training_improved and row['candidate']['de00']['median'] >= row['embedded_parent']['de00']['median'])
        for group, row in scores.items() if row and group!='train'}
    doc = dict(label='电脑预测，未确认硬件方程假设', unit=args.unit, index=args.index, name=meta['name'],
        config=config, backend=args.backend, code_snapshot=code_snapshot, parameters=packed, theta=selected['theta'],
        training_objective=selected['value'], origin=selected['origin'], parent_source=parent_source,
        solver_attempts=attempts, scores=scores, gain_over_current_pp=gaps, overfit_flags=overfit, quality=q,
        training_only_parameter_selection=True, target_sha256=rt.sha(base/f'{args.index:02d}.json'),
        main_candidate=False, recommend_next_dat_build=False,
        mount_T1_also_pending_probe=ui==2,
        storage='hypothetical model integer fields only; C120 is not represented by the current 552-byte record',
        ordinary_Standard_main_record_proof_required_separately=True,
        no_552_record_claim=True, no_dat_built=True, elapsed_seconds=time.monotonic()-start)
    rt.assert_task_code(code_snapshot)
    rt.dump(output.with_suffix('.json'), doc)
    print(args.unit, args.index, config['key'], 'hypothesis only', gaps,
        'new hue intervals', q['new_reverse_hue_intervals'], 'seconds', doc['elapsed_seconds'], flush=True)


def main():
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Hypothesis branch exceeded 25 minutes')))
    signal.alarm(1500)
    ap = argparse.ArgumentParser()
    ap.add_argument('--unit', choices=('a12-50', 'a12-28', 'mount-a12'), required=True)
    ap.add_argument('--index', type=int, required=True)
    ap.add_argument('--level', type=int, choices=(2, 3), required=True)
    ap.add_argument('--axis', choices=('Y', 'C'), required=True)
    ap.add_argument('--order', choices=('pre', 'post'), default='post')
    ap.add_argument('--tint', choices=('add_after', 'Y_before'), default='add_after')
    ap.add_argument('--parent')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--backend', choices=('reference', 'fast'), default='reference')
    ap.add_argument('--nfev', type=int, default=40)
    run(ap.parse_args())


if __name__ == '__main__':
    main()
