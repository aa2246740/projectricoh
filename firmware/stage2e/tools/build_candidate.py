#!/usr/bin/env python3
"""Construct an audited body candidate in the selected Stage 2a build directory."""
import argparse
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]


def create_candidate(output):
    output = Path(output).resolve()
    assert output.is_relative_to(HERE)
    spec = importlib.util.spec_from_file_location('stage2a_candidate_audit', HERE/'tools/audit_image.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    files, hooks, payload, symbols = audit.read_inputs(output)
    report = audit.audit(files, hooks, payload, symbols)
    original = files['ilaunch3']
    body = bytearray(original)
    for hook in hooks['hooks']:
        start = int(hook['file_offset'],16)
        body[start:start+hook['length']] = bytes.fromhex(hook['new_bytes'])
    body[0x796c:0x796c+len(payload)] = payload
    checksum = sum(x * (i % 6 + 2) for i,x in enumerate(body[512:])) & 0xffffffff
    struct.pack_into('>I',body,0x16c,checksum)
    assert audit.sha(body) == report['candidate_image_sha256']
    out = output/'candidate/ilaunch3'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(body)
    artifact = out.read_bytes()
    assert artifact == body
    trace = json.loads((ROOT/'research/stage1b_recovery/native-gates-update-trace.json').read_text())
    sections = [struct.unpack_from('>5I',original,32+i*20) for i in range(16)]
    windows = []
    for group,count in [('boot_trace',14),('osd_trace',16)]:
        source = trace['prior_window_revalidation'][group]['windows']
        assert len(source) == count
        for w in source:
            va,size = int(w['va'],16),w['length']
            offsets = [src+512+va-base for src,base,n,_,_ in sections if base <= va and va+size <= base+n]
            assert len(offsets) == 1
            start = offsets[0]
            part = artifact[start:start+size]
            assert part == original[start:start+size] and audit.sha(part) == w['expected_sha256']
            windows.append(dict(group=group,name=w['name'],va=w['va'],file_offset=hex(start),
                                length=size,sha256=audit.sha(part),byte_identical=True))
    variant = json.loads((output/'manifest.json').read_text())['variant']
    report.update(status='CANDIDATE_IMAGE_HOST_VERIFIED',variant=variant,
                  artifact_path=str(out.relative_to(ROOT)),artifact_readback_verified=True,
                  target_deep_injection_enabled=variant == 'deep',protected_update_windows=windows,
                  protected_update_windows_count=len(windows),camera_executed=False)
    (output/'candidate_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    return bytes(artifact),report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,default=HERE/'build')
    args = parser.parse_args()
    _,report = create_candidate(args.build)
    print(json.dumps({k:report[k] for k in ['status','variant','payload_bytes','candidate_image_sha256',
                                           'protected_update_windows_count','changed_bytes']}))


if __name__ == '__main__':
    main()
