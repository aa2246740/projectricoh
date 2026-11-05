"""Seal the actual package and evidence without promoting missing checks."""
from pathlib import Path
import argparse
import json
import re
import struct
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

REQUIRED=('static','kernel-c','kernel-python','init-c','init-python','init-reference','state-c','state-python','state-reference',
          'full-c','full-reference','cold-native-latest','cold-reference-latest','analysis-check')

def main():
    p=argparse.ArgumentParser(); p.add_argument('--stage',action='store_true'); a=p.parse_args()
    C.setup(); C.gate('seal-and-integrity-verification')
    layout=json.loads((C.PACKAGE/'local/MANIFEST.json').read_text())
    dat=C.PACKAGE/'local/SD_ROOT/GXRCE.DAT'; raw=dat.read_bytes(); digest=C.sha(raw)
    assert digest==layout['dat_sha256']
    rows=[]; missing=[]
    for name in REQUIRED:
        path=C.LOCAL/(name+'.json'); doc=json.loads(path.read_text()) if path.exists() else {}
        good=doc.get('status')=='PASS' and doc.get('dat_sha256')==digest
        rows.append(dict(check=name,status='PASS' if good else 'OPEN',receipt=str(path.relative_to(C.ROOT))))
        if not good: missing.append(name)
    full_cross_compare=False
    cold_cross_compare=False
    state_cross_compare=False; init_cross_compare=False
    for kind in ('state','init'):
        names=[kind+'-'+backend for backend in ('c','python','reference')]
        if all(any(row['check']==name and row['status']=='PASS' for row in rows) for name in names):
            results=[json.loads((C.LOCAL/(name+'.json')).read_text()) for name in names]
            assert results[0]['rows']==results[1]['rows']==results[2]['rows'],kind+' backend divergence'
            if kind=='state': state_cross_compare=True
            else: init_cross_compare=True
    if all(any(row['check']==name and row['status']=='PASS' for row in rows) for name in ('cold-native-latest','cold-reference-latest')):
        left=json.loads((C.LOCAL/'cold-native-latest.json').read_text())
        right=json.loads((C.LOCAL/'cold-reference-latest.json').read_text())
        assert len(left['keys'])==len(right['keys'])
        for x,y in zip(left['keys'],right['keys']):
            assert x==y,('cold GPIO divergence',x,y)
        assert left['ready_text']==right['ready_text']
        for receipt in (left,right):
            assert receipt['loader_zeroed_private_buffers'] and receipt['loaded_DAT_normalized_equal']
            assert receipt['GPIO_init_abort']['init_phase']==4
            assert receipt['GPIO_init_explicit_restart']['init_slices']==1
            assert receipt['GPIO_initialization_ready']['init_slices']==17
            assert receipt['GPIO_initialization_ready']['init_max']<=250
            assert receipt['GPIO_final_safe_standby']['view']==5
            assert receipt['GPIO_final_safe_standby']['activity']==0
        cold_cross_compare=True
    if all(any(row['check']==name and row['status']=='PASS' for row in rows) for name in ('full-c','full-reference')):
        left=json.loads((C.LOCAL/'full-c.json').read_text()); right=json.loads((C.LOCAL/'full-reference.json').read_text())
        assert len(left['samples'])==13
        assert len(right['samples']) in (2,13)
        for receipt in (left,right):
            for row in receipt['samples']:
                bridge=row['bridge']
                assert bridge['actual_resident'] and bridge['encoder_calls']==1
                assert bridge['DAT_session_stores']>0 and not bridge['bad_stores'], 'capture store monitor did not observe DAT reply writes'
        selected=left['samples'] if len(right['samples'])==13 else left['samples'][7:9]
        for x,y in zip(selected,right['samples']):
            for field in ('stage','on','level','target_rows','pairs','expected_pairs','checksum','status','encoder','h41_seen','valid','full','width','height','stride','source_base','delta_valid'):
                assert x['sample'][field]==y['sample'][field],(field,x['sample'],y['sample'])
            assert x['frame_sha256']==y['frame_sha256']
            assert x['source_unchanged'] and y['source_unchanged'] and x['K_unchanged'] and y['K_unchanged']
        assert left['final_stage']==4
        assert right['final_stage']==(4 if len(right['samples'])==13 else 3)
        full_cross_compare=True
    for name,record in json.loads((C.LOCAL/'protected-inputs.json').read_text()).items():
        assert C.sha((C.ROOT/name).read_bytes())==record['sha256'],name
    for name,expected in layout['sources'].items():
        assert C.sha((C.ROOT/name).read_bytes())==expected,'linked source drift: '+name
    harness=json.loads((C.LOCAL/'harness-diff-audit.json').read_text())
    assert harness['status']=='PASS' and harness['panel_exact_ALIAS_only']
    shared=C.ROOT/'tools/gxr_emulator_fast/strict_r4'
    assert C.sha((shared/'panel.py').read_bytes())==harness['source_after_sha256']
    assert C.sha((shared/'NATIVE_REGISTRY.json').read_bytes())==harness['registry_after_sha256']
    r1=[]
    for name in ('SHA256SUMS','local/SHA256SUMS'):
        original=C.LOCAL/'baseline-r1'/name
        current=C.ROOT/'research/lut_shadow_probe_r1'/name
        assert original.read_bytes()==current.read_bytes(),'r1 manifest changed'
        count=0
        for line in original.read_text().splitlines():
            expected,path=line.split('  ',1)
            assert C.sha((C.ROOT/path).read_bytes())==expected,'r1 evidence changed: '+path
            count+=1
        r1.append(dict(manifest=name,entries=count,sha256=C.sha(original.read_bytes()),unchanged=True))
    C.save(C.LOCAL/'r1-integrity-final.json',dict(status='PASS',dat_sha256=digest,manifests=r1))
    # Repository recovery copy only. Never inspect an SD card or claim it is backed up.
    recovery=C.ROOT/'firmware/package_v310_g157_test/local/SD_ROOT/GXRCE.DAT'
    restored=C.PACKAGE/'local/rollback/g157-test/GXRCE.DAT'; restored.parent.mkdir(parents=True,exist_ok=True)
    restored.write_bytes(recovery.read_bytes())
    assert struct.unpack_from('>I',restored.read_bytes(),28)[0]==157
    rollback=dict(source=str(recovery.relative_to(C.ROOT)),sha256=C.sha(restored.read_bytes()),
        package=str(restored.relative_to(C.ROOT)),camera_card_backup=False)
    C.save(C.PACKAGE/'local/rollback.json',rollback)
    template=dict(dat_sha256=digest,status=None,full_pairs=6106112,
        references=[dict(ticks=None,phone_seconds=None),dict(ticks=None,phone_seconds=None)],
        pairs=[dict(kernel_ticks=None,increment_ticks=None,checksum=None,off_encoder_status=None,encoder_status=None,saved_ok=None,full=None,pairs=6106112) for _ in range(3)])
    template_path=C.LOCAL/'field-template.json'
    if template_path.exists():
        previous=json.loads(template_path.read_text())
        if previous.get('dat_sha256')!=digest:
            # Preserve the prior artifact and refuse to replace transcribed
            # owner data. A new candidate needs an empty matching template.
            assert previous.get('status') is None
            assert all(ref.get('ticks') is None and ref.get('phone_seconds') is None for ref in previous['references'])
            assert all(row.get('kernel_ticks') is None and row.get('increment_ticks') is None and row.get('checksum') is None for row in previous['pairs'])
            C.save(C.LOCAL/('field-template-'+previous['dat_sha256']+'.json'),previous)
            C.save(template_path,template)
    else: C.save(template_path,template)
    verdict='可以交复审' if not missing else '有缺陷'
    seal=dict(verdict=verdict,dat_sha256=digest,dat_bytes=len(raw),generation=C.GENERATION,checks=rows,OPEN=missing,
        rollback=rollback,camera_operations=False,network=False,installed_dependencies=False,git_commit=False,git_push=False,
        full_frame_cross_compare=full_cross_compare,
        cold_start_cross_compare=cold_cross_compare,
        state_cross_compare=state_cross_compare,init_cross_compare=init_cross_compare,
        original_r1_unchanged=r1,shared_harness_alias_verified=True,
        sealed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    C.save(C.LOCAL/'seal.json',seal)
    report=C.HERE/'REPORT.md'; text=report.read_text().split('\n',1)[1]
    lead=verdict+'。'+('离线实现与要求的主机、快模拟器和参考模拟器检查通过，实机秒数待机主采集。' if not missing else '离线候选已生成；以下主机验收尚未关闭：'+', '.join(missing)+'。')
    table='\n'.join('| '+r['check']+' | '+r['status']+' |' for r in rows)
    generated='\n'.join(['<!-- BEGIN generated seal -->',
        f'DAT SHA-256：`{digest}`。generation {C.GENERATION}，完整文件 {len(raw):,} B，代码区含表 {layout["engine_bytes"]:,} B，BSS {layout["bss_bytes"]:,} B。',
        f'主块请求 {layout["main_request"]:,} / 107,612 B，余量 {107612-layout["main_request"]:,} B。',
        '', '| 检查 | 当前状态 |','| --- | --- |',table,'',
        ('PASS 回执均绑定本 DAT SHA。整帧交叉比较已通过。' if full_cross_compare else 'PASS 回执均绑定本 DAT SHA；整帧交叉比较仍待关闭。')+
        '[local/seal.json](local/seal.json)列出精确路径。',
        f'仓库 g157 test 回退副本 SHA-256：`{rollback["sha256"]}`。它不是机主卡的备份。',
        '', '实机校时、真实照片的三对 OFF 与 ON、保存等待、DMA 及现场回退均未执行。',
        '<!-- END generated seal -->'])
    text=re.sub(r'<!-- BEGIN generated seal -->.*?<!-- END generated seal -->',generated,text,flags=re.S)
    report.write_text(lead+'\n'+text)
    manifest=dict(generation=C.GENERATION,dat_sha256=digest,dat_bytes=len(raw),main_request=layout['main_request'],
        table_format='Q8.8',table_sha256=layout['table_sha256'],verdict=verdict,camera_verified=False)
    C.save(C.PACKAGE/'MANIFEST.json',manifest)
    # One manifest covers public source plus private reviewer inputs. It is local.
    evidence=[]
    for root in (C.ENGINE,C.PACKAGE,C.HERE):
        for path in sorted(root.rglob('*')):
            if path.is_file() and '/tmp/' not in str(path) and '/decode/' not in str(path) and path.name not in ('SHA256SUMS','queue-status.json'):
                evidence.append((str(path.relative_to(C.ROOT)),C.sha(path.read_bytes())))
    for path in (shared/'panel.py',shared/'NATIVE_REGISTRY.json'):
        evidence.append((str(path.relative_to(C.ROOT)),C.sha(path.read_bytes())))
    (C.LOCAL/'SHA256SUMS').write_text(''.join(sha+'  '+name+'\n' for name,sha in evidence))
    public=[]
    for root in (C.ENGINE,C.PACKAGE,C.HERE):
        for path in sorted(root.rglob('*')):
            if path.is_file() and 'local' not in path.relative_to(root).parts and path.name!='SHA256SUMS':
                public.append((str(path.relative_to(C.ROOT)),C.sha(path.read_bytes())))
    (C.HERE/'SHA256SUMS').write_text(''.join(sha+'  '+name+'\n' for name,sha in public))
    for manifest in (C.HERE/'SHA256SUMS',C.LOCAL/'SHA256SUMS'):
        for line in manifest.read_text().splitlines():
            expected,name=line.split('  ',1)
            assert C.sha((C.ROOT/name).read_bytes())==expected,'sealed evidence drift: '+name
    print(json.dumps(dict(verdict=verdict,dat_sha256=digest,OPEN=missing,
        public_files_verified=len(public),local_evidence_entries_verified=len(evidence)),ensure_ascii=False))
    if missing and not a.stage: sys.exit(2)

if __name__=='__main__': main()
