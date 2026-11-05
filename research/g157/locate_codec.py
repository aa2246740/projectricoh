from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();p=C.PRODUCT/'memory.c';s=p.read_text();start=s.index('int __attribute__((noinline)) memory_owned')
definition=s[start:];p.write_text(s[:start].replace('#include "../../memory_codec.h"\n',''))
p=C.ENGINE/'candidate/engine_services/crc.c';p.write_text('#include "../memory_codec.h"\n'+p.read_text()+'\n'+definition)
