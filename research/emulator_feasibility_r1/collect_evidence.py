#!/usr/bin/env python3
"""Extract cited official instruction windows with independent file offsets."""
import json
from pathlib import Path
import re
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
WINDOWS={
    'main_entry':(0x2004b000,0x2004b0c4),
    'boot_serial_wait':(0x2004b15c,0x2004b2d8),
    'boot_gpio':(0x2004d98c,0x2004da38),
    'nand_ports':(0x20050a08,0x20050bb4),
    'application_entry':(0x20055000,0x20055190),
    'tick_setup':(0x20055488,0x20055524),
    'rtos_irq':(0x05000ee4,0x05000f70),
    'tick_api':(0x2005f164,0x2005f190),
    'tick_trap':(0x0500c584,0x0500c594),
    'module_initializers':(0x2005c1d8,0x2005c320),
    'heap':(0x2005bf00,0x2005c1d8),
    'dmac':(0x20071878,0x200718b8),
    'sd_entry':(0x200a3568,0x200a35d0),
    'sd_setup':(0x20055b74,0x20055cc4),
    'hsp_device62':(0x20074964,0x20074a8c),
    'unit_open62':(0x2009384c,0x20093948),
    'unit_handshake':(0x20063798,0x20063894),
    'i2c':(0x20074a90,0x20074d9c),
    'rtc':(0x20076374,0x20076450),
    'menu_constructor':(0x20287080,0x202871e4),
    'menu_common':(0x2028579c,0x202858d0),
    'view_reset':(0x201c06f4,0x201c0740),
    'view_push':(0x201c07e0,0x201c08f4),
    'render_descriptor':(0x201fdd10,0x201fdd70),
    'render_label':(0x201fe3e0,0x201fe488),
    'render_geometry':(0x201d709c,0x201d7150),
    'lcd_debug_names':(0x203b4734,0x203b4790),
    'display_hardware_candidate':(0x203dad0c,0x203dadb0),
    'capture_h40':(0x2015f9b0,0x2015f9ec),
    'jpeg_dma':(0x203f2150,0x203f22a0),
    'cache_control':(0x2004bab8,0x2004bae4),
}


def main():
    raw=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    sections=[struct.unpack_from('>5I',raw,0x20+i*20) for i in range(16)]
    rows={}
    for p in sorted((HERE/'local/static').glob('section-*.disasm.txt')):
        for m in re.finditer(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$',p.read_text(),re.M):
            pc=int(m[1],16)
            if any(lo<=pc<hi for lo,hi in WINDOWS.values()):
                sec=next(s for s in sections if s[1]<=pc<s[1]+s[2])
                off=sec[0]+512+pc-sec[1]
                data=bytes.fromhex(m[2])
                assert raw[off:off+len(data)]==data
                rows[pc]={'pc':hex(pc),'file_offset':hex(off),'bytes':data.hex(),'assembly':m[3]}
    out=HERE/'local/evidence';out.mkdir(exist_ok=True)
    index={}
    for name,(lo,hi) in WINDOWS.items():
        selected=[v for k,v in sorted(rows.items()) if lo<=k<hi]
        assert selected,name
        (out/(name+'.txt')).write_text('Official ilaunch3; all instruction bytes checked against frozen input.\n'+
            '\n'.join(f"{r['pc']} file {r['file_offset']} {r['bytes']} {r['assembly']}" for r in selected)+'\n')
        index[name]={'start':hex(lo),'end_exclusive':hex(hi),'rows':len(selected),
                     'file_offset':selected[0]['file_offset'],'path':'local/evidence/'+name+'.txt'}
    (HERE/'local/evidence_index.json').write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps({'byte_checked_windows':len(index),'instruction_rows':len(rows)}))


if __name__=='__main__':main()
