from pathlib import Path
import hashlib,json,struct,zlib
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v37_flash'
def digest(data):return hashlib.sha256(data).hexdigest()
def elf_sections(path):
 data=path.read_bytes()
 assert data[:4]==bytes([127,69,76,70]) and data[4]==1
 order='>' if data[5]==2 else '<'
 fields=struct.unpack_from(order+'16sHHIIIIIHHHHHH',data)
 start,entry_size,count,names_index=fields[6],fields[11],fields[12],fields[13]
 entries=[struct.unpack_from(order+'10I',data,start+i*entry_size) for i in range(count)]
 names_entry=entries[names_index];names=data[names_entry[4]:names_entry[4]+names_entry[5]]
 result={}
 for item in entries:
  name=names[item[0]:].split(bytes([0]),1)[0].decode()
  result[name]={'address':item[3],'offset':item[4],'size':item[5],'data':data[item[4]:item[4]+item[5]] if item[1]!=8 else b''}
 return result

def symbol_address(sections,name):
 symbols=sections['.symtab']['data'];names=sections['.strtab']['data']
 for at in range(0,len(symbols),16):
  offset,value,size,info,other,index=struct.unpack_from('>IIIBBH',symbols,at)
  if names[offset:].split(bytes([0]),1)[0].decode()==name:return value
 raise ValueError('missing ELF symbol '+name)

def main():
 body=(ROOT/'firmware/package_v37_redisplay/SD_ROOT/ilaunch3').read_bytes()
 old=(ROOT/'firmware/package_v36_g120b/SD_ROOT/ilaunch3').read_bytes()
 assert len(body)==len(old)==3993340
 changed=[i for i,(a,b) in enumerate(zip(body,old)) if a!=b]
 allowed=[(0x16c,0x170),(0x9118,0x9166),(0x9808,0x9828)]
 groups=[{'begin':hex(a),'end_inclusive':hex(b-1),'changed':sum(a<=i<b for i in changed)} for a,b in allowed]
 outside=[hex(i) for i in changed if not any(a<=i<b for a,b in allowed)]
 recomputed=sum(value*(i%6+2) for i,value in enumerate(body[0x200:]))&0xffffffff
 stored=int.from_bytes(body[0x16c:0x170],'big')
 official=ROOT/'artifacts/firmware/gxr-1.51/ilaunch3'
 siblings=[]
 for p in sorted((ROOT/'firmware/package_v37_redisplay/SD_ROOT').iterdir()):
  if p.name in {'ilaunch3','GXRCE.DAT'}:continue
  b=p.read_bytes();q=ROOT/'firmware/package_v36_g120b/SD_ROOT'/p.name
  v={'file':p.name,'matches_v36':q.read_bytes()==b,'sha256':digest(b)}
  q=official.parent/p.name
  v['matches_official']=q.is_file() and q.read_bytes()==b
  siblings.append(v)
 rs=elf_sections(ROOT/'firmware/package_v37_redisplay/body/evidence/resident.load.elf')
 resident=next(v for v in rs.values() if v['address']==0x2005276c and v['size']==7884)
 at=0x796c
 assert resident['address']==0x2005276c
 code_match=body[at:at+resident['size']]==resident['data']
 dat=(ROOT/'firmware/package_v37_redisplay/SD_ROOT/GXRCE.DAT').read_bytes()
 dat_old=(ROOT/'firmware/engine_v48_own/candidate/local/full-r13/GXRCE.DAT').read_bytes()
 engine=(ROOT/'firmware/engine_v52_redisplay/candidate/local/full-r13/engine.bin').read_bytes()
 prior_engine=(ROOT/'firmware/engine_v48_own/candidate/local/full-r13/engine.bin').read_bytes()
 engine_at=dat.find(engine)
 engine_old_at=dat_old.find(prior_engine)
 es=elf_sections(ROOT/'firmware/engine_v52_redisplay/candidate/local/full-r13/engine.elf')
 old_es=elf_sections(ROOT/'firmware/engine_v48_own/candidate/local/full-r13/engine.elf')
 engine_section=next(v for k,v in es.items() if k=='.engine')
 data_tail_same=dat[engine_at+len(engine)+8+232:]==dat_old[engine_old_at+len(prior_engine)+8+232:]
 sections=[]
 for i in range(7):
  kind,flags,off,n=struct.unpack_from('>HHII',dat,128+12*i)
  old_kind,old_flags,old_off,old_n=struct.unpack_from('>HHII',dat_old,128+12*i)
  same=dat[off:off+n]==dat_old[old_off:old_off+old_n]
  sections.append({'id':kind,'flags':flags,'offset':off,'length':n,'baseline_offset':old_off,'baseline_length':old_n,'content_equal':same})
 for row in sections[1:3]:
  current=dat[row['offset']:row['offset']+row['length']]
  prior=dat_old[row['baseline_offset']:row['baseline_offset']+row['baseline_length']]
  pairs=[(int.from_bytes(prior[i:i+4],'big'),int.from_bytes(current[i:i+4],'big')) for i in range(0,len(current),4)]
  differences=[(a,b) for a,b in pairs if a!=b]
  row['changed_word_count']=len(differences)
  row['changed_words_add_16']=all(b-a==16 for a,b in differences)
 current_reloc=sections[1]['offset'];prior_reloc=sections[1]['baseline_offset']
 patch,target=struct.unpack_from('>II',dat,current_reloc)
 old_patch,old_target=struct.unpack_from('>II',dat_old,prior_reloc)
 relocation={'patch_change':patch-old_patch,'target_change':target-old_target,
             'target_matches_rv_call':target==symbol_address(es,'rv_call'),
             'baseline_target_matches_rv_call':old_target==symbol_address(old_es,'rv_call'),
             'stored_target_matches':int.from_bytes(dat[patch:patch+4],'big')==target}
 crc_header=zlib.crc32(dat[:20]+bytes(4)+dat[24:256])&0xffffffff
 crc_content=zlib.crc32(dat[256:])&0xffffffff
 trust_at=0x97e8
 trust_matches={'body':dat[48:80]==body[trust_at:trust_at+32],
                'build':dat[80:112]==body[trust_at+32:trust_at+64],
                'abi':dat[212:228]==body[trust_at+64:trust_at+80]}
 result={'body_sha256':digest(body),'body_size':len(body),'body_difference_count':len(changed),'body_difference_groups':groups,'body_difference_outside':outside,'checksum_stored':hex(stored),'checksum_recomputed':hex(recomputed),'checksum_equal':stored==recomputed,'resident_section_matches_body':code_match,'resident_section_size':resident['size'],'official_body_sha256':digest(official.read_bytes()),'siblings':siblings,'dat_sha256':digest(dat),'dat_size':len(dat),'dat_baseline_sha256':digest(dat_old),'dat_baseline_size':len(dat_old),'engine_size':len(engine),'engine_size_increase':len(engine)-len(prior_engine),'engine_sha256':digest(engine),'engine_in_dat_offset':engine_at,'engine_exactly_in_dat':engine_at>=0,'engine_matches_elf':engine_section['data']==engine,'dat_data_tail_same':data_tail_same}
 result.update({'sections':sections,'generation':int.from_bytes(dat[28:32],'big'),
                'dat_header_crc_equal':crc_header==int.from_bytes(dat[20:24],'big'),
                'dat_content_crc_equal':crc_content==int.from_bytes(dat[24:28],'big'),
                'dat_trust_matches_body':trust_matches,
                'relocation':relocation,
                'resident_build_id':dat[80:112].hex()})
 (OUT/'local/artifacts.json').write_text(json.dumps(result,indent=2)+'\n')
 assert len(changed)==102 and not outside and stored==recomputed and code_match
 assert all(v['matches_v36'] and v['matches_official'] for v in siblings) and len(siblings)==28
 assert engine_at>=0 and engine_section['data']==engine and len(engine)-len(prior_engine)==16
 assert result['generation']==127 and result['dat_header_crc_equal'] and result['dat_content_crc_equal']
 assert all(trust_matches.values()) and all(row['content_equal'] for row in sections[3:])
 assert sections[2]['changed_words_add_16']
 assert relocation['patch_change']==16 and relocation['target_change']==8
 assert relocation['target_matches_rv_call'] and relocation['baseline_target_matches_rv_call'] and relocation['stored_target_matches']
 print(json.dumps({k:v for k,v in result.items() if k!='siblings'},indent=2))
if __name__=='__main__':main()
