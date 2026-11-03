"""Check the origin of all native menu state writes during replay."""
from ui_trace_scope import touches_ui

AUDITS = []
RPC_AUDITS = []

def install_rpc(v):
    cls = v.pe.RpcEdge
    if getattr(cls, 'range_guard_installed', False):
        return
    original_init, original_call = cls.__init__, cls.call
    def initialize(self, t_value, image):
        original_init(self, t_value, image)
        from common import DAT
        raw = DAT.read_bytes()
        unit = next(name for name, value in v.pe.UNITS.items() if value[1] == image.sha256)
        index = {'50mm':0, '28mm':1, 'mount':2}[unit]
        u16 = lambda b, o: int.from_bytes(b[o:o + 2], 'big')
        u32 = lambda b, o: int.from_bytes(b[o:o + 4], 'big')
        directory = u32(raw, 156) + 64 * index
        mapping = raw[u32(raw, directory + 12):][:152]
        self.review_rows = [(u32(mapping, 32 + 12 * i), u16(mapping, 36 + 12 * i)) for i in range(9)]
        self.review_t = (u16(mapping, 28), u16(mapping, 30))
        self.review_pages = {address >> 16 for address, size in self.review_rows}
        self.review_pages.update((address + size - 1) >> 16 for address, size in self.review_rows)
        self.review_pages.add(self.review_t[0])
        self.review_audit = dict(unit=unit, X=0, V=0, W=0, T_reads=0, T_writes=0,
                                aligned_edge_reads=0, preserved_edge_writes=0, violations=0)
        RPC_AUDITS.append(self.review_audit)
    def checked(self, command, value):
        row = self.review_audit
        def require(condition, detail):
            if not condition:
                row['violations'] += 1
                raise AssertionError(('Mapped communication range', self.review_audit['unit'], command, value, detail))
        if command == 23:
            require(value in self.review_pages, 'page')
            row['X'] += 1
        elif command in (21, 22):
            row['V' if command == 21 else 'W'] += 1
            if self.page == self.review_t[0]:
                if command == 21:
                    require(value == self.review_t[1], 'T index')
                row['T_reads' if command == 21 else 'T_writes'] += 1
            else:
                address = ((self.page or 0) << 16) | (value & 65534) if command == 21 else self.cursor
                spans = [(base, size) for base, size in self.review_rows
                         if (base & ~1) <= address and address + 2 <= ((base + size + 1) & ~1)]
                require(bool(spans), hex(address))
                base, size = spans[0]
                edge_high = address < base
                edge_low = address + 2 > base + size
                if edge_high or edge_low:
                    if command == 21:
                        row['aligned_edge_reads'] += 1
                    else:
                        previous = self.half(address)
                        require(previous is not None, 'neighbor read')
                        if edge_high:
                            require(value >> 8 == previous >> 8, 'leading neighbor')
                        if edge_low:
                            require(value & 255 == previous & 255, 'trailing neighbor')
                        row['preserved_edge_writes'] += 1
        else:
            require(False, 'command')
        return original_call(self, command, value)
    cls.__init__, cls.call = initialize, checked
    cls.range_guard_installed = True

def install(v):
    install_rpc(v)
    cls = v.V35Harness
    if getattr(cls, 'review_guard_installed', False):
        return
    original = cls.__init__
    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        row = dict(cpu_writes=0, native_memory_fill_writes=0, host_writes=0,
                   getter_callback_present=0x20271fec in self.b.breakpoints)
        assert not row['getter_callback_present']
        AUDITS.append(row)
        def watch(ev):
            if not touches_ui(ev):
                return
            if ev.origin == 'cpu':
                row['cpu_writes'] += 1
            elif ev.origin == 'model:native_memset' and ev.pc == 0x20062750:
                row['native_memory_fill_writes'] += 1
            else:
                row['host_writes'] += 1
                raise AssertionError(('Native state write origin', ev.address, ev.pc, ev.origin))
        self.b.add_write_trace(0, 2**32, watch)
    cls.__init__ = initialize
    cls.review_guard_installed = True
