# P0 探针操作

仅在独立复核批准本次 SHA 后执行。r3 候选为 53,100 B，SHA256：

```text
75edcedac2219d31a1cc2e789e9ecc7381df528ee1e94d4b5e08329a668c2e87
```

1. 关机，保持 50mm。备份卡 B 的 `GXRBX0/1.BIN`；把产品 `GXRCE.DAT/OK/CTL` 及实际存在的刷机文件 `ilaunch*、jlaunch*、klaunch*、l06firm*、l08firm*、nlaunch*、qlaunch*、DEEPTBL*` 备份并移出卡 B，留在电脑。照片目录、卡 A 不动。
2. 先不放探针，普通电源冷启动，打开 ADJ 的 Image Settings，记录原产品表现与日志，再关机。这是回退基线；不按刷机组合键。
3. 仅把本次获批 SHA 的 `local/staged/GXRCE.DAT` 放到卡 B 根目录，核对大小和 SHA，安全推出，再普通电源开机，打开同一配方页。
4. 看到 `P0 REF` 就启动秒表，留在页内约 10 秒；按 OK 同时停表，记下实际秒数。若中途退出、休眠、首次发布失败或出现 RESTART，关机后从探针冷启动重来，丢弃本次计时。
5. 重开同一页，按住向下直到 `P0 LUT17 DONE`；不连发就逐次点按。先经过四档 CHECK，再取得 72 条样本。确认 `SAMPLES 48/48 hex`、`ERROR 00000000`、`FLUSH 00000001`，记录 `REF DT` 后按 MENU；不满足就不用结果。
6. 关机，保留两份 `GXRBX0/1.BIN` 和实际秒数供主机解码，删除探针 DAT，再普通电源冷启动核对第 2 步基线。旧产品 DAT 留在电脑，绝不自动放回。卡住时先关机移走探针；仍不恢复则用已验证的卡 A Stage2l、50mm 和“+ & playback”恢复。
