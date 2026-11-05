"""Bind corrected generation-scan evidence to a g158 input snapshot."""
from pathlib import Path
import datetime
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    C.setup()
    C.gate("freeze-g158-after-corrected-generation-scan")
    destination = C.LOCAL / "preflight.json"
    assert not destination.exists(), "Keep the original snapshot; finish.py rechecks it."
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    generation = json.loads((C.LOCAL / 'generation-scan.json').read_text())
    assert generation['DAT_scan_status'] == 'PASS'
    assert generation['status'] == 'BLOCKED_PRIOR_HOST_PROBE_FIXTURE'
    proof = json.loads((C.LOCAL / 'checks/trix-group-r1/equivalence.json').read_text())
    for name, digest in proof['actual_unmodified_C_sources'].items():
        assert C.sha((C.PRODUCT / name).read_bytes()) == digest, 'C source changed after the behavior witness: ' + name
    source = {}
    for folder in (C.BASE, C.ROOT / "firmware/package_v310_g158", C.ROOT / "firmware/package_v310_g158_test"):
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                source[str(path.relative_to(C.ROOT))] = C.sha(path.read_bytes())
    expected = dict(test="6a40262c3fc5b94e7152012c655f5c7d2dc98bf6186cf3e80d2429b76f45fcee",
                    release="756d5840da9d0393f29411a4f8f61c7e2bb88fb546c814b316982ca8c7cb24f6")
    for profile, digest in expected.items():
        assert C.sha(C.baseline_dat(profile).read_bytes()) == digest
    original = C.LOCAL / 'preflight-initial-result.json'
    if original.exists():
        assert json.loads(original.read_text())['baseline_files'] == source, 'Original g158 file snapshot drifted'
    result = dict(status="PASS_INPUT_BINDING", started_utc=started,
                  generation_scan_sha256=C.sha((C.LOCAL / 'generation-scan.json').read_bytes()),
                  generation_status=generation['status'],
                  baseline_files=source, baseline_DAT_sha256=expected,
                  generation159_DAT_created=False, generation159_approved_for_use=False,
                  snapshot_taken_after_behavior_witness=True,
                  behavior_source_and_DAT_hashes_rechecked=True,
                  original_file_snapshot_sha256=C.sha(original.read_bytes()) if original.exists() else None)
    C.save(destination, result)
    print(json.dumps(dict(status=result["status"], generation_status=result['generation_status'],
                          baseline_frozen_files=len(source))))


if __name__ == "__main__":
    main()
