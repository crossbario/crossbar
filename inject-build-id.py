#!/usr/bin/env python3
#
# Stamp the build ID from CROSSBAR_BUILD_ID into the __build__ placeholder of _version.py,
# right before building the wheel and sdist (see `just dist`, issue #2231). Modifies the file
# in place: the stamped value is never committed. Leaves the file alone when the variable is
# not set (local and dev builds keep the placeholder).
#
# Usage: CROSSBAR_BUILD_ID=20261020-abc1234 python inject-build-id.py [path/to/_version.py]

import os
import re
import sys

_EVAR = "CROSSBAR_BUILD_ID"
_SEARCH = '__build__ = "19000101-0000000"'
_REPLACE = '__build__ = "{}"'

if __name__ == "__main__":
    fn = sys.argv[1] if len(sys.argv) > 1 else "src/crossbar/_version.py"
    build_id = os.environ.get(_EVAR)
    if not build_id:
        print("Skipping injection of build ID: {} not set".format(_EVAR))
        sys.exit(0)
    if not re.fullmatch(r"[0-9]{8}-[0-9a-f]{7,40}", build_id):
        print('Error: {}="{}" is not of the form YYYYMMDD-<git sha>'.format(_EVAR, build_id))
        sys.exit(1)
    with open(fn) as f:
        contents = f.read()
    if _REPLACE.format(build_id) in contents:
        print('Ok: build ID "{}" already stamped into "{}"'.format(build_id, fn))
        sys.exit(0)
    if contents.count(_SEARCH) != 1:
        print('Error: build ID placeholder {} not found once in "{}"'.format(_SEARCH, fn))
        sys.exit(1)
    with open(fn, "w") as f:
        f.write(contents.replace(_SEARCH, _REPLACE.format(build_id)))
    print('Ok: stamped build ID "{}" into "{}"'.format(build_id, fn))
