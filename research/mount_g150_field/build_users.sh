#!/bin/zsh -f
set -euo pipefail
cd "${0:A:h:h:h}"
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/mount-g150
export CLANG_MODULE_CACHE_PATH="$TMPDIR/clang-modules"
mkdir -p "$TMPDIR"
/opt/homebrew/bin/python3 -I -B research/mount_g150_field/build_receipt.py before
product=firmware/engine_v58_g150/candidate/containers/product
core=$product/src/firmware/engine/core
container_src=$product/src/firmware/card_container_v2
exec /Library/Developer/CommandLineTools/usr/bin/clang -std=c11 -O2 -shared -fPIC \
  -DENG_HOST -ffreestanding -fno-builtin -fno-modules \
  -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk \
  -I "$core" -I "$product" -I "$container_src" \
  research/emptystack_v38/host_engine.c "$product/memory.c" "$product/ui_v2_data.c" \
  firmware/engine_v58_g150/candidate/engine_services/crc.c \
  "$core/eng_data.c" "$core/eng_semantic.c" "$core/eng_crc_compat.c" "$core/eng_pin_stub.c" \
  "$container_src/common.c" "$container_src/gate.c" "$container_src/api.c" \
  "$product/kv2/kv_data.c" "$product/kv2/kv_ui.c" "$product/kv2/kv_math.c" "$product/kv2/kv_i64.c" \
  -o "$TMPDIR/g150-host.dylib"
