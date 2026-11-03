"""C/Python replay of original buffered-write and close wrappers.

Reproduces the decisive wrapper argument observed in native_log.py. The
low-level media operation and lock returns are declared fixture boundaries;
this is not a second complete FAT implementation or a physical-card test.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
import native_metadata as nm
import native_log as nl


def one(case,start,low_error=False,direct=False):
    im=nm.Image(c.ROOT/'artifacts/firmware/gxr-1.51/ilaunch3')
    cpu=nm.pb.PythonBackend();im.load(cpu)
    cpu.map(0x21000000,b'\xe5'*0x20000)
    nm.preload(cpu,im,[(0x200a437c,0x200a449c),(0x200a45e8,0x200a46f0),(0x200a48c8,0x200a4910)])
    fd=0x81;cache=0x204c86ec+16;buffer=0x21010000;src=0x21018000
    cpu.write(0x204c8668,struct.pack('>I',1))
    cpu.write(cache,struct.pack('>HHIII',0,32,buffer,start,start))
    a,b=nl.line(1,1),nl.line(2,0x41)
    cpu.write(buffer,a)
    file=bytearray(a if start else b'')
    low_position=start;commits=[]
    def ret(cpu,result):
        cpu.set_reg('r0',result&0xffffffff);cpu.set_reg('pc',cpu.get_reg('r14'));return False
    for address in (0x0500d4e4,0x0500d4fc,0x200a6750):
        cpu.add_breakpoint(address,lambda cpu:ret(cpu,0))
    def commit(cpu):
        nonlocal low_position
        n=cpu.get_reg('r6');arg5=cpu.get_reg('r5')
        data=cpu.read(buffer+low_position,n)
        commits.append(dict(low_position=low_position,request_bytes=n,argument_r5=arg5,
                            end_position=low_position+n,data_sha256=hashlib.sha256(data).hexdigest()))
        if low_error:return ret(cpu,-1)
        file[low_position:low_position+n]=data;low_position+=n
        return ret(cpu,n)
    cpu.add_breakpoint(0x200ab02c,commit)
    def direct_commit(cpu):
        nonlocal low_position
        n=cpu.get_reg('r6');data=cpu.read(cpu.get_reg('r5'),n)
        commits.append(dict(low_position=low_position,request_bytes=n,argument_r5=cpu.get_reg('r5'),
                            end_position=low_position+n,data_sha256=hashlib.sha256(data).hexdigest()))
        file[low_position:low_position+n]=data;low_position+=n
        return ret(cpu,n)
    cpu.add_breakpoint(0x200ae360,direct_commit)
    payload=b if start else a+b
    cpu.write(src,payload)
    cpu.set_reg('r15',0x21008000)
    for i,value in enumerate((fd,src,len(payload)),4):cpu.set_reg('r'+str(i),value)
    write=cpu.call(0x200a48c8 if direct else 0x200a45e8,[],0x00dff000,50000)
    n=cpu.get_reg('r0')
    before_close_high_position=int.from_bytes(cpu.read(cache+8,4),'big')
    assert write.reason=='return' and n==len(payload)
    cpu.set_reg('r4',fd)
    close=cpu.call(0x200a437c,[],0x00dff000,50000)
    result=cpu.get_reg('r0');result=result if result<2**31 else result-2**32
    count=int.from_bytes(cpu.read(0x204c8668,4),'big')
    row=dict(case=case,write_stop=asdict(write),close_stop=asdict(close),write_result=n,close_result=result,
             high_position_before_close=before_close_high_position,
             execution_stats=getattr(cpu,'native_stats',{}),backend_class=type(cpu).__qualname__,
             commits=commits,post_close_high_handle_count=count,
             model_file_length=len(file),model_file_equals_two_lines=bytes(file)==a+b,
             media_boundary='low commit consumes the requested span at the declared file offset; locks/low close return success')
    assert close.reason=='return'
    if os.environ['GXR_HARNESS_BACKEND']=='c':assert row['execution_stats'].get('instructions',0)>0
    if low_error:assert result==-1 and count==1
    elif direct:assert result==0 and commits[0]['request_bytes']==75 and bytes(file)==a+b and before_close_high_position==75
    elif start:assert result==0 and commits[0]['request_bytes']==150 and commits[0]['low_position']==75 and len(file)==225
    else:assert result==0 and bytes(file)==a+b and count==0
    return row


def main():
    rows=[one('append-after-75-byte-seek',75),one('rewrite-from-zero',0),one('uncertain-close-stops-own-io',0,True),
          one('direct-wrapper-with-successful-low-write-fixture',75,direct=True)]
    side=os.environ['GXR_HARNESS_BACKEND']
    c.dump('log_wrapper_'+side+'.json',dict(status='PASS',backend=side,rows=rows,
          conclusion='The original close wrapper submits 150 buffered bytes after the low-level offset has already advanced to 75'))
    c.finish('log-wrapper-'+side)
    print('PASS',side,len(rows))


if __name__=='__main__':main()
