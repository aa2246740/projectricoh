"""Reference pictures of the gen 147 pages for reading the camera photos: reference_P1A.svg, reference_P1B.svg,
reference_P2.svg (one cell per character, column numbers on top, row numbers on the left; a space is shown as a
dotted cell). The rows are the ones the DAT formats (checked byte for byte by accept_diag147.py, case full).

Usage: /usr/bin/python3 -I -B research/diag147/make_reference.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
CELL, TOP, LEFT = 28, 34, 34


def page(rows, title, columns):
    width, height = LEFT + CELL * columns + 10, TOP + CELL * len(rows) + 40
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Menlo, monospace">' % (width, height),
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<text x="%d" y="%d" font-size="13" fill="#333">%s</text>' % (LEFT, height - 12, escape(title))]
    for c in range(columns):
        out.append('<text x="%d" y="%d" font-size="11" fill="%s" text-anchor="middle">%d</text>' % (
            LEFT + CELL * c + CELL // 2, TOP - 10, '#c00' if c >= 8 else '#666', c))
    for r, text in enumerate(rows):
        y = TOP + CELL * r
        out.append('<text x="%d" y="%d" font-size="11" fill="#666" text-anchor="end">%d</text>' % (LEFT - 8, y + 19, r))
        for c in range(columns):
            x = LEFT + CELL * c
            ch = text[c] if c < len(text) else None
            stroke = '#c00' if c >= 8 else '#999'
            out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" stroke="%s" stroke-width="0.6"%s/>' % (
                x, y, CELL, CELL, '#f4f4f4' if ch is None else '#ffffff', stroke,
                ' stroke-dasharray="2,2"' if ch == ' ' else ''))
            if ch not in (None, ' '):
                out.append('<text x="%d" y="%d" font-size="18" text-anchor="middle">%s</text>' % (
                    x + CELL // 2, y + 20, escape(ch)))
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def main():
    a = ['P1A 0002'] + [''.join(chr(c) for c in range(0x20 + 8 * i, 0x28 + 8 * i)) for i in range(7)]
    b = ['P1B 0002'] + [''.join(chr(c) for c in range(0x58 + 8 * i, min(0x60 + 8 * i, 0x7f))) for i in range(5)] + \
        ['1234567890ABCDEFGHIJKLMNOPQRSTUV', 'MW' * 16]
    p2 = ['P2 K0 03', 'RES OK', 'B 25152', 'C 32768', 'T 41', 'F 23', 'N02 BZ01', 'ID06 L01']
    (HERE / 'reference_P1A.svg').write_text(page(a, 'P1A 0x20-0x57 (row 1 starts with a space)', 8))
    (HERE / 'reference_P1B.svg').write_text(page(b, 'P1B 0x58-0x7E; red = column 8+', 32))
    (HERE / 'reference_P2.svg').write_text(page(p2, 'P2 example (T/F/task vary)', 8))
    print('wrote 3 svg')


if __name__ == '__main__':
    main()
