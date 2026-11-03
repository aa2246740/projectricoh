"""Run the packaged DAT through the genuine v3.6 H01 constructor.

File reads, link packets, glyph conversion and ticks are explicit device edges.
No host write seeds native UI type, row count, table, cursors, or view stack.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
import zlib
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_common as c
sys.path.insert(0, str(c.ROOT / 'tools/native_harness'))
import field_replay as fr
import harness as hm
import product_execute as pe
import python_backend as pb
from image_loader import Image, Elf

pb.CACHE = c.LOCAL / 'native/decode'
binding = c.load(c.ROOT / 'firmware/engine_v38_b36/native_binding.py', 'probe_native_binding')
pb.CACHE = c.LOCAL / 'native/decode'
DAT = c.LOCAL / 'package/GXRCE.DAT'
ENGINE = c.LOCAL / 'build/probe.elf'
LAYOUT = json.loads((c.LOCAL / 'layout.json').read_text())


class Files:
    def __init__(self, dat):
        product=(c.ROOT/'firmware/package_v36_g117/SD_ROOT/GXRCE.DAT').read_bytes()
        self.paths = {'/ATA1/GXRCE.DAT':dat,'/IROM/GXRCE0.DAT':product,'/IROM/GXRCE1.DAT':product}
        self.live = {}
        self.next_fd = 3

    def open(self, name):
        if name not in self.paths:
            return -1
        self.next_fd += 1
        self.live[self.next_fd] = [name, 0]
        return self.next_fd

    def read(self, fd, buf, size, h):
        if fd not in self.live:
            return -1
        name, pos = self.live[fd]
        chunk = self.paths[name][pos:pos+size]
        if chunk and buf:
            h.b.write(buf, chunk)
        self.live[fd][1] += len(chunk)
        return len(chunk)

    def close(self, fd):
        self.live.pop(fd, None)
        return 0


class Rpc(pe.RpcEdge):
    def __init__(self, image):
        super().__init__(2, image)
        self.backend = pb.PythonBackend()
        image.load(self.backend)
        self.fail_read = False

    def half(self, address):
        if self.fail_read:
            self.fail_read = False
            return None
        return int.from_bytes(self.backend.read(address, 2), 'big')

    def call(self, cmd, value):
        if cmd == 22:
            raise AssertionError('Unit W is forbidden, including failed attempts')
        return super().call(cmd, value)


class Product(pe.Product):
    def __init__(self, h, unit='50mm', t_value=2, ready=1, link=None):
        self.h, self.unit, self.ready, self.link = h, unit, ready, ready if link is None else link
        path, digest, index = pe.UNITS[unit]
        self.dat = DAT.read_bytes()
        self.elf = Elf(ENGINE)
        off, size = struct.unpack_from('>II', self.dat, 132)
        assert next(s for s in self.elf.sections if s['name']=='.engine')['data'] == self.dat[off:off+size]
        self.unit_image = Image(path, digest)
        stock = (c.ROOT/'firmware/package_v36_g117/SD_ROOT/GXRCE.DAT').read_bytes()
        at = int.from_bytes(stock[156:160], 'big')+64*index
        self.identity = stock[at:at+12]
        self.files = Files(self.dat)
        self.rpc = Rpc(self.unit_image)
        self.native_log = []
        self.crc_fast = False
        self.image_base = 0
        self.ticks = 100000
        self.tick_step = 1
        self.tick_log = []
        self._install()
        h.b.map(pe.SCRATCH, bytes(0x1000))
        h.b.map(0xfffffffc, bytes(4))
        # The actual ready publisher replaces a host store to its BSS word.
        require(fr.native(h, 0x200935b4, (ready,)))
        h.b.set_reg('psw', 0x41)
        assert 0x20271fec not in h.b.breakpoints

    def _install(self):
        super()._install()
        self.h.b.breakpoints.pop(0x20271fec, None)
        self.h.b.breakpoints.pop(0x202d6f38, None)
        for address, name in ((0x200a544c,'create'),(0x200a45e8,'write'),(0x200a49d8,'rename'),(0x200a4910,'delete')):
            self.h.b.breakpoints.pop(address, None)
            def forbidden(b, name=name):
                raise AssertionError('File mutation called: '+name)
            self._native(address, 'file_'+name, forbidden)
        def opened(b):
            path=pe.cstr(self.h,b.get_reg('r4'));flags=b.get_reg('r5')
            assert flags==0, (path, flags)
            self.native_log.append(dict(op='open',path=path,flags=flags))
            return self.files.open(path)
        self.h.b.breakpoints.pop(0x200a40b4,None)
        self._native(0x200a40b4,'file_open',opened)
        def tick(b):
            value=self.ticks & 0xffffffff
            self.tick_log.append(dict(value=value,psw=b.get_reg('psw'),sp=b.get_reg('r15')))
            self.ticks=(self.ticks+self.tick_step)&0xffffffff
            return value if b.get_reg('psw')&0x40 else 0
        self._native(0x2005f164,'raw_tick',tick)

    def state_address(self):
        block=self.h.u(pe.ROOT_ADDR+56)
        self.image_base=self.h.u(block+312)
        return self.image_base+LAYOUT['n']

    def state(self):
        base=self.state_address()
        return {name:self.h.u(base+offset) for name,offset in LAYOUT['fields'].items()
                if name not in ('refs','samples','admission','baseline','rows','binding')}

    def rows(self):
        base=self.state_address()+LAYOUT['fields']['rows']
        return [self.h.b.read(base+40*i,40).split(b'\0',1)[0].decode('ascii') for i in range(8)]

    def raw_samples(self):
        state=self.state();base=self.state_address()+LAYOUT['fields']['samples']
        return [dict(zip(('start','end','count','kind','target','crc','valid'),
                    struct.unpack('>7I',self.h.b.read(base+i*28,28)))) for i in range(state['used'])]

    def raw_refs(self):
        state=self.state();base=self.state_address()+LAYOUT['fields']['refs']
        return [dict(zip(('start','end','delta','valid','run'),
                    struct.unpack('>5I',self.h.b.read(base+i*20,20)))) for i in range(state['ref_count'])]


def require(result):
    assert result.get('ok'), result
    return result


def bind():
    hm.Harness=binding.V35Harness
    pe.STAGED,pe.STAGED_SHA,pe.ENGINE_ELF=DAT,c.sha(DAT),ENGINE
    mount=c.ROOT/'firmware/package_v36_g117/SD_ROOT/l08firm3'
    pe.UNITS['mount']=(mount,c.sha(mount),2)
    fr.Product=Product
    elf=Elf(c.RESIDENT)
    fr.OBSERVE=elf.symbols['rv_hook_observe']
    fr.LAND={elf.symbols['rv_skip_06']:'h06_skip',elf.symbols['rv_close_07']:'h07_close',elf.symbols['rv_skip_08']:'h08_skip',
             0x202871dc:'native_setter',0x202bb96c:'native_h08'}


def boot(unit='50mm'):
    bind()
    h,p,w=fr.boot(unit)
    return h,p,w


def open_menu(h,p):
    require(fr.open_settings(h))
    assert h.u(pe.ROOT_ADDR+5,1)==3,fr.root_fields(h)
    assert h.u(0x2022f5ac,1)==8,(p.rows(),fr.root_fields(h),p.state())
    p.state_address()
    if not p.crc_fast:
        p.accelerate_crc(p.image_base)
    return p.rows()


def reopen(h,p):
    h.parent()
    return open_menu(h,p)


def move(h,target):
    for _ in range(8):
        if h.u(0x2022f726,1)==target:
            return
        require(fr.move_key(h,0x20))
    raise AssertionError('cursor failed')


def smoke():
    h,p,w=boot()
    pre=h.state()
    rows=open_menu(h,p)
    result=dict(status='PASS',before=pre,after=h.state(),rows=rows,state=p.state(),
                calls=h.calls,source=h.u(h.u(pe.ROOT_ADDR+56)+328),
                getter_stub_hits=h.stub_hits.get('image_mode_getter',0),getter_visits=h.b.visits[0x20271fec],
                rpc_commands=sorted(set(x['cmd'] for x in p.rpc.log)))
    c.save(c.RESEARCH/'evidence/native-smoke.json',result)
    print(json.dumps({k:result[k] for k in ('rows','state','source','getter_stub_hits','getter_visits','rpc_commands')},indent=2),flush=True)


if __name__=='__main__':
    smoke()
