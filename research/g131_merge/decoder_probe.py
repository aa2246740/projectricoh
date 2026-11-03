"""Capture a retained decoder input through its runtime interface."""
from pathlib import Path
import json

class DataReady(Exception):
    pass

def run(context, arguments, out, sessions):
    kind = context['Session']
    namespace = kind.match.__globals__
    original = namespace['unpack']
    captured = []
    def encode(value):
        if isinstance(value, bytes):
            return dict(bytes_hex=value.hex())
        if isinstance(value, dict):
            return {str(key): encode(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [encode(item) for item in value]
        if isinstance(value, (int, str, float, bool, type(None))):
            return value
        return dict(type=type(value).__name__)
    def capture(raw, unit, slot):
        data = dict(raw=encode(raw), unit=unit, slot=slot,
                    raw_type=type(raw).__name__)
        (out / 'decoder-input.json').write_text(json.dumps(data) + '\n')
        answer = original(raw, unit, slot)
        (out / 'decoder-answer.json').write_text(json.dumps(encode(answer)) + '\n')
        captured.append(1)
        raise DataReady()
    namespace['unpack'] = capture
    try:
        instance = kind(unit='50mm', tag='g131-decoder')
        instance.match()
    except DataReady:
        pass
    finally:
        namespace['unpack'] = original
    assert captured
    print(json.dumps(dict(name='decoder-probe', returncode=0, counts=dict(inputs=len(captured)))))
