"""Reference pictures of every gen 148 page, for reading the camera photos: reference/<nn>-<page>.svg.
One cell per character (8 columns), row numbers on the left, a space is a dotted cell, and a short legend per row
on the right. The rows are the ones the DAT formatted in the host acceptance (accept-full-50mm.json and
accept-pages-50mm.json, compared there byte for byte with an independent model). The numbers are harness-model
values (1 tick = 5000 instructions), not camera readings.

Usage: /usr/bin/python3 -I -B research/cpu_speed_probe/make_reference.py
"""
import json
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
OUT = HERE / 'reference'
CELL, TOP, LEFT, NOTE = 28, 34, 34, 300

TEST_LEGEND = ['测试名；E = 短片单位数的 log2（固定）', '3 组短片之和 最小 tick', '中位', '最大',
               '3 组长片（4 倍）之和 最小', '中位', '最大', 'R = 100×LM/SM（应约 400），标志']
LEGEND = {
    'SUM': ['探测与代号', 'DOWN=RUN / RUN n/9 / DONE 9/9', '单元名', '测量步数（每次上下键一步）',
            'ERR = 出错的测试数，SK = 被拒绝的打开次数', '标签', '时钟寄存器 0xFF000074（十六进制，实时）', '提示'],
    'REF': ['REF + 计过时的关页次数', '最近一次 打开到关页 毫秒', '上一次', '再上一次',
            '最近关页的键码（23 OK，2B ADJ）', '标签', '标签', ''],
    'STA': ['STA + 当前状态（十进制）', '历史 [0] 最新，[1]', '历史 [2]，[3]', '历史 [4]，[5]',
            '历史 [6]，[7]', '历史 [8]，[9] 最旧', 'SE：最近状态字节、事件码（十六进制）', '读法：从左到右、从上到下，由新到旧'],
    'STK': ['任务 26（保存任务）', '栈底地址（十六进制）', '栈大小，字节', '已用：栈顶减高水位',
            '剩余：标记字以上未碰过的字节', '栈底溢出标记 0x8C938D4F', '栈内为 0 的字数（不含标记）', '高水位地址（十六进制）'],
}


def page(rows, title, legend):
    width, height = LEFT + CELL * 8 + 16 + NOTE, TOP + CELL * len(rows) + 40
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Menlo, monospace">' % (width, height),
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<text x="%d" y="%d" font-size="13" fill="#333">%s</text>' % (LEFT, height - 12, escape(title))]
    for c in range(8):
        out.append('<text x="%d" y="%d" font-size="11" fill="#666" text-anchor="middle">%d</text>' % (
            LEFT + CELL * c + CELL // 2, TOP - 10, c))
    for r, text in enumerate(rows):
        y = TOP + CELL * r
        out.append('<text x="%d" y="%d" font-size="11" fill="#666" text-anchor="end">%d</text>' % (LEFT - 8, y + 19, r))
        for c in range(8):
            x = LEFT + CELL * c
            ch = text[c] if c < len(text) else None
            out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" stroke="#999" stroke-width="0.6"%s/>' % (
                x, y, CELL, CELL, '#f4f4f4' if ch is None else '#ffffff', ' stroke-dasharray="2,2"' if ch == ' ' else ''))
            if ch not in (None, ' '):
                out.append('<text x="%d" y="%d" font-size="18" text-anchor="middle">%s</text>' % (x + CELL // 2, y + 20, escape(ch)))
        if r < len(legend) and legend[r]:
            out.append('<text x="%d" y="%d" font-size="11" fill="#225">%s</text>' % (
                LEFT + CELL * 8 + 16, y + 18, escape(legend[r])))
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def main():
    full = json.loads((HERE / 'local/accept-full-50mm.json').read_text())
    pages = json.loads((HERE / 'local/accept-pages-50mm.json').read_text())['pages']
    OUT.mkdir(exist_ok=True)
    first = full['pages_before'][-1]
    shown = []
    shown.append(('00-SUM-start', first, 'SUM at the first open (before DOWN)', LEGEND['SUM']))
    done = full['segments'][-1]['rows']
    shown.append(('01-SUM-done', done, 'SUM after the last DOWN (host model; CLK value is a model)', LEGEND['SUM']))
    shown.append(('02-REF', full['ref_page'], 'REF after one OK close (host model ticks)', LEGEND['REF']))
    shown.append(('03-STA', pages['history fixture 5 2 0 56 5 2 1234 0 0 0']['rows'],
                  'STA with a test history 5 2 0 56 5 2 1234(>999) 0 0 0; 56 = menu open', LEGEND['STA']))
    shown.append(('04-STK', pages['stack: record 1/0x20461A00/16384, used 228']['rows'],
                  'STK with a test stack: 228 B used of 16384', LEGEND['STK']))
    shown.append(('05-STK-bad', pages['stack: record not in use']['rows'],
                  'STK when the task 26 record fails the checks', ['', '任务记录未通过检查', '读到的栈底', '读到的大小']))
    for i, t in enumerate(full['tests']):
        shown.append(('%02d-%s' % (6 + i, t['name']), t['rows'], '%s page after DONE (host model ticks)' % t['name'],
                      TEST_LEGEND))
    for name, rows, title, legend in shown:
        (OUT / (name + '.svg')).write_text(page(rows, title, legend))
    (OUT / 'pages.json').write_text(json.dumps([dict(file=n + '.svg', rows=r, title=t) for n, r, t, _ in shown], indent=1) + '\n')
    print('wrote', len(shown), 'svg')


if __name__ == '__main__':
    main()
