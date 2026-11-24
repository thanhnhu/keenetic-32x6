#!/usr/bin/env python3
"""Patch the Keenetic web UI bundle (ndw4 main-*.js) so it stops calling `ndns get-booked` outside router mode.

Problem (measured 2026-10-14 on v28, extender mode): the UI's KeenDNS service
(`getExtendedConfiguration()`) calls RCI `ndns get-booked` whenever `show ndns` has no `updated`
state, and calls itself again when that returns without errors. ndm queues RCI per session, one
task at a time, and `Ndns::Client` needs 13-30 s to give up ("unable to get a booked name") when the
cloud is unreachable (extender mode has no registered connection). Every request of the logged-in
session waits behind it, so pages spin for up to ~30 s; each freeze ended on the exact second of that
log line. The UI has exactly one call site:

  return this.ndnsGetBookedApi.performContinued().pipe(Ne(a=>$3.keys(Cr.getErrors(a)).length?q({noAccess:!0}):this.getExtendedConfiguration()))

Patched to keep Keenetic's behaviour in router mode and answer "no access" immediately otherwise:

  return this.NDM.isInRouterMode()?<original expression>:q({noAccess:!0})

Minified identifiers differ between releases, so they are captured by regex; the script refuses
anything but exactly one match, is idempotent, and only rewrites the JS text (no offsets inside).
Run on the staged rootfs file usr/share/htdocs_/main-*.js (same place as ndmConstants.json).
"""
import re
import sys

ORIG = re.compile(
    rb"return (this\.ndnsGetBookedApi\.performContinued\(\)\.pipe\("
    rb"(\w+)\((\w+)=>(\$?\w+)\.keys\((\w+)\.getErrors\(\3\)\)\.length\?"
    rb"(\w+)\(\{noAccess:!0\}\):this\.getExtendedConfiguration\(\)\)\))"
)
DONE = b"return this.NDM.isInRouterMode()?this.ndnsGetBookedApi.performContinued()"


def patch(data):
    """Return (new_data, state) with state in {"patched", "already"}; exit on anything unexpected."""
    calls = data.count(b"ndnsGetBookedApi.performContinued(")
    if data.count(DONE) == 1 and calls == 1 and not ORIG.search(data):
        return data, "already"
    hits = list(ORIG.finditer(data))
    if calls != 1 or len(hits) != 1:
        sys.exit(f"ABORT: expected one ndnsGetBookedApi.performContinued() call site in the UI bundle, "
                 f"found {calls} call(s), {len(hits)} match(es) (new release? re-check the bundle)")
    m = hits[0]
    of = m.group(6)
    new = b"return this.NDM.isInRouterMode()?" + m.group(1) + b":" + of + b"({noAccess:!0})"
    return data[:m.start()] + new + data[m.end():], "patched"


def main(path):
    data = open(path, "rb").read()
    new, state = patch(data)
    if state == "already":
        print(f"skip (already patched): {path}")
        return
    open(path, "wb").write(new)
    print(f"patched: {path} ({len(data)} -> {len(new)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
