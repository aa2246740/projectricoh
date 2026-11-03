"""Enumerate table-compatible replacement subsets; never remove a published Look."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import g155c_baseline as base
from publication import atomic_bytes

HERE=Path(__file__).resolve().parent


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):atomic_bytes(path,(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())


def main():
    registry=read(HERE/'candidate_registry.json');D=base.decoder();stock=base.records()
    rows=[r for r in registry['profiles'] if r['accepted_for_existing_g155c_slot'] and r['unit']!='a12-28']
    assert len(rows)==14
    data={(unit,r['name']):(HERE/r['record_file']).read_bytes() for unit,items in stock.items() for r in items}
    candidate=[(HERE/r['record_file']).read_bytes() for r in rows]
    indices={(r['unit'],r['name']):i for i,r in enumerate(rows)}
    rowparts={entry:[entry[offset:offset+D.LENGTHS[kind]] for kind,offset in zip(D.KINDS,D.OFFSETS)]
              for entry in [*data.values(),*candidate]}
    labels=[r['name'] for r in stock['a12-50'] if r['kind']=='look']
    def size(mask):
        pools=[set() for _ in D.LENGTHS];extra=[set() for _ in D.LENGTHS]
        def entry(unit,name):
            i=indices.get((unit,name));changed=i is not None and bool(mask&(1<<i))
            return candidate[i] if changed else data[unit,name],changed
        for unit in base.UNITS:
            for row in stock[unit]:
                if row['kind']=='builtin':
                    raw,_=entry(unit,row['name'])
                    for kind,value in zip(D.KINDS,rowparts[raw]):pools[kind].add(value)
        descriptors=0
        for label in labels:
            groups=set(entry(unit,label) for unit in base.UNITS);descriptors+=len(groups)
            for raw,changed in groups:
                for kind,value in zip(D.KINDS,rowparts[raw]):
                    if value not in pools[kind]:extra[kind].add(value)
        return 80+3*176+sum(D.align4(len(p)*n) for p,n in zip(pools,D.LENGTHS))+32+32*descriptors+sum(D.align4(len(p)*n) for p,n in zip(extra,D.LENGTHS))
    assert size(0)==base.table_cost({})['data_table_bytes']
    allmask=(1<<len(rows))-1
    assert size(allmask)==base.table_cost({(r['unit'],r['name']):HERE/r['record_file'] for r in rows})['data_table_bytes']
    manifest=read(HERE/'local/g155c_baseline/manifest.json')
    def packages(table):
        result=[]
        for p in manifest['profiles']:
            length=p['DAT_bytes']+table-p['shared_table_bytes']
            allocated=7628+D.align4(length+p['BSS_bytes'])
            result.append(dict(profile=p['profile'],predicted_DAT_bytes=length,
                predicted_main_allocation_bytes=allocated,limit=107612,headroom_bytes=107612-allocated))
        return result
    utility=[]
    for row in rows:
        score=read(HERE/row['scores_receipt'])['scores']['train']
        old,new=score['current']['weighted_de00_square'],score['candidate']['weighted_de00_square']
        utility.append(max(0.,1-new/old))
    required={('mount-a12',22),('mount-a12',23),('mount-a12',24),('a12-50',21),('a12-50',26)}
    mandatory=sum(1<<i for i,r in enumerate(rows) if (r['unit'],r['index']) in required)
    pair=[next(i for i,r in enumerate(rows) if r['unit']=='a12-50' and r['index']==j) for j in (19,29)]
    best=None;feasible=0
    for mask in range(1<<len(rows)):
        if mask&mandatory!=mandatory:continue
        if bool(mask&(1<<pair[0]))!=bool(mask&(1<<pair[1])):continue
        table=size(mask);p=packages(table)
        if any(v['headroom_bytes']<0 for v in p):continue
        feasible+=1
        mount=sum(u for i,(u,r) in enumerate(zip(utility,rows)) if mask&(1<<i) and r['unit']=='mount-a12')
        total=sum(u for i,u in enumerate(utility) if mask&(1<<i))
        rank=(mount,total,-table,-mask)
        if best is None or rank>best[0]:best=(rank,mask,table,p)
    assert best is not None,'No subset retaining all five priority shared refits fits both packages'
    _,mask,table,predicted=best
    chosen=[r for i,r in enumerate(rows) if mask&(1<<i)]
    omitted=[r for i,r in enumerate(rows) if not mask&(1<<i)]
    exact=base.table_cost({(r['unit'],r['name']):HERE/r['record_file'] for r in chosen})
    assert exact['data_table_bytes']==table
    def brief(row):return {k:row.get(k) for k in ('unit','index','name','record_file','record_sha256','requires_companion_builtin')}
    result=dict(label='静态容量候选，未构建DAT',enumerated_masks=1<<len(rows),feasible_priority_preserving_subsets=feasible,
        required_five_shared_refits_preserved=True,published_looks_removed=0,
        method='Preserve all five accepted priority shared refits; require03/Tri-X together; maximise MOUNT relative integer training-loss reduction, then total reduction; never read holdouts to choose this subset',
        scope='Same replacement records for release/test; excludes synthetic-only28mm for this package profile; all21 research candidates remain in the full list',
        selected=[brief(r) for r in chosen],keep_g155c_for_capacity=[brief(r) for r in omitted],
        predicted_packages=predicted,data_table_bytes=table,row_accounting=exact,
        generation_and_host_gate_still_required=True,no_DAT_built=True)
    dump(HERE/'capacity_safe_profile.json',result)
    lists=read(HERE/'dat_candidate_lists.json')
    lists['capacity_safe_same_release_test_profile']=dict(file='capacity_safe_profile.json',sha256=sha(HERE/'capacity_safe_profile.json'),
        selected=result['selected'],keep_g155c_for_capacity=result['keep_g155c_for_capacity'],
        data_table_bytes=table,predicted_packages=predicted,all_published_names_retained=True)
    dump(HERE/'dat_candidate_lists.json',lists)
    report=HERE/'REPORT.md';text=report.read_text()
    marker='\n## 同时满足release/test静态容量的选行方案\n'
    if marker in text:text=text.split(marker)[0]
    lines=[marker,'',
        f'全量21条研究候选仍保留。只在MOUNT/50mm的14条现有槽位候选中枚举16,384个子集，保留全部5条已通过的优先共享曲线重做，03/Tri-X必须成对，不删除任何已发布Look。先最大化MOUNT相对整数训练损失下降，再最大化总下降；包装选行不读取照片。得到{len(chosen)}条同时适合release/test静态字节额度的替换，其余条目保留g155c原记录。',
        '', '| 单元 | 本方案换入 | 为容量保留g155c |','| --- | --- | --- |']
    for unit in ('mount-a12','a12-50'):
        lines.append('| '+unit+' | '+'、'.join(r['name'] for r in chosen if r['unit']==unit)+' | '+('、'.join(r['name'] for r in omitted if r['unit']==unit) or '无')+' |')
    lines+=['','| 包 | 预测DAT B | 预测主分配B | 静态余量B |','| --- | --- | --- | --- |']
    for p in predicted:lines.append('| '+' | '.join(map(str,(p['profile'],p['predicted_DAT_bytes'],p['predicted_main_allocation_bytes'],p['headroom_bytes'])))+' |')
    lines+=['', '这只关闭选行方案的静态字节超限，不关闭g156发现的代数或主机运行门。完整记录与SHA绑定在capacity_safe_profile.json，DAT构建时必须原字节采用并重新解包核对。没有创建DAT或修改代码以扩大容量。',
        '', '可进下一轮DAT构建验证的容量方案见capacity_safe_profile.json；完整质量候选见dat_candidate_lists.json，28mm7项仍仅合成。需要机主素材为MOUNT同场正负16定标与更多04整场景、28mm原厂04 RAW+JPG；本任务清理状态见cleanup.json。']
    atomic_bytes(report,(text+'\n'.join(lines)+'\n').encode())
    print('CAPACITY PROFILE',len(chosen),'records;',predicted,flush=True)


if __name__=='__main__':main()
