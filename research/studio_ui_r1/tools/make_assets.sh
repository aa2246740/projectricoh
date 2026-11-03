#!/bin/zsh
# 把几张 GXR 相机 JPG 复制成设计稿用的小图（只读原文件，输出到 screens/assets/photos）。
set -e
ROOT=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
OUT=$ROOT/research/studio_ui_r1/screens/assets/photos
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-ui-design-r1/tmp
G150=$ROOT/captures/street-g150-20261101
G137=$ROOT/captures/street-g137-20261031/jpg
LARGE=(R8051757 R8051629 R8051767 R8051783 R8051729 R8051737 R8051707 R8051554 R8051763)
ALL=(R8051707 R8051709 R8051721 R8051723 R8051729 R8051735 R8051737 R8051741 R8051745 R8051753 R8051757 R8051763 R8051767 R8051771 R8051775 R8051783 R8051795 R8051530 R8051539 R8051542 R8051554 R8051557 R8051560 R8051569 R8051581 R8051584 R8051629 R8051632 R8051659 R8051671)
src() { [[ -f $G150/$1.JPG ]] && echo $G150/$1.JPG || echo $G137/$1.JPG; }
for n in $ALL; do magick "$(src $n)" -auto-orient -resize 480x480 -strip -quality 78 $OUT/thumb/$n.jpg; done
for n in $LARGE; do magick "$(src $n)" -auto-orient -resize 2000x2000 -strip -quality 82 $OUT/large/$n.jpg; done
