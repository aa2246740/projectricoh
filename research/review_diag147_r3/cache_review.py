"""Replay native lookup with a second open file and shared FAT-cache state."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import scope
sys.path.insert(1,str(scope.ROOT/'research/user_storage_r2'))
import collect
collect.BODY=scope.ROOT/'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
collect.EXPECTED={collect.OFFICIAL:'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
                  collect.BODY:'d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'}
collect.OUT=HERE/'local/native-listings'
collect.Image().dump(0x200b527c,0x200b6900,'directory-search-full')
collect.Image().dump(0x200b3af8,0x200b4300,'file-init-full')
collect.Image().dump(0x203d3000,0x203d4200,'arithmetic-helpers')
collect.Image().dump(0x200afc80,0x200b0000,'file-state-helpers')
collect.Image().dump(0x200bb5b8,0x200bbc80,'volume-device-dispatch')
for name in ('directory-search-full','file-init-full','arithmetic-helpers','file-state-helpers','volume-device-dispatch'):
    listing=collect.OUT/(name+'.asm.txt')
    listing.write_text(listing.read_text().replace('fixed v3.6 body','reviewed v3.8 body'))
import host_native as native
import replay
program=native.Program()
F,V=replay.FILES,replay.VOLUME

class CPU(replay.CPU):
    def op(self,name,args,pc):
        if name in ('addx','subx'):
            self.visits.add(pc)
            d,s=native.p.reg(args[0]),native.p.reg(args[1])
            x,y,carry=self.r[d],self.r[s],self.psw&1
            if name=='addx':
                value=x+y+carry
                self.condition(value>0xffffffff)
            else:
                value=x-y-carry
                self.condition(x<y+carry)
            self.r[d]=value&0xffffffff
            return
        if name=='neg':
            self.visits.add(pc)
            self.r[native.p.reg(args[0])]=(-self.r[native.p.reg(args[1])])&0xffffffff
            return
        return super().op(name,args,pc)

check=CPU(program);check.visits=replay.Visits()
for name,x,y,carry,value,out_carry in [
    ('addx',0xffffffff,1,0,0,1),('addx',0,0,1,1,0),
    ('subx',0,1,0,0xffffffff,1),('subx',5,3,1,1,0)]:
    check.r[0:2]=[x,y];check.condition(carry)
    check.op(name,('r0','r1'),0)
    assert (check.r[0],check.psw&1)==(value,out_carry)

class MediaRequest(Exception):
    pass

cases=[]
device_io = sys.argv[1:] == ['device-queue']
real_flush = bool(sys.argv[1:]) and sys.argv[1] in ('real-flush','real-flush-pool','real-flush-queue','device-queue')
pending_queue = device_io or sys.argv[1:] == ['real-flush-queue']
ready_pool = pending_queue or sys.argv[1:] == ['real-flush-pool']
for dirty in (False,True):
    c=CPU(program);c.visits=replay.Visits()
    for i in (0,1):
        f=F+708*i
        c.seed(f+4,0,1)
        c.seed(f+6,i,1)
        c.seed(f+7,0xc2 if i==0 else 0x82,1)
        if i==0:
            c.seed(f+300,replay.BUFFER)
            c.seed(f+124,0)
            c.seed(f+156,32768)
            c.seed(f+160,7)
            c.seed(f+164,7)
            c.seed(f+168,1)
            c.seed(f+202,2,2)
            c.seed(f+354,0xffff,2)
        if i==1:
            c.seed(f+4,255,1)
            c.seed(f+6,255,1)
            c.seed(f+7,0,1)
    c.seed(replay.COUNT,1)
    c.seed(V+4,0,1)
    c.seed(V+6,1,1)
    c.seed(V+172,512,2)
    c.seed(V+174,64,1)
    c.seed(V+178,512,2)
    c.seed(V+196,32768,2)
    c.seed(V+200,2,1)
    c.seed(V+160,200)
    c.seed(V+272,100)
    c.seed(V+284,2)
    if device_io:
        c.seed(V+160,32*512)
        c.seed(V+164,(32+2*8192)*512)
        c.seed(V+184,8192,2)
        c.seed(V+224,8192*512)
        c.seed(V+272,32*512)
        c.seed(V+276,8192)
        c.seed(V+192,1040000)
        c.seed(0x204c8940,0x200a32a8)
        c.seed(0x204c8944,0x200a3358)
    if ready_pool:
        c.seed(V+228,32,2)
        c.seed(V+230,0,2)
        c.seed(V+232,32,2)
    c.seed(0x204c9206,0,1)
    c.seed(0x204c9207,0,1)
    cache=0x204c9228+4
    replay.data(c,cache,bytes(1536))
    replay.data(c,cache,(0x0ffffff8).to_bytes(4,'little')+(0x0fffffff).to_bytes(4,'little')*2)
    replay.data(c,cache+28,(0x0fffffff).to_bytes(4,'little'))
    c.seed(F+700,0,1)
    if pending_queue:
        c.seed(F+308,6,2)
        c.seed(F+310,1,2)
        for i in range(7):
            c.seed(F+312+4*i,7+i)
    if dirty:
        # Execute the original FAT32 setter instead of directly seeding dirty=1.
        assert c.call(0x200b0164,(7,8,cache+28)) >= 0
        assert c.read(F+700,1)==1
        assert replay.blob(c,cache+28,4)==b'\x08\0\0\0'
    before_dirty=c.read(F+700,1)
    # Execute the original wrapper's full-buffer boundary and signal. The native
    # flush is a boundary; the real FAT setter above supplies its pending state.
    native.stub(c,0x0500d4e4,'wait47',0)
    native.stub(c,0x0500d4fc,'signal47',0)
    if not real_flush:
        native.stub(c,0x200ab02c,'buffer_flush_boundary',32768)
    native.stub(c,0x200b10fc,'writer_media_io',0)
    if not device_io:
        native.stub(c,0x200b823c,'writer_sector_io',0)
    native.stub(c,0x0500d514,'kernel_error_notification',0)
    native.stub(c,0x0500d638,'kernel_volume_context_a',0)
    native.stub(c,0x0500d63c,'kernel_volume_context_b',0)
    stage=['writer']
    device_calls=[]
    if device_io:
        def device(x,kind):
            row=dict(kind=kind,stage=stage[0],args=list(x.r[4:8]),
                     cache_byte_address=x.read(V+272),
                     original_file_dirty=x.read(F+700,1),
                     reader_file_dirty=x.read(F+708+695,1))
            device_calls.append(row)
            if stage[0]=='lookup':
                raise MediaRequest()
            assert 1 <= x.r[6] <= 3,row
            # The requested FAT sectors are supplied by a local synthetic device.
            return 0
        native.stub(c,0x200a32a8,'device_read',hook=lambda x:device(x,'read'))
        native.stub(c,0x200a3358,'device_write',hook=lambda x:device(x,'write'))
    def copy_bytes(x):
        replay.data(x,x.r[4],replay.blob(x,x.r[5],x.r[6]))
        return x.r[4]
    native.stub(c,0x200627d8,'copy_bytes',hook=copy_bytes)
    entry=replay.CACHE+16
    c.seed(entry,1,2)
    c.seed(entry+2,64,2)
    c.seed(entry+4,replay.BUFFER)
    c.seed(entry+8,32767)
    replay.data(c,replay.SOURCE,b'x')
    written=c.call(0x200a45e8,(0x81,replay.SOURCE,1))
    expected_dirty=1 if pending_queue else (before_dirty if not real_flush or ready_pool else 0)
    assert written==1 and c.read(F+700,1)==expected_dirty, (written,c.read(F+700,1),expected_dirty,c.trace)
    assert any(x['name']=='signal47' for x in c.trace), c.trace
    writer_fat_setter=0x200b0164 in c.visits
    if pending_queue and not dirty:
        assert writer_fat_setter and before_dirty==0 and expected_dirty==1
    writer_trace=list(c.trace)
    c.trace=[]
    stage[0]='lookup'
    # The real g147 fs_open permits one pre-existing open handle and calls lookup
    # with mode 2. Allocation/path/slot selection are explicit boundaries here.
    def allocate(x):
        assert x.read(F+4,1)==0 and x.read(F+708+4,1)==255
        assert x.read(replay.COUNT)==1
        x.seed(F+708+4,0,1)
        x.seed(F+708+6,1,1)
        x.seed(F+708+300,replay.BUFFER+65536)
        x.seed(F+708+354,0xffff,2)
        x.seed(0x204c9207,1,1)
        return 1
    native.stub(c,0x200af654,'allocate_slot',hook=allocate)
    native.stub(c,0x200af8b8,'slot_check',0)
    media=[]
    def sector(x):
        row=dict(args=list(x.r[4:8]),buffer=hex(x.read(x.r[15])),
                 original_file_dirty=x.read(F+700,1),
                 reader_file_dirty=x.read(F+708+695,1),
                 reader_flags=x.read(F+708+7,1))
        media.append(row)
        raise MediaRequest()
    if not device_io:
        native.stub(c,0x200b823c,'sector_io_boundary',hook=sector)
    try:
        c.call(0x200a65f8,(0x204c866c,2))
    except MediaRequest:
        pass
    expected=2 if expected_dirty else 1
    if device_io:
        media=[x for x in device_calls if x['stage']=='lookup']
        assert len(media)==1 and media[0]['kind']==('write' if expected==2 else 'read'),media
        media[0]['reader_flags']=c.read(F+708+7,1)
    else:
        assert len(media)==1 and media[0]['args'][:2]==[2,expected],media
    assert media[0]['reader_file_dirty']==0 and media[0]['reader_flags']==0x82
    cases.append(dict(other_file_dirty=dirty,other_file_dirty_after_writer=expected_dirty,first_request=media[0],
                      request_kind='write' if expected==2 else 'read',
                      initial_fat_setter=dirty,writer_wrapper_released47=True,
                      writer_committed_fat_entries=writer_fat_setter,
                      device_calls=device_calls,
                      writer_trace=writer_trace,lookup_prefix_trace=c.trace,
                      reached_sector_request_before_lookup_return=True))
output='cache-review-device.json' if device_io else ('cache-review-queue.json' if pending_queue else ('cache-review-pool.json' if ready_pool else ('cache-review-real.json' if real_flush else 'cache-review.json')))
scope.save(HERE/output,dict(
    status='OBSERVED_NATIVE_LOOKUP_WRITE_REQUEST' if not real_flush or ready_pool else 'OBSERVED_WRITER_FLUSHES_FAT_BEFORE_UNLOCK',body_sha256=scope.sha(collect.BODY),
    dat_sha256=scope.sha(scope.ROOT/'firmware/package_v38_diag147/SD_ROOT/GXRCE.DAT'),
    actual_buffer_flush=real_flush,actual_device_dispatch=device_io,ready_cluster_pool=ready_pool,pending_cluster_queue=pending_queue,cases=cases,limits=[
        'Synthetic FAT32 file/volume state, two active file slots, no mounted media.',
        'The FAT setter, high-level buffered write wrapper and lookup/search/cache prefix execute original bytes.',
        'Allocation/slot selection, semaphore services, memcpy and writer data I/O are stubs; flush is a stub only in the boundary run.',
        'In device-queue, sector wrappers/cache ownership/address conversion/device dispatch execute original bytes; only the final device callbacks are stubs.',
        'Execution stops at the first lookup sector request or device callback; it does not complete lookup or claim card corruption.',
        'No real camera scheduling or JPEG history was executed.']))
print('CACHE_REVIEW_DONE',[(x['other_file_dirty'],x['request_kind']) for x in cases],flush=True)
