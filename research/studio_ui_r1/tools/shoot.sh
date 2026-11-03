#!/bin/zsh
# 用无界面 Chrome 给每张设计稿截两种尺寸。Chrome 用户目录在临时盘，截完自行退出。
# 用法：tools/shoot.sh [页面名前缀...]
set -e
R=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/studio_ui_r1
S=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-ui-design-r1
export TMPDIR=$S/tmp
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
mkdir -p $S/chrome $R/screenshots
pages=(${@:-$(cd $R/screens && ls [0-9]*.html | sed 's/\.html$//')})
for p in $pages; do
  sizes=(1728x1117 1920x1080); hide=--hide-scrollbars
  # Windows 风格那张只截 1920×1080（100% 缩放），并保留滚动条
  if [[ $p == *-Windows-* ]]; then sizes=(1920x1080); hide=--enable-features=OverlayScrollbar:disabled; fi
  for size in $sizes; do
    w=${size%x*}; h=${size#*x}
    "$CHROME" --headless=new --user-data-dir=$S/chrome --no-first-run --no-default-browser-check --disable-extensions \
      --disable-sync $hide --force-device-scale-factor=1 --window-size=$w,$h --virtual-time-budget=2500 \
      --screenshot="$R/screenshots/$p-$size.png" "file://$R/screens/$p.html" >/dev/null 2>&1
  done
  echo "shot $p"
done
