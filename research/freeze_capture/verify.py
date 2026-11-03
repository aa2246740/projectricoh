"""freeze-capture-r1 static checks. Run from repo root:
/usr/bin/python3 -I -B research/freeze_capture/verify.py
Reads only; writes research/freeze_capture/local/verify.json (+ disassembly text)."""
import hashlib, json, os, struct, subprocess, sys

ROOT = os.getcwd()
OUT = os.path.join(ROOT, 'research/freeze_capture/local')
TMP = '/Volumes/Workspace/Scratch/tmp/projectricoh/freeze'
OFFICIAL = 'artifacts/firmware/gxr-1.51/ilaunch3'
BODY = 'firmware/package_v37_diag/SD_ROOT/ilaunch3'
ELF = 'firmware/resident_v37/local/resident/build/resident.elf'
V36 = 'firmware/package_v36_g120b/SD_ROOT/ilaunch3'
OBJDUMP = 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
VA_DELTA = 0x2004AE00  # va = file offset + delta for the main segments (hooks-pack.json)
EXPECT = {OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
          BODY: 'd00607405a5bd33290f99e9eda20df31a46386b6e0891cd5e62b15a9e3376283',
          'firmware/package_v36_g120b/SD_ROOT/ilaunch3': '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008',
          ELF: '910686bce5f4097d5606056628641e1c216e3570fb2513d8229887c3ff41f56e'}
HOOKS = {'H01': 0x2028709C, 'H02': 0x202870A8, 'H05': 0x201FEBE4, 'H06': 0x202BE24C,
         'H07': 0x202871D8, 'H08': 0x202BB968, 'H09': 0x2017098C}


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def elf_sections(data):
    shoff, = struct.unpack('>I', data[0x20:0x24])
    shentsize, shnum, shstrndx = struct.unpack('>HHH', data[0x2E:0x34])
    rows = [struct.unpack('>IIIIIIIIII', data[shoff + i * shentsize:shoff + (i + 1) * shentsize]) for i in range(shnum)]
    strtab = rows[shstrndx]
    names = data[strtab[4]:strtab[4] + strtab[5]]
    out = {}
    for r in rows:
        name = names[r[0]:names.index(b'\0', r[0])].decode()
        out[name] = {'addr': r[3], 'offset': r[4], 'size': r[5], 'type': r[1]}
    return out


def elf_symbols(data, secs):
    st = secs['.symtab']; ss = secs['.strtab']
    strs = data[ss['offset']:ss['offset'] + ss['size']]
    syms = {}
    for i in range(st['size'] // 16):
        name, value, size, info, other, shndx = struct.unpack('>IIIBBH', data[st['offset'] + 16 * i:st['offset'] + 16 * i + 16])
        if name:
            syms[strs[name:strs.index(b'\0', name)].decode()] = value
    return syms


def diff_runs(a, b):
    runs, i = [], 0
    while i < len(a):
        if a[i] != b[i]:
            j = i
            while j + 1 < len(a) and a[j + 1] != b[j + 1]:
                j += 1
            if runs and i - runs[-1][1] <= 8:
                runs[-1][1] = j + 1
            else:
                runs.append([i, j + 1])
            i = j + 1
        else:
            i += 1
    return runs


def disasm(blob, base, name):
    os.makedirs(TMP, exist_ok=True)
    path = os.path.join(TMP, name + '.bin')
    open(path, 'wb').write(blob)
    txt = subprocess.run([OBJDUMP, '-D', '-b', 'binary', '-m', 'm32r2', '-EB', '--adjust-vma=0x%x' % base, path],
                         check=True, capture_output=True, text=True).stdout
    os.remove(path)
    open(os.path.join(OUT, name + '.asm.txt'), 'w').write(
        '# disassembled from %s (v3.7 body) at VA 0x%x\n' % (BODY, base) + txt)
    return txt


def main():
    os.makedirs(OUT, exist_ok=True)
    res = {'inputs': {}, 'checks': {}}
    for p, h in EXPECT.items():
        got = sha(p); res['inputs'][p] = got
        assert got == h, (p, got)
    off = open(OFFICIAL, 'rb').read(); body = open(BODY, 'rb').read(); elf = open(ELF, 'rb').read()
    assert len(off) == len(body)
    runs = diff_runs(off, body)
    res['checks']['diff_runs'] = [{'file_offset': hex(s), 'va_if_main_segment': hex(s + VA_DELTA), 'bytes': e - s,
                                   'changed': sum(off[k] != body[k] for k in range(s, e)),
                                   'official_all_ff': all(x == 0xFF for x in off[s:e])} for s, e in runs]
    total = sum(r['changed'] for r in res['checks']['diff_runs'])
    res['checks']['changed_bytes_total'] = total
    # other 28 package files identical to official
    same = []
    for f in sorted(os.listdir('artifacts/firmware/gxr-1.51')):
        same.append((f, open('artifacts/firmware/gxr-1.51/' + f, 'rb').read() == open('firmware/package_v37_diag/SD_ROOT/' + f, 'rb').read()))
    res['checks']['package_files_identical_to_official'] = {f: s for f, s in same}
    secs = elf_sections(elf); syms = elf_symbols(elf, secs)
    for sec in ('.payload', '.root_pins'):
        s = secs[sec]; fo = s['addr'] - VA_DELTA
        res['checks'][sec + '_matches_body'] = body[fo:fo + s['size']] == elf[s['offset']:s['offset'] + s['size']]
    # every changed byte is inside: header checksum word, resident payload, root pins, or a hook word
    allowed = [(0x16C, 0x170)]
    for sec in ('.payload', '.root_pins'):
        s = secs[sec]; allowed.append((s['addr'] - VA_DELTA, s['addr'] - VA_DELTA + s['size']))
    for h, va in HOOKS.items():
        allowed.append((va - VA_DELTA, va - VA_DELTA + (8 if h in ('H01', 'H05') else 4)))
    stray = [k for k in range(len(off)) if off[k] != body[k] and not any(a <= k < b for a, b in allowed)]
    res['checks']['changed_bytes_outside_known_sites'] = len(stray)
    # v3.6 (g120b) body vs v3.7: which VA ranges changed; H09 path must be untouched
    v36 = open(V36, 'rb').read()
    res['inputs'][V36] = hashlib.sha256(v36).hexdigest()
    r36 = diff_runs(v36, body)
    res['checks']['v36_to_v37_runs'] = [[hex(a + VA_DELTA), hex(b + VA_DELTA)] for a, b in r36]
    h09_path = [(syms['rv_hook_observe'], syms['rv_hook_observe'] + 0x7C), (syms['rv_hook_shared'], syms['rv_hook_09'] + 0x20),
                (syms['rv_grain'], syms['rv_grain'] + 0xDE), (0x2017098C, 0x20170990)]
    res['checks']['v36_to_v37_touches_h09_path'] = any(a + VA_DELTA < hi and b + VA_DELTA > lo for a, b in r36 for lo, hi in h09_path)
    # hook branch targets
    br = {}
    for h, va in HOOKS.items():
        w = body[va - VA_DELTA:va - VA_DELTA + 4]
        op = w[0]
        disp = int.from_bytes(w[1:4], 'big')
        if disp & 0x800000:
            disp -= 0x1000000
        target = (va & ~3) + disp * 4
        sym = 'rv_hook_%s' % h[1:]
        br[h] = {'site': hex(va), 'word': w.hex(), 'opcode': 'bra disp24' if op == 0xFF else hex(op),
                 'target': hex(target), 'symbol': sym, 'symbol_addr': hex(syms[sym]), 'ok': op == 0xFF and target == syms[sym],
                 'official_word': off[va - VA_DELTA:va - VA_DELTA + 4].hex()}
    res['checks']['hook_branches'] = br
    # H09 path disassembly from the body bytes
    lo = syms['rv_hook_observe']; fo = lo - VA_DELTA
    disasm(body[fo:fo + 0x80], lo, 'body-rv_hook_observe-head')
    lo = syms['rv_hook_shared']; fo = lo - VA_DELTA
    disasm(body[fo:fo + 0x190], lo, 'body-rv_hook_shared-to-09')
    disasm(body[0x2017098C - VA_DELTA - 0x40:0x2017098C - VA_DELTA + 0x40], 0x2017098C - 0x40, 'body-h09-site')
    disasm(off[0x2017098C - VA_DELTA - 0x40:0x2017098C - VA_DELTA + 0x40], 0x2017098C - 0x40, 'official-h09-site')
    # stack bytes on the H09 path, counted from the instructions
    def pushes(txt, start, stop):
        n, sp = 0, 0
        for line in txt.splitlines():
            parts = line.split('\t')
            if len(parts) < 3 or not parts[0].strip().endswith(':'):
                continue
            a = int(parts[0].strip()[:-1], 16)
            if a < start or a >= stop:
                continue
            ins = parts[2]
            n += ins.count('push ')
            for seg in set(ins.replace('||', '->').split('->')):
                seg = seg.strip()
                if seg.startswith('addi sp,#-'):
                    sp += int(seg.split('#-')[1])
        return n, sp
    t_obs = open(os.path.join(OUT, 'body-rv_hook_observe-head.asm.txt')).read()
    t_sh = open(os.path.join(OUT, 'body-rv_hook_shared-to-09.asm.txt')).read()
    n9, _ = pushes(t_sh, syms['rv_hook_09'], syms['rv_hook_09'] + 4)
    nsh, _ = pushes(t_sh, syms['rv_hook_shared'], syms['rv_hook_shared'] + 0x48)
    nob, spob = pushes(t_obs, syms['rv_hook_observe'], syms['rv_hook_observe'] + 0x18)
    total_stack = 4 * (n9 + nsh + nob) + spob
    res['checks']['h09_stack'] = {'rv_hook_09_push': n9, 'rv_hook_shared_push': nsh, 'rv_hook_observe_push': nob,
                                  'rv_hook_observe_addi': spob, 'total_bytes': total_stack,
                                  'rv_grain_frame': 0, 'task6_stack': 16384,
                                  'native_depth_with_mode2_outer': 492, 'irq_context': 76, 'sentinel': 4,
                                  'remaining': 16384 - 492 - total_stack - 76 - 4}
    # early-return path of hook 9 has no store instruction
    body_lines = []
    for line in t_obs.splitlines():
        parts = line.split('\t')
        if len(parts) >= 3 and parts[0].strip().endswith(':'):
            a = int(parts[0].strip()[:-1], 16)
            if syms['rv_hook_observe'] <= a < syms['rv_hook_observe'] + 0x7C:
                body_lines.append(parts[2])
    res['checks']['h09_early_path_stores'] = [l for l in body_lines if any(s in l for s in (' st r', ' stb ', ' sth ')) or l.startswith(('st ', 'stb ', 'sth '))]
    # official windows cited in REPORT.md, copied from the project's full-section disassembly (Ricoh bytes: local only)
    D = 'research/tooling_m32r/disasm/'
    snips = [('ilaunch3-sec06-load-20155000.disasm.txt', 0x2017094C, 0x201709CC, 'H09 = 0x2F02 sender, queue 15'),
             ('ilaunch3-sec09-load-2025d800.disasm.txt', 0x202E3ADC, 0x202E3B28, 'state callback -> 0x202D6AE4 / 0x202D6BF0'),
             ('ilaunch3-sec09-load-2025d800.disasm.txt', 0x202D6B5C, 0x202D6B6C, 'sender call 1'),
             ('ilaunch3-sec09-load-2025d800.disasm.txt', 0x202D6CB0, 0x202D6CC0, 'sender call 2'),
             ('ilaunch3-sec09-load-2025d800.disasm.txt', 0x202D6D9C, 0x202D6DB0, 'sender call 3'),
             ('ilaunch3-sec09-load-2025d800.disasm.txt', 0x202D6E60, 0x202D6E70, 'sender call 4'),
             ('ilaunch3-sec06-load-20155000.disasm.txt', 0x20155934, 0x20155A90, 'JPEG submit (fmt 1) with low-nibble wait on 0x201BC208'),
             ('ilaunch3-sec06-load-20155000.disasm.txt', 0x20156F6C, 0x20157140, 'RAW submit (fmt 21/22) with 0xF0 wait on 0x201BC208'),
             ('ilaunch3-sec06-load-20155000.disasm.txt', 0x20157140, 0x2015728C, 'JPEG submit (fmt 1) via 0x20109C44'),
             ('ilaunch3-sec06-load-20155000.disasm.txt', 0x201758A0, 0x20175A30, 'opcode 0x2042 -> RAW submit; deferred path 0x20175904'),
             ('ilaunch3-sec01-load-20055000.disasm.txt', 0x2009359C, 0x200935B4, 'rpc_ready = plain loads')]
    with open(os.path.join(OUT, 'official-snippets.asm.txt'), 'w') as fh:
        for f, lo_a, hi_a, title in snips:
            fh.write('\n# %s  [0x%08x,0x%08x)  from %s\n' % (title, lo_a, hi_a, f))
            for line in open(D + f):
                if len(line) > 9 and line[8] == ':':
                    try:
                        a = int(line[:8], 16)
                    except ValueError:
                        continue
                    if lo_a <= a < hi_a:
                        assert a in HOOKS.values() or body[a - VA_DELTA:a - VA_DELTA + 4] == off[a - VA_DELTA:a - VA_DELTA + 4]
                        assert line.split('\t')[1].split() == ['%02x' % x for x in off[a - VA_DELTA:a - VA_DELTA + 4]]
                        fh.write(line)
    res['checks']['official_snippets_bytes_verified_and_unchanged_in_v37'] = True
    json.dump(res, open(os.path.join(OUT, 'verify.json'), 'w'), indent=1)
    ok = (total == 7605 and res['checks']['changed_bytes_outside_known_sites'] == 0 and
          res['checks']['.payload_matches_body'] and res['checks']['.root_pins_matches_body'] and
          all(b['ok'] for b in br.values()) and total_stack == 104 and
          all(v for f, v in same if f != 'ilaunch3') and
          not res['checks']['v36_to_v37_touches_h09_path'] and len(r36) == 3 and not res['checks']['h09_early_path_stores'])
    print(json.dumps({k: res['checks'][k] for k in ('changed_bytes_total', 'changed_bytes_outside_known_sites',
                                                    '.payload_matches_body', '.root_pins_matches_body', 'h09_stack',
                                                    'h09_early_path_stores', 'v36_to_v37_runs', 'v36_to_v37_touches_h09_path')}, indent=1))
    for h, b in br.items():
        print(h, b['word'], b['opcode'], b['target'], b['ok'])
    print('PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
