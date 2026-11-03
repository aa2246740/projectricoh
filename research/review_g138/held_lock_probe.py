import sys,json,time
sys.path.insert(0,__import__('os').path.dirname(__file__))
import g138_host as H, persist_check as P
H.setup()
cam=P.boot('50mm',bytes(40)); cam.put_s(0x6dd,b'\x0a'); P.opened(cam); cam.set_lock(0)
S0=cam.s_bytes(0,4096); w0=cam.writes(); n0=len(cam.p.rpc.log); t=time.time()
r=cam.m.fr.move_key(cam.h,0x20,steps=400000000)
st=cam.state(); S1=cam.s_bytes(0,4096)
log=cam.p.rpc.log[n0:]
print(json.dumps(dict(ok=r.get('ok'),reason=r.get('reason'),seconds=round(time.time()-t),W=cam.writes()-w0,rpc=len(log),
  S_changed=[hex(i) for i in range(4096) if S0[i]!=S1[i]],lock=cam.lock(),slot=st['slot'],failed=st['failed'],labels=st['labels'],rows=st['rows'])))
