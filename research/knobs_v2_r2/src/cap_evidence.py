"""Classify each early stop against actual coefficient/curve saturation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hashlib
import json
import knobs as k
import support as s
from bridge import C, compare


def main():
    s.guard()
    modules = {m['name']:m for m in s.parse()}
    c = C(build=False)
    caps = json.loads((s.LOCAL/'caps.json').read_text())
    payload = bytearray()
    for cap in caps:
        m = modules[cap['unit']]
        stock, base = m['entries'][4], m['entries'][cap['slot']]
        sign, end, last = cap['direction'], abs(cap['domain_end']), abs(cap['last_dose'])
        assert cap['exhaustive_remaining_count'] == end-last and cap['remaining_best_de00'] < 1.0
        endpoint, stats = compare(c, stock, base, k.request_for(cap['param'], sign*end))
        retained, _ = compare(c, stock, base, k.request_for(cap['param'], cap['last_dose']))
        plateau = end
        for dose in range(end-1, last-1, -1):
            b, _ = c.apply(stock, base, k.request_for(cap['param'], sign*dose))
            if b != endpoint:
                break
            plateau = dose
        assert plateau < end, 'no actual endpoint plateau: ' + str(cap)
        if cap['param'] == 'saturation':
            assert stats['colour_cap'] and stats['matrix_cap'], 'Saturation has not reached physical coefficient caps'
            cap['reason'] = '颜色行幅值 127 与矩阵色度幅值 1279 的统一增益上限；8 位显示裁剪/量化使剩余变化不足一档。'
        elif cap['param'] in ('contrast', 'highlight', 'shadow'):
            assert abs(cap['domain_end']) == 16384
            cap['reason'] = '有理曲线已进入 8 位端点量化平台，并受 0≤ΔB≤ΔA 斜率约束；剩余变化不足一档。'
        else:
            raise AssertionError('unclassified early cap: ' + str(cap))
        cap.update(endpoint_plateau_start=sign*plateau,
                   endpoint_plateau_state_count=end-plateau+1,
                   retained_sha256=hashlib.sha256(retained).hexdigest(),
                   endpoint_sha256=hashlib.sha256(endpoint).hexdigest(),
                   retained_offset=len(payload), endpoint_offset=len(payload)+552,
                   endpoint_changed_bytes=sum(a!=b for a,b in zip(retained, endpoint)))
        payload.extend(retained+endpoint)
    (s.LOCAL/'caps_entries.bin').write_bytes(payload)
    s.dump(s.LOCAL/'caps.json', caps)
    print('PASS', len(caps), 'early stops: exhaustive tail below threshold, physical endpoint plateau confirmed')


if __name__ == '__main__':
    main()
