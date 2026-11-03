当前前提：Windows runner 的 Chrome 已自带并能加载 SwiftShader 所需的全部运行库，只缺测试启动参数。

同一前提下两组参数都没有取得适配器：035ea43 的 Vulkan/ANGLE 显式选择，4b2d9f2 再增加 GPU 进程设置和 Dawn 开发选项。继续改参数前，先核对这项前提。

平台记录：Linux check 和 macOS 完整套件均已通过 13 组颜色对照；Windows 仅空场景就失败。scripts/windows_probe.py gpu 已记录 Chrome 路径和版本目录中的 vk_swiftshader.dll 文件大小，并实际调用生产引擎的初始化入口。ci-candidate12-probes.log 保留初始化日志；以这些数据核对运行库加载和后台进程状态，再选择修法。

实际记录：Chrome 156.0.8078.80 自带 5406872 B 的 vk_swiftshader.dll。初始化错误是 `Failed to query ID3D11Device from ANGLE`，没有发生在 LUT 或照片处理。Chromium 的 Windows 路径在选择 WebGPU 后端前向 ANGLE 取 D3D11 设备；Vulkan/SwiftShader 的 ANGLE 实现不提供这个设备。新修法将 ANGLE 设为 Windows 自带软件 D3D11 WARP，WebGPU 保持 SwiftShader。删除前两轮无效的 Vulkan 和额外进程选项，等待原生运行核对。

源码依据：https://chromium.googlesource.com/chromium/src/+/lkgr/gpu/command_buffer/service/webgpu_decoder_impl.cc ，https://chromium.googlesource.com/chromium/src/+/master/ui/gl/gl_switches.cc 。
