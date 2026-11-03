"""Compile real resident/gen114 services and test both installed artifacts."""
import importlib.util
import json
from pathlib import Path
import struct

s=importlib.util.spec_from_file_location('verify_common',Path(__file__).with_name('common.py'))
c=importlib.util.module_from_spec(s);s.loader.exec_module(c)


def main():
    c.guard();out=c.LOCAL/'host';out.mkdir(exist_ok=True)
    c.load(c.HERE/'native_model.py','verify_native_order').main()
    service_build=json.loads((c.LOCAL/'service-build.json').read_text())
    assert c.sha(c.ARCHIVE)==service_build['archive_sha256']
    for path,expected in service_build['copies'].items():assert c.sha(c.ROOT/path)==expected
    e=c.Elf(c.RESIDENT);sym=e.symbols['rv_trust'];sec=e.sections[sym['section']]
    raw=e.content(sec)[sym['value']-sec['va']:sym['value']-sec['va']+80]
    literal='{'+','.join('{'+','.join(str(b) for b in f)+'}' for f in (raw[:32],raw[32:64],raw[64:]))+'}'
    pins=e.symbols['rv_pins'];sec=e.sections[pins['section']]
    values=struct.unpack_from('>3I',e.content(sec),pins['value']-sec['va'])
    (c.LOCAL/'trust.inc').write_text('const RvTrust rv_trust='+literal+';\nconst uint32_t rv_pins[3]={'
        +','.join(str(x)+'u' for x in values)+'};\nstatic const uint8_t p0_running_body[32]={'
        +','.join(str(x) for x in bytes.fromhex(c.sha(c.BODY)))+'};\n')
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DRV_HOST',
           '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
           '-fno-builtin','-I',c.HERE,'-I',c.R]
    sources=[(c.HERE/n,False) for n in ('host_checks.c','probe.c','kernel.c','support.c')]
    sources += [(c.LOCAL/n,False) for n in ('data.c','blackbox.c')]
    sources += [(c.R/n,False) for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    sources += [(c.S/n,True) for n in ('services.c','api.c','runtime.c','crc.c','mark.c','native_seed.c')]
    sources += [(c.R/'shared.c',True)]
    sources += [(c.R.parent/'engine_services/native_seed.c',True)]
    panel=c.PRODUCT/'src/firmware/engine/panel'
    sources += [(panel/n,False) for n in ('panel_store.c','panel_port.c')]
    sources += [(c.PRODUCT/'memory.c',False)]
    sources += [(c.PRODUCT/'src/firmware/card_container_v2'/n,False) for n in ('gate.c','common.c')]
    objects=[]
    for i,(source,service) in enumerate(sources):
        obj=out/(str(i)+'-'+source.stem+'.o');objects.append(obj)
        extra=['-DRV_ENGINE_SERVICES'] if service else []
        if source.name=='common.c':extra+=['-Dgxr2_crc32=gate_crc32']
        if source==c.R.parent/'engine_services/native_seed.c':extra+=['-Drv_native_seed=old_rv_native_seed']
        if source.name=='runtime.c':extra+=['-Dmemcpy=host_private_memcpy','-Dmemset=host_private_memset'] if not service else ['-Dmemcpy=host_service_memcpy','-Dmemset=host_service_memset']
        c.run(['/usr/bin/clang',*flags,*extra,'-c',source,'-o',obj],'host-compile-'+str(i))
    binary=out/'checks'
    c.run(['/usr/bin/clang','-fsanitize=address,undefined',*objects,'-o',binary],'host-link')
    runs=[]
    for generation,artifact in ((113,c.FULL),(114,c.FULL114)):
        if generation==114:assert c.sha(artifact)=='132e56389808970b0db8a8c4a359c46f18f0fb2423ecbc11f671d18df19a49a5'
        output=c.LOCAL/('host-GXRBX'+('-114' if generation==114 else '')+'.BIN')
        r=c.run([binary,c.LOCAL/'GXRCE.DAT',artifact,output],'host-run-'+str(generation))
        assert r.stdout.startswith('PASS host installed='+str(generation)+' ')
        runs.append(dict(generation=generation,fixture=str(artifact.relative_to(c.ROOT)),fixture_sha256=c.sha(artifact),
            summary=r.stdout.strip(),log=str(output.relative_to(c.ROOT)),log_sha256=c.sha(output)))
        print(r.stdout.strip())
    c.save(c.LOCAL/'host-results.json',dict(status='PASS',dat_sha256=c.sha(c.LOCAL/'GXRCE.DAT'),runs=runs,
        resident_loader='real frozen C',services='gen114 source copies; target sections/relocations match original archive',
        install='real ps_install, product gate and envelope-only verifier',
        generations=[113,114,115,4294967295],actual_product_generations=[113,114],future_generations='in-memory header fixtures for install rejection only',
        first_entry=dict(prior_types=[0,4,9],table='0x2022F56C',capacity=256,published=True,old_seed_rejected=True),
        later_entry=dict(prior_type=5,published=True),native_view=dict(count=1,tag=33,state='0x2022F71C'),
        full_flow=['first H01 REF','OK end reference','reopen','4 admission DOWN callbacks','72 sample DOWN callbacks','DONE','MENU out'],
        legacy_hand_seed='labelled compatibility regression only',
        ui_entry='real H01/H02/H07/H08 C',native_calls='official byte slices plus host boundary doubles',product_entries='selection-only doubles',
        native_model_sha256=c.sha(c.LOCAL/'native_model.h'),native_generator_sha256=c.sha(c.HERE/'native_model.py'),
        sanitizers='ASan+UBSan',camera_tested=False,
        sources={str(p.relative_to(c.ROOT)):c.sha(p) for p,_ in sources}))


if __name__=='__main__':main()
