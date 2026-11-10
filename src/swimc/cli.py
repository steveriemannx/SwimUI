"""Command line interface for the Swim compiler."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .codegen import generate
from .errors import SwimError
from .modules import load_project
from .types import build_registry


# Swim targets Nim's ARC memory management (automatic reference counting).
# `atomicArc` is like Swift's ARC: reference counts are updated atomically, so
# objects can be shared between threads.  It is opt-in because plain `arc` is
# cheaper for single-threaded programs.
DEFAULT_MEMORY_MANAGEMENT = "arc"
MEMORY_MANAGEMENT_CHOICES = ("arc", "atomicArc", "orc", "refc")

NIM_ERROR_RE = re.compile(r"^(?P<file>.*?)\((?P<line>\d+),\s*(?P<col>\d+)\)\s+"
                          r"(?P<kind>Error|Warning|Hint):\s*(?P<msg>.*)$")


def package_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def runtime_dir() -> Path:
    env = os.environ.get("SWIM_RUNTIME")
    if env:
        return Path(env)
    return package_root() / "runtime"


def nim_executable() -> str:
    env = os.environ.get("SWIM_NIM")
    if env:
        return env
    found = shutil.which("nim")
    if found:
        return found
    for candidate in (Path.home() / ".nimble" / "bin" / "nim",
                      Path.home() / ".choosenim" / "toolchains"):
        if candidate.is_file():
            return str(candidate)
    raise SwimError("could not find the Nim compiler; install Nim or set "
                    "SWIM_NIM")


_COMPILER_SIG: str | None = None


def compiler_signature() -> str:
    """Hash of the compiler sources, so cached binaries invalidate on change."""
    global _COMPILER_SIG
    if _COMPILER_SIG is None:
        h = hashlib.sha1()
        pkg = Path(__file__).resolve().parent
        for py in sorted(pkg.glob("*.py")):
            h.update(py.read_bytes())
        _COMPILER_SIG = h.hexdigest()[:12]
    return _COMPILER_SIG


def cache_dir() -> Path:
    env = os.environ.get("SWIM_CACHE")
    if env:
        path = Path(env)
    else:
        path = Path(tempfile.gettempdir()) / "Swim-build-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class BuildResult:
    nim_source: str
    nim_path: Path
    binary: Path | None = None
    line_map: dict = field(default_factory=dict)
    project: object | None = None  # modules.Project


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
def render_swim_error(err: SwimError, source: str) -> str:
    out = [err.render()]
    if err.line is not None and source:
        lines = source.splitlines()
        idx = err.line - 1
        if 0 <= idx < len(lines):
            gutter = f"{err.line:>4} | "
            out.append("")
            if idx > 0:
                out.append(f"{err.line - 1:>4} | {lines[idx - 1]}")
            out.append(gutter + lines[idx])
            if err.col:
                out.append(" " * (len(gutter) + max(0, err.col - 1)) + "^")
            if idx + 1 < len(lines):
                out.append(f"{err.line + 1:>4} | {lines[idx + 1]}")
    return "\n".join(out)


def translate_nim_errors(stderr: str, result: BuildResult) -> str:
    """Map Nim diagnostics on the generated file back to .sw source lines."""
    out: list[str] = []
    seen: set = set()
    project = result.project
    for raw in stderr.splitlines():
        m = NIM_ERROR_RE.match(raw.strip())
        if not m:
            continue
        kind = m.group("kind")
        if kind == "Hint":
            continue
        gen_line = int(m.group("line"))
        msg = m.group("msg")
        composed = result.line_map.get(gen_line - 1)
        owner = project.path_at_line(composed) if (
            project is not None and composed is not None) else None
        if owner is None:
            if msg not in seen:
                seen.add(msg)
                out.append(f"error: {msg}")
            continue
        path, local_line = owner
        key = (str(path), local_line, msg)
        if key in seen:
            continue
        seen.add(key)
        snippet = ""
        source = project.source_for(path)
        lines = source.splitlines()
        if 0 <= local_line - 1 < len(lines):
            snippet = lines[local_line - 1].strip()
        out.append(f"{path}:{local_line}: error: {msg}")
        if snippet:
            out.append(f"  --> {snippet}")
    if not out:
        out.append(stderr.strip())
    return "\n".join(out)


def error_source(err: SwimError, entry: Path) -> str:
    """Best effort source text for rendering a diagnostic snippet."""
    if err.filename:
        candidate = Path(err.filename)
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf8")
        except OSError:
            pass
    try:
        return entry.read_text(encoding="utf8")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Compilation pipeline
# ---------------------------------------------------------------------------
def compile_project(entry: Path, *, keep: bool = False, nim_only: bool = False,
                    out_path: Path | None = None,
                    nim_args: list[str] | None = None,
                    entry_source: str | None = None,
                    defines: list[str] | None = None,
                    mm: str = DEFAULT_MEMORY_MANAGEMENT) -> BuildResult:
    from .lexer import set_defines
    set_defines(defines)
    project = load_project(entry, entry_source)
    registry = build_registry(project.module, str(entry))
    try:
        nim_code, line_map = generate(project.module, registry, str(entry),
                                      native_modules=project.native_modules)
    except SwimError as err:
        # codegen errors use composed line numbers; map them back to files
        if err.line is not None:
            owner = project.path_at_line(err.line)
            if owner is not None:
                err.filename, err.line = str(owner[0]), owner[1]
        raise

    # The runtime is more than swimrt.nim: the native modules (Nimx, Zeta,
    # FerroUI) are separate Nim files in runtime/ imported by the generated
    # program, so every runtime file goes into the cache key.
    runtime_sig = ""
    rt_dir = runtime_dir()
    if rt_dir.is_dir():
        digest = hashlib.sha1()
        for rt in sorted(rt_dir.glob("*.nim")):
            digest.update(rt.name.encode("utf8"))
            digest.update(b"\0")
            digest.update(rt.read_bytes())
            digest.update(b"\0")
        runtime_sig = digest.hexdigest()[:12]
    elif (rt_dir / "swimrt.nim").exists():
        runtime_sig = hashlib.sha1((rt_dir / "swimrt.nim").read_bytes()).hexdigest()[:12]
    h = hashlib.sha1()
    for sf in project.files:
        h.update(str(sf.path).encode("utf8"))
        h.update(b"\0")
        h.update(sf.source.encode("utf8"))
        h.update(b"\0")
    h.update((__version__ + runtime_sig + compiler_signature() + mm +
              repr(nim_args or []) +
              repr(sorted(defines or []))).encode("utf8"))
    cache_key = h.hexdigest()[:12]
    workdir = cache_dir() / ("src-" + cache_key)
    workdir.mkdir(parents=True, exist_ok=True)
    stem = Path(entry).stem or "program"
    safe_stem = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    if not safe_stem or safe_stem[0].isdigit():
        safe_stem = "swim_" + safe_stem
    nim_path = workdir / f"{safe_stem}.nim"
    if keep:
        nim_path = Path(entry).with_suffix(".nim")
    nim_path.write_text(nim_code)
    result = BuildResult(nim_source=nim_code, nim_path=nim_path,
                         line_map=line_map, project=project)
    if nim_only:
        return result

    binary = Path(out_path) if out_path is not None else workdir / safe_stem
    if out_path is None and binary.exists():
        result.binary = binary
        return result
    cmd = [nim_executable(), "c",
           f"--mm:{mm}",
           "--hints:off", "--warnings:off",
           f"--nimcache:{workdir / 'nimcache'}",
           f"--path:{runtime_dir()}", f"-o:{binary}"]
    if nim_args:
        # Extra compiler flags must come before the source file; anything
        # after it is treated as a program argument by nim.
        cmd.extend(nim_args)
    cmd.append(str(nim_path))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise BuildFailure(translate_nim_errors(proc.stderr, result), result)
    result.binary = binary
    return result


def compile_source(source: str, filename: str, **kwargs) -> BuildResult:
    """Compile an in-memory source as the entry file of a project."""
    return compile_project(Path(filename), entry_source=source, **kwargs)


class BuildFailure(SwimError):
    def __init__(self, message: str, result: BuildResult | None = None):
        super().__init__(message)
        self.result = result


def run_binary(binary: Path, args: list[str]) -> int:
    try:
        proc = subprocess.run([str(binary)] + args)
    except FileNotFoundError:
        raise SwimError(f"could not execute compiled program at {binary}")
    return proc.returncode


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
USAGE = """Swim -- a Swift-flavoured language that compiles to Nim

Usage:
  Swim <file.sw> [args...]     compile and run a program
  Swim run <file.sw> [args...] compile and run a program
  Swim build <file.sw> [-o <out>] [--keep]
                               compile to a native executable
  Swim check <file.sw>         type-check / compile without producing output
  Swim emit <file.sw>          print the generated Nim source
  Swim deps <file.sw>          show resolved module imports and order
  Swim new <name>              create a new program in <name>.sw
  Swim test [options]          run the compiler's test suite (checkout only)
  Swim version                 print the compiler version
  Swim help                    show this help

Options:
  -o, --output <path>   output executable path (build only)
  --keep                write the generated .nim file next to the source
  --release             compile with Nim optimisations (-d:release)
  --cache-dir <path>    override the build cache directory
  -D <name>, --define <name>
                        define a flag for #if conditional compilation
  --mm <mode>           memory management: arc (default), atomicArc, orc, refc
                        (atomicArc = Swift-style atomically refcounted ARC)
  --nim-arg <flag>      extra flag for the Nim compiler (repeatable), e.g.
                        --nim-arg:--path:/opt/nimx

Memory management: ARC by default (--mm:arc); use --mm:atomicArc for Swift
semantics.  License: MIT.
"""

TEMPLATE = r"""// {name}.sw -- a Swim program
// Compile & run with: Swim run {name}.sw

func greet(_ name: String) -> String {{
    return "Hello, \(name)!"
}}

let language = "Swim"
print(greet(language))

var numbers = [1, 2, 3, 4, 5]
print("sum = \(numbers.reduce(0) {{ $0 + $1 }})")
"""


def _load(path: Path) -> str:
    if not path.exists():
        raise SwimError(f"file not found: {path}")
    if path.suffix != ".sw":
        raise SwimError(f"expected a .sw file, got '{path.name}'")
    return path.read_text(encoding="utf8")


def _compile_with_diagnostics(entry: Path, **kwargs):
    """Compile a project and report compiler diagnostics with snippets."""
    try:
        return compile_project(entry, **kwargs)
    except BuildFailure:
        raise
    except SwimError as exc:
        print(render_swim_error(exc, error_source(exc, entry)), file=sys.stderr)
        raise SystemExit(1)


def _parse_common(rest: list[str]) -> tuple[list[str], dict]:
    """Separate file/args from options for the simple commands."""
    opts = {"keep": False, "release": False, "output": None, "cache": None,
            "defines": [], "mm": DEFAULT_MEMORY_MANAGEMENT, "nim_args": []}
    pos: list[str] = []
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg in ("-o", "--output") and i + 1 < len(rest):
            opts["output"] = rest[i + 1]
            i += 2
            continue
        if arg in ("-D", "--define") and i + 1 < len(rest):
            opts["defines"].append(rest[i + 1])
            i += 2
            continue
        if arg.startswith("-D") and len(arg) > 2:
            opts["defines"].append(arg[2:])
            i += 1
            continue
        if arg == "--mm" and i + 1 < len(rest):
            mode = rest[i + 1]
            if mode not in MEMORY_MANAGEMENT_CHOICES:
                raise SwimError(f"unknown memory management mode '{mode}'; "
                                "choose one of " +
                                ", ".join(MEMORY_MANAGEMENT_CHOICES))
            opts["mm"] = mode
            i += 2
            continue
        if arg.startswith("--mm="):
            mode = arg.split("=", 1)[1]
            if mode not in MEMORY_MANAGEMENT_CHOICES:
                raise SwimError(f"unknown memory management mode '{mode}'; "
                                "choose one of " +
                                ", ".join(MEMORY_MANAGEMENT_CHOICES))
            opts["mm"] = mode
            i += 1
            continue
        if arg == "--nim-arg" and i + 1 < len(rest):
            opts["nim_args"].append(rest[i + 1])
            i += 2
            continue
        if arg.startswith("--nim-arg="):
            opts["nim_args"].append(arg.split("=", 1)[1])
            i += 1
            continue
        if arg.startswith("--nim-arg:"):
            opts["nim_args"].append(arg[len("--nim-arg:"):])
            i += 1
            continue
        if arg == "--keep":
            opts["keep"] = True
        elif arg == "--release":
            opts["release"] = True
        elif arg == "--cache-dir" and i + 1 < len(rest):
            opts["cache"] = rest[i + 1]
            i += 2
            continue
        elif arg == "--":
            pos.extend(rest[i + 1:])
            break
        elif not arg.startswith("-") or Path(arg).suffix == ".sw":
            pos.append(arg)
        i += 1
    return pos, opts


def cmd_run(args: list[str]) -> int:
    pos, opts = _parse_common(args)
    if not pos:
        print(USAGE, file=sys.stderr)
        return 2
    path = Path(pos[0])
    _load(path)
    if opts["cache"]:
        os.environ["SWIM_CACHE"] = opts["cache"]
    try:
        nim_args = list(opts["nim_args"])
        if opts["release"]:
            nim_args.append("-d:release")
        result = _compile_with_diagnostics(
            path, keep=opts["keep"], defines=opts["defines"],
            mm=opts["mm"], nim_args=nim_args or None)
    except BuildFailure as exc:
        print(exc.message, file=sys.stderr)
        print("(set --keep to inspect the generated Nim source)", file=sys.stderr)
        return 1
    assert result.binary is not None
    return run_binary(result.binary, pos[1:])


def cmd_build(args: list[str]) -> int:
    pos, opts = _parse_common(args)
    if not pos:
        print(USAGE, file=sys.stderr)
        return 2
    path = Path(pos[0])
    _load(path)
    if opts["cache"]:
        os.environ["SWIM_CACHE"] = opts["cache"]
    out = Path(opts["output"]) if opts["output"] else \
        Path.cwd() / (path.stem or "program")
    try:
        nim_args = list(opts["nim_args"])
        if opts["release"]:
            nim_args.append("-d:release")
        result = _compile_with_diagnostics(
            path, keep=opts["keep"], out_path=out,
            defines=opts["defines"], mm=opts["mm"],
            nim_args=nim_args or None)
    except BuildFailure as exc:
        print(exc.message, file=sys.stderr)
        return 1
    print(f"built {result.binary}")
    return 0


def cmd_new(args: list[str]) -> int:
    if not args:
        print("usage: Swim new <name>", file=sys.stderr)
        return 2
    name = args[0]
    if name.endswith(".sw"):
        name = name[:-3]
    path = Path.cwd() / (name + ".sw")
    if path.exists():
        print(f"error: {path} already exists", file=sys.stderr)
        return 1
    path.write_text(TEMPLATE.format(name=name), encoding="utf8")
    print(f"created {path}")
    print(f"run it with: Swim run {path.name}")
    return 0


def cmd_test(args: list[str]) -> int:
    script = package_root() / "tests" / "run_tests.py"
    if not script.exists():
        print("error: test suite not found (are you running from a checkout?)",
              file=sys.stderr)
        return 1
    proc = subprocess.run([sys.executable, str(script)] + args)
    return proc.returncode


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def cmd_deps(args: list[str]) -> int:
    pos, opts = _parse_common(args)
    if not pos:
        print("usage: Swim deps <file.sw>", file=sys.stderr)
        return 2
    path = Path(pos[0])
    _load(path)
    from .lexer import set_defines
    set_defines(opts["defines"])
    project = load_project(path)
    print(f"module import graph for {path} (execution order, "
          "dependencies first):")
    for index, sf in enumerate(project.files, start=1):
        suffix = "  (entry)" if sf.path == project.entry else ""
        print(f"  {index}. {display_path(sf.path)}{suffix}")
        entries = project.imports.get(sf.path, [])
        if entries:
            parts = []
            for name, target, builtin in entries:
                if builtin:
                    parts.append(f"{name} [builtin]")
                elif target is None:
                    parts.append(f"{name} [native]")
                else:
                    parts.append(f"{name} -> {display_path(target)}")
            print("     imports: " + ", ".join(parts))
    return 0


def cmd_emit(args: list[str]) -> int:
    pos, opts = _parse_common(args)
    if not pos:
        print(USAGE, file=sys.stderr)
        return 2
    path = Path(pos[0])
    _load(path)
    if opts["cache"]:
        os.environ["SWIM_CACHE"] = opts["cache"]
    result = _compile_with_diagnostics(path, nim_only=True,
                                        defines=opts["defines"])
    print(result.nim_source, end="")
    return 0


def cmd_check(args: list[str]) -> int:
    pos, opts = _parse_common(args)
    if not pos:
        print(USAGE, file=sys.stderr)
        return 2
    path = Path(pos[0])
    _load(path)
    nim_args = list(opts["nim_args"])
    try:
        _compile_with_diagnostics(path, defines=opts["defines"], mm=opts["mm"],
                                  nim_args=nim_args or None)
    except BuildFailure as exc:
        print(exc.message, file=sys.stderr)
        return 1
    print(f"{path}: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(USAGE)
        return 0
    cmd = argv[0]
    if cmd == "new":
        return _guard(lambda: cmd_new(argv[1:]))
    if cmd in ("deps", "modules"):
        return _guard(lambda: cmd_deps(argv[1:]))
    if cmd == "test":
        return _guard(lambda: cmd_test(argv[1:]))
    if cmd in ("version", "--version", "-v"):
        print(f"Swim {__version__} (Nim backend, default --mm:"
              f"{DEFAULT_MEMORY_MANAGEMENT}, MIT)")
        return 0
    if cmd == "run":
        return _guard(lambda: cmd_run(argv[1:]))
    if cmd == "build":
        return _guard(lambda: cmd_build(argv[1:]))
    if cmd == "emit":
        return _guard(lambda: cmd_emit(argv[1:]))
    if cmd == "check":
        return _guard(lambda: cmd_check(argv[1:]))
    if cmd.startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2
    # default: run a .sw file
    return _guard(lambda: cmd_run(argv))


def _guard(fn) -> int:
    try:
        return fn()
    except BuildFailure as exc:  # pragma: no cover - safety net
        print(exc.message, file=sys.stderr)
        return 1
    except SwimError as exc:
        print(exc.render(), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
