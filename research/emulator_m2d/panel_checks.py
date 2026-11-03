"""Check pin levels, matrix row selection, release and the host write boundary."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
from input_run import machine_from
from panel import Panel
from dial import set_dial
from backend import REGS
from storage_run import sources


def main():
    target = OUT / (sys.argv[1]+".json")
    if target.exists():
        raise ValueError("use a fresh panel check record")
    machine = machine_from(ROOT / "research/emulator_m2b/local/stable-final-r1-stop.pkl", "panel-check")
    cpu, gpio = machine.cpu, machine.devices["gpio"]
    panel = Panel(cpu, machine.devices)
    def ram_hashes():
        return [hashlib.sha256(data).hexdigest() for _, data, _ in cpu.regions]
    checks = []
    try:
        original_ram = ram_hashes()
        original_registers = {name: cpu.get_reg(name) for name in REGS}
        expected = {"ADJ": (0, 4, 23), "OK": (2, 16, 24), "DISP": (3, 8, 21),
                    "UP": (2, 1, 15), "DOWN": (2, 2, 18),
                    "LEFT": (2, 4, 17), "RIGHT": (2, 8, 16)}
        for name, (row, mask, code) in expected.items():
            panel.set_key(name, True)
            values = []
            for selected in range(4):
                gpio.write(0xFF7040AF, bytes([0xF0 & ~(0x80 >> selected)]))
                panel.advance()
                value = gpio.read(0xFF7040B0, 1)[0] & 0x1F
                assert value == (0x1F & ~mask if selected == row else 0x1F)
                values.append(value)
            assert panel.records[name]["code"] == code
            panel.set_key(name, False)
            assert gpio.read(0xFF7040B0, 1)[0] & 0x1F == 0x1F
            checks.append({"key": name, "row_values": values, "release": 31, "passed": True})
        for name, mask, code in (("HALF", 2, 13), ("FULL", 4, 14)):
            panel.set_key(name, True)
            assert not gpio.read(0xFF7040AF, 1)[0] & mask
            assert panel.records[name]["code"] == code
            panel.set_key(name, False)
            assert gpio.read(0xFF7040AF, 1)[0] & mask
            checks.append({"key": name, "mask": mask, "passed": True})
        dial = set_dial(cpu, machine.devices, 2)
        assert dial["hid_index"] == 27 and gpio.read(0xFF7040B1, 1)[0] & 0xF8 == 0xD8
        set_dial(cpu, machine.devices, 0)
        assert gpio.read(0xFF7040B1, 1)[0] & 0xF8 == 0
        checks.append({"case": "mode_dial_table_and_port", "code": 2, "value": 216, "passed": True})
        before = dict(gpio.inputs)
        try:
            set_dial(cpu, machine.devices, 3)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown mode-dial code accepted")
        assert gpio.inputs == before
        checks.append({"case": "unknown_dial_code_rejected", "passed": True})
        before = dict(gpio.inputs)
        try:
            panel.set_key("UNDECLARED", True)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown key accepted")
        assert gpio.inputs == before
        assert original_ram == ram_hashes()
        assert original_registers == {name: cpu.get_reg(name) for name in REGS}
        monitor = machine.devices["monitor"]
        assert monitor.base+0x5C in cpu.breakpoints
        checks.append({"case": "host_changes_only_input_bits_and_preserves_monitor", "passed": True})
        target.write_text(json.dumps({"passed": len(checks), "total": len(checks),
                                      "checks": checks, "sources": sources()}, indent=2) + "\n")
        print(json.dumps({"passed": len(checks), "total": len(checks)}))
    finally:
        machine.close()


if __name__ == "__main__":
    main()
