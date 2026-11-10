"""Module resolution and multi-file project loading for Swim.

Import scheme
-------------
Swim supports two kinds of ``import`` statements:

1. **Built-in modules** (``Foundation``, ``Swift``, ``Glibc``, ``Darwin``,
   ``Dispatch``, ``Math``, ``Strings``, ``Collections``, ``Random``, ``Time``):
   accepted as a no-op -- the Swim runtime already provides the corresponding
   Swift-style API.  These names exist for source compatibility with Swift.

   **Native modules** are built-in names whose implementation is C source in
   ``runtime/``: ``FerroUI`` (the GUI binding of SwimUI) is the one the direct
   C backend supports.  Importing a native module makes the compiler include
   its header and compile its C shim into the program
   (``runtime/swimferroui.c``), so a C library is exposed to Swim without any
   foreign code in ``.sw`` sources.  The Nim-era modules (``Nimx``, ``Zeta``)
   are retired.

2. **Swim modules**: ``import Foo`` (or ``import Foo.Bar``) resolves to a
   ``.sw`` file:

   - ``Foo.sw`` or ``Foo/main.sw`` next to the importing file,
   - then the same names relative to the entry program's directory,
   - then the current working directory,
   - then each directory listed in the ``SWIM_PATH`` environment variable
     (``:``-separated).

All resolved files are parsed and merged into a single program.  Imported
modules are compiled together with the entry file: their top level statements
run first (dependencies before dependents, each module at most once), then the
entry file.  Declarations share one flat namespace; redeclaring a type, global
variable or type alias in two different files is a compile error (function
overloads are allowed).

No Nim source is ever imported: Swim sources may only use Swift syntax, and
the only native dependency is the bundled ``swimrt`` runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import ast_nodes as A
from .errors import SwimError
from .parser import parse_source


# Modules provided by the runtime; importing them is a no-op.
BUILTIN_MODULES = {
    "Swift",
    "Foundation",
    "Glibc",
    "Darwin",
    "Dispatch",
    "ObjectiveC",
    "Math",
    "Strings",
    "Collections",
    "Random",
    "Time",
}

# "Native" modules: built-in module names whose implementation is C source in
# runtime/ plus, for FerroUI, a shared library built from ffi/.  Importing one
# makes the generated C include the module's header, call its C shim and link
# its library; the Swift-facing functions are declared in
# `swimc/native_ferroui.py`.  See docs/internals.md "Add a native module".
NATIVE_MODULES = {
    "FerroUI": {"shim": "swimferroui", "library": "ferroui_swim"},
}

# Native modules of the retired Nim backend.  Importing one is a compile error
# that explains what happened.
RETIRED_NATIVE_MODULES = {"Nimx", "Zeta"}

def native_module_names() -> set[str]:
    """The names of the native modules the compiler can bind."""
    return set(NATIVE_MODULES)


MODULE_HELP = (
    "imports resolve to '<Name>.sw' or '<Name>/main.sw'; search order is the "
    "importing file's directory, the entry file's directory, the current "
    "directory and SWIM_PATH"
)


@dataclass
class SourceFile:
    path: Path
    source: str
    module: A.Module | None = None
    line_offset: int = 0  # composed (0 based) line offset of this file


@dataclass
class Project:
    entry: Path
    files: list[SourceFile]  # dependency order, entry last
    module: A.Module
    source: str  # concatenated source, used as a fallback for snippets
    line_owner: list = field(default_factory=list)  # composed line -> (path, local)
    sources: dict = field(default_factory=dict)  # path -> source text
    imports: dict = field(default_factory=dict)  # path -> [(name, target|None, builtin)]
    native_modules: list = field(default_factory=list)  # e.g. ["FerroUI"]

    def path_at_line(self, composed_line: int) -> tuple[Path, int] | None:
        idx = composed_line - 1
        if 0 <= idx < len(self.line_owner):
            return self.line_owner[idx]
        return None

    def owner_path(self, composed_line: int) -> Path | None:
        owner = self.path_at_line(composed_line)
        return owner[0] if owner is not None else None

    def source_for(self, path: Path) -> str:
        return self.sources.get(path, "")

    def normalize_error(self, err: SwimError) -> SwimError:
        """Map a composed-line error back to its original file."""
        if err.line is None:
            return err
        owner = self.path_at_line(err.line)
        if owner is None:
            return err
        path, local_line = owner
        # Only remap errors that came from codegen/merge (composed coordinates).
        if err.filename is None:
            err.filename = str(path)
            err.line = local_line
        return err


class ModuleError(SwimError):
    pass


class _Loader:
    def __init__(self, entry: Path, entry_source: str | None = None) -> None:
        self.entry = entry.resolve()
        self.entry_source = entry_source
        self.roots: list[Path] = []
        self.seen: dict[Path, SourceFile] = {}
        self.order: list[SourceFile] = []
        self.sources: dict[Path, str] = {}
        self.import_map: dict[Path, list] = {}
        for root in (self.entry.parent, Path.cwd()):
            if root not in self.roots:
                self.roots.append(root)
        env = os.environ.get("SWIM_PATH", "")
        for part in env.split(os.pathsep):
            if part:
                resolved = Path(part).expanduser().resolve()
                if resolved not in self.roots:
                    self.roots.append(resolved)

    # ------------------------------------------------------------------ io
    def read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf8")
        except OSError as exc:
            raise SwimError(f"cannot read module '{path}': {exc}",
                            filename=str(path)) from exc

    def resolve_module(self, name: str, importer: Path) -> Path | None:
        rel = Path(*name.split("."))
        with_sw = rel.parent / (rel.name + ".sw")
        with_main = rel / "main.sw"
        candidates: list[Path] = []
        for base in [importer.parent] + self.roots:
            candidates.append(base / with_sw)
            candidates.append(base / with_main)
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return None

    def searched_locations(self, name: str, importer: Path) -> str:
        rel = Path(*name.split("."))
        places = [str(importer.parent)]
        places += [str(r) for r in self.roots if str(r) != str(importer.parent)]
        return ", ".join(dict.fromkeys(places))

    # --------------------------------------------------------------- visit
    def visit(self, path: Path, stack: tuple[Path, ...],
              import_site: A.ImportDecl | None) -> None:
        real = path.resolve()
        if real in self.seen:
            return
        if real in stack:
            # Import cycle: the files are already being loaded; the merged
            # declarations don't depend on order, so simply stop here.
            return
        in_memory_entry = (real == self.entry and
                           self.entry_source is not None)
        if not real.exists() and not in_memory_entry:
            raise SwimError(f"file not found: {path}",
                            filename=str(stack[-1] if stack else path),
                            line=getattr(import_site, "line", None))
        source = (self.entry_source if real == self.entry and
                  self.entry_source is not None else self.read(real))
        if real == self.entry and self.entry_source is not None:
            source = self.entry_source
        mod = parse_source(source, str(real))
        sf = SourceFile(path=real, source=source, module=mod)
        self.seen[real] = sf
        self.sources[real] = source
        entries: list = []
        self.import_map[real] = entries
        for decl in mod.decls:
            if not isinstance(decl, A.ImportDecl):
                continue
            name = decl.path
            target = self.resolve_module(name, real)
            if target is None and name in RETIRED_NATIVE_MODULES:
                raise SwimError(
                    f"native module '{name}' is not supported by the direct C "
                    "backend (native modules were retired together with the "
                    "Nim backend)",
                    filename=str(real), line=decl.line, col=decl.col,
                )
            if target is None and name in NATIVE_MODULES:
                entries.append((name, None, True))
                continue
            if target is None and name in BUILTIN_MODULES:
                entries.append((name, None, True))
                continue
            if target is not None:
                entries.append((name, target.resolve(), False))
            if target is None:
                raise SwimError(
                    f"cannot find module '{name}' (no '{name}.sw' or "
                    f"'{name}/main.sw' in: {self.searched_locations(name, real)})",
                    filename=str(real), line=decl.line, col=decl.col,
                    hint=MODULE_HELP,
                )
            self.visit(target, stack + (real,), decl)
        # only the entry file may declare @main
        for decl in mod.decls:
            if isinstance(decl, A.StructDecl) and "main" in decl.attributes:
                if real != self.entry:
                    raise SwimError("only the entry file may declare '@main'",
                                    filename=str(real), line=decl.line,
                                    col=decl.col)
        self.order.append(sf)

    # --------------------------------------------------------------- merge
    def build(self) -> Project:
        self.visit(self.entry, (), None)
        all_decls: list = []
        all_stmts: list = []
        all_top: list = []
        line_owner: list[tuple[Path, int]] = []
        parts: list[str] = []
        offset = 0
        declared: dict[str, tuple[Path, int]] = {}
        declared_funcs: dict[str, tuple[Path, int]] = {}

        def shift(node) -> None:
            if isinstance(node, A.Node):
                node.line += offset
                for key, value in vars(node).items():
                    if key in ("line", "col"):
                        continue
                    shift(value)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    shift(item)
            elif isinstance(node, dict):
                for value in node.values():
                    shift(value)

        for sf in self.order:
            sf.line_offset = offset
            lines = sf.source.split("\n")
            for local_line, _ in enumerate(lines, start=1):
                line_owner.append((sf.path, local_line))
            parts.append(sf.source)
            assert sf.module is not None
            for item in sf.module.top_items:
                shift(item)
                if isinstance(item, A.ImportDecl):
                    continue
                all_top.append(item)
                if isinstance(item, A.Decl):
                    all_decls.append(item)
                else:
                    all_stmts.append(item)
                name = getattr(item, "name", None)
                local_line = item.line - sf.line_offset
                if (isinstance(item, (A.StructDecl, A.ClassDecl, A.EnumDecl,
                                      A.ProtocolDecl, A.TypeAliasDecl,
                                      A.VarDecl))
                        and name is not None):
                    if name in declared:
                        prev_path, prev_line = declared[name]
                        if prev_path != sf.path:
                            raise SwimError(
                                f"duplicate top-level declaration '{name}' "
                                f"(also declared in {prev_path.name}:"
                                f"{prev_line})",
                                filename=str(sf.path), line=local_line,
                                col=item.col,
                            )
                    else:
                        declared[name] = (sf.path, local_line)
                elif isinstance(item, A.FuncDecl):
                    key = func_key(item)
                    if key in declared_funcs:
                        prev_path, prev_line = declared_funcs[key]
                        if prev_path != sf.path:
                            raise SwimError(
                                f"duplicate function '{item.name}' with the "
                                f"same signature (also declared in "
                                f"{prev_path.name}:{prev_line})",
                                filename=str(sf.path), line=local_line,
                                col=item.col,
                            )
                    else:
                        declared_funcs[key] = (sf.path, local_line)
            offset += len(lines)

        module = A.Module(decls=all_decls, statements=all_stmts,
                          top_items=all_top,
                          filename=str(self.entry), line=1, col=1)
        native = []
        for entries in self.import_map.values():
            for name, _target, _builtin in entries:
                if name in NATIVE_MODULES and name not in native:
                    native.append(name)
        composed = "\n".join(parts)
        return Project(entry=self.entry, files=self.order, module=module,
                       source=composed, line_owner=line_owner,
                       sources=self.sources, imports=self.import_map,
                       native_modules=native)


def type_key(node) -> str:
    """A textual fingerprint of a type AST used to detect duplicate overloads."""
    if node is None:
        return "Void"
    if isinstance(node, A.NamedType):
        if node.args:
            return node.name + "<" + ",".join(type_key(a) for a in node.args) + ">"
        return node.name
    if isinstance(node, A.OptionalType):
        return type_key(node.inner) + "?"
    if isinstance(node, A.InoutType):
        return "inout " + type_key(node.inner)
    if isinstance(node, A.ArrayType):
        return "[" + type_key(node.elem) + "]"
    if isinstance(node, A.DictType):
        return "[" + type_key(node.key) + ":" + type_key(node.value) + "]"
    if isinstance(node, A.TupleType):
        return "(" + ",".join(
            (label + ":" if label else "") + type_key(ty)
            for label, ty in node.elements) + ")"
    if isinstance(node, A.FuncType):
        return "(" + ",".join(type_key(p) for p in node.params) + ")->" + \
            type_key(node.ret)
    return "?"


def func_key(decl: A.FuncDecl) -> str:
    params = ",".join(type_key(p.ty) for p in decl.params)
    ret = type_key(decl.ret)
    generics = ",".join(name for name, _ in decl.generic_params)
    return f"{decl.name}<{generics}>({params})->{ret}"


def load_project(entry: Path | str, entry_source: str | None = None) -> Project:
    """Parse the entry file and every transitively imported Swim module."""
    path = Path(entry)
    if not path.exists() and entry_source is None:
        raise SwimError(f"file not found: {path}")
    return _Loader(path, entry_source).build()
