#!/usr/bin/env python3
"""Offline GXR arithmetic and evidence extraction. Run: python3 -I -B analyze.py.

No device, network, assembler, image patching or RPC implementation is present.
All derived firmware data and instruction listings stay in ignored local/.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
FIRM = ROOT / 'artifacts/firmware/gxr-1.51'
READS = {}
OFFICIAL = {
    'jlaunch3':'951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673',
    'jlaunch8':'92554edf413e0090550f192973d0555ee13770cee0764802be209f491f2c424f',
    'ilaunch3':'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    p = Path(path).resolve()
    data = p.read_bytes()
    READS[str(p.relative_to(ROOT))] = sha(data)
    return data


def save(path, obj):
    p = LOCAL / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


class Image:
    def __init__(self, name):
        self.name = name
        self.data = read(FIRM / name)
        assert sha(self.data) == OFFICIAL[name], name
        self.sections = [(o + 512, v, n) for o, v, n, _, _ in
                         (struct.unpack_from('>IIIII', self.data, 32+i*20)
                          for i in range(16))]

    def offset(self, va):
        for o, v, n in self.sections:
            if v <= va < v+n:
                return o + va-v
        raise ValueError(f'unmapped {va:#x}')

    def bytes(self, va, n):
        o = self.offset(va)
        return self.data[o:o+n]


def script():
    data = read(FIRM / 'jlaunch8')
    assert sha(data) == OFFICIAL['jlaunch8']
    domain = cursor = None
    mem, origins = {}, {}
    pos = 512
    lines = data[512:].splitlines(keepends=True)
    for number, line in enumerate(lines, 1):
        s = line.strip().decode('latin1')
        m = re.fullmatch(r'([XVWU])([0-9A-Fa-f]{4})', s)
        if m:
            op, value = m[1], int(m[2], 16)
            if op == 'U':
                domain = value
            elif op == 'V':
                cursor = value
            elif op == 'W':
                assert domain == 0xEEF1 and cursor is not None
                for i, b in enumerate(value.to_bytes(2, 'big')):
                    mem[cursor+i] = b
                    origins[cursor+i] = {'line': number, 'file_offset': hex(pos),
                                         'token': s, 'cursor': hex(cursor)}
        elif s and not s.startswith('#'):
            raise ValueError((number, s))
        pos += len(line)
    return mem, origins


class Listing:
    def __init__(self, image):
        self.rows = {}
        self.image = image
        for p in sorted((ROOT / 'research/tooling_m32r/disasm').glob(image.name+'-sec*.disasm.txt')):
            for no, line in enumerate(read(p).decode().splitlines(), 1):
                a = line.split('\t')
                if len(a) < 3 or not re.fullmatch(r'\s*[0-9a-f]+:', a[0]):
                    continue
                va = int(a[0][:-1], 16)
                raw = bytes.fromhex(a[1])
                self.rows[va] = (len(raw), a[2], raw, str(p.relative_to(ROOT)), no)

    def get(self, va):
        row = self.rows[va]
        assert self.image.bytes(va, row[0]) == row[2], hex(va)
        return row

    def excerpt(self, lo, hi, name):
        rows = []
        for va in sorted(self.rows):
            if lo <= va < hi:
                n, asm, raw, p, no = self.get(va)
                rows.append(f'{va:08x} file={self.image.offset(va):#x} {raw.hex(" ")}  {asm}  [{p}:{no}]')
        assert rows, name
        path = LOCAL / 'evidence' / (name + '.disasm.txt')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'# {self.image.name} SHA-256 {sha(self.image.data)}\n' + '\n'.join(rows) + '\n')
        return {'image': self.image.name, 'range': [hex(lo), hex(hi)],
                'file_offset': hex(self.image.offset(lo)), 'rows': len(rows),
                'path': str(path.relative_to(HERE))}


def signed(value, bits=32):
    return value - (1 << bits) if value & (1 << (bits-1)) else value


class Arithmetic:
    """Bounded interpretation of verified scalar listing, without executing binary.

    Calls are rejected except explicitly modeled pure getters and the type-32
    write collector. Memory is a Python dictionary; MMIO stores are collected.
    Unknown reads fail. This models CPU arithmetic, never ISP pixel behavior.
    """
    def __init__(self, listing, defaults):
        self.listing = listing
        self.image = listing.image
        self.mem = {}
        self.reg = {f'r{i}': 0 for i in range(16)}
        self.reg['r15'] = 0x70010000
        self.reg['r14'] = 0x7FFFFFFC
        self.c = False
        self.mmio = {}
        self.trace = []
        self.read_addresses = set()
        self.write_addresses = set()
        self.calls = []
        for i, b in enumerate(self.image.bytes(0x200B81D4, 0x4000)):
            self.mem[0x20022000+i] = b
        for off, b in defaults.items():
            self.mem[0x20022000+off] = b

    @staticmethod
    def regname(name):
        return {'sp': 'r15', 'lr': 'r14', 'fp': 'r13'}.get(name, name)

    def value(self, text):
        if text.startswith('#'):
            return int(text[1:], 0)
        if text.startswith('0x'):
            return int(text, 16)
        return self.reg[self.regname(text)]

    def put(self, name, value):
        self.reg[self.regname(name)] = value & 0xFFFFFFFF

    def load(self, addr, n, sign=False):
        self.read_addresses.update(range(addr, addr+n))
        bs = []
        for a in range(addr, addr+n):
            if a in self.mem:
                bs.append(self.mem[a])
            else:
                bs.append(self.image.bytes(a, 1)[0])
        v = int.from_bytes(bytes(bs), 'big')
        return signed(v, 8*n) if sign else v

    def store(self, addr, value, n):
        self.write_addresses.update(range(addr, addr+n))
        if addr >= 0xF0000000:
            self.mmio[addr] = value & ((1 << (8*n))-1)
            return
        for i, b in enumerate((value & ((1 << (8*n))-1)).to_bytes(n, 'big')):
            self.mem[addr+i] = b

    def address(self, operand, n):
        m = re.fullmatch(r'@\((-?\d+),(\w+)\)', operand)
        if m:
            return (self.value(m[2]) + int(m[1])) & 0xFFFFFFFF
        m = re.fullmatch(r'@(\w+)\+', operand)
        if m:
            a = self.value(m[1]); self.put(m[1], a+n); return a
        m = re.fullmatch(r'@\+(\w+)', operand)
        if m:
            a = self.value(m[1])+n; self.put(m[1], a); return a
        assert operand.startswith('@'), operand
        return self.value(operand[1:])

    def call(self, target):
        if target == 0x20115B30:
            self.put('r0', 0x20383F08)
        elif target == 0x20115638:
            self.put('r0', 28 if self.value('r4') == 0 else 29)
        elif target == 0x20255740:
            typ, ap, src, count = [self.value(f'r{i}') for i in (4,5,6,7)]
            assert typ == 32 and count <= 32
            addr = self.load(ap, 4)
            values = [self.load(src+4*i, 4) for i in range(count)]
            self.calls.append({'address': hex(addr), 'values': [hex(x) for x in values]})
            self.mmio.update({addr+4*i: value for i, value in enumerate(values)})
            self.put('r0', 0)
        elif target == 0x202569A0:
            ap, dp = self.value('r4'), self.value('r5')
            for _ in range(100):
                a, d = self.load(ap,4), self.load(dp,4)
                addr = self.load(a,4)
                if not addr:
                    break
                self.store(addr,self.load(d,4),4)
                self.store(ap,a+4,4); self.store(dp,d+4,4)
            else:
                raise ValueError('descriptor sentinel not reached')
        else:
            raise ValueError(f'unmodeled call {target:#x}')

    def run(self, start, max_steps=100000):
        pc = start
        for _ in range(max_steps):
            if pc == 0x7FFFFFFC:
                return
            n, asm, _, _, _ = self.listing.get(pc)
            self.trace.append(pc)
            next_pc = pc+n
            for instruction in re.split(r' -> | \|\| ', asm):
                op, _, operands = instruction.partition(' ')
                args = re.split(r',(?!(?:[^()]*)\))', operands) if operands else []
                v = self.value
                if op == 'nop':
                    continue
                if op in ('mv', 'ldi', 'ld24'):
                    self.put(args[0], v(args[1]))
                elif op == 'seth':
                    self.put(args[0], v(args[1]) << 16)
                elif op in ('add3', 'and3', 'or3', 'sll3', 'srl3', 'sra3'):
                    a, b = v(args[1]), v(args[2])
                    value = {'add3': lambda:a+b, 'and3':lambda:a&b, 'or3':lambda:a|b,
                             'sll3':lambda:a<<b, 'srl3':lambda:a>>b,
                             'sra3':lambda:signed(a)>>b}[op]()
                    self.put(args[0], value)
                elif op in ('add', 'addi', 'sub', 'and', 'or', 'xor', 'mul', 'slli', 'srli', 'srai'):
                    a, b = v(args[0]), v(args[1])
                    value = {'add':lambda:a+b, 'addi':lambda:a+b, 'sub':lambda:a-b,
                             'and':lambda:a&b, 'or':lambda:a|b, 'xor':lambda:a^b,
                             'mul':lambda:a*b, 'slli':lambda:a<<b,
                             'srli':lambda:a>>b, 'srai':lambda:signed(a)>>b}[op]()
                    self.put(args[0], value)
                elif op == 'neg':
                    self.put(args[0], -v(args[1]))
                elif op.startswith('cmp'):
                    a, b = v(args[0]), v(args[1])
                    self.c = a < b if op in ('cmpu','cmpui') else signed(a) < signed(b & 0xFFFFFFFF)
                elif op in ('ld','lduh','ldub','ldh','ldb'):
                    size = {'ld':4,'lduh':2,'ldub':1,'ldh':2,'ldb':1}[op]
                    self.put(args[0], self.load(self.address(args[1],size),size,op in ('ldh','ldb')))
                elif op in ('st','sth','stb'):
                    size = {'st':4,'sth':2,'stb':1}[op]
                    value = v(args[0]); addr = self.address(args[1],size)
                    self.store(addr,value,size)
                elif op == 'push':
                    value = v(args[0]); self.put('sp',v('sp')-4); self.store(v('sp'),value,4)
                elif op == 'pop':
                    value = self.load(v('sp'),4); self.put('sp',v('sp')+4); self.put(args[0],value)
                elif op == 'jl':
                    self.call(v(args[0]))
                elif op == 'jmp':
                    next_pc = v(args[0]); break
                elif op in ('bra','bc','bnc','beq','bne','beqz','bnez','bgez','bltz'):
                    take = {'bra':lambda:True,'bc':lambda:self.c,'bnc':lambda:not self.c,
                            'beq':lambda:v(args[0])==v(args[1]), 'bne':lambda:v(args[0])!=v(args[1]),
                            'beqz':lambda:v(args[0])==0, 'bnez':lambda:v(args[0])!=0,
                            'bgez':lambda:signed(v(args[0]))>=0,
                            'bltz':lambda:signed(v(args[0]))<0}[op]()
                    if take:
                        next_pc = int(args[-1],16); break
                else:
                    raise ValueError(f'{pc:#x}: unsupported {instruction}')
            pc = next_pc
        raise ValueError('bounded arithmetic step limit')


def fields(defaults, mode, increment=False):
    off = 0x3B00 if mode == 1 else 0x3B0A
    a, b = [bytes(defaults[off+j+i] for i in range(5)) for j in (0,5)]
    f = {2:a[1]>>4,5:a[1]&15,8:a[2]>>4,9:a[2]>>4,14:a[2]&15,15:a[2]&15,
         38:a[3]>>4,39:a[3]&15,40:a[4]>>4,
         4:b[0]>>4,7:b[0]&15,10:b[1],11:b[1],12:b[2],13:b[2],3:b[3],6:b[4]}
    if increment:
        assert mode == 1
        f[8]+=1;f[9]+=1
    return a,b,f


def main():
    import subprocess
    import sys
    assert sys.flags.isolated and sys.dont_write_bytecode, 'Use python3 -I -B'
    assert not LOCAL.is_symlink() and LOCAL.resolve().is_relative_to(HERE)
    assert (HERE/'.gitignore').read_text() == 'local/\n'
    subprocess.run(['git','check-ignore','-q',str(LOCAL/'guard')],cwd=ROOT,check=True)
    LOCAL.mkdir(exist_ok=True)
    defaults, origins = script()
    for path in ['research/focus_assist/REPORT.md','research/focus_assist/tables.json',
                 'research/focus_assist/packer_arithmetic.json',
                 'research/focus_assist/official-inputs.before.sha256',
                 'research/t_persistence/REPORT.md','research/t_recovery/REPORT.md',
                 'research/stage2j/REPORT.md','research/isp_pipeline/REPORT.md',
                 'research/color_injection/REPORT.md','research/hidden_processing/REPORT.md',
                 'firmware/stage2j/deep_isp.c','firmware/stage2j/deep_isp.h',
                 'firmware/stage2j/recipe_v1/recipe_v1.h',
                 'firmware/stage2j/tools/make_recipes.py']:
        read(ROOT/path)
    image = Image('jlaunch3'); listing = Listing(image)
    save('script_coverage.json', {'covered_bytes':len(defaults), 'targets':{
        hex(i):{'value':defaults.get(i),'origin':origins.get(i)} for i in
        [0x254A,0x254B,0x2572,0x2573,*range(0x3B00,0x3B14)]}})
    windows = [(0x20115E80,0x2011659C,'fast-packer'),
               (0x20116850,0x201180E4,'full-packer'),
               (0x2010D7BC,0x2010E530,'color-builder'),
               (0x20114FB8,0x201159D8,'color-pack-and-control'),
               (0x2010C67C,0x2010C90C,'fast-toggle'),
               (0x201999C8,0x2019A260,'normalized-settings'),
               (0x20257690,0x20257D00,'type32-writer'),
               (0x20110FD8,0x20111178,'assist-record-selector'),
               (0x20111B28,0x20111C18,'record-expansion'),
               (0x20198440,0x201984A0,'shared-parser-normalization'),
               (0x201A9A38,0x201A9A70,'capture-parser-call'),
               (0x201AA9FC,0x201AAA28,'preview-parser-call'),
               (0x201AA8D0,0x201AA9B4,'toggle-change-detection'),
               (0x202429C8,0x20242B68,'adjust-bookkeeping'),
               (0x20242B68,0x20243178,'adjust-v-w-x'),
               (0x20065D54,0x20065E90,'t-load-and-commit'),
               (0x2007C0F8,0x2007C34C,'adjcom-update-dispatch')]
    evidence = [listing.excerpt(lo,hi,name) for lo,hi,name in windows]
    save('evidence_index.json',evidence)
    modes = {}
    for name, mode, inc in [('mode1',1,False),('mode1_increment',1,True),('mode2',2,False)]:
        a,b,f = fields(defaults,mode,inc)
        vm = Arithmetic(listing,defaults)
        for i in range(0x80):vm.store(0x20383F08+i,0,1)
        for i,value in f.items():vm.store(0x20383F08+i,value,1)
        vm.put('r4',0x20383F08);vm.run(0x20115E80)
        fast = vm.mmio.copy()
        full = Arithmetic(listing,defaults)
        for i in range(0x80):full.store(0x20383F08+i,0,1)
        for i,value in f.items():full.store(0x20383F08+i,value,1)
        full.put('r4',0x20383F08);full.run(0x20116850)
        full.put('lr',0x7FFFFFFC)
        full.put('r4',0x2029C720);full.put('r5',0x20142B88)
        full.run(0x20257690)
        assert all(full.mmio[k] == value for k,value in fast.items()), name
        modes[name]={'A':a.hex(' '),'B':b.hex(' '), 'F':{hex(k):v for k,v in f.items()},
                     'fast_registers':{hex(k):hex(v) for k,v in sorted(fast.items())},
                     'full_registers':{hex(k):hex(v) for k,v in sorted(full.mmio.items())},
                     'full_mirror':{hex(i):hex(full.load(0x20142B88+i,4)) for i in
                                    range(0,0x400,4) if all(0x20142B88+i+j in full.mem for j in range(4))},
                     'fast_steps':len(vm.trace),'full_steps':len(full.trace)}
    save('register_reconstruction.json',modes)
    all_registers = sorted(set(modes['mode1']['full_registers']) | set(modes['mode2']['full_registers']))
    diff = [{'register':k,'mode1':modes['mode1']['full_registers'].get(k),
             'mode1_increment':modes['mode1_increment']['full_registers'].get(k),
             'mode2':modes['mode2']['full_registers'].get(k)} for k in all_registers
            if modes['mode1']['full_registers'].get(k) != modes['mode2']['full_registers'].get(k)
            or modes['mode1_increment']['full_registers'].get(k) != modes['mode2']['full_registers'].get(k)]
    save('register_differences.json',diff)
    assert len(diff) == 20
    assert modes['mode2']['full_registers']['0xf0353324'] == '0x600000'
    assert modes['mode1']['fast_registers']['0xf0353114'] == '0x30025'
    assert modes['mode1_increment']['full_registers']['0xf0353114'] == '0x30005'
    tone_selectors = []
    for tone,native in [('sepia',6),('red',1),('green',2),('blue',3),('purple',4)]:
        vm=Arithmetic(listing,defaults)
        vm.put('r4',native);vm.put('r5',0x70020000);vm.put('r6',0x70020002)
        vm.run(0x2010D800)
        tone_selectors.append({'name':tone,'native':native,'selector':vm.load(0x70020000,1)})
    assert [r['selector'] for r in tone_selectors] == [0,1,2,3,4]
    save('te_selector_mapping.json',tone_selectors)
    te = []
    for index in range(5):
        values=[]
        for level in range(9):
            vm=Arithmetic(listing,defaults); vm.put('r4',index);vm.put('r5',level)
            vm.run(0x2011564C)
            word=vm.value('r0');hi,lo=word>>8,word&255
            decode=lambda b:-(b&127) if b&128 else b
            values.append({'level_zero_based':level,'word':hex(word),
                           'sign_magnitude':[decode(hi),decode(lo)]})
        te.append({'index':index,'values':values})
    save('te_control_words.json',te)
    assert [r['values'][4]['word'] for r in te] == ['0x8604','0x8004','0x84','0x582','0x301']
    save('raw_tables.json',{
        hex(addr):image.bytes(addr,count).hex(' ') for addr,count in
        [(0x2012F008,6),(0x2012F00E,6),(0x2012F014,6),
         (0x2012D0B4,12),(0x2012C5D4+27*96,96)]})
    assert image.bytes(0x2012C5D4+27*96,96) == bytes(96)
    body = Listing(Image('ilaunch3'))
    evidence.extend(body.excerpt(lo,hi,name) for lo,hi,name in
                    [(0x202D41FC,0x202D4240,'body-te-field'),
                     (0x202D4FE4,0x202D5004,'body-assist-fields'),
                     (0x2017098C,0x20170A0C,'body-command-2f02-2f03'),
                     (0x2036F244,0x2036F260,'body-full-update-mask')])
    save('evidence_index.json',evidence)
    calculate()
    save('inputs.used.json',{'base_directory':str(ROOT),'sha256':READS})
    print(json.dumps({'mode2_fast_triplet':modes['mode2']['fast_registers']['0xf0353324'],
                      'evidence_windows':len(evidence),'inputs':len(READS)}))


def calculate():
    """Conditional BT.601-style arithmetic, not an ISP color specification."""
    def rgb(y, cb, cr):
        result = [y+1.402*cr,y-0.344136*cb-0.714136*cr,y+1.772*cb]
        return [round(max(0,min(255,x))) for x in result]
    def decode(b,model):
        if model == 'sign_magnitude':return -(b&127) if b&128 else b
        if model == 'twos_complement':return b-256 if b&128 else b
        return b-128
    probe = [0x400000,0x604000,0x600040,0x608180]
    candidates = [0x60A040,0x60A0A0,0x60C0C0,0x4CAB7F,0x96D4EB]
    results=[]
    for word in [0x600000,*probe,*candidates]:
        y,u,v=word>>16,(word>>8)&255,word&255
        models={}
        for model in ('sign_magnitude','twos_complement','offset_binary'):
            cu,cv=decode(u,model),decode(v,model)
            models[model]={'Cb_Cr_order':rgb(y,cu,cv),'Cr_Cb_order':rgb(y,cv,cu),
                           'decoded_middle_low':[cu,cv]}
        results.append({'word':f'0x{word:06X}','models':models})
    cpu=[]
    for w,h,fps in [(320,240,30),(640,480,30),(640,480,60),(320,240,15),(160,120,15)]:
        pixels=w*h*fps
        cpu.append({'width':w,'height':h,'fps':fps,'pixels_per_second':pixels,
                    'read_write_MB_s_assuming_4_B_per_pixel':4*pixels/1e6,
                    'MHz_for_50_100_cycles_per_pixel':[50*pixels/1e6,100*pixels/1e6],
                    'cycles_per_pixel_at_MHz':{str(mhz):round(mhz*1e6/pixels,6) for mhz in (50,100,200)}})
    save('color_models.json',results)
    save('cpu_budget.json',cpu)


if __name__ == '__main__':
    main()
