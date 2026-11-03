"""Join final identities, complete model captures and the revised callback gate."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import native_gate as g

def main():
    s.enable();s.verify_inputs();digest=s.sha(s.PACKAGE/'GXRCE.DAT');e=s.HERE/'evidence';reasons=[];results={};callbacks=[]
    def take(name):
        path=e/(name+'.json');doc=json.loads(path.read_text()) if path.exists() else {}
        results[name]=doc.get('status','MISSING')
        if results[name]!='PASS':reasons.append(name+' 未通过或缺结果')
        if 'dat_sha256' in doc and doc['dat_sha256']!=digest:reasons.append(name+' DAT 身份不符')
        return doc
    for name in ('static','emulator','native-summary','cli-smoke'):take(name)
    for name in ('legacy-summary','gate-positive-summary','gate-mutation-summary'):
        path=e/(name+'.json');doc=json.loads(path.read_text()) if path.exists() else {}
        results[name]=doc
        if not doc:reasons.append(name+' 缺结果')
    for unit in ('50mm','28mm','mount'):
        host=take('host-'+unit);callbacks.extend(dict(unit=unit,**x) for x in host.get('audit',{}).get('callbacks',[]))
        for name in ('cross-body-','readonly-'):
            doc=take(name+unit)
            audit=doc.get('audit',{})
            callbacks.extend(dict(unit=unit,case=name,**x) for x in audit.get('callbacks',[]))
            for key,value in doc.get('audits',{}).items():callbacks.extend(dict(unit=unit,case=name+key,**x) for x in value.get('callbacks',[]))
        for case in ('cursors',):
            doc=take('boundary-'+case+'-'+unit)
            callbacks.extend(dict(unit=unit,case=case,**x) for x in doc.get('result',{}).get('audit',{}).get('callbacks',[]))
        raw=e/('record-'+unit+'.bin')
        if raw.exists():
            try:g.expand(raw.read_bytes(),digest,g.reference((s.HERE/'reference-v7.json').read_bytes(),s.sha(s.HERE/'reference-v7.json')),s.sha(s.HERE/'reference-v7.json'))
            except (ValueError,KeyError,TypeError) as err:reasons.append(unit+' 实采合同未通过: '+str(err))
        elif host.get('current_rows')!=10 or not host.get('burst_closure') or set(host.get('pages',{}))!=set(map(str,range(11))):
            reasons.append(unit+' 缺当前快照、各页或连拍封存结果')
    exceeded=[x for x in callbacks if x['our_instructions']>2000000]
    if exceeded:reasons.append('自有工作回调超过 2.0 M')
    result=dict(verdict='有缺陷' if reasons else '可以交复审',dat_sha256=digest,g0_pass=not reasons,
        results=results,reasons=reasons,largest_callbacks=sorted(callbacks,key=lambda r:r['our_instructions'],reverse=True)[:15],
        callback_count=len(callbacks),resident_first_load_excluded=True,
        p2=['栈仅含编译器帧和模型 SP；设备原厂完整调用链仍未知','正常按键机会不足时现场记录保持不完整','MMIO 调色板读回与实际显示时机仅完成模型验证','完整原生正例为50mm；另两单元本轮跑当前快照、页面、连拍封存、只读与退出'],
        scope='离线构建、Python 主机模型与批量模拟器')
    s.save(e/'acceptance.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if reasons else 0
if __name__=='__main__':raise SystemExit(main())
