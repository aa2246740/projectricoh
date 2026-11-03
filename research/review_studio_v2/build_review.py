"""Assemble the Chinese acceptance report from persisted observations."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1] / "studio"


def source(name, line):
    return f"[{name}:{line}]({STUDIO / name}:{line})"


def evidence(name):
    return f"[{name}]({HERE / name})"


def main():
    a = json.loads((HERE / "acceptance.json").read_text())
    f = json.loads((HERE / "focused.json").read_text())
    ui = json.loads((HERE / "ui-acceptance.json").read_text())
    checks = json.loads((HERE / "checks.json").read_text())
    portable = json.loads((HERE / "portable.json").read_text())
    clean = json.loads((HERE / "cleanup.json").read_text())
    suite = next(ET.parse(HERE / "portable.junit.xml").getroot().iter("testsuite"))
    ptests, pskip = int(suite.attrib["tests"]), int(suite.attrib["skipped"])
    portable_coverage = re.search(r"Total coverage: ([\d.]+)%", (HERE / "portable.log").read_text()).group(1)
    manifest_sha = hashlib.sha256((HERE / "source_manifest.json").read_bytes()).hexdigest()
    copy_rows = list(csv.reader((HERE / "COPY_VIOLATIONS.tsv").open(), delimiter="\t"))[1:]
    problems = [
        ("01", "P1", source("src/gxr_studio/api/routes.py", 174),
         "导出仍分两条流水线。JPG 只改曝光、白平衡、对比度、高光、阴影或曲线时，预览变化，导出与未编辑导出逐像素相同。只通过全局默认加边框/时间戳也走旧导出。RAW+JPG 零编辑时，预览用 RAW 标准配方，导出用相机 JPG，实测平均 ΔE00 2.58。",
         "统一预览和导出的来源选择、已解析默认值及渲染步骤；把这些情况纳入端到端像素比对。"),
        ("02", "P1", source("src/gxr_studio/finish/serve.py", 68),
         "成片导出调用半分辨率 render_preview。4288 × 2848 RAW 不加边框导出为原尺寸，加白边后只有 2316 × 1596，照片本体只剩 2144 × 1424。新 API 的 size=full 同样不是 RAW 原尺寸。",
         "导出使用完整分辨率 RAW 解码和渲染，再接统一成片步骤；让 size=full 遵守合同。"),
        ("03", "P1", source("src/gxr_studio/library/edits.py", 109) + "；" + source("src/gxr_studio/library/edits.py", 160),
         "GET/PUT crop 仍用原始尺寸。640 × 480 向左旋转后，uncropped 是 480 × 640，crop.frame 却仍为 640 × 480；选 1:1 后预览和导出都是 360 × 640。垂直、畸变后的 1:1 也分别变成 536 × 484、371 × 400。违反合同修订 1 第 10 条。",
         "保留 sidecar 原始尺寸，另按几何后的画布推导 API frame、比例、方向和裁剪验证。"),
        ("04", "P1", source("src/gxr_studio/finish/compose.py", 82) + "；" + source("src/gxr_studio/render/edits.py", 108),
         "没有 crop 或 rect=[0,0,1,1] 时跳过有效区域收缩。只写 straighten=15 的成片保留四个 #1b1c1f 空白角；垂直、畸变同样有无效边缘。保存时也未把收缩后的框写回 sidecar。",
         "所有最终画面都必须落在有效区域内；在正确坐标系里保存实际裁剪框，并覆盖空框和整幅框。"),
        ("05", "P1", source("web/assets/preview.js", 528) + "；" + source("src/gxr_studio/library/thumbs.py", 131),
         "按住空格的原图仍请求 /preview；这个接口现在会带已保存编辑。640 × 480 的测试照片加白边后，按住空格得到 692 × 532 的带框图，界面却标原图。",
         "给原图比较提供明确绕过编辑和默认装饰的图像来源，与成片缩略图分开。"),
        ("06", "P1", source("src/gxr_studio/api/finish_routes.py", 86) + "；" + source("src/gxr_studio/finish/auto_lines.py", 130),
         "自动返回的值不能直接保存。合成水平线图设拉直 +10° 后，auto 返回 straighten=-10、vertical=51.94、confident=true；按前端原样 PUT edit 返回 422，因为 vertical 必须是整数。估计还作用在已纠正画面上，却把残余角度当绝对值返回。",
         "让自动估计输出合法的最终几何参数；使用未纠正输入或正确合成当前变换，并测试建议值可直接应用及再次自动的稳定性。"),
        ("07", "P1", source("src/gxr_studio/finish/stamp.py", 14) + "；" + source("src/gxr_studio/finish/frame.py", 157),
         "中文自定义文字不能正常出图。无衬线时间戳的上海与北京逐像素相同，拍立得边框的这两个文本也逐像素相同，均为缺字方块。",
         "为自定义文字提供符合素材大小和许可约定的中文字体或字形回退；检查每种文字字体的缺字行为。"),
        ("08", "P1", source("web/assets/viewer.js", 223) + "；" + source("src/gxr_studio/finish/serve.py", 112),
         "有全局默认装饰时复原不能回到原图。复原写 frame:null、stamp:null，后端把它们解释为重新继承默认值。默认白边下，复原并刷新后仍是 692 × 532。",
         "复原时写明确的 frame.style=none 和 stamp.enabled=false；区分继承默认与禁用装饰。"),
        ("09", "P2", source("src/gxr_studio/library/thumbs.py", 132),
         "默认装饰不参与缩略图缓存。已复现 rev=0 的照片直接跳过成片，设默认白边后缩略图字节不变，仍带一年 immutable；静态检查还确认 rev>0 的缓存键只有 rev，没有默认值版本。",
         "按最终解析出的编辑和默认值版本缓存；默认值变化时让列表 URL 和图像缓存一起失效。"),
        ("10", "P2", source("src/gxr_studio/finish/serve.py", 150),
         "导出长边限制在装饰之前应用。请求 long_edge=512，加白边后实际输出 552 × 380；size=thumb/preview 同样可能超过合同长边。",
         "按最终成片尺寸计算输出缩放，明确包含边框和画布。"),
        ("11", "P2", source("src/gxr_studio/finish/serve.py", 158),
         "新导出只继承中间 JPEG 的空 EXIF，再写 ImageDescription。加边框后的 EXIF 只剩标签 270；同一照片旧导出仍带日期、相机与曝光子目录等信息。",
         "沿用原有导出元数据清理逻辑，从源照片复制可迁移字段，更新方向和输出尺寸。"),
        ("12", "P2", source("src/gxr_studio/finish/stamp.py", 108),
         "合法的 24 字时间戳会被裁断。竖幅 480 像素宽时，24 个 W 的大号无衬线文字宽 745.875 像素，直接从负 x 坐标绘制。",
         "把实际字形包围框收进照片，必要时缩小字号；同时覆盖日期和文字并存及边框文字。"),
        ("13", "P2", source("src/gxr_studio/finish/spec.py", 200) + "；" + source("src/gxr_studio/finish/serve.py", 154),
         "新分支有可持久化的无效输入。date_override=2026-99-99 保存返回 200，随后预览、导出都返回 500。带边框时 format=tiff 也返回 KeyError 导致的 500，绕过旧 ExportOptions.validate。",
         "保存前解析真实日期；所有导出路径先验证统一选项，返回中文 422，不能保存会使后续渲染失败的状态。"),
        ("14", "P2", source("src/gxr_studio/export.py", 118) + "；" + source("src/gxr_studio/export.py", 90),
         "reveal 只核对解析后路径位于目录中，没有核对本次产物身份。把已登记导出路径换成指向同目录 not-exported.jpg 的符号链接，返回 200 并调用 open -R 打开这个未导出文件。目录外链接返回 404。",
         "登记并核对文件身份，拒绝符号链接和被替换的产物；保持不接受请求体路径的现有约束。"),
        ("15", "P2", source("web/assets/preview.js", 410) + "；" + source("src/gxr_studio/finish/geometry.py", 135),
         "松手后的 full 纠正预览未达到 1.5 秒合同。独立临时 HTTP 实例上，5 次不同角度请求为 1.539–1.597 秒，中位 1.557 秒，全部成功并解码到 2144 × 1424。有效矩形的 Python 全图扫描是主要耗时。",
         "松手预览使用合同的 preview 尺寸，并减少或缓存有效矩形计算；在同样负载下复验完整用户等待时间。"),
        ("16", "P2", source("web/assets/app.css", 152) + "；" + source("web/assets/app.css", 407),
         "样式缩略图继承图库 object-fit:cover。徕卡样图实际 240 × 244，却装入 109 × 72 的框，底部标志和参数被裁掉；哈苏、画布等比例也被裁。",
         "边框卡片显示完整成片，覆盖图库的 cover 样式，调整容器比例及对齐。"),
        ("17", "P2", source("src/gxr_studio/api/lut_routes.py", 77) + "；" + source("src/gxr_studio/render/params.py", 183),
         f"后端文案未遵守 COPY。已确认 {len(copy_rows)} 个位置，包含调色文件、说明长句、内部接口键、异常原文、路径及未写成两短句的错误；全文清单见后附表。",
         "按 COPY 固定术语统一 API message、note、label；用户主句和诊断信息分开，补后端文案检查。"),
        ("18", "P2", source("src/gxr_studio/finish/serve.py", 177) + "；" + source("src/gxr_studio/api/routes.py", 245),
         "render_label 未遵守合同修订 1 的 prediction/approx/original 值域，实际返回电脑预测 未校准、相机 JPG 或照片本身。docs/openapi.json 与代码相同，但响应没有把这项合同写成模型。",
         "按合同分开机器枚举与显示文字，并将响应类型写入 OpenAPI。"),
        ("19", "P2", source("tests/test_finish.py", 30) + "；" + source("tests/test_approx_holdout.py", 16),
         "部分测试名称强于断言。水平正方向测试只检查左右都有像素；近似留出测试只检查文件存在和 ENABLED=False，不重算色差。自动纠正仅 10% 行覆盖，成片服务 46%，未拦住本报告的核心失败。",
         "补有明确预期的方向、自动建议应用、预览与导出、全分辨率和默认值组合测试。近似开关测试与实际留出评估分开命名。"),
        ("20", "P1", source(".github/workflows/ci.yml", 19) + "；" + source("tests/test_render.py", 43),
         "仅源码且没有相邻私有夹具的环境不能通过 85% 覆盖率门槛。隔离快照复跑结果见第 8 项；CI 仅 checkout 本仓库，没有提供 firmware/captures/research 夹具。",
         "用可分发的合成或脱敏夹具覆盖同等行为，或在私有 CI 中明确、安全地提供本机专用输入；不要降低合同规定的覆盖率门槛。"),
    ]
    out = ["不能交付", "", "验收对象是基线 `e6952acb89de95e089c8e7080c5d92de99057cc4` 上的未提交工作区。验收日期为 2026-10-31，范围为本机源码、API、图像产物和固定 Chromium 的前端流程。没有修改产品代码，没有提交、检出、stash 或其他 Git 写操作，没有访问真实图库、49667 服务或存储卡。", "",
           f"本机全量检查通过，{checks['seconds']:.2f} 秒，478 passed、0 skipped、0 failed，行覆盖率 87.29%。仍有 {sum(p[1]=='P1' for p in problems)} 项 P1 和 {sum(p[1]=='P2' for p in problems)} 项 P2。交付阻塞包括编辑导出丢失、RAW 分辨率下降、几何裁剪不符合同、原图比较错误、自动纠正无法应用及中文缺字。没有发现 P0 原文件损坏。", "",
           "问题表如下。P1 阻止本次交付；P2 为范围明确的功能、合同或质量缺陷。", "",
           "| 编号 | 严重度 | 文件:行 | 说明 | 建议 |", "| --- | --- | --- | --- | --- |"]
    out += [f"| V2-{n} | {sev} | {loc} | {desc} | {fix} |" for n, sev, loc, desc, fix in problems]
    out += ["", "1．效果可见：不通过。", "",
            "DIAG 的四个编号原因与最后的缓存问题分别复验如下。不能把渲染函数能改像素等同于成片一致。", "",
            "| DIAG 原因 | 本轮结论 | 证据 |", "| --- | --- | --- |",
            "| 相机 JPG 作为编辑后的默认画面，且永久缓存 | 常规已保存编辑已修；全局默认仍漏掉，原图比较被连带改坏 | 编辑 RAW 的缩略图字节变化且 no-cache；V2-05、09仍失败 |",
            "| 两套预览切换，颜色预览不带裁剪/拉直 | 前端已统一 final/uncropped；导出没有统一 | 浏览器六个标签使用新接口；V2-01至04仍失败 |",
            "| JPG 在调整前被 NoRaw 拦住 | 普通调整、曲线与装饰预览已修；常用调整导出未修 | jpg_effect_export；JPG capabilities.recipe=none，禁用按钮及两行固定文字符合要求 |",
            "| 曲线拖动发送旧曲线 | 已修 | 鼠标尚未松开时已发送 master=[[0,0],[128,204],[255,255]]；ui-acceptance.json |",
            "| JPEG quality 未进入缓存键 | 已修 | 同一 RAW 的 quality=40/88 均返回 200，字节和 ETag 不同 |", "",
            "日常 RAW 的 01、02、05、06、07、08 相对 04 标准平均 ΔE00 为 2.421、4.302、5.939、5.179、4.439、4.326；03 为 11.930，RGB 三通道最大差为 0。04 是比较基准，色差 0，不能要求它相对自身达到 2。近似配方保持关闭，未把 JPG 调整称为近似。", "",
            "JPG 的十项调整在两端都改变预览像素，记录了亮度、RGB 均值、色度和标准差；普通 1:1、16:9 裁剪的预览与导出尺寸一致。六种边框和时间戳都在预览与导出中可见，同尺寸下两次 JPEG 编码的平均像素差约 0.06–0.13。曝光 +1.5 EV 的预览与未编辑导出平均像素差为 59.86，导出与原始导出的平均差却为 0。这是功能丢失，不能归因于 JPEG 编码误差。", "",
            "成片函数内部顺序为基础颜色/曲线、新四项调整、畸变和透视、拉直、旋转/翻转、裁剪、时间戳、边框、JPEG。单独纠正、整幅框和旧导出分支仍破坏合同。自动纠正另有 V2-06；无明显线条的平面测试则正确返回 confident=false 和未检测到明显的水平线。", "",
            f"原始观测见 {evidence('acceptance.json')}、{evidence('focused.json')}、{evidence('auto-level-lines.json')}、{evidence('ui-acceptance.json')}。", "",
            "2．合同：部分通过，整体不通过。", "",
            "接口路径、GET/POST render 的 stage/size、草稿键、frames、meta、defaults、capabilities 和空请求体的 geometry/auto 均存在。运行时 OpenAPI 与 docs/openapi.json 完全相同，独立比较和 export_openapi.py --check 都通过。相同的 OpenAPI 不能证明几何坐标、size=full 和 render_label 的语义符合 PRD。", "",
            "边框 API 仍叫 frame，sidecar 确实写 border，尺寸 frame 保留 orientation/width/height；把 frame 改成只有样式的坏记录后，GET crop 能恢复 640 × 480、把样式迁入 border，并保留裁剪。PUT crop 省略 angle_deg 保留 3.5°，显式 0 才归零。geometry.straighten 与 crop.angle_deg 共用 rev 并同步。", "",
            "界面的复原在出厂默认下会清掉配方、调整、曲线、几何、装饰，并把裁剪写回 original/[0,0,1,1]/0°。DELETE edit 单独调用仍保留裁剪，这个接口行为未在 PRD 中明确要求改变；本报告不把它单独列为缺陷。保存了全局默认装饰之后的复原失败见 V2-08。", "",
            "3．兼容现有图库：记录兼容通过，成片兼容不通过。", "",
            "基线源码只通过 git show 导出到 Scratch，再用基线自己的导入器及编辑写入函数造库。共有 5 张去重后的照片，包括两张真实 DNG+JPG、一张真实只有 JPG 和合成 JPG。旧 RAW 记录包含槽位 08、旋钮记忆、曝光/白平衡/对比度、曲线以及 1:1/+3.5°；旧 JPG 记录包含曝光 +1 EV 和 16:9/−2°。", "",
            "V2 首次打开时，各 sidecar 与基线生成内容相同，所有媒体 SHA-256 相同；GET edit/crop 正常。省略角度重新保存裁剪并导出后，recipe/adjust/curve 原样保留，角度分别仍为 +3.5° 和 −2°，RAW/JPG 均能导出。旧 JPG 的曝光在导出中仍会被 V2-01忽略，属于输出未尊重编辑意图，不能将记录保留判成整体通过。", "",
            f"基线输入与过程见 {evidence('baseline-fixture.json')}、{evidence('baseline.log')}。固件字节没有复制到 studio 或报告目录。", "",
            "4．相机配方文件：通过本机文件导入与编解码验收。", "",
            "| 代数 | 文件字节数 | parse→pack | 导入 HTTP | 原文件 SHA-256 |", "| --- | --- | --- | --- | --- |"]
    for gen in ("137", "138"):
        v = a["firmware"][gen]
        out.append(f"| {gen} | {v['bytes']} | 逐字节一致 | {v['import_status']} | `{v['sha256']}` |")
    out += ["", "两份输入文件的最终哈希未变。第 121 代拒绝测试只在内存中改代数字段，属于合成不支持代数输入，返回 422，文字精确为“不支持第 121 代相机配方文件。请使用第 127 代或更新的版本。”没有在相机或存储卡上操作。", "",
            "5．在访达中显示：基本功能及目录外边界通过，严格产物归属不通过。", "",
            "临时 TestClient 实例上真实调用一次返回 200，实际执行 open -R 指向本次临时导出。注入请求体 path=/etc/passwd 仍只打开登记的导出；不存在的 export_id 和指向目录外的符号链接均为 404。同目录未导出文件能通过替换链接被打开，见 V2-14。该反例中的 open 被替换为记录器，未真实打开那个替代文件。", "",
            "6．文案：前端静态控件大体通过，后端不通过。", "",
            f"逐行核对 ES module、页面、后端消息与 COPY 第 3.9–3.12 条，并执行附录允许沿用的词。前端直接文字未发现仍在显示的禁用术语；按钮动作、标签、JPG 两行提示及自动无结果提示符合固定文案。说明注释、源码内的技术名、COPY_GAPS 中已获允许的词没有按界面问题计入。", "",
            f"对后端错误表达式做 AST 抽取，再逐条检查外露位置，共记录 {len(copy_rows)} 个不合规位置，含重复字符串的不同调用点。主要问题是调色文件、照片本身、长解释句和内部参数名；错误还会拼接原始异常或路径。清单中的模板保留源码变量，诊断原文不会被当成实际固件内容。完整字符串和位置列在本文后附表及 {evidence('COPY_VIOLATIONS.tsv')}。", "",
            "7．视觉：仍有具体问题，不重复判旧截图已修的问题。", "",
            "已看 final 的全部 8 张图和 phase2 的全部 37 张截图。final 的六种边框、撇号时间戳和几何样图没有明显文字溢出；徕卡信息条两行右对齐，哈苏参数居中。旧 04-frame-cards.png 和 24-fresh-frame-set.png 的第三列溢出、重复颜色控件已在当前代码中修掉；27-restore-crop-full.png 的旧参考线按钮组与底部截断也未在本轮当前界面复现。", "",
            "当前 1360 × 860 和 1024 × 768 下，卡片都在侧栏内，设为默认及裁剪底栏可达，未见横向溢出。仍有 V2-16 的水印缩略图裁切；新增文字反例还有 V2-07 缺字与 V2-12 长文字截断。这些由新截图和像素验证支持，不依据过时截图推断现状。", "",
            f"查看 {evidence('ui-frame-settled-1360.png')}、{evidence('ui-frame-settled-1024.png')}、{evidence('ui-crop-current.png')}、{evidence('ui-space-original.png')}、{evidence('stamp-chinese.png')}、{evidence('stamp-long-text.png')}。字体文件约 768 KiB，仓库含许可文本、标志来源和商标说明；中文缺字仍须修复。", "",
            "8．质量：本机工具检查真实通过，隔离环境与行为覆盖仍不达标。", "",
            "本机 ruff check/format、strict mypy、秘密扫描、Bandit、死开关、AGENTS 命令核对、大文件、OpenAPI、import-linter、deptry、vulture、pylint 重复代码及全量 pytest 全部通过。mypy 配置 strict=true，检查 83 个源文件；锁定引擎通过存根检查。覆盖率 87.29% 是行覆盖，不是分支覆盖。JUnit 确认 478 tests、0 failure、0 error、0 skip；没有发现 assert True、空测试或新增 xfail 来掩盖本机失败。", "",
            "存在弱断言，见 V2-19；caution == 空串是在检验删除文案，不能据此认定空断言。近似留出开关测试没有重新计算平均 ΔE00，5.18 是已给定报告中的留出结果，本轮独立确认的是该功能保持关闭。本轮另用真实 API、导出文件及浏览器操作补证，不能把新增脚本的发现算作产品现有测试已经覆盖。", "",
            f"为了核对 PRD 的干净克隆要求，按工作区 215 个可交付文件制作无私有相邻目录的源码快照，保留执行权限，复用同一已锁定依赖环境。实际导入模块来自快照。结果为 {ptests-pskip} passed、{pskip} skipped，覆盖率 {portable_coverage}%，进程退出码 {portable['exit_code']}，85% 覆盖率门槛失败；见 {evidence('portable.log')}。这是 macOS 上的源码隔离实测，没有把它称为远端 Linux CI 实测。工作流未安排私有夹具，故当前未满足“干净克隆 CI 通过”的交付条件。", "",
            "新增 Python/JS 的命名和格式总体沿用仓库习惯。新成片层在组织上独立，但旧导出分支仍保留，geometry/frame/stamp 的 Any 字段也意味着 strict mypy 并不能验证它们的领域约束。三条 pytest warning 和 Bandit 的 nosec 注释解析提示均保留在日志中，没有将其当成交付通过证据。", "",
            f"时延测量使用 10 个逻辑核心的本机，未停止用户说明的其他固件工作；观测负载约 4.9–5.6。按真实接口返回、解码图像、不同角度重复 5 次计时，错误数为 0。preview 的中位数 0.858 秒，full 的中位数 1.557 秒。独立 cProfile 只用于定位，未混入这些时延，主要耗时为 max_area_rect 的 Python 扫描。详见 {evidence('geometry-profile.txt')}。", "",
            "复跑命令如下。所有命令从 studio 执行，完整检查超时设为 1800 秒，超过历史六分钟的三倍；pytest basetemp、coverage 和浏览器 profile 都在指定 Scratch 目录。不要对这些命令改用默认图库。", "",
            "```bash", f"cd {STUDIO}", "export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2", 'mkdir -p "$TMPDIR"',
            ".venv/bin/python -B ../research/review_studio_v2/run_checks.py",
            ".venv/bin/python -B ../research/review_studio_v2/baseline_fixture.py",
            ".venv/bin/python -B ../research/review_studio_v2/acceptance.py",
            ".venv/bin/python -B ../research/review_studio_v2/portable_check.py",
            ".venv/bin/python -B ../research/review_studio_v2/copy_audit.py", "```", "",
            "acceptance.py 包含一次获准的真实访达显示。前端及补充验证另用两个终端；先在终端 A 启动以下临时实例，它会选择新端口。", "",
            "```bash", f"cd {STUDIO}", "export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2", ".venv/bin/python -B ../research/review_studio_v2/temp_server.py", "```", "",
            "然后在终端 B 依次运行，不并行修改同一临时图库。", "",
            "```bash", f"cd {STUDIO}", "export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2", "node ../research/review_studio_v2/ui_acceptance.mjs",
            ".venv/bin/python -B ../research/review_studio_v2/focused_checks.py",
            ".venv/bin/python -B ../research/review_studio_v2/auto_check.py",
            "node ../research/review_studio_v2/visual_check.mjs", "```", "",
            "浏览器脚本在 finally 中关闭固定 Chromium。停止终端 A 的临时实例后，用 cleanup.py 核对进程、原文件和代码哈希并清理 Scratch。", "",
            "```bash", ".venv/bin/python -B ../research/review_studio_v2/cleanup.py", "```", "",
            f"本轮最终记录：产品文件哈希未变={clean['source_unchanged']}，临时实例已停止={clean['server_stopped']}，临时 Chromium 已停止={clean['browser_stopped']}，临时目录已删除={clean['scratch_removed']}，媒体哈希未变={clean['media_unchanged']}。源码清单文件的 SHA-256 为 `{manifest_sha}`，见 {evidence('source_manifest.json')}。", "",
            "后附文案表。表内是用户可收到的字符串或其源码模板，包含同一文字的各个返回位置；不是把注释当成界面。两短句规则按 COPY 第 4 节，固定例外按 3.9–3.12 执行。", "",
            "| 文件:行 | 不合规字符串或模板 | 原因 |", "| --- | --- | --- |"]
    for loc, string, reason in copy_rows:
        out.append("| " + loc + " | " + string.replace("|", "\\|").replace("\n", " ") + " | " + reason + " |")
    (HERE / "REVIEW.md").write_text("\n".join(out) + "\n")
    print(json.dumps({"report": str(HERE / "REVIEW.md"), "issues": len(problems), "P1": sum(p[1]=="P1" for p in problems),
                      "P2": sum(p[1]=="P2" for p in problems), "copy_locations": len(copy_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
