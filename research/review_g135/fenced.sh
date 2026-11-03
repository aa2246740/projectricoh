#!/bin/sh
# Run a Python script under the review write fence (review_g135 and the permitted g135_v37/local exception only, no network).
cd "$(dirname "$0")/../.." || exit 2
mkdir -p research/review_g135/local/tmp
export TMPDIR="$PWD/research/review_g135/local/tmp" PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
exec /usr/bin/sandbox-exec -f research/review_g135/write-fence.sb /usr/bin/python3 -I -B "$@"
