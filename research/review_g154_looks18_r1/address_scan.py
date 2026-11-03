"""Check decoded direct branches and constant address constructions beyond RELA."""
import json,re,struct,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *
from link_check import Elf

def main():
    guard();elf=Elf(TMP/'link/final/engine.elf');code=elf.data('.engine')
    tool=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    args=[str(tool),'-d','-z','-j','.engine',str(TMP/'link/final/engine.elf')]
    p=subprocess.run(args,capture_output=True,text=True,check=True,timeout=10800)
    (TMP/'final-disassembly.txt').write_text(p.stdout)
    funcs=[s for s in elf.symbols if s['section']==elf.byname['.engine']['index'] and s['info']&15==2 and s['size']]
    def executable(pc):return any(s['value']<=pc<s['value']+s['size'] for s in funcs)
    lines=[];verified=0
    for line in p.stdout.splitlines():
        m=re.match(r'^\s*([0-9a-f]+):\s*((?:[0-9a-f]{2}\s+){2,4})\s*(.*)$',line)
        if not m:continue
        pc=int(m[1],16);raw=bytes.fromhex(m[2]);assert code[pc-256:pc-256+len(raw)]==raw
        if not executable(pc):continue
        verified+=len(raw)
        parts=re.split(r'\s*(?:->|\|\|)\s*',m[3])
        assert len(parts)<=2
        for i,asm in enumerate(parts):lines.append((pc+2*i,asm.strip()))
    lo=len(dat(True));hi=lo+struct.unpack_from('>I',dat(True),116)[0]
    branches=[];badbranch=[];constructions=[];bare=[]
    rel={r['patch']:r for r in elf.relocs}
    branch_names={'bra','bl','bc','bnc','beq','bne','beqz','bnez','bgez','bgtz','blez','bltz'}
    def target(text):
        m=re.search(r'(?:^|[,\s])([0-9a-f]+)(?:\s*<[^>]*>)?$',text)
        return int(m[1],16) if m else None
    for i,(pc,asm) in enumerate(lines):
        op=asm.split()[0] if asm else ''
        if op in branch_names:
            address=target(asm)
            assert address is not None,(pc,asm)
            item=dict(pc=pc,assembly=asm,target=address);branches.append(item)
            if lo<=address<hi:badbranch.append(item)
        if op=='ld24':
            value=target(asm)
            assert value is not None,(pc,asm)
            if lo<=value<hi:
                item=dict(pc=pc,assembly=asm,value=value,relocation=rel.get(pc));constructions.append(item)
                if pc not in rel:bare.append(item)
        m=re.fullmatch(r'seth (r\d+|lr|sp),#0x([0-9a-f]+)',asm)
        if m and i+1<len(lines):
            q,low=lines[i+1];n=re.fullmatch(r'(add3|or3) '+m[1]+','+m[1]+r',#(-?\d+|0x[0-9a-f]+)',low)
            if n and q==pc+4:
                high=int(m[2],16)<<16;imm=int(n[2],0)
                value=((high+imm) if n[1]=='add3' else (high|imm))&0xffffffff
                if lo<=value<hi:
                    item=dict(pc=pc,low_pc=q,assembly=asm+'; '+low,value=value,high_relocation=rel.get(pc),low_relocation=rel.get(q));constructions.append(item)
                    if pc not in rel and q not in rel:bare.append(item)
    classified=[];unclassified=[]
    for item in bare:
        owners=[s['name'] for s in funcs if s['value']<=item['pc']<s['value']+s['size']]
        index=next(i for i,(pc,asm) in enumerate(lines) if pc==item['pc'])
        following=[asm for pc,asm in lines[index+1:index+5]]
        register=re.match(r'ld24 (r\d+),',item['assembly'])
        if item['value']==98304-256 and register and owners and all(n in ('eng_data_accept','init_core') for n in owners):
            assert any('cmpu '+register[1]+',r4'==asm for asm in following)
            item['owners']=owners;item['following']=following
            item['source_proof']='Unsigned file-length range test: 256 <= length <= 98304, compiled as length-256 <= 98048; immediate is compared, not dereferenced'
            classified.append(item)
        else:unclassified.append(item)
    assert branches and funcs and verified
    result=dict(status='PASS' if not badbranch and not unclassified else 'FAIL',objdump_sha256=sha(tool.read_bytes()),
                code_sha256=sha(code),function_symbols=len(funcs),verified_function_bytes=verified,
                decoded_operations=len(lines),direct_branch_count=len(branches),old_BSS_range=[lo,hi],
                direct_branches_to_old_BSS=badbranch,constructions_in_old_numeric_range=constructions,
                classified_non_address_constants=classified,unrelocated_constructions_in_old_BSS_range=unclassified,
                qualification='Indirect address expressions are covered by the complete relocation audit and source/constant checks; this scan adds direct branch and immediate-construction checks.')
    save('evidence/address-scan.json',result)
    print(json.dumps({k:result[k] for k in ('status','function_symbols','verified_function_bytes','decoded_operations','direct_branch_count','direct_branches_to_old_BSS','unrelocated_constructions_in_old_BSS_range')}))
    assert result['status']=='PASS'

if __name__=='__main__':main()
