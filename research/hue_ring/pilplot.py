#!/usr/bin/env python3
"""Minimal static charts with Pillow (matplotlib is not installed here).

Palette: reference light-mode slots (blue, orange, aqua) on an off-white
surface; text in ink colours, never in series colours. Series identity is
also carried by marker shape and a legend.
"""
from PIL import Image, ImageDraw, ImageFont

SURFACE = (252, 252, 251)
INK = (11, 11, 11)
INK2 = (82, 81, 78)
GRID = (226, 225, 221)
SERIES = [(42, 120, 214), (235, 104, 52), (27, 175, 122), (98, 80, 214)]
NEUTRAL = (150, 149, 145)


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


class Plot:
    def __init__(self, w, h, xlim, ylim, title="", xlabel="", ylabel="", margins=(72, 44, 24, 54)):
        self.w, self.h = w, h
        self.xlim, self.ylim = xlim, ylim
        self.ml, self.mt, self.mr, self.mb = margins
        self.im = Image.new("RGB", (w, h), SURFACE)
        self.d = ImageDraw.Draw(self.im)
        self.f = font(15)
        self.fs = font(13)
        self.title, self.xlabel, self.ylabel = title, xlabel, ylabel

    def x(self, v):
        a, b = self.xlim
        return self.ml + (v - a) / (b - a) * (self.w - self.ml - self.mr)

    def y(self, v):
        a, b = self.ylim
        return self.h - self.mb - (v - a) / (b - a) * (self.h - self.mt - self.mb)

    def inside(self, xv, yv):
        return self.xlim[0] <= xv <= self.xlim[1] and self.ylim[0] <= yv <= self.ylim[1]

    def axes(self, xticks, yticks, fmt="{:g}"):
        d = self.d
        for t in yticks:
            yy = self.y(t)
            d.line([(self.ml, yy), (self.w - self.mr, yy)], fill=GRID, width=1)
            d.text((self.ml - 6, yy), fmt.format(t), fill=INK2, font=self.fs, anchor="rm")
        for t in xticks:
            xx = self.x(t)
            d.line([(xx, self.mt), (xx, self.h - self.mb)], fill=GRID, width=1)
            d.text((xx, self.h - self.mb + 6), fmt.format(t), fill=INK2, font=self.fs, anchor="mt")
        d.line([(self.ml, self.h - self.mb), (self.w - self.mr, self.h - self.mb)], fill=INK2, width=1)
        d.line([(self.ml, self.mt), (self.ml, self.h - self.mb)], fill=INK2, width=1)
        if self.title:
            d.text((self.ml, 12), self.title, fill=INK, font=self.f, anchor="lt")
        if self.xlabel:
            d.text(((self.ml + self.w - self.mr) / 2, self.h - 18), self.xlabel, fill=INK2, font=self.fs, anchor="mm")
        if self.ylabel:
            d.text((8, self.mt - 4), self.ylabel, fill=INK2, font=self.fs, anchor="ls")

    def hline(self, v, color=INK2, width=1):
        yy = self.y(v)
        self.d.line([(self.ml, yy), (self.w - self.mr, yy)], fill=color, width=width)

    def vline(self, v, color=NEUTRAL, width=1, top=None, bottom=None):
        xx = self.x(v)
        y0 = self.mt if top is None else self.y(top)
        y1 = self.h - self.mb if bottom is None else self.y(bottom)
        self.d.line([(xx, y0), (xx, y1)], fill=color, width=width)

    def line(self, xs, ys, color, width=2, break_gap=None):
        pts = []
        prev = None
        for xv, yv in zip(xs, ys):
            if yv is None or xv is None or yv != yv:
                if len(pts) > 1:
                    self.d.line(pts, fill=color, width=width, joint="curve")
                pts, prev = [], None
                continue
            if break_gap is not None and prev is not None and abs(xv - prev) > break_gap:
                if len(pts) > 1:
                    self.d.line(pts, fill=color, width=width, joint="curve")
                pts = []
            yv = min(max(yv, self.ylim[0]), self.ylim[1])
            pts.append((self.x(xv), self.y(yv)))
            prev = xv
        if len(pts) > 1:
            self.d.line(pts, fill=color, width=width, joint="curve")

    def points(self, xs, ys, color, shape="o", size=8, hollow=False):
        r = size / 2
        for xv, yv in zip(xs, ys):
            if yv is None or yv != yv or not self.inside(xv, yv):
                continue
            cx, cy = self.x(xv), self.y(yv)
            box = [cx - r, cy - r, cx + r, cy + r]
            fill = None if hollow else color
            if shape == "o":
                self.d.ellipse(box, fill=fill, outline=SURFACE if not hollow else color, width=2 if hollow else 1)
            elif shape == "s":
                self.d.rectangle(box, fill=fill, outline=SURFACE if not hollow else color, width=2 if hollow else 1)
            elif shape == "^":
                self.d.polygon([(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r)], fill=fill,
                               outline=SURFACE if not hollow else color)
            elif shape == "x":
                self.d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=color, width=2)
                self.d.line([(cx - r, cy + r), (cx + r, cy - r)], fill=color, width=2)

    def hbar(self, x0, x1, yv, color, width=2, cap=4):
        a, b, yy = self.x(x0), self.x(x1), self.y(yv)
        self.d.line([(a, yy), (b, yy)], fill=color, width=width)
        self.d.line([(a, yy - cap), (a, yy + cap)], fill=color, width=width)
        self.d.line([(b, yy - cap), (b, yy + cap)], fill=color, width=width)

    def text(self, xv, yv, s, color=INK2, anchor="lm", small=True):
        self.d.text((self.x(xv), self.y(yv)), s, fill=color, font=self.fs if small else self.f, anchor=anchor)

    def legend(self, items, x=None, y=None):
        x = self.w - self.mr - 8 if x is None else x
        y = self.mt + 6 if y is None else y
        widths = [self.d.textlength(lbl, font=self.fs) for lbl, _, _ in items]
        bw = max(widths) + 34
        x0 = x - bw
        for i, (lbl, color, shape) in enumerate(items):
            yy = y + 18 * i + 8
            if shape == "-":
                self.d.line([(x0 + 4, yy), (x0 + 20, yy)], fill=color, width=2)
            else:
                r = 4
                box = [x0 + 12 - r, yy - r, x0 + 12 + r, yy + r]
                if shape == "s":
                    self.d.rectangle(box, fill=color)
                elif shape == "^":
                    self.d.polygon([(x0 + 12, yy - r), (x0 + 12 + r, yy + r), (x0 + 12 - r, yy + r)], fill=color)
                else:
                    self.d.ellipse(box, fill=color)
            self.d.text((x0 + 26, yy), lbl, fill=INK, font=self.fs, anchor="lm")

    def legend_top(self, items):
        """Horizontal legend in the title row, right-aligned, clear of the data."""
        x = self.w - self.mr
        y = 20
        for lbl, color, shape in reversed(items):
            tw = self.d.textlength(lbl, font=self.fs)
            x -= tw
            self.d.text((x, y), lbl, fill=INK, font=self.fs, anchor="lm")
            x -= 18
            if shape == "-":
                self.d.line([(x - 4, y), (x + 12, y)], fill=color, width=2)
            else:
                r = 4
                box = [x + 4 - r, y - r, x + 4 + r, y + r]
                if shape == "s":
                    self.d.rectangle(box, fill=color)
                elif shape == "^":
                    self.d.polygon([(x + 4, y - r), (x + 4 + r, y + r), (x + 4 - r, y + r)], fill=color)
                elif shape == "x":
                    self.d.line([(x, y - r), (x + 8, y + r)], fill=color, width=2)
                    self.d.line([(x, y + r), (x + 8, y - r)], fill=color, width=2)
                else:
                    self.d.ellipse(box, fill=color)
            x -= 22

    def save(self, path):
        self.im.save(path)


def stack(images, path, pad=8):
    w = max(i.width for i in images)
    h = sum(i.height for i in images) + pad * (len(images) - 1)
    out = Image.new("RGB", (w, h), SURFACE)
    y = 0
    for i in images:
        out.paste(i, (0, y))
        y += i.height + pad
    out.save(path)
