# 本轮改动清单

基于工作室 `main`、`cb23e70d21f3cc63b809350942d3bc61513ec6c5` 上既有 HDR 未提交实现。开工快照为 246 个工作室文件；本轮修改其中 9 个，新增 2 个。下列路径相对 `studio/`，最终内容以 `SHA256SUMS` 和完整检查的源码快照为准。

| 文件 | 本轮变化 |
| --- | --- |
| `src/gxr_studio/hdr/capture.py` | 新增原始拍摄字段的读取、归一化和双方已知字段比较。 |
| `src/gxr_studio/hdr/gain.py` | RAW 亮度附带拍摄字段；生成前核对配对；增加局部正相关和多种窗口大小的残差门槛；收紧可信局部位移；固定全局微调搜索中心。增益计算与封装算式不变。 |
| `src/gxr_studio/hdr/derived.py` | 缓存版本升为 v2；拍摄冲突 JSON 写入中文原因；枚举时检查取消；整轮失败收束进度并交任务表告警。 |
| `src/gxr_studio/finish/hdr_export.py` | 用原始配对 JPG 与 DNG 核对拍摄信息，失败后保留原因并导出 SDR。 |
| `src/gxr_studio/finish/serve.py` | 把原始配对 JPG 路径传给 HDR 导出层。 |
| `src/gxr_studio/api/routes.py` | 补拍摄冲突的导出提示；关闭开始后不接受新 HDR 任务。 |
| `src/gxr_studio/app.py` | 关闭图库前，按启动共用的锁停止接收 HDR 任务、取消并等待现有线程退出。 |
| `tests/test_hdr_review.py` | 新增合成配对、各拍摄字段冲突、双侧字段缺失、导入与导出、移动变体、轻微径向校正、全局平移、关闭与枚举失败及旧缓存检查。真实样本缺失时跳过对应测试。 |
| `tests/test_api.py` | 重建仅比较应保持不变的字段；另用事件和线程等待，确定性地覆盖 HDR 在重建期间结束的场景。 |
| `tests/hdr_support.py` | 合成 DNG 的型号和时间改为与合成 JPG 一致，避免仅靠原夹具的元数据冲突使移动用例被拒。 |
| `docs/architecture.md` | 记录拍摄配对规则、局部门槛、v2 缓存及关闭顺序。 |

其他既有 HDR 变更沿用上一轮实现。本轮没有修改 Makefile、依赖、锁定的渲染源码、复审目录或真实样本。

本目录的 `run_checks.py` 前台执行检查并保留独立日志，完整 `make check` 使用一次性标记。`hdr_fix_receipt.py` 记录实际 pytest 汇总及重跑次数。`verify_alignment.py` 复建复审中的配对、移动和径向校正场景；`verify_motion_matrix.py` 覆盖 144 种合成变体。`measure_*.py`、各阶段日志及 JSON 保留了门槛选择和未通过的中间结果。

`coverage.json` 保留逐文件、逐行及总计数据；完整覆盖率数据库保留在 `make_check.coverage`。`coverage_view_receipt.json` 记录 JSON 整理前后的哈希和数据库哈希。
