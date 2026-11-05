"""Build explicit g158 S fixtures from the audited, unchanged g157 close snapshots.

These are derived fixtures, not g158 GPIO source sessions. Every replay still
starts a new g158 MAIN. New saves are independently checked by native sweeps
and actual SETTINGS op5; no old record is silently accepted by g158.
"""
from pathlib import Path
import json,struct,sys,zlib
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';C.compute_gate('derive-S48-fixtures')
out=C.LOCAL/'persistence-r1-model';out.mkdir(exist_ok=True)
oldroot=C.ROOT/'research/g157/local/fix-r1/final'
sources=json.loads((oldroot/'persistence-fix-r1-model/sources.queue.json').read_text());inputs=[];queue=[]
for source in sources:
    args=source['args'];profile=args[args.index('--version')+1];close=args[args.index('--close-key')+1]
    name=source['label'].split('-'+profile+'-')[1].rsplit('-',1)[0]
    folder=oldroot/'runs'/source['label'];r=json.loads((folder/'result.json').read_text());old=(folder/'final-S.bin').read_bytes()
    prior=(C.LOCAL/'before'/profile/'GXRCE.DAT').read_bytes();raw=C.artifact(profile)['dat'].read_bytes()
    assert r['status']=='OBSERVED' and r['actual_backend']=='native' and r['dat_sha256']==C.sha(prior)
    assert len(old)==4096 and old[0xfd4:0xffc]==bytes.fromhex(r['after_close']['record']) and old[0xff0:0xff8]==prior[20:28]
    new=bytearray(old);new[0xff0:0xff8]=raw[20:28];new[0xff8:0xffc]=zlib.crc32(new[0xfd4:0xff8]).to_bytes(4,'big')
    assert old[:0xff0]==new[:0xff0] and old[-4:]==new[-4:]
    checksum=(sum(struct.unpack('>2046H',new[:4092]))&0xffffffff).to_bytes(4,'big')
    stem=profile+'-'+name+'-'+close;rawpath=out/(stem+'-rebound-raw-S.bin');rawpath.write_bytes(new)
    twin=out/(stem+'-checksum-S.bin');twin.write_bytes(new[:4092]+checksum)
    expected=out/(stem+'-expected552.bin');expected.write_bytes((folder/'final-live-552.bin').read_bytes())
    for target in ('test','release'):
        for mode,path in (('raw',rawpath),('checksum',twin)):
            label='r1-model-replay-'+profile+'-'+name+'-'+close+'-to-'+target+'-'+mode
            args=['--dataset','model','--version',target,'--unit','mount','--backend','native','--dial','AUTO','--label',label,'--action','menu','--settings',str(path)]
            if (mode=='checksum' or bytes(new[-4:])==checksum) and profile==target=='test':args+=['--expected',str(expected)]
            queue.append(dict(label=label,args=args))
            inputs.append(dict(source=source['label'],source_kind='g157 complete GPIO close snapshot; only g158 record binding/record CRC rebased, original whole-S checksum retained',source_DAT_sha256=r['dat_sha256'],source_S_sha256=C.sha(old),source_path=str(folder.relative_to(C.ROOT)),target=target,mode=mode,label=label,input=str(path.relative_to(C.ROOT)),sha256=C.sha(path.read_bytes()),raw_source_sha256=C.sha(bytes(new)),raw_checksum_valid=bytes(new[-4:])==checksum,changed_offsets=[i for i,(x,y) in enumerate(zip(new,path.read_bytes())) if x!=y],rebinding_changed_offsets=[i for i,(x,y) in enumerate(zip(old,new)) if x!=y],record=bytes(new[0xfd4:0xffc]).hex()))
assert len(queue)==48
C.save(out/'inputs.json',inputs);C.save(out/'replays.queue.json',queue)
path=C.HERE/'jobs.json';jobs=json.loads(path.read_text());known={r['id'] for r in jobs}
for row in queue:
    if row['label'] not in known:jobs.append(dict(id=row['label'],script='research/g158/run.py',args=row['args'],needs=[],log=str(C.LOCAL/'logs'/(row['label']+'.log'))))
if 'verify-S48' not in known:jobs.append(dict(id='verify-S48',script='research/g158/replay.py',args=['--dataset','model','--tag','r1','--verify'],needs=[r['label'] for r in queue],log=str(C.LOCAL/'logs/verify-S48.log')))
C.save(path,jobs);print(json.dumps(dict(status='PREPARED',replays=48,sources='g157 actual close snapshots plus explicit g158 binding rebasing; not new g158 source MAIN runs')))
