"""Isolate raw -1 versus fixture -2 using the unchanged real product/resident C."""
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('diag_common',Path(__file__).with_name('common.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

DRIVER=r'''
int main(int argc,char **argv)
{
    uint8_t rawtrust[232],before[4096];unsigned i;RvRequest q={0};RvReply reply;RvSession *s;int32_t result;
    if(argc!=5&&argc!=6)return 2;
    scenario="missing-code-isolation";unit=(unsigned)strtoul(argv[4],0,10);CHECK(unit<3);
    diag_missing_code=(int)strtol(argv[3],0,10);
    base_bytes=load_file(argv[1],base_raw,sizeof(base_raw));new_bytes=base_bytes;memcpy(new_raw,base_raw,base_bytes);
    CHECK(load_file(argv[2],rawtrust,sizeof(rawtrust))==232);
    memcpy(trust.body_sha256,rawtrust+8,32);memcpy(trust.resident_build_id,rawtrust+40,32);
    memcpy(trust.resident_abi_id,rawtrust+72,16);
    for(i=0;i<3;i++){
        memcpy(&trust.modules[i].unit,&units[i],sizeof(units[i]));
        trust.modules[i].stock_crc32=be32(rawtrust+100+48*i);
        memcpy(trust.modules[i].stock_sha256,rawtrust+104+48*i,32);
    }
    reboot();put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);
    memcpy(before,RV_PTR(0x20500000),sizeof(before));
    CHECK(rv_load(&root,&rv_trust)==RV_OK);s=session();
    /* Skip install before its first write-capable stage. Isolate GXTS preload
     * with the same allocation failure for both missing-file return codes. */
    if(argc==5)fail_alloc=alloc_calls+1;
    result=rv_engine(&root,s->entries.menu_open,&q,&reply);
    CHECK(!writes&&!renames&&!rpc_w&&!previews&&opens==closes);
    CHECK(!memcmp(before,RV_PTR(0x20500000),sizeof(before)));
    CHECK(file("/ATA1/GXRCE.DAT")&&!file("/ATA1/GXRCE.OK"));
    if(diag_missing_code==-2){CHECK(result==RV_CONSUMED&&root.state==RV_READY&&RV_BYTE(0x2022f5ac)==16);}
    else {CHECK(result==RV_CLOSE_AND_PASS&&root.state==RV_DISABLED_UNTIL_REBOOT&&RV_BYTE(0x2022f5ac)==7);}
    printf("PASS missing_raw=%d unit=%u full_load=OK menu_result=%d reply_status=%d "
        "rows=%u root_state=%u root_fault=%d check_failure=%u install=%d "
        "RPC_W=0 S_writes=0 file_writes=0 rename=0\n",diag_missing_code,unit,result,reply.status,
        RV_BYTE(0x2022f5ac),root.state,root.fault,root.check_failure,ig_host_install_status());
    return 0;
}
'''


def main():
    c.guard();p=c.ROOT/'firmware/resident_v32/containers/product';out=c.LOCAL/'product-repro';out.mkdir(exist_ok=True)
    upstream=(p/'host_checks.c').read_text()
    original='if(i<0||(!write&&!files[i].exists))return -2;'
    assert upstream.count(original)==1
    source=upstream.replace(original,'if(i<0||(!write&&!files[i].exists))return diag_missing_code;')
    source=source.replace('static int32_t open_file(', 'static int diag_missing_code=-2;\nstatic int32_t open_file(')
    source=source.replace('#include "../../local/product/entries.h"',
                          '#include "'+str(p.parents[1]/'local/product/entries.h')+'"')
    source=source.replace('int main(int argc,char **argv)','int upstream_main(int argc,char **argv)')
    driver=out/'driver.c';driver.write_text(source+DRIVER)
    b=c.load(p/'build.py','diag_readonly_product_source_list')
    sources=[x for x in b.sources() if x[0].suffix=='.c']
    sources += [(c.R/n,False) for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    sources += [(c.LOCAL/'trust.c',False),(driver,False)]
    flags=['/usr/bin/clang','-std=c11','-O1','-g','-fno-omit-frame-pointer','-fsanitize=address,undefined',
           '-fno-sanitize-recover=all','-Wall','-Wextra','-Werror','-DRV_HOST','-DENG_HOST',
           '-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER','-I',p,'-I',c.R]
    objects=[]
    for i,(src,service) in enumerate(sources):
        obj=out/(str(i)+'-'+src.stem+'.o');objects.append(obj);extra=[]
        if service:extra+=['-DRV_ENGINE_SERVICES']
        if src.name=='runtime.c':extra+=['-Dmemcpy='+('es_memcpy' if service else 'rv_memcpy'),
                                         '-Dmemset='+('es_memset' if service else 'rv_memset')]
        if src.name=='gxts.c':extra+=['-include',p/'src/firmware/engine/core/eng_crc_bindings.h']
        c.run([*flags,*extra,'-c',src,'-o',obj],'product-repro-compile-'+str(i))
    binary=out/'checks';c.run(['/usr/bin/clang','-fsanitize=address,undefined',*objects,'-o',binary],'product-repro-link')
    trust=p.parents[1]/'local/product/candidates/full/trust.bin'
    results=[]
    for code in (-2,-1):
        for unit in range(3):
            run=c.run([binary,c.FULL,trust,str(code),str(unit)],f'product-repro-missing-{code}-{unit}')
            assert run.stdout.startswith('PASS ')
            results.append(dict(missing_native_code=code,unit=unit,output=run.stdout.strip()))
    for unit in range(3):
        run=c.run([binary,c.FULL,trust,'-1',str(unit),'native-firstboot'],f'product-repro-firstboot-{unit}')
        assert 'rows=7 root_state=6' in run.stdout
        results.append(dict(missing_native_code=-1,unit=unit,no_forced_allocation_failure=True,output=run.stdout.strip()))
    c.save(c.LOCAL/'product-reproduction.json',dict(status='PASS',cases=results,
        isolates='Only missing-file native return differs; same full input and forced install allocation failure',
        actual_product_C=True,actual_resident_C=True,ASan_UBSan=True,
        transport='double; official wrapper has -1 failure exits, no -2 translation',
        scope='Conditional counterexample, not observation of the camera failed boot'))
    for row in results:print(row['output'])


if __name__=='__main__':main()
