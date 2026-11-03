"""Locate the first missing font/raster dependency below glyph submission.

This is deliberately incomplete: only a framebuffer and genuine font metrics
are provided. Missing bitmap/cache/OS behavior must fault or remain explicitly
unresolved, never be replaced by successful empty drawing.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import native_modules, save, sha
from text_probe import resources, encoded_at


def main():
    image_loader, _, harness = native_modules()
    h = harness.Harness(body=image_loader.OFFICIAL)
    h.quiet_trace = True
    arena, framebuffer = 0x20680000, 0x21000000
    h.b.map(arena, bytes(0x10000))
    h.b.map(framebuffer, b'\x77'*(640*480))
    font, metrics, _, _ = resources(h.image)
    h.b.write(0x205cc84c, font[metrics:])
    for group in range(1, 32):
        h.put(0x205c2c88+4*group, 0x205cc84c+1024*(group-1))
    text = 'DISP:Tw'
    h.b.write(arena, text.encode('ascii')+b'\0')
    h.invoke(0x201d73e0, (arena, len(text), arena+0x100, 1))
    glyphs = encoded_at(h, arena+0x100)
    style = arena+0x200
    h.b.write(style, bytes(24))
    h.put(style, 223, 2)
    h.put(style+2, 100, 2)
    h.put(style+4, 8, 1)
    h.put(style+8, arena+0x100)
    for offset, value in ((12,3),(14,2),(16,2),(18,2)):
        h.put(style+offset, value, 2)
    h.b.breakpoints.pop(0x201d7170)
    h.stub(0x201be074, 'model_layer_framebuffer', value=framebuffer)
    writes = []
    h.b.add_write_trace(framebuffer, framebuffer+640*480,
        lambda event: writes.append(dict(address=hex(event.address), bytes=len(event.data),
                                         pc=hex(event.pc) if event.pc else None)))
    for index, value in enumerate((2, style)):
        h.b.set_reg('r'+str(4+index), value)
    stop = h.b.call(0x201d7170, (), harness.END, 300000)
    record = dict(status='INCOMPLETE_RASTER_ENVIRONMENT',
        text=text, glyph_sha256=sha(glyphs), native_stop=dict(reason=stop.reason,
        pc=hex(stop.pc), steps=stop.steps, detail=stop.detail),
        framebuffer_model=True, genuine_font_metrics_loaded=True,
        font_bitmap_and_cache_loaded=False, glyph_draw_stub_removed=True,
        changed_framebuffer_writes=len(writes),
        scope='A returned call or framebuffer writes cannot prove correct glyph pixels '
              'without the missing bitmap/cache environment and independent expected pixels.')
    save('raster-boundary.json', record)
    save('local/raster-boundary-raw.json', dict(result=record, writes=writes,
        instruction_tail=[dict(pc=hex(pc), assembly=asm) for pc,asm in h.b.tail],
        stub_hits=h.stub_hits))
    print(record['status'], record['native_stop'], 'framebuffer writes', len(writes))


if __name__ == '__main__':
    main()
