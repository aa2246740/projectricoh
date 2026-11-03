"""在最终 DAT 的真实 M32R 指令上注入文件边界故障并记录结果。"""
from pathlib import Path
import hashlib
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
acc = scope.load(scope.ROOT / 'research/unit28_stock/accept_diag145.py', 'review145_probe_base')
OUT = scope.HERE / 'probes'
OUT.mkdir(exist_ok=True)
runtime = scope.SCRATCH / sys.argv[1]
runtime.mkdir(parents=True, exist_ok=True)
acc.HERE = acc.base.HERE = runtime
acc.DAT = acc.base.DAT = scope.ROOT / 'firmware/package_v38_diag145/SD_ROOT/GXRCE.DAT'
acc.FIELDS = tuple(dict.fromkeys((*acc.FIELDS, 'trace_file', 'opens', 'initialized')))
off = acc.offsets()
TRACE = acc.TRACE
all_results = []

def boot(label, content=None, ready=1):
    files = {'/ATA1/GXRCE.DAT': acc.DAT.read_bytes()}
    if content is not None:
        files[TRACE] = bytes(content)
    m, h, p, w, syms, log = acc.boot('28mm', ready, files)
    settings = h.u(0x200c0dac)
    before = scope.sha(acc.DAT)
    settings0 = hashlib.sha256(h.b.read(settings,4096)).hexdigest()
    settings_writes = []
    h.b.add_write_trace(settings, settings+4096, lambda e: settings_writes.append(
        dict(pc=hex(e.pc), offset=e.address-settings, bytes=e.data.hex())))
    def entered(b):
        block = h.u(acc.R+56)
        if block:
            p.image_base = h.u(block+312)
        return False
    h.b.add_breakpoint(h.symbols['rv_invoke'], entered)
    def nb():
        return p.image_base + p.elf.symbols['n']
    def field(name, size=1):
        return h.u(nb()+off[name],size) if p.image_base else None
    def opening():
        h.parent()
        result = m.fr.native(h,0x20287080,(),steps=40000000)
        assert result['ok'],result
        return dict(state=h.u(acc.R+5,1), rows=h.u(acc.ROWS,1),
                    trace_error=field('trace_error'), trace_verify=field('trace_verify'),
                    trace_flushes=field('trace_flushes'), trace_slot=field('trace_slot'),
                    opens=field('opens',4), page=[h.b.read(nb()+off['rows']+9*i,9).split(b'\0')[0].decode('ascii')
                                               for i in range(8)] if p.image_base else [])
    def close():
        assert m.fr.press(h,0x23,steps=40000000)['ok']
    row = dict(case=label, input_sha256=hashlib.sha256(bytes(content)).hexdigest() if content is not None else None)
    return m,h,p,log,nb,field,opening,close,settings,settings0,settings_writes,row

def finish(state):
    m,h,p,log,nb,field,opening,close,s,s0,sw,row = state
    content = p.files.paths.get(TRACE)
    row.update(file_log=log, s_writes=sw,
        s_unchanged=hashlib.sha256(h.b.read(s,4096)).hexdigest()==s0,
        rpc_w=sum(x['cmd']==22 for x in p.rpc.log),
        forbidden=[x for x in p.native_log if x.get('op') in ('create','rename','delete')])
    assert row['s_unchanged'] and not sw and row['rpc_w']==0 and not row['forbidden'],row
    if content is not None:
        file=OUT/(row['case']+'.bin')
        file.write_bytes(bytes(content))
        row.update(file_bytes=len(content), output_sha256=scope.sha(file))
        if len(content)==4096:
            row['slots']=[acc.decode_slot(content,i) for i in range(4)]
    scope.save(OUT/(row['case']+'.json'),row)
    all_results.append(row)
    print('故障复现结束',row['case'],row.get('file_bytes'),flush=True)

def basic(label, content, ready=1):
    state=boot(label,content,ready)
    state[-1]['menu']=[state[6]()]
    if ready: state[7]()
    finish(state)
    assert not [e for e in state[3] if e['op']=='write']

def failure(label, mode):
    state=boot(label,acc.header())
    m,h,p,log,nb,field,opening,close,s,s0,sw,row=state
    count={'writes':0,'opens':0,'partial':False}
    if mode=='readonly-open':
        def opened(b):
            path=m.pe.cstr(h,b.get_reg('r4'));flags=b.get_reg('r5')
            fd=-1 if path==TRACE and flags==2 else p.files.open(path)
            if fd>=0:p.files.flags[fd]=flags
            log.append(dict(op='open',path=path,flags=flags,fd=fd))
            return fd
        h.b.breakpoints.pop(0x200a40b4,None);p._native(0x200a40b4,'故障打开',opened)
    else:
        def write(b):
            fd,buf,n=(b.get_reg('r%d'%i) for i in (4,5,6))
            count['writes']+=1
            live=p.files.live.get(fd)
            log.append(dict(op='write',path=live[0] if live else None,fd=fd,n=n,
                            flags=p.files.flags.get(fd),attempt=count['writes'],fault=mode))
            if not live:return -1
            path,pos=live
            if mode=='all-write-fail' or mode=='menu-write-fail' and count['writes']>=2:return -1
            if mode in ('partial-menu','removed') and count['writes']>=2:
                if count['partial']:return -1
                count['partial']=True
                n=min(n,1232)
                if mode=='removed':p.files.present=False
            content=p.files.paths[path]
            content[pos:pos+n]=h.b.read(buf,n);live[1]+=n
            return n
        h.b.breakpoints.pop(0x200a45e8,None);p._native(0x200a45e8,'故障写入',write)
    row['menu']=[]
    for _ in range(3 if mode=='menu-write-fail' else 1):
        row['menu'].append(opening());close()
    finish(state)
    if mode in ('readonly-open','all-write-fail'):
        assert not row['slots'][1]['written']
    if mode=='menu-write-fail':
        assert row['slots'][1]['menus']==0 and row['slots'][1]['stages']==1
        assert row['menu'][-1]['opens']==3
    if mode=='partial-menu':
        assert row['slots'][1]['menus']==1
        assert row['slots'][1]['menu'][0]['outcome']=='K'
        assert row['menu'][-1]['trace_verify']==2

def cap():
    state=boot('cap',acc.header())
    m,h,p,log,nb,field,opening,close,s,s0,sw,row=state
    row['menu']=[opening()];close()
    # 真实菜单入口保留前八条与最后一条；超过 16 次 flush 后卡上停止更新。
    for _ in range(17):
        row['menu'].append(opening());close()
    finish(state)
    assert row['menu'][-1]['trace_flushes']==16
    assert row['slots'][1]['menus']==15 and row['slots'][1]['flushes']==16
    assert len([e for e in log if e['op']=='write'])==16
    assert row['slots'][1]['last']['entry']==15

def stale():
    original=(OUT/'menu-write-fail.bin').read_bytes()
    state=boot('stale-notready',original,0)
    state[-1]['menu']=[state[6]()]
    finish(state)
    assert state[-1]['output_sha256']==hashlib.sha256(original).hexdigest()

def main():
    if sys.argv[1]=='faults':
        basic('missing',None)
        basic('short4095',acc.header()[:-1])
        basic('long4097',acc.header()+b'\0')
        bad=acc.header();bad[4]=ord('0');basic('badheader',bad)
        failure('readonly-open','readonly-open')
        failure('all-write-fail','all-write-fail')
        failure('menu-write-fail','menu-write-fail')
        failure('partial-menu','partial-menu')
        failure('removed','removed')
        stale()
    elif sys.argv[1]=='cap':
        cap()
    else:
        raise SystemExit('未知复现组')
    scope.save(OUT/('summary-'+sys.argv[1]+'.json'),all_results)
    print('独立复现组结束',sys.argv[1])

if __name__=='__main__':
    main()
