"""Run a-h on shipped body/resident/engine instructions; only device edges are models."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import traceback
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "local/integration"
sys.path.insert(0, str(HERE))
import native_binding as v
fr, pe = v.fr, v.pe
R = pe.ROOT_ADDR
u16 = lambda b, o: int.from_bytes(b[o:o+2], "big")
u32 = lambda b, o: int.from_bytes(b[o:o+4], "big")
sha = lambda b: hashlib.sha256(b).hexdigest()
DAT = ROOT / "firmware/package_v36_g117/SD_ROOT/GXRCE.DAT"
OLD117 = ROOT / "firmware/package_v35_g117/SD_ROOT/GXRCE.DAT"
OLD115 = ROOT / "firmware/engine_v36_r28/candidate/local/full-r13/GXRCE.DAT"
INDEX = {"50mm": 0, "28mm": 1, "mount": 2}
FS_SETUP = {}
ALL_PRODUCTS = []


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


class Files:
    def __init__(self, dat):
        self.dat = dat
        self.paths = dict(FS_SETUP)
        self.live = {}
        self.next_fd = 3
        self.log = []
        self.present = "/ATA1/GXRCE.DAT" in self.paths

    def open(self, path):
        self.log.append(path)
        if (path.startswith("/ATA1/") and not self.present) or path not in self.paths:
            return -1
        fd = self.next_fd; self.next_fd += 1
        self.live[fd] = [path, 0]
        return fd

    def read(self, fd, buf, n, h):
        if fd not in self.live or n < 0:
            return -1
        path, pos = self.live[fd]
        if path.startswith("/ATA1/") and not self.present:
            return -1
        chunk = self.paths[path][pos:pos+n]
        if chunk and buf:
            h.b.write(buf, chunk)
        self.live[fd][1] += len(chunk)
        return len(chunk)

    def close(self, fd):
        self.live.pop(fd, None)
        return 0


class Product(pe.Product):
    def _install(self):
        super()._install()
        def opened(b):
            path = pe.cstr(self.h, b.get_reg("r4"))
            flags = b.get_reg("r5")
            fd = self.files.open(path)
            self.native_log.append(dict(op="open", path=path, flags=flags, fd=fd))
            return fd
        self.h.b.breakpoints.pop(0x200a40b4, None)
        self._native(0x200a40b4, "file_open", opened)
        for address, operation in ((0x200a544c,"create"), (0x200a45e8,"write"),
                                   (0x200a49d8,"rename"), (0x200a4910,"delete")):
            def mutation(b, operation=operation):
                self.native_log.append(dict(op=operation, pc=hex(b.get_reg("pc"))))
                return -1
            self.h.b.breakpoints.pop(address, None)
            self._native(address, "file_"+operation, mutation)
        def sd(b):
            if not self.files.present:
                self.native_log.append(dict(op="sd_id", present=False))
                return -1
            b.write(b.get_reg("r4"), b"\x11"*16)
            self.native_log.append(dict(op="sd_id", present=True))
            return 0
        self.h.b.breakpoints.pop(0x200a3240, None)
        self._native(0x200a3240, "sd_id", sd)
        self.h.b.breakpoints.pop(0x2009359c, None)
        self.load_headers = []
        def header_seen(b):
            ptr = b.get_reg("r0")
            header = self.h.b.read(ptr, 256)
            self.load_headers.append(dict(build_id=header[80:112].hex(), generation=u32(header,28),
                                          resident_match=header[80:112] == DAT.read_bytes()[80:112]))
            return False
        self.h.b.add_breakpoint(self.h.symbols["rv_header"], header_seen)
        ALL_PRODUCTS.append(self)


def bind():
    assert sha(DAT.read_bytes()) == "35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211"
    assert sha(OLD117.read_bytes()) == "4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a"
    assert sha(OLD115.read_bytes()) == "a9743bb9f0ace0ebba1d807af124210a2a098ad64f31c27083412923c841c4b8"
    pe.STAGED, pe.STAGED_SHA, pe.ENGINE_ELF = DAT, sha(DAT.read_bytes()), v.ENGINE_ELF
    mount = ROOT / "firmware/package_v36_g117/SD_ROOT/l08firm3"
    pe.UNITS["mount"] = (mount, sha(mount.read_bytes()), 2)
    pe.FileEdge = Files
    fr.Product = Product
    v.harness_mod.Harness = v.V35Harness
    elf = v.Elf(v.RESIDENT_ELF)
    fr.LAND = {elf.symbols["rv_skip_06"]:"h06_skip", elf.symbols["rv_close_07"]:"h07_close",
               elf.symbols["rv_skip_08"]:"h08_skip", 0x202871dc:"native_setter",
               0x202bb96c:"native_h08", 0x20268768:"native_setter_store",
               0x20268774:"native_row_store",0x202688d4:"native_row_compare"}
    fr.OBSERVE = elf.symbols["rv_hook_observe"]


def need(result):
    assert result.get("ok"), result
    return result


def boot(unit, files=None, ready=1, link=1):
    global FS_SETUP
    FS_SETUP = dict(files if files is not None else {"/ATA1/GXRCE.DAT":DAT.read_bytes()})
    h,p,w = fr.boot(unit, ready=ready, link=link)
    assert 0x20271fec not in h.b.breakpoints
    need(fr.native(h, 0x200935b4, (ready,)))
    assert h.u(0x200d7fd8) == ready and h.u(0x2040f804) == link
    return h,p,w


def snap(h,p):
    root = fr.root_fields(h)
    raw = b"".join(a.to_bytes(4,"big") + x.to_bytes(2,"big") for a,x in sorted(p.rpc.overlay.items()))
    block = root["block"]
    return dict(mode=pe.settings_byte(h)[1],rows=fr.u8(h,0x2022f5ac),cursor=fr.u8(h,0x2022f726),
                root=root,deep_sha256=sha(raw),t=p.rpc.t,
                native_h08=h.b.visits[0x202bb96c], rv_load_visits=h.b.visits[h.symbols["rv_load"]],
                source=fr.u32(h,block+328) if block else None,
                generation=fr.u32(h,block+332) if block else None,
                getter_visits=h.b.visits[0x20271fec], getter_stub=h.stub_hits.get("image_mode_getter",0))


def published(h,p,w):
    opened,_,error = fr.publish(h,p,w)
    need(opened); assert error is None, error
    assert fr.u8(h,R+5) == 3 and fr.u8(h,0x2022f5ac) == 8, snap(h,p)
    return snap(h,p)


def reopen(h,p,w):
    h.parent()
    return published(h,p,w)


def move_to(h,target):
    moves = []
    for _ in range(12):
        if fr.u8(h,0x2022f726) == target:
            return moves
        moves.append(need(fr.move_key(h,0x20)))
    raise AssertionError(("cursor",target,moves))


def unpack(dat, unit, slot):
    d = dat[u32(dat,156)+64*unit:u32(dat,156)+64*(unit+1)]
    table,shared = u32(d,20),u32(dat,192)
    desc = next(dat[table+16+20*i:table+36+20*i] for i in range(dat[table+5]) if dat[table+16+20*i] == slot)
    e = bytearray(552);e[:2]=desc[:2];e[4:8]=desc[4:8];e[445:447]=desc[2:4]
    for off,size,kind,index in zip((20,82,115,216,284,346,379,412,456,518),
        (62,33,96,56,62,33,33,33,62,33),(0,1,2,3,0,1,1,1,0,1),desc[8:18]):
        pool=shared+16+12*kind;assert u16(dat,pool+2)==size
        at=shared+u32(dat,pool+4)+size*index;e[off:off+size]=dat[at:at+size]
    return bytes(e),dat[u32(d,12):u32(d,12)+152]


def deep(p,slot):
    unit=INDEX[p.unit];entry,mapping=unpack(p.dat,unit,slot);stock,_=unpack(p.dat,unit,4)
    checks=[]
    for i in range(9):
        r=mapping[32+12*i:44+12*i]
        address,n,off,bit=u32(r,0),u16(r,4),u16(r,6),r[10]
        source=stock if bit and not(entry[1]&bit) else entry
        expected=source[off:off+n];actual=bytearray()
        for a in range(address,address+n):
            word=p.rpc.half(a&~1);assert word is not None,(slot,hex(a))
            actual.append((word>>(8 if not(a&1) else 0))&255)
        assert bytes(actual)==expected,(p.unit,slot,i,hex(address),sha(actual),sha(expected))
        checks.append(dict(row=i,address=hex(address),bytes=n,actual_sha256=sha(actual),expected_sha256=sha(expected)))
    assert p.rpc.t == u16(entry,445),(p.unit,slot,p.rpc.t,u16(entry,445))
    assert pe.settings_byte(p.h)[1] == 1
    return dict(slot=slot,nine_rows=True,bytes=sum(x["bytes"] for x in checks),t=p.rpc.t,rows=checks)


def no_writes(p):
    counts={op:sum(x["op"]==op for x in p.native_log) for op in ("create","write","rename","delete")}
    counts["write_open"]=sum(x["op"]=="open" and x["flags"]!=0 for x in p.native_log)
    assert not any(counts.values()),counts
    assert not p.files.live,p.files.live
    assert not any(x["op"]=="open" and ("/IROM/T" in x["path"] or "/IROM/L" in x["path"]) for x in p.native_log)
    assert not p.h.stub_hits.get("image_mode_getter",0)
    return counts


def bounded_h01(h,p,count=32):
    before=dict(opens=sum(x["op"]=="open" for x in p.native_log),loads=h.b.visits[h.symbols["rv_load"]])
    frame=pe.SCRATCH+0x400
    for _ in range(count):
        h.b.write(frame,bytes(128))
        need(p.call(h.symbols["rv_hook_observe"],(R,1,frame)))
    after=dict(opens=sum(x["op"]=="open" for x in p.native_log),loads=h.b.visits[h.symbols["rv_load"]])
    assert before==after,(before,after)
    return dict(calls=count,before=before,after=after,retries=0)


def header_reject(h,p,blob):
    h.b.write(pe.SCRATCH+0x800,blob[:256])
    result=need(p.call(h.symbols["rv_header"],(pe.SCRATCH+0x800,len(blob),h.symbols["rv_trust"])))
    assert result["r0"]==8,result
    return dict(result=result,reason="GXRCE_RESIDENT_ID",build_id=blob[80:112].hex())


def session(unit, report):
    h,p,w=boot(unit,ready=0 if unit=="28mm" else 1,link=1)
    if unit=="28mm":
        need(fr.open_settings(h)); first=snap(h,p)
        assert first["rows"]==7 and first["root"]["state"]==0 and not(first["root"]["flags"]&32),first
        assert not p.native_log
        need(fr.native(h,0x200935b4,(1,)));p.ready=1
        assert h.u(0x200d7fd8)==h.u(0x2040f804)==1
        assert fr.u8(h,0x2022f5ac)==7
        need(fr.press(h,0x29));h.parent()
        report["a_first_open"]=first
    report["a"]=published(h,p,w)
    assert report["a"]["source"]==3 and report["a"]["generation"]==117,report["a"]
    assert any(x["resident_match"] for x in p.load_headers)
    print("PASS",unit,"a rv_load=ACCEPT source=CARD generation=117 rows=8 second_ADJ="+str(unit=="28mm"),flush=True)
    assert fr.u8(h,0x2022f726)==4
    report["b"]=dict(cold=snap(h,p),stock=deep(p,4),rpc_writes=sum(x["cmd"]==22 for x in p.rpc.log))
    assert report["b"]["rpc_writes"]==0
    print("PASS",unit,"b cold_cursor=04 live_stock04=1 S=1",flush=True)
    move_to(h,1);need(fr.press(h,0x23));one=deep(p,1)
    reopened=reopen(h,p,w);assert reopened["cursor"]==1,reopened
    need(fr.press(h,0x29));reopen(h,p,w);move_to(h,2);need(fr.press(h,0x23));two=deep(p,2)
    report["c"]=dict(apply01=one,reopen01=reopened,apply02=two,final=snap(h,p))
    print("PASS",unit,"c apply01 S=1 deep01=503B+T reopen=01 close_reopen_apply02 deep02=503B+T",flush=True)
    reopen(h,p,w)
    need(fr.native(h,0x202be220));panel=snap(h,p)
    assert panel["rows"]==11,panel
    need(fr.move_key(h,0x20));need(fr.press(h,0x23));after=snap(h,p)
    assert after["mode"]==1 and after["root"]["state"]==3,after
    report["e"]=dict(fn2=panel,save_attempt=after,counters=no_writes(p))
    print("PASS",unit,"e Fn2 scroll OK_save_attempt create=0 write=0 rename=0 delete=0 write_open=0",flush=True)
    report["session_native_log"]=p.native_log
    report["session_headers"]=p.load_headers
    save("native-"+unit+".json",report)


def corruption(unit,report):
    h,p,w=boot(unit);published(h,p,w);move_to(h,1);need(fr.press(h,0x23));expected=deep(p,1)
    reopen(h,p,w);before=snap(h,p);move_to(h,1)
    address=fr.u32(h,R+136)+1960
    h.put(address,fr.u32(h,address)^1)
    mark=w.mark();need(fr.move_key(h,0x20));after=snap(h,p)
    assert after["mode"]==1 and after["native_h08"]==0 and after["root"]["state"]==6,after
    assert after["deep_sha256"]==before["deep_sha256"]
    assert deep(p,1)==expected
    report["d"]=dict(before=before,negative=dict(address=hex(address),operation="detached snapshot magic xor 1"),
                     after=after,hooks=w.since(mark),deep01=expected,counters=no_writes(p))
    print("PASS",unit,"d viii-b S=1 native_H08_202BB96C=0 deep01_unchanged=1",flush=True)
    save("native-"+unit+".json",report)


def negative(unit,report):
    h,p,w=boot(unit,files={"/ATA1/GXRCE.DAT":OLD117.read_bytes()})
    need(fr.open_settings(h));state=snap(h,p)
    assert state["rows"]==7 and state["root"]["state"]==6 and state["root"]["block"]==0,state
    rejected=header_reject(h,p,OLD117.read_bytes())
    retry=bounded_h01(h,p)
    report["f"]=dict(state=state,header=rejected,h01=retry,counters=no_writes(p),native_log=p.native_log)
    print("PASS",unit,"f old_v35_gen117 rejected=RESIDENT_ID rows=7 H01=32 retries=0 writes=0",flush=True)
    save("native-"+unit+".json",report)


def stale_files(unit):
    old=OLD115.read_bytes();idx=INDEX[unit];files={"/IROM/GXRCE0.DAT":old,"/IROM/GXRCE1.DAT":old}
    # The C validator expands the actual gen115 DAT to obtain its binding.
    import subprocess
    expand=HERE/"candidate/local/v34c-host/expand"
    result=subprocess.run([str(expand),str(OLD115),str(ROOT/"firmware/engine_v36_r28/candidate/local/full-r13/trust.bin")],
                          capture_output=True,text=True,check=True)
    records={tuple(map(int,r[:2])):r for r in map(str.split,result.stdout.splitlines())}
    prefix=("50","28","M0")[idx]
    for slot in range(1,9):
        row=records[idx,slot];binding=bytes.fromhex(row[4]);ts=bytearray.fromhex(row[5])
        assert len(binding)==160 and len(ts)==240
        struct.pack_into(">I",ts,12,11);struct.pack_into(">I",ts,196,2);ts[16:20]=bytes(4)
        struct.pack_into(">I",ts,16,zlib.crc32(ts))
        for copy in "AB":files[f"/IROM/T{prefix}{slot-1:02}{copy}.BIN"]=bytes(ts)
        if slot==8:
            ls=bytearray(192);ls[:4]=b"GXLS";ls[5]=1;ls[7]=192;struct.pack_into(">I",ls,8,11)
            ls[16]=8;ls[17]=idx;ls[24:184]=binding;struct.pack_into(">I",ls,12,zlib.crc32(ls))
            for copy in "AB":files[f"/IROM/L{prefix}{copy}.BIN"]=bytes(ls)
    folder=OUT/"stale-fixtures"/unit;folder.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():
        if not name.endswith(".DAT"):(folder/Path(name).name).write_bytes(data)
    return files


def stale_and_removed(unit,report):
    stale=stale_files(unit);files=dict(stale);files["/ATA1/GXRCE.DAT"]=DAT.read_bytes()
    h,p,w=boot(unit,files=files);published(h,p,w)
    cold=snap(h,p);assert cold["cursor"]==4 and cold["source"]==3 and cold["generation"]==117,cold
    stock=deep(p,4)
    # Card-first loading does not scan IROM. Execute the real header gate for both old copies.
    rejected=[header_reject(h,p,stale[path]) for path in ("/IROM/GXRCE0.DAT","/IROM/GXRCE1.DAT")]
    checks=[]
    for slot in range(1,9):
        move_to(h,slot);need(fr.press(h,0x23));checks.append(deep(p,slot))
        reopen(h,p,w)
        need(fr.native(h,0x202be220));panel=snap(h,p)
        assert panel["rows"]==11 and panel["cursor"]==6,(slot,panel)
        need(fr.press(h,0x29));reopen(h,p,w)
    report["g"]=dict(cold=cold,stock=stock,IROM_header_rejects=rejected,defaults=checks,
                     stale_inventory=[dict(path=n,sha256=sha(b)) for n,b in sorted(stale.items())],
                     stale_files_unchanged=all(p.files.paths[n]==b for n,b in stale.items()),
                     old_preferences_opened=False,IROM_not_scanned_when_card_accepts=True,counters=no_writes(p))
    assert report["g"]["stale_files_unchanged"]
    print("PASS",unit,"g IROM115=a9743bb9 two_headers=RESIDENT_ID source=CARD gen117 stale_GXLS_GXTS_ignored defaults=8 writes=0",flush=True)
    move_to(h,1);need(fr.press(h,0x23));before=snap(h,p)
    p.files.present=False;p.files.paths.pop("/ATA1/GXRCE.DAT")
    reopen(h,p,w);move_to(h,2);need(fr.press(h,0x23));deep(p,2)
    during=snap(h,p);same_boot=bounded_h01(h,p)
    no_writes(p)
    # A fresh interpreter models the next boot with the real stale IROM still present.
    h2,p2,w2=boot(unit,files=stale);need(fr.open_settings(h2));after=snap(h2,p2)
    assert after["rows"]==7 and after["mode"]==1 and after["root"]["state"]==6,after
    reboot_stock=deep(p2,4);next_boot=bounded_h01(h2,p2)
    assert sum(x["generation"]==115 and not x["resident_match"] for x in p2.load_headers)==2,p2.load_headers
    report["h"]=dict(before_removal=before,removed_session=during,same_boot_h01=same_boot,
                     next_boot=after,next_boot_stock04=reboot_stock,next_boot_h01=next_boot,
                     actual_IROM_probe_headers=p2.load_headers,counters=no_writes(p2))
    print("PASS",unit,"h card_removed no_crash same_boot_RAM_apply=02 H01=32 retries=0 next_boot_native04 rows=7 IROM115_rejected=2 writes=0",flush=True)
    save("native-"+unit+".json",report)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("unit",choices=INDEX);parser.add_argument("--group",choices=("all","session","corruption","negative","stale"),default="all")
    args=parser.parse_args();v.python_backend.CACHE=OUT/"decode"/args.unit;bind();report=dict(unit=args.unit,body_sha256=v.BODY_SHA,dat_sha256=sha(DAT.read_bytes()),
        resident_elf_sha256=sha(v.RESIDENT_ELF.read_bytes()),engine_elf_sha256=sha(v.ENGINE_ELF.read_bytes()),
        getter_fixed_return_stub_removed=True,group=args.group)
    previous=OUT/("native-"+args.unit+".json")
    if args.group!="all" and previous.exists():
        report={**json.loads(previous.read_text()),**report}
        report.pop("error",None)
    try:
        if args.group in ("all","session"):session(args.unit,report)
        if args.group in ("all","corruption"):corruption(args.unit,report)
        if args.group in ("all","negative"):negative(args.unit,report)
        if args.group in ("all","stale"):stale_and_removed(args.unit,report)
        report["all_session_counters"]=[no_writes(p) for p in ALL_PRODUCTS]
        report["status"]="PASS"
    except Exception:
        report["status"]="FAIL";report["error"]=traceback.format_exc();save("native-"+args.unit+".json",report)
        raise
    save("native-"+args.unit+".json",report)
    print("PASS integrated",args.unit,args.group,flush=True)


if __name__=="__main__":main()
