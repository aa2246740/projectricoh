审查脚本纠错记录，不属于候选缺陷。

- artifact_review 最初误把 section 目录的下一项 type/flags 读成 CRC/reserved。按 packer 的 HHII 布局改为单独读 type/flags 和 offset/length，header/payload CRC 另算，最终通过。
- view 数组不是文件承载的静态段，删除了对它虚构 file offset 的读取，改由 native 初始化和 view push 指令作证。
- native_flow 初版沿用了原测试的 count=2 预期，真实 continuation 复现了 native layer 先清零再压栈得到 count=1。已改正独立测试，并将原测试局限单列 P2-02。
- CPU add3 的负立即数曾被二次符号扩展，导致测试栈误差 65536 B。修正后要求函数入口/退出 SP 相同；完整 128 个 continuation 和 19 个 row loop 全部通过。
- native row loop 的 memset 和底层图形调用原先未列入模型，遇到未知 PC 就中止。确认各边界后分别增加明确的 memset 语义和图形替身，不跳过未知业务指令；stub 地址保存在 native_flow.json。
- baseline C 比较的初版错误预期 fixture 有一项差异。实际对应 C/H/S 完全一致，改为严格要求零差异。
- 新增“首次直接 MENU 退出取日志”用例一度也让原生 28mm 调用了引擎专属退出断言，因未被引擎接管而失败。该协议只适用于有八行的 50mm/Mount，已收窄测试分支，28mm 继续验证原生路径。

未因上述脚本错误修改候选、放宽容量上限或改写冻结输入。
