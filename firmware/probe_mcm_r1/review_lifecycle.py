"""Record why frozen v3.6 epochs cannot certify natural mode/sleep invalidation."""
from pathlib import Path
import json
import re
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import probe_common as c


def window(raw,address,length):
    spans=[struct.unpack_from('>5I',raw,0x20+20*i) for i in range(16)]
    selected=[r for r in spans if r[1]<=address and address+length<=r[1]+r[2]]
    assert len(selected)==1,(address,length)
    source,va,_,_,_=selected[0]
    offset=512+source+address-va
    return raw[offset:offset+length]


def main():
    c.guard()
    policy_path=c.ROOT/'firmware/image_v36/policy.json'
    policy=json.loads(policy_path.read_text())
    assert [h['number'] for h in policy['hooks'] if h['enabled']]==list(range(1,10))
    body=c.BODY.read_bytes();official=c.OFFICIAL.read_bytes();disabled=[]
    for hook in policy['hooks']:
        if hook['enabled']:continue
        actual=window(body,hook['va'],hook['length'])
        stock=window(official,hook['va'],hook['length'])
        assert actual==stock,hook
        disabled.append(dict(id=hook['id'],number=hook['number'],address=hex(hook['va']),bytes=actual.hex()))
    elf=c.Elf(c.RESIDENT)
    excluded=[name for name in elf.symbols if name.startswith(('rv_notify','rv_epochs','rv_post_'))]
    assert not excluded
    actual_hooks=sorted(name for name in elf.symbols if re.fullmatch('rv_hook_[0-9]{2}',name))
    assert actual_hooks==['rv_hook_'+str(i).zfill(2) for i in (1,2,5,6,7,8,9)],actual_hooks
    folder=c.ROOT/'firmware/resident_v36/resident'
    files=[folder/name for name in ('resident.c','hooks.c','loader.c','shared.c','runtime.c','validate_envelope.inc.c','bridges.S')]
    sources={str(path.relative_to(c.ROOT)):c.sha(path) for path in files}
    mentions=[]
    for path in files:
        for index,line in enumerate(path.read_text().splitlines(),1):
            if 'RV_MODE_E' in line or 'RV_POWER_E' in line:
                mentions.append(dict(file=str(path.relative_to(c.ROOT)),line=index,text=line))
    assert not mentions
    root=(folder/'resident.c').read_text()
    assert 'do{*e++=1;}while(e!=r->epoch+RV_EPOCH_COUNT)' in root
    c.save(c.RESEARCH/'evidence/lifecycle-closure.json',dict(status='GAP',dat_sha256=c.sha(c.LOCAL/'package/GXRCE.DAT'),
        body_sha256=c.sha(c.BODY),resident_elf_sha256=c.sha(c.RESIDENT),policy_sha256=c.sha(policy_path),
        actual_execution_hook_symbols=actual_hooks,disabled_windows_equal_official=disabled,
        mode_power_epoch_mentions_in_compiled_resident_sources=mentions,source_hashes=sources,
        root_epochs_initialized_to_one=True,lifecycle_notifier_symbols_absent=True,
        observed_status='epoch-injection rejection is tested separately; natural event coverage is not proven',
        limitation='This is a targeted artifact/source check, not an exhaustive proof of all computed native stores or physical power behavior.',
        decision='candidate only; keep body frozen and do not invent an event counter'))
    print('CONFIRMED GAP: only H01/H02/H05-H09 execute; disabled mode/sleep hook windows remain official; no natural invalidation claim')


if __name__=='__main__':main()
