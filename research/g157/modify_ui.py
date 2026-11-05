"""Expose saved selection, verified active selection, and the eight-row diagnostic."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();P=C.PRODUCT
p=P/'adapter.c';s=p.read_text().replace('UV_VALUE,UV_ERR=6','UV_VALUE,UV_DIAG=5,UV_ERR=6')
at=s.index('static int uv_adjusted(')
s=s[:at]+'''static unsigned uv_saved_row(void)
{
    EngRecipeRef r;UvLevels t;unsigned i,user,count=uv_looks();
    if(!eng_saved_selection(&r,&t,&user))return 255;
    if(user)return 8+count+user-1;
    if(!r.effect)return r.slot-1;
    for(i=0;i<count;++i)if(fx_visible(eng_validated_view(),r.unit,i)+1==r.effect)return 8+i;
    return 255;
}
'''+s[at:]
s=s.replace('if(n.ui.screen==UV_L1)return 9+', 'if(n.ui.screen==UV_DIAG)return 8;\n    if(n.ui.screen==UV_L1)return 9+')
s=s.replace('const Gxr2View *v=eng_validated_view();unsigned user;pn_zero(text,KV_UI_TEXT);',
    'const Gxr2View *v=eng_validated_view();unsigned user;pn_zero(text,KV_UI_TEXT);\n    if(n.ui.screen==UV_DIAG){diag_text(row,text);return;}')
s=s.replace('}else pn_copy(text," DISP:Tw",8);', '''}else {pn_copy(text," B00 Status",12);text[2]='0'+diag_code()/10;text[3]='0'+diag_code()%10;}
        if(text[0]==' '&&row==uv_saved_row())text[0]='~';''')
s=s.replace('if(text[0]==\'>\'&&eng_memory_pending())pn_copy(text,">Unsaved",9);',
    '''if(text[0]=='>'&&eng_memory_pending()){
            pn_copy(text,">M00 Unsaved",13);text[3]='0'+eng_memory_error();
        }''')
s=s.replace('const uint8_t *e;UvLevels t;\n    if(index<0)', 'const uint8_t *e;UvLevels t,saved;EngRecipeRef ref;unsigned user;\n    if(index<0)')
s=s.replace('if(n.ui.effect==(unsigned)index+1u)t=n.ui.levels;\n    else if(kv_ui_default',
    '''if(n.ui.effect==(unsigned)index+1u)t=n.ui.levels;
    else if(eng_saved_selection(&ref,&saved,&user)&&ref.effect==(unsigned)index+1u)t=saved;
    else if(kv_ui_default''')
s=s.replace('n.ui.last_cur=n.ui.cur;n.spare.io.preselect=0;\n    if(offer&&n.ui.screen==UV_L1&&cur==offer-1u&&uv_preview(offer,&n.values[offer-1],0)!=ENG_OK)return RV_FAULT;',
    '''n.ui.last_cur=n.ui.cur;
    if(n.ui.screen==UV_DIAG){n.ui.screen=UV_L1;n.ui.cur=offer?offer-1:uv_current_row();n.ui.top=0;return list_bind(3)==RV_OK?RV_CONSUMED:RV_FAULT;}
    if(n.ui.screen==UV_L1&&cur+1u==n.ui.count){n.ui.screen=UV_DIAG;n.ui.cur=n.ui.top=0;return list_bind(3)==RV_OK?RV_CONSUMED:RV_FAULT;}
    n.spare.io.preselect=0;
    if(offer&&n.ui.screen==UV_L1&&cur==offer-1u&&uv_flat_row(cur)!=ENG_OK)return RV_FAULT;''')
start=s.index('    {UvLevels t;unsigned slot=eng_preselect(');end=s.index('    /* Fn rotation:',start)
s=s[:start]+'''    {EngRecipeRef ref;UvLevels t;unsigned user,row;
     if(eng_saved_selection(&ref,&t,&user)){
        if(user)n.ui.saved[user-1]=t;else if(!ref.effect)n.values[ref.slot-1]=t;
        row=uv_saved_row();
        if(!eng_display_current(&ref,&t)&&row<255){} /* active and saved are already separate */
        else if(row<255){n.ui.cur=(uint8_t)row;n.spare.io.preselect=(uint8_t)(row+1);}
     }}
'''+s[end:]
# The display call above returns ENG_OK (0) only for a verified commit.
s=s.replace('if(!eng_display_current(&ref,&t)&&row<255){} /* active and saved are already separate */\n        else if(row<255)',
    'if(eng_display_current(&ref,&t)!=ENG_OK&&row<255)')
s=s.replace('    if(list_bind(1)!=RV_OK)return finish(r,ENG_IO);\n    n.retry=0;',
    '    if(diag_page()){n.ui.screen=UV_DIAG;n.ui.cur=n.ui.top=0;}\n    if(list_bind(1)!=RV_OK)return finish(r,ENG_IO);\n    n.retry=0;')
s=s.replace('uv_preview(offer,&n.values[offer-1],0)!=ENG_OK', 'uv_flat_row(offer-1)!=ENG_OK')
s=s.replace('if(view==56&&code==0x23&&ig_body_config.ok_to_panel&&ok_entry_row())',
    'if(view==56&&code==0x23&&((n.ui.screen==UV_DIAG)||(n.ui.screen==UV_L1&&n.ui.cur+1u==n.ui.count)||(ig_body_config.ok_to_panel&&ok_entry_row())))')
p.write_text(s)
print('diagnostic and independent saved-selection UI applied')
