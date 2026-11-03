#!/usr/bin/env python3
"""Independent boundary cases on frozen sources with declared native doubles."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
LOCAL = HERE / 'local'
spec = importlib.util.spec_from_file_location('review', HERE / 'review.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

DRIVER = r'''
#define main development_fixture_main
#define rv_invoke fixture_invoke
#define rv_native_open fixture_native_open
#define rv_native_read fixture_native_read
#define rv_native_alloc fixture_native_alloc
#define rv_native_sd_id fixture_native_sd_id
#include "../frozen/firmware/resident_v3/resident/v3_checks.c"
#undef main
#undef rv_invoke
#undef rv_native_open
#undef rv_native_read
#undef rv_native_alloc
#undef rv_native_sd_id
static uint32_t last_entry,last_row;
static int32_t force_event_result=-1;
static uint32_t read_attempts,read_fail_at,fail_alloc,fd_peak,sd_calls,sd_change_at;
static unsigned char fixture_backup[RV_MAX_FILE+1];
int32_t rv_native_open(const char *path,uint32_t flags)
{
    unsigned i,live=0;int32_t fd=fixture_native_open(path,flags);
    for(i=0;i<3;++i)live+=fds[i].live;
    if(live>fd_peak)fd_peak=live;
    CHECK(live<=1);return fd;
}
int32_t rv_native_read(int32_t fd,void *out,uint32_t n)
{
    ++read_attempts;if(read_fail_at&&read_attempts>=read_fail_at)return -1;
    return fixture_native_read(fd,out,n);
}
uint32_t rv_native_alloc(uint32_t n){return fail_alloc?0:fixture_native_alloc(n);}
int32_t rv_native_sd_id(void *out)
{
    int32_t result=fixture_native_sd_id(out);++sd_calls;
    if(sd_change_at&&sd_calls>=sd_change_at)((uint32_t *)out)[0]^=0x100;
    return result;
}
int32_t rv_invoke(uint32_t a,const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    int32_t result;last_entry=a;last_row=q->args[8];result=fixture_invoke(a,api,context,q,p);
    if(force_event_result>=0&&q->args[8]==7)return force_event_result;
    return result;
}
int main(int argc,char **argv)
{
    uint32_t block,snap,was_free,was_invoke,frame[32]={0},row,full_bytes,i;
    RvRequest q={0};RvReply p;RvSession *s;
    CHECK(development_fixture_main(argc,argv)==0);
    CHECK(!irq_depth&&psw==0xc1);
    /* Model a native allocation reusing the main address and size while the
     * resident root survives. Its new payload is not a resident session. */
    reset();s=load();block=root.block;was_free=frees;was_invoke=invokes;
    memset(RV_PTR(block),0,root.block_bytes);
    CHECK(rv_allocation(block,root.block_bytes,root.alloc_bytes));
    CHECK(rv_check(&root)==RV_CHECK_SESSION);
    CHECK(rv_engine(&root,264,&q,&p)==RV_FAULT);
    CHECK(invokes==was_invoke&&frees==was_free+1&&RV_BYTE(block-8)==0);
    printf("COUNTEREXAMPLE same_header_reallocated_main replacement_freed=1 old_engine_calls=0 address=%08x\n",block);
    /* Model expiry of the separately retained allocation, as at heap reuse.
     * The fixture's native free marks and poisons it; production never
     * voluntarily frees this snapshot. Do not claim a device event here. */
    reset();load();snap=ui(2);rv_native_free(snap);rv_ui_abort(&root);
    CHECK(RV_WORD(0x2022f5a8)==0x2022d610&&RV_BYTE(0x2022f5ac)==7);
    CHECK(RV_WORD(0x205b0004)==snap&&!root.ui_restore[0]&&RV_BYTE(snap-8)==0);
    printf("COUNTEREXAMPLE expired_snapshot native_view_retains_dead_state=1 recovery_record_erased=1 address=%08x\n",snap);
    reset();load();snap=ui(2);was_invoke=invokes;
    RV_WORD(0x200d3488)=0x20730000;
    CHECK(rv_engine(&root,264,&q,&p)==RV_FAULT&&invokes==was_invoke);
    CHECK(!root.block&&RV_WORD(0x205b0004)==snap&&!root.ui_restore[0]);
    printf("COUNTEREXAMPLE moved_heap old_view_retained=1 snapshot_outside_current_heap=1 address=%08x\n",snap);
    reset();s=load();snap=ui(1);CHECK(s&&snap);
    frame[7]=0x1234;rv_hook_observe(&root,6,frame);
    CHECK(frame[7]==0&&frame[1]==(uint32_t)(uintptr_t)rv_skip_06);
    printf("OBSERVED H06_owned_native_return=0 stage2l_return=2\n");
    for(row=1;row<=16;row+=15){
        reset();s=load();ui(1);RV_BYTE(0x2022f726)=row;
        memset(frame,0,sizeof(frame));rv_hook_observe(&root,8,frame);
        CHECK(last_entry==s->image_address+s->entries.apply_step&&last_row==row);
        printf("OBSERVED H08_native_row=%u engine_arg8=%u product_slot_after_plus_one=%u\n",row,last_row,last_row+1);
    }
    reset();load();snap=ui(1);RV_WORD(0x2037f3bc)=32;
    memset(frame,0,sizeof(frame));frame[11]=0;force_event_result=RV_PASS;
    rv_hook_observe(&root,7,frame);force_event_result=-1;
    CHECK(frame[1]==(uint32_t)(uintptr_t)rv_skip_07&&frame[15]==0);
    CHECK(RV_WORD(0x2037f3bc)==32&&RV_WORD(0x205b0004)==snap&&root.ui_restore[0]);
    puts("COUNTEREXAMPLE H07_close_PASS swallowed=1 overlay_word_still_32=1 owned_view_still_published=1");
    reset();load();was_free=frees;was_invoke=invokes;
    RV_BYTE(0x2040f81c)^=1;memset(frame,0,sizeof(frame));frame[10]=0x20500000;
    rv_hook_observe(&root,9,frame);
    CHECK(frees==was_free+1&&invokes==was_invoke&&!root.block);
    puts("OBSERVED H09_failed_unit_check native_main_free=1 old_engine_calls=0");
    full_bytes=bytes;memcpy(fixture_backup,fixture,bytes);
    for(i=0;i<5;++i){
        reset();enabled=4;bytes=full_bytes;memcpy(fixture,fixture_backup,bytes);
        read_attempts=0;read_fail_at=fail_alloc=sd_calls=sd_change_at=0;
        if(i==0)--bytes;
        if(i==1)fixture[bytes++]=0;
        if(i==2)rv_put32(fixture+16,RV_MAX_FILE+4);
        if(i==3)fail_alloc=1;
        if(i==4)read_fail_at=6;
        CHECK(rv_load(&root,&rv_trust)!=RV_OK&&!root.block&&!(root.flags&RF_BUSY)&&!invokes);
        CHECK(allocs==frees);
        for(row=0;row<3;++row)CHECK(!fds[row].live);
        printf("CASE independent_loader_fault_%u closed_fds=1 allocations=%u frees=%u old_engine_calls=0\n",i,allocs,frees);
    }
    read_fail_at=fail_alloc=0;reset();enabled=4;bytes=full_bytes;memcpy(fixture,fixture_backup,bytes);
    sd_calls=0;sd_change_at=4;
    CHECK(rv_load(&root,&rv_trust)==RV_STALE&&!root.block&&!invokes&&allocs==frees);
    for(i=0;i<3;++i)CHECK(!fds[i].live);
    sd_change_at=0;
    printf("CASE independent_sd_changed fd_peak=%u all_fds_closed=1 old_engine_calls=0\n",fd_peak);
    CHECK(!irq_depth&&psw==0xc1);
    puts("REVIEW_BOUNDARY_CASES_REPRODUCED native_m32r=0 heap_events=modeled engine=double");
    return 0;
}
'''


def main():
    r.preflight()
    out = LOCAL / 'host'
    out.mkdir(exist_ok=True)
    (LOCAL / 'tmp').mkdir(exist_ok=True)
    driver = out / 'review_behaviour.c'
    driver.write_text(DRIVER)
    # Freeze the exact input fixture and trust source, without running builders.
    rels = ['firmware/resident_v3/local/resident/trust.c',
            'firmware/resident_v3/local/resident/fixtures/synthetic-container.fixture']
    inputs = json.loads((LOCAL / 'inputs-before.json').read_text())
    for rel in rels:
        data = (r.ROOT / rel).read_bytes()
        inputs[rel] = dict(size=len(data), sha256=hashlib.sha256(data).hexdigest())
        dest = LOCAL / 'frozen' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    r.save('inputs-before.json', inputs)
    env = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'),
               ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    source = LOCAL / 'frozen/firmware/resident_v3'
    flags = ['/usr/bin/clang', '-std=c11', '-O1', '-g', '-DRV_HOST', '-fno-builtin',
             '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
             '-I', str(source / 'resident')]
    sources = [(source / 'resident' / n, False) for n in
               ['resident.c', 'loader.c', 'shared.c', 'hooks.c', 'runtime.c', 'validate_envelope.inc.c']]
    sources += [(source / 'engine_services' / n, True) for n in
                ['services.c', 'api.c', 'runtime.c', 'crc.c', 'mark.c', 'native_seed.c']]
    sources += [(source / 'resident/shared.c', True), (driver, False),
                (LOCAL / 'frozen/firmware/resident_v3/local/resident/trust.c', False)]
    commands = []
    def run(name, args):
        p = subprocess.run([str(a) for a in args], env=env, text=True, capture_output=True)
        (out / (name+'.log')).write_text(p.stdout+p.stderr)
        commands.append(dict(name=name, argv=[str(a) for a in args], returncode=p.returncode))
        r.save('host-commands.json', commands)
        if p.returncode:
            (LOCAL / 'failures').mkdir(exist_ok=True)
            (LOCAL / 'failures' / (name+'-'+hashlib.sha256((p.stdout+p.stderr).encode()).hexdigest()[:12]+'.log')).write_text(p.stdout+p.stderr)
            raise SystemExit(p.stdout+p.stderr)
        return p
    objects = []
    for i, (src, service) in enumerate(sources):
        obj = out / ('%02d.o' % i)
        extra = ['-DRV_ENGINE_SERVICES'] if service else []
        if src.name == 'runtime.c':
            extra += ['-Dmemcpy='+('es_test_memcpy' if service else 'rv_test_memcpy'),
                      '-Dmemset='+('es_test_memset' if service else 'rv_test_memset')]
        run('compile-%02d' % i, flags+extra+['-c', src, '-o', obj])
        objects.append(obj)
    binary = out / 'review_behaviour'
    run('link', ['/usr/bin/clang', '-fsanitize=address,undefined', *objects, '-o', binary])
    p = run('behaviour', [binary, LOCAL / 'frozen' / rels[1]])
    print('\n'.join(line for line in p.stdout.splitlines() if not line.startswith('CASE ')))


if __name__ == '__main__':
    main()
