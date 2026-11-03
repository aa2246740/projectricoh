"""Render actual final menu states using the unchanged r1 host scene inputs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import support as s
s.dependencies()
import csv
import hashlib
import json
import shutil
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
import menu
from model_adapter import Model, masks
from verify import CMenu, write_csv

NAMES = {'amount':'强度', 'contrast':'对比', 'highlight':'高光', 'shadow':'阴影', 'fade':'褪黑',
         'saturation':'饱和', 'warmth':'冷暖', 'tint':'品绿', 'split':'分离色调', 'filter':'黑白滤镜'}


def display_levels(item):
    levels = [p['level'] for p in item['points']]
    if len(levels) <= 7:
        return levels
    selected = {levels[round(i*(len(levels)-1)/6)] for i in range(7)}
    selected.add(item['default_level'])
    return sorted(selected)


def main():
    s.guard()
    s.verify_inputs()
    start = time.monotonic()
    data, modules, model = menu.load(), s.parse(), Model()
    cm = CMenu(build=False)
    r1local = s.ROOT / 'research/knobs_v2_r1/local'
    scenes = json.loads((r1local / 'scenes.json').read_text())
    s.dump(s.LOCAL / 'scenes.json', scenes)
    images, samples = {}, {}
    for scene in scenes:
        filename = scene['id'] + '_input.npz'
        shutil.copyfile(r1local / filename, s.LOCAL / filename)
        with np.load(s.LOCAL / filename, allow_pickle=False) as z:
            x, size = z['x'].copy(), tuple(z['size'])
        images[scene['id']] = x, size
        yy = np.linspace(0, size[1]-1, 43).round().astype(int)
        xx = np.linspace(0, size[0]-1, 64).round().astype(int)
        samples[scene['id']] = x.reshape(size[1], size[0], 3)[yy[:, None], xx[None, :]].reshape(-1, 3)
    folder = s.LOCAL / 'previews'
    folder.mkdir(exist_ok=True)
    font = '/System/Library/Fonts/Supplemental/Songti.ttc'
    title_font, text_font = ImageFont.truetype(font, 24), ImageFont.truetype(font, 17)
    index, frames, scene_metrics = [], [], []
    for recipe in data['recipes']:
        unit, slot = recipe['unit'], recipe['slot']
        module = modules[unit]
        stock, base = module['entries'][4], module['entries'][slot]
        items = data['items'][recipe['first_item']:recipe['first_item']+recipe['item_count']]
        defaults = [a['default_level'] for a in items]
        for i, item in enumerate(items):
            param = data['controls'][item['control']]['name']
            display = display_levels(item)
            sheet = Image.new('RGB', (196*len(display), 772), '#f4f2ed')
            draw = ImageDraw.Draw(sheet)
            title = f'电脑预测 | {module["name"]} {slot:02d} {NAMES[param]}'
            draw.text((10, 7), title, font=title_font, fill='#171b19')
            note = '固定 A12-50 ISO200 模型；曝光与白平衡固定；! 表示该方向提前到顶。'
            if unit:
                note = '跨单元电脑预测，尚未实测标定。! 表示该方向提前到顶。'
            draw.text((10, 43), note, font=text_font, fill='#414740')
            filename = f'{module["name"]}-{slot:02d}-{param}.png'
            outputs = {}
            for point in item['points']:
                levels = defaults.copy()
                levels[i] = point['level']
                outputs[point['level']] = cm.apply(unit, slot, levels, stock, base)[0]
            for row, scene in enumerate(scenes):
                sid = scene['id']
                x, size = images[sid]
                sample = samples[sid]
                regions = masks(model, base, sample, param)
                labs = {level:model.lab(model.predict(b, sample, quantize=True)) for level, b in outputs.items()}
                ordered = sorted(outputs)
                for a, b in zip(ordered, ordered[1:]):
                    de = model.de(labs[a], labs[b])
                    for region_num, region in enumerate(regions):
                        n = int(region.sum())
                        median = float(np.median(de[region])) if n >= 16 else None
                        scene_metrics.append(dict(unit=module['name'], slot=slot, param=param, scene=sid,
                                                  from_level=a, to_level=b, region=region_num, n=n,
                                                  median_de00=median, complete=n >= 16,
                                                  visible=median is not None and median >= 1.0))
                for col, level in enumerate(display):
                    rgb = model.predict(outputs[level], x, quantize=True)
                    image = Image.fromarray(rgb.reshape(size[1], size[0], 3), 'RGB')
                    px, py = col*196, 92+row*168
                    sheet.paste(image, (px, py))
                    bang = ('!' if (level == item['min_level'] and item['cap_lower']) or
                            (level == item['max_level'] and item['cap_upper']) else '')
                    label = f'{level}%' if param == 'amount' else f'{level:+d}{bang}'
                    draw.text((px+4, py+134), f'{sid} {label} 电脑预测', font=text_font, fill='#171b19')
                    if level == item['default_level']:
                        draw.rectangle((px, py, px+195, py+129), outline='#936b2d', width=2)
                    frames.append(dict(unit=module['name'], slot=slot, param=param, level=level, scene=sid,
                                       entry_sha256=hashlib.sha256(outputs[level]).hexdigest(),
                                       display_RGB_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(), sheet=filename))
            meta = PngImagePlugin.PngInfo()
            meta.add_itxt('Title', title)
            meta.add_itxt('Description', note)
            meta.add_itxt('Levels', json.dumps(display))
            sheet.save(folder / filename, pnginfo=meta)
            with Image.open(folder / filename) as im:
                assert '电脑预测' in im.info['Title'] and im.size == sheet.size
                im.verify()
            index.append(dict(unit=module['name'], slot=slot, param=param, path='local/previews/'+filename,
                              levels=json.dumps(display), width=sheet.width, height=sheet.height))
        print('previews', module['name'], f'{slot:02d}', len(index), f'{time.monotonic()-start:.1f}s', flush=True)
    write_csv(folder / 'index.csv', index)
    write_csv(s.LOCAL / 'scene_adjacent.csv', scene_metrics)
    s.dump(s.LOCAL / 'preview_frames.json', frames)
    s.dump(s.LOCAL / 'preview_verification.json', dict(PNGs=len(index), cells=len(frames),
           PNG_decode_and_label='PASS', scene_region_records=len(scene_metrics),
           scene_below_threshold=sum(r['complete'] and not r['visible'] for r in scene_metrics),
           scene_incomplete=sum(not r['complete'] for r in scene_metrics),
           computer_prediction_only=True, elapsed_seconds=time.monotonic()-start))
    s.dump(s.LOCAL / 'model_inputs_previews.json', model.provenance())
    s.verify_inputs()
    print('DONE', len(index), 'PNGs', len(frames), 'cells', flush=True)


if __name__ == '__main__':
    main()
