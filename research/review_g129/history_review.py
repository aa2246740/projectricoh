"""Judge each retained observation against the current menu contract."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
PIN='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'

def main():
    records=[]
    for unit in ('50mm','28mm','mount'):
        folder=WORK/'local'/('history122-'+unit)
        for path in sorted(folder.glob('**/121-'+unit+'-*.json')):
            d=json.loads(path.read_text());case=d['case'];after=d['after'];partial=case=='partial_reset'
            checks={'final_dat':d['artifact']['dat_sha256']==PIN,
                    'native_draw_clean':not d['native_UI']['bad'],
                    'file_mutations_zero':not any(d['file_mutations'].values()),
                    'confirmed_slot_retained':after['list']['confirmed_slot']==5}
            if partial:
                checks.update({'reset_changes_visible':not d['fault_before_reopen']['matches'],
                               'confirmed_rows_restored':d['after_recipe5']['matches'],
                               'eight_rows_after_restore':after['rows']==8,
                               'restoration_writes_present':d['W']>0})
                basis='重开先恢复已确认 05 的九行和 T，再发布八行；不能沿用旧数据字节期望。'
            else:
                checks.update({'seven_native_rows':after['rows']==7,
                               'no_event_rpc':d['event_RPC']==0,
                               'no_event_row_write':d['W']==0,
                               'recipe_not_applied':not d['after_recipe5']['matches'] and not d['after_recipe6']['matches']})
                if case=='deferred_direction':
                    checks['native_direction_mode']=after['mode']==10
                    basis='列表已撤下；方向键由原生菜单处理，不把原生 mode 10 当作软件 06。'
                else:
                    checks['stock_rows_retained']=d['after_stock']['matches']
                    basis='待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。'
            records.append({'unit':unit,'case':case,'status':'PASS' if all(checks.values()) else 'REVIEW_REQUIRED',
                            'checks':checks,'basis':basis,'source':str(path.relative_to(ROOT)),
                            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                            'rpc_count':d['RPC'],'write_count':d['W'],'rows':after['rows'],'mode':after['mode']})
    assert len(records)==27
    result={'dat_sha256':PIN,'record_count':len(records),'pass_count':sum(r['status']=='PASS' for r in records),'records':records}
    (WORK/'history122-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['27 条历史记录逐条判断。这里只认定本轮主机指令模型中的行为；原记录 OBSERVED 不自动等于产品通过。外层文件名保留旧记录编号，实际 DAT 逐条核对为 gen 129。','',
           '| 单元 | 历史条目 | 行数 / mode | RPC / W | 判断 | 依据 |',
           '| --- | --- | --- | --- | --- | --- |']
    for r in records:
        lines.append('| '+' | '.join(str(v) for v in (r['unit'],r['case'],str(r['rows'])+' / '+str(r['mode']),str(r['rpc_count'])+' / '+str(r['write_count']),r['status'],r['basis']))+' |')
    lines+=['','半按记录只证明模型入口处理；未验证拍摄、RTOS 调度或照片。H07 父层问题及首次发布前窗口仍分别保留，不由这些记录关闭。']
    (WORK/'HISTORY122.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'name':'history122_review','returncode':0,'records':27,'pass':result['pass_count']}))

if __name__=='__main__':main()
