"""Bounded classic-TIFF traversal. Existing IFDs and allocations stay in place."""
from dataclasses import dataclass
import math
import struct
import numpy as np
from common import require

TYPES = {1: ('B', 1), 2: (None, 1), 3: ('H', 2), 4: ('I', 4), 5: ('I', 8),
         6: ('b', 1), 7: (None, 1), 8: ('h', 2), 9: ('i', 4), 10: ('i', 8),
         11: ('f', 4), 12: ('d', 8), 13: ('I', 4)}


@dataclass
class Entry:
    tag: int
    typ: int
    count: int
    pos: int
    offset: int
    size: int
    value: object
    endian: str


@dataclass
class IFD:
    label: str
    offset: int
    entries: dict
    next: int


class Tiff:
    def __init__(self, data):
        self.data = bytes(data)
        require(self.data[:2] in (b'II', b'MM'), '不是 TIFF')
        self.endian = '<' if self.data[:2] == b'II' else '>'
        require(self.unpack('H', 2)[0] == 42, '只接受 classic TIFF')
        self.ifds = []
        self._visited = set()
        self.walk(self.unpack('I', 4)[0], 'IFD0')
        candidates = [i for i in self.ifds if self.scalar(i, 262) == 32803]
        require(len(candidates) == 1, '需要唯一 CFA IFD')
        self.raw = candidates[0]
        self.root = self.ifds[0]

    def unpack(self, fmt, off, endian=None):
        n = struct.calcsize(fmt)
        require(0 <= off <= len(self.data) - n, 'TIFF 引用越界')
        return struct.unpack_from((endian or self.endian) + fmt, self.data, off)

    def parse_ifd(self, off, label, base=0, endian=None):
        endian = endian or self.endian
        count = self.unpack('H', off, endian)[0]
        require(0 < count < 512, 'IFD 项目数量不符')
        require(off + 2 + 12 * count + 4 <= len(self.data), 'IFD 越界')
        entries = {}
        for i in range(count):
            pos = off + 2 + i * 12
            tag, typ, n = self.unpack('HHI', pos, endian)
            require(typ in TYPES and tag not in entries, '未知 TIFF 类型或重复 tag')
            code, unit = TYPES[typ]
            size = n * unit
            at = pos + 8 if size <= 4 else base + self.unpack('I', pos + 8, endian)[0]
            require(0 <= at <= len(self.data) - size, f'tag {tag:#x} 越界')
            b = self.data[at:at + size]
            if typ == 2:
                value = b.split(b'\0')[0].decode('latin1')
            elif code is None:
                value = list(b)
            elif typ in (5, 10):
                v = self.unpack(code * (2 * n), at, endian)
                require(all(v[k] != 0 for k in range(1, len(v), 2)), 'TIFF 有零分母')
                value = [v[k] / v[k + 1] for k in range(0, len(v), 2)]
            else:
                value = list(self.unpack(code * n, at, endian))
            entries[tag] = Entry(tag, typ, n, pos, at, size, value, endian)
        nxt = self.unpack('I', off + 2 + 12 * count, endian)[0]
        return IFD(label, off, entries, base + nxt if nxt else 0)

    def walk(self, off, label):
        require(off not in self._visited, 'IFD 循环或重复引用')
        self._visited.add(off)
        node = self.parse_ifd(off, label)
        self.ifds.append(node)
        for tag in (330, 34665, 34853, 40965):
            if tag in node.entries:
                for k, child in enumerate(node.entries[tag].value):
                    if child:
                        self.walk(child, f'{label}/{tag}:{k}')
        if node.next:
            self.walk(node.next, label + '/next')

    @staticmethod
    def scalar(node, tag, default=None):
        e = node.entries.get(tag)
        return e.value[0] if e and isinstance(e.value, list) and len(e.value) == 1 else (e.value if e else default)

    def tags(self):
        return {tag: e.value for i in (self.root, self.raw) for tag, e in i.entries.items()}

    def geometry(self):
        t = self.tags()
        w, h = (int(t[k][0]) for k in (256, 257))
        active = list(map(int, t.get(50829, [0, 0, h, w])))
        origin = np.rint(t[50719]).astype(int).tolist()
        crop = np.rint(t[50720]).astype(int).tolist()
        xy = [active[1] + origin[0], active[0] + origin[1]]
        require(t[33422] == [0, 1, 1, 2] and t.get(33421) == [2, 2], '只支持 RGGB')
        require(t[259] == [7] and t.get(277) == [1], '只支持无损 JPEG CFA')
        require(t[258] == [14], '当前 GR 模板必须为 14 位')
        require(all(v % 2 == 0 for v in xy + crop + [w, h]), '需要偶数 RAW/CFA 几何')
        require(0 <= xy[0] < xy[0] + crop[0] <= active[3] <= w
                and 0 <= xy[1] < xy[1] + crop[1] <= active[2] <= h, '裁切越界')
        require(not any(k in t for k in (51008, 51009, 51022, 50712)), '不支持带 Opcode/LinearizationTable 的模板')
        black = t[50714]
        if len(black) == 1:
            black = black * 4
        require(len(black) == 4 and all(math.isfinite(v) for v in black), '黑电平不符')
        require(max(black) < t[50717][0] < 2 ** t[258][0], '白电平不符')
        return dict(width=w, height=h, bits=14, active_tlbr=active, crop_xy=xy,
                    crop_wh=crop, black=black, white=t[50717][0], neutral=t[50728],
                    baseline_exposure=t.get(50730, [0])[0], cfa=t[33422],
                    model=self.scalar(self.root, 272), orientation=self.scalar(self.root, 274, 1))

    def segments(self, node):
        e = node.entries
        w, h = (int(self.scalar(node, k)) for k in (256, 257))
        if 273 in e:
            offsets, counts = e[273], e[279]
            rows = int(self.scalar(node, 278, h))
            boxes = [(0, y, w, min(rows, h - y)) for y in range(0, h, rows)]
        else:
            require(324 in e and 325 in e and 322 in e and 323 in e, '没有条带或瓦片')
            offsets, counts = e[324], e[325]
            tw, th = int(self.scalar(node, 322)), int(self.scalar(node, 323))
            boxes = [(x, y, tw, th) for y in range(0, h, th) for x in range(0, w, tw)]
        require(len(offsets.value) == len(counts.value) == len(boxes), '条带/瓦片数量不符')
        result = []
        for i, (at, n, box) in enumerate(zip(offsets.value, counts.value, boxes)):
            require(0 <= at <= len(self.data) - n and n > 0, '图像数据越界')
            result.append(dict(index=i, offset=at, capacity=n, box=list(box), count_entry=counts))
        return result

    def maker(self):
        for node in self.ifds:
            for tag in (37500, 50740):
                e = node.entries.get(tag)
                if e and self.data[e.offset:e.offset + 6] == b'RICOH\0':
                    order = self.data[e.offset + 6:e.offset + 8]
                    require(order in (b'II', b'MM'), 'MakerNote 字节序不符')
                    return self.parse_ifd(e.offset + 8, 'MakerNote', e.offset,
                                          '<' if order == b'II' else '>')
        raise ValueError('缺少原生 RICOH MakerNote')

    def signature(self):
        return [(n.label, n.offset, n.next,
                 [(e.tag, e.typ, e.count, e.offset) for e in n.entries.values()])
                for n in self.ifds + [self.maker()]]


def write_uint(data, e, index, value):
    require(e.typ in (1, 3, 4, 13), '计数字段必须为无符号整数')
    code, unit = TYPES[e.typ]
    require(0 <= index < e.count and 0 <= value < 2 ** (unit * 8), '整数写入越界')
    struct.pack_into(e.endian + code, data, e.offset + unit * index, value)


def sof_info(data):
    require(data[:2] == b'\xff\xd8', '缺少 SOI')
    at, frame, scan = 2, None, None
    while at + 4 <= len(data):
        require(data[at] == 255, 'JPEG marker 不对齐')
        marker = data[at + 1]
        n = int.from_bytes(data[at + 2:at + 4], 'big')
        require(n >= 2 and at + 2 + n <= len(data), 'JPEG 段越界')
        payload = data[at + 4:at + 2 + n]
        if marker == 0xc3:
            c = payload[5]
            require(len(payload) == 6 + 3 * c and all(payload[7 + i * 3] == 0x11 for i in range(c)),
                    'SOF3 采样格式不符')
            frame = dict(precision=payload[0], height=int.from_bytes(payload[1:3], 'big'),
                         width=int.from_bytes(payload[3:5], 'big'), components=c,
                         ids=[payload[6 + i * 3] for i in range(c)])
        if marker == 0xda:
            c = payload[0]
            scan = dict(predictor=payload[1 + 2 * c], point=payload[3 + 2 * c],
                        ids=[payload[1 + i * 2] for i in range(c)],
                        tables=[payload[2 + i * 2] for i in range(c)])
            require(payload[2 + 2 * c] == 0, '非 lossless SOS')
            break
        require(marker not in (0xdd, 0xc0, 0xc1, 0xc2), '不支持的 JPEG 帧或 restart')
        at += 2 + n
    require(frame is not None and scan is not None and scan['predictor'] == 1 and scan['point'] == 0,
            '只支持 predictor 1、Pt 0 的 SOF3')
    require(frame['ids'] == scan['ids'] and scan['tables'] == [0] * frame['components'], 'SOF3 分量不符')
    require(data.endswith(b'\xff\xd9'), '缺少 EOI')
    return {**frame, **scan}
