"""Independent typed hashes of the actual driver audit files, not author totals."""
import json
import os
from pathlib import Path
import pickle
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review as V

assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
sys.addaudithook(V.fence)
rows = []
for stem, steps in [('bench-input-' + str(i), 50000000) for i in range(1, 6)] + [('input-segments', 1000054)]:
    states = {}
    for backend in ('reference', 'native'):
        receipt = json.loads((V.RUNS / (stem + '-' + backend + '.json')).read_text())
        state = pickle.loads(zlib.decompress(Path(receipt['audit']).read_bytes()))
        assert state['cpu']['steps'] == steps
        assert len(state['architecture']) == 145
        assert len(state['cpu']['device_types']) == 19
        assert sum(len(r[1]) for r in state['cpu']['regions']) > 100 * 1024 * 1024
        for name, device in zip(state['cpu']['device_types'], state['cpu']['devices']):
            if name == 'SdHost' and device.get('medium_record'):
                device['medium_record']['path'] = '<review-private-medium>'
        states[backend] = V.digest(state)
        del state
    assert states['reference'] == states['native'], stem
    row = dict(case=stem, steps=steps, hashes=states, equal=True)
    rows.append(row)
    print(json.dumps(row), flush=True)
(V.RUNS / 'driver-independent-state-audit.json').write_text(json.dumps(dict(status='PASS', rows=rows), indent=2) + '\n')
