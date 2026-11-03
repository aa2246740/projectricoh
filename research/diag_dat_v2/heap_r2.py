"""Repeat the heap cases and retain the r1 result unchanged."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import heap_tests
import legacy_call
import scope


def main():
    sys.addaudithook(legacy_call.fence)
    scope.freeze_check()
    heap_tests.LOCAL = scope.HERE / 'local/heap-tests-r2'
    original = scope.save
    def save(path, value):
        if Path(path) == scope.HERE / 'heap-tests.json':
            path = scope.HERE / 'heap-tests-r2.json'
        return original(path, value)
    scope.save = save
    heap_tests.main()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('HEAP_R2 RETURN 1 COUNT 0 TYPE', type(error).__name__)
        raise SystemExit(1)
