"""初始机械修改记录；最终完整差异以 evidence/source.diff 为准。"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ENGINE=ROOT/'firmware/engine_v64_g155'
PRODUCT=ENGINE/'candidate/containers/product'

def change(path,old,new):
    text=path.read_text()
    if old not in text:
        assert new in text,(path,old)
        return
    assert text.count(old)==1,(path,old,text.count(old))
    path.write_text(text.replace(old,new))

def main():
    for path in (ROOT/'firmware/resident_v310_g155/resident/resident.h',ENGINE/'resident/resident.h'):
        change(path,'RV_MAX_CODE=65536','RV_MAX_CODE=69632')
    for name in ('src/firmware/card_container_v2/gate.c','src/firmware/engine/core/eng_data.c','ui_v2_data.c','pack.py'):
        p=PRODUCT/name
        p.write_text(p.read_text().replace('==154','==155').replace('== 154','== 155').replace('!=154','!=155'))
    change(PRODUCT/'src/firmware/card_container_v2/gate.c','v.sections[0].length>65536','v.sections[0].length>69632')
    change(PRODUCT/'src/firmware/engine/core/eng_data.c','v->sections[0].length>65536','v->sections[0].length>69632')
    change(PRODUCT/'pack.py','len(engine) > 65536','len(engine) > 69632')
    change(PRODUCT/'engine.ld','SIZEOF(.engine) <= 65536, "engine exceeds 64 KiB"','SIZEOF(.engine) <= 69632, "engine exceeds 68 KiB"')
    change(PRODUCT/'looks_data.py','CAPS=(8,28,32,32)','CAPS=(0,16,12,12)')
    core=PRODUCT/'src/firmware/engine/core/eng_core.c'
    change(core,'record is not stored yet. A user entry\'s record is forty zeros.','record is not stored yet. User indices remain one-based in RAM.')
    change(core,'uint8_t live_verified,snapshot_fault;','uint8_t live_verified,snapshot_fault,boot_active;')
    change(core,'    return result;\n}\nstatic int snapshot','    if(g.boot_active&&!eng_boot_check())return RV_STALE;\n    return result;\n}\nstatic int snapshot')
    change(core,'    if(user||r->effect)return;\n    copy(p,"GXR2\\1",5);p[5]=r->slot;p[6]=g.data.unit;p[7]=1;',
        '    copy(p,"GXR2\\3",5);p[5]=user?(uint8_t)(0x80+user-1):r->effect?(uint8_t)(0x40+r->effect-1):r->slot;p[6]=g.data.unit;p[7]=1;')
    change(core,'/* GXR2 v1: slot, unit, complete, ten int16 controls, the DAT header\'s two',
        '/* GXR2 v3: category/index, unit, complete, ten int16 controls, the DAT header\'s two')
    change(core,'void eng_memory_user(unsigned user){g.memory_user=(uint8_t)(user!=0);}',
        'void eng_memory_user(unsigned user){g.memory_user=(uint8_t)user;}\nunsigned eng_current_user(void){return g.current_user;}')
    # The menu-only v1 offer stays separate from the automatic transaction.
    # v3 is decoded by the shared record reader below.
    change(core,'    if(g.boot_my||p[5]-1u>7u)return ENG_OK;',
        '    if(g.boot_my||p[5]-1u>7u)return ENG_OK;')
    if '#include "eng_boot.inc.c"' not in core.read_text():
        core.write_text(core.read_text()+'\n#include "eng_boot.inc.c"\n')
    header=PRODUCT/'src/firmware/engine/core/eng_core.h'
    change(header,'void eng_boot_source(unsigned my);',
        'void eng_boot_source(unsigned my);\nint eng_boot_check(void);\nEngStatus eng_boot_run(volatile uint32_t *,unsigned *);\nunsigned eng_current_user(void);')
    adapter=PRODUCT/'adapter.c'
    change(adapter,'#include "blackbox.h"','#include "blackbox.h"\n#ifndef G155_BOOT\n#define G155_BOOT 0\n#endif')
    change(adapter,'static BodyState body;','static BodyState body;\nstatic uint32_t boot_mode_epoch,boot_settings,boot_settings_bytes;')
    change(adapter,'    return rv_view_owned(RV_PTR(n.context->root_address),u,n.entry==1);',
        '    if(n.entry==51)return rv_settings_owned(RV_PTR(n.context->root_address),n.request.args[6]);\n    return rv_view_owned(RV_PTR(n.context->root_address),u,n.entry==1);')
    change(adapter,'const uint8_t *entry;unsigned user=n.ui.applied_user;',
        'const uint8_t *entry;unsigned user=eng_current_user();n.ui.applied_user=(uint8_t)user;')
    change(adapter,'    if(!body_request(c,q,r,a))return RV_PASS;\n    if(q->args[8]==9){',
        '    if(!body_request(c,q,r,a))return RV_PASS;\n    if(q->args[8]==0x101)return boot_run(a,c,q,r);\n    if(q->args[8]==9){')
    change(adapter,'int32_t ig_panel_event(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)',
        '#include "boot_adapter.inc.c"\nint32_t ig_panel_event(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)')

if __name__=='__main__':main()
