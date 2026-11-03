"""Exercise the actual m2.py detail and idle options in fast mode."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
impl = sys.argv[1]
TOOLS = ROOT / ('tools/gxr_emulator' if impl == 'step' else 'tools/gxr_emulator_batch')
sys.path.insert(0, str(TOOLS))
import backend
import m2


def main():
    m2.OUT = HERE / 'local' / ('m2-options-' + impl)
    m2.OUT.mkdir()
    original_factory, original_load, original_install = m2.Backend, m2.Image.load, m2.install

    def factory(**kw):
        cpu = original_factory(**{'mode': 'fast', **kw})
        if impl == 'batch':
            cpu.set_batch(True)
        return cpu
    m2.Backend = factory
    cases = {}
    for idle in [False, True]:
        def load(image, cpu):
            original_load(image, cpu)
            if idle:
                # A short synthetic instruction window at the native idle PC isolates this option.
                cpu.write(0x0500c884, bytes.fromhex('70007000') * 12)
                cpu.set_reg('pc', 0x0500c884)

        def install(cpu, **kw):
            result = original_install(cpu, **kw)
            if idle:
                result['timer'].regs = {(0xff701896, 2): 1, (0xff70188a, 2): 10}
                result['timer'].counter = 2
            return result
        m2.Image.load, m2.install = load, install
        args = SimpleNamespace(image='official', profile='m2', name='idle' if idle else 'detail',
            budget=12, resume=None, output_dir=None, board_m2b=False, synthetic_unit_ready=False,
            nand_pages=None, dma_rx=None, hsp_rx=[], hsp_hello=False, hsp_rpc_errors=False,
            hsp_rpc8=False, adc_sample=[], checkpoints=False, idle_tick=idle, watch=[], stop_at=[],
            detail_after=5)
        result = m2.run(args)
        selected = ['steps', 'stop', 'registers', 'diagnostic_registers', 'idle_clock',
                    'idle_tick_enabled', 'timer_expirations', 'irq_delivered']
        cases[args.name] = {k: result[k] for k in selected}
    (HERE / 'local' / ('m2-options-' + impl + '.json')).write_text(json.dumps(cases, indent=2) + '\n')


if __name__ == '__main__':
    main()
