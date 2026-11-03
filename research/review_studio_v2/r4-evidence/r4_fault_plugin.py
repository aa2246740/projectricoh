import inspect,io,os
import numpy as np
from PIL import Image

def pytest_configure(config):
 fault=os.environ['R4_REINTRODUCE_FAULT']
 if fault=='decode_without_exif':
  from gxr_studio.finish import serve
  def unrotated(jpeg):
   with Image.open(io.BytesIO(jpeg)) as image:return np.asarray(image.convert('RGB'))
  serve._decode=unrotated
 elif fault=='stamp_floor_8':
  from gxr_studio.finish import stamp
  source=inspect.getsource(stamp.apply_stamp)
  assert 'px > 1:' in source
  exec(source.replace('px > 1:', 'px > 8:'),stamp.__dict__)
 else:raise AssertionError(fault)
