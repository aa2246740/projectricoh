"""Run the generation 133 diagnostic on the pinned body (3 units): two menu
opens, every page in order GIJABCDFH, checking the open-history pages."""
from pathlib import Path
import contextlib, io, json, os, sys, types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V1 = ROOT / 'research/diag_dat_v1'
ENGINE = ROOT / 'firmware/engine_diag_v3'
DAT = ENGINE / 'candidate/local/full-r13/GXRCE.DAT'
ORDER = 'GIJABCDFHG'


def fake_scope():
    real = {'__file__': str(V1 / 'scope.py'), '__name__': 'scope'}
    exec(compile((V1 / 'scope.py').read_text().replace('sys.addaudithook(fence)', ''),
                 str(V1 / 'scope.py'), 'exec'), real)
    m = types.ModuleType('scope')
    m.__dict__.update({k: v for k, v in real.items() if not k.startswith('__')})
    m.OUT = HERE / 'local/support_out'
    m.ENGINE = ENGINE
    m.PACKAGE = HERE / 'local/package'
    m.ALLOWED = (HERE,)
    return m


def main():
    sys.modules['scope'] = fake_scope()
    sys.path.insert(0, str(V1))
    import native_support as support
    assert support.DAT.read_bytes() == DAT.read_bytes()
    results = []
    for unit in sys.argv[1:] or ('50mm', '28mm', 'mount'):
        events = []
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            h, p, *_ = support.setup(unit)
            assert int.from_bytes(p.dat[28:32], 'big') == 133
            path, attached = [], []
            def attach(b):
                if attached or not h.u(0x20054700 + 56):
                    return False
                attached.append(True)
                for name in ('ig_menu', 'ig_panel_open', 'capture'):
                    if name in p.elf.symbols or name + '.lto_priv.0' in p.elf.symbols or name + '.constprop.0' in p.elf.symbols:
                        def entered(b, name=name):
                            path.append(name)
                            return False
                        h.b.add_breakpoint(support.symbol(p, name), entered)
                return False
            h.b.add_breakpoint(h.symbols['rv_invoke'], attach)
            for opening in (1, 2):
                if opening == 2:
                    support.action(h, p, 'ok')
                for index, expected in enumerate(ORDER):
                    at = len(path)
                    if not index:
                        support.open_menu(h, p)
                    else:
                        support.action(h, p, 'disp')
                    rows = support.text_rows(h, p)
                    events.append(dict(opening=opening, expected=expected, rows=rows, path=path[at:]))
                    assert len(rows) == 8 and all(0 < len(r) <= 8 for r in rows), rows
                    assert rows[0][0] == expected, rows
                    assert ('ig_menu' if not index else 'ig_panel_open') in path[at:], path[at:]
                    assert path[at:].count('capture') == (0 if index else 1), path[at:]
                    if expected in 'IJ' or (expected == 'G' and opening == 1):
                        assert rows[1] == 'NONE' and rows[2:] == ['--------'] * 6, rows
                    elif expected == 'G':
                        assert rows[0][1:5] == '0001' and rows[0][6] == 'K', rows
                    else:
                        assert rows[0][1:5] == f'{opening:04X}', rows
                    if expected == 'H':
                        assert rows[7].startswith('OK') and rows[4].startswith('M1') and rows[5] == 'SI0007B0', rows
        results.append(dict(unit=unit, events=events))
        print('ARTIFACT_V3', unit, 'PASS', len(events), flush=True)
        for e in events:
            if e['expected'] in 'GH':
                print(' ', e['opening'], e['expected'], ' | '.join(e['rows']), flush=True)
    (HERE / 'local/artifact-v3.json').write_text(json.dumps(results, indent=1) + '\n')


if __name__ == '__main__':
    main()
