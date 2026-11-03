#!/usr/bin/env python3
"""Reproducible report tables, read-only inputs, no native firmware execution."""
import argparse
import csv
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('mine', HERE / 'mine.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

REPORTS = [
    'isp_pipeline/REPORT.md', 'beyond24/REPORT.md',
    'capability_ladder/REPORT.md', 'channel_mixing/REPORT.md',
    'split_tone/REPORT.md', 't_persistence/REPORT.md', 't_recovery/REPORT.md',
    'hidden_processing/REPORT.md', 'fidelity_ceiling/fuji/REALISTIC.md',
    'gr4_lut_ceiling/REPORT.md', 'body_lut/REPORT.md', 'body_lut_r2/REPORT.md',
    'gr_firmware/REPORT.md', 'gr_complete_pipeline/REPORT.md',
    'frame_gr2/color_pipeline/REPORT.md', 'bw_and_base_modes/REPORT.md',
]
EXTRA_DIRS = ['hue_ring', 'tone_curve', 'contrast_curve', 'multi_module', 'module_adapt']

URLS = {
    'gxr_image_settings': 'https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/docs10/EDXR01012.html',
    'p10_dr_double_shot': 'https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/docs10/EDXR03019.html',
    'a16_a12_comparison': 'https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/06/gxr06000.html',
    'mount_shooting_menu': 'https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/08/gxr08099.html',
    'gxr_firmware': 'https://www.ricoh-imaging.co.jp/english/products/gxr/firmware.html',
    'grd4_image_settings': 'https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/grd4/gr04404.html',
}

def inputs():
    paths = [m.ROOT / 'research' / p for p in REPORTS]
    for rel in EXTRA_DIRS:
        paths.extend(sorted((m.ROOT / 'research' / rel).glob('*.md')))
    paths += [m.ROOT / 'research/isp_pipeline/register_layouts.json',
              m.ROOT / 'research/isp_pipeline/analyze.py',
              m.ROOT / 'research/bw_and_base_modes/facts.py', m.ARCHIVE, m.OBJDUMP]
    entries = {str(p.relative_to(m.ROOT)): dict(size=p.stat().st_size,
              sha256=m.sha(p.read_bytes())) for p in paths}
    m.save(m.EVIDENCE / 'read-inputs.json', dict(
        observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='Snapshot at report preparation; not a claimed pre-session repository baseline.',
        inputs=entries))
    print('Input snapshot:', len(entries), 'files')

def tables():
    drivers = json.loads((m.EVIDENCE / 'cross-unit-drivers.json').read_text())
    path = m.EVIDENCE / 'all39-writers.csv'
    with path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['image', 'type', 'writer_vma', 'writer_file_offset', 'descriptor_vma',
                    'descriptor_file_offset', 'payload_u32_count', 'registers_in_payload_order'])
        for name, info in drivers.items():
            im = m.Image(name)
            assert [r['type'] for r in info['entries']] == list(range(39))
            for r in info['entries']:
                w.writerow([name, r['type'], r['writer'], hex(im.offset(int(r['writer'], 16))),
                            r['descriptor'], r['descriptor_file_offset'],
                            r['payload_u32_count'], ' '.join(r['registers'])])
    precision = dict(
        q10_step=1/1024, q10_sign_magnitude_max=2047/1024,
        q10_max_magnitude_before_160_percent_overflow=2047*100//160,
        sector_q5_step=1/32, sector_q5_sign_magnitude_max=127/32,
        c040_angle_step_degrees=360/256,
        lut8_output_step=1/255, lut12_output_step=1/4095,
        lut12_vs_lut8_levels=4095/255,
        shading_q10_step=1/1024, shading_13bit_max=8191/1024,
        required_remaining_error_reduction={str(s): 1-0.05/(1-s)
                                            for s in (.87, .83, .52, .66)},
        gr4_old_baseline_median_de00=[3.841,4.168],
        gr4_95_percent_threshold_de00=[3.841*.05,4.168*.05],
        caveat='Arithmetic from encoding and user-supplied score only; no new image evaluation or device measurement.')
    m.save(m.EVIDENCE / 'precision-and-target.json', precision)
    # Native P10 packer independently observed groups, not claimed pixel semantics.
    groups = [
        ('threshold32', 4, 'u32', 8, [4]),
        ('threshold16', 8, 'u16', 9, [0x24]),
        ('group_A_inputs', 0xC, 'u16', 16, [0x38,0x98,0xF8,0x158]),
        ('group_A_outputs', 0x10, 'u32', 16, [0x58,0xB8,0x118,0x178]),
        ('group_B_inputs', 0x14, 'u16', 16, [0x1B8,0x218,0x278,0x2D8]),
        ('group_B_outputs', 0x18, 'u32', 16, [0x1D8,0x238,0x298,0x2F8]),
        ('group_C_outputs', 0x1C, 'u32', 16, [0x338,0x398,0x3F8]),
        ('group_C_inputs', 0x20, 'u16', 16, [0x378,0x3D8,0x438]),
    ]
    m.save(m.EVIDENCE/'p10-wdr-packer-layout.json', dict(
        image='nlaunch3', writer_vma='0x2011a280', mirror_vma='0x20144c64',
        descriptor_success_field=1, groups=[dict(name=n,source_pointer_offset=hex(o),
            source_type=t,source_count=c,destination_offsets=[hex(a) for a in ds])
            for n,o,t,c,ds in groups],
        caveat='A/B/C are labels for copy groups, not RGB or luma labels. u16 data packed into BE u32.'))
    print('Derived tables:', path.name, 'precision-and-target.json, p10-wdr-packer-layout.json')

def download(item):
    name, url = item
    target = m.LOCAL / 'sources' / (name+'.html')
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'GXR-read-only-research/1.0'})
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read(4_000_000)
            assert response.headers.get_content_type() == 'text/html'
            assert len(data) < 4_000_000
            meta = dict(url=url, final_url=response.url, status=response.status,
                        size=len(data), sha256=m.sha(data), saved=str(target.relative_to(HERE)))
        target.write_bytes(data)
        return name, meta
    except Exception as e:
        return name, dict(url=url, error=f'{type(e).__name__}: {e}')

def web():
    with ThreadPoolExecutor(max_workers=6) as pool:
        items = dict(pool.map(download, URLS.items()))
    m.save(m.EVIDENCE/'public-sources.json', dict(
        accessed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=items))
    for k,v in items.items(): print(k, v.get('status', v.get('error')), v.get('sha256',''))

def windows():
    jobs = [
        ('nlaunch3',0x2011B738,0x2011CBFC,'p10-wdr-generator-full'),
        ('nlaunch3',0x201A07E0,0x201A08A8,'p10-effect15-candidate'),
        ('ilaunch3',0x200F7B74,0x200F7D38,'body-mcm-getters'),
        ('ilaunch3',0x2016583C,0x20165AA0,'body-jpeg-wrapper'),
        ('ilaunch3',0x203ED714,0x203ED774,'body-jpeg-dma-submit'),
        ('ilaunch3',0x203F20D0,0x203F2290,'body-jpeg-dma-format'),
    ]
    for name,a,b,label in jobs: print(m.Image(name).window(a,b,label))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('command', choices=['inputs','tables','web','windows'])
    args=p.parse_args()
    globals()[args.command]()
