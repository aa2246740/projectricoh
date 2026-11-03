#!/bin/bash
# 裁切走查的启动脚本：临时的假卡、图库、导出、Chrome 配置都放在 _tmp 下，结束后删除。
# 工作室只看得见这个临时卡（GXR_STUDIO_VOLUMES），碰不到真实的卡和图库。
set -u
ROOT=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
STUDIO="$ROOT/studio"
OUT="$ROOT/research/studio_crop_guides"
WORK="$OUT/_tmp"
SHOTS="$OUT/screenshots"
PORT=8799
TOKEN="tok-crop-r1"

cleanup() {
  [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null
  sleep 1
  rm -rf "$WORK"
}
trap cleanup EXIT

rm -rf "$WORK"
mkdir -p "$WORK/vol" "$WORK/lib" "$WORK/exp" "$WORK/appdata" "$WORK/profile" "$SHOTS"
export TMPDIR="$WORK"

cd "$STUDIO" || exit 1
uv run python -m gxr_studio.devtools.synthetic_card "$WORK/vol" --no-real || exit 1

export GXR_STUDIO_VOLUMES="$WORK/vol" GXR_STUDIO_LIBRARY="$WORK/lib" GXR_STUDIO_EXPORT="$WORK/exp"
export GXR_STUDIO_HOME="$WORK/appdata" GXR_STUDIO_TOKEN="$TOKEN"
"$STUDIO/.venv/bin/gxr-studio" --no-browser --port "$PORT" > "$WORK/server.log" 2>&1 &
SERVER_PID=$!

for i in $(seq 1 100); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/health")
  [ "$code" != "000" ] && break
  sleep 0.2
done

WT_BASE="http://127.0.0.1:$PORT" WT_TOKEN="$TOKEN" WT_CDP_PORT=9335 WT_PROFILE="$WORK/profile" WT_SHOTS="$SHOTS" \
  node "$OUT/walkthrough.mjs" > "$OUT/walkthrough-log.txt" 2>&1
echo "walkthrough exit=$?"
cat "$OUT/walkthrough-log.txt"
