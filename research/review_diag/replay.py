"""Replay supplied final-DAT tests without writing to their input directories."""
from pathlib import Path
import argparse
import importlib
import json
import os
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCE = ROOT / 'research/diag_dat_v1'
sys.path.insert(0, str(SOURCE))
import scope
scope.ALLOWED = (OUT,)
import trace
import native_support as ns
ns.v.python_backend.CACHE = OUT / 'local/decode' / str(os.getpid())

BaseAudit = trace.Audit


class ReviewAudit(BaseAudit):
    def __init__(self, h, p, arm):
        self.row_stores = []
        self.review_private_blocks = []
        self.preset_writes = [e for e in h.writes if any(
            lo <= int(e['address'], 16) < hi for lo, hi in ns.UI_RANGES)
            and e['origin'] not in ('cpu', 'model:native_memset')]
        super().__init__(h, p, arm)

    def enter(self):
        block = self.h.u(ns.pe.ROOT_ADDR + 56)
        length = self.h.u(ns.pe.ROOT_ADDR + 104)
        if block:
            assert self.h.u(0x200d3488) <= block < block + length <= self.h.u(0x200d348c)
            pair = (block, length)
            if pair not in self.review_private_blocks:
                self.review_private_blocks.append(pair)
        super().enter()

    def classify(self, event):
        address, size, *_ = event
        if any(base <= address and address + size <= base + length
               for base, length in self.review_private_blocks):
            return 'dat_private'
        return super().classify(event)

    def write(self, event):
        super().write(event)
        if event.address <= 0x2022f5ac < event.address + len(event.data):
            self.row_stores.append(dict(value=self.h.u(0x2022f5ac, 1),
                pc=hex(event.pc) if event.pc is not None else None,
                origin=event.origin, dat_active=self.active, external=self.external))

    def result(self, check=True):
        result = super().result(check)
        invalid = [e for e in self.row_stores if e['dat_active'] and not e['external'] and e['value'] != 8]
        current_settings = self.h.b.read(self.h.settings, 0xc9e)
        settings_diff = [dict(offset=hex(i), before=a, after=b)
            for i, (a,b) in enumerate(zip(self.initial_settings, current_settings)) if a != b]
        result.update(review_row_stores=self.row_stores,
            review_invalid_DAT_row_stores=invalid,
            review_boot_host_UI_presets=self.preset_writes,
            review_all_rpc_model_calls=len(self.p.rpc.log),
            review_settings_diff=settings_diff,
            review_validated_private_blocks=self.review_private_blocks)
        if check:
            assert not invalid, invalid
            assert not self.preset_writes, self.preset_writes
            assert not self.p.rpc.log, self.p.rpc.log
        return result


trace.Audit = ReviewAudit
for name in ('functional', 'cutpoints', 'h01_cuts', 'variants'):
    importlib.import_module(name)
for module in list(sys.modules.values()):
    if getattr(module, '__file__', None) and Path(module.__file__).parent == SOURCE:
        if hasattr(module, 'OUT'):
            module.OUT = OUT
scope.OUT = OUT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('script', choices=('functional', 'cutpoints', 'h01_cuts', 'variants', 'probes', 'errors'))
    args, remaining = parser.parse_known_args()
    started = time.time()
    with (OUT / 'local/commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(argv=sys.argv, cwd=str(ROOT), started=started,
            runner_sha256=scope.sha(Path(__file__)))) + '\n')
    if args.script in ('probes', 'errors'):
        sys.path.insert(0, str(OUT))
        module = importlib.import_module(args.script)
    else:
        module = sys.modules[args.script]
    if args.script == 'functional':
        p = argparse.ArgumentParser()
        p.add_argument('--unit', required=True)
        module.run(p.parse_args(remaining).unit)
    else:
        sys.argv = [str(SOURCE / (args.script + '.py')), *remaining]
        module.main()
    print('ELAPSED_SECONDS', round(time.time() - started, 3), flush=True)


if __name__ == '__main__':
    main()
