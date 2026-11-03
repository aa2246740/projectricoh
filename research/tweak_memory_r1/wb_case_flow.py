"""Compare HC BW restart after a WB selection produced by native GPIO input."""
import argparse
import json
from pathlib import Path
import struct
import sys
import traceback
import zlib

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from repro_flow import phase
from runtime import sha,load_snapshot


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version',choices=('g154','g155c'),required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--wb-evidence',type=Path,required=True)
    p.add_argument('--prefix',required=True)
    a=p.parse_args();old=a.version=='g154';prefix=a.prefix
    engine=ROOT/'firmware'/('engine_v63_g154' if old else 'engine_v67_g155c')
    elf=engine/('candidate/local/full-r13/engine.elf' if old else 'candidate/local/boot-on/engine.elf')
    dat=ROOT/('firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT' if old else 'firmware/package_v310_g155c_test/GXRCE.DAT')
    image=ROOT/('firmware/package_v39_g154_test/local/SD_ROOT/ilaunch3' if old else 'firmware/image_v310/local/ilaunch3')
    common=['--engine',engine,'--elf',elf];rows=[]
    out=HERE/'evidence'/(prefix+'-flow.json');assert not out.exists()
    evidence=json.loads(a.wb_evidence.read_text());assert evidence['status']=='OBSERVED'
    assert evidence['camera_setting_writes_by_runner']==0 and evidence['keys']
    assert evidence['snapshot']['sha256']==sha(a.source.read_bytes())
    saved=load_snapshot(a.source)
    assert saved['dat_sha256']==sha(dat.read_bytes()) and saved['body_sha256']==sha(image.read_bytes())
    wb=evidence['final']['WB_presets']['still']
    assert wb==1,'The source must contain the native daylight selection.'
    assert any(row['name']=='WB-preset' and row['value']==wb for row in evidence['native_setters']), 'No native WB setter call was observed.'
    assert any(change['offset']==0x395 and change['after']==wb and change['before']!=wb
        for view in evidence['views'] for change in view.get('changed_bytes',[])), 'No actual WB preset change was observed.'
    result=dict(status='OPEN',version=a.version,phases=rows,dat_sha256=sha(dat.read_bytes()),
        native_WB_evidence=str(a.wb_evidence.relative_to(ROOT)),native_WB_evidence_sha256=sha(a.wb_evidence.read_bytes()),
        WB_preset_before=wb,native_state_presets=[],camera_setting_writes_by_runner=0,
        persistence_layer='Actual native-menu S bytes replayed at settings read; real shutdown NAND remains OPEN.')
    def run(script,args,suffix,backend='c'):
        phase(script,args,prefix+'-'+suffix+'-run',rows,backend)
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    def read(suffix):return json.loads((HERE/'evidence'/(prefix+'-'+suffix+'.json')).read_text())
    def probe(mode,source,suffix):
        run('probe.py',['--source',source,*common,'--mode',mode,'--name',prefix+'-'+suffix,
            '--kind','builtin','--number',3],suffix)
        return HERE/'local'/(prefix+'-'+suffix+'-final.pkl.z')
    try:
        if old:
            source=a.source
            result['manual_source_reused']=dict(snapshot=str(a.source.relative_to(ROOT)),
                reason='The source already contains a completed manual HC BW and three nonzero controls; only the native WB preset was changed.')
        else:
            source=probe('choose',a.source,'choose')
            source=probe('tweak-only',source,'controls')
        run('accept.py',['--source',source,*common,'--name',prefix+'-manual-accept'],'manual-accept')
        manual=read('manual-accept');assert bytes.fromhex(manual['record'])[5]==3
        target=HERE/'local'/(prefix+'-manual-accept-target.bin')
        if old:
            assert evidence['final']['state']==5
            settings=ROOT/evidence['settings']['persistent_path']
        else:
            source=probe('exit',source,'exit')
            exit_data=read('exit');settings=ROOT/exit_data['settings']['persistent_path']
        block=settings.read_bytes();assert block[0x395]==wb
        run('cold_run.py',['--name',prefix+'-cold','--unit','mount','--dat',dat,'--image',image,
            '--settings-source',settings,'--budget',650000000,'--timeout',7200],'cold')
        cold=HERE/'local'/(prefix+'-cold-session.pkl.z')
        after=(HERE/'local'/(prefix+'-cold-S.bin')).read_bytes()
        record=after[0xfd4:0xffc]
        assert record.hex()==manual['record']
        assert zlib.crc32(record[:36])==int.from_bytes(record[36:],'big')
        assert record[28:36]==dat.read_bytes()[20:28] and after[0x395]==wb
        result.update(record_40B_equal=True,CRC_equal=True,DAT_pair_equal=True,
            record_levels=list(struct.unpack('>10h',record[8:28])),WB_preset_after_cold=after[0x395],
            WB_offsets_after_cold=list(after[0x6dd:0x6df]))
        if not old:
            run('accept.py',['--source',cold,*common,'--expected',target,'--name',prefix+'-cold-accept'],'cold-accept')
        source=probe('inspect',cold,'menu')
        menu=read('menu');assert menu['first_controls']['levels']==manual['levels']
        assert menu['first_controls']['engine_levels']==manual['levels']
        assert menu['open_menu_W_T']==0
        if not old:assert menu['first_menu']['levels']==manual['levels'] and menu['open_controls_W_T']==0
        run('accept.py',['--source',source,*common,'--expected',target,'--name',prefix+'-menu-accept'],'menu-accept')
        for backend in ('c','python'):
            for suffix,snapshot in [('first',HERE/'local'/(prefix+'-menu-first-menu.pkl.z')),('controls',source)]:
                run('glyphs.py',['--source',snapshot,*common,'--name',prefix+'-'+suffix+'-glyphs'],suffix+'-glyphs-'+backend,backend)
                glyph=json.loads((HERE/'evidence'/(prefix+'-'+suffix+'-glyphs-'+backend+'.json')).read_text())
                if suffix=='first':assert 'HC BW' in glyph['selected_text']
        result.update(status='PASS',menu_levels=menu['first_menu']['levels'],
            control_levels=menu['first_controls']['levels'],open_controls_W_T=menu['open_controls_W_T'])
    except BaseException as exc:
        result.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
        raise
    finally:out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
