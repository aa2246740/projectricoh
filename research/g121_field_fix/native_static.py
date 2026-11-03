"""Retain byte-checked native key and capture routine excerpts."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, load, save, sha

image = load(ROOT/'tools/native_harness/image_loader.py', 'native_image')
body = image.Image(ROOT/'firmware/package_v36_g120b/SD_ROOT/ilaunch3', '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008')
folder = OUT/'native-static'
folder.mkdir(exist_ok=True)
records = []
for address, length, name in [(0x202741a8,0x58,'key_context'),(0x20272ed8,0x28,'key_gate'),
    (0x20265818,0x24,'keep'),(0x202b4370,0x40,'dispatch_state'),(0x2005f3a0,0x180,'task_lock'),
    (0x202b1350,0x70,'dispatch_end'),(0x2029fdc4,0x340,'half_first'),
    (0x202a00e4,0x700,'full_first'),(0x202b8c14,0x500,'full_second'),
    (0x202be8b4,0x280,'shutter_close'),(0x20375f14,0x74,'raw_table'),
    (0x202b106c,0x94,'input_init'),(0x202b8608,0x700,'zoom_keys'),
    (0x202af8ec,0x58,'key_counters'),(0x20374eb0,0x100,'key_table_init'),
    (0x2027418c,0x28,'key_mode_set'),(0x20375f88,0x88,'raw_shutter_table'),
    (0x202a4a28,0x180,'display_key'),(0x202be160,0xc0,'display_editor_exit'),
    (0x2016fd80,0x150,'half_packet'),(0x20172f60,0x140,'half_packet_caller'),
    (0x201d21c0,0x120,'full_text'),(0x201d73b0,0x100,'full_text_caller')]:
    path = folder/(name+'.bin')
    data = body.bytes_at(address,length)
    path.write_bytes(data)
    command = [str(ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),'-D','-b','binary','-m','m32r','-EB','--adjust-vma='+hex(address),str(path)]
    result = subprocess.run(command,capture_output=True,text=True,check=True)
    path.with_suffix('.txt').write_text(result.stdout)
    records.append(dict(name=name,address=hex(address),bytes=length,sha256=sha(data)))
save('native-static/identity.json',dict(body_sha256=body.sha256,routines=records))
print('PASS native byte excerpts',len(records),flush=True)
