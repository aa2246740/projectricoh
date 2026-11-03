"""Retain real CPU/device state and drive native input scans in private media."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import re
import shutil
import struct
import subprocess
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/tweak-memory-r1')
TOOL = ROOT/'research/tooling_m32r/prefix/bin'
GCC = ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def models():
    sys.path.insert(0, str(ROOT/'tools/gxr_emulator_standby'))
    module('unit_link', HERE/'emulator/unit_link_copy.py')
    module('v310_preview_link', HERE/'emulator/preview_link.py').install()
    if (HERE/'emulator/menu_notice_peer.py').exists():
        module('r2_menu_notice',HERE/'emulator/menu_notice_peer.py')
    if 'GXR_TWEAK_UNIT68_RESULT' in os.environ:
        module('tm_ready_peer', HERE/'emulator/ready_peer.py').install()
    import devices
    if 'word_columns' not in devices.NAND.contract:
        module('v310_word_nand', HERE/'emulator/nand_word.py').install()
    for stem in ('nand_read_tail', 'sd_long_response', 'panel_lever'):
        module('tm_'+stem, HERE/'emulator'/(stem+'.py')).install()
    import panel
    panel.KEY_CODES['DOWN'] = 16
    panel.KEY_CODES['RIGHT'] = 18
    panel.KEY_CODES['MENU'] = 24


def load_snapshot(path):
    models()
    return pickle.loads(zlib.decompress(path.read_bytes()))


def snapshot_dat(saved):
    path=Path(saved['dat_path'])
    if not path.exists() or sha(path.read_bytes())!=saved['dat_sha256']:
        candidates=[p for p in (HERE/'local/p1-before').rglob('GXRCE.DAT')
                    if sha(p.read_bytes())==saved['dat_sha256']]
        assert candidates,('retained DAT not found',saved['dat_sha256'])
        path=candidates[0]
    raw=path.read_bytes();assert sha(raw)==saved['dat_sha256']
    return raw


def symbols(elf):
    table = {}
    for line in subprocess.check_output([str(TOOL/'m32r-elf-objdump'), '-t', str(elf)], text=True).splitlines():
        fields = line.split()
        if len(fields) >= 5:
            try:
                table[fields[-1]] = int(fields[0], 16)
            except ValueError:
                pass
    return table


def layout(engine):
    """Ask the target compiler for actual structure offsets, without linking."""
    product = engine.resolve()/'candidate/containers/product'
    fields = {
        'adapter.c': ('Integrated', ['ui.text', 'ui.levels', 'ui.saved', 'ui.screen', 'ui.cur',
            'ui.top', 'ui.physical', 'ui.count', 'ui.slot', 'ui.param', 'ui.applied_user', 'ui.effect',
            'ui.confirmed_user', 'values']),
        'src/firmware/engine/core/eng_core.c': ('Engine', ['live', 'current', 'tweak',
            'memory_dirty', 'current_user', 'memory_blocked', 'settings_pending', 'stage',
            'staging', 'memory_want', 's_unwritten', 'uncertain', 'write_started'])}
    out = {}
    for index, (name, (kind, names)) in enumerate(fields.items()):
        source = TEMP/(engine.name+'-'+str(os.getpid())+'-layout-'+str(index)+'.c')
        obj = source.with_suffix('.o')
        binary = source.with_suffix('.bin')
        source.write_text('#include <stddef.h>\n#include "'+str(product/name)+'"\n'
            'const unsigned tm_layout[] __attribute__((section(".tm_layout")))={'+
            ','.join('offsetof('+kind+','+field+')' for field in names)+'};\n')
        subprocess.run([str(GCC), '-Os', '-ffreestanding', '-fno-builtin',
            '-std=c11', '-m32r', '-msdata=none', '-DG155_BOOT=1',
            '-DPN_CORE_HEADER="../core/eng_core.h"', '-DPN_GXTS_SHARED_PARAMETER',
            '-I', str(product), '-c', str(source), '-o', str(obj)], check=True,
            stdout=subprocess.DEVNULL)
        dump = subprocess.check_output([str(TOOL/'m32r-elf-objdump'), '-s',
            '-j', '.tm_layout', str(obj)], text=True)
        words = []
        for line in dump.splitlines():
            columns = line.split()
            if columns and re.fullmatch('[0-9a-f]{4,8}', columns[0]):
                for word in columns[1:5]:
                    if re.fullmatch('[0-9a-f]{8}', word):
                        words.append(word)
        values = struct.unpack('>'+str(len(names))+'I', bytes.fromhex(''.join(words)))
        out.update({('n.' if index == 0 else 'g.')+key: value for key, value in zip(names, values)})
    return out


class Runtime:
    def __init__(self, source, name, engine=None, elf=None):
        assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
        assert Path(os.environ['TMPDIR']).resolve() == TEMP
        self.source, self.name = source, name
        self.saved = load_snapshot(source)
        import outputs
        outputs.declare_media(TEMP)
        from storage_run import Machine
        sd = next(d for t, d in zip(self.saved['cpu']['device_types'], self.saved['cpu']['devices']) if t == 'SdHost')
        record = sd['medium_record']
        medium = None
        if record:
            retained = Path(record['path'])
            if not retained.exists() or sha(retained.read_bytes()) != record['sha256']:
                retained = HERE/'local/media'/(record['sha256']+'.img')
            assert sha(retained.read_bytes()) == record['sha256']
            medium = TEMP/(name+'.img')
            assert not medium.exists(), medium
            shutil.copyfile(retained, medium)
            sd['medium_record'] = dict(record, path=str(medium))
        self.machine = Machine(str(medium) if medium else None)
        self.cpu = self.machine.cpu
        self.cpu.restore(self.saved['cpu'])
        if 'GXR_TWEAK_UNIT68_RESULT' in os.environ:
            import unit_link
            prior = self.machine.devices['startup'].standby_model
            declared = unit_link.UnitLink(prior.unit, dict(prior.inputs))
            declared.events, declared.sequence = prior.events, prior.sequence
            self.machine.devices['startup'].standby_model = declared
        self.cpu.set_mode('fast')
        self.cpu.set_batch(True)
        from panel import Panel
        self.panel = Panel(self.cpu, self.machine.devices)
        self.panel.chain(self.cpu)
        self.inputs, self.events, self.calls, self.pending = [], [], [], []
        self.native_settings = []
        def settings_save(cpu):
            address, length = cpu.get_reg('r4'), cpu.get_reg('r5')
            row = dict(step=cpu.steps, call='native-settings-save',
                S=hex(self.u(0x200c0dac)), record=cpu.read(self.u(0x200c0dac)+0xfd4, 40).hex())
            self.native_settings.append(row)
            return False
        def settings_write(cpu):
            address, length = cpu.get_reg('r4'), cpu.get_reg('r5')
            if length == 4096 and 0x20000000 <= address <= 0x20800000-length:
                data = cpu.read(address, length)
                path = HERE/'local'/(self.name+'-native-store-'+str(cpu.steps)+'.bin')
                path.write_bytes(data)
                self.native_settings.append(dict(step=cpu.steps, call='native-settings-store',
                    path=str(path.relative_to(ROOT)), sha256=sha(data), record=data[0xfd4:0xffc].hex()))
                row = self.native_settings[-1]
                task, ret = self.machine.task(), cpu.get_reg('lr')
                prior = cpu.breakpoints.get(ret)
                def store_return(current):
                    result = prior(current) if prior else False
                    if self.machine.task() == task and 'return_step' not in row:
                        row.update(return_step=current.steps, result=current.get_reg('r0'))
                    return result
                cpu.add_breakpoint(ret, store_return)
            return False
        self.cpu.add_breakpoint(0x20067bb4, settings_save)
        self.cpu.add_breakpoint(0x200997cc, settings_write)
        self.engine = engine
        self.base = None
        self.observe_call(0x20287080, 'native-image-constructor')
        if engine:
            self.dat = snapshot_dat(self.saved)
            assert sha(self.dat) == self.saved['dat_sha256']
            self.sym = symbols(elf)
            self.offsets = layout(engine)
            def loaded(address=None, data=None):
                code = self.u(0x20054770)
                if not 0x20000000 <= code < 0x20800000 or self.base is not None:
                    return
                self.base = code-int.from_bytes(self.dat[132:136], 'big')
                for name in ('ig_menu', 'ig_apply', 'ig_event', 'ig_panel_open', 'ig_panel_event'):
                    if name in self.sym:
                        self.observe_call(self.base+self.sym[name], name)
                if os.environ.get('GXR_TWEAK_CAPTURE_RECORD')=='1' and 'rv_call' in self.sym:
                    captured=[]
                    def record_store(cpu):
                        if not captured and cpu.get_reg('r0')==6 and cpu.get_reg('r1')==5:
                            captured.append(self.save('record-store-input'))
                        return False
                    self.cpu.add_breakpoint(self.base+self.sym['rv_call'],record_store)
            self.cpu.add_write_trace(0x20054770, 0x20054774, loaded)
            loaded()

    def u(self, address, n=4):
        return int.from_bytes(self.cpu.read(address, n), 'big')

    def at(self, name):
        symbol, _ = name.split('.', 1)
        return self.base+self.sym[symbol]+self.offsets[name]

    def levels(self, name='n.ui.levels'):
        return list(struct.unpack('>10h', self.cpu.read(self.at(name), 20)))

    def state(self, label):
        S = self.u(0x200c0dac)
        row = dict(label=label, step=self.cpu.steps, state=self.u(0x205d9c00),
            activity=self.u(0x205d9bf8), word=self.u(0x200547ec),
            rows=self.u(0x2022f5ac, 1), cursor=self.u(0x2022f726, 1),
            cached_cursor=self.u(0x205a2944, 1), record=self.cpu.read(S+0xfd4, 40).hex(),
            W_T=self.writes())
        if self.engine and self.base is not None and self.u(0x20054705, 1) == 3:
            row.update({key:self.u(self.at('n.ui.'+key), 1) for key in
                ('screen', 'cur', 'top', 'physical', 'count', 'slot', 'param', 'applied_user', 'effect')})
            raw = self.cpu.read(self.at('n.ui.text'), 8*14)
            row['text'] = [raw[i:i+14].split(b'\0', 1)[0].decode('ascii') for i in range(0, 8*14, 14)]
            row['levels'] = self.levels()
            row['engine_levels'] = self.levels('g.tweak')
        self.events.append(row)
        return row

    def writes(self):
        return sum(x['cmd'] == 22 for x in self.machine.devices['startup'].rpc_state.get('log', []))

    def observe_call(self, address, name):
        def entered(cpu):
            row = dict(name=name, step=cpu.steps, task=self.machine.task())
            self.calls.append(row)
            self.pending.append(row)
            ret, task = cpu.get_reg('lr'), self.machine.task()
            prior = cpu.breakpoints.get(ret)
            def returned(c):
                old = prior(c) if prior else False
                if self.machine.task() == task and 'return_step' not in row:
                    row.update(return_step=c.steps, result=c.get_reg('r0'))
                    self.pending.remove(row)
                    if prior:
                        c.add_breakpoint(ret, prior)
                    else:
                        c.breakpoints.pop(ret, None)
                return old
            cpu.add_breakpoint(ret, returned)
            return False
        self.cpu.add_breakpoint(address, entered)

    def run(self, count):
        stop = self.cpu.run(count)
        if stop.reason != 'max_steps':
            raise RuntimeError('native session stopped: '+str(stop.to_dict()))
        return stop

    def key(self, name, quiet=2_000_000):
        self.inputs.append(self.panel.set_key(name, True))
        self.run(400_000)
        self.inputs.append(self.panel.set_key(name, False))
        for _ in range(90):
            self.run(10_000_000)
            if not self.pending:
                self.run(quiet)
                if not self.pending:
                    break
        else:
            raise RuntimeError('native call did not finish within 900 M steps')
        row = self.state('after-'+name)
        print(json.dumps(dict(name=self.name, step=self.cpu.steps, key=name,
            screen=row.get('screen'), levels=row.get('levels'), pending=len(self.pending))), flush=True)
        return row

    def open_menu(self):
        for key in ('ADJ', *['ADJ_RIGHT']*5):
            row = self.key(key)
            if row['activity'] == 8 and row['rows'] == 8:
                return row
        raise RuntimeError('Image Settings was not opened')

    def save(self, label):
        state = self.cpu.snapshot()
        for device in state['devices']:
            if isinstance(device, dict):
                for key in list(device):
                    if callable(device[key]):
                        del device[key]
        data = dict(self.saved, cpu=state, native_state_presets=[], source_name=self.name)
        path = HERE/'local'/(self.name+'-'+label+'.pkl.z')
        assert not path.exists(), path
        path.write_bytes(zlib.compress(pickle.dumps(data, protocol=4), 3))
        sd = next(d for t, d in zip(state['device_types'], state['devices']) if t == 'SdHost')
        if sd['medium_record']:
            rec = sd['medium_record']
            target = HERE/'local/media'/(rec['sha256']+'.img')
            if not target.exists():
                shutil.copyfile(rec['path'], target)
        return dict(path=str(path.relative_to(ROOT)), sha256=sha(path.read_bytes()), steps=self.cpu.steps)

    def settings(self, label):
        raw = self.cpu.read(self.u(0x200c0dac), 4096)
        path = HERE/'local'/(self.name+'-'+label+'-S.bin')
        path.write_bytes(raw)
        block = bytearray(raw)
        block[-4:] = (sum(struct.unpack('>2046H', block[:0xffc])) & 0xffffffff).to_bytes(4, 'big')
        persisted = path.with_name(path.stem+'-persistent.bin')
        persisted.write_bytes(block)
        assert raw[:4092] == block[:4092]
        return dict(path=str(path.relative_to(ROOT)), sha256=sha(raw),
            persistent_path=str(persisted.relative_to(ROOT)), persistent_sha256=sha(block),
            first_4092_equal=True, record=raw[0xfd4:0xffc].hex())
