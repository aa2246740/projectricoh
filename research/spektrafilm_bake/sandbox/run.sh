#!/bin/zsh
# usage: run.sh <cmd...>  — runs under the spektrafilm sandbox with HOME/TMPDIR/caches in Scratch, cwd = empty work dir
W=/Volumes/Workspace/Scratch/tmp/projectricoh/spektrafilm
export HOME=$W/home TMPDIR=$W/tmp/ UV_CACHE_DIR=$W/uv-cache UV_PYTHON_INSTALL_DIR=$W/python UV_NO_CONFIG=1 UV_OFFLINE=1
export MPLCONFIGDIR=$W/home/mpl NUMBA_CACHE_DIR=$W/home/numba XDG_CACHE_HOME=$W/home/cache PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-4} NUMBA_NUM_THREADS=${NUMBA_NUM_THREADS:-4} OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
cd $W/work || exit 1
exec nice -n 10 /usr/bin/sandbox-exec -f $W/sb/spektrafilm.sb "$@"
