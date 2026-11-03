#!/bin/zsh
# 自检全流程：编译 ImageIO 检查程序（只用系统框架）→ 对 15 张跑 → selfcheck.py 汇总。临时文件放外置盘。
set -eu
ROOT=${0:A:h:h:h}
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/hdr-gainmap
OUT=$ROOT/captures/hdr-gainmap-proto
IO=$TMPDIR/imageio
mkdir -p $IO
nice -n 10 swiftc -O -o $TMPDIR/check_imageio $ROOT/research/hdr_gainmap/check_imageio.swift
$TMPDIR/check_imageio $OUT/R805*_HDR.JPG $ROOT/captures/street-g137-20261031/jpg/R8051530.JPG > $IO/info.jsonl
: > $IO/compare.jsonl
for f in $OUT/R805*_HDR.JPG; do
  n=${${f:t}%_HDR.JPG}
  $TMPDIR/check_imageio --compare $ROOT/captures/street-g137-20261031/jpg/$n.JPG $f $IO/c$n.f32 >> $IO/compare.jsonl
done
nice -n 10 $ROOT/studio/.venv/bin/python -I $ROOT/research/hdr_gainmap/selfcheck.py --imageio-dir $IO
