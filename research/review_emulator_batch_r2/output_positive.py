"""Exercise explicit caller output and medium paths without policy adapters."""
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_batch'))
import backend
import fat_image
import outputs
import sdcard
import storage_run


def main():
    out = HERE / 'local/output-positive'
    out.mkdir(exist_ok=True)
    assert outputs.require(out) == out
    outputs.declare_media(out)
    path = out / 'medium.img'
    source = ROOT / 'research/emulator_speed/local/card-seed.img'
    shutil.copyfile(source, path)
    fixture = fat_image.inspect(path)
    medium = sdcard.BlockImage(path)
    content = bytes((index * 19 + 7) & 255 for index in range(512))
    medium.write(65000, content)
    assert sdcard.BlockImage(path).read(65000) == content
    storage_run.OUT = out
    original_init = backend.Backend.__init__
    stats = []
    def initialize(cpu, **kwargs):
        original_init(cpu, **kwargs)
        cpu.set_mode('fast')
        cpu.set_batch(True)
        stats.append(cpu.batch_stats)
    backend.Backend.__init__ = initialize
    storage_run.run(SimpleNamespace(name='explicit-output', budget=10000, resume=None, card=path,
                                   card_event=False, stop_at=[], task=None))
    run = json.loads((out / 'explicit-output.json').read_text())
    assert run['stop']['reason'] == 'max_steps' and run['steps'] == 10000
    assert (out / 'explicit-output-stop.pkl').is_file()
    assert sdcard.BlockImage(path).read(65000) == content
    result = {'caller_output_accepted': True, 'fat_inspected': fixture,
              'medium_source': str(source.relative_to(ROOT)),
              'medium_source_sha256': storage_run.sha(source),
              'block_write_reopen_equal': True, 'run_stop': run['stop'],
              'batch_stats': [dict(value) for value in stats], 'passed': True}
    (HERE / 'local/output-positive.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'steps': run['steps']}), flush=True)


if __name__ == '__main__':
    main()
