# 研究交付自检

状态为 PASS，范围仅限本次只读研究、数据解析和交付完整性。模拟器修补、实拍色差重测和 GXR 01/02 重拟合均未执行。

审阅日期为 2026-10-27，时区 Asia/Taipei。外置卷已核对为可写 APFS，Volume UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，已读盘根 AGENTS.md。数据解析环境是 `/usr/bin/python3` 3.9.6，全部 Python 调用带 `-I -B`，仅使用标准库，没有安装依赖。

| 项目 | 数量／结果 | 状态 |
|---|---|---|
| 五仓库实际资料 | 772 个文件，HEAD 和逐文件摘要保存在 local。 | OK |
| 冻结输入 | 初始 988 项，后补 2 项；未变、未缺失、未新增。 | 990/990 OK |
| 自家固件表内部一致性 | 按各表格式把数值重打包，核对长度和原摘要。 | 104/104 OK |
| 自家 gamma 原始块 | 核对字节长度及原摘要，没有执行曲线算法。 | 58/58 OK |
| 保存的显式 gamma 曲线 | 按 256×u16LE 核对原摘要，没有重生成曲线。 | 16/16 OK |
| 跨来源原厂参数 | Positive look、Negative look、Positive MA bank，偏移和摘要相符。 | 3/3 OK |
| 原描述符指针 | 两模式的 MA/gamma，共四组、每组三套原指针。 | 12/12 OK |
| 另一个 colour 资源 | 指向独立后级资源，前级 record 对应关系被否决并保留说明。 | 不计入匹配通过项 |
| 作者 DNG 清单 | 三张 DNG 的实算 SHA256 与作者清单一致。 | 3/3 OK |
| 数据去重 | 三张 DNG 的 SHA256 不在 r1 冻结输入清单内。 | 3/3 为新增候选 |
| 照片元数据 | 三张 DNG、ZIP 八张 JPEG 均读到机型、版本、模式和主要字段。 | 11/11 OK |
| DNG 内全尺寸预览 | 条带边界、SOI/EOI、baseline SOF、6192×4128、8 bit、3 分量和流摘要。 | 3/3 OK；未解码整张 JPEG |
| 两张 UI/预览素材 | 没有 EXIF，按素材记录，不当作相机验证样片。 | 预期的元数据缺失 |
| 文本检索覆盖 | 五仓库 571 个选定类型文本文件，保存关键词及命中位置。 | 已记录检索边界 |
| 文件行号证据 | 每项源文件摘要与冻结记录相同，行号范围存在。 | 94/94 OK |
| 报告链接与表格 | 证据锚点存在、源文件链接可定位，Markdown 表格列数一致。 | OK |
| 非 local 交付 | `.gitignore`、REPORT、EVIDENCE、索引、解析器及本文件。 | SHA256SUMS 覆盖 6 项，全部 OK |
| Git 忽略 | 本目录 `local/` 被忽略。 | OK |

下载项目的 Python、TypeScript、JavaScript、测试和二进制均未运行或 import。LUTSmith 内嵌资料通过 AST 取字符串字面量，再按 Base64、zlib、JSON 解析，未执行其赋值语句或函数。只把已有的小缩略图提取到 local 供场景识别；未复制 DNG、ZIP 或全尺寸 JPEG。

未联网、构建、启动服务、开子代理或 sleep 轮询，未操作相机／存储卡，未修改 r1、r2 或其他既有研究文件。上游的上机结论和 r1 旧成绩均作为有来源的已有证据引用，没有重跑成像模型。

从仓库根核对现有冻结记录：

```sh
/usr/bin/python3 -I -B research/gr4_repos_review_r1/audit_data.py verify-inputs
/usr/bin/python3 -I -B research/gr4_repos_review_r1/audit_data.py evidence
/usr/bin/python3 -I -B research/gr4_repos_review_r1/audit_data.py check
```

重新解析资料只写 local，不执行下载项目：

```sh
/usr/bin/python3 -I -B research/gr4_repos_review_r1/audit_data.py constants
/usr/bin/python3 -I -B research/gr4_repos_review_r1/audit_data.py metadata
/usr/bin/python3 -I -B research/gr4_repos_review_r1/audit_data.py coverage
```

在本目录核对标准清单：

```sh
shasum -a 256 -c SHA256SUMS
```

清单排除 `local/` 和 SHA256SUMS 自身；额外的 `audit_data.py check` 同时检查覆盖范围，防止非 local 新文件漏列。原始核对结果保存在 `local/input_verification.json`、`local/evidence_verification.json`、`local/own_table_integrity.json`、`local/own_gamma_integrity.json` 和 `local/checksum_verification.log`。
