"""文字对背景的对比度（WCAG 2.x 相对亮度公式）。半透明底色先按给定的下层颜色合成。
用法：python3 -I tools/contrast.py  → 输出 Markdown 表格"""

def hex2rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]

def over(rgba: tuple[str, float], under: str) -> str:
    c, a = rgba
    fg, bg = hex2rgb(c), hex2rgb(under)
    mix = [round((f * a + b * (1 - a)) * 255) for f, b in zip(fg, bg)]
    return "#" + "".join(f"{v:02x}" for v in mix)

def lum(h: str) -> float:
    def ch(v: float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in hex2rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def ratio(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)

T1, T2, T3, TD = "#ececec", "#b3b3b3", "#999999", "#6e6e6e"
BG = {"顶栏 #111111": "#111111", "窗口/胶片条 #161616": "#161616", "面板 #1b1b1b": "#1b1b1b", "卡片/输入框 #242424": "#242424",
      "对话框/菜单 #262626": "#262626", "次按钮/分段底 #2b2b2b": "#2b2b2b", "画面深灰 #2a2a2a": "#2a2a2a", "悬停 #333333": "#333333",
      "按下 #3c3c3c": "#3c3c3c", "分段选中 #424242": "#424242"}
rows = []
for name, bg in BG.items():
    rows.append(("主文字 --text-1 #ececec", name, T1, bg))
    rows.append(("次文字 --text-2 #b3b3b3", name, T2, bg))
for name in ["顶栏 #111111", "窗口/胶片条 #161616", "面板 #1b1b1b", "卡片/输入框 #242424", "对话框/菜单 #262626", "次按钮/分段底 #2b2b2b"]:
    rows.append(("弱文字 --text-3 #999999", name, T3, BG[name]))
for name in ["窗口/胶片条 #161616", "面板 #1b1b1b", "对话框/菜单 #262626"]:
    rows.append(("强调文字 --accent-text #6aa6ff", name, "#6aa6ff", BG[name]))
    rows.append(("出错文字 --danger-text #ff7a70", name, "#ff7a70", BG[name]))
for lab, bg in [("主按钮 #2a64cc", "#2a64cc"), ("主按钮悬停 #2f6fde", "#2f6fde"), ("主按钮按下 #2457b8", "#2457b8"),
                ("危险按钮 #c4302a", "#c4302a"), ("危险悬停 #cc3a31", "#cc3a31"), ("危险按下 #a92822", "#a92822"), ("菜单高亮行 #2a64cc", "#2a64cc")]:
    rows.append(("白字 #ffffff", lab, "#ffffff", bg))
for under_name, under in [("面板", "#1b1b1b"), ("窗口", "#161616"), ("对话框", "#262626")]:
    rows.append(("小标签（电脑预测等）#e8b04a", f"琥珀底 14% 叠在{under_name}上", "#e8b04a", over(("#e8b04a", 0.14), under)))
    rows.append(("中性小标签 --text-2", f"白 7% 叠在{under_name}上", T2, over(("#ffffff", 0.07), under)))
rows.append(("强调小标签 #6aa6ff", "蓝 16% 叠在面板上", "#6aa6ff", over(("#4a8cff", 0.16), "#1b1b1b")))
rows.append(("侧栏选中行 --text-1", "蓝 16% 叠在面板上", T1, over(("#4a8cff", 0.16), "#1b1b1b")))
rows.append(("侧栏选中行计数 --text-2", "蓝 16% 叠在面板上", T2, over(("#4a8cff", 0.16), "#1b1b1b")))
# 叠在照片上的角标：按最坏情况（纯白照片）合成
rows.append(("角标白字（拍摄配方）", "黑 66% 叠在纯白照片上（最坏）", "#ffffff", over(("#000000", 0.66), "#ffffff")))
rows.append(("角标白字（文件类型）", "黑 62% 叠在纯白照片上（最坏）", "#ffffff", over(("#000000", 0.62), "#ffffff")))
rows.append(("HDR 角标 #111111", "#f2f2f2", "#111111", "#f2f2f2"))
rows.append(("画面上的标签 --text-1", "#141414 72% 叠在纯白照片上（最坏）", T1, over(("#141414", 0.72), "#ffffff")))
rows.append(("画面上的标签 --text-1", "#141414 72% 叠在 18% 灰背景上", T1, over(("#141414", 0.72), "#767676")))
rows.append(("提示气泡/数值气泡 #111111", "#ececec", "#111111", "#ececec"))
rows.append(("提示气泡快捷键 #555555", "#ececec", "#555555", "#ececec"))
rows.append(("禁用文字 #6e6e6e（豁免）", "面板 #1b1b1b", TD, "#1b1b1b"))
rows.append(("主按钮禁用 #7f8ba0（豁免）", "#24324a", "#7f8ba0", "#24324a"))

print("| 前景 | 背景 | 合成后背景 | 对比度 | ≥ 4.5:1 |")
print("| --- | --- | --- | --- | --- |")
fails = 0
for fg_name, bg_name, fg, bg in rows:
    r = ratio(fg, bg)
    exempt = "豁免" in fg_name
    ok = "是" if r >= 4.5 else ("（豁免）" if exempt else "**否**")
    if r < 4.5 and not exempt:
        fails += 1
    print(f"| {fg_name} | {bg_name} | `{bg}` | {r:.2f}:1 | {ok} |")
print(f"\n共 {len(rows)} 组，未达标（不含豁免）{fails} 组。")
