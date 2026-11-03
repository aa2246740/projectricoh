"""FAT32 equal-length flush/release with actual chain finalization instructions."""
from pathlib import Path
import hashlib
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
sys.path.insert(0,str(scope.ROOT/'research/user_storage_r2'))
import collect
collect.BODY=scope.ROOT/'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
collect.EXPECTED={collect.OFFICIAL:'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
                  collect.BODY:'d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'}
collect.OUT=scope.HERE/'native-listings'
collect.Image().dump(0x200afc80,0x200b0000,'file-state-helpers')
label=collect.OUT/'file-state-helpers.asm.txt'
label.write_text(label.read_text().replace('fixed v3.6 body','reviewed v3.8 body'))
import host_native as n
import replay as r
import metadata_replay as m

p=n.Program()
rows=[]
scope.save(scope.HERE/'fat32-premise.json',dict(
    premise='A clean per-handle dirty range remains clean through chain finalization, so only an injected range can cause FAT I/O.',
    observation='Expanded synthetic execution emitted two FAT calls even without that injection. Prior count assertions failed.',
    decision='Record per-stage state and I/O calls. Do not treat this incomplete synthetic context as a normal mounted FAT32 volume.'))
for valid in (False,True):
    for dirty in (False,True):
        c=m.lower(p,8704)
        F,V=m.F,m.V
        c.seed(V+174,64,1)
        c.seed(V+200,2,1)
        c.seed(V+276,3)
        c.seed(V+288,1,2)
        c.seed(V+156,1000)
        c.seed(V+292,0)
        c.seed(V+296,9)
        cluster=0x12345
        c.seed(F+160,cluster)
        c.seed(F+164,cluster)
        r.data(c,F+176+20,(cluster>>16).to_bytes(2,'little'))
        r.data(c,F+176+26,(cluster&0xffff).to_bytes(2,'little'))
        for address in (0x200b0240,0x200b7b10,0x200ba1c8):
            c.stubs.pop(address,None)
        media=[]
        def sector(x):
            args=list(x.r[4:8])
            buffer=x.read(x.r[15])
            row=dict(args=args,buffer=hex(buffer),stage=stage[0],
                     dirty_range=[x.read(F+354,2),x.read(F+356,2)],
                     volume_fields_160_224=[x.read(V+160),x.read(V+224)],
                     pending_chain=[x.read(F+308,2),x.read(F+310,2)])
            if args[0]==5 and args[1]==1:
                page=bytearray(512)
                if valid:
                    page[:4],page[484:488],page[510:]=b'RRaA',b'rrAa',b'\x55\xaa'
                r.data(x,buffer,page)
            if args[0]==5 and args[1]==2:
                row['fsinfo_488_496']=r.blob(x,buffer+488,8).hex()
                row['page_sha256']=hashlib.sha256(r.blob(x,buffer,512)).hexdigest()
            media.append(row)
            return 0
        n.stub(c,0x200b823c,'sector_io_boundary',hook=sector)
        before=m.fields(c)
        stage=['flush']
        written=c.call(0x200ab02c,(0x81,8704,8704))
        # Inject the optional dirty range at the close boundary. This is a
        # conditional-state experiment, not a mounted-volume state.
        if dirty:
            c.seed(F+354,0,2)
            c.seed(F+356,0,2)
        stage[0]='close'
        result=c.call(0x200a6750,(0x81,))
        final=m.fields(c)
        fsinfo_writes=[x for x in media if x['args'][0:2]==[5,2]]
        fat_calls=[x for x in media if x['args'][0]==2 and x['args'][3] in (100,200)]
        assert written==8704 and result==0
        assert final['length']==8704 and final['cluster_high']==1 and final['cluster_low']==0x2345
        assert len(fsinfo_writes)==int(valid)
        rows.append(dict(valid_fsinfo_signature=valid,injected_fat_dirty_range_at_close=dirty,
                         cluster_bytes=32768,first_cluster=hex(cluster),before=before,after_close=final,
                         write_return=written,close_return=result,media_calls=media,
                         fsinfo_writes=len(fsinfo_writes),fat_writes=len(fat_calls),
                         real_chain_transition=0x200b0240 in c.visits,
                         real_chain_close=0x200b7b10 in c.visits,
                         fat_setter_executed=0x200b0164 in c.visits,
                         allocation_search_executed=0x200b79c8 in c.visits,trace=c.trace))
scope.save(scope.HERE/'fat32-paths.json',dict(status='OBSERVED_SYNTHETIC_FAT32_PATHS',cases=rows,
           body_sha256=scope.sha(collect.BODY),
           boundary='Synthetic native file/volume context. Unexpected FAT I/O is retained, not classified as a product defect or normal-volume proof. Media dispatch and sector device are stubs; no FAT32 mount or real card.'))
print('FAT32_PATHS_DONE',len(rows),flush=True)
