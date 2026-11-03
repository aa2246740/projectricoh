"""Run the unit's actual shutdown reply constructors with both instruction cores."""
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime import ROOT, TEMP, models


def main():
    models()
    from unit_peer import UnitImage
    sys.path.insert(0, str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    assert PB.PythonBackend.native_api == 5
    rows = []
    for unit, constructor, sender in (('50mm',0x201a7a14,0x2007c894),
            ('28mm',0x201aae18,0x2007c894),('mount',0x201a7240,0x2007d398)):
        image = UnitImage(unit)
        for backend, Backend in (('c', PB.PythonBackend), ('python', PB.PurePythonBackend)):
            PB.CACHE = TEMP/'power-reply-check'/unit/backend
            b = Backend()
            for off, base, n, _, _ in image.sections:
                if n:
                    b.map(base, image.raw[512+off:512+off+n], False)
            b.map(0x10000000, bytes(65536), True)
            b.set_reg('r15', 0x1000f000)
            b.set_reg('r4', 0x8400)
            sent = []
            def send(c):
                queue, pointer, n = c.get_reg('r4'), c.get_reg('r5'), c.get_reg('r6')
                sent.append(dict(queue=queue, n=n, data=c.read(pointer, n).hex()))
                return True
            b.add_breakpoint(sender, send)
            stop = b.call(constructor, [], 0x7ffffff0, 10000)
            assert stop.reason == 'breakpoint' and sent == [dict(queue=1,n=16,data='00108400800020040000000000000000')]
            rows.append(dict(unit=unit, backend=backend, constructor=hex(constructor),
                sender=hex(sender), sent=sent, steps=stop.steps))
    result = dict(status='PASS', layer='主机模型：原厂单元构造器指令', rows=rows,
        declaration='Normal header 0x8400; the constructor leaves its reserved word untouched, declared zero in the device reply',
        boundary='The unit shutdown business operation and its hardware completion were not executed')
    path = HERE/'evidence/power-reply-check.json'
    assert not path.exists()
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status='PASS', rows=len(rows))))


if __name__ == '__main__':
    main()
