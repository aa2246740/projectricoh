#!/usr/bin/env python3
"""Independent review cases plus explicit reruns of the submitted host fixtures.

Fresh windows come from validate.py. The existing bounded CPU is a shared
dependency, not a second independent instruction implementation. No device I/O.
"""
import importlib.util
import json
from pathlib import Path
import re
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate as v

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

submitted = module("submitted_gpt_replay", v.ROOT / "research/body_v4_storage/gpt/replay.py")
base, CPU, stub = submitted.base, submitted.CPU, submitted.stub
gemini = module("submitted_gemini_replay", v.ROOT / "research/body_v4_storage/gemini/replay.py")

class Program:
    def __init__(self):
        self.name, self.image = "fresh-validation-windows", v.Image()
        self.symbols, self.code, self.width = {}, {}, {}
        for path in sorted(v.OUT.glob("*.asm.txt")):
            if ".body." in path.name:
                continue
            for line in path.read_text().splitlines():
                m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$", line)
                if not m:
                    continue
                pc, raw = int(m[1], 16), bytes.fromhex(m[2])
                assert self.image.raw(pc, len(raw)) == raw, (str(path), hex(pc))
                if len(raw) in (2, 4):
                    ops = tuple(base.native.p.Program.parse(x) for x in re.split(r" -> | \|\| ", m[3]))
                    if pc in self.code:
                        assert self.code[pc] == ops, (str(path), hex(pc))
                    self.code[pc], self.width[pc] = ops, len(raw)

    def byte(self, address):
        try:
            return self.image.raw(address, 1)[0]
        except AssertionError:
            return 0

class Blocked(Exception):
    pass

def snap(c):
    return {hex(a): c.read(a, n) for a, n in (
        (0x2056fc38, 4), (0x201bc1a8, 4), (0x201bc19c, 4), (0x201bc560, 4),
        (0x201bc1bc, 2), (0x201bc208, 1), (0x204f41e8, 1), (0x204f41ea, 1), (0x204c8668, 4))}

def completion_fixture(p):
    c = CPU(p)
    ctx, msg = 0x20640000, 0x20650000
    c.seed(msg, 48, 2)
    c.seed(msg+6, 0x1003, 2)
    c.seed(msg+12, ctx)
    for off, val in ((7, 1), (13, 1), (112, 0)):
        c.seed(ctx+off, val, 1)
    for a, val, n in ((0x2056fc38, 1, 4), (0x201bc19c, 2, 4), (0x201bc560, 1, 4),
                       (0x201bc1a8, 0, 4), (0x201bc1bc, 0, 2), (0x204f41e8, 1, 1), (0x204c8668, 0, 4)):
        c.seed(a, val, n)
    for a in (0x2015664c, 0x20171ed8, 0x20171f0c, 0x20163dd8, 0x2016c75c, 0x2005dad4):
        stub(c, a, "completion_dependency_" + hex(a))
    return c, ctx, msg

def task6_cycle(p):
    rows = []
    for full in (False, True):
        c, ctx, msg = completion_fixture(p)
        sends = []
        def send(cc):
            sends.append(dict(queue=cc.r[4], length=cc.r[6], wait=hex(cc.r[7]), snapshot=snap(cc)))
            if full:
                raise Blocked("synthetic full queue 1; task 6 is not receiving")
            return 0
        stub(c, 0x2005e034, "queue1_boundary", hook=send)
        c.call(0x20173280, (msg,))
        first = snap(c)
        assert first["0x201bc19c"] == 1 and first["0x201bc560"] == 2 and not sends
        blocked = False
        try:
            c.call(0x20173280, (msg,))
        except Blocked:
            blocked = True
        final = snap(c)
        assert sends[0]["queue"] == 1 and sends[0]["wait"] == "0xffffffff"
        assert final["0x2056fc38"] == 0 and final["0x201bc19c"] == 0
        assert final["0x201bc560"] == (2 if full else 1) and blocked == full
        rows.append(dict(case="task6_drain_queue1_cycle", queue1_full=full, first_completion=first,
                         second_completion=final, sends=sends, blocked=blocked,
                         limits="Queue full is synthetic. Actual 71674 instructions run; RTOS send is the declared boundary. Task 6 never consumes a completion in either case."))
    return rows

def one_dispatch(p, code, flags):
    c = CPU(p)
    c.seed(0x204f41e8, 1, 1)
    c.seed(0x204f41ea, flags, 1)
    received = []
    def receive(cc):
        if received:
            raise base.Stop()
        received.append(code)
        cc.seed(0x204f41ba, code, 2)
        return 48
    stub(c, 0x20109b28, "one_synthetic_message", hook=receive)
    stub(c, 0x2005ff88, "scheduler_hint")
    stub(c, 0x2010e5c8, "photo_handler_boundary", 1)
    stub(c, 0x2010e14c, "remount_boundary", 1)
    try:
        c.call(0x2010de04)
    except base.Stop:
        pass
    else:
        raise AssertionError("second receive not reached")
    return c

def flags_and_receive(p):
    rows = []
    for flag in (0x40, 0x10, 0x18, 0x50):
        c = one_dispatch(p, 0x1f03, flag)
        final = c.read(0x204f41ea, 1)
        assert final == flag & ~0x40
        assert 0x2010e064 not in c.visits and 0x2010e14c not in c.calls
        rows.append(dict(case="ordinary_message_clears_bit6_without_1f12", initial_flags=hex(flag),
                         final_flags=hex(final), opcode="0x1f03", remount_calls=0,
                         limits="Photo body and RTOS receive are stubs; real classifier, table dispatch and loop tail run."))
    c = CPU(p)
    c.seed(0x204f0cc4, 2)
    attempts = []
    def receive(cc):
        attempts.append(list(cc.r[4:7]))
        return -50 if len(attempts) == 1 else 48
    stub(c, 0x2005e078, "receive_timeout_then_message", hook=receive)
    ret = c.call(0x20109b28, (0x20650000, 0x8ca0))
    assert ret == 48 and len(attempts) == 2
    rows.append(dict(case="receive_negative_is_retried_inside_wrapper", calls=attempts, result=ret,
                     limits="Timeout result injected; no elapsed time or RTOS scheduling replayed."))
    for state in (0, 1, 2):
        c = CPU(p)
        c.seed(0x204f41e8, state, 1)
        c.seed(0x204f41ea, 0, 1)
        c.call(0x2010a558)
        c.call(0x2010a534)
        assert c.read(0x204f41ea, 1) == (0x18 if state == 2 else 0)
        rows.append(dict(case="control_requests_do_not_send_card_message", state=state,
                         flags=hex(c.read(0x204f41ea, 1)), calls=[hex(x) for x in c.calls],
                         limits="Equality of 41D0/41D4 and zeroed control state are synthetic. No queue send occurs."))
    return rows

def delay_cases(p):
    rows = []
    for task in (6, 8):
        for value in (10, 1000):
            c = CPU(p)
            c.psw = 0xc1
            called = []
            stub(c, 0x0500c6ec, "context_check", 0)
            stub(c, 0x0500c550, "delay_trap_boundary", hook=lambda cc: (called.append(cc.r[4]), 0)[1])
            ret = c.call(0x2005de00, (value,))
            assert ret == 0 and called == [value]
            k = base.fixture(p, task)
            base.run_until(k, 0x050055cc, [0x0500c784], regs={4:value})
            timeout = k.read(0x200d2224+4*(task-1))
            task_state = k.read(0x200d2594+4*(task-1))
            assert timeout == value+1 and task_state == 2
            rows.append(dict(case="delay_schedules_current_task", task=task, input=value,
                             timeout_slot=timeout, task_wait_state=task_state, service=80,
                             kernel_target="0x050055cc", limits="Synthetic valid task frame. Stops before scheduler; no timer interrupt, wall-clock duration or queue consumption."))
    for psw in (0, 0x80):
        c = CPU(p)
        c.psw = psw
        ret = c.call(0x2005de00, (10,))
        assert ret == -28
        rows.append(dict(case="delay_rejects_wrong_psw_context", psw=hex(psw), result=ret))
    return rows

def io_direction(p):
    rows = []
    for entry, native, mode in ((0x200a449c, 0x200aad38, 2), (0x200a46f0, 0x200aba64, 2)):
        c = CPU(p)
        fd, cache, out = 0, 0x204c86ec, 0x20650000
        c.seed(cache+2, 1, 2)
        c.seed(cache+4, out)
        c.seed(cache+8, 0)
        c.seed(cache+12, 0)
        stub(c, 0x0500d4e4, "semaphore_wait")
        stub(c, 0x0500d4fc, "semaphore_signal")
        def read_boundary(cc):
            for i in range(cc.r[6]): cc.seed(cc.r[5]+i, 0x5a, 1)
            return cc.r[6]
        stub(c, native, "native_read_boundary", hook=read_boundary)
        ret = c.call(entry, (fd, out, 1))
        assert ret == 1 and c.read(out, 1) == 0x5a and c.read(cache, 2) == mode
        assert not any(a in c.calls for a in (0x200ab02c, 0x200ac020))
        rows.append(dict(case="mode2_functions_are_reads", entry=hex(entry), mode=mode, result=ret,
                         destination_byte=c.read(out, 1), trace=c.trace,
                         limits="Read content is supplied by the named native read boundary; no media."))
    return rows

def producer_handshake(p):
    rows = []
    for producer in ("jpeg", "raw"):
        for flag in (0, 1, 0x10, 0xff, 0x22):
            c = CPU(p)
            ctx = 0x20640000
            c.seed(ctx+7, 1, 1)
            c.seed(ctx+13, 1, 1)
            c.seed(0x201bc208, flag, 1)
            c.r[8] = c.r[9] = ctx
            stop_at = 0x20155970 if producer == "jpeg" else 0x20157020
            c.stubs[stop_at] = lambda cc: (_ for _ in ()).throw(base.Stop())
            def delay(cc):
                raise Blocked("producer waits for another producer tag")
            c.stubs[0x2005de00] = delay
            blocked = False
            try:
                c.call(0x20155934 if producer == "jpeg" else 0x20156fe0, bound=1000)
            except base.Stop:
                pass
            except Blocked:
                blocked = True
            expected = ((flag & 0xf) != 0 and flag != 0xff) if producer == "jpeg" else ((flag & 0xf0) != 0)
            assert blocked == expected and c.read(0x201bc208, 1) == flag
            rows.append(dict(case="producer_tag_nibble_wait", producer=producer, tag=hex(flag),
                             waits=blocked, limits="Only the real conditional/wait fragment runs. Stop/delay are explicit boundaries; no consumer or scheduler."))
    c, ctx, msg = completion_fixture(p)
    stub(c, 0x2005e034, "queue1_has_space")
    c.call(0x20173280, (msg,))
    other = ctx+0x1000
    for off, value in ((7, 1), (13, 1), (112, 0)):
        c.seed(other+off, value, 1)
    c.seed(msg+12, other)
    c.call(0x20173280, (msg,))
    assert c.read(0x201bc560) == 1 and 0x20171674 in c.visits
    rows.append(dict(case="pair_counter_accepts_different_second_object", first_object=hex(ctx),
                     second_object=hex(other), final=snap(c), trace=c.trace,
                     limits="Different-object fixture reachability on camera is unknown; proves no identity comparison at this branch."))
    return rows

def main():
    v.preflight()
    p = Program()
    reruns = []
    for f in (submitted.classifier, submitted.dispatcher, submitted.builders, submitted.pair_completion,
              submitted.completion_routes, submitted.close_paths):
        rows = f(p)
        reruns.extend(rows)
    v.save("submitted-gpt-rerun.json", dict(cases=len(reruns), rows=reruns,
            limits="Original fixtures rerun using independently extracted windows and the shared bounded interpreter."))
    gs = {}
    for f in (gemini.test_task8_opcode_mapping_and_handlers, gemini.test_raw_jpeg_lifecycle,
              gemini.test_handle_quota_and_dirty_close, gemini.test_task8_resident_bridge_dispatch):
        gs[f.__name__] = f(p)
    v.save("submitted-gemini-rerun.json", gs)
    rows = task6_cycle(p) + flags_and_receive(p) + delay_cases(p) + io_direction(p) + producer_handshake(p)
    v.save("independent-replay.json", dict(status="PASS_BOUNDED_REVIEW_CASES", cases=len(rows), rows=rows,
           limits=["No camera, media, RTOS execution or real elapsed time.",
                   "Queue capacity and OS boundaries explicitly injected. Queue saturation reachability remains unknown.",
                   "CPU implementation is shared with prior reports; fresh fixtures do not independently validate the ISA interpreter."]))
    print(json.dumps(dict(status="PASS_BOUNDED_REVIEW_CASES", independent_cases=len(rows),
                          gpt_rerun_cases=len(reruns), gemini_rerun_groups=len(gs))))

if __name__ == "__main__":
    try:
        main()
    except Exception:
        v.OUT.mkdir(exist_ok=True)
        n = len(list(v.OUT.glob("replay-failure-*.txt"))) + 1
        (v.OUT / ("replay-failure-"+str(n)+".txt")).write_text(traceback.format_exc())
        raise
