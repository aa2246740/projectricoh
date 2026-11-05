from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();p=C.ENGINE/'candidate/memory_codec.h';s=p.read_text();start=s.index('static inline int memory_owned');end=s.rindex('#endif')
definition=s[start:end].replace('static inline int memory_owned','int __attribute__((noinline)) memory_owned')
p.write_text(s[:start]+'int memory_owned(const uint8_t p[MEMORY_BYTES],uint32_t crc);\n'+s[end:])
p=C.PRODUCT/'memory.c';p.write_text('#include "../../memory_codec.h"\n'+p.read_text()+'\n'+definition)
p=C.PRODUCT/'src/firmware/engine/core/eng_core.c';s=p.read_text()
s=s.replace('static EngStatus boot_restore(void);','static EngStatus boot_restore(void);\nstatic int boot_s_valid(void);')
s=s.replace('''    int mismatch=0;const uint8_t *S;
    eng_read_saved();g->remember_checked=1;
    /* Establish active 04 independently. Native Vivid/WB is never 04. */
    if(settings_match(&(unsigned){0},0)!=ENG_OK)return ENG_OK;
    S=eng_wire_pointer(io.info.address);
    if(!S||S[0x36e]!=1||S[0x6dd]!=9||S[0x6de]!=9||S[8]||
       live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2){''', '''    int mismatch=0,valid;
    eng_read_saved();g->remember_checked=1;
    /* Establish active 04 independently. Native Vivid/WB is never 04. */
    if(settings_info()!=RV_OK)return ENG_OK;
    valid=io.info.token&&io.info.header.version==1&&io.info.header.bytes==sizeof(io.info)&&!io.info.header.flags&&boot_s_valid();
    if(settings_release()!=RV_OK||!valid)return ENG_OK;
    if(live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2){''')
p.write_text(s)
print('one out-of-line record codec and one native baseline predicate')
