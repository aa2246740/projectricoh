"""从本机已安装的 lucide-react（ISC 许可）读取图标几何数据，生成 SVG sprite。只读源包。
用法：python3 -I make_icons.py <lucide-react 包目录> <输出目录>
"""
import json, re, sys, pathlib

ICONS = [
    "undo-2", "redo-2", "chevron-left", "chevron-right", "chevron-down", "chevron-up", "x", "check", "plus", "minus",
    "image", "images", "layout-grid", "grid-3x3", "columns-2", "eye", "eye-off", "sliders-horizontal", "swatch-book",
    "crop", "frame", "calendar-clock", "share", "rotate-ccw-square", "flip-horizontal-2", "wand-sparkles", "rotate-ccw",
    "import", "keyboard", "settings", "circle-help", "star", "search", "folder", "folder-open", "trash-2",
    "pencil", "info", "triangle-alert", "circle-check", "circle-alert", "zoom-in", "scan", "film", "type", "ellipsis",
    "panel-bottom", "panel-right", "list-filter", "calendar", "upload", "download", "arrow-left-right", "square-split-horizontal",
    "maximize-2", "sun", "palette", "spline", "camera", "hard-drive", "lock", "copy", "square-dashed", "move", "ratio",
    "file-down", "file-up", "external-link", "circle", "sparkles", "layers", "aperture", "save", "ban", "hard-drive-download",
]

def main(pkg: str, out: str) -> None:
    src = pathlib.Path(pkg) / "dist" / "esm" / "icons"
    version = json.loads((pathlib.Path(pkg) / "package.json").read_text())["version"]
    syms, missing = [], []
    for name in ICONS:
        f = src / f"{name}.js"
        if not f.exists():
            missing.append(name)
            continue
        js = f.read_text()
        body = js.split("const __iconNode = [", 1)[1].split("];", 1)[0]
        parts = []
        for tag, attrs in re.findall(r'\[\s*"(\w+)",\s*\{([^}]*)\}\s*\]', body):
            kv = dict(re.findall(r'(\w+):\s*"([^"]*)"', attrs))
            kv.pop("key", None)
            a = " ".join(f'{k}="{v}"' for k, v in kv.items())
            parts.append(f"<{tag} {a}/>")
        syms.append(f'<symbol id="i-{name}" viewBox="0 0 24 24">{"".join(parts)}</symbol>')
    o = pathlib.Path(out)
    o.mkdir(parents=True, exist_ok=True)
    head = f"<!-- Lucide v{version} (lucide-react), ISC License, https://lucide.dev . See LICENSE-lucide.txt -->\n"
    (o / "lucide-sprite.svg").write_text(head + '<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n' + "\n".join(syms) + "\n</svg>\n")
    (o / "LICENSE-lucide.txt").write_text((pathlib.Path(pkg) / "LICENSE").read_text())
    print(len(syms), "icons; missing:", missing)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
