from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *

assert file_sha(DAT) == PIN and DAT.stat().st_size == 63380
before = inputs()
save('input-before.json', before)
print(json.dumps(dict(files=len(before), dat_sha256=file_sha(DAT),
                     baseline_sha256=file_sha(BASE_DAT), elf_sha256=file_sha(ELF),
                     body_sha256=file_sha(BODY))))
