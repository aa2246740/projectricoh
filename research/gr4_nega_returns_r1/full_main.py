#!/usr/bin/env python3
"""Original full MAIN function, with its incoming output directory redirected."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
import ast
import inspect


def main():
    rb, a, common = rt.readback_modules()
    original_setup = rb.setup

    def setup(owner):
        result = original_setup(owner)
        result.LOCAL, result.TMP = rt.RETURNS, rt.LOCAL/'tmp'
        a.LOCAL = rt.RETURNS
        for key in ('TMPDIR', 'TMP', 'TEMP'):
            rb.os.environ[key] = str(rt.LOCAL/'tmp')
        return result

    rb.setup = setup
    tree = ast.parse(inspect.getsource(rb.read_returns))
    replacements = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == 'incoming':
            node.value = rt.RETURNS.name
            replacements += 1
    assert replacements == 1, 'only the output-directory constant may change'
    namespace = dict(rb.__dict__)
    exec(compile(tree, str(Path(rb.__file__)), 'exec'), namespace)
    rt.RETURNS.mkdir(exist_ok=True)
    destination = rt.RETURNS/'main.json'
    assert not destination.exists(), 'do not overwrite a completed readback'
    paths, dngs = [], []
    for number in range(103, 107):
        folder = rt.INPUT/f'R{number:07d}'
        paths.extend(folder/f'R{number:07d} {style}.JPG' for style in ('Std', 'Posi', 'Nega'))
        dngs.append(folder/f'R{number:07d}.DNG')
    try:
        result = namespace['read_returns']('gr4', paths, dngs, destination, stage='main')
    except ValueError as error:
        rt.dump(rt.RETURNS/'gate_rejection.json', dict(stop_condition=True, gate=str(error), original_readback_sha256=rt.sha(rb.__file__)))
        raise
    assert result['passed'] and result['camera_evidence'] and not result['offline_prediction']
    assert len(result['identities']) == 12 and len(result['returned_dngs']) == 4
    gates = []
    for ident, receipt in result['analyses'].items():
        d = rt.read(Path(receipt['path']))
        for style, state in d['modes'].items():
            rb.defaults(state['metadata'], style)
            assert state['radial']['passed'] and state['radial']['colour_holdout']['passed']
            assert all(p['spatially_flat'] for p in state['patches'])
            gates.append(dict(card=ident, style=style, patches=len(state['patches']), radial=True, radial_colour_holdout=True, all_flat=True))
    rt.dump(rt.RETURNS/'gates.json', dict(passed=True, full_MAIN_complete=True, original_gates_unchanged=True,
        adapter_change='incoming output directory constant only; setup redirects task temporary files',
        original_readback_sha256=rt.sha(rb.__file__), cases=gates))
    print('full MAIN passed: 4 bands, 12 default-style JPEGs, 4 unchanged DNGs', flush=True)


if __name__ == '__main__':
    main()
