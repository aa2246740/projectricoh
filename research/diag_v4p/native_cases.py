"""Generated closed-schema and raw-source mutations, using actual model captures."""
from pathlib import Path
from contextlib import redirect_stdout
import copy,gzip,hashlib,io,json,os,struct,sys,time,zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import native_gate as g

def leaves(value,path=()):
    yield path,value
    if type(value) is dict:
        for k,v in value.items():yield from leaves(v,path+(k,))
    elif type(value) is list:
        for i,v in enumerate(value):yield from leaves(v,path+(i,))
def set_at(doc,path,value,delete=False):
    out=copy.deepcopy(doc);parent=out
    for key in path[:-1]:parent=parent[key]
    if delete:del parent[path[-1]]
    else:parent[path[-1]]=value
    return out

def call(text,raw,expected,label,stream):
    folder=s.TMP/'native-cases';folder.mkdir(exist_ok=True)
    rp=folder/'source.bin';rp.write_bytes(raw)
    ref=s.HERE/'reference-v7.json';pin=s.sha(ref);dat=s.sha(s.PACKAGE/'GXRCE.DAT')
    argv=['-','--raw',str(rp),'--raw-sha256',g.sha(raw),'--dat-sha256',dat,'--reference',str(ref),'--reference-sha256',pin]
    sys.stdout.flush();sys.stderr.flush();rd,wr=os.pipe();pid=os.fork()
    if pid==0:
        try:
            os.close(rd);sys.stdin=io.StringIO(text);out=io.StringIO()
            with redirect_stdout(out):code=g.main(argv)
            result=json.loads(out.getvalue())
            if (code==0)!=result['records_complete']:os._exit(91)
            if code and any(result[k]!='undetermined' for k in ('record_stage','capacity','h43','time')):os._exit(92)
            os.write(wr,json.dumps(dict(code=code,complete=result['records_complete'],reasons=result.get('reasons'))).encode());os._exit(code)
        except BaseException:os._exit(93)
    os.close(wr);chunks=[]
    while True:
        part=os.read(rd,65536)
        if not part:break
        chunks.append(part)
    os.close(rd);_,status=os.waitpid(pid,0);code=os.waitstatus_to_exitcode(status)
    row=dict(name=label,exit_code=code,expected=expected,record_sha256=g.sha(text.encode()),raw_sha256=g.sha(raw),result=json.loads(b''.join(chunks)) if chunks else {})
    stream.write(json.dumps(row,ensure_ascii=False)+'\n');check=(code==expected)
    if not check:raise AssertionError(row)

def reseal(raw):
    out=bytearray(raw);out[16:20]=bytes(4);struct.pack_into('>I',out,16,zlib.crc32(out)&0xffffffff);return bytes(out)

def main():
    s.enable();started=time.monotonic();ref=(s.HERE/'reference-v7.json').read_bytes();pin=g.sha(ref);r=g.reference(ref,pin);dat=s.sha(s.PACKAGE/'GXRCE.DAT')
    counts=dict(model_positive=0,quick_incomplete_negative=0,valid_observation_positive=0,field_mutations=0,raw_semantic_mutations=0,malformed_json=0)
    with gzip.open(s.HERE/'evidence/native-cli.jsonl.gz','wt') as stream:
        units=[u for u in ('50mm','28mm','mount') if (s.HERE/'evidence'/('record-'+u+'.bin')).exists()]
        assert units and units[0]=='50mm'
        for unit in units:
            raw=(s.HERE/'evidence'/('record-'+unit+'.bin')).read_bytes();doc=g.expand(raw,dat,r,pin);text=g.canonical(doc).decode()
            result=g.classify(text,raw,g.sha(raw),dat,ref,pin);assert result['records_complete'],result
            s.save(s.HERE/'evidence'/('decode-'+unit+'.json'),doc)
            call(text,raw,0,unit+'/complete_model',stream);counts['model_positive']+=1
            changed=bytearray(raw);changed[g.L['record_size']+g.L['mem']+32]^=1;changed=reseal(changed)
            observed=g.expand(changed,dat,r,pin)
            call(g.canonical(observed).decode(),changed,0,unit+'/newly_sealed_valid_MEM_observation',stream);counts['valid_observation_positive']+=1
            # Every path is selected from the actual decoded record; variants change only that path.
            # One unit covers every path; the other two repeat the source-boundary set below.
            if unit=='50mm':
                generator=s.load(s.ROOT/'research/body_v4_design/r5/mutations.py','native_v7_r5_generator')
                for mutation in generator.generate(doc):
                    if mutation.get('summary'):
                        counts['generator_noops']=mutation['noops'];break
                    if '--osd-only' in sys.argv:
                        affected={'osd','palette','current','schema_version','capability','kind','raw_source','raw_sha256','dat_sha256','reference_sha256','identity','allocation','derived','limits','records_complete','record_stage','verdict'}
                        paths=mutation['path'];first=paths[0] if paths else None
                        if type(first) in (list,tuple):
                            if not any(p and p[0] in affected for p in paths):continue
                        elif first not in affected:continue
                    candidate=mutation['data'].decode()
                    call(candidate,raw,2,unit+'/'+str(mutation['path'])+'/'+mutation['operation'],stream)
                    counts['field_mutations']+=1
                    if counts['field_mutations']%1000==0:print('native mutations',counts['field_mutations'],flush=True)
                for name,candidate in (('duplicate_root',text[:-1]+',"schema_version":7}'),('not_finite',text.replace('"schema_version":7','"schema_version":NaN',1)),('unknown_root',text[:-1]+',"not_declared":0}')):
                    call(candidate,raw,2,name,stream);counts['malformed_json']+=1
            R=g.L['record_size'];positions={
              'version':4,'record_flags':20,'scene_missing':g.L['scene']+22,'scene_id':g.L['scene']+18,
              'key_missing':g.L['keys'],'sequence_gap':g.L['counts'],'slot_coverage':R+g.L['slots']+64,
              'slot_stride':R+g.L['slots']+112,'slot_count':R+g.L['slots']+904,'slot_matrix_crc':R+g.L['slots']+60,
              'slot_reserved':R+g.L['slots']+1003,'palette':R+g.L['palette']+4,'palette_count':R+g.L['palette_count']+3,
              'osd_piece':g.L['osd']+188,'osd_flag':g.L['osd']+19,'osd_settings':R+g.L['osd_config']+45,
              'quality':g.L['images']+43,'image_stride':g.L['images']+39,'h09_missing':g.L['requests'],
              'k_source_missing':g.L['k_sources'],'h41_missing':g.L['times']+24,'lifecycle':g.L['times']+12,
              'h41_copy':g.L['times']+56,'unknown_class':g.L['k_sources']+20+5,
              'time_zero':g.L['times']+28,'bw_missing':g.L['bw']+23,'bw_source':g.L['bw']+16,
              'bw_result':g.L['bw']+8,'mem_missing':R+g.L['mem'],'unit':48,'current':R+128}
            for name,at in positions.items():
                out=bytearray(raw);out[at]^=0x80
                if name=='time_zero':out[g.L['times']+24:g.L['times']+28]=out[g.L['times']+20:g.L['times']+24]
                changed=reseal(out)
                call(text,changed,2,unit+'/resealed_raw/'+name,stream);counts['raw_semantic_mutations']+=1
                # Also prove semantic decoding rejects the newly sealed raw source itself.
                try:g.expand(changed,dat,r,pin)
                except (ValueError,KeyError,TypeError,struct.error,g.old.g.InvalidRecord):pass
                else:raise AssertionError('raw semantic mutation accepted: '+name)
            for kind in range(3):
                out=bytearray(raw)
                for i in range(32):
                    at=g.L['bw']+(32*kind+i)*24;start=int.from_bytes(out[at:at+4],'big')
                    struct.pack_into('>I',out,at+4,(start+1)&0xffffffff)
                changed=reseal(out)
                try:g.expand(changed,dat,r,pin)
                except ValueError:pass
                else:raise AssertionError('insufficient BW total time accepted')
                call(text,changed,2,unit+'/resealed_short_BW/'+str(kind),stream);counts['raw_semantic_mutations']+=1
            for case in ('stopped_current_clock','reversed_current_row'):
                out=bytearray(raw);at=g.L['record_size'];m=g.words(out,at,32)
                if case=='stopped_current_clock':
                    struct.pack_into('>I',out,at+16,m[3])
                    for i in range(10):
                        struct.pack_into('>I',out,at+4*(8+i),m[3]);struct.pack_into('>I',out,at+4*(18+i),m[3])
                else:struct.pack_into('>I',out,at+4*27,(m[17]-1)&0xffffffff)
                changed=reseal(out)
                try:g.expand(changed,dat,r,pin)
                except (ValueError,g.old.g.InvalidRecord):pass
                else:raise AssertionError('invalid current time accepted')
                call(text,changed,2,unit+'/'+case,stream);counts['raw_semantic_mutations']+=1
            for which in range(2):
                out=bytearray(raw);at=g.L['record_size']+g.L['slots']+1004*which
                step=int.from_bytes(out[at+112+11*4:at+116+11*4],'big')+64;struct.pack_into('>I',out,at+112+11*4,step)
                begin,end=struct.unpack_from('>2I',out,at+20);out[at+904+11]=min(18,(end-begin)//step)
                matrix=[]
                for j in range(99):
                    stride=int.from_bytes(out[at+112+4*j:at+116+4*j],'big');base=int.from_bytes(out[at+508+4*j:at+512+4*j],'big');count=out[at+904+j]
                    matrix.extend([base+n*stride for n in range(count)]+[0]*(19-count))
                struct.pack_into('>I',out,at+60,zlib.crc32(struct.pack('>1881I',*matrix))&0xffffffff);changed=reseal(out)
                try:g.expand(changed,dat,r,pin)
                except ValueError:pass
                else:raise AssertionError('self-consistent reserved row change accepted')
                call(text,changed,2,unit+'/resealed_reserved_row/'+str(which),stream);counts['raw_semantic_mutations']+=1
        for unit in ('28mm','mount'):
            path=s.HERE/'evidence'/('quick-record-'+unit+'.bin')
            if path.exists():
                call(text,path.read_bytes(),2,unit+'/focused_capture_is_incomplete',stream);counts['quick_incomplete_negative']+=1
    s.save(s.HERE/'evidence/native-summary.json',dict(status='PASS',dat_sha256=dat,reference_sha256=pin,counts=counts,
        real_model_sources=True,actual_public_cli_os_exit=True,scope='OSD/current/identity/schema and raw semantic groups' if '--osd-only' in sys.argv else 'all native fields',seconds=round(time.monotonic()-started,2)))
    print('PASS native cases',counts,flush=True)
if __name__=='__main__':main()
