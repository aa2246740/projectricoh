"""Local target previews for the owner; no image content leaves local/."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    C.admit('render')
    C.numerical()
    C.sys.addaudithook(C.fence)
    from targets import Targets
    np = C.np
    targets = Targets()
    inventory = {r['id']:r for r in C.read(C.LOCAL / 'inventory.json')}
    bank = C.read(C.LOCAL / 'bank.json')['records']
    stock = Path(next(r['record'] for r in bank if r['name'] == '04 Std')).read_bytes()
    result = []
    for row in C.read(C.LOCAL / 'summary.json')['rows']:
        frame = C.LOCAL / 'frames' / row['id']
        with np.load(frame / 'preview-input.npz', allow_pickle=False) as z:
            raw = z['raw_codes']
        d = C.Dng(inventory[row['id']]['path'])
        xyz = C.scene_colour(d).xyz(raw.reshape(-1, 3))
        model = C.camera_model(row['metadata']['iso'], row['metadata']['color_raw13'])
        base = C.predict(model, stock, C.input_codes(raw.reshape(-1, 3)))
        old, support, details = targets.old_target(row['best'], raw.reshape(-1, 3), xyz, base)
        new, detail = targets.current_target(row['best'], raw.reshape(-1, 3), xyz, base, old)
        for tag, image in (('target-original', old), ('target-scene', new)):
            if image is not None:
                C.save_jpeg(frame / (tag + '.jpg'), image.reshape(raw.shape))
        result.append(dict(id=row['id'], original_target=old is not None, scene_target=new is not None,
                           smooth_patch_metrics_are_separate_from_coarse_previews=True))
        d.release()
    C.dump('rendered-targets.json', dict(frames=result, image_content_local_only=True,
        image_kind='256-pixel coarse CFA colour previews; no spatial ISP / demosaic simulation', created_utc=C.utc()))
    print('RENDER TARGETS', len(result), 'frames, local only', flush=True)


if __name__ == '__main__':
    main()
