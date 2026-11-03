from pathlib import Path
import os
import sys

from scope import WORK, save, sha, ROOT


class FramesDone(Exception):
    """Raised inside the first engine call of the frames-only mode, after the frame checks."""


def frame_checks(captured, mode):
    required = ('h', 'n', 'adapter', 'frames', 'menu', 'select', 'disp', 'arrow', 'published', 'get', 'vector')
    assert all(name in captured for name in required), sorted(captured)
    h, n, adapter = captured['h'], captured['n'], captured['adapter']
    menu, select, disp, arrow, published, get, vector = (captured[name] for name in required[4:])
    unit = captured['unit_name']
    evidence = {'unit': unit, 'mode': mode, 'dat_sha256': sha(ROOT / 'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT'),
                'status': 'INCOMPLETE', 'frames': []}
    path = WORK / ('menu-frames-' + unit + '.json')

    def record(name):
        rows = published()
        value = dict(captured['frames'][-1])
        assert value['rows'] == rows
        assert len(rows) == 8 and all(isinstance(row, str) and row.isascii() and len(row) <= 8 for row in rows)
        value['rows'] = [row.ljust(8) for row in rows]
        value.update(name=name, physical=get('physical'), armed=get('armed'), slot=get('slot'))
        evidence['frames'].append(value)
        save(path, evidence)
        return value

    def circle(name, screen):
        assert get('screen') == screen, (name, 'screen', get('screen'), screen)
        select(0)
        count = get('count')
        record(name + '-first')
        arrow(-1)
        assert get('cur') == count - 1, (name, 'up-wrap', get('cur'), count)
        record(name + '-up')
        arrow(1)
        assert get('cur') == 0, (name, 'down-wrap', get('cur'))
        value = record(name + '-down')
        if count < 8:
            assert value['rows'][count] == '--------', (name, value['rows'])
            assert all(not row.strip() for row in value['rows'][count + 1:]), (name, value['rows'])
        return count

    try:
        # the retained sequence ends with its simulated failure latch set (screen 6); clear it before the frame checks
        if mode == 'after-full-checks':
            assert get('screen') == 6, ('final screen of the retained sequence', get('screen'))
            h.put(n + adapter['failed'], 0, 1)
        menu()
        select(0)
        before = list(vector())
        circle('l1', 0)
        assert list(vector()) == before and get('slot') == 1
        select(9)
        arrow(1)
        assert get('cur') == 0 and get('slot') == 1
        record('l1-preview')

        menu()
        select(2)
        disp()
        circle('card-03', 1)
        select(get('count') - 1)
        disp()
        assert get('armed') == 1
        arrow(1)
        assert get('cur') == 0 and get('armed') == 0
        record('default-move')

        select(1)
        disp()
        circle('items-03', 2)
        select(1)
        disp()
        assert get('screen') == 3
        select(0)
        arrow(-1)
        assert get('cur') == 0
        record('value-top')
        select(get('count') - 1)
        arrow(1)
        assert get('cur') == get('count') - 1
        record('value-bottom')

        menu()
        select(9)
        disp()
        circle('group', 4)
        select(1)
        disp()
        circle('entries', 5)
        evidence['status'] = 'PASS'
        save(path, evidence)
    except BaseException as error:
        evidence['status'] = 'FAIL'
        evidence['error'] = type(error).__name__ + ': ' + str(error)
        save(path, evidence)
        raise


def extend(run):
    def checked(context, arguments, out, sessions):
        products = [item for session in sessions for item in (session if isinstance(session, tuple) else (session,))
                    if callable(getattr(item, 'engine', None))]
        assert len(products) == 1
        product = products[0]
        original = product.engine
        captured = {}
        frames_only = os.environ.get('GXR_FRAMES_ONLY') == '1'

        def observe(*args, **keywords):
            frame = sys._getframe(1)
            while frame:
                if Path(frame.f_code.co_filename).name == 'product_checks.py' and frame.f_code.co_name == 'run':
                    captured.update(frame.f_locals)
                    break
                frame = frame.f_back
            product.engine = original
            if frames_only:
                frame_checks(captured, 'frames-only')
                raise FramesDone()
            return original(*args, **keywords)

        product.engine = observe
        try:
            result = run(context, arguments, out, sessions)
        except FramesDone:
            return None
        finally:
            product.engine = original
        frame_checks(captured, 'after-full-checks')
        return result
    return checked
