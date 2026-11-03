"""Read frozen images, retain byte evidence, and generate a bounded native writer replay.

Run with /usr/bin/python3 -I -B. No device, card, network, or frozen-output writes.
"""
import hashlib
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local/native'
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
BODY = ROOT / 'firmware/image_v34c/local/package/SD_ROOT/ilaunch3'


def at(raw, address, count):
    for i in range(16):
        source, base, size, _, _ = struct.unpack_from('>5I', raw, 32+20*i)
        if base <= address and address+count <= base+size:
            offset = 512+source+address-base
            return raw[offset:offset+count], offset
    raise AssertionError(hex(address))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw, body = OFFICIAL.read_bytes(), BODY.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    assert hashlib.sha256(body).hexdigest() == '24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72'
    state, state_offset = at(raw, 0x2022f71c, 32)
    table = struct.unpack_from('>I', state, 4)[0]
    assert state[0] == 5 and table == 0x2022f56c
    descriptors, table_offset = at(raw, table, 72)
    assert struct.unpack_from('>I', descriptors, 60)[0] == 0x2022d610 and descriptors[64] == 7
    writers = {}
    for name, start, end, kind in [('adj', 0x20285904, 0x20285914, 0),
                                   ('exposure', 0x20286f30, 0x20286f46, 4),
                                   ('white_balance', 0x202876a4, 0x202876ba, 9),
                                   ('image', 0x20287118, 0x2028712e, 5)]:
        code, offset = at(raw, start, end-start)
        assert code == at(body, start, end-start)[0]
        writers[name] = dict(start=hex(start), end=hex(end), file_offset=hex(offset),
                             bytes=code.hex(), stored_kind=kind)
    ranges = [('adj-constructor', 0x202858d4, 0x20285a50),
              ('image-constructor', 0x20287080, 0x202871d8),
              ('descriptor-consumer-writer', 0x202858a0, 0x202858d4),
              ('adj-common', 0x20285724, 0x202858a0)]
    lines = (ROOT / 'research/tooling_m32r/disasm/ilaunch3-sec09-load-2025d800.disasm.txt').read_text().splitlines()
    for name, start, end in ranges:
        excerpt = []
        for line in lines:
            match = re.match(r'([0-9a-f]{8}):\s+((?:[0-9a-f]{2} )+)\s+(.+)', line)
            if match and start <= int(match[1], 16) < end:
                address = int(match[1], 16)
                code = bytes.fromhex(match[2])
                assert at(raw, address, len(code))[0] == code
                excerpt.append(line)
        (OUT / (name+'.disasm.txt')).write_text('\n'.join(excerpt)+'\n')
    # A literal/effective-address census is evidence, not an exhaustive alias proof.
    refs = []
    for line in (ROOT / 'research/hidden_processing/ilaunch3-refs.tsv').read_text().splitlines():
        cells = line.split('\t')
        if len(cells) >= 6 and cells[1] in ('0x2022f71c', '0x2022f720'):
            refs.append(dict(pc=cells[0], target=cells[1], kind=cells[2], instruction=cells[5]))
    direct_table_stores = [r for r in refs if r['target']=='0x2022f720' and r['kind'].startswith('st')]
    assert not direct_table_stores
    def cb(blob):
        return '{'+','.join(str(v) for v in blob)+'}'
    header = '''/* Generated from the frozen official bytes by native_evidence.py.
 * Only seth, or3, and3, ldi, stb and nop are supported. Unknown opcodes fail.
 * This executes the native kind writers; it does not emulate a camera/UI task. */
static void native_writer_bytes(const uint8_t *code,unsigned size)
{
    uint32_t r[16]={0};unsigned i=0,a,b,d,s,imm;
    while(i<size){
        CHECK(i+2<=size);a=code[i];b=code[i+1];d=a&15;s=b&15;
        if((a&240)==208&&b==192){
            CHECK(i+4<=size);r[d]=((uint32_t)code[i+2]<<24)|((uint32_t)code[i+3]<<16);i+=4;
        }else if((a&240)==128&&((b&240)==224||(b&240)==192)){
            CHECK(i+4<=size);imm=((unsigned)code[i+2]<<8)|code[i+3];
            r[d]=(b&240)==224?r[s]|imm:r[s]&imm;i+=4;
        }else if((a&240)==96){r[d]=(uint32_t)(int32_t)(int8_t)b;i+=2;
        }else if((a&240)==32&&(b&240)==0){RV_BYTE(r[s])=(uint8_t)r[d];i+=2;
        }else{CHECK(a==240&&b==0);i+=2;}
    }
}
'''
    for name, data in writers.items():
        header += f'static void native_writer_{name}(void)\n{{static const uint8_t code[]={cb(bytes.fromhex(data["bytes"]))};native_writer_bytes(code,sizeof(code));}}\n'
    header += f'''static void native_seed_boot(void)
{{
    static const uint8_t state[]={cb(state)},descriptors[]={cb(descriptors)};
    memcpy(RV_PTR(0x2022f71c),state,sizeof(state));
    memcpy(RV_PTR(0x2022f56c),descriptors,sizeof(descriptors));
    /* RV_WORD is a host uint32_t lvalue. Decode image words at this boundary. */
    {{unsigned i;for(i=0;i<6;i++){{
        RV_WORD(0x2022f56c+12*i)=be32(descriptors+12*i);
        RV_WORD(0x2022f56c+12*i+8)=be32(descriptors+12*i+8);
    }}}}
    RV_WORD(0x2022f720)=be32(state+4);
    RV_WORD(0x2022f730)=be32(state+20);RV_WORD(0x2022f734)=be32(state+24);
    native_writer_adj();
    CHECK(RV_BYTE(0x2022f71c)==0&&RV_WORD(0x2022f720)==0x2022f56c);
}}
'''
    for folder in ('candidate',):
        path = HERE / folder / 'local/native_seed_model.h'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header)
    result = dict(official_sha256=hashlib.sha256(raw).hexdigest(), body_sha256=hashlib.sha256(body).hexdigest(),
                  state=dict(address='0x2022f71c',file_offset=hex(state_offset),bytes=state.hex(),
                             initial_kind=5,table=hex(table)),
                  descriptor_table=dict(address=hex(table),file_offset=hex(table_offset),bytes=descriptors.hex(),
                                        record_bytes=12,image_settings_index=5,names='0x2022d610',count=7),
                  writers=writers,direct_references=refs,direct_table_stores=direct_table_stores,
                  capacity=dict(value=256,authority='engine_services/api.c rv_services_init; resident.h RV_UI_CAPACITY'),
                  timing=dict(hook='0x2028709c',hook_file_offset='0x23c29c',type5_store='0x2028712c',
                              type5_store_file_offset='0x23c32c',engine_calls_seed_before_type5_store=True),
                  limits=['The gen113 log did not retain the kind byte or table word. Its exact prior kind is unknown.',
                          'ADJ kind0 is a real reachable counterexample, not a claimed observation on this boot.',
                          'The direct-reference census does not prove absence of every aliased write or corruption.'])
    (OUT / 'evidence.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS official writer bytes and descriptor layout; generated bounded native replay')


if __name__ == '__main__':
    main()
