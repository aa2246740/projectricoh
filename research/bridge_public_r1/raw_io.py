"""Read-only DNG adapters; upstream parsers are frozen and never edited."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
from common import np
import hashlib
import types


def dng_module():
    m = c.module('public_bridge_dng_scene', 'research/color_table_fit/dng_scene.py')
    patch = c.module('public_bridge_tiff_adapter', 'research/chart_session_20261024/session_runtime.py')
    patch.patch_tiff(m.analyze_capture().Tiff)
    return m


def tags(path):
    m = dng_module(); t = m.analyze_capture().Tiff(c.inp(path).read_bytes())
    root = t.ifd(t.root)
    candidates = [root] + [t.ifd(v) for v in root.get(330, {}).get('value', [])]
    raw = next(v for v in candidates if v.get(262, {}).get('value', [None])[0] == 32803)
    return {k: v['value'] for k,v in {**root, **raw}.items()}


class RawDng:
    """Frozen upstream CFA methods, with a local lossless-JPEG input adapter."""
    def __init__(self,path):
        self._module=dng_module();self.path=c.inp(path);self.data=self.path.read_bytes()
        self.sha256=hashlib.sha256(self.data).hexdigest()
        t=self._module.analyze_capture().Tiff(self.data);root=t.ifd(t.root)
        nodes=[root]+[t.ifd(v) for v in root.get(330,{}).get('value',[])]
        raw=next(v for v in nodes if v.get(262,{}).get('value',[None])[0]==32803)
        self.compression=int(raw.get(259,{}).get('value',[1])[0])
        if self.compression==1:
            original=self._module.Dng(self.path);self.__dict__.update(original.__dict__)
            self.compression=1;return
        assert self.compression==7, f'unsupported raw compression {self.compression}'
        def val(tag,default=None):return raw.get(tag,root.get(tag,{})).get('value',default)
        self.width=int(val(256)[0]);self.height=int(val(257)[0]);self.bps=int(val(258)[0])
        self.endian='little' if t.endian=='<' else 'big'
        self._strips=(val(273),val(279));self._tiles=(val(324),val(325))
        self._tile_width=int(val(322,[self.width])[0]);self._tile_height=int(val(323,[self.height])[0])
        self.cfa=np.array(list(val(33422)),int).reshape(list(val(33421,[2,2])))
        assert sorted(set(self.cfa.ravel()))==[0,1,2]
        self.active=tuple(int(v) for v in val(50829,[0,0,self.height,self.width]))
        self.crop_origin=tuple(int(v) for v in val(50719,[0,0]))
        self.crop_size=tuple(int(v) for v in val(50720,[self.width,self.height]))
        self.default_scale=tuple(val(50718,[1.,1.]));self.orientation=int(val(274,[1])[0])
        self.lin_table=np.array(val(50712)) if val(50712) is not None else None
        dim=val(50713,[1,1]);bl=np.array(val(50714,[0.]),float)
        if bl.size==1:bl=np.full(int(np.prod(dim)),bl[0])
        self.black_pattern=bl.reshape(dim)
        self.black_dh=np.array(val(50715)) if val(50715) is not None else None
        self.black_dv=np.array(val(50716)) if val(50716) is not None else None
        self.white=float(val(50717,[(1<<self.bps)-1])[0])
        self.as_shot_neutral=np.array(val(50728),float)
        self.as_shot_white_xy=np.array(val(50729),float) if val(50729) is not None else None
        def mat(tag):return np.array(val(tag),float).reshape(3,3) if val(tag) is not None else None
        self.color_matrix=[mat(50721),mat(50722)];self.camera_calibration=[mat(50723),mat(50724)]
        self.forward_matrix=[mat(50964),mat(50965)]
        self.illuminant=[int(val(50778,[0])[0]),int(val(50779,[0])[0])]
        self.analog_balance=np.array(val(50727,[1.,1.,1.]))
        self.baseline_exposure=float(val(50730,[0.])[0]);self.exif={}
        if 34665 in root:
            ex=t.ifd(root[34665]['value'][0])
            for tag,name in [(34855,'iso'),(33434,'t'),(33437,'f')]:
                if tag in ex:self.exif[name]=ex[tag]['value'][0]
        self._mosaic=None

    def __getattr__(self,name):
        method=getattr(self._module.Dng,name,None)
        if method is None:raise AttributeError(name)
        return types.MethodType(method,self)

    def mosaic(self):
        if self._mosaic is not None:return self._mosaic
        if self.compression==1:return self._module.Dng.mosaic(self)
        import imagecodecs
        offsets,counts=self._tiles if self._tiles[0] is not None else self._strips
        assert offsets is not None and counts is not None
        if self._tiles[0] is None:
            assert len(offsets)==1, 'multiple lossless-JPEG strips need explicit row accounting'
            blob=self.data[offsets[0]:offsets[0]+counts[0]]
            raw=imagecodecs.ljpeg_decode(blob)
            assert raw.size==self.width*self.height
            self._mosaic=raw.reshape(self.height,self.width)
        else:
            self._mosaic=np.zeros((self.height,self.width),np.uint16)
            per_row=(self.width+self._tile_width-1)//self._tile_width
            for i,(off,count) in enumerate(zip(offsets,counts)):
                decoded=imagecodecs.ljpeg_decode(self.data[off:off+count])
                tile=decoded.reshape(-1,self._tile_width)
                y=(i//per_row)*self._tile_height;x=(i%per_row)*self._tile_width
                hh=min(tile.shape[0],self.height-y);ww=min(self._tile_width,self.width-x)
                self._mosaic[y:y+hh,x:x+ww]=tile[:hh,:ww]
        return self._mosaic


if __name__ == '__main__':
    p = c.inp('artifacts/downloads/dpreview-gxr-a12-studio/studio_iso200.DNG')
    d = dng_module().Dng(p)
    c.dump('gxr_metadata.json', d.summary())
    print('GXR', d.width, d.height, 'bits',d.bps,'crop',d.crop_window(),
          'black',d.black_pattern.tolist(),'white',d.white,'neutral',d.as_shot_neutral.tolist())
    print('mosaic',d.mosaic().shape)
