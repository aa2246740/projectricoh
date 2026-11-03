"""Check the origin of all native menu state writes during replay."""
from ui_trace_scope import touches_ui

AUDITS = []

def install(v):
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
