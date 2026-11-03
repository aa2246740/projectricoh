#!/usr/bin/env python3
"""Known resident call graph costs and an explicit product stack lower bound."""
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('review', HERE / 'review.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def functions(text):
    return {m[2]: (int(m[1], 16), m[3]) for m in re.finditer(
        r'^([0-9a-f]+) <([^>]+)>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)', text, re.M | re.S)}


def main():
    r.preflight()
    text = (r.LOCAL / 'disasm/resident.txt').read_text()
    funcs = functions(text)
    frames = {}
    for p in (r.LOCAL / 'frozen/firmware/resident_v3/local/resident/build').glob('*.su'):
        for line in p.read_text().splitlines():
            fields = line.split('\t')
            if len(fields) == 3:
                assert fields[2] == 'static'
                frames[fields[0].rsplit(':', 1)[-1]] = int(fields[1])
    graph = {name: sorted(set(re.findall(r'\bbl [0-9a-f]+ <([^>+]+)>', body)))
             for name, (_, body) in funcs.items()}
    for name in list(funcs):
        if name.startswith('rv_native_'):
            frames[name] = 28
            graph[name] = []
    frames['rv_cache_sync'] = frames['rv_irq_save'] = frames['rv_irq_restore'] = 0
    def cost(name, blocked, seen=()):
        if name in blocked:
            return 0, []
        assert name not in seen, seen+(name,)
        children = [cost(n, blocked, seen+(name,)) for n in graph.get(name, [])]
        n, chain = max(children, default=(0, []), key=lambda v:v[0])
        return frames.get(name, 0)+n, [name]+chain
    rows = []
    for hook in r.ENABLED:
        blocked = set()
        if hook != 1:
            blocked.add('rv_load')
        if hook in (2, 5, 9):
            blocked.add('rv_engine')
        n, chain = cost('rv_hook_observe', blocked)
        rows.append(dict(hook=hook, known_resident_and_bridge_peak=68+n, chain=chain,
                         engine_ingress_live_bytes=68+120+40+4 if hook in (1,6,7,8) else None))
    product = functions((r.LOCAL / 'disasm/product.txt').read_text())
    expected = {'ig_apply': (7,76), 'bind_gxts': (7,1252), 'gxts_load.part.0': (7,688)}
    parts = []
    for name, (pushes, reserve) in expected.items():
        va, body = product[name]
        head = '\n'.join(body.splitlines()[:12])
        assert len(re.findall(r'\bpush (?:r\d+|lr|fp)\b',head)) == pushes
        assert re.search(r'(?:addi sp,#|add3 sp,sp,#)-'+str(reserve)+r'\b',head)
        parts.append(dict(function=name,address=va,saved_registers_bytes=4*pushes,reserved_bytes=reserve,frame=4*pushes+reserve))
    assert re.search(r'\bbl [0-9a-f]+ <bind_gxts>', product['ig_apply'][1])
    assert re.search(r'\bbl [0-9a-f]+ <gxts_load.part.0>', product['bind_gxts'][1])
    total = 68+120+40+4+sum(x['frame'] for x in parts)
    assert total == 2332
    value = dict(resident=rows, resident_frames=frames, resident_calls=graph,
                 H08_product_lower_bound=dict(bytes=total, resident_prefix=[68,120,40,4], product_parts=parts),
                 whole_stack_upper_bound_known=False,
                 limitations='Known compiled C graph plus 68 B hook frame and 28 B native bridge. Native firmware callees, indirect engine calls, interrupts and task baseline are excluded. Product chain is a lower bound, not an upper bound.')
    r.save('stack-independent.json', value)
    print(json.dumps(dict(resident=[dict(hook=x['hook'],known_peak=x['known_resident_and_bridge_peak']) for x in rows], H08_product_lower_bound=total,whole_stack_upper_bound_known=False)))


if __name__ == '__main__':
    main()
