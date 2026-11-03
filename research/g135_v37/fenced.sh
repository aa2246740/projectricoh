#!/bin/sh
# Run a Python script under the write fence (only the three g135 directories are writable, no network).
cd "$(dirname "$0")/../.." || exit 2
mkdir -p research/g135_v37/local/tmp
export TMPDIR="$PWD/research/g135_v37/local/tmp" PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
exec /usr/bin/sandbox-exec -f research/g135_v37/write-fence.sb /usr/bin/python3 -I -B "$@"
