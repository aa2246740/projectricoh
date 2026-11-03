#!/bin/zsh
# usage: run.sh <cmd...>  — runs under the fotufilm sandbox with HOME/TMPDIR in Scratch
W=/Volumes/Workspace/Scratch/tmp/projectricoh/fotufilm
export HOME=$W/home TMPDIR=$W/tmp/ HALIDE_ROOT=$W/deps/halide/Halide-21.0.0-arm-64-osx FOTUFILM_COMPILED_CACHE=0 CLANG_MODULE_CACHE_PATH=$W/tmp/clang-mc
export SDKROOT=/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun_nocache=1
exec nice -n 10 /usr/bin/sandbox-exec -f $W/sb/fotufilm.sb "$@"
