"""Real product C flows, raw native failures, frozen-validator and wire checks."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c

REVISION_CASES=('review-free-preload','review-free-save','review-free-repeat','r3-workspace-release',
    'r3-install-free-work','r3-install-free-raw','r3-install-free-alloc',
    'review-hidden-engine','r3-hidden-engine-B','r3-newer-generation','r3-target-exists',
    'r3-rename-preserves','r3-rename-source-loss','r3-both-unknown','review-hidden-tweak','r3-hidden-tweak-B',
    'r3-sticky-read','r3-sticky-open','r3-sticky-save-read','r3-sticky-save-open',
    'r3-gxts-rename-preserves','r3-gxts-source-loss','r3-empty-gxts')

VECTOR = r'''
#define main validator_original_main
#include "VALIDATOR"
#undef main
#include "gxts.h"
static void hex(const uint8_t *p,unsigned n){unsigned i;for(i=0;i<n;++i)printf("%02x",p[i]);}
int main(int argc,char **argv)
{
    Gxr2Trust trust;Gxr2View view;GxtsBinding binding;GxtsState state;
    uint8_t raw[GXR2_MAX_FILE],entry[448],encoded[GXTS_BYTES];size_t n;unsigned m,s;
    if(argc!=3||!load_trust(argv[2],&trust)||!read_file(argv[1],raw,sizeof(raw),&n))return 2;
    for(m=0;m<3;++m) {
        if(gxr2_validate(raw,n,&trust,&trust.modules[m].unit,0,&view)!=GXR2_OK)return 3;
        for(s=1;s<=16;++s) {
            if(gxr2_expand(&view,m,s,entry)!=GXR2_OK||gxts_bind(&view,m,s,&binding)!=GXTS_OK)return 4;
            gxts_defaults(&binding,&state);state.generation=7;
            if(gxts_encode(&binding,&state,encoded)!=GXTS_OK)return 5;
            printf("%u %u ",m,s);hex(entry,448);putchar(' ');hex(binding.identity,160);
            putchar(' ');hex(encoded,GXTS_BYTES);putchar('\n');
        }
    }
    return 0;
}
'''


def vectors():
    out=c.LOCAL/'independent';out.mkdir(exist_ok=True)
    results={}
    for label,p in (('frozen-v32',c.UPSTREAM/'containers/product'),('r2',c.PRODUCT)):
        container=p/'src/firmware/card_container_v2';core=p/'src/firmware/engine/core'
        driver=out/(label+'.c');driver.write_text(VECTOR.replace('VALIDATOR',str(container/'validate.c')))
        binary=out/label
        flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DRV_HOST',
               '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
        c.run(['/usr/bin/clang',*flags,'-include',core/'eng_crc_bindings.h','-I',container,
               driver,*[container/n for n in ('gate.c','semantic.c','common.c','api.c','gxts.c')],
               p.parents[1]/'engine_services/crc.c',p/'memory.c',core/'eng_crc_compat.c',
               '-o',binary],'vector-compile-'+label)
        folder=c.LOCAL/'product/candidates/full-r3'
        r=c.run([binary,folder/'GXRCE.DAT',folder/'trust.bin'],'vector-final-'+label)
        results[label]=[dict(unit=int(row[0]),slot=int(row[1]),entry=row[2],binding=row[3],gxts=row[4])
                        for row in (line.split() for line in r.stdout.splitlines())]
        assert len(results[label])==48
    assert results['frozen-v32']==results['r2'],'streaming CRC changed binding or GXTS wire bytes'
    previous_r2=c.ROOT/'firmware/engine_fix_r1/local/product/candidates/full-r2'
    old_r2=c.run([out/'frozen-v32',previous_r2/'GXRCE.DAT',previous_r2/'trust.bin'],'vector-full-r2')
    assert old_r2.stdout==r.stdout,'full-r3 must preserve all full-r2 entries, bindings and default wire records'
    previous=c.UPSTREAM/'local/product/candidates/full'
    old=c.run([out/'frozen-v32',previous/'GXRCE.DAT',previous/'trust.bin'],'vector-original-full')
    oldrows=[line.split() for line in old.stdout.splitlines()]
    current=results['r2'];checks=[]
    mount=c.ROOT/'research/mount_calib_r1/local/entries'
    records=(mount/'records64.bin').read_bytes()
    final=(c.LOCAL/'product/candidates/full-r3/GXRCE.DAT').read_bytes()
    u32=lambda b,o:int.from_bytes(b[o:o+4],'big')
    banks=u32(final,180)
    import zlib
    for i,row in enumerate(current):
        m,s=row['unit'],row['slot'];actual=bytes.fromhex(row['entry'])
        if m<2 or s>8:
            assert row['entry']==oldrows[i][2]
            source='resident_v32 full: C-expanded slot'
        else:
            raw=(mount/f'{s:02}.entry').read_bytes();record=records[64*(s-1):64*s]
            target_record=final[banks+2*1056+32+64*(s-1):banks+2*1056+96+64*(s-1)]
            assert target_record==record
            expected=bytearray(raw);expected[0]=s
            identity=record[2:3]+record[4:36]+record[3:4]+record[36:51]
            expected[4:8]=(zlib.crc32(identity)&0xffffffff).to_bytes(4,'big')
            assert actual==expected and not actual[1]&6 and actual[445:447]==b'\0\2'
            source=f'research/mount_calib_r1/local/entries/{s:02}.entry'
        checks.append(dict(unit=m,slot=s,source=source,entry_sha256=__import__('hashlib').sha256(actual).hexdigest(),equal=True))
    c.save(c.LOCAL/'data-and-gxts-compatibility.json',dict(status='PASS',slots=checks,
        frozen_complete_validator_units=3,GXTS_wire_equal_slots=48,streaming_CRC_preserves_bytes=True,
        full_r2_entries_bindings_and_wire_equal_slots=48))


def semantic_negatives():
    import zlib
    folder=c.LOCAL/'product/candidates/full-r3';raw=(folder/'GXRCE.DAT').read_bytes()
    out=c.LOCAL/'semantic-negatives';out.mkdir(exist_ok=True);results=[]
    for kind in ('wrong-slot','wrong-identity'):
        for unit,slot in ((0,1),(0,5),(0,7),(0,9),(2,1),(2,6),(2,7),(2,8)):
            b=bytearray(raw);bank=int.from_bytes(b[180:184],'big')+unit*1056;rec=bank+32+64*(slot-1)
            if kind=='wrong-slot':b[rec]=16
            else:b[rec+4]=ord('9') if b[rec+4]!=ord('9') else ord('8')
            for target,start,end in ((rec+60,rec,rec+60),(bank+24,bank+32,bank+1056),(bank+28,bank,bank+28),(24,256,len(b))):
                b[target:target+4]=(zlib.crc32(b[start:end])&0xffffffff).to_bytes(4,'big')
            b[20:24]=bytes(4);b[20:24]=(zlib.crc32(b[:256])&0xffffffff).to_bytes(4,'big')
            path=out/f'{kind}-{unit}-{slot}.DAT';path.write_bytes(b)
            result=c.run([c.LOCAL/'independent/frozen-v32',path,folder/'trust.bin'],f'semantic-{kind}-{unit}-{slot}',check=False)
            assert result.returncode==3,'the complete frozen C validator must reject the semantic mutation'
            results.append(dict(kind=kind,unit=unit,slot=slot,returncode=result.returncode,all_CRCS_resealed=True))
    c.save(c.LOCAL/'semantic-results.json',results)


def main():
    c.guard()
    r=c.run(['/usr/bin/python3','-I','-B',c.PRODUCT/'verify.py'],'complete-product-suite',timeout=180)
    base=json.loads((c.LOCAL/'product/acceptance.json').read_text())
    print(r.stdout.strip())
    folder=c.LOCAL/'product/candidates/full-r3';host=c.LOCAL/'product/host/host_checks'
    extras=['firstboot-empty','gxts-read-failure','gxts-partial-io','install-readback-failure',
            'install-readback-mismatch','install-readback-open','gxts-readback-open',
            'gxts-readback-mismatch','lease-preload','lease-save']
    extras += ['boundary-'+name+suffix for name in ('open','create','read','write','close','rename','delete')
               for suffix in ('','-neg2')]
    checks=[]
    for scenario in extras:
        for unit in range(3):
            r=c.run([host,scenario,unit,folder/'GXRCE.DAT',folder/'GXRCE.DAT',folder/'trust.bin',
                     folder/'effective-rows.bin',folder/'effective-rows.bin'],f'extra-{scenario}-{unit}')
            assert r.stdout.rstrip().splitlines()[-1].startswith('OK scenario=')
            checks.append(dict(scenario=scenario,unit=unit,status='PASS',output=r.stdout.strip()))
    c.save(c.LOCAL/'extra-acceptance.json',checks)
    revisions=[];previous=c.LOCAL/'product/candidates/full-r3-prev'
    for scenario in REVISION_CASES:
        for unit in range(3):
            result=c.run([host,scenario,unit,previous/'GXRCE.DAT',folder/'GXRCE.DAT',folder/'trust.bin',
                          previous/'effective-rows.bin',folder/'effective-rows.bin'],f'revision-{scenario}-{unit}')
            assert result.stdout.rstrip().splitlines()[-1].startswith('OK scenario=')
            revisions.append(dict(scenario=scenario,unit=unit,status='PASS',output=result.stdout,
                                  container_sha256=c.sha(folder/'GXRCE.DAT')))
    c.save(c.LOCAL/'revision-acceptance.json',revisions)
    risks=[]
    for unit in range(3):
        scenario='r3-gxts-persistent-minus1'
        result=c.run([host,scenario,unit,previous/'GXRCE.DAT',folder/'GXRCE.DAT',folder/'trust.bin',
                      previous/'effective-rows.bin',folder/'effective-rows.bin'],f'limitation-{scenario}-{unit}')
        assert 'RESIDUAL_RISK' in result.stdout
        risks.append(dict(unit=unit,status='LIMITATION_REPRODUCED',output=result.stdout))
    c.save(c.LOCAL/'remaining-risk.json',risks)
    vectors()
    semantic_negatives()
    c.save(c.LOCAL/'test-summary.json',dict(status='PASS',product_cases=len(base),extra_cases=len(checks),
        revision_cases=len(revisions),total_cases=len(base)+len(checks)+len(revisions),
        remaining_risk_cases=len(risks),F02_unconditional_preservation_proven=False,native_missing_code=-1,ASan_UBSan=True,
        frozen_full_C_validator_units=3,expanded_slots=48,GXTS_wire_compatibility_slots=48,
        native_transport='host doubles',M32R_instructions_executed=False,camera_acceptance=False))
    print(f'PASS {len(base)+len(checks)+len(revisions)} product/negative cases; frozen validator 3 units; 48 slots and GXTS bytes match; 16 semantic mutants rejected')


if __name__=='__main__':main()
