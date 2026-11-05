"""Remove disabled Fn rotation and unconsumed legacy observation counters."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();P=C.PRODUCT
p=P/'adapter.c';s=p.read_text()
s=s.replace('''    uint32_t grain,rotate_serial,h40,h41,last_outer,last_status;
    int8_t rotate;uint8_t last_code;''','''    uint32_t grain;''')
start=s.index('    /* Fn rotation:');end=s.index('    if(diag_page())',start)
s=s[:start]+s[end:]
s=s.replace('    body.last_code=(uint8_t)code;\n','')
start=s.index('    if(view==5&&code&&');end=s.index('    return RV_PASS;',start)
s=s[:start]+s[end:]
s=s.replace('if(q->args[8]==41){++body.h41;body.last_status=q->args[13];return RV_PASS;}','if(q->args[8]==41)return RV_PASS;')
s=s.replace('    ++body.h40;body.last_outer=outer;\n','')
p.write_text(s)
p=P/'boot_adapter.inc.c';s=p.read_text().replace('volatile uint8_t ig_boot_raw_mode;\n','').replace('diag_capture(51);ig_boot_raw_mode=RV_BYTE(0x205d9a7f);bits=boot_fail_bits();','diag_capture(51);bits=boot_fail_bits();');p.write_text(s)
p=P/'src/firmware/engine/core/eng_boot.inc.c';s=p.read_text().replace('g->saved_crc=eng_crc(record,40)','g->saved_crc=b32(record+36)');p.write_text(s)
