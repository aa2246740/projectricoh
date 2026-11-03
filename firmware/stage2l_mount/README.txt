Stage2l MOUNT A12 常量替换候选

未审查，不得上卡。payload 8084 B，大于原 Stage2l 的 8080 B，未达到本任务大小条件。
详见 REPORT.md。所有固件、DAT、构建与审计证据只放 local/。

核对与重建：
  python3 -I -B firmware/stage2l_mount/tools/prepare_mount.py
  python3 -I -B firmware/stage2l_mount/tools/verify_mount.py
  python3 -I -B firmware/stage2l_mount/tools/compare_mount.py

compare_mount.py 会保存比较证据，并因大小条件不符返回 1。
复制保留的旧 regen.py / verify.py 适用于原 50mm 研究链，本候选使用上述三个入口。
