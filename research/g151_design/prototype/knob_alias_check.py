"""Host-C pre-check for the g151 MOUNT knob design (Scratch prototype; not a delivery test).

Builds the host engine twice: 'base' = g150 sources, 'alias' = g150 + the kv_data_recipe alias (MOUNT slots
1-3, 5-8 read the 50mm knob records). On the g150 release DAT, for slot 1..8 and each control alone, it lists
the legal levels (g135_request succeeds) for 50mm and MOUNT, the request (amount + nine doses), and the
552-byte computed entry. Reports per variant: slots where MOUNT and 50mm legal sets differ, requests differ,
and entries differ (split into Amount==100 and Amount!=100). Writes knob-alias-check.json in this folder."""
import ctypes as ct, json, os, subprocess, sys
from pathlib import Path
ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
HERE = Path(__file__).resolve().parent
DAT = ROOT / 'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT'
NAME, TREE = sys.argv[1], Path(sys.argv[2])

class Levels(ct.Structure): _fields_ = [('v', ct.c_int16 * 10)]
class Req(ct.Structure): _fields_ = [('amount', ct.c_int32), ('dose', ct.c_int32 * 9), ('a', ct.c_int32), ('b', ct.c_int32)]

def build(name, tree):
    product = tree / 'candidate/containers/product'
    core, container = product / 'src/firmware/engine/core', product / 'src/firmware/card_container_v2'
    src = [ROOT / 'research/emptystack_v38/host_engine.c', product / 'memory.c', product / 'ui_v2_data.c',
           tree / 'candidate/engine_services/crc.c']
    src += [core / n for n in ('eng_data.c', 'eng_semantic.c', 'eng_crc_compat.c', 'eng_pin_stub.c')]
    src += [container / n for n in ('common.c', 'gate.c', 'api.c')]
    src += [product / 'kv2' / n for n in ('kv_data.c', 'kv_ui.c', 'kv_math.c', 'kv_i64.c')]
    out = HERE / ('host-%s.dylib' % name)
    subprocess.run(['clang', '-std=c11', '-O2', '-shared', '-fPIC', '-DENG_HOST', '-ffreestanding', '-fno-builtin',
                    '-I', str(core), '-I', str(product), '-I', str(container), *map(str, src), '-o', str(out)],
                   check=True, capture_output=True, env=dict(os.environ))
    return ct.CDLL(str(out))

def table(lib, unit):
    raw = DAT.read_bytes(); mem = (ct.c_uint8 * len(raw)).from_buffer_copy(raw)
    assert lib.g135_open(mem, len(raw), unit) == 0
    res = {}
    for slot in range(1, 9):
        for control in range(10):
            span = range(0, 151) if control == 0 else range(-9, 10)
            for level in span:
                v = [100] + [0] * 9; v[control] = level
                r = Req(); entry = (ct.c_uint8 * 552)()
                if lib.g135_request(slot, ct.byref(Levels((ct.c_int16 * 10)(*v))), ct.byref(r)) != 0:
                    continue
                assert lib.g135_compute(slot, ct.byref(Levels((ct.c_int16 * 10)(*v))), entry) == 0
                res[(slot, control, level)] = (r.amount, tuple(r.dose), bytes(entry))
    return res

def compare(lib):
    fifty, mount = table(lib, 0), table(lib, 2)
    out = {}
    for slot in range(1, 9):
        keys50 = {k for k in fifty if k[0] == slot}; keysM = {k for k in mount if k[0] == slot}
        both = sorted(keys50 & keysM)
        req = [k for k in both if fifty[k][:2] != mount[k][:2]]
        ent100 = [k for k in both if k[1] == 0 and k[2] == 100 or k[1] != 0]
        diff100 = [k for k in ent100 if fifty[k][2] != mount[k][2]]
        diffbytes = sorted({i for k in diff100 for i in range(552) if fifty[k][2][i] != mount[k][2][i]})
        amt = [k for k in both if k[1] == 0 and k[2] != 100]
        out[slot] = dict(legal_50mm=len(keys50), legal_mount=len(keysM),
                         only_50mm=[list(k[1:]) for k in sorted(keys50 - keysM)][:12],
                         only_mount=[list(k[1:]) for k in sorted(keysM - keys50)][:12],
                         request_differs=len(req), amount100_entry_differs=len(diff100), amount100_cases=len(ent100),
                         differing_byte_ranges=ranges(diffbytes),
                         amount_not100_cases=len(amt), amount_not100_entry_differs=sum(1 for k in amt if fifty[k][2] != mount[k][2]))
    return out

def ranges(ix):
    r = []
    for i in ix:
        if r and r[-1][1] == i - 1: r[-1][1] = i
        else: r.append([i, i])
    return r

def main():
    result = compare(build(NAME, TREE))
    (HERE / ('knob-check-%s.json' % NAME)).write_text(json.dumps(result, indent=1) + '\n')
    for s, d in result.items():
        print(NAME, s, {k: v for k, v in d.items() if k not in ('only_50mm', 'only_mount')}, 'only50', d['only_50mm'], 'onlyM', d['only_mount'], flush=True)

if __name__ == '__main__':
    main()
