"""Training-only integer search for coupled affine offsets, tint and C120 gains."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import *
from run import routes
import itertools


def refine(m, d, doc, problem=None):
    reg_scale = float(doc['route'].split('_reg')[1]) if '_reg' in doc['route'] else 1.
    P = problem or Problem(m, doc['slot'], d, doc['features'], doc['daily'], reg_scale)
    p = np.array(doc['theta'])
    state = P.state(p, True)
    original = P.state(p, False)
    pre = np.einsum('ncj,cj->nc', P.H, state['q'])
    rlut_nodes = np.r_[0, np.arange(1, 32) * 128, 4095].astype(int)
    rlut_x = rlut_nodes * 255 / 4095
    if 'rlut' in P.blocks:
        state['rlut'] = np.array([np.maximum.accumulate(np.rint(np.interp(rlut_x, np.linspace(0, 255, 33), q) * 4095 / 255)) * 255 / 4095 for q in state['rlut']])
    indices = d['train']
    calls = 0
    gain_key = next((k for k in P.blocks if k in ('gain_Y', 'gain_C', 'gain_C2')), None)
    tint_key = next((k for k in ('tint_add', 'tint_Y') if k in P.blocks), None)

    def forward(s):
        if 'rlut' not in P.blocks:
            return P.forward(s, pre)
        transformed = np.column_stack([np.interp(pre[:, ch], rlut_x, s['rlut'][ch]) for ch in range(3)])
        return P.forward(s, transformed, skip_rlut=True)

    def objective(s):
        nonlocal calls
        calls += 1
        raw = forward(s)
        components = m.fs.de00_components(m.fs.lab_from_codes(np.clip(raw + d['bias'], 0, 255)), d['target'])
        effective = p.copy()
        if 'offsets' in P.blocks:
            effective[P.blocks['offsets']] = s['offsets']
        if tint_key:
            effective[P.blocks[tint_key]] = s['tint']
        if gain_key:
            effective[P.blocks[gain_key]] = (s['gains'] - 1) * 64
        reg = P.R @ effective
        return float(np.sum(components[indices] ** 2) + reg @ reg)

    start_objective = best_cost = objective(state)
    tried = 1
    affine_choices = [state['offsets']]
    if 'offsets' in P.blocks:
        desired = original['offsets'][:3] + (original['C'] / 1024) @ INPUT_INV @ original['offsets'][3:]
        base_in = np.rint(original['offsets'][3:])
        for delta in itertools.product((-1, 0, 1), repeat=2):
            inputs = base_in + delta
            output = np.rint(desired - (state['C'] / 1024) @ INPUT_INV @ inputs)
            candidate = np.r_[output, inputs]
            if np.all(abs(candidate) <= np.array([4, 8, 8, 8, 8])):
                affine_choices.append(candidate)
    tint_choices = [state['tint']]
    if tint_key:
        value = original['tint']
        tint_choices += [np.array(q) for q in itertools.product(*[(np.floor(v), np.ceil(v)) for v in value]) if np.max(np.abs(q)) <= 8]
    for offsets, tint in itertools.product(affine_choices, tint_choices):
        trial = dict(state, offsets=offsets, tint=tint)
        cost = objective(trial)
        tried += 1
        if cost < best_cost - 1e-9:
            state, best_cost = trial, cost
    # Bounded coordinate descent only on integer-encoded added controls.
    # Selection uses training loss and fixed regularizers, never heldout scores.
    for _ in range(2):
        improved = False
        for key, count, step, limit in [('offsets', 5, 1., None), ('tint', 2, 1., 8.), ('gains', 9, 1 / 64, None)]:
            active = ('offsets' in P.blocks if key == 'offsets' else bool(tint_key) if key == 'tint' else bool(gain_key))
            if not active:
                continue
            for i in range(count):
                choices = []
                for direction in (-1, 1):
                    value = state[key].copy()
                    value[i] += step * direction
                    if key == 'offsets' and abs(value[i]) > (4 if i == 0 else 8):
                        continue
                    if key == 'tint' and abs(value[i]) > 8:
                        continue
                    if key == 'gains' and not .5 <= value[i] <= 1.5:
                        continue
                    trial = dict(state)
                    trial[key] = value
                    choices.append((objective(trial), trial))
                if choices:
                    cost, trial = min(choices, key=lambda q: q[0])
                    if cost < best_cost - 1e-9:
                        state, best_cost = trial, cost
                        improved = True
        if not improved:
            break
    pred = np.clip(forward(state) + d['bias'], 0, 255)
    error = m.fs.delta_e00(m.fs.lab_from_codes(pred), d['target'])
    packed = packed_parameters(P, p)
    packed['output_input_offset_delta'] = np.rint(state['offsets']).astype(int)
    packed['c004_signed_magnitude_delta'] = np.rint(state['tint']).astype(int)
    packed['c120_gain_u8'] = np.rint(state['gains'] * 64).astype(int)
    if 'rlut' in P.blocks:
        packed['rlut_inputs_u12'] = rlut_nodes
        packed['rlut_outputs_u12'] = np.rint(state['rlut'] * 4095 / 255).astype(int)
    assert best_cost <= start_objective + 1e-8
    held = d['held'] if doc['fold'] != 'full' else d['score_mask']
    result = dict(slot=doc['slot'], fold=doc['fold'], route=doc['route'], features=doc['features'],
                  packed=packed, model_sha256=doc['model_sha256'], prediction_label='电脑预测',
                  start_training_objective=start_objective, final_training_objective=best_cost,
                  objective_evaluations=calls, heldout_used_for_selection=False,
                  integer_score=score(error[held], d['baseline'][held]),
                  method='coupled affine integer seeds plus at most two coordinate passes on offset/tint/gain codes',
                  integer_units='same as primary model; all other rounded fields remain frozen')
    return result, pred, error


def main():
    m = rt.model()
    cache, count = {}, 0
    for path in sorted((rt.LOCAL / 'fits').rglob('*.json')):
        doc = rt.read(path)
        if not any(k in doc['features'] for k in ('offsets', 'tint_add', 'tint_Y', 'gain_Y', 'gain_C', 'gain_C2', 'rlut')):
            continue
        dest = rt.LOCAL / 'integer_refined' / path.relative_to(rt.LOCAL / 'fits')
        if dest.exists():
            old = rt.read(dest)
            if 'rlut' not in doc['features'] or 'rlut_inputs_u12' in old['packed']:
                continue
            import shutil
            archive = rt.LOCAL / 'initial_rlut_grid' / path.relative_to(rt.LOCAL / 'fits')
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dest, archive)
            shutil.copyfile(dest.with_suffix('.npz'), archive.with_suffix('.npz'))
        key = doc['slot'], doc['fold']
        if key not in cache:
            cache[key] = prepare_data(m, *key)
        result, pred, error = refine(m, cache[key], doc)
        rt.dump(dest, result)
        np.savez_compressed(dest.with_suffix('.npz'), prediction_integer=pred, error_integer=error)
        count += 1
    rt.finish('integer_refine')
    print('integer refined', count, flush=True)


if __name__ == '__main__':
    main()
