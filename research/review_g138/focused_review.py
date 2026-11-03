"""Observe first-menu rejection and record replacement in the final DAT.

The starting row and settings states are explicit model inputs. This script
does not claim that a physical camera reaches those inputs on its own.
"""
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g138_host as H

OUT = Path(__file__).resolve().parent
ZERO = [100] + [0] * 9


def summary(cam):
    rows, control = cam.unit_rows()
    return dict(row_sha256=[hashlib.sha256(row).hexdigest() for row in rows],
                T=control, mode=cam.s_bytes(0x36e, 1)[0],
                WB=list(cam.s_bytes(0x6dd, 2)), source=cam.s_bytes(8, 1)[0],
                S_sha256=hashlib.sha256(cam.s_bytes(0, 4096)).hexdigest(),
                state=cam.state() if cam.p.image_base else None, lock=cam.lock())


def run():
    H.setup()
    records = []
    cam = H.Camera('50mm')
    # First make a complete state with the real key path, then use its unit
    # rows as an explicitly non-stock startup fixture in another model.
    cam.open_menu()
    cam.press('DOWN')
    assert cam.ui('slot') == 5
    recipe_rows, recipe_t = cam.unit_rows()
    recipe_overlay = dict(cam.p.rpc.overlay)
    boot = H.Camera('50mm')
    stock_rows, stock_t = boot.unit_rows()
    boot.p.rpc.overlay.update(recipe_overlay)
    boot.p.rpc.t = recipe_t
    boot.put_s(0x36e, bytes([4]))
    boot.put_s(0xfd4, H.record_bytes(H.DAT_BYTES[boot.dat_path], 5, 0, ZERO))
    before = summary(boot)
    at = boot.writes()
    boot.open_menu()
    after = summary(boot)
    assert boot.unit_rows() == (recipe_rows, recipe_t)
    assert boot.s_bytes(0x36e, 1) == bytes([4])
    assert before['S_sha256'] == after['S_sha256'] and boot.writes() == at
    assert recipe_rows != stock_rows
    assert not any(label.startswith('>') for label in boot.labels())
    records.append(dict(case='nonstock-rows-with-nonstandard-S',
                        observation='RETAINED_MIXED_MODEL_INPUT', before=before, after=after,
                        unit_writes=boot.writes() - at,
                        native_reachability='NOT_PROVEN'))
    # Request Default for 04 through the normal key path. The constructor's
    # internal stock ledger is not evidence that those unit rows are stock.
    at = boot.writes()
    boot.press('DISP')
    boot.goto(boot.ui('count') - 1)
    boot.press('DISP')
    boot.press('DISP')
    default_state = summary(boot)
    rows_after_default, t_after_default = boot.unit_rows()
    assert boot.s_bytes(0x36e, 1) == bytes([1])
    assert rows_after_default == recipe_rows and rows_after_default != stock_rows
    assert boot.writes() == at
    records.append(dict(case='default04-after-rejected-startup',
                        observation='S_NORMALIZED_WITH_RECIPE_ROWS_RETAINED',
                        after=default_state, unit_writes=boot.writes() - at,
                        expected_stock_T=stock_t, actual_T=t_after_default,
                        native_reachability='STARTING_STATE_IS_SYNTHETIC'))
    # An unknown nonzero tail must not silently become program-owned data
    # under persist_recipe_r2 section 7.1.
    other = H.Camera('50mm')
    unknown = bytes([0xa5]) * 40
    other.put_s(0xfd4, unknown)
    other.open_menu()
    assert other.record() == unknown
    other.press('DOWN')
    replaced = other.record()
    assert replaced == H.record_bytes(H.DAT_BYTES[other.dat_path], 5, 0, ZERO)
    records.append(dict(case='unknown-tail-then-user-selection',
                        observation='UNKNOWN_NONZERO_RECORD_REPLACED',
                        before_sha256=hashlib.sha256(unknown).hexdigest(),
                        after_sha256=hashlib.sha256(replaced).hexdigest(),
                        state=other.state()))
    result = dict(status='OBSERVED', dat_sha256=H.sha(H.DAT), cases=records)
    (OUT / 'evidence/focused-review.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'cases':
                      [{'case': row['case'], 'observation': row['observation']} for row in records]}), flush=True)


if __name__ == '__main__':
    started = time.monotonic()
    run()
    print('focused-review seconds', round(time.monotonic() - started, 3), flush=True)
