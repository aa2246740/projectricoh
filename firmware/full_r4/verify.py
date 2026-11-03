"""Full C validation, 48 expanded slots, real -1 fixture flows and old GXTS."""
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c

VECTOR = r'''
#define main original_validator_main
#include "VALIDATOR"
#undef main
#include "gxts.h"
static void hex(const uint8_t *p,unsigned n){unsigned i;for(i=0;i<n;++i)printf("%02x",p[i]);}
static unsigned get32(const uint8_t *p){return (unsigned)p[0]<<24|(unsigned)p[1]<<16|(unsigned)p[2]<<8|p[3];}
int main(int argc,char **argv)
{
    Gxr2Trust trust;Gxr2View view;GxtsBinding binding;GxtsState state;
    uint8_t raw[GXR2_MAX_FILE],entry[448],encoded[GXTS_BYTES];size_t n;unsigned m,s,bank;
    if(argc!=3||!load_trust(argv[2],&trust)||!read_file(argv[1],raw,sizeof(raw),&n))return 2;
    for(m=0;m<3;++m){
        if(gxr2_validate(raw,n,&trust,&trust.modules[m].unit,0,&view)!=GXR2_OK)return 3;
        bank=get32(raw+view.sections[2].offset+64*m+16);
        for(s=1;s<=16;++s){
            if(gxr2_expand(&view,m,s,entry)!=GXR2_OK||gxts_bind(&view,m,s,&binding)!=GXTS_OK)return 4;
            gxts_defaults(&binding,&state);state.generation=7;
            if(gxts_encode(&binding,&state,encoded)!=GXTS_OK)return 5;
            printf("%u %u ",m,s);hex(entry,448);putchar(' ');hex(raw+bank+32+64*(s-1),64);
            putchar(' ');hex(binding.identity,160);putchar(' ');hex(encoded,GXTS_BYTES);putchar('\n');
        }
    }
    return 0;
}
'''


def compile_all(build):
    out = c.LOCAL / 'host'
    out.mkdir(exist_ok=True)
    flags = ['-std=c11', '-O1', '-g', '-fno-omit-frame-pointer', '-fsanitize=address,undefined',
             '-fno-sanitize-recover=all', '-Wall', '-Wextra', '-Werror', '-DRV_HOST', '-DENG_HOST',
             '-DPN_CORE_HEADER="../core/eng_core.h"', '-DPN_GXTS_SHARED_PARAMETER', '-I', c.PRODUCT]
    slim = c.RESIDENT
    rows = [r for r in build.sources() if r[0].suffix == '.c']
    rows += [(c.HERE / 'host.c', False)]
    rows += [(slim / n, False) for n in ('resident.c', 'loader.c', 'shared.c', 'hooks.c', 'runtime.c', 'validate_envelope.inc.c')]
    rows += [(c.ROOT / 'firmware/resident_v32/local/resident/trust.c', False)]
    objects = []
    for i, (src, service) in enumerate(rows):
        obj = out / (f'{i:02}-' + src.stem + '.o')
        objects.append(obj)
        extra = ['-DRV_ENGINE_SERVICES'] if service else []
        if src.name == 'runtime.c':
            extra += ['-Dmemcpy=' + ('es_memcpy' if service else 'rv_memcpy'),
                      '-Dmemset=' + ('es_memset' if service else 'rv_memset')]
        if src.name == 'gxts.c':
            extra += ['-include', build.SRC / 'firmware/engine/core/eng_crc_bindings.h']
        c.run(['/usr/bin/clang', *flags, *extra, '-I', slim, '-c', src, '-o', obj], 'host-compile-' + str(i))
    c.run(['/usr/bin/clang', *flags, *objects, '-o', out / 'host_checks'], 'host-link')
    container = build.SRC / 'firmware/card_container_v2'
    core = build.SRC / 'firmware/engine/core'
    crc = c.ROOT / 'firmware/engine_fix_r2/engine_services/crc.c'
    validator = [container / n for n in ('gate.c', 'semantic.c', 'common.c', 'api.c')]
    common = ['/usr/bin/clang', *flags, '-include', core / 'eng_crc_bindings.h', '-I', container]
    tail = [*validator, crc, c.PRODUCT / 'memory.c', core / 'eng_crc_compat.c']
    c.run([*common, container / 'validate.c', *tail, '-o', out / 'validate'], 'validator-compile')
    driver = out / 'expand.c'
    c.write(driver, VECTOR.replace('VALIDATOR', str(container / 'validate.c')).encode())
    c.run([*common, driver, container / 'gxts.c', *tail, '-o', out / 'expand'], 'expand-compile')
    return out


def vectors(out, pack):
    streams = {}
    replacements = {(row['unit'], row['slot']): row for row in
                    json.loads((c.OUT / 'manifest.json').read_text())['changes']}
    for label, folder in (('full-r3', c.BASE), ('full-r4', c.OUT)):
        result = c.run([out / 'expand', folder / 'GXRCE.DAT', folder / 'trust.bin'], 'expand-' + label)
        rows = [line.split() for line in result.stdout.splitlines()]
        assert len(rows) == 48
        streams[label] = {(int(row[0]), int(row[1])): [bytes.fromhex(v) for v in row[2:]] for row in rows}
    changes = {(0, 1), (0, 2), (2, 1)}
    checks = []
    raw = (c.OUT / 'GXRCE.DAT').read_bytes()
    old = (c.BASE / 'GXRCE.DAT').read_bytes()
    old_bank = pack.u32(old, 180)
    for mi, name in enumerate(pack.NAMES):
        for slot in range(1, 17):
            key = (mi, slot)
            entry, record, binding, default = streams['full-r4'][key]
            base_entry, base_record, base_binding, _ = streams['full-r3'][key]
            assert len(entry) == 448 and len(record) == 64 and len(binding) == 160 and len(default) == 240
            owner = base_entry[0]
            assert base_entry == (c.BASE / 'expanded' / name / f'{owner:02}.entry').read_bytes()
            assert base_record == old[old_bank + mi*1056 + 32 + (slot-1)*64:old_bank + mi*1056 + 96 + (slot-1)*64]
            expected = c.LOCAL / 'rebound' / name / f'{slot:02}.entry'
            if key in changes:
                assert entry == expected.read_bytes() and entry != base_entry
                source = replacements[name, slot]
                table = (c.ROOT / source['source']).read_bytes()
                source_entries = [table[16 + 448*i:16 + 448*(i+1)] for i in range(8)]
                rebound = bytearray(next(e for e in source_entries if e[0] == source['source_slot']))
                rebound[0] = slot
                identity = record[2:3] + record[4:36] + record[3:4] + record[36:51]
                rebound[4:8] = pack.crc(identity).to_bytes(4, 'big')
                assert entry == rebound
                assert binding != base_binding
            else:
                assert entry == base_entry and binding == base_binding
            assert record == base_record
            assert pack.u32(record, 60) == pack.crc(record[:60])
            assert entry == (c.OUT / 'expanded' / name / f'{slot:02}.entry').read_bytes()
            if owner != 4:
                assert pack.u32(entry, 4) == pack.crc(pack.identity(record))
            checks.append(dict(unit=name, slot=slot, changed=key in changes,
                               entry_sha256=hashlib.sha256(entry).hexdigest(),
                               record_sha256=hashlib.sha256(record).hexdigest(), record_equal=True,
                               binding_changed=binding != base_binding))
    # Slot 02 has precisely the v6 colour data carried by the unchanged slot 10.
    neg2 = bytearray(streams['full-r4'][(0, 2)][0])
    neg10 = bytearray(streams['full-r4'][(0, 10)][0])
    for entry in (neg2, neg10):
        entry[0] = 0
        entry[4:8] = bytes(4)
    assert neg2 == neg10
    for label, folder in (('full-r3', c.BASE), ('full-r4', c.OUT)):
        golden = bytearray()
        for mi in range(3):
            stock = streams[label][mi, 4][0]
            for slot in range(1, 17):
                entry = streams[label][mi, slot][0]
                for _, count, offset, _, mask, _ in pack.v1.ROWS:
                    effective = entry if not mask or entry[1] & mask else stock
                    golden += effective[offset:offset + count]
                golden += (0 if entry[1] & 4 else 2).to_bytes(2, 'big')
        assert bytes(golden) == (folder / 'effective-rows.bin').read_bytes()
    c.save(c.LOCAL / 'slot-checks.json', dict(status='PASS', slots=checks, changed_entries=3,
           unchanged_entries=45, identical_records=48, expanded_slots=48, golden_slots=48,
           slot02_matches_slot10_colour_data=True, all_current_C_paths=True))


def flows(out):
    scenarios = ('r4-first-replace', 'r4-first-reject', 'r4-update-ok-replace', 'r4-update-ok-reject',
                 'r4-update-clean-replace', 'r4-update-clean-reject', 'r4-downgrade')
    results = []
    cases = [(scenario, unit) for scenario in scenarios for unit in range(3)]
    cases += [('r4-gxts', 0), ('r4-gxts', 2)]
    for scenario, unit in cases:
        evidence = c.LOCAL / 'host-evidence' / f'{scenario}-{unit}'
        evidence.mkdir(parents=True, exist_ok=True)
        r = c.run([out / 'host_checks', scenario, unit, c.BASE / 'GXRCE.DAT', c.OUT / 'GXRCE.DAT',
                   c.OUT / 'trust.bin', c.BASE / 'effective-rows.bin', c.OUT / 'effective-rows.bin', evidence],
                  f'flow-{scenario}-{unit}')
        last = r.stdout.splitlines()[-1]
        match = re.search(r'assertions=(\d+)', last)
        assert match and last.startswith('OK ') and 'missing_open=-1' in last
        expected_collision = scenario == 'r4-update-ok-reject'
        assert ('EXPECTED_OK_COLLISION' in r.stdout) == expected_collision
        results.append(dict(scenario=scenario, unit=unit, status='EXPECTED_COLLISION' if expected_collision else 'PASS',
                            assertions=int(match[1]), output=r.stdout))
    c.save(c.LOCAL / 'host-results.json', results)
    return results


def main():
    c.guard()
    frozen = json.loads((c.LOCAL / 'inputs-before.json').read_text())
    assert c.snapshot() == frozen
    _, pack, build = c.upstream()
    layout = json.loads((c.OUT / 'layout.json').read_text())
    header = (c.ROOT / 'firmware/engine_fix_r2/local/product/entries.h').read_text()
    for name, offset in layout['entries'].items():
        assert f'#define OFF_{name.upper()} {offset}u\n' in header
    out = compile_all(build)
    validators = []
    for name in pack.NAMES:
        r = c.run([out / 'validate', c.OUT / 'GXRCE.DAT', c.OUT / 'trust.bin', name], 'validate-' + name)
        assert 'OK build=106' in r.stdout and 'semantic=1' in r.stdout
        validators.append(dict(unit=name, output=r.stdout.strip()))
    vectors(out, pack)
    results = flows(out)
    assert c.snapshot() == frozen
    c.save(c.LOCAL / 'scope-after.json', dict(status='PASS', protected_files=len(frozen), unchanged=True))
    summary = dict(status='PASS', current_C_validator=validators, expanded_slots=48, changed_entries=3,
                   unchanged_entries=45, identical_records=48, golden_slots=48,
                   host_cases=len(results), successful_host_cases=sum(r['status'] == 'PASS' for r in results),
                   expected_OK_collision_cases=sum(r['status'] == 'EXPECTED_COLLISION' for r in results),
                   assertions=sum(r['assertions'] for r in results), GXTS_slots=4,
                   required_card_precondition='delete old GXRCE.OK and any old GXRCE.DAT before copying full-r4 GXRCE.DAT',
                   real_camera_rename_semantics='UNPROVEN', camera_acceptance=False)
    c.save(c.LOCAL / 'verification.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
