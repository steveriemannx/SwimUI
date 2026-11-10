#!/usr/bin/env python3
"""End-to-end tests of the `FerroUI` native module: the SwimUI binding.

The binding is four layers -- the compiler table, the Nim bridge
(runtime/swimferroui.nim), the Rust bridge (ffi/) and FerroUI itself -- and the
tests here check each one where it can be checked without a person in front of
the screen:

1. the compiler: `import FerroUI` resolves as a native module, `Swim emit`
   emits `import swimferroui` and the `swimFerroUI*` calls, and a call without
   the import is reported as an error;
2. the bridge: `Swim check` accepts every program under ui/ and
   tests/binding/, and the shared library exists (built on demand with
   scripts/build-ffi.sh);
3. the demo: it builds, runs, writes a 390 x 844 PNG that is not blank, quits
   by itself and reports no failed bridge call;
4. the binding scene (tests/binding/BindingTest.sw): it changes properties,
   reads them back, raises a click as a pointer would, and writes two
   snapshots that differ.

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


def run(command: list[str], *, cwd: Path = ROOT, env: dict | None = None,
        timeout: int = 900) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.setdefault("SWIM_PATH", str(UI))
    if env:
        environment.update(env)
    debug("$ " + " ".join(str(part) for part in command))
    return subprocess.run([str(part) for part in command], cwd=str(cwd),
                          capture_output=True, text=True, timeout=timeout,
                          env=environment)


def swim(*arguments: str, timeout: int = 900) -> subprocess.CompletedProcess:
    return run([SWIM, *arguments], timeout=timeout)


# ---------------------------------------------------------------------------
# PNG reading: the size and the distinct colours, without a dependency
# ---------------------------------------------------------------------------
def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise Failure("the file is not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


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


# ---------------------------------------------------------------------------
# 1. The compiler
# ---------------------------------------------------------------------------
def test_compiler() -> None:
    log("compiler: the FerroUI native module")
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)

        without = directory / "WithoutImport.sw"
        without.write_text(
            "let h = ferrouiLabel(parent: 0, x: 0, y: 0, width: 10, height: 10,\n"
            '                     text: "x", size: 10, color: 0, align: 0, bold: false)\n'
        )
        result = swim("check", str(without))
        if result.returncode == 0:
            raise Failure("a call of ferrouiLabel without 'import FerroUI' compiled")
        if "import FerroUI" not in result.stdout + result.stderr:
            raise Failure("the missing-import error does not mention 'import FerroUI':\n"
                          + result.stdout + result.stderr)
        log("  a call without the import is reported")

        with_import = directory / "WithImport.sw"
        with_import.write_text(
            "import FerroUI\n"
            "\n"
            "ferrouiRun {\n"
            '    let title = ferrouiVersion()\n'
            '    ferrouiLog(message: "FerroUI " + title)\n'
            "}\n"
        )
        result = swim("check", str(with_import))
        if result.returncode != 0:
            raise Failure("a program with 'import FerroUI' did not compile:\n"
                          + result.stdout + result.stderr)
        log("  'import FerroUI' type-checks")

        result = swim("emit", str(with_import))
        if result.returncode != 0:
            raise Failure("Swim emit failed:\n" + result.stdout + result.stderr)
        nim = result.stdout
        for expected in ("import swimferroui", "swimFerroUIRun(", "swimFerroUIVersion("):
            if expected not in nim:
                raise Failure(f"the generated Nim misses {expected!r}")
        log("  the generated Nim imports swimferroui and calls the bridge")

        module = directory / "FerroUIManual.sw"
        module.write_text(
            "import FerroUI\n"
            "\n"
            "let base = 3\n"
            "ferrouiAfter(ms: 1) {\n"
            '    ferrouiLog(message: "alive")\n'
            "}\n"
        )
        if swim("check", str(module)).returncode != 0:
            raise Failure("a program that only uses ferrouiAfter/ferrouiLog did not compile")
        log("  a program may import FerroUI for its helpers only")


# ---------------------------------------------------------------------------
# 2. The program check of everything under ui/ and tests/binding/
# ---------------------------------------------------------------------------
def test_programs() -> None:
    log("programs: type-check the view layer, the demo and the tests")
    programs = sorted(UI.glob("*.sw")) + sorted(BINDING.glob("*.sw"))
    if not programs:
        raise Failure("no Swim programs under ui/ or tests/binding/")
    for program in programs:
        result = swim("check", str(program))
        if result.returncode != 0:
            raise Failure(f"{program.relative_to(ROOT)} did not type-check:\n"
                          + result.stdout + result.stderr)
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
# 4. The demo
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
    if "swimferroui:" in output:
        raise Failure("the bridge reported a failed call while the demo ran:\n" + output)
    check_png(snapshot, 390, 844, 40)
    log("  the demo ran without a failed bridge call")


# ---------------------------------------------------------------------------
# 5. The binding scene
# ---------------------------------------------------------------------------
EXPECTED_CHECKS = {
    "ready": "true",
    "clientWidth": "320",
    "clientHeight": "480",
    "labelText": "before",
    "buttonText": "tap",
    "fieldText": "field",
    "sliderValue": "10.0",
    "barValue": "10.0",
    "checkboxBefore": "false",
    "visibleBefore": "true",
    "labelTextAfter": "after",
    "buttonTextAfter": "tapped",
    "fieldTextAfter": "changed",
    "sliderValueAfter": "55.0",
    "barValueAfter": "75.0",
    "checkboxAfter": "true",
    "tapsAfterRaise": "1",
    "tapsAfterSecondRaise": "2",
    "movedValue": "55.0",
    "visibleHidden": "false",
    "visibleShown": "true",
    "quitting": "true",
}


def test_binding_scene() -> None:
    log("binding: change properties, read them back, raise a click")
    out = BUILD / "test"
    out.mkdir(parents=True, exist_ok=True)
    before = out / "binding-before.png"
    for path in (before, Path(str(before) + ".after.png")):
        if path.exists():
            path.unlink()
    binary = out / "BindingTest"
    result = swim("build", str(BINDING / "BindingTest.sw"), "-o", str(binary),
                  "--nim-arg:-d:swimFerroUIImage=" + str(before),
                  "--nim-arg:-d:swimFerroUIQuitMs=1900")
    if result.returncode != 0:
        raise Failure("BindingTest.sw did not build:\n" + result.stdout + result.stderr)
    result = run([binary], timeout=300)
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise Failure("BindingTest did not exit cleanly:\n" + output)
    if "swimferroui:" in output:
        raise Failure("the bridge reported a failed call:\n" + output)

    seen: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"^check: ([A-Za-z0-9_]+)=(.*)$", line.strip())
        if match:
            seen[match.group(1)] = match.group(2)
    missing = sorted(set(EXPECTED_CHECKS) - set(seen))
    if missing:
        raise Failure("the checks that did not print: " + ", ".join(missing) + "\n" + output)
    wrong = {name: (seen[name], expected) for name, expected in EXPECTED_CHECKS.items()
             if seen[name] != expected}
    if wrong:
        detail = "\n".join(f"  {name}: {got!r}, expected {expected!r}"
                           for name, (got, expected) in sorted(wrong.items()))
        raise Failure("checks that disagree:\n" + detail + "\n" + output)
    log(f"  {len(seen)} observations agree")

    check_png(before, 320, 480, 30)
    after = Path(str(before) + ".after.png")
    if not after.is_file():
        raise Failure(f"no second snapshot at {after}")
    check_png(after, 320, 480, 30)
    if before.read_bytes() == after.read_bytes():
        raise Failure("the snapshots before and after the changes are identical")
    log("  the snapshots before and after the changes differ")


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

    tests = [test_compiler, test_programs]
    try:
        for test in tests:
            test()
        ensure_bridge(arguments.no_build)
        for test in (test_demo, test_binding_scene):
            test()
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
