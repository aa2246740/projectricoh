"""Adapt the retained host model to the required batch M32R interpreter."""
from pathlib import Path
import atexit
import collections
import json
import os
import sys

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_body_v39/evidence'
sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_batch'))
import backend as batch
sys.path.insert(0, str(ROOT / 'tools/native_harness'))
from backend_api import WriteEvent

INSTANCES = []
original_init = batch.Backend.__init__


def registered(self, *args, **kwargs):
    kwargs['mode'] = 'fast'
    original_init(self, *args, **kwargs)
    self.set_batch(True)
    INSTANCES.append(self)


batch.Backend.__init__ = registered


def save_stats(suffix=''):
    rows = [{'index': i, 'steps': item.steps, 'batch': item.batch,
             'mode': item.mode, 'batch_stats': dict(item.batch_stats)}
            for i, item in enumerate(INSTANCES)]
    name = os.environ.get('REVIEW_CASE', 'batch')
    tail = '-' + suffix if suffix else ''
    (OUT / (name + tail + '-batch.json')).write_text(json.dumps(rows, indent=1) + '\n')


atexit.register(save_stats)


class Registers:
    def __init__(self, cpu):
        self.cpu = cpu

    def __getitem__(self, index):
        if not 0 <= index < 16:
            raise IndexError(index)
        return self.cpu.get_reg('r%d' % index)

    def __setitem__(self, index, value):
        if not 0 <= index < 16:
            raise IndexError(index)
        self.cpu.set_reg('r%d' % index, value)


class CoreState:
    def __init__(self, cpu):
        self.cpu = cpu
        self.registers = Registers(cpu)

    @property
    def r(self):
        return self.registers

    @r.setter
    def r(self, values):
        assert len(values) == 16
        for index, value in enumerate(values):
            self.registers[index] = value

    @property
    def psw(self):
        return self.cpu.get_reg('psw') & 0xff

    @psw.setter
    def psw(self, value):
        self.cpu.set_reg('psw', (self.cpu.get_reg('psw') & ~0xff) | (value & 0xff))

    @property
    def bpsw(self):
        return self.cpu.get_reg('psw') >> 8 & 0xff

    @bpsw.setter
    def bpsw(self, value):
        self.cpu.set_reg('psw', (self.cpu.get_reg('psw') & 0xff) | ((value & 0xff) << 8))

    @property
    def bbpsw(self):
        return self.cpu.get_reg('bbpsw')

    @bbpsw.setter
    def bbpsw(self, value):
        self.cpu.set_reg('bbpsw', value)

    @property
    def acc(self):
        return self.cpu.get_reg('acc')

    @acc.setter
    def acc(self, value):
        self.cpu.set_reg('acc', value)

    @property
    def cr(self):
        return {name: self.cpu.get_reg(name) for name in ('spi', 'spu', 'bpc', 'bbpc', 'evb')}

    @cr.setter
    def cr(self, values):
        for name, value in values.items():
            self.cpu.set_reg(name, value)

    def op(self, *args):
        raise RuntimeError('instruction accounting is outside this adapter')


class CallList(list):
    def __init__(self, cpu, address, values):
        super().__init__(values)
        self.cpu, self.address = cpu, address

    def __call__(self, cpu):
        self.cpu.visits[self.address] += 1
        for fn in tuple(self):
            if fn(cpu) is not False:
                return True
        return False


class ModelPoints(batch.Breakpoints):
    def __init__(self, cpu, values=()):
        self.cpu = cpu
        super().__init__()
        self.update(dict(values))

    def __setitem__(self, address, value):
        entries = list(value) if isinstance(value, (list, tuple)) else [value]
        super().__setitem__(address, CallList(self.cpu, address, entries))

    def update(self, values=(), **keywords):
        for address, value in dict(values, **keywords).items():
            self[address] = value

    def setdefault(self, address, value=None):
        if address not in self:
            self[address] = [] if value is None else value
        return self[address]


class ModelBackend(batch.Backend):
    def __init__(self):
        super().__init__(mode='fast')
        self.core = CoreState(self)
        self.visits = collections.Counter()
        self.tail = collections.deque(maxlen=16)
        self.running = False
        self.origin = 'host'
        self._model_traces = []

    @property
    def breakpoints(self):
        return self._breakpoints

    @breakpoints.setter
    def breakpoints(self, value):
        self._breakpoints = ModelPoints(self, value)

    @property
    def traces(self):
        return self._model_traces

    @traces.setter
    def traces(self, values):
        self._model_traces = []
        self.write_traces = []
        for lo, hi, callback in values:
            self.add_write_trace(lo, hi, callback)

    @property
    def total_steps(self):
        return self.steps

    @property
    def pc(self):
        return self.get_reg('pc')

    @pc.setter
    def pc(self, value):
        self.set_reg('pc', value)

    def get_reg(self, name):
        if name == 'acc':
            return super().get_reg('acch') << 32 | super().get_reg('accl')
        return super().get_reg(name)

    def set_reg(self, name, value):
        if name == 'acc':
            super().set_reg('acch', value >> 32)
            super().set_reg('accl', value & 0xffffffff)
        else:
            super().set_reg(name, value)

    def map(self, base, data, writable=True):
        if not len(data):
            return
        super().map(base, data, writable)
        merged = []
        for address, content, permission in self.regions:
            if merged and merged[-1][0] + len(merged[-1][1]) == address and merged[-1][2] == permission:
                previous, old, flag = merged.pop()
                merged.append((previous, old + content, flag))
            else:
                merged.append((address, content, permission))
        self.regions = merged
        assert len(merged) <= 32

    def add_write_trace(self, lo, hi, callback):
        self._model_traces.append((lo, hi, callback))
        def observed(address, data):
            origin = 'cpu' if getattr(self, '_in_step', False) or self._batching else self.origin
            callback(WriteEvent(address, data, self._pc if self.running else None,
                                origin if self.running else 'host'))
        return super().add_write_trace(lo, min(hi, 0xffffffff), observed)

    def add_breakpoint(self, address, callback):
        self.breakpoints.setdefault(address, []).append(callback)

    def call(self, addr, args, lr_sentinel, max_steps):
        assert not self.running
        self.running = True
        try:
            return super().call(addr, args, lr_sentinel, max_steps)
        finally:
            self.running = False
            self.origin = 'host'


def bind_integration(module):
    defaults = list(module.v.V35Harness.__init__.__defaults__)
    defaults[1] = ModelBackend
    module.v.V35Harness.__init__.__defaults__ = tuple(defaults)


def bind_host(module, target):
    module.LOCAL = target
    module.TMP = Path(os.environ['REVIEW_TEMP']) / 'host-model'
    original = module.accept_module

    def accepted():
        old = original()
        load = old.load

        def loaded(path, name):
            result = load(path, name)
            if name == 'accept_integration':
                bind_integration(result)
            return result
        old.load = loaded
        return old
    module.accept_module = accepted
