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
from .checker import check as check_program
from .codegen_c import generate as generate_c
from .errors import SwimError
from .modules import load_project
from . import native_ferroui as ferro
from .types import build_registry


# The direct C backend always uses Swift-style atomically refcounted ARC.
DEFAULT_MEMORY_MANAGEMENT = "atomicArc"
MEMORY_MANAGEMENT_CHOICES = ("atomicArc",)

NIM_ERROR_RE = re.compile(r"^(?P<file>.*?)\((?P<line>\d+),\s*(?P<col>\d+)\)\s+"
                          r"(?P<kind>Error|Warning|Hint):\s*(?P<msg>.*)$")


def package_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def runtime_dir() -> Path:
    env = os.environ.get("SWIM_RUNTIME")
    if env:
        return Path(env)
    return package_root() / "runtime"


def cc_executable() -> str:
    env = os.environ.get("SWIM_CC")
    if env:
        return env
    for candidate in ("cc", "clang", "gcc"):
        found = shutil.which(candidate)
        if found:
            return found
    raise SwimError("could not find a C compiler; install clang or gcc")


def runtime_sources() -> list[Path]:
    rt = runtime_dir()
    return sorted(rt.glob("swimrt_*.c")) + [rt / "swimrt_core.c"] * 0


def runtime_source_files() -> list[Path]:
    rt = runtime_dir()
    out = [rt / "swimrt_core.c", rt / "swimrt_collections.c",
           rt / "swimrt_call.c", rt / "swimrt_builtin.c", rt / "swimrt_error.c"]
    return [p for p in out if p.exists()]


class NativeLink:
    """What a program with native modules needs: extra sources, includes and
    libraries, and the files its cache key must cover."""

    def __init__(self, modules: list[str]) -> None:
        self.sources: list[Path] = []
        self.include_dirs: list[Path] = []
        self.link_flags: list[str] = []
        self.files: list[Path] = []
        self.library_dir: Path | None = None
        if ferro.MODULE_NAME not in modules:
            return
        shim = runtime_dir() / ferro.SHIM_SOURCE
        header = runtime_dir() / ferro.SHIM_HEADER
        abi_header = package_root() / "ffi" / "include" / "ferroui_swim.h"
        self.sources.append(shim)
        self.include_dirs.append(package_root() / "ffi" / "include")
        self.files.extend([shim, header, abi_header])
        lib_dir = os.environ.get(ferro.LIBRARY_DIR_ENV)
        self.library_dir = Path(lib_dir) if lib_dir else package_root() / "build"
        self.link_flags.append("-L%s" % self.library_dir)
        self.link_flags.append("-l%s" % ferro.LIBRARY_NAME)
        if os.name != "nt":
            self.link_flags.append("-Wl,-rpath,%s" % self.library_dir)


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
    source: str
    source_path: Path
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


def translate_cc_errors(stderr: str, result: BuildResult) -> str:
    """Map C compiler diagnostics back to .sw source lines where possible."""
    out: list[str] = []
    seen: set = set()
    project = result.project
    pattern = re.compile(r"^(?P<file>.*?):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
                         r"(?P<kind>error|warning):\s*(?P<msg>.*)$")
    for raw in stderr.splitlines():
        m = pattern.match(raw.strip())
        if not m:
            continue
        if m.group("kind") == "warning":
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
        lines = source.split("\n")
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
def compile_project(entry: Path, *, keep: bool = False, emit_only: bool = False,
                    out_path: Path | None = None,
                    cc_args: list[str] | None = None,
                    entry_source: str | None = None,
                    defines: list[str] | None = None,
                    mm: str = DEFAULT_MEMORY_MANAGEMENT) -> BuildResult:
    from .lexer import set_defines
    set_defines(defines)
    project = load_project(entry, entry_source)
    registry = build_registry(project.module, str(entry))
    # Static semantic checking (pure Python, no code emission).
    try:
        check_program(project.module, registry, str(entry),
                      native_modules=getattr(project, "native_modules", []))
    except SwimError as err:
        if err.line is not None:
            owner = project.path_at_line(err.line)
            if owner is not None:
                err.filename, err.line = str(owner[0]), owner[1]
        raise

    c_code = generate_c(project.module, registry, str(entry),
                        native_modules=project.native_modules)
    line_map: dict = {}
    native = NativeLink(project.native_modules)
    runtime_sig = ""
    h = hashlib.sha1()
    for src in runtime_source_files():
        h.update(src.read_bytes())
    hdr = runtime_dir() / "swimrt.h"
    if hdr.exists():
        h.update(hdr.read_bytes())
    for path in native.files:
        h.update(path.name.encode("utf8"))
        if path.exists():
            h.update(path.read_bytes())
    runtime_sig = h.hexdigest()[:12]
    for sf in project.files:
        h.update(str(sf.path).encode("utf8"))
        h.update(b"\0")
        h.update(sf.source.encode("utf8"))
        h.update(b"\0")
    h.update((__version__ + runtime_sig + compiler_signature() +
              repr(cc_args or []) +
              repr(sorted(defines or []))).encode("utf8"))
    cache_key = h.hexdigest()[:12]
    workdir = cache_dir() / ("src-" + cache_key)
    workdir.mkdir(parents=True, exist_ok=True)
    stem = Path(entry).stem or "program"
    safe_stem = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    if not safe_stem or safe_stem[0].isdigit():
        safe_stem = "swim_" + safe_stem
    c_path = workdir / f"{safe_stem}.c"
    if keep:
        c_path = Path(entry).with_suffix(".c")
    c_path.write_text(c_code)
    result = BuildResult(source=c_code, source_path=c_path,
                         line_map=line_map, project=project)
    if emit_only:
        return result

    binary = Path(out_path) if out_path is not None else workdir / safe_stem
    if out_path is None and binary.exists():
        result.binary = binary
        return result
    cmd = [cc_executable(), "-std=c11", "-O2", "-w",
           "-I", str(runtime_dir())]
    for include in native.include_dirs:
        if include.exists():
            cmd.extend(["-I", str(include)])
    cmd.append(str(c_path))
    cmd.extend(str(p) for p in runtime_source_files())
    cmd.extend(str(p) for p in native.sources)
    cmd.extend(["-o", str(binary)])
    cmd.extend(native.link_flags)
    cmd.append("-lm")
    if cc_args:
        cmd[1:1] = cc_args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise BuildFailure(translate_cc_errors(proc.stderr, result), result)
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
USAGE = """Swim -- a Swift-flavoured language that compiles to C

Usage:
  Swim <file.sw> [args...]     compile and run a program
  Swim run <file.sw> [args...] compile and run a program
  Swim build <file.sw> [-o <out>] [--keep]
                               compile to a native executable
  Swim check <file.sw>         type-check / compile without producing output
  Swim emit <file.sw>          print the generated C source
  Swim deps <file.sw>          show resolved module imports and order
  Swim new <name>              create a new program in <name>.sw
  Swim test [options]          run the compiler's test suite (checkout only)
  Swim version                 print the compiler version
  Swim help                    show this help

Options:
  -o, --output <path>   output executable path (build only)
  --keep                write the generated .c file next to the source
  --release             compile with -O3
  --cache-dir <path>    override the build cache directory
  -D <name>, --define <name>
                        define a flag for #if conditional compilation
  --mm <mode>           memory management: atomicArc (Swift-style atomically
                        refcounted ARC; the only mode of the C backend)
  --cc-arg <flag>       extra flag for the C compiler (repeatable)

Memory management: Swift-style atomic ARC, implemented by runtime/swimrt.c.
License: MIT.
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
            "defines": [], "mm": DEFAULT_MEMORY_MANAGEMENT, "cc_args": []}
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
        if arg == "--cc-arg" and i + 1 < len(rest):
            opts["cc_args"].append(rest[i + 1])
            i += 2
            continue
        if arg.startswith("--cc-arg="):
            opts["cc_args"].append(arg.split("=", 1)[1])
            i += 1
            continue
        if arg.startswith("--cc-arg:"):
            opts["cc_args"].append(arg[len("--cc-arg:"):])
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
        cc_args = list(opts["cc_args"])
        if opts["release"]:
            cc_args.append("-O3")
        result = _compile_with_diagnostics(
            path, keep=opts["keep"], defines=opts["defines"],
            mm=opts["mm"], cc_args=cc_args or None)
    except BuildFailure as exc:
        print(exc.message, file=sys.stderr)
        print("(set --keep to inspect the generated C source)", file=sys.stderr)
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
        cc_args = list(opts["cc_args"])
        if opts["release"]:
            cc_args.append("-O3")
        result = _compile_with_diagnostics(
            path, keep=opts["keep"], out_path=out,
            defines=opts["defines"], mm=opts["mm"],
            cc_args=cc_args or None)
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
    result = _compile_with_diagnostics(path, emit_only=True,
                                        defines=opts["defines"])
    print(result.source, end="")
    return 0


def cmd_check(args: list[str]) -> int:
    pos, opts = _parse_common(args)
    if not pos:
        print(USAGE, file=sys.stderr)
        return 2
    path = Path(pos[0])
    _load(path)
    cc_args = list(opts["cc_args"])
    try:
        _compile_with_diagnostics(path, defines=opts["defines"], mm=opts["mm"],
                                  cc_args=cc_args or None)
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
        print(f"Swim {__version__} (direct C backend, atomic ARC, MIT)")
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
