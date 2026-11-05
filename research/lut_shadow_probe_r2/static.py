"""Read-only target-byte, call-closure, generation and write-boundary audit."""
from pathlib import Path
import json
import re
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import vectors as V

def function(source,name):
    match=re.search(r'\b'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{',source)
    assert match,name
    begin=match.end()-1; depth=0
    for at in range(begin,len(source)):
        if source[at]=='{': depth+=1
        if source[at]=='}':
            depth-=1
            if depth==0:return source[match.start():at+1]
    raise AssertionError('unterminated function '+name)

def main():
    C.setup()
    folder=C.ENGINE/'local/build'; layout=json.loads((folder/'layout.json').read_text())
    raw=(C.PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert C.sha(raw)==layout['dat_sha256']
    trust=json.loads((C.RESIDENT/'local/resident/trust.json').read_text())
    assert raw[80:112].hex()==trust['resident_build_id'] and raw[212:228].hex()==trust['resident_abi_id']
    assert raw[48:80].hex()==trust['body_sha256']
    assert (folder/'GXRCE.DAT').read_bytes()==raw
    assert struct.unpack_from('>I',raw,28)[0]==C.GENERATION and struct.unpack_from('>H',raw,34)[0]==C.GENERATION
    assert zlib.crc32(raw[256:])==struct.unpack_from('>I',raw,24)[0]
    header=bytearray(raw[:256]); header[20:24]=bytes(4)
    assert zlib.crc32(header)==struct.unpack_from('>I',raw,20)[0]
    assert layout['kernel_no_lto'] and layout['pic_translation_verified']
    nodes=V.packed(V.table('identity')); at=layout['table_symbol']
    assert len(nodes)==29478 and raw[at:at+29478]==nodes
    assert C.sha(nodes)==layout['table_sha256']
    offsets=json.loads((folder/'offsets.json').read_text())
    assert offsets['block.overhead']==7628 and offsets['session.bytes']==1228
    assert layout['main_request']==7628+len(raw)+layout['bss_bytes']<=107612
    assert layout['engine_bytes']<=69632 and len(raw)<=98304
    checked=[]
    for name,record in json.loads((C.LOCAL/'protected-inputs.json').read_text()).items():
        assert C.sha((C.ROOT/name).read_bytes())==record['sha256'],name
        checked.append(name)
    for name,expected in layout['sources'].items():
        assert C.sha((C.ROOT/name).read_bytes())==expected,'build input changed: '+name
    adapter=(C.ENGINE/'local/adapter.c').read_text(); core=(C.ENGINE/'probe.c').read_text()
    capture=function(adapter,'ig_panel_abort'); h41=function(core,'lp_h41')
    assert 'service(' not in capture and 'publish(' not in capture and 'RV_WORD(' not in h41
    assert not re.search(r'RV_(?:BYTE|WORD)\([^;]+\)\s*=',capture)
    assert 'IMG_TOUCHED' not in adapter
    assert 'CAP_UI|CAP_BODY' in adapter and 'CAP_FILE_WRITE' not in adapter and 'CAP_S|' not in adapter and 'CAP_W|' not in adapter
    assert 'q->args[8]==41' in capture and 'IMG_REPLY_DONE' in capture
    services=(C.ENGINE/'local/dependencies/engine_services/services.c').read_text()
    assert 'id!=RV_UI_LIST&&id!=RV_UI_TEXT' in services
    ascii_abi='rv_native_ascii(RV_PTR(u->source_address),u->source_bytes,RV_PTR(u->glyph_address),u->language)'
    assert ascii_abi in services and ascii_abi in (C.HERE/'prepare.py').read_text(), 'native ASCII ABI must match in generated service and generator'
    bridges=(C.ENGINE/'local/dependencies/engine_services/bridges.S').read_text()
    assert not any('NATIVE '+name+',' in bridges for name in ('rv_native_open','rv_native_read','rv_native_close','rv_native_create','rv_native_write','rv_native_rename','rv_native_delete','rv_native_preview'))
    dis=(C.LOCAL/'logs/disassembly.log').read_text(); bodies={}
    for match in re.finditer(r'^([0-9a-f]+) <([^>]+)>:\n',dis,re.M):
        bodies[match.group(2)]=match.end()
    names=list(bodies); code={}
    for i,name in enumerate(names):
        start=bodies[name]; end=bodies[names[i+1]] if i+1<len(names) else len(dis)
        code[name]=dis[start:end].split('\nDisassembly of section ',1)[0]
    closure=set(); indirect=[]
    def visit(name):
        if name in closure:return
        assert name in code,name
        closure.add(name)
        for line in code[name].splitlines():
            for op in re.split(r' -> | \|\| ',line):
                match=re.search(r'\bbl(?:\.l)?\s+[0-9a-f]+\s+<([^>]+)>',op)
                if match:
                    target=match.group(1).split('+')[0]
                    if target in code:visit(target)
                if re.search(r'\bjl\s+r\d+',op):indirect.append(dict(function=name,assembly=op.strip()))
    visit('ig_panel_abort')
    assert all(r['function']=='lp_tick' for r in indirect),indirect
    assert not closure&{'rv_call','rv_service','rv_services_init','rv_native_draw','rv_native_alloc','rv_native_seed','ig_menu'}
    assert not any(re.search(r'\b(?:trap|mvtc)\b',code[name]) for name in closure)
    assert {'lp_kernel','pixel','lp_checksum','lp_h40','lp_h41'}<=closure
    kernel_obj=C.run([C.OBJDUMP,'-dr',folder/'0-kernel.o'],'kernel-object-audit').stdout
    assert 'lp_identity' not in kernel_obj, 'kernel specialized on identity symbol'
    loader=(C.BASE/'resident/validate_envelope.inc.c').read_text()
    assert '!rv_be32(p+28)' in loader and '!rv_aligned32(p+28)' in loader
    # This DAT has its own exact generation gate, with no recipe/UI parser.
    assert 'rv_be32(image+28)!=LP_GENERATION||rv_be16(image+34)!=LP_GENERATION' in adapter
    source=(C.BASE/'resident/loader.c').read_text()
    assert 'chosen=2' in source and not any(x in source for x in ('rv_native_create(', 'rv_native_write(', 'rv_native_rename('))
    assert 'rv_clear(work+n,bytes-RV_SESSION_BYTES-n)' in source
    reset=function(core,'lp_reset'); initialize=function(adapter,'ig_init')
    assert 'clear(&lp' not in reset and 'lp_kernel(' not in reset and 'lp_empty(' not in reset
    assert 'crc32(' not in initialize and 'lp_init_step(' not in initialize
    init=(C.ENGINE/'init.c').read_text(); step=function(init,'lp_init_step')
    assert 'LP_INIT_CHUNK' in step and 'LP_INIT_BUDGET' in step
    assert 'lp_kernel(input,output,4,lp_identity,lp_coordinates)' in step
    assert 'i<64' in step and 'lp_empty()' in step and 'lp.table_crc=~crc' in step
    header=(C.ENGINE/'probe.h').read_text()
    assert 'LP_INIT_BUDGET=250, LP_INIT_CHUNK=2048' in header
    assert (C.ENGINE/'kernel.c').read_bytes()==(C.ROOT/'firmware/engine_lutprobe_r1/kernel.c').read_bytes()
    assert (C.ENGINE/'kernel.h').read_bytes()==(C.ROOT/'firmware/engine_lutprobe_r1/kernel.h').read_bytes()
    assert 'if(!idle_ui())' in function(adapter,'ig_menu') and 'if(!idle_ui())' in function(adapter,'ig_apply')
    panel=(C.ROOT/'tools/gxr_emulator_fast/strict_r4/panel.py').read_text()
    assert '"OK": 24, "MENU": 24' in panel
    allowed=[str(p.relative_to(C.ROOT)) for p in (C.PACKAGE/'local/SD_ROOT/GXRCE.DAT',folder/'engine.elf',C.ENGINE/'local/adapter.c',C.LOCAL/'harness.json')]
    result=C.run(['git','check-ignore',*allowed],'ignore-audit')
    assert set(result.stdout.splitlines())==set(allowed)
    C.save(C.LOCAL/'static.json',dict(status='PASS',dat_sha256=layout['dat_sha256'],generation=C.GENERATION,
        protected_inputs_unchanged=len(checked),table_nodes=4913,table_bytes=len(nodes),main_request=layout['main_request'],
        capture_call_closure=sorted(closure),capture_indirect_calls=indirect,source_write_boundaries=True,
        no_DAT_file_bridges=True,no_color_or_settings_capability=True,resident_generation_gate='any nonzero',
        DAT_generation_gate=f'exact {C.GENERATION} in bootstrap',card_first=True,IROM_writes=False,ignored=allowed,
        boundary='Static closure plus target bytes; runtime readonly mappings and store monitors are checked separately.'))
    print(json.dumps(dict(status='PASS',dat_sha256=layout['dat_sha256'],capture_functions=len(closure))))

if __name__=='__main__': main()
