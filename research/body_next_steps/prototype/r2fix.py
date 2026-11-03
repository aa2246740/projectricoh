#!/usr/bin/python3 -I
"""Apply the review fixes (review_body_reclaim P1-01..P1-03, P2-03) to a copy of r3.

Usage: r2fix.py <variant_dir> <flags>
flags is a comma list of:
  cap      P1-01  CAP_BODY in the READY publish whitelist and RV_PRODUCT_CAPS
  args     P1-02  image events use args[12] = native SP (f+68) and args[13] =
                  r0 at H40 / encoder status word 0x201BC3AC at H41
  freeze   P1-03  option A: the resident freezes root.epoch[0,1,2,3,6,7] into
                  args[2..7] again (reverts C5)
  freezecp P1-03  option A, compact form (memcpy of epoch[0..3] + two stores)
  done     P2-03  the single handshake call must also return detail=RV_INIT_DONE
  wide     P2-04  r4: also save/restore K+0x190..0x19B
  inline   space  drop noinline on discard_main (loader) and ui_call (hooks)
Edits are exact string replacements; any miss aborts.
"""
import sys
from pathlib import Path

v = Path(sys.argv[1])
flags = set(sys.argv[2].split(','))


def edit(name, old, new):
    p = v / name
    t = p.read_text()
    assert t.count(old) == 1, (name, old)
    p.write_text(t.replace(old, new))


if 'cap' in flags:
    edit('resident.h', 'RV_PRODUCT_CAPS=0xf7fff', 'RV_PRODUCT_CAPS=0x1f7fff')
    edit('loader.c', '(reply->capabilities&(CAP_FILE_WRITE|CAP_UI|CAP_S|CAP_W))',
         '(reply->capabilities&(CAP_FILE_WRITE|CAP_UI|CAP_S|CAP_W|CAP_BODY))')
if 'args' in flags:
    edit('hooks.c', 'q->args[10]=(uint32_t)(uintptr_t)f+68;q->args[11]=f[15];',
         '/* args[10..11] belong to rv_engine (private context); image values use\n'
         '     * args[12] = native SP (outer return address at +4) and args[13] = r0 at\n'
         '     * H40 / the encoder status word at H41 (the wrapper itself returns 0). */\n'
         '    q->args[12]=(uint32_t)(uintptr_t)f+68;q->args[13]=hook==40?f[15]:RV_WORD(0x201bc3ac);')
    edit('hooks.c', '/* K, native sp (outer caller frame) and r0 by value.',
         '/* K, native sp (outer caller frame) and r0 / encoder status by value.')
if 'freeze' in flags:
    edit('resident.c', '    /* args[2..7]: the DAT copies r->epoch itself on entry (root_address in context). */\n',
         '    q->args[2]=r->epoch[RV_BOOT_E];q->args[3]=r->epoch[RV_HEAP_E];\n'
         '    q->args[4]=r->epoch[RV_LINK_E];q->args[5]=r->epoch[RV_UNIT_E];\n'
         '    q->args[6]=r->epoch[RV_VIEW_E];q->args[7]=r->epoch[RV_S_E];\n')
if 'freezecp' in flags:
    edit('resident.c', '    /* args[2..7]: the DAT copies r->epoch itself on entry (root_address in context). */\n',
         '    /* Frozen with IRQs off: args[2..7] = epoch[BOOT,HEAP,LINK,UNIT,VIEW,S]. */\n'
         '    _Static_assert(RV_BOOT_E==0&&RV_HEAP_E==1&&RV_LINK_E==2&&RV_UNIT_E==3&&RV_S_E==RV_VIEW_E+1,"epoch map");\n'
         '    memcpy(&q->args[2],r->epoch,16);q->args[6]=r->epoch[RV_VIEW_E];q->args[7]=r->epoch[RV_S_E];\n')
if 'done' in flags:
    edit('resident.h', 'IMG_REPLY_DONE=1,', 'IMG_REPLY_DONE=1,RV_INIT_DONE=0x49,')
    edit('loader.c', 'reply->actual!=40||r->state!=RV_VALIDATED)goto fail;',
         'reply->actual!=40||\n'
         '       reply->detail!=RV_INIT_DONE||r->state!=RV_VALIDATED)goto fail;')
    edit('loader.c', '    /* One validated entry both registers the entry table and runs the\n'
         "     * engine's pure init (formerly two calls).",
         '    /* One validated entry both registers the entry table and runs the\n'
         "     * engine's pure init (formerly two calls); detail=RV_INIT_DONE only\n"
         '     * after init has fully succeeded.')
if 'wide' in flags:
    edit('hooks.c', 'if(hook==40){memcpy(save,RV_PTR(k+0x14c),16);r->image_state=IMG_ENTERED;}',
         'if(hook==40){memcpy(save,RV_PTR(k+0x14c),16);memcpy(save+4,RV_PTR(k+0x190),12);r->image_state=IMG_ENTERED;}')
    edit('hooks.c', '    else memcpy(RV_PTR(k+0x14c),save,16);',
         '    else {memcpy(RV_PTR(k+0x14c),save,16);memcpy(RV_PTR(k+0x190),save+4,12);}')
    edit('resident.h', '    uint32_t k_save[4];', '    uint32_t k_save[7];')
if 'inline' in flags:
    edit('loader.c', 'static __attribute__((noinline)) int32_t discard_main', 'static int32_t discard_main')
    edit('hooks.c', 'static __attribute__((noinline)) int32_t ui_call', 'static int32_t ui_call')
