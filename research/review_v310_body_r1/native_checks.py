#!/usr/bin/python3
"""Independent C/Python instruction checks for SD, T and shutter boundaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle
import struct
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1')
BODY=ROOT/'research/v310_body'
sys.path.insert(0,str(HERE))
from audit import snapshot,memory


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',choices=('c','python'),required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    target=HERE/'evidence'/('native-checks-'+a.backend+'.json');assert not target.exists()
    os.environ['GXR_HARNESS_BACKEND']=a.backend
    os.environ['TMPDIR']=str(TEMP)
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    PB.CACHE=TEMP/'decode'/a.backend
    def machine(state):
        b=PB.PythonBackend()
        for at,data,writable in state['regions']:b.map(at,data,writable)
        b.set_reg('psw',state['registers']['psw'])
        regs=state['registers']
        for name in ('spi','spu','bpc','bbpc','evb'):
            if name in regs:b.set_reg(name,regs[name])
        for i in range(16):b.set_reg('r'+str(i),regs['r'+str(i)])
        if 'acch' in regs:b.set_reg('acc',(regs['acch']<<32)|regs['accl'])
        return b
    result=dict(backend=a.backend,nice=os.getpriority(os.PRIO_PROCESS,0),
                runner_sha256=sha(Path(__file__).read_bytes()),SD=[],T_gate=[],H52=[],identity=[],qualification=[],status='ERROR')
    try:
        path=BODY/'fix/r2/local/recovery-sd-short-prefix-file-service-start.pkl.z'
        state=snapshot(path)['cpu']
        result['SD_source_sha256']=sha(path.read_bytes())
        sys.path.insert(0,str(ROOT/'tools/gxr_emulator_standby'))
        import sdcard
        from types import SimpleNamespace
        for sectors in (65536,131072,262144):
            host=sdcard.SdHost();host.medium=SimpleNamespace(sectors=sectors)
            wire=host.csd()
            for shifted in (False,True):
                b=machine(state)
                value=wire>>8 if shifted else wire
                words=[(value>>(16*i))&0xffff for i in range(8)]
                def read(at,n):
                    assert n==2 and (at-0xff70601a)%4==0
                    return words[(at-0xff70601a)//4].to_bytes(2,'big')
                b.add_mmio(0xff706000,0xff706400,read,None)
                b.set_reg('r4',0x204c5bf4);b.set_reg('r5',5)
                collect=b.call(0x2005a06c,[],0x7ffffff0,2000)
                assert collect.reason=='return'
                b.set_reg('r4',0x204c5bf4);b.set_reg('r5',1)
                formula=b.call(0x200562a8,[],0x7ffffff0,2000)
                assert formula.reason=='return'
                actual=int.from_bytes(b.read(0x204c5bf8,4),'big')
                assert (actual==sectors) if shifted else (actual!=sectors)
                result['SD'].append(dict(sectors=sectors,response_bits_127_to_8=shifted,
                    official_capacity=actual,collector_steps=collect.steps,formula_steps=formula.steps,
                    response_sha256=sha(wire.to_bytes(16,'big'))))
        identity_cases=[
            ('v310-release','v310','firmware/package_v310_g155b/GXRCE.DAT',0),
            ('v310-test','v310','firmware/package_v310_g155b_test/GXRCE.DAT',0),
            ('v39-release','v39','firmware/package_v310_g155b/GXRCE.DAT',8),
            ('v39-test','v39','firmware/package_v310_g155b_test/GXRCE.DAT',8),
            ('v310-g154','v310','firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT',8),
            ('v310-g153','v310','firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT',8),
            ('v310-diag','v310','firmware/package_v39_diagv4p/GXRCE.DAT',8)]
        for name,version,relative,expected in identity_cases:
            body_path=ROOT/('firmware/image_v310/local/ilaunch3' if version=='v310' else 'firmware/package_v39_g154_test/local/SD_ROOT/ilaunch3')
            raw_body=body_path.read_bytes();dat=(ROOT/relative).read_bytes();b=PB.PythonBackend()
            for i in range(16):
                pos,at,n,_,_=struct.unpack_from('>5I',raw_body,32+20*i)
                if n:b.map(at,raw_body[512+pos:512+pos+n],True)
            b.map(0x27000000,dat[:256],False)
            b.map(0x27f00000,bytes(65536),True)
            b.set_reg('psw',0);b.set_reg('r15',0x27f0ff00)
            entry=0x20052e18 if version=='v310' else 0x200541f8
            arguments=[0x27000000,len(dat)] if version=='v310' else [0x27000000,len(dat),0x20054684]
            stop=b.call(entry,arguments,0x7ffffff0,200000)
            assert stop.reason=='return' and b.get_reg('r0')==expected,(name,stop,b.get_reg('r0'))
            result['identity'].append(dict(case=name,header_result=expected,steps=stop.steps,
                DAT_sha256=sha(dat),body_sha256=sha(raw_body),DAT_code_mapped=False,
                layer='Actual resident header function; loader control flow reviewed separately'))
        qual_source=BODY/'fix/local/valid-mount-look-r5-gate-input.z'
        qual=pickle.loads(zlib.decompress(qual_source.read_bytes()))
        variants=[('unchanged',None,None,1),('MY1',0x205d9aa3,b'\x01',0),
                  ('MY2',0x205d9aa3,b'\x02',0),('MY3',0x205d9aa3,b'\x03',0),
                  ('pending',0x205da00b,b'\x01',0),('activity8',0x205d9bf8,(8).to_bytes(4,'big'),0),
                  ('activity1',0x205d9bf8,(1).to_bytes(4,'big'),0),
                  ('state32',0x205d9c00,(32).to_bytes(4,'big'),0),
                  ('guard',0x200547ec,(14).to_bytes(4,'big'),0)]
        for name,address,data,expected in variants:
            b=machine(qual)
            if address is not None:b.write(address,data)
            S=int.from_bytes(b.read(0x200c0dac,4),'big')
            before=b.read(S,4096);word=b.read(0x200547ec,4)
            stop=b.call(qual['expected_function'],[],0x7ffffff0,200000)
            assert stop.reason=='return' and b.get_reg('r0')==expected,(name,stop,b.get_reg('r0'))
            assert b.read(S,4096)==before and b.read(0x200547ec,4)==word
            result['qualification'].append(dict(case=name,result=expected,steps=stop.steps,
                S_unchanged=True,fixed_word_unchanged=True,source_sha256=sha(qual_source.read_bytes()),
                layer='Host variants of an actual cold qualification input; physical MY cold start not claimed'))
        record_path=BODY/'fix/r3/local/recovery-adjc-entry-official-20261103-UEE00-entry.json'
        record=json.loads(record_path.read_text())
        raw=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
        def T_machine():
            b=PB.PythonBackend();ranges=[]
            for i in range(16):
                offset,at,n,_,_=struct.unpack_from('>5I',raw,32+20*i)
                if n:b.map(at,raw[offset+512:offset+512+n],True);ranges.append((at,at+n))
            for item in record['memory']:
                at=item['address'];data=bytes.fromhex(item['data'])
                if any(lo<=at and at+len(data)<=hi for lo,hi in ranges):b.write(at,data)
                else:b.map(at,data,True)
            b.set_reg('psw',record['psw'])
            for name,value in record['registers'].items():b.set_reg(name,value)
            return b
        for first in (0xff,0xbb,0xaa,0x55):
            b=T_machine();at=record['parameter_pointer']
            before=b.read(at,16384)
            if first!=0xff:b.write(at,bytes([first]))
            declared=b.read(at,16384)
            if first in (0xaa,0x55):b.add_breakpoint(0x20077880,lambda cpu:True)
            stop=b.call(0x2007785c,[],record['registers']['r14'],20000)
            accepted=first in (0xaa,0x55)
            assert stop.reason==('breakpoint' if accepted else 'return')
            if not accepted:assert b.get_reg('r0')==0xffffffff
            assert b.read(at,16384)==declared
            result['T_gate'].append(dict(first_byte=first,accepted_for_commit=accepted,
                stop=stop.reason,steps=stop.steps,T_unchanged=True,
                input_role='Actual empty-entry replay; first-byte variants are separate host fixtures'))
        result['T_source_sha256']=sha(record_path.read_bytes())
        cases=[('fault-half','h52-guard-cold-key-2.pkl.z',True),
               ('fault-full','h52-guard-cold-key-3.pkl.z',True),
               ('success-full','h52-success-time-key-2.pkl.z',False),
               ('success-half','h52-success-time-key-3.pkl.z',False),
               ('reset-half','h52-reset-valid-dat-r1-key-2.pkl.z',False)]
        for name,filename,blocked in cases:
            source=BODY/'fix/r2/local'/filename
            state=snapshot(source)['cpu'];b=machine(state)
            regs=state['registers'];word=int.from_bytes(b.read(0x200547ec,4),'big')
            msg=regs['r4'];key=int.from_bytes(b.read(msg+12,4),'big')
            S=int.from_bytes(b.read(0x200c0dac,4),'big');before=b.read(S,4096)
            if not blocked:b.add_breakpoint(0x202afe9c,lambda cpu:True)
            stop=b.call(regs['pc'],[],regs['r14'],20000)
            assert regs['pc']==0x202afe98 and b.read(S,4096)==before
            assert stop.reason==('return' if blocked else 'breakpoint')
            assert (b.get_reg('r0')==0) if blocked else (b.get_reg('pc')==0x202afe9c)
            result['H52'].append(dict(case=name,source_sha256=sha(source.read_bytes()),
                original_cold_step=state['steps'],raw=key,word=word,blocked=blocked,
                stop=stop.reason,steps=stop.steps,S_unchanged=True))
        result['status']='PASS'
    except BaseException as exc:
        result['error']=dict(type=type(exc).__name__,message=str(exc))
        raise
    finally:
        target.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(status=result['status'],backend=a.backend,SD=len(result['SD']),identity=len(result['identity']),qualification=len(result['qualification']),T_gate=len(result['T_gate']),H52=len(result['H52']))),flush=True)


if __name__=='__main__':main()
