"""Verify old checkpoint acceptance and strict candidate snapshot rejection."""
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable, admit_medium
enable()
TOOLS = ROOT / 'tools/gxr_emulator_batch'
sys.path.insert(0, str(TOOLS))
import sdcard
import storage_run
import speed_snapshot as snap
from input_run import CheckpointReader
admit_medium(sdcard)


def main():
    out = HERE / 'local/checkpoints'
    out.mkdir(exist_ok=True)
    result = {}
    for suffix in ['.pkl', '.json']:
        source = ROOT / ('research/emulator_speed/local/cold-speed-r1-stop' + suffix)
        shutil.copyfile(source, out / ('frozen-stop' + suffix))
    storage_run.OUT = out
    path = out / 'frozen-stop.pkl'
    meta = json.loads(path.with_suffix('.json').read_text())
    assert meta['library_sha256'] == 'ba1efa53ce71dbd5632b2a540d0ca3ad02c395498688ce90089a41d85e8c07ff'
    assert storage_run.sha(path) == meta['sha256']
    with path.open('rb') as stream:
        frozen_state = CheckpointReader(stream).load()
    machine = storage_run.Machine(resume=path)
    try:
        restored_state = machine.cpu.snapshot()
        result['storage_restore'] = {'steps': machine.cpu.steps, 'pc': machine.cpu.get_reg('pc'),
                                     'library_sha256': meta['library_sha256'], 'accepted': True,
                                     'frozen_state_hash': snap.value_hash(frozen_state),
                                     'restored_state_hash': snap.value_hash(restored_state)}
        assert machine.cpu.steps == meta['steps']
        assert machine.cpu.get_reg('pc') == meta['pc']
        assert result['storage_restore']['frozen_state_hash'] == result['storage_restore']['restored_state_hash']
    finally:
        machine.close()
    source = ROOT / 'tools/gxr_emulator/local/speed/no-card.snap.z'
    path = out / 'no-card.snap.z'
    shutil.copyfile(source, path)
    shutil.copyfile(source.with_suffix('.json'), path.with_suffix('.json'))
    original_private = snap.private
    def private(value):
        value = Path(value).resolve()
        return value if value.is_relative_to(out) else original_private(value)
    snap.private = private
    try:
        machine, _ = snap.load(path, allow_idle_task=True)
    except ValueError as error:
        result['candidate_restore'] = {'accepted': False, 'message': str(error),
                                        'file_sha256': storage_run.sha(source)}
        assert str(error).startswith('boot identity differs; ')
    else:
        machine.close()
        raise AssertionError('old candidate identity was unexpectedly accepted')
    (HERE / 'local/checkpoints.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
