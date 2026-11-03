"""Replay current-body FAT32 helpers; all media operations are recorded stubs."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
sys.path.insert(0, str(scope.ROOT / 'research/user_storage_r2'))
import collect

collect.BODY = scope.ROOT / 'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
collect.EXPECTED = {
    collect.OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
    collect.BODY: 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'}
collect.OUT = scope.HERE / 'native-listings'
collect.OUT.mkdir(exist_ok=True)
image = collect.Image()
for name, (lo, hi) in collect.WINDOWS.items():
    if name in ('photo-create', 'photo-path', 'dcf-path', 'dcf-path2', 'photo-name-builder'):
        continue
    image.dump(lo, hi, name)
    label=collect.OUT/(name+'.asm.txt')
    label.write_text(label.read_text().replace('fixed v3.6 body','reviewed v3.8 body'))

import host_native as n
import replay as r
import metadata_replay as m

program = n.Program()
rows = []
for sectors in (32, 64):
    for fd in (0x81, 0x82):
        c, entry = r.setup(program, sectors=sectors, native_fd=fd)
        index = fd - 0x81
        assert c.call(0x200ba2c8, (index,)) >= 0
        buffer = c.read(r.FILES + 708 * index + 300)
        assert buffer == r.BUFFER + (index << 16)
        assert c.call(0x200ab4f0, (fd, entry+4, entry+2)) == 0
        assert c.read(entry+4) == buffer and c.read(entry+2, 2) == sectors
        rows.append(dict(case='native_buffer_and_attach', fd=hex(fd), sectors=sectors,
                         bytes=sectors<<9, buffer=hex(buffer),
                         buffer_stride=65536, fits_private_buffer=(sectors<<9)<=65536))

F,V = m.F,m.V
for fat32 in (False, True):
    for sectors in (32,64):
        for cluster in (7, 0x12345):
            if not fat32 and cluster>0xffff:
                continue
            c=m.lower(program,8704)
            c.seed(V+174,sectors,1)
            c.seed(V+200,2 if fat32 else 1,1)
            c.seed(F+160,cluster)
            c.seed(F+164,cluster)
            r.data(c,F+176+20,(cluster>>16).to_bytes(2,'little'))
            r.data(c,F+176+26,(cluster&0xffff).to_bytes(2,'little'))
            # This branch uses a clean FAT cache and no pending chain.
            c.seed(F+354,0xffff,2)
            c.seed(F+356,0,2)
            # FAT32 flush examines this synthetic FAT size and FSInfo sector index.
            c.seed(V+276,3)
            c.seed(V+288,1,2)
            c.seed(V+156,1000)
            c.seed(V+292,0)
            c.seed(V+296,9)
            before=m.fields(c)
            written=c.call(0x200ab02c,(0x81,8704,8704))
            after_write=m.fields(c)
            result=c.call(0x200a6750,(0x81,))
            final=m.fields(c)
            assert written==8704 and result==0
            assert final['length']==8704
            assert final['cluster_high']==cluster>>16 and final['cluster_low']==cluster&0xffff
            rows.append(dict(case='existing_file_flush_release', fat='FAT32' if fat32 else 'FAT16',
                             bytes_per_cluster=sectors<<9, cluster=hex(cluster), write=written, close=result,
                             before=before, after_write=after_write, after_close=final,
                             visited_fat_flush=0x200b0c6c in c.visits,
                             visited_fsinfo=0x200b76ec in c.visits,
                             real_chain_transition_executed=0x200b0240 in c.visits,
                             trace=c.trace,
                             boundary='synthetic file/volume state; media, directory cursor and chain close are stubs'))

for valid in (False,True):
    rows.append(m.fsinfo(program,valid))
for dirty in (False,True):
    rows.append(m.fat_flush(program,dirty))

scope.save(scope.HERE/'native-probe.json',dict(
    status='PASS_BOUNDED_CURRENT_BODY_INSTRUCTIONS', cases=rows,
    instruction_bytes=sum(program.width.values()),
    body_sha256=scope.sha(collect.BODY),
    limits=['No complete FAT32 mount or real cluster-chain traversal.',
            'No SD hardware, power-loss, media removal or physical-card evidence.']))
print('NATIVE_PROBE_DONE',len(rows),flush=True)
