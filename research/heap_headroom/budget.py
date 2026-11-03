#!/usr/bin/python3
"""Recalculate heap budgets with a first-fit model of the decoded allocator."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/heap_headroom"
BEGIN = 0x20704800
END = 0x20744800
CAPACITY = END - BEGIN


def align4(n):
    return (n + 3) & ~3


class Heap:
    def __init__(self):
        self.free_blocks = [(BEGIN + 12, CAPACITY)]
        self.live = {}

    def alloc(self, request, tracked=False):
        raw_request = align4(request) + 12 if tracked else request
        if raw_request <= 0 or raw_request >= CAPACITY:
            return 0
        extent = align4(raw_request) + 12
        for index, (address, available) in enumerate(self.free_blocks):
            if available < extent:
                continue
            if available - extent >= 28:
                self.free_blocks[index] = (address + extent, available - extent)
            else:
                extent = available
                del self.free_blocks[index]
            pointer = address + (24 if tracked else 12)
            self.live[pointer] = {"header": address, "extent": extent,
                                  "request": request, "tracked": tracked}
            return pointer
        return 0

    def release(self, pointer):
        block = self.live.get(pointer)
        if block is None:
            return False
        raw_pointer = block["header"] + 12
        if raw_pointer < BEGIN or raw_pointer >= END or block["extent"] >= CAPACITY:
            return False
        del self.live[pointer]
        self.free_blocks.append((block["header"], block["extent"]))
        self.free_blocks.sort()
        merged = []
        for address, extent in self.free_blocks:
            if merged and merged[-1][0] + merged[-1][1] == address:
                old_address, old_extent = merged[-1]
                merged[-1] = (old_address, old_extent + extent)
            else:
                merged.append((address, extent))
        self.free_blocks = merged
        return True

    def summary(self):
        return {"free_extent_total": sum(s for a, s in self.free_blocks),
                "largest_free_extent": max((s for a, s in self.free_blocks), default=0),
                "free_blocks": [{"address": a, "extent": s} for a, s in self.free_blocks],
                "live_extent_total": sum(v["extent"] for v in self.live.values())}

    def loader_accepts(self, pointer):
        if not pointer or pointer not in self.live:
            return False
        block = self.live[pointer]
        return not block["tracked"] and block["extent"] < CAPACITY and (
            BEGIN <= block["header"] and block["header"] + block["extent"] <= END
            and pointer + block["request"] <= END
        )


def baseline(main_request):
    heap = Heap()
    records = []
    for label, request in [("loader_work", 608), ("main", main_request), ("ui_snapshot", 1968)]:
        pointer = heap.alloc(request)
        assert pointer and heap.loader_accepts(pointer)
        records.append({"name": label, "request": request, "pointer": pointer, **heap.live[pointer]})
    return heap, records


def main():
    checkpoint = json.loads((OUT / "checkpoint-summary.json").read_text())
    assert checkpoint["used_blocks"] == []
    assert checkpoint["largest_free_extent"] == CAPACITY
    census = json.loads((OUT / "call-census.json").read_text())
    application = [c for c in census["calls"] if c["name"] == "system_alloc"]
    assert len(application) == 12 and all(c["r4"] is not None for c in application)
    results = {}
    for request in [75124, 108124, 122192]:
        heap, records = baseline(request)
        results[str(request)] = {"allocations": records, **heap.summary()}
    isolated = []
    for call in application:
        heap, records = baseline(108124)
        before = heap.summary()
        pointer = heap.alloc(call["r4"], tracked=True)
        assert pointer
        allocated = dict(heap.live[pointer])
        after = heap.summary()
        assert heap.release(pointer) and heap.summary() == before
        isolated.append({"call": call["pc"], "request": call["r4"],
                         "extent": allocated["extent"], "remaining_extent": after["free_extent_total"],
                         "allocation_succeeded": True, "release_restored_layout": True})

    conditional = []
    scenarios = [
        ("three_event_buffers", [8560,8560,8560,16384,938,77312,4608,12368]),
        ("adjustment_and_logs", [32768,16384,938,77312,4608,12368]),
        ("adjustment_and_reader", [32768,16384,938,77312,4608,12368,32768]),
    ]
    for label, requests in scenarios:
        heap, records = baseline(108124)
        steps = []
        for request in requests:
            pointer = heap.alloc(request, tracked=True)
            steps.append({"request": request, "success": bool(pointer), **heap.summary()})
        conditional.append({"name": label, "requests": requests, "steps": steps,
                            "assumption": "These independent native objects overlap. Camera reachability is not established."})

    heap = Heap()
    arrangement = [(77312,False),(8560,True),(32768,False),(16384,True),
                   (25452,False),(938,True),(32768,True),(4608,False),(8560,True)]
    pointers = []
    for request, keep in arrangement:
        pointer = heap.alloc(request, tracked=True)
        assert pointer
        pointers.append((pointer, keep, request))
    for pointer, keep, request in pointers:
        if not keep:
            assert heap.release(pointer)
    loader_work = heap.alloc(608)
    assert loader_work and heap.loader_accepts(loader_work)
    fragmented_before = heap.summary()
    candidate_pointer = heap.alloc(108124)
    assert candidate_pointer == 0
    old_pointer = heap.alloc(75124)
    assert old_pointer and heap.loader_accepts(old_pointer)
    fragment = {"native_arrangement": [{"request": r, "held": k} for r,k in arrangement],
                "before_main": fragmented_before, "candidate_main_succeeded": False,
                "old_main_succeeded": True,
                "assumption": "Synthetic allocation history using observed sizes; no camera trace establishes this history."}

    edge = Heap()
    pointer = edge.alloc(CAPACITY-12)
    edge_result = {"request": CAPACITY-12, "allocation_succeeded": bool(pointer),
                   "loader_accepts": edge.loader_accepts(pointer), "free_accepts": edge.release(pointer),
                   "extent_end": BEGIN+12+CAPACITY, "configured_end": END}
    assert edge_result["allocation_succeeded"] and not edge_result["loader_accepts"] and not edge_result["free_accepts"]
    open_failures = []
    for main_request in [75124,108124]:
        heap, records=baseline(main_request)
        for count in range(3):
            assert heap.alloc(32768,tracked=True)
        before=heap.summary()
        large=heap.alloc(77312,tracked=True)
        open_failures.append({"main_request":main_request,"retained_file_buffers":3,
                              "before_large_request":before,"large_request":77312,
                              "large_request_succeeded":bool(large),
                              "assumption":"The adjustment reader is entered three times and each file open fails. This sequence was not run on a camera."})
    assert open_failures[0]["large_request_succeeded"] and not open_failures[1]["large_request_succeeded"]
    output = {"evidence_level": "Host arithmetic and allocator model; no CPU or camera run.",
              "main_request_delta": 33000, "baselines": results, "isolated_native_calls": isolated,
              "conditional_scenarios": conditional, "fragmented_example": fragment,
              "initial_full_extent_edge": edge_result,
              "three_file_open_failures":open_failures,
              "unconditional_camera_peak_margin": None}
    (OUT/"budget-results.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"candidate":results["108124"],"isolated_calls":len(isolated),
                      "conditional_final":[{"name":s["name"],**s["steps"][-1]} for s in conditional],
                      "fragmented":fragment},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
