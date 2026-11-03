"""Drive original menu keys and retain native labels and complete S changes."""
import argparse
import json
from pathlib import Path
import signal
import struct
import sys
import traceback

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import Runtime,load_snapshot,TEMP,sha,module,models


def ascii_map(source):
    path=HERE/'local/r2-ascii-map.json'
    if path.exists():return json.loads(path.read_text())['codes']
    saved=load_snapshot(source);cpu=saved['cpu'];regs=cpu['registers']
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'));import python_backend as PB
    PB.CACHE=TEMP/'native-menu-font';b=PB.PythonBackend()
    for at,data,writable in cpu['regions']:b.map(at,data,writable)
    for key in ('psw','spi','spu','bpc','bbpc','evb',*[f'r{i}' for i in range(16)]):b.set_reg(key,regs[key])
    b.map(0x10000000,bytes(16384),True)
    stop=b.call(0x201dc180,[],0x7ffffff0,10000);assert stop.reason=='return';language=b.get_reg('r0')
    codes={}
    for value in range(32,127):
        b.write(0x10000000,bytes([value,0]));b.write(0x10001000,bytes(128))
        for i,v in enumerate((0x10000000,1,0x10001000,language),4):b.set_reg('r'+str(i),v)
        stop=b.call(0x201d73e0,[],0x7ffffff0,20000);assert stop.reason=='return'
        glyph=b.read(0x10001000,2).hex();codes.setdefault(glyph,chr(value))
    path.write_text(json.dumps(dict(language=language,codes=codes,source_sha256=sha(source.read_bytes())),indent=2)+'\n')
    return codes


def native_view(r,codes):
    def word(at):return r.u(at)
    rows=r.u(0x2022f5ac,1);table=word(0x2022f5a8);labels=[]
    count=r.u(0x205a27d4,1);array=word(0x205a27d8);views=[]
    if count<=8 and 0x20000000<=array<0x20800000-count*8:
        for index in range(count):
            tag=r.u(array+8*index,1);obj=word(array+8*index+4)
            views.append(dict(tag=tag,object=hex(obj),prefix=r.cpu.read(obj,32).hex()
                if 0x20000000<=obj<0x20800000-32 else None))
    if (views and views[-1]['tag']==33 and (views[-1]['prefix'] or '').startswith('05')
            and 0<=rows<=32 and 0x20000000<=table<0x20800000-4*rows):
        for index in range(rows):
            obj=word(table+4*index);label=dict(row=index+1,object=hex(obj))
            try:
                pointer=word(obj)
                if not 0x20000000<=pointer<0x20800000-256:raise ValueError('not a text pointer')
                raw=r.cpu.read(pointer,256);parts=[];units=[]
                for i in range(0,256,2):
                    pair=raw[i:i+2]
                    if pair==b'\0\0':break
                    code=pair.hex();units.append(code);parts.append(codes.get(code,'{'+code+'}'))
                label.update(text=''.join(parts),codes=units,pointer=hex(pointer))
            except Exception as exc:label['read_note']=type(exc).__name__
            labels.append(label)
    S=word(0x200c0dac);block=r.cpu.read(S,4096)
    return dict(step=r.cpu.steps,state=word(0x205d9c00),activity=word(0x205d9bf8),
        native_kind=r.u(0x2022f71c,1),rows=rows,cursor=r.u(0x2022f726,1),
        part=r.u(0x205a280f,1),labels=labels,active_views=views,
        original_text_available=any(x.get('text') for x in labels),
        main_menu=dict(kind=r.u(0x2022f28c,1),page=r.u(0x2022f394,1),row=r.u(0x2022f395,1),
            section=r.u(0x2022f398,1)),
        original_menu_rows=dict(WB=r.u(0x205d9e24,1),WB_compensation=r.u(0x205d9e25,1)),
        WB_editor=r.cpu.read(0x2037f38d,4).hex(),
        selector=block[0x36e],source=block[8],
        WB_offsets=list(block[0x6dd:0x6df]),S740=block[0x740],
        WB_presets=dict(still=block[0x395],movie=block[0x605]),
        WB_range=block[0x6d0:0x6e8].hex(),record=block[0xfd4:0xffc].hex(),S_sha256=sha(block))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--name',required=True)
    p.add_argument('--engine',choices=('g154','g155c','native'),default='g155c')
    p.add_argument('--keys',default='MENU');p.add_argument('--settle',type=int,default=0)
    p.add_argument('--wb-preset',choices=('auto','daylight'))
    p.add_argument('--shoot-row',choices=('wb-compensation',))
    a=p.parse_args();engine=None if a.engine=='native' else ROOT/'firmware'/('engine_v63_g154' if a.engine=='g154' else 'engine_v67_g155c')
    elf=None if engine is None else engine/('candidate/local/full-r13/engine.elf' if a.engine=='g154' else 'candidate/local/boot-on/engine.elf')
    out=HERE/'evidence'/(a.name+'.json');assert not out.exists()
    models();module('r2_menu_notice',HERE/'emulator/menu_notice_peer.py')
    import panel
    panel.KEY_CODES['FN2']=22
    codes=ascii_map(a.source)
    r=Runtime(a.source,a.name,engine,elf);S=r.u(0x200c0dac);writes=[];setters=[]
    for address,label in ((0x20266c58,'WB-preset'),(0x2026e5bc,'WB-compensation-first-axis'),
                          (0x2026e5c8,'WB-compensation-second-axis')):
        def entered(cpu,address=address,label=label):
            row=dict(step=cpu.steps,entry=hex(address),name=label,
                value=cpu.get_reg('r4'),caller=hex(cpu.get_reg('lr')))
            setters.append(row)
            if label=='WB-preset':row['input_snapshot']=r.save('native-WB-input-'+str(len(setters)))
            return False
        r.cpu.add_breakpoint(address,entered)
    from r2_menu_notice import MenuNoticePeer
    peer=r.machine.devices['startup'];prior=peer.standby_model
    current=MenuNoticePeer(prior.unit,dict(prior.inputs));current.events=prior.events;current.sequence=prior.sequence
    peer.standby_model=current
    r.cpu.add_write_trace(S,S+4096,lambda at,data:writes.append(dict(step=r.cpu.steps,pc=hex(r.cpu._pc),offset=at-S,data=bytes(data).hex())))
    result=dict(status='OPEN',source=str(a.source),source_sha256=sha(a.source.read_bytes()),dat_sha256=r.saved['dat_sha256'],
        native_state_presets=[],camera_setting_writes_by_runner=0,keys=[],views=[],S_writes=writes,native_setters=setters,
        layer='实际 GPIO 经原厂菜单路径；字形用原厂转换器建立的 ASCII 对照读取')
    original_run=r.run;last_progress=[r.cpu.steps]
    def progress_run(count):
        stop=original_run(count)
        if r.cpu.steps-last_progress[0]>=50_000_000:
            last_progress[0]=r.cpu.steps
            print(json.dumps(dict(name=a.name,step=r.cpu.steps,state=r.u(0x205d9c00),
                activity=r.u(0x205d9bf8),pc=hex(r.cpu.get_reg('pc')),
                pending=[x['name'] for x in r.pending])),flush=True)
        return stop
    r.run=progress_run
    send_key=r.key
    signal.alarm(10800)
    try:
        result['views'].append(native_view(r,codes));previous=r.cpu.read(S,4096)
        def press(key):
            nonlocal previous
            index=len(result['keys'])+1
            send_key(key);view=native_view(r,codes);current=r.cpu.read(S,4096)
            view['changed_bytes']=[dict(offset=i,before=x,after=y) for i,(x,y) in enumerate(zip(previous,current)) if x!=y]
            view['snapshot']=r.save('key-'+str(index)+'-'+key.lower());view['settings']=r.settings('key-'+str(index)+'-'+key.lower())
            result['keys'].append(key);result['views'].append(view);previous=current
            print(json.dumps(dict(name=a.name,key=key,state=view['state'],activity=view['activity'],kind=view['native_kind'],
                cursor=view['cursor'],rows=view['rows'],selector=view['selector'],WB_offsets=view['WB_offsets'],WB_presets=view['WB_presets'],
                part=view['part'],main_menu=view['main_menu'],active_views=view['active_views'],WB_editor=view['WB_editor'],
                labels=[x.get('text','')[:100] for x in view['labels'][:16]]),ensure_ascii=False),flush=True)
        if a.shoot_row:
            if r.u(0x205d9c00)!=9:press('MENU')
            for _ in range(6):
                if r.u(0x205d9c00)==9:break
                r.run(10_000_000)
            assert r.u(0x205d9c00)==9 and r.u(0x2022f28c,1)==0
            target=r.u(0x205d9e25,1)
            assert 1<=target<=40,'The native WB compensation row is unavailable.'
            result['native_target_row']=target
            if r.u(0x2022f395,1)==1 and target>2:
                press('UP')
                if r.u(0x2022f28c,1)!=0:press('DOWN')
                assert r.u(0x205d9c00)==9 and r.u(0x2022f28c,1)==0
            visited=set()
            for _ in range(50):
                if r.u(0x2022f395,1)==target:break
                current=(r.u(0x2022f395,1),r.u(0x2022f398,1))
                assert current not in visited,'The native WB compensation row is not reachable.'
                visited.add(current)
                press('UP' if current[0]>target else 'DOWN')
            assert r.u(0x2022f395,1)==target
            press('RIGHT')
            r.run(20_000_000)
            result['views'].append(native_view(r,codes))
            for key in filter(None,a.keys.split(',')):press(key)
        elif a.wb_preset:
            def is_wb():return r.u(0x205d9c00)==56 and r.u(0x205d9bf8)==2 and r.u(0x2022f71c,1)==1
            if r.u(0x205d9c00)==56 and not is_wb():press('OK')
            if not is_wb():press('ADJ')
            for _ in range(5):
                if is_wb():break
                press('ADJ_RIGHT')
            assert is_wb(),'The original WB preset menu was not reached.'
            target=1 if a.wb_preset=='auto' else 3
            for _ in range(12):
                cursor=r.u(0x2022f726,1)
                if cursor==target:break
                press('DOWN' if cursor<target else 'UP')
            assert r.u(0x2022f726,1)==target
            press('OK')
            for _ in range(8):
                if r.u(0x205d9c00)==5:break
                r.run(10_000_000)
            assert r.u(0x205d9c00)==5,'The native WB selection did not return to shooting.'
            expected=0 if a.wb_preset=='auto' else 1
            assert r.cpu.read(S+0x395,1)==bytes([expected]),'The native WB preset store did not match the selected row.'
            result.update(selected_WB_preset=a.wb_preset,selected_WB_row=target,expected_WB_byte=expected)
        else:
            for key in filter(None,a.keys.split(',')):press(key)
        if a.settle:r.run(a.settle);result['views'].append(native_view(r,codes))
        result.update(status='OBSERVED',snapshot=r.save('final'),settings=r.settings('final'))
    except BaseException as exc:
        result.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc(),snapshot=r.save('stopped'))
        raise
    finally:
        signal.alarm(0);result['final']=native_view(r,codes);result.update(inputs=r.inputs,calls=r.calls)
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');r.machine.close()


if __name__=='__main__':main()
