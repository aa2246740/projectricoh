import json
import sys

_path = None
_writer = None
_differences = []


def configure(path, writer):
    global _path, _writer
    _path, _writer = path, writer


def save_display(complete):
    if _path is not None:
        with _writer(_path, 'w') as stream:
            json.dump({'status': 'FAIL' if _differences else 'PASS', 'other_assertions_completed': complete, 'differences': _differences}, stream, indent=2)
            stream.write('\n')


def compare_title(actual, expected):
    if actual != expected:
        frame = sys._getframe(1)
        difference = {'file': frame.f_code.co_filename, 'line': frame.f_lineno, 'actual': actual, 'expected': expected}
        for value in frame.f_locals.values():
            if callable(getattr(value, 'state', None)) and hasattr(value, 'p'):
                state = value.state()
                difference['state'] = {key: state[key] for key in ['screen', 'cur', 'top', 'count', 'physical', 'slot', 'levels', 'applied_user', 'labels'] if key in state}
                break
        _differences.append(difference)
        save_display(False)
    return True


def finish_user_checks():
    save_display(True)
    if _differences:
        raise AssertionError('User card title differs from the previous display contract')


def expected_levels(values):
    prior = list(values)
    if len(prior) == 10:
        return prior
    if len(prior) != 11 or any(prior[4:]):
        raise ValueError('requires the four reviewed GXUI v1 controls')
    return [100, prior[0], prior[1], prior[2], 0, prior[3], 0, 0, 0, 0]
