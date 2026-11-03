#!/usr/bin/env python3
"""Interpret objdump-decoded bridge instructions from the linked artifact.

This checks the ABI model and actual emitted instruction stream on the host.
It is not an M32R hardware emulator or a camera-execution claim.
"""
import argparse
import json
from pathlib import Path
import re


class BridgeModel:
    def __init__(self, disassembly, symbols):
        self.code = {}
        for line in disassembly.splitlines():
            match = re.match(r"\s*([0-9a-f]+):\s*(?:[0-9a-f]{2}\s+)+\s*(.*)",line)
            if match:
                instructions = re.split(r"\s*(?:->|\|\|)\s*",match[2].split(" <")[0])
                self.code[int(match[1],16)] = instructions
        self.symbols = symbols

    @staticmethod
    def reg(name):
        return {"lr":14,"sp":15,"fp":13}.get(name,int(name[1:]) if name.startswith("r") else -1)

    def execute(self, name, returns=None, stops=()):
        self.registers = [0x10001000 + index * 0x101 for index in range(16)]
        self.registers[15] = 0x30010000
        self.registers[14] = 0xeeee0000
        self.psw = 0x81
        self.memory = {}
        self.calls = []
        self.stack_calls = []
        self.before = self.registers[:]
        self.before_psw = self.psw
        pc = self.symbols[name]
        if returns is None: returns = {}
        for _ in range(1000):
            if pc == 0xeeee0000 or pc in stops:
                return pc
            if pc in returns:
                callback, result = returns[pc]
                target = self.registers[14]
                args = self.registers[4:8] if callback == "native" else self.registers[:4]
                self.calls.append((callback,args[:]))
                self.stack_calls.append([self.memory.get(self.registers[15] + i*4) for i in range(3)])
                for index in range(14): self.registers[index] = 0xcccc0000 + index
                self.psw = 0
                self.registers[14] = 0xcccccccc
                self.registers[0] = result
                pc = target
                continue
            word = self.code[pc]
            next_pc = pc + 4
            for instruction in word:
                parts = instruction.split(" ",1)
                op = parts[0]; args = parts[1].split(",") if len(parts) == 2 else []
                r = self.registers
                if op == "nop": continue
                if op == "push":
                    r[15] -= 4; self.memory[r[15]] = r[self.reg(args[0])]
                elif op == "pop":
                    r[self.reg(args[0])] = self.memory[r[15]]; r[15] += 4
                elif op == "mv": r[self.reg(args[0])] = r[self.reg(args[1])]
                elif op == "mvfc":
                    assert args[1] == "psw"; r[self.reg(args[0])] = self.psw
                elif op == "mvtc":
                    assert args[1] == "psw"; self.psw = r[self.reg(args[0])]
                elif op == "ldi": r[self.reg(args[0])] = int(args[1].lstrip("#"),0) & 0xffffffff
                elif op == "addi": r[self.reg(args[0])] = (r[self.reg(args[0])] + int(args[1].lstrip("#"),0)) & 0xffffffff
                elif op == "seth": r[self.reg(args[0])] = int(args[1].lstrip("#"),0) << 16
                elif op == "or3": r[self.reg(args[0])] = r[self.reg(args[1])] | int(args[2].lstrip("#"),0)
                elif op == "st":
                    match = re.match(r"@\((-?\d+),([a-z0-9]+)\)",",".join(args[1:]))
                    assert match, instruction
                    address = r[self.reg(match[2])] + int(match[1])
                    self.memory[address] = r[self.reg(args[0])]
                elif op in ("jl","jmp"):
                    if op == "jl": r[14] = pc + 4
                    next_pc = r[self.reg(args[0])]; break
                elif op in ("bl","bra"):
                    if op == "bl": r[14] = pc + 4
                    next_pc = int(args[0],16); break
                elif op == "bne":
                    if r[self.reg(args[0])] != r[self.reg(args[1])]:
                        next_pc = int(args[2],16); break
                elif op == "beqz":
                    if r[self.reg(args[0])] == 0:
                        next_pc = int(args[1],16); break
                else: raise AssertionError(f"unsupported bridge instruction: {instruction}")
            pc = next_pc
        raise AssertionError("bridge did not return")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build",type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.build/"manifest.json").read_text())
    symbols = {name:int(value,16) for name,value in manifest["symbols"].items()}
    model = BridgeModel((args.build/"payload-disasm.txt").read_text(),symbols)
    results = []
    foreign = {"gxr_open":0x200a40b4,"gxr_read":0x200a449c,
               "gxr_close":0x200a437c,
               "gxr_alloc":0x2005bf5c,
               "gxr_preview":0x202d6f38,"gxr_ascii":0x201d73e0,
               "gxr_language":0x201dc180,"gxr_layer_action":0x201c092c, "gxr_rpc_ready":0x2009359c,
               "gxr_rpc_limit":0x20094e2c,"gxr_thread_context":0x2005f228,
               "gxr_unit_info":0x20063f64}
    for name,target in foreign.items():
        model.execute(name,{target:("native",0xabcdef12)})
        assert model.calls == [("native",model.before[:4])]
        assert model.registers[8:14] == model.before[8:14]
        assert model.registers[14:] == model.before[14:]
        assert model.registers[0] == 0xabcdef12
        results.append({"case":name,"pass":True})
    for name,target in (("ricoh_recipe_open","rfw_open"),("ricoh_recipe_apply","rfw_apply_action")):
        model.execute(name,{symbols[target]:("gcc",16)})
        assert model.calls == [("gcc",model.before[4:8])]
        assert model.registers[8:] == model.before[8:]
        assert model.registers[0] == 16
        results.append({"case":name,"pass":True})
    # Seed original registers at the first instruction through a small subclass.
    class Seeded(BridgeModel):
        def execute(self,*a,seed=None,**kw):
            original = self.code[self.symbols[a[0]]]
            self.code[self.symbols[a[0]]] = [f"ldi r{index},#{value}" for index,value in (seed or {}).items()] + original
            try: return super().execute(*a,**kw)
            finally: self.code[self.symbols[a[0]]] = original
    seeded = Seeded((args.build/"payload-disasm.txt").read_text(),symbols)
    for letter in (21,22,23):
        for value in (0,1,65535):
            seeded.execute("rfw_rpc8_native",{0x2009005c:("native",value)},seed={0:letter,1:value})
            assert seeded.calls[0][1][0] == 8
            assert seeded.stack_calls == [[2,letter,value]]
            assert seeded.registers[0] == value
            assert seeded.registers[8:] == seeded.before[8:]
            results.append({"case":f"rpc8_native_{letter}_{value}","pass":True})
    if manifest["variant"] == "safe":
        seeded.execute("rfw_deep_ownership")
        assert seeded.registers[0] == 0 and seeded.registers[8:] == seeded.before[8:]
        results.append({"case":"target_deep_write_interlock_denies_ownership","pass":True})
    else:
        target = symbols["rfw_rpc8_preflight"]
        assert seeded.execute("rfw_deep_ownership",stops=(target,)) == target
        assert seeded.registers == seeded.before
        results.append({"case":"target_deep_enablement_tailcalls_runtime_preflight","pass":True})
    # Start at the actual native call sites. A non-Image activity must branch
    # away before even the first payload instruction, regardless of its body.
    root = Path(__file__).resolve().parents[3]
    native_lines = []
    for line in (root/"research/stage1_codespace/evidence/body-seg09.disasm.txt").read_text().splitlines():
        match = re.match(r"([0-9a-f]{8}):",line)
        if match and any(lo <= int(match[1],16) < hi for lo,hi in
                         ((0x202be244,0x202be254),(0x202bb960,0x202bb978))):
            native_lines.append(line)
    callsite_symbols = dict(symbols,fn2_callsite=0x202be244,live_callsite=0x202bb960)
    callsites = Seeded("\n".join(native_lines),callsite_symbols)
    hook_list = json.loads((args.build/"hooks.json").read_text())["hooks"]
    for hook in hook_list:
        if hook["id"] in ("fn2_no_editor","live_recipe_commit"):
            replacement = BridgeModel((root/hook["replacement_disassembly"]).read_text(),symbols)
            callsites.code.update(replacement.code)
    activities = tuple(value for value in range(256) if value != 8) + (0x80000000,0xffffffff)
    for name,register,payload_name,native_other in (
        ("fn2_callsite",1,"recipe_fn2_guard",0x202be338),
        ("live_callsite",3,"recipe_live_commit",0x202bbad8),
    ):
        payload_entry = symbols[payload_name]
        for activity in activities:
            destination = callsites.execute(name,stops=(payload_entry,native_other),seed={register:activity})
            assert destination == native_other, f"{name}: non-Image activity {activity} entered payload"
        assert callsites.execute(name,stops=(payload_entry,native_other),seed={register:8}) == payload_entry
        results.append({"case":f"{name}_native_branch_bypasses_payload","activities":len(activities),"pass":True})
    for keep_open in (0,1):
        seeded.execute("ricoh_recipe_action",{symbols["rfw_is_active"]:("gcc",1),
                                              symbols["rfw_apply_action"]:("gcc",1)},seed={4:keep_open})
        assert len(seeded.calls) == 2 and seeded.calls[1][1][0] == keep_open
        assert seeded.registers[0] == 1 and seeded.registers[8:] == seeded.before[8:]
        results.append({"case":f"action_recipe_keep_{keep_open}","pass":True})
        stop = seeded.execute("ricoh_recipe_action",{symbols["rfw_is_active"]:("gcc",0)},
                              stops=(0x202871dc,),seed={4:keep_open})
        assert stop == 0x202871dc and len(seeded.calls) == 1
        expected = seeded.before[:]; expected[4] = keep_open; expected[15] -= 4
        assert seeded.registers == expected and seeded.psw == seeded.before_psw
        assert seeded.memory[expected[15]] == seeded.before[14]
        results.append({"case":f"action_non_recipe_native_resume_keep_{keep_open}","pass":True})
    for opened in (0,1):
        stop = 0x202bcf58 if opened else 0x202bb96c
        assert seeded.execute("recipe_live_commit",{symbols["rfw_cursor_commit"]:("gcc",opened)},
                              stops=(stop,),seed={2:8,3:8}) == stop
        expected = seeded.before[:]; expected[2:4] = [8,8]
        if not opened: expected[11] = 0x20220000
        assert seeded.registers == expected
        assert seeded.psw == seeded.before_psw
        results.append({"case":f"live_commit_open_{opened}","pass":True})
    for opened in (0,1):
        stop = 0x202be6a8 if opened else 0x202be250
        assert seeded.execute("recipe_fn2_guard",{symbols["rfw_is_active"]:("gcc",opened)},
                              stops=(stop,),seed={0:8,1:8}) == stop
        assert seeded.registers[:2] == [8 if opened else 0x20260000,8]
        assert seeded.registers[2:8] == seeded.before[2:8]
        assert seeded.registers[8] == (2 if opened else seeded.before[8])
        assert seeded.registers[9:] == seeded.before[9:]
        assert seeded.psw == seeded.before_psw
        results.append({"case":f"fn2_open_{opened}","pass":True})
    assert "recipe_force_dispatch" not in symbols and "native_image_branch" not in symbols
    results.append({"case":"no_forced_adj_function_dispatch","pass":True})
    assert "recipe_layer_action" not in symbols and "recipe_layer_original" not in symbols
    assert "gxr_free" not in symbols
    results.append({"case":"no_generic_layer_interception_or_cache_free","pass":True})
    report = {"cases":len(results),"passed":True,"results":results,
              "artifact_sha256":manifest["payload_sha256"],"camera_executed":False,
              "method":"Host model of decoded linked bridge instructions; foreign bodies are stubs"}
    (args.build/"abi-tests.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"abi_cases":len(results),"pass":True}))


if __name__ == "__main__":
    main()
