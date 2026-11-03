#!/usr/bin/python3 -I -B
"""Compile only the proposed data layouts, then recompute the design budget."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v4-r3')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbol_sizes(raw):
    assert raw[:6] == b'\x7fELF\x01\x02'
    offset = struct.unpack_from('>I', raw, 32)[0]
    entry_size, count = struct.unpack_from('>HH', raw, 46)
    entries = [struct.unpack_from('>10I', raw, offset + entry_size * i) for i in range(count)]
    found = {}
    for entry in entries:
        if entry[1] != 2:
            continue
        strings = entries[entry[6]]
        names = raw[strings[4]:strings[4] + strings[5]]
        for pos in range(entry[4], entry[4] + entry[5], entry[9]):
            name, _, size, _, _, _ = struct.unpack_from('>IIIBBH', raw, pos)
            label = names[name:].split(b'\0', 1)[0].decode()
            if label.startswith('r3_'):
                found[label] = size
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    assert output.is_relative_to(SCRATCH)
    assert Path(os.environ['TMPDIR']).resolve() == SCRATCH
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    output.mkdir(parents=True, exist_ok=True)
    gcc = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    obj = output / 'layout.o'
    command = [str(gcc), '-std=c11', '-Os', '-ffreestanding', '-fno-builtin',
               '-fno-stack-protector', '-fno-common', '-fno-pic', '-m32r',
               '-mmodel=large', '-msdata=none', '-G0', '-Wall', '-Wextra', '-Werror',
               '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
               '-I', str(ROOT / 'firmware/resident_v39/resident'),
               '-c', str(HERE / 'layout_probe.c'), '-o', str(obj)]
    built = subprocess.run(command, text=True, capture_output=True, timeout=120)
    (output / 'compiler.log').write_text(built.stdout + built.stderr)
    assert built.returncode == 0, built.stderr
    sizes = symbol_sizes(obj.read_bytes())
    expected = dict(r3_root_layout=512, r3_diag_layout=77824,
                    r3_shot_ring_layout=1728, r3_encode_save_layout=48,
                    r3_existing_session_layout=1228,
                    r3_existing_overhead_layout=7628,
                    r3_existing_ui_layout=1968)
    assert sizes == expected, sizes
    parent_cap = 108744 - 620 - 12
    default_parent_cap = parent_cap - 2*24
    rows = [dict(extension_slot=e, dat_image_cap=parent_cap - 64 - e - 16 - 7628,
                 dat_image_with_tail_budget=default_parent_cap - 64 - e - 16 - 7628,
                 dat_image_planning_cap=default_parent_cap - 64 - e - 16 - 7628 - 512)
            for e in (8192, 10240, 12288, 16384)]
    linked = json.loads((ROOT / 'firmware/engine_v59_g151/candidate/local/full-r13/layout.json').read_text())
    baseline = linked['file_bytes'] + linked['bss_bytes']
    assert baseline == linked['image_bss_bytes'] == 97776
    code_estimate, root, protection = 6440, sizes['r3_root_layout'], 24
    window = 0x20054800 - 0x2005276c
    uncertainty = ((3800 + 544) * 30 + 399) // 400 * 4
    diag_request = 20480 + sizes['r3_diag_layout'] + sizes['r3_existing_overhead_layout']
    reservations = []
    for name, reservation in [('12.25MiB', 0xc40000), ('12MiB', 0xc00000), ('512KiB', 0x80000)]:
        end = 0x87f7c000
        frame = 2144 * 2848 * 2 if reservation >= 0xc00000 else 0
        used = 0x50000 + frame
        reservations.append(dict(name=name, bytes=reservation,
                                 length_word=hex(0x076c0000 - reservation),
                                 base=hex(end - reservation), end=hex(end),
                                 frame_bytes=frame, tail_bytes=reservation - used))
    doc = dict(classification='target_layout_object_and_arithmetic_only',
               checker_sha256=digest(Path(__file__)),
               compile=dict(command=command, returncode=built.returncode,
                            compiler_sha256=digest(gcc), source_sha256=digest(HERE / 'layout_probe.c'),
                            object_sha256=digest(obj), symbols=sizes),
               window=dict(bytes=window, code_estimate=code_estimate, root=root,
                           protection=protection,
                           remainder=window-code_estimate-root-protection,
                           uncertainty_30percent=uncertainty,
                           remainder_after_uncertainty=window-code_estimate-root-protection-uncertainty),
               parent=dict(request_cap=parent_cap, ordinary_span_cap=parent_cap+12,
                           workspace_span=620, total_span_cap=108744,
                           short_tail_per_block=24, default_request_cap=default_parent_cap,
                           max_workspace_span=644, max_parent_span=108100,
                           control=64, internal_guard=16, session_state_ui=7628,
                           options=rows, actual_span_including_short_tails_required=True),
               current_g151=dict(file=linked['file_bytes'], bss=linked['bss_bytes'],
                                 image=baseline, main_request=baseline+7628,
                                 excess_over_12KiB_extension_cap=baseline-rows[2]['dat_image_cap'],
                                 excess_over_default_cap=baseline-rows[2]['dat_image_with_tail_budget'],
                                 excess_after_9480B_data_saving=baseline-9480-rows[2]['dat_image_with_tail_budget']),
               diag=dict(file_estimate=20480, bss=sizes['r3_diag_layout'],
                         fixed_overhead=sizes['r3_existing_overhead_layout'],
                         main_request_estimate=diag_request,
                         ceiling=107612, user_ceiling=108124,
                         margin=107612-diag_request,
                         read_control_bytes=65536, ui_extra_allocation=0,
                         ui_snapshot_within_existing_state=1968),
               er=reservations,
               limit='No v4 window, extension or diagnostic program was linked. G0 remains unpassed.')
    assert doc['window']['remainder'] == 1364
    assert doc['window']['remainder_after_uncertainty'] == 60
    assert diag_request == 105932
    assert default_parent_cap == 108064
    (HERE / 'layout-budget.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(target_layouts=sizes, no_tail_arithmetic_cap=parent_cap,
                          default_parent_request_cap=default_parent_cap,
                          diag_request_estimate=diag_request,
                          window_estimated_remainder=doc['window']['remainder'],
                          final_link_passed=False)))


if __name__ == '__main__':
    main()
