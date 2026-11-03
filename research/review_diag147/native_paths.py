"""Conservative native call graphs and explicitly constrained read branches."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import scope
import callgraph
import m32r_listing

body = scope.ROOT / 'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
raw = body.read_bytes()
focus = HERE / 'focused-listings'
focus.mkdir(exist_ok=True)
windows = {
    'parse':(0x200a531c,0x200a544c),
    'ascii':(0x201d73e0,0x201d7800),
    'language':(0x201dc180,0x201dc200),
    'try-wrapper':(0x2005e360,0x2005e3dc),
    'device-read-write':(0x200a2cb8,0x200a3450),
    'native-confirm':(0x202c2d00,0x202c2e00),
    'tick-increment':(0x0500856c,0x050085c0),
}
for name,(start,end) in windows.items():
    (focus / (name+'.txt')).write_text(m32r_listing.dis(raw,start,end)+'\n')
roots = [0x200a531c,0x200a65f8,0x200ab4f0,0x200aad38,0x200a6750]
graph = callgraph.Graph(body)
unrestricted = graph.walk(roots)
scope.save(HERE / 'native-graph-unrestricted.json',dict(roots=[hex(x) for x in roots],graph=unrestricted))

# These substitutions are analysis assumptions only. The replay executes the
# original bytes; no reviewed firmware is changed.
assumptions = {
    0x200a6860:('beqz r8,0x200a6c80','bra 0x200a6c80',
                'Clean lookup/read: flags 0x82 and file+695 zero.'),
    0x200b4a30:('bne r9,r0,0x200b4b48','bra 0x200b4b48',
                'The lookup invokes open-existing with operation 1, never 2.'),
    0x200aae16:('bnc 0x200aae8c','bra 0x200aae8c',
                'One fresh first-cluster read: file sector index 1 <= sectors per cluster.'),
}
for address,(old,new,reason) in assumptions.items():
    assert graph.insn[address] == old,(hex(address),graph.insn.get(address),old)
    graph.insn[address] = new
restricted = graph.walk(roots)
special = {hex(address):name for address,name in callgraph.SEM47.items()}
sem = sorted(address for address in restricted if address in special)
assert not sem,sem
summary = dict(
    body_sha256=scope.sha(body),roots=[hex(x) for x in roots],
    unrestricted_functions=len(unrestricted),read_branch_functions=len(restricted),
    assumptions={hex(pc):dict(original=a,replacement=b,reason=c) for pc,(a,b,c) in assumptions.items()},
    semaphore47_leaves=sem,
    indirect={k:v['indirect'] for k,v in restricted.items() if v.get('indirect')},
    traps={k:v['traps'] for k,v in restricted.items() if v.get('traps')},
    outside={k:v for k,v in restricted.items() if v.get('leaf')=='outside-listing'},
    metadata_entries_in_graph=[hex(x) for x in [0x200b0c6c,0x200b76ec,0x200b823c,0x200b97d0]
                               if hex(x) in restricted],
    limits='Static over-approximation; shared helper modes and indirect device/error dispatch are not exhaustive execution.',
    graph=restricted)
scope.save(HERE / 'native-read-paths.json',summary)
print('NATIVE_PATHS_DONE',len(unrestricted),len(restricted),summary['indirect'],flush=True)
