"""Route gen116 host expectations to the explicitly read-only gen117 contract."""
from pathlib import Path
import difflib, json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ORIGINAL=ROOT/'firmware/engine_v37/candidate'
TARGET=HERE/'candidate'
changes=[]
s=(ORIGINAL/'host_v34c.c').read_text()
def swap(old,new,reason):
 global s
 assert old in s,old
 count=s.count(old)
 s=s.replace(old,new)
 changes.append(dict(old=old,new=new,reason=reason,occurrences=count))
def function(name,body,reason):
 global s
 a=s.index('static void '+name+'(');b=s.index('\nstatic void ',a+1)
 old=s[a:b];s=s[:a]+body.rstrip()+'\n'+s[b:]
 changes.append(dict(old=old,new=body,reason=reason,occurrences=1))
swap('#include "../baseline/engine_services/native_seed.c"','#include "../../engine_v37/baseline/engine_services/native_seed.c"','测试负对照只读引用原文件，产品代码不变。')
swap('#define rv_rpc8_native fixture_rpc8','#define rv_native_open fixture_open\n#define rv_native_close fixture_close\n#define rv_rpc8_native fixture_rpc8','记录每个 native open/close。')
swap('#undef rv_rpc8_native','#undef rv_native_open\n#undef rv_native_close\n#undef rv_rpc8_native','记录每个 native open/close。')
swap('static void mutation(const char *p)','''static unsigned native_create_calls,native_write_calls,native_rename_calls,native_delete_calls;
static unsigned native_write_opens,native_preference_opens,native_open_calls,native_close_calls;
int32_t rv_native_open(const char *p,uint32_t flags)
{
    ++native_open_calls;
    if(flags)++native_write_opens;
    CHECK(flags==0);
    if(!strncmp(p,"/IROM/T",7)||!strncmp(p,"/IROM/L",7))++native_preference_opens;
    return fixture_open(p,flags);
}
int32_t rv_native_close(int32_t fd)
{ ++native_close_calls;CHECK(fd>=17&&fd<19&&!fds[fd-17].write);return fixture_close(fd); }
static void mutation(const char *p)''','全阶段检查 open flags=0，close 仅处理只读句柄。')
swap('mutation(p);return fixture_create(p,f);','++native_create_calls;mutation(p);return fixture_create(p,f);','累计所有 native create 尝试。')
swap('mutation(files[fds[fd-17].file].path);return fixture_write(fd,p,n);','++native_write_calls;mutation(files[fds[fd-17].file].path);return fixture_write(fd,p,n);','累计所有 native write 尝试。')
swap('mutation(p);return fixture_delete(p);','++native_delete_calls;mutation(p);return fixture_delete(p);','累计所有 native delete 尝试。')
swap('mutation(a);mutation(b);return fixture_rename(a,b);','++native_rename_calls;mutation(a);mutation(b);return fixture_rename(a,b);','累计所有 native rename 尝试。')
swap('CHECK(t_reads>=1&&log_writes);','CHECK(t_reads>=1&&!log_writes);','T 校验保留，黑盒不落盘。')
swap('native_mode_rows[native_s_modes[mode]]:remembered?remembered:1','native_mode_rows[native_s_modes[mode]]:4','冷启动不读 GXLS，光标等于纯 04。')
swap('matches_recipe(new_raw,remembered?remembered:1,new_golden);','matches_recipe(new_raw,4,new_golden);','冷启动 Fn2/OK 操作针对 04。')
swap('CHECK(first_frame_entry(mode)==(remembered?remembered:1));','CHECK(first_frame_entry(mode)==4);','未提交重开仍高亮 04。')
swap('CHECK(internal_mutations&&!log_writes);','CHECK(!internal_mutations&&!log_writes);','无卡/无 SD 身份也不写 GXLS。')
swap('CHECK(ig_host_install_status()==RV_OK&&(valid_irom(0)||valid_irom(1)));','CHECK(ig_host_install_status()==RV_UNAVAILABLE&&!writes&&!renames);\n    CHECK(valid_irom(0)==(state==1)&&!valid_irom(1));','不安装，原有 IROM 文件保持原状。')
function('blackbox34',r'''static void blackbox34(const char *out)
{
    unsigned count;FILE *f;const uint8_t *ram;uint8_t first[64];
    clean();ready(1);menu();if(!fixture_has_recipes())return;
    ram=RV_PTR(session()->context.state_address+2048);
    CHECK(!memcmp(ram,"GXB03501",8));
    memcpy(first,ram+2496,64);CHECK(!memcmp(first,"GXSD3501",8));
    CHECK(!log_writes);count=log_writes;select_slot(5);CHECK(count==log_writes);
    open_fn2();CHECK(log_writes==count&&!file("/ATA1/GXRBX0.BIN"));
    select_slot(8);CHECK(log_writes==count);close_menu();
    CHECK(log_writes==count&&!file("/ATA1/GXRBX1.BIN"));
    CHECK(be32(ram+44)>0&&!memcmp(first,ram+2496,64));
    root.inflight=1;CHECK(ig_bx_flush(1)==0&&ig_bx_flush(2)==0&&ig_bx_flush(3)==0);root.inflight=0;
    f=fopen(out,"wb");CHECK(f&&fwrite(ram,1,4096,f)==4096&&!fclose(f));
}''','不再要求 SD 两个日志；检查 RAM 环、首次 seed 和无 I/O flush，导出仅为 Host RAM 证据。')
swap('tweak_path(path,slot,0);CHECK(file(path)&&gxts_decode(file(path)->bytes,file(path)->length,&binding,&state)==GXTS_OK&&state.generation==1);','for(replica=0;replica<copies;replica++){tweak_path(path,slot,replica);CHECK(file(path)&&!memcmp(file(path)->bytes,before,sizeof(before)));}\n        CHECK(!native_preference_opens&&!internal_mutations);','旧 GXTS 不读取、不升级，所有旧副本逐字节保持。')
swap('        CHECK(fault_used);\n        if(kind){matches_recipe(new_raw,slot,new_golden);}','        CHECK(!fault_used&&!internal_mutations);\n        if(kind){current(2);}','不触发 GXLS/GXTS 存储故障；Fn2 OK 在 RAM 接受 +2。')
function('quarantine_service34',r'''static void quarantine_service34(void)
{
    RvRequest q={0};RvReply reply;uint32_t card;
    clean();ready(1);menu();root.inflight=1;
    q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];q.args[2]=2;q.args[3]=unit+1;q.args[5]=4;q.args[8]=240;
    CHECK(rv_service(&root,RV_STORAGE,3,&q,&reply)==RV_CAPABILITY);
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];q.args[2]=1;q.args[5]=1;
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
    CHECK(rv_service(&root,RV_STORAGE,2,&q,&reply)==RV_OK&&!(root.flags&RF_QUARANTINE));card=reply.token;
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];q.args[1]=card;
    q.args[6]=session()->context.state_address;q.args[7]=16;
    native_fail_op=4;native_fail_path="/ATA1/GXRCE.DAT";native_fail_left=1;native_fail_code=-1;
    CHECK(rv_service(&root,RV_STORAGE,4,&q,&reply)==RV_IO&&(root.flags&RF_QUARANTINE));
    q.args[6]=q.args[7]=0;CHECK(rv_service(&root,RV_STORAGE,6,&q,&reply)==RV_OK);
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];
    q.args[2]=2;q.args[3]=unit+1;q.args[5]=4;q.args[8]=240;
    CHECK(rv_service(&root,RV_STORAGE,3,&q,&reply)==RV_CONFLICT);
    q.args[8]=0;q.args[9]=2;CHECK(rv_service(&root,RV_STORAGE,7,&q,&reply)==RV_CONFLICT);
    q.args[9]=0;CHECK(rv_service(&root,RV_STORAGE,8,&q,&reply)==RV_CONFLICT);
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];q.args[1]=card;
    q.args[6]=session()->context.state_address;q.args[7]=16;
    CHECK(rv_service(&root,RV_STORAGE,5,&q,&reply)==RV_STALE);
    root.inflight=0;CHECK(root.state==RV_READY&&(root.flags&RF_QUARANTINE));
}''','初始 create 由成功改为 CAPABILITY，无写 token；保留 DAT 读故障和 quarantine 拦截，已关闭 token 写返回 STALE。')
function('log_fault34',r'''static void log_fault34(void)
{
    unsigned op;uint8_t prior[4096];File *old;const char *path="/ATA1/GXRBX1.BIN";
    if(!fixture_has_recipes())return;
    memset(prior,0x5a,sizeof(prior));
    for(op=3;op<=6;op++){
        clean();put_file("/ATA1/GXRBX0.BIN",prior,sizeof(prior));put_file(path,prior,sizeof(prior));
        ready(1);menu();open_fn2();old=file("/ATA1/GXRBX0.BIN");CHECK(old&&old->length==4096);
        native_fail_op=op;native_fail_path=path;native_fail_left=1;native_fail_code=-1;fault_used=0;
        close_menu();CHECK(!fault_used&&root.state==RV_READY&&!(root.flags&RF_UNCERTAIN));
        CHECK(!memcmp(old->bytes,prior,4096)&&!memcmp(file(path)->bytes,prior,4096));
        native_fail_left=0;native_fail_op=0;native_fail_path=0;
        menu();open_fn2();close_menu();CHECK(root.state==RV_READY&&!log_writes);
    }
}''','黑盒故障不可达；预置两份旧日志并验证全部未改、未触发故障、会话仍可用。')
swap('be32(file("/IROM/GXRCE0.DAT")->bytes+28)==be32(new_raw+28)','be32(file("/IROM/GXRCE0.DAT")->bytes+28)==be32(new_raw+28)+1','ACCEPTED_F02 不再覆盖隐藏的较新 IROM 副本。')
swap('synthetic next generation hidden by native open=-1 was replaced by current','synthetic next generation hidden by native open=-1 remains unchanged; zero writes','输出改为本轮实际只读语义。')
swap('CHECK(ig_host_install_status()==RV_CONFLICT&&(root.flags&RF_QUARANTINE));','CHECK(ig_host_install_status()==RV_UNAVAILABLE&&(root.flags&RF_QUARANTINE));','loader 的 quarantine 保留；没有发起安装，安装状态为 UNAVAILABLE。')
swap('CHECK(file("/ATA1/GXRCE.OK")&&!file("/ATA1/GXRCE.DAT"));reboot();','CHECK(!file("/ATA1/GXRCE.OK")&&file("/ATA1/GXRCE.DAT"));reboot();','DAT 始终保留，不重命名 OK。')
swap('CHECK(session()->cursor==(pass?7u:0u));','CHECK(session()->cursor==3);','冷启动 native cursor 零基 3，对应 04。')
swap('if(pass){open_fn2();current(3);close_menu();CHECK(root.state==RV_READY);continue;}','if(pass){open_fn2();current(0);close_menu();CHECK(root.state==RV_READY);continue;}','断电后忽略旧微调，只用当前配方默认值。')
swap('CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK&&internal_mutations>before);','CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK&&internal_mutations==before);','Fn2 OK 接受 RAM 修改，不要求持久写入。')
swap('current(3);tweak_path(path,8,0);saved=file(path);CHECK(saved&&saved->length==GXTS_BYTES);','current(3);tweak_path(path,8,0);saved=file(path);CHECK(!saved);','GXTS 不创建。')
swap('last_path(path,0);saved=file(path);CHECK(saved&&saved->length==192&&saved->bytes[16]==8);','last_path(path,0);saved=file(path);CHECK(!saved);','GXLS A 不创建。')
swap('menu();apply_ok(6);last_path(path,1);saved=file(path);CHECK(saved&&saved->bytes[16]==6);','menu();apply_ok(6);last_path(path,1);saved=file(path);CHECK(!saved);','GXLS B 不创建。')
swap('DAILY mode=%u Fn2_saved=3 OK_updates_GXLS=1 cold_cursor=8 cold_tweak=3','DAILY mode=%u Fn2_RAM=3 GXLS_writes=0 cold_cursor=4 cold_tweak=0','打印当前契约。')
swap('unsigned i,slot,replica;Gxr2View v;GxtsBinding binding;GxtsState state;','unsigned i,slot,replica;Gxr2View v;GxtsBinding binding;','删除不再写入时用不到的测试变量。')
# With no installation there is no post-load IROM conflict scan. Real loader
# rejection/quarantine tests remain unchanged; only installer-only flags differ.
a=s.index('static void conflict34(');b=s.index('static void daily34(',a)
old=s[a:b];new=old.replace('hidden_hits&&file(', '!hidden_hits&&file(').replace('&&(root.flags&RF_QUARANTINE)', '&&!(root.flags&RF_QUARANTINE)')
assert new!=old;s=s[:a]+new+s[b:]
changes.append(dict(old=old,new=new,reason='安装扫描已关闭，不探测隐藏 IROM，也不因安装冲突设置 quarantine；原有 loader 拒绝/quarantine 检查不变，IROM 较新文件必须保持。',occurrences=1))
swap(' #include "host_r28.inc.c"',' #include "host_r28.inc.c"\n #include "host_gen117.inc.c"','新增三单元只读回归。')
swap('    if(!strcmp(argv[1],"seed115"))','    if(!strcmp(argv[1],"gen117"))gen117_cases(old,old_bytes);\n    else if(!strcmp(argv[1],"seed115"))','新增三单元只读回归入口。')
swap('    CHECK(opens==closes);for(i=0;i<2;i++)CHECK(!fds[i].live);','    CHECK(!native_create_calls&&!native_write_calls&&!native_rename_calls&&!native_delete_calls&&!native_write_opens&&!native_preference_opens);\n    CHECK(opens==closes);for(i=0;i<2;i++)CHECK(!fds[i].live);','每个阶段结束时，全流程六类 native 变更次数及旧偏好读取次数必须为零。')
(TARGET/'host_v34c.c').write_text(s)
(HERE/'local/host-expectation-changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
(HERE/'local/host117.patch').write_text(''.join(difflib.unified_diff((ORIGINAL/'host_v34c.c').read_text().splitlines(True),s.splitlines(True),fromfile='gen116/host_v34c.c',tofile='gen117/host_v34c.c')))
# History preserves its full-settings and unit-swap checks, changes only cursor policy.
h=(ORIGINAL/'host_history34c.c').read_text()
h=h.replace('session()->cursor==remembered-1','session()->cursor==3').replace('session()->cursor==0','session()->cursor==3').replace('session()->cursor==slot-1','session()->cursor==3')
(TARGET/'host_history34c.c').write_text(h)
print('PASS host expectation edits',len(changes))
