"""Decode transcribed D00..D0F rows, requiring the complete screen CRC."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys
import zlib

TIERS=(96,88,80,72,64,56,48,40,32,24,16)
GATE={0:'OK',1:'ARGUMENT',2:'LENGTH',3:'VERSION',4:'FLAGS',5:'CRC',6:'LAYOUT',
      7:'BODY_ID',8:'RESIDENT_ID',15:'RELOCATION',128:'REOPEN_IO',255:'UNKNOWN'}
PIN={0:'MATCH',1:'MISMATCH',2:'UNIT_UNKNOWN',3:'MAP_OR_POOL_LAYOUT',4:'READ_OR_BOUNDS',5:'GATE_NOT_PASSED'}


def decode(text):
    rows={}
    for m in re.finditer(r'(?im)\bD([0-9a-f]{2})\s+([0-9a-f]{8})\b',text):
        i=int(m[1],16);value=int(m[2],16)
        if i>15:raise ValueError(f'未知行 D{i:02X}')
        if i in rows and rows[i]!=value:raise ValueError(f'D{i:02X} 重复且内容不同')
        rows[i]=value
    missing=[f'D{i:02X}' for i in range(16) if i not in rows]
    if missing:raise ValueError('缺少行: '+', '.join(missing))
    w=[rows[i] for i in range(16)]
    if w[0]!=0xD1320101:raise ValueError('DIAG 协议版本不匹配')
    if zlib.crc32(struct.pack('>15I',*w[:15]))!=w[15]:raise ValueError('屏幕 CRC 不符，请核对抄录文字')
    allocated=[n for i,n in enumerate(TIERS) if w[1]>>i&1]
    freed=[n for i,n in enumerate(TIERS) if w[1]>>(i+11)&1]
    unit=struct.pack('>2I',w[5],w[6]).rstrip(b'\0').decode('ascii',errors='backslashreplace')
    fault=(w[13]>>16);fault=fault-65536 if fault&32768 else fault
    raw_open=w[11]&65535;raw_open=raw_open-65536 if raw_open&32768 else raw_open
    tweak_codes=[w[11]>>shift&127 for shift in (23,16)]
    tweak_codes=[n-128 if n&64 else n for n in tweak_codes]
    result=dict(protocol=1,screen_crc='PASS',heap=dict(
        allocated_KiB=allocated,freed_KiB=freed,max_success_KiB=max(allocated,default=0),
        bad_header=bool(w[1]>>24&1),free_not_confirmed=bool(w[1]>>25&1),
        full_exact_allocated=bool(w[1]>>22&1),full_exact_freed=bool(w[1]>>23&1),
        full_main_request=w[10],probe_context='DIAG 主块和加载工作区仍占堆；不是刷入 full 前的堆快照'),
        file=dict(path='/ATA1/GXRCF.DAT',io_code=w[2]>>24,open_raw_low16=raw_open,
        bytes=w[3],crc32=f'{w[4]:08x}',crc_scope='whole file' if w[2]>>24 in (0,4) else 'read prefix only',
        header_gate=GATE.get(w[2]>>16&255,str(w[2]>>16&255)),
        outer_gate=GATE.get(w[2]>>8&255,str(w[2]>>8&255))),
        unit=dict(name=unit,main=f'{w[7]>>16:04x}',cmp=f'{w[7]&65535:04x}',
        candidate_map_stock_pin=PIN.get(w[2]&255,str(w[2]&255)),
        observed_crc=f'{w[8]:08x}',expected_resident_crc=f'{w[9]:08x}'),
        tweak_files=dict(A_open_raw_signed7=tweak_codes[0],B_open_raw_signed7=tweak_codes[1],
        unknown_sentinel=-64,close_failed_sentinel=-63,
        contract='-1 在产品服务中是 RV_IO，只有 -2 才会触发缺文件默认值；负值本身不证明 ENOENT'),
        T=dict(status='SKIPPED' if w[11]>>30==1 else 'UNKNOWN',
        reason='X 会改变单元全局地址游标，缺少与原生任务互斥和恢复游标的证据；DIAG 不发任何 RPC'),
        root=dict(state=w[12]>>24,flags=w[12]>>16&255,inflight=w[12]>>8&255,
        version=w[12]&255,fault=fault,check_failure=w[13]&65535,
        event_head_saturated16=w[14]>>16,dropped_saturated16=w[14]&65535,
        per_reason_counters='resident_v32 没有此字段；这里仅为 DIAG 本次开机状态'))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('text',nargs='?',help='照片中抄录的 16 行 ASCII；省略则读标准输入')
    args=parser.parse_args()
    try:print(json.dumps(decode(Path(args.text).read_text() if args.text else sys.stdin.read()),ensure_ascii=False,indent=2))
    except ValueError as e:parser.exit(2,str(e)+'\n')


if __name__=='__main__':main()
