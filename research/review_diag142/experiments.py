"""Focused native-instruction checks of binding and the reported heap criterion."""
from pathlib import Path
import json
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
scope.freeze_check()
source = scope.ROOT / 'research/unit28_stock'
accept = scope.load(source / 'accept_diag38.py', 'review142_experiments_accept')
accept.HERE = scope.HERE / 'experiments'
accept.HERE.mkdir(parents=True,exist_ok=True)
accept.DAT = scope.ROOT / 'firmware/package_v38_diag/SD_ROOT/GXRCE.DAT'
off = accept.probe_offsets()
diag_dat = accept.DAT
diag_engine = accept.ENGINE


def rows(h,p):
    at=p.image_base+p.elf.symbols['n']+off['rows']
    return [h.b.read(at+9*i,9).split(bytes(1),1)[0].decode('ascii') for i in range(8)]


def require(result):
    assert result.get('ok'), result
    return result


def update_image_base(h,p):
    def entered(b):
        block=h.u(accept.R+56)
        if block:p.image_base=h.u(block+312)
        return False
    h.b.add_breakpoint(h.symbols['rv_invoke'],entered)


def heap(h):
    base,end=h.u(0x200d3488),h.u(0x200d348c)
    at=base+12;blocks=[]
    for _ in range(1024):
        if at==end+12:return blocks
        span=h.u(at+8);state=h.u(at+4,1)
        assert span>=12 and span%4==0 and at+span<=end+12
        blocks.append({'header':hex(at),'span':span,'used':state})
        at+=span
    raise AssertionError('heap traversal did not terminate')


result={}
m,h,p,w,syms=accept.boot('28mm',1)
update_image_base(h,p)
dat=accept.DAT.read_bytes()
trust=syms['rv_trust']
assert h.b.read(trust,80) == dat[48:112]+dat[212:228]
tests=[]
for label,index,expected in (('valid',None,0),('body-id',48,7),('resident-build-id',80,8),('resident-abi-id',212,8)):
    header=bytearray(dat[:256])
    if index is not None:header[index]^=1
    header[20:24]=bytes(4);header[20:24]=zlib.crc32(header).to_bytes(4,'big')
    pointer=0x206e1000
    h.b.write(pointer,header)
    run=require(p.call(syms['rv_header'],(pointer,len(dat),trust),steps=1000000))
    assert run['r0']==expected,(label,run)
    tests.append({'case':label,'result':run['r0'],'expected':expected})
result['binding_header_instructions']=tests
allocated=require(m.fr.native(h,0x2005bf5c,(0x20000,),steps=1000000))['r0']
assert allocated
result['diag_heap_before_load']=heap(h)
h.parent();require(m.fr.native(h,0x20287080,steps=40000000))
shown=rows(h,p)
assert shown[0]=='S0001 R9' and int(shown[5][-3:])<106 and h.u(accept.R+5,1)==3,shown
result['diag_page']=shown
result['diag_heap_after_load']=heap(h)
result['diag_main_request']=h.u(accept.R+104)
result['diag_main_span']=h.u(accept.R+108)
assert result['diag_main_span']==45520
result['diag_file_writes']=m.no_writes(p)
result['diag_rpc_commands']=sorted({e['cmd'] for e in p.rpc.log})
assert result['diag_rpc_commands']==[21,23] and not p.rpc.overlay
print('DIAG_HEAP_COUNTEREXAMPLE',shown,flush=True)

accept.DAT=scope.ROOT/'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT'
accept.ENGINE=scope.ROOT/'firmware/engine_v54_g137/candidate/local/full-r13/engine.elf'
accept.HERE=scope.HERE/'experiments-g137'
accept.HERE.mkdir(parents=True,exist_ok=True)
m,h,p,w,syms=accept.boot('28mm',1)
update_image_base(h,p)
allocated=require(m.fr.native(h,0x2005bf5c,(0x20000,),steps=1000000))['r0']
assert allocated
result['g137_heap_before_load']=heap(h)
assert result['g137_heap_before_load']==result['diag_heap_before_load']
h.parent();require(m.fr.native(h,0x20287080,steps=40000000))
root=m.fr.root_fields(h)
assert root['state']==3 and h.u(0x2022f5ac,1)==8,(root,h.u(0x2022f5ac,1))
assert root['block_bytes']==108124 and h.u(accept.R+108)==108136
result['g137_root']=root
result['g137_main_span']=h.u(accept.R+108)
result['g137_rows']=h.u(0x2022f5ac,1)
result['g137_rpc_w']=sum(e['cmd']==22 for e in p.rpc.log)
result['g137_file_writes']=m.no_writes(p)
result['counterexample_observed']=True
result['dat_sha256']=scope.sha(diag_dat)
result['g137_sha256']=scope.sha(accept.DAT)
result['frozen_inputs_unchanged']=scope.freeze_check()
scope.save(scope.HERE/'experiments.json',result)
print('EXPERIMENTS_PASS: diagnostic below 106 KiB, identical pre-load heap permits gen137',flush=True)
