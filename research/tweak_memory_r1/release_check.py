"""Check the final release's real cold BOOT dispatch and its zero-write result."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import sha


def main():
    source=HERE/'evidence/p1final-release-detail.json'
    result=json.loads(source.read_text())
    dat=(ROOT/'firmware/package_v310_g155c/GXRCE.DAT').read_bytes()
    assert result['dat_sha256']==sha(dat)
    calls=[r for r in result['calls'] if r['op']==257]
    assert len(calls)==1 and calls[0]['result']==0
    reply=bytes.fromhex(calls[0]['reply'])
    assert int.from_bytes(reply[4:8],'big',signed=True)==-4,reply.hex()
    assert not result['all_boot_settings_writes'] and not result['dirty_settings_writes']
    peer=result['final']['rpc_state']
    assert not any(v['cmd']==22 for v in peer.get('log',[])) and not peer.get('overlay')
    assert result['final']['word']&12==0
    out=HERE/'evidence/final-release-check.json';assert not out.exists()
    out.write_text(json.dumps(dict(status='PASS',layer='模拟器 MAIN 第 0 步冷启动',dat_sha256=sha(dat),
        source_sha256=sha(source.read_bytes()),BOOT_calls=1,BOOT_return=0,reply_status=-4,
        W_S_T_writes=0,DIRTY_GUARD=False,native_state_presets=[]),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',dat_sha256=sha(dat))))


if __name__=='__main__':main()
