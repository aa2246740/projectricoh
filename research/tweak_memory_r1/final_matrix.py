"""Summarize only receipts bound to the final DAT, keeping earlier baselines separate."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',default='final-matrix');a=p.parse_args()
    digest=sha((ROOT/'firmware/package_v310_g155c_test/GXRCE.DAT').read_bytes())
    def read(name):
        path=HERE/'evidence'/(name+'.json')
        return json.loads(path.read_text()) if path.exists() else None
    groups=[]
    for label,prefix,cycles in (('MOUNT builtin, including tweak-only second cycle','p1final-mount',2),
        ('MOUNT user','p1final-user',1),('MOUNT Look','p1final-look',1),
        ('50mm builtin','p1final-50',1),('28mm builtin','p1final-28',1)):
        flow=read(prefix+'-resume-flow') or read(prefix+'-flow');manual=read(prefix+'-manual-accept')
        receipts=[read(prefix+'-cold'+str(i)+'-accept') for i in range(1,cycles+1)]
        menus=[read(prefix+'-menu'+str(i)) for i in range(1,cycles+1)]
        glyphs=[read(prefix+'-menu1-glyphs'+part+'-'+backend) for part in ('','-controls') for backend in ('c','python')]
        accepted=bool(flow and flow.get('status')=='PASS' and manual and manual['dat_sha256']==digest)
        accepted=accepted and all(r and r.get('status')=='PASS' and r.get('dat_sha256')==digest and r.get('complete_552_equal') for r in receipts)
        accepted=accepted and all(m and m.get('status')=='PASS' and m.get('open_menu_W_T')==m.get('open_controls_W_T')==0 for m in menus)
        accepted=accepted and all(g and g.get('status')=='PASS' and g.get('dat_sha256')==digest for g in glyphs)
        per_cycle=[]
        for i,(r,m) in enumerate(zip(receipts,menus),1):
            complete=bool(r and r.get('status')=='PASS' and r.get('dat_sha256')==digest and m and m.get('status')=='PASS'
                and m.get('open_menu_W_T')==m.get('open_controls_W_T')==0)
            per_cycle.append(dict(cycle=i,status='PASS' if complete else 'OPEN'))
        groups.append(dict(case=label,prefix=prefix,status='PASS' if accepted else 'OPEN',
            manual_complete=bool(manual and manual.get('status')=='PASS' and manual.get('dat_sha256')==digest),
            complete_cold_cycles=sum(bool(r and r.get('status')=='PASS' and r.get('dat_sha256')==digest) for r in receipts),
            required_cycles=cycles,flow_status=flow.get('status') if flow else 'NOT_RUN',per_cycle=per_cycle,
            note='Only final-SHA complete UI flows count. These use a declared settings read boundary and do not prove NAND persistence.'))
    contracts={}
    for name in ('final-qualification','final-transaction-contract','final-transaction-refusals','final-guard-check','final-record-store'):
        r=read(name);contracts[name]=dict(status='PASS' if r and r.get('status')=='PASS' and r.get('dat_sha256')==digest else 'OPEN',
            evidence=name+'.json',layer=r.get('layer') if r else None,cases=len(r.get('rows',[])) if r else 0)
    native=read('final-native-mode-proof');normal=read('p1final-mount-cold1-accept')
    p1_closed=bool(native and native.get('status')=='PASS' and normal and normal.get('status')=='PASS' and normal.get('dat_sha256')==digest and
        all(contracts[n]['status']=='PASS' for n in ('final-qualification','final-transaction-contract','final-transaction-refusals')))
    recovery=read('final-noDAT-recovery-result')
    release=read('final-release-check')
    zero=read('p1final-zero-result')
    result=dict(verdict='有缺陷',test_DAT_sha256=digest,
        release_DAT_sha256=sha((ROOT/'firmware/package_v310_g155c/GXRCE.DAT').read_bytes()),
        P1_mode_contract='CLOSED_HOST_AND_MODEL' if p1_closed else 'OPEN',groups=groups,contracts=contracts,
        release_BOOT=dict(status='PASS' if release and release.get('status')=='PASS' else 'OPEN',evidence='final-release-check.json'),
        same_DAT_zero_record=dict(status='PASS' if zero and zero.get('status')=='PASS' and zero.get('dat_sha256')==digest else 'OPEN',evidence='p1final-zero-result.json'),
        no_DAT_recovery=dict(status='PASS' if recovery and recovery.get('status')=='PASS' else 'OPEN',evidence='final-noDAT-recovery-result.json',
            scope='HALF/FULL resume at the native C01 continuation; complete photos remain OPEN.'),
        actual_shutdown_NAND=dict(status='OPEN',reason='The native store returned -1 before NAND programming, with logical block count 0.',
            evidence=['store-path-trace-r2.json','store-guard-check.json']),
        owner_builtin_HC_BW_root_cause=dict(status='OPEN',reason='Not reproduced with the specified g154 and g155b artifacts.'),
        earlier_SHA_baselines=['g155c-mount-builtin-flow.json','resumelook-flow.json','finaluser-flow.json',
            'resume28-flow.json','final50-flow.json','gate-zero-result.json'],
        earlier_baselines_count_as_final=False)
    path=HERE/'evidence'/(a.name+'.json');assert not path.exists();path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(verdict=result['verdict'],P1=result['P1_mode_contract'],groups=[(r['case'],r['status']) for r in groups]),ensure_ascii=False))


if __name__=='__main__':main()
