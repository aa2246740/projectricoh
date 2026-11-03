"""Replay S readout selection through original packed-parameter code."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study
from replay import Rig, S, STATE, checksum

rows=[]
for mode, wb in ((1,[9,9]),(4,[11,10])):
    rig=Rig()
    try:
        data=bytearray(rig.valid_s())
        data[0x36e]=mode
        data[0x6dd:0x6df]=bytes(wb)
        data[4092:]=checksum(data).to_bytes(4,'big')
        rig.blocks=bytes(data)
        rig.stub(0x2009ac58,0,'block_read_model',rig.block_read)
        result=rig.call(0x20067d68)
        assert result==0 and rig.cpu.read(S,4096)==data
        rows.append(dict(case='valid_body_s_read',mode=mode,wb=wb,
                         result=result,whole_block_equal=True))
    finally:
        rig.close()
for source in (0,1):
    rig=Rig()
    try:
        rig.valid_s()
        rig.stub(0x20062860,0x20640000,'allocation_model')
        rig.stub(0x20062874,0,'release_model')
        rig.stub(0x2006c65c,0,'buffer_ready_model')
        rig.word(S+8,source,1)
        rig.word(STATE+28,1,2)
        assert rig.call(0x20067670,(0x20650000,0x20650004))==0
        rig.word(S+0x36e,1,1)
        rig.cpu.write(S+0x6dd,bytes((9,9)))
        tail=bytes([202])*40
        rig.cpu.write(S+0xfd4,tail)
        rig.word(STATE+8,0)
        value=rig.call(0x200677ac)
        mode=rig.read_word(S+0x36e,1)
        wb=list(rig.cpu.read(S+0x6dd,2))
        assert value==0
        assert mode==(4 if source else 1)
        assert wb==([11,10] if source else [9,9])
        assert rig.cpu.read(S+0xfd4,40)==tail
        rows.append(dict(case='unit_parameter_source',s_source_byte=source,result=value,mode=mode,wb=wb,
                         body_tail_preserved=True,events=rig.events))
    finally:
        rig.close()
study.save('s-source-replay.json',dict(status='PASS_FUNCTION_REPLAY',cases=rows,
           limits='Incoming parameter buffer and allocation are explicit models; no unit transport or MAIN boot.'))
print(json.dumps(dict(status='PASS_FUNCTION_REPLAY',cases=len(rows))))
