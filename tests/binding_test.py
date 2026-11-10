#!/usr/bin/env python3
"""End-to-end tests of the `FerroUI` native module and of the SwiftUI-shaped
layer of SwimUI.

The binding is four layers -- the compiler table, the C shim
(runtime/swimferroui.c), the Rust bridge (ffi/) and FerroUI itself -- with a
declarative view layer (ui/SwiftUI.sw) on top of it.  The tests check each
layer where it can be checked without a person in front of the screen:

1. the compiler: `import FerroUI` resolves as a native module, `Swim emit`
   emits `#include "swimferroui.h"` and the `swimferroui_*` calls, a call
   without the import is reported, and the retired `import Nimx` explains
   itself;
2. the programs: every program under ui/ and tests/binding/ type-checks and
   builds, with the C shim compiled in and the bridge linked;
3. the native module (tests/binding/NativeTest.sw): every control, the
   setters and getters, events raised as a pointer would raise them, timers and
   two snapshots that differ, with no failed bridge call;
4. the layer (tests/binding/SwiftUITest.sw): state changes re-render and patch
   the mounted controls in place (the text read back from the controls proves
   it), a click raised as a pointer would runs the button action, and the
   snapshot before and after the state change differ;
5. the demo (ui/LibraryApp.sw): it runs, writes a 390 x 844 PNG with content,
   quits by itself and reports no failed bridge call.

Usage:
    python3 tests/binding_test.py [--no-build] [-v]

`--no-build` fails instead of building the bridge when it is missing.
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWIM = ROOT / "bin" / "Swim"
BUILD = ROOT / "build"
UI = ROOT / "ui"
BINDING = ROOT / "tests" / "binding"
BRIDGE = {
    "Darwin": BUILD / "libferroui_swim.dylib",
    "Linux": BUILD / "libferroui_swim.so",
}.get(os.uname().sysname, BUILD / "libferroui_swim.so")

VERBOSE = False


class Failure(Exception):
    pass


def log(message: str) -> None:
    print(message)


def debug(message: str) -> None:
    if VERBOSE:
        print("  " + message)


def environment(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env.setdefault("SWIM_PATH", str(UI))
    # The tests must not inherit the settings of a documentation run.
    env.pop("SWIMUI_IMAGE", None)
    env.pop("SWIMUI_QUIT_MS", None)
    if extra:
        env.update(extra)
    return env


def run(command: list[str], *, env: dict | None = None,
        timeout: int = 900) -> subprocess.CompletedProcess:
    debug("$ " + " ".join(str(part) for part in command))
    return subprocess.run([str(part) for part in command], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=timeout,
                          env=environment(env))


def swim(*arguments: str, env: dict | None = None,
         timeout: int = 900) -> subprocess.CompletedProcess:
    return run([SWIM, *arguments], env=env, timeout=timeout)


# ---------------------------------------------------------------------------
# PNG reading: the size and the distinct colours, without a dependency
# ---------------------------------------------------------------------------
def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise Failure("the file is not a PNG")
    return struct.unpack(">II", data[16:24])


def png_colours(data: bytes) -> set[bytes]:
    """The distinct pixels of a non-interlaced 8-bit PNG (grey, RGB or RGBA)."""
    position = 8
    width = height = bit_depth = colour_type = interlace = 0
    compressed = bytearray()
    while position < len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8]
        payload = data[position + 8:position + 8 + length]
        if kind == b"IHDR":
            width, height, bit_depth, colour_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
        position += 12 + length
    if bit_depth != 8 or interlace != 0 or colour_type not in (0, 2, 4, 6):
        return set()
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colour_type]
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    previous = bytearray(stride)
    colours: set[bytes] = set()
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset:offset + stride])
        offset += stride
        for i in range(stride):
            left = row[i - channels] if i >= channels else 0
            up = previous[i]
            up_left = previous[i - channels] if i >= channels else 0
            if filter_type == 1:
                row[i] = (row[i] + left) & 0xFF
            elif filter_type == 2:
                row[i] = (row[i] + up) & 0xFF
            elif filter_type == 3:
                row[i] = (row[i] + (left + up) // 2) & 0xFF
            elif filter_type == 4:
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                predictor = left if pa <= pb and pa <= pc else (up if pb <= pc else up_left)
                row[i] = (row[i] + predictor) & 0xFF
        for x in range(0, stride, channels):
            colours.add(bytes(row[x:x + channels]))
        previous = row
    return colours


def check_png(path: Path, width: int, height: int, minimum_colours: int) -> None:
    if not path.is_file():
        raise Failure(f"no snapshot at {path}")
    data = path.read_bytes()
    size = png_size(data)
    if size != (width, height):
        raise Failure(f"{path.name}: {size[0]}x{size[1]}, expected {width}x{height}")
    colours = png_colours(data)
    if len(colours) < minimum_colours:
        raise Failure(f"{path.name}: only {len(colours)} colours, the image is blank")
    log(f"  {path.name}: {width}x{height}, {len(colours)} colours")


def check_no_bridge_errors(output: str) -> None:
    if "swimferroui:" in output:
        raise Failure("the bridge reported a failed call:\n" + output)


def check_lines(output: str) -> dict[str, str]:
    seen: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"^check: ([A-Za-z0-9_]+)=(.*)$", line.strip())
        if match:
            seen[match.group(1)] = match.group(2)
    return seen


def assert_checks(seen: dict[str, str], expected: dict[str, str], output: str) -> None:
    missing = sorted(set(expected) - set(seen))
    if missing:
        raise Failure("the checks that did not print: " + ", ".join(missing) + "\n" + output)
    wrong = {name: (seen[name], want) for name, want in expected.items()
             if seen[name] != want}
    if wrong:
        detail = "\n".join(f"  {name}: {got!r}, expected {want!r}"
                           for name, (got, want) in sorted(wrong.items()))
        raise Failure("checks that disagree:\n" + detail + "\n" + output)


# ---------------------------------------------------------------------------
# 1. The compiler
# ---------------------------------------------------------------------------
def test_compiler() -> None:
    log("compiler: the FerroUI native module")
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)

        without = directory / "WithoutImport.sw"
        without.write_text('let unused = ferrouiLog(message: "no import")\n')
        result = swim("check", str(without))
        if result.returncode == 0:
            raise Failure("a call of a ferroui* function without 'import FerroUI' compiled")
        if "import FerroUI" not in result.stdout + result.stderr:
            raise Failure("the missing-import error does not mention 'import FerroUI':\n"
                          + result.stdout + result.stderr)
        log("  a call without the import is reported")

        retired = directory / "Retired.sw"
        retired.write_text("import Nimx\n\nprint(1)\n")
        result = swim("check", str(retired))
        if result.returncode == 0:
            raise Failure("the retired 'import Nimx' compiled")
        if "retired" not in result.stdout + result.stderr:
            raise Failure("the retired module error does not explain itself:\n"
                          + result.stdout + result.stderr)
        log("  the retired Nimx module explains itself")

        with_import = directory / "WithImport.sw"
        with_import.write_text(
            "import FerroUI\n"
            "\n"
            'ferrouiSetThemeVariant(name: "dark")\n'
            "ferrouiRun {\n"
            "    let window = ferrouiWindow(width: 320, height: 200,\n"
            '                               title: "Compiler", background: 0x0B0C10,\n'
            "                               onClosed: {})\n"
            "    let canvas = ferrouiCreate(parent: window, kind: 1)\n"
            "    let label = ferrouiCreate(parent: canvas, kind: 4)\n"
            '    ferrouiSetString(handle: label, property: 1, value: "compiler")\n'
            "    ferrouiQuit()\n"
            "}\n"
        )
        result = swim("check", str(with_import))
        if result.returncode != 0:
            raise Failure("a program with 'import FerroUI' did not compile:\n"
                          + result.stdout + result.stderr)
        log("  'import FerroUI' type-checks and builds with the C shim")

        result = swim("emit", str(with_import))
        if result.returncode != 0:
            raise Failure("Swim emit failed:\n" + result.stdout + result.stderr)
        c_code = result.stdout
        for expected in ('#include "swimferroui.h"', "swimferroui_run(",
                         "swimferroui_window(", "swimferroui_create(",
                         "swimferroui_set_string("):
            if expected not in c_code:
                raise Failure(f"the generated C misses {expected!r}")
        log("  the generated C includes the shim and calls the bridge")


# ---------------------------------------------------------------------------
# 2. Build every program of the binding
# ---------------------------------------------------------------------------
def test_programs() -> None:
    log("programs: the view layer, the demo and the tests")
    programs = sorted(UI.glob("*.sw")) + sorted(BINDING.glob("*.sw"))
    if not programs:
        raise Failure("no Swim programs under ui/ or tests/binding/")
    out = BUILD / "test"
    out.mkdir(parents=True, exist_ok=True)
    for program in programs:
        target = out / program.stem
        result = swim("build", str(program), "-o", str(target))
        if result.returncode != 0:
            raise Failure(f"{program.relative_to(ROOT)} did not build:\n"
                          + result.stdout + result.stderr)
        debug(f"built {target}")
        log(f"  {program.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# 3. The bridge
# ---------------------------------------------------------------------------
def ensure_bridge(no_build: bool) -> None:
    if BRIDGE.is_file():
        log(f"bridge: {BRIDGE.relative_to(ROOT)} exists")
        return
    if no_build:
        raise Failure(f"the bridge is not built ({BRIDGE}); run scripts/build-ffi.sh")
    log("bridge: building it (this takes a while the first time)")
    result = run([ROOT / "scripts" / "build-ffi.sh"])
    if result.returncode != 0:
        raise Failure("scripts/build-ffi.sh failed:\n" + result.stdout + result.stderr)
    if not BRIDGE.is_file():
        raise Failure("scripts/build-ffi.sh produced no bridge library")
    log(f"bridge: {BRIDGE.relative_to(ROOT)} built")


# ---------------------------------------------------------------------------
# 4. The native module test
# ---------------------------------------------------------------------------
NATIVE_CHECKS = {
    "text": "typed",
    "buttonTitle": "Tap me",
    "sliderValue": "25.0",
    "checked": "true",
    "visible": "true",
    "hidden": "false",
    "toggled": "true",
    "extraChildReleased": "true",
    "tapsAfterRaise": "2",
    "sliderSet": "90.0",
    "valuesSeen": "1",
}


def test_native_module() -> None:
    log("native: controls, properties, events, timers, snapshots")
    out = BUILD / "test"
    binary = out / "NativeTest"
    if not binary.is_file():
        raise Failure("build/test/NativeTest is missing (see the program test)")
    image = out / "native.png"
    after = Path(str(image) + ".after.png")
    for path in (image, after):
        if path.exists():
            path.unlink()
    result = run([binary], env={"SWIMUI_IMAGE": str(image),
                                "SWIMUI_QUIT_MS": "1600"}, timeout=300)
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise Failure("NativeTest did not exit cleanly:\n" + output)
    check_no_bridge_errors(output)
    assert_checks(check_lines(output), NATIVE_CHECKS, output)
    log(f"  {len(NATIVE_CHECKS)} observations agree")
    check_png(image, 320, 260, 30)
    check_png(after, 320, 260, 30)
    if image.read_bytes() == after.read_bytes():
        raise Failure("the native snapshots before and after the changes are identical")
    log("  the two snapshots differ")


# ---------------------------------------------------------------------------
# 5. The SwiftUI layer test
# ---------------------------------------------------------------------------
LAYER_CHECKS = {
    "tapped": "true",
    "slider": "80.0",
    "done": "true",
}


def test_swiftui_layer() -> None:
    log("layer: state, re-render/patch, a click, snapshots")
    out = BUILD / "test"
    binary = out / "SwiftUITest"
    if not binary.is_file():
        raise Failure("build/test/SwiftUITest is missing (see the program test)")
    base = out / "swiftui.png"
    before = Path(str(base) + ".before.png")
    after = Path(str(base) + ".after.png")
    for path in (before, after, base):
        if path.exists():
            path.unlink()
    result = run([binary], env={"SWIMUI_IMAGE": str(base),
                                "SWIMUI_QUIT_MS": "1300"}, timeout=300)
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise Failure("SwiftUITest did not exit cleanly:\n" + output)
    check_no_bridge_errors(output)
    seen = check_lines(output)
    assert_checks(seen, LAYER_CHECKS, output)
    texts = seen.get("texts", "")
    # The controls were patched in place: the text read back from the mounted
    # controls shows the state written after the first render, and the click of
    # the "Add" button ran the action (5 + 1 = 6).
    for expected in ("count=6", "toggle=true", "slider=80", "text=typed",
                     "rows=1", "Add", "row one"):
        if expected not in texts:
            raise Failure(f"the patched controls do not show {expected!r}:\n  {texts}")
    log("  the mounted controls show the new state")
    check_png(before, 320, 560, 30)
    check_png(after, 320, 560, 30)
    if before.read_bytes() == after.read_bytes():
        raise Failure("the layer snapshots before and after the state change are identical")
    log("  the two snapshots differ")


# ---------------------------------------------------------------------------
# 6. The demo
# ---------------------------------------------------------------------------
def test_demo() -> None:
    log("demo: build, run, snapshot, quit")
    snapshot = BUILD / "test" / "demo.png"
    if snapshot.exists():
        snapshot.unlink()
    result = run([ROOT / "scripts" / "run-demo.sh", "--snapshot", str(snapshot)])
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise Failure("the demo did not exit cleanly:\n" + output)
    check_no_bridge_errors(output)
    check_png(snapshot, 390, 844, 40)
    log("  the demo ran without a failed bridge call")


# ---------------------------------------------------------------------------
def main() -> int:
    global VERBOSE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true",
                        help="fail instead of building the bridge when it is missing")
    parser.add_argument("-v", "--verbose", action="store_true")
    arguments = parser.parse_args()
    VERBOSE = arguments.verbose

    if not SWIM.is_file():
        print(f"no Swim launcher at {SWIM}", file=sys.stderr)
        return 1
    BUILD.mkdir(exist_ok=True)

    try:
        test_compiler()
        ensure_bridge(arguments.no_build)
        test_programs()
        test_native_module()
        test_swiftui_layer()
        test_demo()
    except Failure as failure:
        print()
        print("FAILED:", failure)
        return 1
    except subprocess.TimeoutExpired as timeout:
        print()
        print("FAILED: a program did not finish:", timeout)
        return 1
    print()
    print("binding tests: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
