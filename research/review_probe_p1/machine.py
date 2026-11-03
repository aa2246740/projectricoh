"""Small, bounded M32R instruction runner for this offline review."""
import re
from collections import Counter, deque

MASK = 0xffffffff


def signed(x):
    return x - 0x100000000 if x & 0x80000000 else x


def parse(text):
    rows = {}
    names = {}
    for line in text.splitlines():
        head = re.match(r'^([0-9a-f]{8}) <([^>]+)>:', line)
        if head:
            names[head[2]] = int(head[1], 16)
        m = re.match(r'^\s*([0-9a-f]+):\t((?:[0-9a-f]{2} ?)+)\t(.+)$', line)
        if not m:
            continue
        address, raw, operations = int(m[1], 16), bytes.fromhex(m[2]), []
        for item in re.split(r' -> | \|\| ', m[3]):
            item = re.sub(r'\s*<[^>]*>', '', item).strip()
            op, _, args = item.partition(' ')
            args = re.split(r',\s*(?![^()]*\))', args.strip()) if args else []
            operations.append((op, args))
        rows[address] = (len(raw), operations)
    return rows, names


class Machine:
    def __init__(self, text):
        self.rows, self.names = parse(text)
        self.memory = bytearray(0x800000)
        self.regs = [0]*16
        self.control = {'cbr': 0, 'psw': 0x40}
        self.pc = 0
        self.next = 0
        self.count = 0
        self.trace = []
        self.stores = deque(maxlen=4096)
        self.write_cells = Counter()
        self.store_count = 0
        self.edges = {}
        self.delta = 0
        self.special = {}

    def relocate(self, delta):
        self.rows = {a+delta:v for a,v in self.rows.items()}
        self.names = {n:a+delta for n,a in self.names.items()}
        self.delta = delta

    def put(self, address, data):
        if address in self.special:
            assert len(data)==4
            self.special[address]=int.from_bytes(data,'big')
            return
        at = address-0x20000000
        assert 0 <= at <= len(self.memory)-len(data), hex(address)
        self.memory[at:at+len(data)] = data

    def get(self, address, size):
        if address in self.special:
            assert size==4
            return self.special[address].to_bytes(4,'big')
        at = address-0x20000000
        assert 0 <= at <= len(self.memory)-size, hex(address)
        return bytes(self.memory[at:at+size])

    def u(self, address, size=4):
        return int.from_bytes(self.get(address, size), 'big')

    def w(self, address, value, size=4):
        self.put(address, (value & ((1 << (size*8))-1)).to_bytes(size, 'big'))

    @staticmethod
    def reg(name):
        return {'sp':15, 'lr':14, 'fp':13}.get(name, int(name[1:]) if name.startswith('r') else -1)

    def value(self, arg, radix=0):
        if arg.startswith('r') or arg in ('sp', 'lr', 'fp'):
            return self.regs[self.reg(arg)]
        return int(arg.lstrip('#'), radix)

    def assign(self, name, value):
        self.regs[self.reg(name)] = value & MASK

    def address(self, arg):
        assert arg.startswith('@'), arg
        arg = arg[1:]
        if arg.startswith('+'):
            name=arg[1:];self.assign(name,self.value(name)+4)
            return self.value(name)
        if arg.endswith('+'):
            name=arg[:-1];old=self.value(name);self.assign(name,old+4)
            return old
        if arg.startswith('('):
            offset, name = arg[1:-1].split(',')
            return (self.value(name) + int(offset, 0)) & MASK
        return self.value(arg)

    def jump(self, dest):
        self.next = dest
        self.did_jump = True

    def execute(self, op, a):
        if op == 'nop':
            return
        if op in ('ldi', 'ld24', 'seth'):
            v = self.value(a[1], 16 if op == 'ld24' else 0)
            self.assign(a[0], v << 16 if op == 'seth' else v)
        elif op == 'mv':
            self.assign(a[0], self.value(a[1]))
        elif op in ('add', 'sub', 'and', 'or', 'xor', 'mul'):
            x, y = self.value(a[0]), self.value(a[1])
            self.assign(a[0], {'add':lambda:x+y, 'sub':lambda:x-y,
                        'and':lambda:x&y, 'or':lambda:x|y, 'xor':lambda:x^y,
                        'mul':lambda:x*y}[op]())
        elif op in ('addi', 'add3', 'and3', 'or3', 'xor3'):
            x, y = self.value(a[0] if op == 'addi' else a[1]), self.value(a[-1])
            self.assign(a[0], x+y if op in ('addi','add3') else
                        x&y if op == 'and3' else x|y if op == 'or3' else x^y)
        elif op in ('not','neg'):
            x = self.value(a[1]); self.assign(a[0], ~x if op == 'not' else -x)
        elif op in ('slli','srli','srai','sll','srl','sra','sll3','srl3','sra3'):
            x = self.value(a[1] if op.endswith('3') else a[0])
            n = self.value(a[-1]) & 31
            self.assign(a[0], x << n if op.startswith('sll') else
                        signed(x) >> n if op.startswith('sra') else x >> n)
        elif op in ('cmp','cmpu','cmpi','cmpui'):
            x, y = self.value(a[0]), self.value(a[1])
            y &= MASK
            self.control['cbr'] = int(x < y if op in ('cmpu','cmpui') else signed(x) < signed(y & MASK))
            self.control['psw'] = (self.control['psw'] & ~1) | self.control['cbr']
        elif op == 'mvfc':
            self.assign(a[0], self.control[a[1]])
        elif op == 'mvtc':
            self.control[a[1]] = self.value(a[0])
            if a[1]=='psw':self.control['cbr']=self.control['psw']&1
        elif op == 'push':
            self.regs[15] = (self.regs[15]-4) & MASK
            self.store(self.regs[15], self.value(a[0]), 4)
        elif op == 'pop':
            self.assign(a[0], self.u(self.regs[15])); self.regs[15] += 4
        elif op in ('ld','ldb','ldub','ldh','lduh'):
            size = 4 if op == 'ld' else 1 if op.endswith('b') else 2
            x = self.u(self.address(a[1]), size)
            if op in ('ldb','ldh') and x & (1 << (size*8-1)):
                x -= 1 << (size*8)
            self.assign(a[0], x)
        elif op in ('st','stb','sth'):
            self.store(self.address(a[1]), self.value(a[0]), {'st':4,'stb':1,'sth':2}[op])
        elif op in ('bl','bra','bc','bnc','beq','bne','beqz','bnez','bltz','bgez','bgtz','blez','jl','jmp'):
            take = True
            if op in ('bc','bnc'):
                take = self.control['cbr'] == (1 if op == 'bc' else 0)
            elif op in ('beq','bne'):
                take = (self.value(a[0]) == self.value(a[1])) == (op == 'beq')
            elif op in ('beqz','bnez','bltz','bgez','bgtz','blez'):
                x = signed(self.value(a[0]))
                take = {'beqz':x==0,'bnez':x!=0,'bltz':x<0,'bgez':x>=0,'bgtz':x>0,'blez':x<=0}[op]
            if take:
                if op in ('bl','jl'):
                    self.regs[14] = self.pc+4
                dest = self.value(a[-1]) if op in ('jl','jmp') else int(a[-1],16)+self.delta
                self.jump(dest)
        else:
            raise RuntimeError((hex(self.pc), op, a))

    def store(self, address, value, size):
        old = self.u(address,size)
        self.w(address,value,size)
        self.store_count += 1
        self.write_cells[(address,size)] += 1
        self.stores.append((self.pc,address,size,old,value & ((1 << (size*8))-1)))

    def run(self, address, args=(), limit=300000, initial=None):
        self.regs = [0]*16
        self.regs[15] = 0x20700000
        self.regs[14] = 0x20fffff0
        for i, value in enumerate(args):
            self.regs[i] = value & MASK
        for name,value in (initial or {}).items():
            self.assign(name,value)
        self.pc = address
        start = self.count
        while self.pc != 0x20fffff0:
            if self.count-start >= limit:
                raise RuntimeError(('step limit',hex(self.pc),limit))
            self.count += 1
            if self.pc in self.edges:
                self.edges[self.pc](self)
                self.pc = self.regs[14]
                continue
            if self.pc not in self.rows:
                raise RuntimeError(('missing instruction',hex(self.pc)))
            size, ops = self.rows[self.pc]
            self.next = self.pc+size
            self.did_jump = False
            for op, a in ops:
                self.execute(op,a)
                if self.did_jump:
                    break
            self.trace.append(self.pc)
            self.pc = self.next
        assert self.regs[15] == 0x20700000, hex(self.regs[15])
        return signed(self.regs[0])
