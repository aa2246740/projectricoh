"""Execute both actual gate bodies against a literal field contract."""
from pathlib import Path
import ctypes as T,json,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';C.compute_gate('host-gate-domain')
out=C.LOCAL/'gate';out.mkdir(exist_ok=True)
def gate(path,suffix):
    s=path.read_text();s=s[s.index('static uint32_t boot_fail_bits'):s.index('static int boot_native_ready')]
    return s.replace('boot_fail_bits','gate_'+suffix)
old=C.LOCAL/'before/source/boot_adapter.inc.c';new=C.PRODUCT/'boot_adapter.inc.c'
source='''#include <stdint.h>
static unsigned m,u,n,y,p,a,v,s;
static uint32_t word(uint32_t at){if(at==0x200c0dac)return v?0x20100000:0;if(at==0x200c0db0)return v?4096:0;if(at==0x201002fc)return n;if(at==0x205d9bf8)return a;if(at==0x205d9c00)return s;return 0;}
static uint8_t byte(uint32_t at){if(at==0x205d9a7f)return m;if(at==0x205d9a9f)return u;if(at==0x205d9aa3)return y;if(at==0x205da00b)return p;return 0;}
#define RV_WORD(at) word(at)
#define RV_BYTE(at) byte(at)
'''
diag=(C.PRODUCT/'diagnostic.h').read_text();constants=diag[diag.index('enum { BF_DISPATCH'):diag.index('};',diag.index('enum { BF_DISPATCH'))+2]
source+=constants+'\n'+gate(old,'old')+gate(new,'new')+'''
unsigned test_gate(unsigned which,unsigned M,unsigned U,unsigned N,unsigned Y,unsigned P,unsigned A,unsigned V,unsigned S){m=M;u=U;n=N;y=Y;p=P;a=A;v=V;s=S;return which?gate_new():gate_old();}
'''
path=out/'gate.c';path.write_text(source);libpath=out/'gate.dylib'
r=subprocess.run(['/usr/bin/clang','-std=c11','-O2','-dynamiclib',str(path),'-o',str(libpath)],capture_output=True,text=True);(out/'build.log').write_text(r.stdout+r.stderr);assert not r.returncode,r.stderr
lib=T.CDLL(str(libpath));f=lib.test_gate;f.argtypes=[T.c_uint]*9;f.restype=T.c_uint
pairs={(4,0,0x8010),(4,1,0x8020),(4,2,0x8008),(4,3,0x8800)};added=[];cases=0
for mode in range(256):
    for sub in range(256):
        for N in (0x8001,0x8010,0x8020,0x8008,0x8800,0x8040,0,0x10000,0xffffffff):
            previous=f(0,mode,sub,N,0,0,0,1,5);actual=f(1,mode,sub,N,0,0,0,1,5)
            allowed=mode==0 and N==0x8001 or (mode,sub,N) in pairs
            assert actual==(0 if allowed else 4),(mode,sub,N,actual)
            assert previous==(0 if mode==0 and N==0x8001 else 4)
            if not actual and previous:added.append([mode,sub,N])
            cases+=1
assert {tuple(x) for x in added}==pairs
edges=[]
for mode,sub,N in sorted(pairs):
    for bit in range(32):
        actual=f(1,mode,sub,N^(1<<bit),0,0,0,1,5);assert actual==4;cases+=1
    for name,args,expected in [('MY',(1,0,0,1,5),8),('pending',(0,1,0,1,5),16),('activity',(0,0,6,1,5),2),('settings',(0,0,0,0,5),36),('state',(0,0,0,1,32),64)]:
        actual=f(1,mode,sub,N,*args);assert actual==expected,(name,actual,expected);cases+=1;edges.append(dict(mode=mode,submode=sub,N=N,case=name,failed=actual))
C.save(out/'result.json',dict(status='PASS',cases=cases,added_only=added,edges=edges,old_gate_sha256=C.sha(old.read_bytes()),new_gate_sha256=C.sha(new.read_bytes()),driver_sha256=C.sha(Path(__file__).read_bytes()),scope='Actual old/new C gate bodies; every uint8 mode/submode against nine N domains, all N-bit mutations at each admitted PASM pair, unchanged independent gates. SCENE physical mapping not supplied; all non-admitted domains reject.'))
print(json.dumps(dict(status='PASS',cases=cases,added_only=added)))
