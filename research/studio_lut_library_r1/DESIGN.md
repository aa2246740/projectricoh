# LUT 库 R1 界面约定

依据：studio_camera_manager/DESIGN.md §8 和 studio_v2/COPY.md。单 agent 实施，沿用现有页面、控件、颜色、字体和间距。

「配方」页先列 LUT 库，再显示选中 LUT 的输入空间、预览和署名。导入支持多文件、文件夹选择和文件夹拖放。照片编辑的「配方」面板增加 LUT 选择，预览和导出使用同一记录。

输入空间未知或冲突时为空，不能套用或拟合；用户可改选全部实现支持的空间。现有锁定的 spaces.py 实际列出 12 种，设计写 13 种；本版全部列出这 12 种，不新增未经实现的空间。

删除采用「删除「名称」？」和「取消」「删除」。删除组保留 LUT，移至「未分组」。名称和署名只作为文本显示。输出路径固定在应用数据目录内，由 PrivateDir 核对。

| Reference | Decision | Artifact target | Verification |
| --- | --- | --- | --- |
| ultimate-design/references/branch-web-product.md | 保留现有视觉和交互，补齐空、错误、忙碌、删除确认状态 | LUT 库和照片配方面板 | 合成 API 测试及固定 Playwright 界面检查 |
| ultimate-design/references/content-model.md | 简短标签，保留来源、作者、许可，空间冲突需要选择 | 新增控件和状态 | 文案清单与空间组合测试 |
| ultimate-design/references/design-okf/digital/accessibility-usability.md | 沿用原生表单、具名控件、键盘操作与删除确认 | 库、署名表单、照片选择 | 真实浏览器操作、快照版面检查 |
| ultimate-design/references/design-okf/content/ux-writing.md | 状态一句，名称为数据，错误沿用现有主句 | 导入逐项结果、空间选择、删除标题 | COPY.md 和浏览器文字检查 |

两档预测延期，本版不显示空分数。布局沿用已有 LUT 页和配方面板，无新的风格选择。所有新增文案最终集中列入 COPY.md。
