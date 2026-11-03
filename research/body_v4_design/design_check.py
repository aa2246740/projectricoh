#!/usr/bin/env python3
"""Check byte accounting and design data; does not test firmware behavior."""
from pathlib import Path
import importlib.util
import json
import struct

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("body_v4_collect", HERE / "collect.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def main():
    c.preflight()
    inv = json.loads((HERE / "local/resident-inventory.json").read_text())
    b = json.loads((HERE / "budget.json").read_text())
    hooks = json.loads((HERE / "hook-catalog.json").read_text())
    anchors = json.loads((HERE / "hook-anchors.json").read_text())
    abi = json.loads((HERE / "abi-layout.json").read_text())
    for name in ("envelope", "event", "reply", "api_header", "service_descriptor", "root"):
        layout = abi[name]
        occupied = set()
        for field, offset, amount in layout["fields"]:
            assert offset >= 0 and amount > 0 and offset+amount <= layout["bytes"], (name, field)
            cells = set(range(offset, offset+amount))
            assert not occupied & cells, ("overlapping design fields", name, field)
            occupied |= cells
        assert occupied == set(range(layout["bytes"])), ("unaccounted design bytes", name)
    assert abi["root"]["bytes"] == b["root_bytes"]
    assert len(abi["entries"]) == 16 and len(abi["capabilities"]) == 14
    assert len({s["id"] for s in abi["services"]}) == 8
    assert sum(inv["linked_objects"].values()) + inv["linker_padding"] == inv["payload_bytes"] == 7884
    assert inv["payload_bytes"] + inv["root_bytes"] + inv["physical_gap"] == 8340
    assert inv["additional_bytes"] == 0 and inv["payload_matches_body"]
    assert len(hooks) == len({h["id"] for h in hooks}) == 32
    assert {f for h in hooks for f in h["features"]} == set(range(1, 9))
    assert b["physical_hook_slots"] >= len(hooks)
    assert {h["id"] for h in hooks} == {a["id"] for a in anchors}
    assert sum(h["kind"] == "existing" for h in hooks) == 7
    target = sum(r["target"] for r in b["rows"])
    high = sum(r["high"] for r in b["rows"])
    results = {}
    for name, payload in (("target", target), ("high", high)):
        physical = b["window_bytes"] - payload - b["root_bytes"]
        results[name] = dict(payload_bytes=payload, root_bytes=b["root_bytes"],
                             code_end=hex(int(b["window_start"], 16) + payload),
                             physical_gap=physical, mandatory_reserve=b["mandatory_reserve"],
                             additional_bytes=physical-b["mandatory_reserve"],
                             meets_200B_gate=physical >= b["mandatory_reserve"])
    assert results["target"]["meets_200B_gate"]
    assert not results["high"]["meets_200B_gate"], "high estimate intentionally exposes fit risk"
    assert results["target"]["additional_bytes"] == 108
    assert 36*32+104+96 <= next(r["target"] for r in b["rows"] if r["id"] == "hook_thunks_metadata")
    dats = []
    for generation in (117, 121, 122, 123):
        p = c.ROOT / f"firmware/package_v36_g{generation}/SD_ROOT/GXRCE.DAT"
        raw = p.read_bytes()
        u32 = lambda off: struct.unpack_from(">I", raw, off)[0]
        assert u32(16) == len(raw) and u32(28) == generation
        dats.append(dict(generation=generation, path=str(p.relative_to(c.ROOT)), sha256=c.sha(p),
                         file_bytes=len(raw), engine_bytes=u32(136), bss_bytes=u32(116),
                         remaining_v3_engine_bytes=65536-u32(136)))
    de = b["dat_estimates"]
    estimate = sum(de[k] for k in ("baseline_gen123_engine_bytes", "moved_policy_bytes",
                                  "storage_backend_bytes", "grain_bytes", "optional_render_bytes"))
    result = dict(status="PASS_STATIC_DESIGN_CONSISTENCY_ONLY", resident_v36=inv,
                  budget=results, located_addresses=sum(h["address"] is not None for h in hooks),
                  unresolved_address_contracts=[h["id"] for h in hooks if h["address"] is None],
                  enumerated_contracts=len(hooks), budgeted_physical_sites=b["physical_hook_slots"],
                  unassigned_site_budget=b["physical_hook_slots"]-len(hooks),
                  dat_inputs=dats, dat_engine_nominal_estimate=estimate,
                  dat_engine_ceiling=de["default_code_ceiling"],
                  dat_engine_remaining_nominal=de["default_code_ceiling"]-estimate,
                  abi_layout="PASS_DESIGN_BYTE_LAYOUT_ONLY",
                  firmware_implementation="NOT_RUN_DESIGN_ONLY", camera="NOT_RUN", card="NOT_RUN",
                  full_hook_closure="INCOMPLETE", worst_case_size_proof="INCOMPLETE")
    (HERE / "budget-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    (HERE / "local/design-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "budget": results,
                      "dat_engine_nominal_estimate": estimate,
                      "unresolved_address_contracts": result["unresolved_address_contracts"]}, indent=2))


if __name__ == "__main__":
    main()
