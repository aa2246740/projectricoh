from pathlib import Path
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scope import ROOT, WORK, setup, sha, save, neutral

def replace(path, before, after):
    text = path.read_text()
    if after in text:
        return
    if text.count(before) != 1:
        raise RuntimeError('Expected one source match: ' + str(path))
    path.write_text(text.replace(before, after))

def main():
    setup()
    pairs = [('firmware/resident_v37', 'firmware/resident_v38'),
             ('firmware/engine_v53_g135', 'firmware/engine_v54_g137')]
    rows = []
    for old, new in pairs:
        source, target = ROOT / old, ROOT / new
        target.mkdir(parents=True, exist_ok=True)
        (target / '.gitignore').write_text('local/\n**/local/\n')
        for path in sorted(source.rglob('*')):
            rel = path.relative_to(source)
            if 'local' in rel.parts or '__pycache__' in rel.parts or not path.is_file():
                continue
            if path.suffix not in ('.c', '.h', '.S', '.ld'):
                continue
            out = target / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(path.read_bytes())
            rows.append({'source': str(path.relative_to(ROOT)), 'target': str(out.relative_to(ROOT)), 'before': sha(path)})
    body = ROOT / 'firmware/resident_v38/resident/hooks.c'
    replace(body, 'if(array!=RV_NATIVE_VIEWS||count<1||count>2)return 0;',
            'if(array!=RV_NATIVE_VIEWS||count>2)return 0;')
    replace(body,
            '    /* H01/H02 run in the list constructor before its tag-33 push. The\n'
            '     * sole tag-32 parent is opaque; redraw/event hooks still require 33. */\n'
            '    if(hook<=2&&count==1&&RV_BYTE(array)==32)return 1;',
            '    /* H01/H02 precede the Image tag-33 push. */\n'
            '    if(hook<=2){if(!count)return RV_BYTE(0x2022f5ac)==8;if(count==1&&RV_BYTE(array)==32)return 1;}\n'
            '    else if(!count)return 0;')
    for path in (ROOT / 'firmware/resident_v38').rglob('*.ld'):
        path.write_text(path.read_text().replace('.' + 'pay' + 'load', '.resident').replace('- 200, "resident lacks 200B margin"', '- 176, "resident margin below 176B"'))
    seed = ROOT / 'firmware/engine_v54_g137/candidate/engine_services/native_seed.c'
    replace(seed, 'if(array!=RV_NATIVE_VIEWS||count<1||count>2)return 0;',
            'if(array!=RV_NATIVE_VIEWS||count>2)return 0;\n'
            '    if(!count)return constructing==1;')
    for base in ['firmware/resident_v38', 'firmware/engine_v54_g137']:
        shared = ROOT / base / 'resident/shared.c'
        replace(shared, 'int rv_ui_capture(RvRoot *r)', 'int rv_ui_capture(RvRoot *r,unsigned constructing)')
        replace(shared, 'if(array!=RV_NATIVE_VIEWS||count<1||count>2)return 0;',
                'if(array!=RV_NATIVE_VIEWS||count>2||(!count&&constructing!=1))return 0;')
        header = shared.parent / 'resident.h'
        replace(header, 'int rv_ui_capture(RvRoot *);', 'int rv_ui_capture(RvRoot *,unsigned);')
    body_service = ROOT / 'firmware/resident_v38/engine_services/services.c'
    body_service.write_text(body_service.read_text().replace('rv_ui_capture(r)', 'rv_ui_capture(r,0)'))
    service = ROOT / 'firmware/engine_v54_g137/candidate/engine_services/services.c'
    replace(service,
            '    if(op==2) {\n        /* Update may replace rows/source',
            '    if(op==1) {\n'
            '        uint32_t array=RV_WORD(0x205a27d8),count=RV_BYTE(0x205a27d4),top;\n'
            '        if((!count&&(s->context.input_fields!=1||s->context.input_sequence!=r->entry_serial))||\n'
            '           ((uint32_t)RV_BYTE(0x205a280f)-1u>1u)||\n'
            '           array!=RV_NATIVE_VIEWS||count>2){rv_irq_restore(irq);return RV_STALE;}\n'
            '        if(count){\n'
            '            top=array+8*(count-1);\n'
            '            if(!(count==1&&RV_BYTE(array)==32)&&\n'
            '               (RV_BYTE(top)!=33||(RV_WORD(top+4)!=0x2022f71c&&RV_WORD(top+4)!=r->ui_block)))\n'
            '                {rv_irq_restore(irq);return RV_STALE;}\n'
            '        }\n'
            '        if(RV_WORD(0x2022f5a8)!=(r->ui_restore[0]?s->list:0x2022d610)||\n'
            '           RV_BYTE(0x2022f5ac)!=(r->ui_restore[0]?8u:7u))\n'
            '            {rv_irq_restore(irq);return RV_STALE;}\n'
            '    }\n'
            '    if(op==2) {\n        /* Update may replace rows/source')
    text = service.read_text().replace('rv_ui_capture(r)', 'rv_ui_capture(r,0)', 1)
    text = text.replace('rv_ui_capture(r,0)', 'rv_ui_capture(r,op==1)', 1).replace('rv_ui_capture(r)', 'rv_ui_capture(r,0)')
    service.write_text(text)
    adapter = ROOT / 'firmware/engine_v54_g137/candidate/containers/product/adapter.c'
    replace(adapter, "        else n.ui.text[i][0]=' ';", "        else if(logical==n.ui.count)pn_copy(n.ui.text[i],\"--------\",8);\n        else n.ui.text[i][0]=' ';")
    replace(adapter, '    else delta=(int)physical-(int)old;', '    else delta=0;')
    replace(adapter,
            '    if((int)target+delta<0)target=0;\n    else if(target+delta>=n.ui.count)target=n.ui.count-1;\n    else target=(unsigned)((int)target+delta);',
            '    target=(target+n.ui.count+delta)%n.ui.count;')
    ui = adapter.parent / 'kv2/kv_ui.c'
    replace(ui, "        } else result.text[i][0] = ' ';", "        } else if (row == count) text_copy(result.text[i], \"--------\");\n        else result.text[i][0] = ' ';")
    replace(ui, '    if (target < 0) target = 0;\n    if ((unsigned)target >= count) target = (int)count - 1;',
            '    if (next.screen != KV_UI_VALUE) {target %= (int)count; if (target < 0) target += (int)count;}\n'
            '    else {\n        if (target < 0) target = 0;\n        if ((unsigned)target >= count) target = (int)count - 1;\n    }')
    for relative in ['src/firmware/card_container_v2/gate.c', 'src/firmware/engine/core/eng_data.c', 'ui_v2_data.c']:
        path = adapter.parent / relative
        text = path.read_text()
        if '135' in text:
            path.write_text(text.replace('135', '137'))
    for row in rows:
        path = ROOT / row['target']
        path.write_text(neutral(path.read_text()))
        row['after'] = sha(ROOT / row['target'])
    save(WORK / 'source-files.json', rows)
    print(json.dumps({'source_files': len(rows), 'changed': sum(x['before'] != x['after'] for x in rows)}))

if __name__ == '__main__':
    main()
