"""Bind the review decision and evidence to the shipped artifact."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
out=scope.HERE
def get(name):
    return json.loads((out/name).read_text())
dat=(scope.ROOT/'firmware/package_v38_diag146/SD_ROOT/GXRCE.DAT').read_bytes()
head=bytearray(dat[:256]);head[20:24]=bytes(4)
assert zlib.crc32(head)&0xffffffff==struct.unpack_from('>I',dat,20)[0]
assert zlib.crc32(dat[256:])&0xffffffff==struct.unpack_from('>I',dat,24)[0]
assert hashlib.sha256(dat).hexdigest()=='1a3ed0457540a86100bb1327b9120a05460bb9e0b6169c017e374188cc4b4abd'
assert get('rebuild/result.json')['byte_equal']
assert get('static-diag146.json')['generation']==146
assert json.loads((out/'lock-proof.log').read_text())['status']=='PASS'
rows=get('host-suite.json')
assert len(rows)==18 and all(r['returncode']==0 for r in rows)
for r in rows:
    case=get('local/accept146-'+r['case']+'.json')
    assert case['s_hash_same'] and not case['s_writes'] and case['rpc_w']==0
    assert not case['violations'] and not case['creates_renames_deletes']
a=out/'host-files/accept146-28mm-retire-last.bin'
b=out/'counterexample/GXRTRACE.BIN'
assert a.read_bytes()==b.read_bytes()
assert scope.sha(a)=='25e43ffcd27d943380f688f341e1ffb5ebc447425d3742d3ddafdf17fff57c63'
c=out/'host-files/accept146-busyall-last.bin'
d=out/'host-files/accept146-notready-last.bin'
assert c.read_bytes()==d.read_bytes()
assert all(get('cluster32/buffer-guards.json')['guards'].values())
overlay=get('overlay-case/result.json')['entry']
assert (overlay['outcome'],overlay['overlay_on'],overlay['ov_fail'])==('X',0,1)
assert (out/'REVIEW.md').read_text().splitlines()[0]=='不能上卡'
scope.save(out/'final-checks.json',dict(
    status='REVIEW_COMPLETE_WITH_BLOCKING_FINDING',decision='不能上卡',
    dat_sha256=hashlib.sha256(dat).hexdigest(),dat_header_crc=True,dat_payload_crc=True,
    required_lock_and_static_checks=True,rebuild_byte_equal=True,
    host_cases_passed=18,all_host_cases_no_s_or_rpc_w_or_create_rename_delete=True,
    retired_and_three_busy_menus_full_file_equal=True,
    counterexample_trace_sha256=scope.sha(a),
    all_busy_and_notready_full_file_equal=True,
    native_probe_cases=len(get('native-probe.json')['cases']),
    expanded_fat32_status=get('fat32-paths.json')['status'],
    overlay_failure_fields_verified=True,cluster32_guards_verified=True,
    physical_card_and_camera_accessed=False,full_fat32_emulator_run=False))
print('FINAL_CHECKS_DONE','cannot_test_card','host_cases=18',flush=True)
