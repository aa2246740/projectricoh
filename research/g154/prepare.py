"""从冻结的 g153 源码重放 g154 的差异。"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'firmware/engine_v62_g153/candidate/containers/product'
DEST = ROOT / 'firmware/engine_v63_g154/candidate/containers/product'
HERE = Path(__file__).resolve().parent


def change(text, old, new):
    assert text.count(old) == 1, old[:100]
    return text.replace(old, new)


def function(text, name, next_name, replacement):
    start = text.index(name)
    end = text.index(next_name, start)
    return text[:start] + replacement + '\n' + text[end:]


def main():
    a = (BASE / 'adapter.c').read_text()
    a = change(a, 'enum { UV_L1,UV_CARD,UV_ITEMS,UV_VALUE,UV_GROUP,UV_ENTRIES,UV_ERR,UV_LOOKS };',
               'enum { UV_L1,UV_CARD,UV_ITEMS,UV_VALUE,UV_ERR=6 };')
    a = change(a, 'static int keep_view(RvReply *r);',
               'static int keep_view(RvReply *r);\nstatic void cache_home(void);')
    a = change(a, '        (void)es_ui_abort(root);',
               '        cache_home();(void)es_ui_abort(root);')
    a = change(a, '    eng_view_lost(0);eng_menu_close();n.panel.open=n.panel.input_enabled=0;',
               '    if(n.entry==7&&!n.request.args[9])cache_home();\n    eng_view_lost(0);eng_menu_close();n.panel.open=n.panel.input_enabled=0;')
    a = function(a, 'static const char uv_groups', 'static int uv_adjusted', '''static unsigned uv_looks(void)
{return fx_count(eng_validated_view(),eng_validated_view()->selected_module);}
static unsigned uv_current_row(void)
{
    unsigned i,count=uv_looks();
    if(n.ui.applied_user)return 8+count+n.ui.applied_user-1;
    if(n.ui.effect)for(i=0;i<count;++i)
        if(fx_visible(eng_validated_view(),eng_validated_view()->selected_module,i)+1==n.ui.effect)return 8+i;
    return n.ui.slot-1;
}''')
    a = change(a, 'static unsigned uv_rows(void)\n{\n    if(n.ui.screen<KV_UI_SCREENS){',
               'static unsigned uv_rows(void)\n{\n    if(n.ui.screen==UV_L1)return 9+uv_looks()+uv_users(eng_validated_view());\n    if(n.ui.screen<KV_UI_SCREENS){')
    a = change(a, '    if(n.ui.screen==UV_LOOKS)return 1+fx_count(eng_validated_view(),eng_validated_view()->selected_module);\n    if(n.ui.screen==UV_GROUP)return 9;\n    if(n.ui.screen==UV_ENTRIES){unsigned c=uv_count_group(n.ui.group);return c?1+c:2;}\n', '')
    a = function(a, 'static void uv_text(', 'static void cursor_cache(', '''static void uv_text(unsigned row,char text[KV_UI_TEXT])
{
    const Gxr2View *v=eng_validated_view();unsigned user;pn_zero(text,KV_UI_TEXT);
    if(n.ui.screen==UV_L1){
        unsigned count=uv_looks();
        if(row<8){
            unsigned applied=eng_baseline()&&!n.ui.effect&&!n.ui.applied_user&&n.ui.slot==row+1;
            (void)kv_ui_title(eng_knobs_view(),v->selected_module,row+1,
                applied?&n.ui.levels:&n.values[row],eng_list()->row[row].ascii+3,applied?'>':' ',text);
        }else if(row<8+count){
            int index=fx_visible(v,v->selected_module,row-8);
            text[0]=n.ui.effect==(unsigned)index+1u?(uv_adjusted(&n.ui.levels)?'*':'>'):' ';
            fx_name(v,(unsigned)index,text+1);
        }else if((user=row-8-count)<uv_users(v)){
            uv_name(text,uv_user(v,user)[0],user+1,n.ui.applied_user==user+1?'>':' ',&n.ui.saved[user]);
        }else pn_copy(text," DISP:Tw",8);
        if(text[0]=='>'&&eng_memory_pending())pn_copy(text,">Unsaved",9);
        {unsigned w=eng_t_warn();if(w&&row==w-1){text[1]=(char)('0'+w);pn_copy(text+2," Error",6);}}
        return;
    }
    if(n.ui.screen<KV_UI_SCREENS){
        pn_copy(text,n.ui.frame.text[row-n.ui.frame.top],KV_UI_TEXT);
        if(!row&&n.ui.applied_user&&(n.ui.screen==UV_CARD||n.ui.screen==UV_ITEMS)){
            pn_copy(text+1,uv_user(v,n.ui.applied_user-1)+2,7);
            text[4]=uv_adjusted(&n.ui.levels)?'*':'-';
        }
        if(n.ui.effect&&!row&&(n.ui.screen==UV_CARD||n.ui.screen==UV_ITEMS)){
            text[0]='<';fx_name(v,n.ui.effect-1u,text+1);
        }
        return;
    }
    pn_copy(text,n.failed_text,8);
}''')
    a = change(a, 'static int32_t list_bind_impl(unsigned operation)', '''static void cache_home(void)
{
    RvRoot *root=RV_PTR(n.context->root_address);unsigned home=root->ui_restore[11];
    if(root->ui_restore[0]&&home>=1&&home<=7)cursor_cache(home,&n.list,0);
}
static int32_t list_bind_impl(unsigned operation)''')
    a = change(a, 'n.ui.count=(uint8_t)uv_rows();if(!n.ui.count)return RV_RANGE;',
               'n.ui.count=(uint8_t)uv_rows();if(!n.ui.count||n.ui.count>49)return RV_RANGE;')
    a = change(a, '    status=list_bind(3);if(status!=RV_OK)return 0;\n    n.watch_view=',
               '    status=list_bind(3);if(status!=RV_OK)return 0;\n    if(n.entry==7&&!n.request.args[9])cache_home();\n    n.watch_view=')
    a = change(a, '    n.watch_view=n.safe_entry=n.flush_reason=n.active=0;r->status=RV_OK;return result;',
               '    if(result==RV_CLOSE_AND_PASS)cache_home();\n    n.watch_view=n.safe_entry=n.flush_reason=n.active=0;r->status=RV_OK;return result;')
    a = change(a, 'static EngStatus uv_look_row(unsigned row)', 'static EngStatus uv_look_row(unsigned ordinal)')
    a = change(a, 'selected_module,row-1u);', 'selected_module,ordinal);')
    a = function(a, 'static EngStatus uv_move(', 'static int32_t init_core(', '''static EngStatus uv_flat_row(unsigned row)
{
    unsigned count=uv_looks(),user;
    if(row<8)return uv_preview(row+1,&n.values[row],0);
    if(row<8+count)return uv_look_row(row-8);
    user=row-8-count;
    if(user<uv_users(eng_validated_view())){
        const uint8_t *entry=uv_user(eng_validated_view(),user);
        return uv_preview(entry[0],&n.ui.saved[user],user+1);
    }
    return ENG_OK;
}
static EngStatus uv_move(unsigned physical)
{
    unsigned old=n.ui.physical,target=n.ui.cur;int delta;UvLevels levels;EngStatus status=ENG_OK;KvUiNav nav;
    if(physical>=UV_PHYSICAL)return ENG_REJECTED;
    n.spare.io.preselect=0;n.ui.last_cur=n.ui.cur;
    if(n.ui.screen==UV_L1){
        if(physical==(old+1)%UV_PHYSICAL)delta=1;
        else if(physical==(old+UV_PHYSICAL-1)%UV_PHYSICAL)delta=-1;
        else delta=0;
        n.ui.armed=0;n.ui.physical=(uint8_t)physical;
        target=(target+n.ui.count+delta)%n.ui.count;
        status=uv_flat_row(target);
        if(status==ENG_OK)n.ui.cur=(uint8_t)target;
        return status;
    }
    if(n.ui.screen<KV_UI_SCREENS){
        uv_nav_load();
        if(kv_ui_native_move(eng_knobs_view(),eng_validated_view()->selected_module,n.ui.slot,
            &n.ui.levels,&n.ui.nav,physical,&levels,&nav))return ENG_REJECTED;
        n.ui.physical=(uint8_t)physical;
        if(n.ui.screen==UV_VALUE&&!pn_equal(&levels,&n.ui.levels,sizeof(levels)))status=uv_active(&levels);
        if(status==ENG_OK)uv_nav_accept(&nav);
    }
    return status;
}
static int32_t uv_disp(void)
{
    unsigned cur=n.ui.cur,offer=n.spare.io.preselect;UvLevels levels;KvUiNav nav;KvUiEvent event;
    n.ui.last_cur=n.ui.cur;n.spare.io.preselect=0;
    if(offer&&n.ui.screen==UV_L1&&cur==offer-1u&&uv_preview(offer,&n.values[offer-1],0)!=ENG_OK)return RV_FAULT;
    if(n.ui.screen==UV_L1){
        if(kv_ui_nav_init(eng_knobs_view(),eng_validated_view()->selected_module,n.ui.slot,&n.ui.levels,&nav))return RV_FAULT;
        n.ui.l1_cur=n.ui.cur;uv_nav_accept(&nav);
    }else if(n.ui.screen==UV_CARD&&!cur){
        n.ui.screen=UV_L1;n.ui.cur=n.ui.l1_cur;n.ui.top=0;
    }else if(n.ui.screen<KV_UI_SCREENS){
        uv_nav_load();
        if(kv_ui_disp(eng_knobs_view(),eng_validated_view()->selected_module,n.ui.slot,&n.ui.levels,
            &n.ui.nav,&levels,&nav,&event))return RV_FAULT;
        if(event.kind==KV_UI_EVENT_DEFAULT&&uv_active(&levels)!=ENG_OK)return RV_FAULT;
        uv_nav_accept(&nav);
    }
    return list_bind(3)==RV_OK?RV_CONSUMED:RV_FAULT;
}''')
    a = change(a, 'n.ui.cur=n.ui.effect?8:n.ui.applied_user?9:n.ui.slot-1;', 'n.ui.cur=uv_current_row();')
    a = change(a, 'n.ui.screen==UV_L1&&n.ui.cur<8&&', 'n.ui.screen==UV_L1&&n.ui.cur+1u<n.ui.count&&')
    a = change(a, '    eng_menu_close();n.stopped=1;', '    cache_home();eng_menu_close();n.stopped=1;')
    (DEST / 'adapter.c').write_text(a)
    k = (BASE / 'kv2/kv_data.c').read_text()
    k = change(k, '    p = v->bytes + KV_DATA_RECIPE_OFFSET + (unit * 8 + slot - 1) * KV_DATA_RECORD;',
               '    if (unit == 2 && slot != 4) unit = 0;\n    p = v->bytes + KV_DATA_RECIPE_OFFSET + (unit * 8 + slot - 1) * KV_DATA_RECORD;')
    (DEST / 'kv2/kv_data.c').write_text(k)
    k = (BASE / 'kv2/kv_ui.c').read_text()
    k = change(k, 'case KV_UI_L1: return 11;', 'case KV_UI_L1: return 9;')
    start = k.index('        if (row == 8) text_copy(text, " Looks");')
    end = k.index('        break;', start)
    k = k[:start] + '        text_copy(text, " DISP:Tw");\n' + k[end:]
    k = change(k, 'event.kind = row == 8 ? KV_UI_EVENT_LOOKS : row == 9 ? KV_UI_EVENT_MYREC : KV_UI_EVENT_RECIPE;',
               'event.kind = row < 8 ? KV_UI_EVENT_RECIPE : KV_UI_EVENT_NONE;')
    (DEST / 'kv2/kv_ui.c').write_text(k)
    for rel in ('pack.py', 'ui_v2_data.c', 'src/firmware/card_container_v2/gate.c', 'src/firmware/engine/core/eng_data.c'):
        text = (BASE / rel).read_text()
        assert text.count('153') == 1, rel
        text = text.replace('153', '154')
        if rel == 'ui_v2_data.c':
            text = change(text, '#include "ui_v2_data.h"', '#include "ui_v2_data.h"\n#include "fx_pool.h"')
            text = change(text, '    n=uv_users(v);\n', '    n=uv_users(v);\n    if(9+fx_count(v,v->selected_module)+n>49)return 0;\n')
        (DEST / rel).write_text(text)
    entry = DEST.parents[1] / 'build153.py'
    if entry.exists(): entry.unlink()
    (DEST.parents[1] / 'build154.py').write_text("from pathlib import Path\nimport runpy\nrunpy.run_path(str(Path(__file__).resolve().parents[3] / 'research/g154/build.py'), run_name='__main__')\n")
    tool=(BASE.parents[1]/'user_entries.py').read_text()
    tool=change(tool,'    if generation != 152:\n        raise ValueError(\'requires the gen 152 envelope\')',
        "    if generation != 154:\n        raise ValueError('requires the current generation envelope')")
    tool=change(tool,'def parse(raw):', '''def entry_limit(raw):
    shared=struct.unpack_from('>I',raw,192)[0]
    area=shared+struct.unpack_from('>I',raw,shared+64)[0]
    count=struct.unpack_from('>H',raw,area+10)[0]
    visible=[sum(bool(raw[area+32+32*i+18] & (1<<unit)) for i in range(count)) for unit in range(3)]
    return min(gxui.CAPACITY,40-max(visible))


def parse(raw):''')
    tool=change(tool,"    if count > gxui.CAPACITY:\n        raise ValueError('entry count exceeds capacity')",
        "    if count > entry_limit(raw):\n        raise ValueError('flat list user limit: '+str(entry_limit(raw)))")
    tool=change(tool,'def replace(raw, users):\n    at, _, _ = parse(raw)',
        "def replace(raw, users):\n    if len(users)>entry_limit(raw):\n        raise ValueError('flat list user limit: '+str(entry_limit(raw)))\n    at, _, _ = parse(raw)")
    (DEST.parents[1]/'user_entries.py').write_text(tool)
    files = [p for p in DEST.rglob('*') if p.is_file() and 'local' not in p.parts]
    changes = [str(p.relative_to(DEST)) for p in files if (BASE/p.relative_to(DEST)).is_file() and p.read_bytes() != (BASE/p.relative_to(DEST)).read_bytes()]
    (HERE / 'evidence/source-changes.json').write_text(json.dumps(dict(status='PASS', files=changes,
        core_unchanged=(DEST/'src/firmware/engine/core/eng_core.c').read_bytes()==(BASE/'src/firmware/engine/core/eng_core.c').read_bytes()),indent=2)+'\n')
    print(json.dumps(dict(status='PASS', files=changes)))


if __name__ == '__main__': main()
