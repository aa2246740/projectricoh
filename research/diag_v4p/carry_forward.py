"""Preserve unaffected receipts, naming their original artifact and the exact reason."""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s

def main():
    s.enable();e=s.HERE/'evidence';prior=e/'before-width32';round1=s.HERE/'round1/evidence'
    current=json.loads((s.ENGINE/'build/layout.json').read_text());old=json.loads((prior/'static.json').read_text())['layout']
    source=(s.ENGINE/'src/diag.c').read_text()
    before=source.replace('width=RV_WORD(0x205a1594)==1?640:320;base=RV_WORD(0x200c0dc8);\n    if(width!=640){scene()->flags|=DG_INVALID;return;}',
                          'width=RV_BYTE(0x205a1594)?640:320;base=RV_WORD(0x200c0dc8);')
    assert hashlib.sha256(before.encode()).hexdigest()==old['build_inputs']['src/diag.c']
    assert all(digest==old['build_inputs'][name] for name,digest in current['build_inputs'].items() if name!='src/diag.c')
    a=(s.ROOT/'firmware/package_v39_g151/local/SD_ROOT/ilaunch3').read_bytes();b=s.BODY.read_bytes();assert len(a)==len(b)
    diff=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    assert set(diff)<=set((366,367))|set(range(39076,39108))
    groups=[]
    def inherit(name,path,reason,subgroup=None):
        original=json.loads(path.read_text());out=dict(status='PASS',mode='carried_forward',source=str(path.relative_to(s.ROOT)),
            source_sha256=s.sha(path),source_dat_sha256=original.get('dat_sha256',old['dat_sha256']),
            applies_to_dat_sha256=current['dat_sha256'],reason=reason,new_execution=False)
        if subgroup:out['subgroup']=subgroup
        if name in ('legacy-summary','gate-positive-summary','gate-mutation-summary'):
            out.update(original);out['mode']='carried_forward';out['new_execution']=False
        s.save(e/(name+'.json'),out);groups.append(dict(name=name,**out))
    inherit('legacy-summary',round1/'legacy-summary.json','旧 R5 version 4 程序、派生合同和输入全部冻结未变；独立入口不读取 DAT 的 OSD 标志。')
    inherit('gate-positive-summary',round1/'gate-positive-summary.json','历史 version 6 合成包裹合同及当前九行/T 的结构未改；CPU OSD 宽度标志不在其来源内。')
    inherit('gate-mutation-summary',round1/'gate-mutation-summary.json','与上项相同；保留首轮 2793 个真实命令负例的原回执，不声称最终 DAT 重新执行了这些合成输入。')
    inherit('emulator',round1/'emulator.json','原冷启动两次均未装载或执行 DAT；g151/g153 全文件差别仅校验字和 resident build 的 32 字节，其他字节完全相同。新改动只在 DAT 的 H10 OSD 分支。沿用的是冷启动边界证据，不是本轮 g153 新模拟执行。')
    for u in ('28mm','mount'):
        if not (e/('cross-body-'+u+'.json')).exists():
            inherit('cross-body-'+u,prior/('cross-body-'+u+'.json'),'build、ABI、generation、格式与固定机身不变；拒绝在执行 DAT 前完成。最终 DAT 的新旧机身交叉另在50mm实跑，三单元的新机身正常装载另用最终 DAT 实跑。')
        if not (e/('boundary-cursors-'+u+'.json')).exists():
            inherit('boundary-cursors-'+u,prior/('boundary-cursors-'+u+'.json'),'源差异仅 OSD 宽度读取与拒绝；游标恢复和退出分派未改。最终 DAT 在三个单元均实跑五种退出，原15组合边界沿用。')
        if not (e/('readonly-'+u+'.json')).exists():
            inherit('readonly-'+u,prior/('readonly-'+u+'.json'),'只沿用 H40 三来源28B逐笔同值恢复与DAT零K写；该分支及固定resident未改。旧OSD读取结果不作为最终宽度证明，最终32位正反例另在readonly-50mm实跑。','H40 metadata only')
    result=dict(status='PASS',groups=groups,only_engine_source_change='32-bit OSD width and rejection of values other than 1',
        source_reconstruction_matches_previous_sha256=True,body_byte_differences=diff,
        legacy_full_mutation_trace_not_rerun=True,legacy_original_checker_unchanged=True)
    s.save(e/'carry-forward.json',result);print('PASS unaffected receipts',len(groups))
if __name__=='__main__':main()
