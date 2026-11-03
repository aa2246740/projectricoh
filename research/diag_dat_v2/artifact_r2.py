"""Check the packaged generation 128 and retain every menu event."""
from pathlib import Path
import contextlib
import io
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_call as legacy
import scope


def main():
    sys.addaudithook(legacy.fence)
    scope.freeze_check()
    mappings = legacy.MAPPINGS
    support = legacy.load_path(scope.ROOT / 'research/diag_dat_v1/native_support.py')
    assert legacy.MAPPINGS == mappings
    dat = scope.ROOT / 'firmware/package_v36_diag2/local/SD_ROOT/GXRCE.DAT'
    units = []
    for unit in ('50mm', '28mm', 'mount'):
        events = []
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            h, p, *_ = support['setup'](unit)
            assert p.dat == dat.read_bytes()
            assert int.from_bytes(p.dat[28:32], 'big') == 128
            assert support['setup'].__globals__['DAT'] == dat
            path = []
            attached = []
            def attach(b):
                if attached or not h.u(0x20054700+56):
                    return False
                attached.append(True)
                for name in ('ig_menu', 'ig_panel_open', 'ig_apply', 'ig_event', 'capture'):
                    if name not in p.elf.symbols:
                        continue
                    def entered(b, name=name):
                        path.append(dict(entry=name, steps=b.total_steps))
                        return False
                    h.b.add_breakpoint(support['symbol'](p, name), entered)
                return False
            h.b.add_breakpoint(h.symbols['rv_invoke'], attach)
            for opening in (1, 2):
                if opening == 2:
                    support['action'](h, p, 'ok')
                for index, expected in enumerate('ABCDFHA'):
                    at = len(path)
                    result = None
                    if not index:
                        support['open_menu'](h, p)
                    else:
                        result = support['action'](h, p, 'disp')
                    rows = support['text_rows'](h, p)
                    event = dict(opening=opening, event='open' if not index else 'disp',
                                 expected_page=expected, actual_page=rows[0][0], rows=rows,
                                 path=path[at:], result=result)
                    events.append(event)
                    scope.save(scope.HERE / ('artifact-r2-'+unit+'.json'), dict(
                        unit=unit, status='RUNNING', dat_sha256=scope.sha(dat), events=events))
                    assert len(rows) == 8 and all(0 < len(row) <= 8 for row in rows)
                    assert rows[0][0] == expected
                    assert rows[0][1:5] == f'{opening:04X}'
                    assert any(x['entry'] == ('ig_menu' if not index else 'ig_panel_open')
                               for x in event['path'])
                    assert sum(x['entry'] == 'capture' for x in event['path']) == (0 if index else 1)
                    if expected == 'H':
                        assert rows[7] == 'OK'
                        assert rows[4].startswith('M1') and rows[5] == 'SI0007B0'
                same_open = [e['rows'][0][1:] for e in events if e['opening'] == opening]
                assert len(set(same_open)) == 1
        scope.save(scope.HERE / ('artifact-r2-'+unit+'.json'), dict(
            unit=unit, status='PASS', dat_sha256=scope.sha(dat), events=events))
        units.append(dict(unit=unit, events=len(events), sequence='ABCDFHA', openings=2))
        print('ARTIFACT_R2', unit, 'RETURN 0 COUNT', len(events), flush=True)
    scope.save(scope.HERE / 'artifact-r2.json', dict(status='PASS', units=units,
               dat_sha256=scope.sha(dat), root_cause='TEST_ADAPTER'))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        frames = []
        tb = error.__traceback__
        while tb:
            frames.append(dict(file=Path(tb.tb_frame.f_code.co_filename).name,
                               function=tb.tb_frame.f_code.co_name, line=tb.tb_lineno))
            tb = tb.tb_next
        scope.save(scope.HERE / 'artifact-r2-error.json', dict(
            type=type(error).__name__, frames=frames))
        print('ARTIFACT_R2 RETURN 1 COUNT 0 TYPE', type(error).__name__)
        raise SystemExit(1)
