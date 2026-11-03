"""Replay the retained pre-DAT NAND fault, separately on C and Python."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_review import ROOT, LOCAL, TMP, sha, save, setup


def main():
    setup()
    source = ROOT / 'research/review_probe_pack_r1/local/gpio-review-r3/C-boundary.json'
    record = json.loads(source.read_text())
    captured = record['captured']
    assert captured['root_image'] == 0 and not 0x20000000 <= captured['root_block'] < 0x21000000
    sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_standby'))
    from devices import NAND
    nand = NAND()
    nand.restore(captured['NAND'])
    sys.path.insert(0, str(ROOT / 'tools/native_harness_c'))
    import python_backend as P
    from image_loader import Image
    body = Image(ROOT / 'firmware/package_v39_g154_looks18_test/local/SD_ROOT/ilaunch3',
                 '8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d')
    instruction = bytes.fromhex(captured['instruction'])
    assert body.bytes_at(captured['pc'], len(instruction)) == instruction
    backend = os.environ['GXR_HARNESS_BACKEND']
    assert (P.PythonBackend is P.PurePythonBackend) == (backend == 'python')
    P.CACHE = TMP / ('boundary-' + backend)
    cpu = P.PythonBackend()
    cpu.map(captured['pc'], instruction)
    for name, value in captured['registers'].items():
        cpu.set_reg(name, value)
    def read(address, size):
        try:
            return nand.read(address, size)
        except Exception as exc:
            raise P.Fault(str(exc))
    cpu.add_mmio(0, 4, read, None)
    result = cpu.call(captured['pc'], (), 0x0bad0000, 1)
    assert result.reason == 'fault' and result.pc == captured['pc']
    assert captured['message'] in str(result.detail)
    save(LOCAL / ('boundary-' + backend + '.json'), dict(status='OBSERVED',backend=backend,
         reason=result.reason,detail=result.detail,pc=result.pc,input_sha256=sha(source.read_bytes()),
         root_block=captured['root_block'],root_image=0,scope='Retained pre-DAT state and one instruction, not a fresh complete GPIO run.'))
    print(backend + ' reproduces the retained pre-DAT geometry boundary')


if __name__ == '__main__':
    main()
