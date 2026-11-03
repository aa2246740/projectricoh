本件是 HOST 候选：无 C120/C004/C100/C040 写探针，真实休眠/模式失效未闭合，尚未满足完整上机规格。
拍摄场景预留灰卡加色卡，M 档、ISO 200，固定白平衡与曝光；本版各行相机照片均为 0 张。
仅 50mm/jlaunch 1.51；八行为 BASE、TIME、LUT、RESULTS、REF HISTORY、33 NOT FIT、MCM OMITTED、MCM1 351b6621。
BASE 按 OK，重开看 BASE OK；只比对首次 H01 的 260 B 读回记录，不触发配置重建。
TIME 按 OK 后重开 ADJ，看到 REF RUN 才启动手机秒表；约 30 s 时按 OK，同时停表，记实际秒数。
重开记录 REF 的 start/end/delta/run，至少两次；退出、切模式、休眠或出错时主动作废并冷启动重做。
LUT 按 OK 后重开，每按一次 DOWN 推进一块直到 DONE；LOW RES 不用于精确换算。
DONE 按 OK 后重开，DOWN 翻样本页，每页手机拍屏 1 张；REF HISTORY 中每个参考也拍 1 张。
错误、版本不符或 50MM ONLY 时停止；关机后按 CARD_SWAP.md 换回已验收、绑定 v3.6 的 gen117/gen118 DAT。
