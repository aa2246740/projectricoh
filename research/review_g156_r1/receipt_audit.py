"""Recheck all nine reference receipts and recompute the raw write logs."""
from pathlib import Path
import collections
import io
import json
import pickle
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
D=C.DF

class InertPreviewLink:
    pass

class DataUnpickler(pickle.Unpickler):
    def find_class(self,module,name):
        allowed={('collections','Counter'):collections.Counter,
                 ('collections','deque'):collections.deque,
                 ('builtins','bytearray'):bytearray,
                 ('v310_preview_link','PreviewLink'):InertPreviewLink}
        if (module,name) not in allowed:
            raise ValueError(('unsupported data class',module,name))
        return allowed[module,name]

def snapshot(info):
    path=C.ROOT/info['path'];raw=path.read_bytes()
    assert C.sha(raw)==info['sha256']
    return DataUnpickler(io.BytesIO(zlib.decompress(raw))).load()

def memory(saved,address,n):
    for base,raw,_ in reversed(saved['cpu']['regions']):
        if base<=address and address+n<=base+len(raw):return bytes(raw[address-base:address-base+n])
    raise ValueError(('unmapped',hex(address),n))

def rpc(saved):
    return next(d['rpc_state'] for typ,d in zip(saved['cpu']['device_types'],saved['cpu']['devices']) if typ=='StartupRegisters')

S_ALLOWED={0x36e,0x36f,0x370,0x371,0x6dd,0x6de,*range(0x641,0x647),*range(0x8ac,0x8b6),*range(0xfd4,0xffc)}
body=(C.ROOT/'firmware/image_v310/local/ilaunch3').read_bytes()
segments=[struct.unpack_from('>5I',body,32+20*i)for i in range(16)]

def settings(stores,code):
    engine=[];resident=[];factory=[]
    for off,n,pc in stores:
        assert 0<=off<4096 and n>0 and off+n<=4096
        if code[0]<=pc<code[1]:engine.append([off,n,pc])
        elif 0x2005276c<=pc<0x20054700:resident.append([off,n,pc])
        else:
            assert any(size and start<=pc<start+size for _,start,size,_,_ in segments),('unknown settings writer',hex(pc))
            factory.append([off,n,pc])
    assert all(set(range(off,off+n))<=S_ALLOWED for off,n,pc in engine+resident)
    return dict(engine=len(engine),resident=len(resident),factory=len(factory),
                factory_PCs=sorted({hex(pc)for _,_,pc in factory}))

def writes(raw,unit,log,start=0,end=None):
    directory=D.u32(raw,156)+unit*64;mapping=D.u32(raw,directory+12)
    allowed=set()
    for i in range(9):
        at,n,_=struct.unpack_from('>IHH',raw,mapping+32+12*i)
        allowed.update(range(at,at+n))
    page=None;cursor=0;known={};count=0;edges=0;T=[]
    for index,row in enumerate(log[:end]):
        cmd,value=row['cmd'],row['value']
        if cmd==23:page=value
        elif cmd==21:
            cursor=0 if page==0x12c0 else ((page or 0)<<16)|(value&0xfffe)
            if page!=0x12c0 and 0<=row.get('result',-1)<=65535:known[cursor]=row['result']
        elif cmd==22:
            if index>=start:
                count+=1
                if page==0x12c0:
                    assert value in (0,2),('unexpected T',value)
                    T.append(value)
                else:
                    assert cursor in allowed or cursor+1 in allowed,('out-of-map W',index,hex(cursor))
                    for offset,shift in ((0,8),(1,0)):
                        if cursor+offset not in allowed:
                            assert cursor in known and ((known[cursor]>>shift)&255)==((value>>shift)&255),('changed outside edge',index,hex(cursor+offset))
                            edges+=1
            if page!=0x12c0:known[cursor]=value&65535
            cursor=0 if page==0x12c0 else (cursor+2)&0xffffffff
    return dict(unit_W=count,edge_bytes_preserved=edges,T_values=sorted(set(T)))

records=json.loads((C.HERE/'evidence/records.json').read_text())['rows']
names={'mount':2,'50mm':0,'28mm':1}
labels=[]
for profile in ('release','test'):
    for unit in names:
        labels.append((profile,unit,False,'r4-reference-'+profile+'-'+unit+'-flow'+('-r2'if profile=='release'and unit=='28mm'else'')))
for unit in names:
    labels.append(('test',unit,True,'r4-reference-test-'+unit+'-restore'+('-r2'if unit=='mount'else'')))
out=[]
for profile,unit,restore,label in labels:
    path=C.ORIGINAL/'evidence'/(label+'.json');d=json.loads(path.read_text())
    raw=(C.PACKAGES[profile]/'GXRCE.DAT').read_bytes();ui=names[unit]
    row=dict(profile=profile,unit=unit,restore=restore,receipt=str(path.relative_to(C.ROOT)),receipt_sha256=C.sha(path.read_bytes()))
    assert d['status']=='PASS' and d['DAT_sha256']==C.sha(raw)
    assert d['backend'] in ('reference','Python-device-reference')
    if 'fast_snapshot_saved_or_restored'in d:
        assert d['fast_snapshot_saved_or_restored'] is False
    if d['backend']=='reference':
        driver=C.ROOT/d['driver_source_copy'];source=driver.read_text()
        assert C.sha(driver.read_bytes())==d['driver_sha256']
        assert 'storage_run.Machine(str(medium))'in source
        assert 'load_snapshot'not in source and 'restore_snapshot'not in source
        row['cold_driver_sha256']=d['driver_sha256']
    first=d['first_menu'];cached=first.get('cached_cursor',first.get('cached'))
    assert (first['state'],first['activity'],first['word'])==(56,8,2)
    assert first['cursor']==cached==first['physical']+1
    assert d['OK_close'] and d['ADJ_close']
    if not restore:
        expected={r['name']:r['sha256']for r in records if r['profile']==profile and r['unit']==C.UNITS[ui] and r['action']=='replace'}
        if not expected:expected={'04 Std':C.sha(D.expand(raw,ui,4))}
        actual={x['name']:x.get('readback',x)['sha256']for x in d['checks']}
        assert len(d['checks'])==len(expected) and actual==expected
        for item in d['checks']:
            check=item.get('readback',item)
            assert check['complete_552_equal'] and item['DISP_no_write']
            cur=item.get('cursor')
            if cur:
                assert cur['native']==cur['cached']==cur['physical'] and cur['equal']
                cur=item['cursor_after_DISP'];assert cur['native']==cur['cached']==cur['physical'] and cur['equal']
            else:assert item['cursor_equal'] and item['cursor_after_DISP']
            if 'rows'in check:
                assert len(check['rows'])==9 and all(x['equal']for x in check['rows'])
                record=next(r for r in records if r['profile']==profile and r['unit']==C.UNITS[ui]and r['name']==item['name'])
                data=(C.RECORDS/record['registry_file']).read_bytes()if record['action']=='replace'else D.expand(raw,ui,4)
                mapping=D.u32(raw,D.u32(raw,156)+64*ui+12)
                for i,observed in enumerate(check['rows']):
                    _,n,off=struct.unpack_from('>IHH',raw,mapping+32+12*i)
                    assert observed['index']==i and observed['bytes']==n and observed['sha256']==C.sha(data[off:off+n])
                assert check['T']==int.from_bytes(data[445:447],'big')
        row['records']=expected
    else:
        normal_label='r4-reference-test-'+unit+'-flow'
        normal=json.loads((C.ORIGINAL/'evidence'/(normal_label+'.json')).read_text())
        target=(C.ROOT/normal['tweak_target_path']).read_bytes()
        a=d['restore_readback'];b=d['restore_readback_after_menu']
        assert len(target)==552 and a['complete_552_equal'] and b['complete_552_equal']
        assert a['sha256']==b['sha256']==d['target_sha256']==C.sha(target)
        levels=d['restored_levels'];assert levels==first['levels'] and levels!=[100,0,0,0,0,0,0,0,0,0]
        controls=d.get('restored_first_controls',d.get('controls'))
        assert controls['screen']==2 and controls['levels']==levels
        if d['backend']=='reference':
            assert C.sha((C.ROOT/normal['settings_path']).read_bytes())==d['settings_sha256']
        row.update(target_sha256=C.sha(target),levels=levels)
    if d['backend']=='reference':
        assert d['actual_backend']=='reference' and d['body_sha256']==C.sha(body)
        path=C.ROOT/d['rpc_log_path'];assert C.sha(path.read_bytes())==d['rpc_log_sha256']
        log=json.loads(path.read_text());code=d['engine_code_range'];start=d['unit_log_start']
        row['writes']=writes(raw,ui,log,start)
        row['S']=settings(d['S_stores'],code);row['BOOT_S']=settings(d['BOOT_S_stores'],code)
        closes=[k['state']for k in d['keys']if k['key']in('OK','ADJ')and k['state']['state']==5]
        assert len(closes)>=2
        assert all(s['word']==2 for s in closes)
        if profile=='release':
            boot=writes(raw,ui,log,0,start)
            assert boot['unit_W']==0 and row['BOOT_S']['engine']==row['BOOT_S']['resident']==0
            row['release_BOOT_zero_write']=True
    else:
        for info in d['reference_modules'].values():
            module=Path(info['path'])
            assert module.is_file() and C.sha(module.read_bytes())==info['sha256'],('reference module drift',str(module))
        cold_path=C.ROOT/d['cold_receipt'];assert C.sha(cold_path.read_bytes())==d['cold_receipt_sha256']
        cold=json.loads(cold_path.read_text())
        assert cold['cold_origin'] and cold['error'] is None and cold['state']==5
        detail=json.loads(cold_path.with_name(cold_path.stem+'-detail.json').read_text())
        assert detail['dat_sha256']==C.sha(raw) and detail['cold_origin']
        if not restore:
            final=snapshot(d['snapshot'])
            assert final['dat_sha256']==C.sha(raw) and final['body_sha256']==C.sha(body) and final['cold_origin']
            base=int.from_bytes(memory(final,0x20054770,4),'big')-256
            expected=bytearray(raw);rel,n=D.sections(raw)[1]
            for at in range(rel,rel+n,8):
                patch,target=struct.unpack_from('>II',raw,at);struct.pack_into('>I',expected,patch,base+target)
            actual=memory(final,base,len(raw))
            differences=[i for i,(a,b)in enumerate(zip(actual,expected))if a!=b]
            # t_seen is the existing initialized data word inside .engine.
            # It records actual T reads; accept only that named 4-byte variable.
            elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','review_receipt_elf').Elf(
                C.ENGINE/'candidate/local'/('boot-on'if profile=='test'else'boot-off')/'engine.elf')
            symbol=elf.symbols['t_seen'];assert symbol['size']==4
            assert set(differences)<=set(range(symbol['value'],symbol['value']+4)),('loaded final artifact differs',differences[:20])
            if differences:assert actual[symbol['value']:symbol['value']+4]==b'\0\0\0\2'
            row['loaded_DAT_mutable_word']=dict(symbol='t_seen',offset=symbol['value'],changed_offsets=differences)
            peer=rpc(final);log=peer['log'];w=d['write_whitelist']
            assert len(log)==w['log_end']
            row['writes']=writes(raw,ui,log,w['log_start'])
            assert row['writes']['unit_W']==w['unit_W']
            code=[base+256,base+256+D.u32(raw,136)]
            stores=w['engine_stores']+w['resident_service_stores']+w['body_stores']
            row['S']=settings(stores,code)
            assert len(stores)==w['S_store_count']
            assert memory(final,0x205d9c00,4)==b'\0\0\0\5' and memory(final,0x200547ec,4)==b'\0\0\0\2'
            windows=d['physical_key_windows']
            assert any(k['key']=='OK'and k['state']['state']==5 for k in windows)
            assert any(k['key']=='ADJ'and k['state']['state']==5 for k in windows)
            row['snapshot_use']='read data and RPC log only; never restored into a runtime'
            del final
        else:
            source=C.ROOT/d['reference_source'];assert C.sha(source.read_bytes())==d['reference_source_sha256']
            saved=snapshot(dict(path=str(source.relative_to(C.ROOT)),sha256=d['reference_source_sha256']))
            code=d['engine_code_range'];log=rpc(saved)['log'];w=d['write_whitelist']
            # Restore-menu logs are represented individually by every validated W address.
            for item in w['writes']:
                assert item['page']==0x12c0 or item['address']is not None
            assert w['unit_W']==0 and not w['writes']
            row['writes']=dict(unit_W=0,BOOT=writes(raw,ui,log,0))
            row['S']=settings(w['engine_stores']+w['resident_service_stores']+w['body_stores'],code)
            assert d['DISP_no_write']
            stores=[[int(x['at'],16)-int(detail['final']['s_address'],16),len(bytes.fromhex(x['data'])),int(x['pc'],16)]for x in detail['all_boot_settings_writes']]
            row['BOOT_S']=settings(stores,code)
            persistent=(C.ROOT/normal['settings']['persistent_path']).read_bytes()
            assert C.sha(persistent)==normal['settings']['persistent_sha256']
            assert persistent[0xfd4:0xffc]==bytes.fromhex(first['record'])==bytes.fromhex(detail['final']['record'])
            assert any(e.get('label')=='persistent-settings-source'and e.get('sha256')==C.sha(persistent)for e in detail['events'])
            del saved
        if profile=='release':
            assert not detail['all_boot_settings_writes']
            calls=[c for c in detail['calls']if c['op']==257]
            assert len(calls)==1 and calls[0]['return_step'] and calls[0]['word']==2
            assert first['W_T']==0
            initial=snapshot(d['first_menu_snapshot'])
            assert not any(x['cmd']==22 for x in rpc(initial)['log'])
            del initial
            row['release_BOOT_zero_write']=True
    row.update(status='PASS',backend=d['backend'],DAT_sha256=C.sha(raw))
    out.append(row)
C.save(C.HERE/'evidence/receipt_audit.json',dict(status='PASS',rows=out,
    boundary='Independent data/log audit of existing receipts. No old machine snapshot executed. New cold-start rerun is separate.'))
print(json.dumps(dict(status='PASS',rows=[{k:r[k]for k in ('profile','unit','restore','backend','status')}for r in out])))
