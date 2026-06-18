"""
Run the full golden-test suite with one command (no pytest dependency required):

    python tests/run_all.py

Exits non-zero if any test fails, so it doubles as a CI gate.
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODULES = ["tests.test_waterfall", "tests.test_tax", "tests.test_state_qsbs",
           "tests.test_montecarlo", "tests.test_reverse"]


def main():
    total = passed = 0
    for modname in MODULES:
        mod = importlib.import_module(modname)
        fns = [v for k, v in sorted(vars(mod).items()) if k.startswith("test_") and callable(v)]
        print(f"\n=== {modname} ===")
        for fn in fns:
            total += 1
            try:
                fn()
                print(f"  PASS  {fn.__name__}")
                passed += 1
            except AssertionError as e:
                print(f"  FAIL  {fn.__name__}: {e}")
            except Exception as e:  # noqa
                print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{'='*40}\nTOTAL: {passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
