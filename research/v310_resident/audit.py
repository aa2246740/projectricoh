#!/usr/bin/python3
"""复核封存链接证据和源文件摘要，不编译、不运行固件。"""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_resident'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    receipt=json.loads((HERE/'input_receipt.json').read_text())
    changed=[name for name,value in receipt.items()
             if not (ROOT/name).is_file() or sha(ROOT/name)!=value['sha256']]
    assert not changed,changed
    ld=ROOT/'firmware/resident_v310_boot/resident/resident.ld'
    assert sha(ld)==sha(ROOT/'firmware/resident_v310_proto/resident/resident.ld')
    rows=[]
    for name in ('neutral','one_irom_combined','card_combined'):
        out=HERE/'evidence'/name
        m=json.loads((out/'measurement.json').read_text())
        text=(out/'resident.map').read_text()
        end=int(re.search(r'0x([0-9a-f]+)\s+__resident_code_end = \.',text).group(1),16)
        assert m['code_bytes']==end-0x2005276c
        assert m['free_above_margin']==0x20054700-24-end<0
        assert not m['link_ok'] and not (out/'resident.elf').exists() and not (out/'resident.bin').exists()
        assert re.search(r'^\.root\s+0x20054700\s+0xf4$',text,re.M)
        assert re.search(r'^\.root_pins\s+0x200547f4\s+0xc$',text,re.M)
        assert 'mutable globals forbidden)' in text
        for hook in (50,51,52):assert 'rv_hook_'+str(hook) in text
        commands=json.loads((out/'commands.json').read_text())
        policy=[x for x in commands if x['name']=='compile-boot_policy']
        assert len(policy)==1 and '-flto' not in policy[0]['argv']
        assert all(x['returncode']==0 for x in commands if x['name']!='constrained-link')
        assert commands[-1]['name']=='constrained-link' and commands[-1]['returncode']!=0
        assert m['layout']['RvRoot']['bytes']==256
        for tool,value in m['tools_sha256'].items():assert sha(ROOT/tool)==value
        for filename,value in m['source_sha256'].items():
            p=ROOT/'firmware/resident_v310_boot/resident'/filename
            if filename=='loader.c' and name!='neutral':
                p=ROOT/'firmware/resident_v310_proto/options'/name/'resident/loader.c'
            assert sha(p)==value,(name,filename)
        rows.append(dict(variant=name,code_bytes=m['code_bytes'],
                         free_bytes=m['free_above_margin'],link_ok=False))
    result=dict(status='PASS',scope='已封存链接证据与源文件复核，非功能测试',
                input_files=len(receipt),changed_inputs=changed,linker_script_unchanged=True,
                state_word_offset=236,state_word_bytes=4,root_bytes=256,rows=rows,
                functional_tests='NOT_RUN，按中性基线超窗即停止的任务条件停止')
    (HERE/'evidence/audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
