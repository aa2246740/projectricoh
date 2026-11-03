#!/usr/bin/env python3
"""Decode transcribed or already-OCRed menu text. Reads text, never a camera."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys
import zlib

KINDS = {'L': 1, 'N': 2, 'V': 3}
EPOCHS = 'boot heap link unit sd irom view settings mode segment power io'.split()
COMMON = 'sticky valid last_stage last_status last_native last_detail mark dropped gaps ring_first ring_last nonce'.split()
SCHEMAS = {
    ('L', 2): 'state replica status native actual_bytes crc32 close_status close_native reference_bytes reference_crc32 sd_before sd_after'.split(),
    ('L', 3): 'allocations lease address bytes nonce baseline_crc32 observed_crc32 canary_bad baseline_code_crc32 observed_code_crc32 checks attempted'.split(),
    ('L', 4): 'h15_pre h16_pre h17_pre h17_post h17_a h17_b h18_pre h18_post h18_a h18_b session witness_republish'.split(),
    ('N', 2): 'id0 id1 id2 id3 sd_epoch previous_sd_epoch id_changes same_id_new_epoch status native h22_pre h22_post'.split(),
    ('N', 3): 'name0 name1 main_cmp valid unit_epoch link_epoch rx_sequence changes same_name_reconnects status native h21_pre'.split(),
    ('N', 4): 'sequence logical_event source edge activity native_state part tag top_tag top_state count view_epoch'.split(),
    ('N', 5): 'h10_pre h06_pre h11_pre h12_pre h13_pre h14_pre h19_pre h20_pre h20_post h20_b input_valid_fields draft_panel'.split(),
    ('V', 2): 'raw_6dd raw_6de signed_6dd signed_6de previous_6dd previous_6de changes settings_epoch status native axis_order wb_enable'.split(),
    ('V', 3): 'h37_pre h37_post h37_a h37_b valid_fields sequence apply_sequence stage native rows_verified s_published preview_sequence'.split(),
    ('V', 4): 'write_driver_enabled manual_wb_driver_enabled rows_without_driver frame_completion reserved0 reserved1 reserved2 reserved3 reserved4 reserved5 reserved6 reserved7'.split(),
    ('V', 5): ['draft'+str(i) for i in range(6)]+['reserved'+str(i) for i in range(6)],
}
CAPACITY_SCHEMA = 'state maximum_bytes attempted_mask allocated_mask freed_mask measured_session measured_sample boot_epoch heap_epoch alloc_codes free_codes witness_bytes'.split()
CAPACITY_NATIVE_SCHEMA = [f'alloc_native_{i}' for i in range(5)]+[f'free_header_detail_{i}' for i in range(5)]+['state','maximum_bytes']
CAPACITY_STAGES = ['首次菜单', '回放之后', '睡眠唤醒之后']
STICKY = {1: 'HEAP_LOST', 2: 'ROOT_NEW', 4: 'DATA_BAD', 8: 'CODE_BAD',
          16: 'CANARY_BAD', 32: 'RING_DROPPED', 64: 'SEQUENCE_GAP',
          128: 'BINDING_CHANGED', 256: 'COUNTER_END', 512: 'BAD_REPLY', 1024:'CAPACITY_BAD'}
TOKEN = re.compile(r'(?<![A-Z0-9])([LNV])([A-Z0-9]{2})\s+([A-Z0-9]{8})(?![A-Z0-9])', re.I)


def signed(value):
    return value if value < 0x80000000 else value-0x100000000


def decode_frame(prefix, rows, partial=False):
    missing = [i for i in range(16) if i not in rows]
    if missing and not partial:
        raise ValueError('缺行: '+', '.join(prefix+f'{i:02X}' for i in missing))
    result = dict(engine=prefix, verified=False, missing=[f'{i:02X}' for i in missing],
                  words={f'{i:02X}':f'{w:08X}' for i, w in sorted(rows.items())})
    if 0 not in rows:
        result['notes'] = ['缺页头，只保留原始字，不能判定页号或结果。']
        return result
    h = rows[0]
    version, kind, page, flags = h>>24, (h>>16)&255, (h>>8)&255, h&255
    if version != 1 or kind != KINDS[prefix] or page >= (17 if prefix == 'L' else 12) or flags & ~31:
        raise ValueError('页头、引擎标识、页号或 flags 无效')
    result.update(protocol=version, page=page, flags=flags,
                  sample=rows.get(1), session=rows.get(2))
    if not missing:
        expected = zlib.crc32(struct.pack('>15I', *(rows[i] for i in range(15))))
        if rows[15] != expected:
            raise ValueError(f'整页 CRC 不符: 抄录={rows[15]:08X}, 计算={expected:08X}')
        result['verified'] = True
    if page == 0:
        names = COMMON
    elif page == 1:
        names = EPOCHS
    elif prefix == 'L' and 5 <= page <= 7:
        names = CAPACITY_SCHEMA
    elif prefix == 'L' and 14 <= page <= 16:
        names = CAPACITY_NATIVE_SCHEMA
    elif (prefix == 'L' and 8 <= page <= 13) or (prefix != 'L' and page >= 6):
        names = [f'event{i}_{field}' for i in range(3) for field in ('sequence', 'hook_phase', 'a', 'b')]
    else:
        names = SCHEMAS.get((prefix, page), [f'reserved{i}' for i in range(12)])
    fields = {name:rows[i+3] for i, name in enumerate(names) if i+3 in rows}
    result['fields'] = fields
    result['signed_fields'] = {k:signed(v) for k, v in fields.items()
                               if k in ('status', 'native', 'close_status', 'close_native', 'last_status', 'last_native')
                               or k.startswith('signed_') or k.startswith('draft')
                               or k.startswith('alloc_native_') }
    notes = ['CRC 只检查抄录完整性，不代表探针通过或相机安全。']
    if page == 0 and 'sticky' in fields:
        result['sticky_reasons'] = [text for bit, text in STICKY.items() if fields['sticky'] & bit]
    if prefix == 'L' and page == 2:
        states = {0:'未读', 1:'读取中', 2:'参考长度和 CRC 匹配，且读到 EOF、关闭成功',
                  3:'读到 EOF，但没有可信参考值，不能报 IROM 校验通过', 4:'失败'}
        result['irom_result'] = states.get(fields.get('state'), '未知状态')
        notes.append('源对象由探针固定为 IROM A 或 B；当前记录媒体没有 ABI 读接口，须由人工观察。')
    if prefix == 'L' and page == 3:
        notes.append('同一 sample/session 下检查 allocations=1、CRC、canary 和 sticky；不能仅凭地址相同判断保持。')
    if prefix == 'L' and page == 4:
        notes.append('loader 栈见证重新发布仍为 UNKNOWN，hook 计数不能单独证明段重载覆盖。')
    if prefix == 'L' and 5 <= page <= 7:
        result['capacity_stage'] = CAPACITY_STAGES[page-5]
        result['largest_successful_tier_kib'] = fields.get('maximum_bytes', 0)//1024
        outcomes = []
        for i, kib in enumerate((64,48,40,32,16)):
            a = (fields.get('alloc_codes', 0xeeeeeeee)>>(4*i))&15
            f = (fields.get('free_codes', 0xeeeeeeee)>>(4*i))&15
            outcomes.append(dict(kib=kib, alloc_status=-a if a<=12 else None,
                                 free_status=-f if f<=12 else None))
        result['capacity_attempts'] = outcomes
        mask = fields.get('allocated_mask', 0)
        expected_max = max((kib*1024 for i,kib in enumerate((64,48,40,32,16)) if mask&(1<<i)), default=0)
        coherent_codes = all((a['alloc_status']==0 and a['free_status']==0) if mask&(1<<i)
                             else (a['alloc_status'] not in (None,0) and a['free_status'] is None)
                             for i,a in enumerate(outcomes))
        result['capacity_complete'] = (result['verified'] and fields.get('state')==2 and fields.get('attempted_mask')==31
                                       and fields.get('allocated_mask')==fields.get('freed_mask')
                                       and mask&~31==0 and fields.get('maximum_bytes')==expected_max
                                       and coherent_codes and fields.get('measured_session')==result['session'])
        notes.append('只试五个档位，64 KiB 成功表示至少该档可分配；不表示绝对最大值。仅对三项都完成的同一会话比较。')
        notes.append('服务不支持、参数或权限错误不能解释成内存不足；原始 native 返回在 LIFE 页 14..16。48 KiB 文件还需加 BSS 和 loader 分配开销。')
    if prefix == 'N' and page == 2 and all('id'+str(i) in fields for i in range(4)):
        result['sd_id_hex'] = ''.join(f'{fields["id"+str(i)]:08X}' for i in range(4))
        notes.append('缓存非零不等于插拔通知完整；结合 sd_epoch、H22 pre/post 和原生操作记录。')
    if prefix == 'N' and page == 3 and 'name0' in fields and 'name1' in fields:
        name = struct.pack('>2I', fields['name0'], fields['name1'])
        result['unit_name_hex'] = name.hex().upper()
        result['unit_name_ascii'] = name.rstrip(b'\0').decode('ascii', errors='backslashreplace')
    if prefix == 'N' and page == 4:
        notes.append('source/edge 的有效位和语义来自 resident 复制的消息合同；不把 0x25/0x22 预先命名为某个物理键。')
    if prefix == 'V' and page == 2:
        notes.append('0x6DD/0x6DE 各自 raw 1..17、signed=raw-9；AB/GM 轴次序、正方向和使能条件均为 UNKNOWN。')
    if prefix == 'V' and page in (3, 4):
        notes.append('只观察 H37 和另行接入的阶段记录；探针不请求 preview，不发 RPC，不证明下一帧已变化。')
    if missing:
        notes.insert(0, '部分抄录未验 CRC，只能查看原始字段。')
    result['notes'] = notes
    return result


def decode_text(text, partial=False, ocr=False):
    results, rows = [], {}
    prefix = None
    corrections = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for match in TOKEN.finditer(line):
            letter, index, word = [x.upper() for x in match.groups()]
            if ocr:
                table = str.maketrans({'O':'0', 'I':'1', 'L':'1'})
                fixed = index.translate(table), word.translate(table)
                if fixed != (index, word):
                    corrections.append(dict(line=line_number, before=index+' '+word, after=' '.join(fixed)))
                index, word = fixed
            if not re.fullmatch('[0-9A-F]{2}', index) or not re.fullmatch('[0-9A-F]{8}', word):
                raise ValueError(f'第 {line_number} 行包含非十六进制字符；核对照片或显式使用 --ocr')
            i, value = int(index, 16), int(word, 16)
            if i > 15:
                raise ValueError(f'第 {line_number} 行的行号超出 00..0F')
            if i == 0 and 0 in rows:
                results.append(decode_frame(prefix, rows, partial))
                rows = {}
            if rows and letter != prefix:
                raise ValueError(f'第 {line_number} 行混入另一个引擎')
            if i in rows:
                raise ValueError(f'第 {line_number} 行重复了 {letter}{i:02X}')
            prefix = letter
            rows[i] = value
    if rows:
        results.append(decode_frame(prefix, rows, partial))
    if not results:
        raise ValueError('未找到探针行，例如 L00 01010003')
    groups = {}
    for capture in results:
        if capture.get('verified') and capture['engine']=='L' and 5<=capture.get('page',-1)<=7:
            groups.setdefault(capture['session'], {})[capture['page']-5]=capture
    capacity = []
    for session, phases in groups.items():
        complete = len(phases)==3 and all(c.get('capacity_complete') for c in phases.values())
        conditions = {(c['fields'].get('measured_session'),c['fields'].get('boot_epoch'),
                       c['fields'].get('heap_epoch'),c['fields'].get('witness_bytes')) for c in phases.values()}
        complete = complete and len(conditions)==1
        capacity.append(dict(session=session, all_three_complete=complete,
                             minimum_successful_tier_kib=min(c['largest_successful_tier_kib'] for c in phases.values()) if complete else None,
                             file_plus_bss_accepted=False,
                             note='这是最大成功档位的三时机下限，未验最终容器，也未给出 BSS 预算。'))
    return dict(captures=results, ocr_corrections=corrections, heap_capacity=capacity)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('text', nargs='?', default='-', help='抄录或 OCR 文字文件，- 表示标准输入')
    parser.add_argument('--ocr', action='store_true', help='显式修正数值区中的 O/I/L，并仍校验 CRC')
    parser.add_argument('--partial', action='store_true', help='允许缺行，但 verified 保持 false')
    args = parser.parse_args()
    text = sys.stdin.read() if args.text == '-' else Path(args.text).read_text(encoding='utf-8')
    try:
        result = decode_text(text, args.partial, args.ocr)
    except ValueError as e:
        parser.exit(2, f'解码失败: {e}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
