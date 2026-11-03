"""Convert numbered REC text to the explicitly declared version 7 binary record."""
from pathlib import Path
import argparse,json,re,struct,sys,zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import native_gate as g

def parse(text,version):
    g.check(version==7,'unsupported_page_version');lines=text.splitlines();size=g.L['record_size']+g.L['aux_size'];pages=(size+27)//28
    g.check(len(lines)==pages*8,'page_lines_missing_or_extra');out=bytearray()
    for i in range(pages):
        row=lines[8*i:8*i+8];g.check(row[0]==f'REC {i:04X}/{pages:04X}','page_sequence_missing_or_replaced')
        g.check(all(re.fullmatch('[0-9A-F]{8}',x) for x in row[1:]),'page_word_not_fixed_hex')
        out.extend(bytes.fromhex(''.join(row[1:])))
    g.check(out[size:]==bytes(len(out)-size),'page_padding_nonzero');raw=bytes(out[:size])
    g.check(struct.unpack_from('>4I',raw)==(0x44563450,7,160,size),'page_record_identity')
    checksum=int.from_bytes(raw[16:20],'big');out=bytearray(raw);out[16:20]=bytes(4)
    g.check(zlib.crc32(out)&0xffffffff==checksum,'page_record_crc');return raw

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('pages',type=Path);p.add_argument('--version',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args(argv)
    try:
        raw=parse(a.pages.read_text(),a.version);g.check(s.allowed(a.output),'output_outside_task');a.output.parent.mkdir(exist_ok=True,parents=True);a.output.write_bytes(raw)
        print(json.dumps(dict(converted=True,version=7,bytes=len(raw),raw_sha256=g.sha(raw))));return 0
    except (ValueError,OSError,UnicodeError) as error:print(json.dumps(g.incomplete(str(error)),ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
