"""Arithmetic for the main-request / heap section (no simulation): loader formula, field reading, and the heap_headroom scenarios recomputed for 107,760 B."""
from pathlib import Path
import json

WORK = Path(__file__).resolve().parent
POOL = 262144
span = lambda n: ((n + 3) & ~3) + 12            # block span for a direct (loader) request of n bytes
native = lambda n: ((n + 3) & ~3) + 24          # tracked native client request: extra 12 B tracking header (heap_headroom report)
def request(dat, bss):
    return 1104 + ((dat + bss + 3) & ~3) + 6144 + 256
result = {}
g135 = request(89572, 10684)
g131 = request(89556, 10684)
result['request_g135'] = g135
result['request_g131'] = g131
result['design_limit'] = 108124
result['headroom_to_design_limit'] = 108124 - g135
result['loader_ceiling'] = 122192
result['headroom_to_loader_ceiling'] = 122192 - g135
workspace, snapshot = span(608), span(1968)
main_span = span(g135)
used = workspace + main_span + snapshot
result.update(workspace_span=workspace, main_span=main_span, snapshot_span=snapshot, session_total=used, free_after_session=POOL - used)
# field reading (diag v2.1, generation 132 on a gen 121 base, 50mm): sentinel next = 0x207124DC with pool base 0x20704800
diag_request = 1104 + ((22020 + 26372 + 3) & ~3) + 6144 + 256
sentinel = 12
result['diag_request'] = diag_request
result['diag_expected_first_free'] = sentinel + workspace + span(diag_request)
result['diag_observed_first_free'] = 0x207124DC - 0x20704800
result['diag_first_free_matches_sum_of_own_blocks'] = result['diag_expected_first_free'] == result['diag_observed_first_free']
free = POOL - used
big = native(77312)
scenarios = {}
scenarios['three_leaked_32KiB_then_77312'] = dict(free=free - 3 * native(32768), needed=big, ok=free - 3 * native(32768) >= big)
scenarios['two_leaked_32KiB_then_77312'] = dict(free=free - 2 * native(32768), needed=big, ok=free - 2 * native(32768) >= big)
tight = free - (3 * native(8560) + native(16384) + native(938) + big + native(4608) + native(12368))
scenarios['heap_report_pressure_1_remaining'] = tight
tight2 = free - (native(32768) + native(16384) + native(938) + big + native(4608) + native(12368))
scenarios['heap_report_pressure_2_remaining'] = tight2
scenarios['heap_report_pressure_2_then_32KiB'] = dict(free=tight2, needed=native(32768), ok=tight2 >= native(32768))
result['scenarios'] = scenarios
(WORK / 'heap-check.json').write_text(json.dumps(result, indent=1) + '\n')
print(json.dumps(result))
