"""Swim code generator: turns the Swim AST into Nim source code.

The generator mirrors the structure of the runtime (`swimrt.nim`): the generated
program imports the runtime and then emits type declarations, global variables,
forward declarations, procedure bodies and finally top level statements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import ast_nodes as A
from .errors import SwimError
from .modules import NATIVE_MODULES
from .types import (
    ANY,
    BOOL,
    CHAR,
    FLOAT,
    FLOAT_KINDS,
    INT,
    INT_KINDS,
    NIM_PRIM,
    STRING,
    UNKNOWN,
    VOID,
    ComputedProp,
    EnumCaseInfo,
    FieldInfo,
    FuncInfo,
    Registry,
    SubscriptInfo,
    Ty,
    TypeInfo,
    make_optional,
    substitute,
    ty_to_str,
    unwrap_optional,
)


# ---------------------------------------------------------------------------
# Nim identifier mangling
# ---------------------------------------------------------------------------
NIM_RESERVED = {
    "addr", "and", "as", "asm", "bind", "block", "break", "case", "cast",
    "concept", "const", "continue", "converter", "defer", "discard", "distinct",
    "div", "do", "elif", "else", "end", "enum", "except", "export", "finally",
    "for", "from", "func", "generic", "if", "import", "in", "include",
    "interface", "is", "isnot", "iterator", "let", "macro", "method", "mixin",
    "mod", "nil", "not", "notin", "object", "of", "or", "out", "proc", "ptr",
    "raise", "ref", "return", "shl", "shr", "static", "template", "try",
    "tuple", "type", "using", "var", "when", "while", "xor", "yield",
    "true", "false", "echo", "result", "self", "result",
}

# Names provided by swimrt that user code should not shadow accidentally.
BUILTIN_FREE_NAMES = {
    "print", "debugPrint", "fatalError", "preconditionFailure", "assert",
    "precondition", "readLine", "exit", "abs", "min", "max", "pow", "sqrt",
    "floor", "ceil", "round", "trunc", "sin", "cos", "tan", "asin", "acos",
    "atan", "atan2", "log", "log2", "log10", "exp", "fabs", "swap", "stride",
    "type", "dump", "zip",
}

# Free functions that make up the `Nimx` native module (runtime/swimnimx.nim).
# Signature: Swim name -> (Nim proc, [(argument label, kind)], return kind).
# Kind "closure" expects `() -> Void`; the trailing-closure syntax is allowed
# for it.  Keep this table in sync with runtime/swimnimx.nim.
NIMX_FUNCS = {
    "nimxWindow": ("swimNimxWindow",
                   [("width", "int"), ("height", "int"), ("title", "string"),
                    ("background", "int")], "int"),
    "nimxPanel": ("swimNimxPanel",
                  [("parent", "int"), ("x", "int"), ("y", "int"),
                   ("width", "int"), ("height", "int"), ("color", "int"),
                   ("radius", "int")], "int"),
    "nimxLabel": ("swimNimxLabel",
                  [("parent", "int"), ("x", "int"), ("y", "int"),
                   ("width", "int"), ("height", "int"), ("size", "int"),
                   ("color", "int"), ("align", "int"), ("bold", "bool"),
                   ("text", "string")], "int"),
    "nimxButton": ("swimNimxButton",
                   [("parent", "int"), ("x", "int"), ("y", "int"),
                    ("width", "int"), ("height", "int"), ("fill", "int"),
                    ("titleColor", "int"), ("radius", "int"),
                    ("size", "int"), ("bold", "bool"), ("title", "string"),
                    ("onTap", "closure")], "int"),
    "nimxProgressBar": ("swimNimxProgressBar",
                        [("parent", "int"), ("x", "int"), ("y", "int"),
                         ("width", "int"), ("height", "int"),
                         ("track", "int"), ("fill", "int"), ("radius", "int"),
                         ("percent", "int")], "int"),
    "nimxOnTap": ("swimNimxOnTap",
                  [("handle", "int"), ("onTap", "closure")], "void"),
    "nimxSetText": ("swimNimxSetText",
                    [("handle", "int"), ("text", "string")], "void"),
    "nimxSetColor": ("swimNimxSetColor",
                     [("handle", "int"), ("color", "int")], "void"),
    "nimxSetTextColor": ("swimNimxSetTextColor",
                         [("handle", "int"), ("color", "int")], "void"),
    "nimxSetHidden": ("swimNimxSetHidden",
                      [("handle", "int"), ("hidden", "bool")], "void"),
    "nimxSetProgress": ("swimNimxSetProgress",
                        [("handle", "int"), ("percent", "int")], "void"),
    "nimxAfter": ("swimNimxAfter",
                  [("ms", "int"), ("action", "closure")], "void"),
    "nimxSnapshot": ("swimNimxSnapshot",
                     [("delayMs", "int"), ("path", "string")], "void"),
    "nimxRun": ("swimNimxRun", [], "void"),
    "nimxQuit": ("swimNimxQuit", [], "void"),
}

ZETA_FUNCS = {
    "zetaNewSession": ("zetaNewSession", [], "int"),
    "zetaEval": ("zetaEval",
                 [("session", "int"), ("code", "string")], "bool"),
    "zetaOutput": ("zetaOutput", [("session", "int")], "string"),
    "zetaError": ("zetaError", [("session", "int")], "string"),
    "zetaPlotJson": ("zetaPlotJson", [("session", "int")], "string"),
    "zetaVarCount": ("zetaVarCount", [("session", "int")], "int"),
    "zetaVarName": ("zetaVarName",
                    [("session", "int"), ("index", "int")], "string"),
    "zetaVarSize": ("zetaVarSize",
                    [("session", "int"), ("index", "int")], "string"),
    "zetaVarClass": ("zetaVarClass",
                     [("session", "int"), ("index", "int")], "string"),
    "zetaVarValue": ("zetaVarValue",
                     [("session", "int"), ("index", "int")], "string"),
    "zetaReset": ("zetaReset", [("session", "int")], "void"),
    "zetaFreeSession": ("zetaFreeSession", [("session", "int")], "void"),
    "zetaWindow": ("zetaWindow",
                   [("width", "int"), ("height", "int"), ("title", "string"),
                    ("background", "int")], "int"),
    "zetaTextField": ("zetaTextField",
                      [("parent", "int"), ("x", "int"), ("y", "int"),
                       ("width", "int"), ("height", "int"), ("size", "int"),
                       ("background", "int"), ("textColor", "int"),
                       ("text", "string")], "int"),
    "zetaTextFieldText": ("zetaTextFieldText",
                          [("handle", "int")], "string"),
    "zetaTextArea": ("zetaTextArea",
                     [("parent", "int"), ("x", "int"), ("y", "int"),
                      ("width", "int"), ("height", "int"), ("size", "int"),
                      ("background", "int"), ("textColor", "int"),
                      ("text", "string")], "int"),
    "zetaSetTextFieldEditable": ("zetaSetTextFieldEditable",
                                 [("handle", "int"),
                                  ("editable", "bool")], "void"),
    "zetaSetTextFieldText": ("zetaSetTextFieldText",
                             [("handle", "int"), ("text", "string")], "void"),
    "zetaTextFieldOnSubmit": ("zetaTextFieldOnSubmit",
                              [("handle", "int"),
                               ("action", "closure")], "void"),
    "zetaPlotView": ("zetaPlotView",
                     [("parent", "int"), ("x", "int"), ("y", "int"),
                      ("width", "int"), ("height", "int"),
                      ("background", "int")], "int"),
    "zetaPlotSet": ("zetaPlotSet",
                    [("handle", "int"), ("json", "string")], "void"),
    "zetaPlotClear": ("zetaPlotClear", [("handle", "int")], "void"),
    "zetaSetTextFieldMono": ("zetaSetTextFieldMono",
                             [("handle", "int"), ("size", "int")], "void"),
    "zetaFocusField": ("zetaFocusField", [("handle", "int")], "void"),
    "zetaCwd": ("zetaCwd", [], "string"),
    "zetaWriteFile": ("zetaWriteFile",
                      [("path", "string"), ("text", "string")], "int"),
    "zetaReadFile": ("zetaReadFile", [("path", "string")], "string"),
    "zetaParentDir": ("zetaParentDir", [], "string"),
    "zetaEnterDir": ("zetaEnterDir", [("entry", "string")], "int"),
    "zetaIndexedTileButton": ("zetaIndexedTileButton",
                              [("parent", "int"), ("x", "int"),
                               ("y", "int"), ("width", "int"),
                               ("height", "int"), ("iconKind", "int"),
                               ("listIndex", "int"), ("fill", "int"),
                               ("textColor", "int"), ("iconColor", "int"),
                               ("small", "int"), ("onTap", "closure")],
                              "int"),
    "zetaLastTileIndex": ("zetaLastTileIndex", [], "int"),
    "zetaFolderActivate": ("zetaFolderActivate",
                           [("index", "int")], "int"),
    "zetaOpenedPath": ("zetaOpenedPath", [], "string"),
    "zetaOpenedName": ("zetaOpenedName", [], "string"),
    "zetaTileSetContent": ("zetaTileSetContent",
                           [("handle", "int"), ("iconKind", "int"),
                            ("title", "string")], "void"),
    "zetaListDir": ("zetaListDir", [("path", "string")], "string"),
    "zetaSnapshot": ("zetaSnapshot",
                     [("delayMs", "int"), ("path", "string")], "void"),
    "zetaSnapshotAll": ("zetaSnapshotAll",
                        [("delayMs", "int"), ("mainPath", "string"),
                         ("figurePath", "string")], "void"),
    "zetaEnv": ("zetaEnv", [("name", "string")], "string"),
    "zetaFigureWindow": ("zetaFigureWindow",
                         [("width", "int"), ("height", "int"),
                          ("title", "string"), ("background", "int")],
                         "int"),
    "zetaShowFigureWindow": ("zetaShowFigureWindow", [], "void"),
    "zetaScrollArea": ("zetaScrollArea",
                       [("parent", "int"), ("x", "int"), ("y", "int"),
                        ("width", "int"), ("height", "int"),
                        ("background", "int")], "int"),
    "zetaScrollText": ("zetaScrollText",
                       [("scrollHandle", "int"), ("width", "int"),
                        ("height", "int"), ("size", "int"),
                        ("background", "int"), ("textColor", "int"),
                        ("text", "string")], "int"),
    "zetaScrollToBottom": ("zetaScrollToBottom", [("scrollHandle", "int")],
                           "void"),
    "zetaScrollToTop": ("zetaScrollToTop", [("scrollHandle", "int")], "void"),
    "zetaTileButton": ("zetaTileButton",
                       [("parent", "int"), ("x", "int"), ("y", "int"),
                        ("width", "int"), ("height", "int"),
                        ("iconKind", "int"), ("title", "string"),
                        ("fill", "int"), ("textColor", "int"),
                        ("iconColor", "int"), ("small", "int"),
                        ("onTap", "closure")], "int"),
    "zetaFigureExists": ("zetaFigureExists", [], "int"),
    "zetaRun": ("zetaRun", [], "void"),
}

# Free functions that make up the `FerroUI` native module
# (runtime/swimferroui.nim).  This is the GUI binding of SwimUI: Swift-style
# names over a control library, the way `Nimx` binds the nimx toolkit.  The Nim
# side of the binding calls into the Rust shared library in `ffi/`, which hosts
# FerroUI; a `.sw` source sees only `Int` handles, numbers, strings, booleans
# and `() -> Void` closures.  Signature: Swim name -> (Nim proc,
# [(argument label, kind)], return kind).  Kind "double" is a `Double`; the
# trailing-closure syntax is allowed for a last "closure" parameter.  Keep this
# table in sync with runtime/swimferroui.nim.
FERROUI_FUNCS = {
    "ferrouiRun": ("swimFerroUIRun", [("build", "closure")], "void"),
    "ferrouiQuit": ("swimFerroUIQuit", [], "void"),
    "ferrouiClose": ("swimFerroUIClose", [("window", "int")], "void"),
    "ferrouiWindow": ("swimFerroUIWindow",
                      [("width", "int"), ("height", "int"),
                       ("title", "string"), ("background", "int"),
                       ("onClosed", "closure")], "int"),
    "ferrouiCanvas": ("swimFerroUICanvas", [("parent", "int")], "int"),
    "ferrouiClientWidth": ("swimFerroUIClientWidth", [], "int"),
    "ferrouiClientHeight": ("swimFerroUIClientHeight", [], "int"),
    "ferrouiSetThemeVariant": ("swimFerroUISetThemeVariant",
                               [("name", "string")], "void"),
    "ferrouiSetDecorations": ("swimFerroUISetDecorations",
                              [("handle", "int"), ("mode", "int")], "void"),
    "ferrouiOnReady": ("swimFerroUIOnReady",
                       [("handle", "int"), ("onReady", "closure")], "void"),
    "ferrouiStack": ("swimFerroUIStack",
                     [("parent", "int"), ("vertical", "bool"),
                      ("spacing", "int")], "int"),
    "ferrouiBox": ("swimFerroUIBox",
                   [("parent", "int"), ("x", "int"), ("y", "int"),
                    ("width", "int"), ("height", "int"), ("fill", "int"),
                    ("radius", "int"), ("borderColor", "int"),
                    ("borderWidth", "int")], "int"),
    "ferrouiScrollView": ("swimFerroUIScrollView",
                          [("parent", "int"), ("x", "int"), ("y", "int"),
                           ("width", "int"), ("height", "int"),
                           ("fill", "int"), ("radius", "int")], "int"),
    "ferrouiContent": ("swimFerroUIContent", [("container", "int")], "int"),
    "ferrouiLabel": ("swimFerroUILabel",
                     [("parent", "int"), ("x", "int"), ("y", "int"),
                      ("width", "int"), ("height", "int"),
                      ("text", "string"), ("size", "int"), ("color", "int"),
                      ("align", "int"), ("bold", "bool")], "int"),
    "ferrouiButton": ("swimFerroUIButton",
                      [("parent", "int"), ("x", "int"), ("y", "int"),
                       ("width", "int"), ("height", "int"),
                       ("title", "string"), ("size", "int"),
                       ("bold", "bool"), ("fill", "int"),
                       ("titleColor", "int"), ("radius", "int"),
                       ("onTap", "closure")], "int"),
    "ferrouiTextField": ("swimFerroUITextField",
                         [("parent", "int"), ("x", "int"), ("y", "int"),
                          ("width", "int"), ("height", "int"),
                          ("text", "string"), ("placeholder", "string"),
                          ("size", "int"), ("onChanged", "closure")], "int"),
    "ferrouiCheckBox": ("swimFerroUICheckBox",
                        [("parent", "int"), ("x", "int"), ("y", "int"),
                         ("width", "int"), ("height", "int"),
                         ("text", "string"), ("checked", "bool"),
                         ("onChanged", "closure")], "int"),
    "ferrouiSlider": ("swimFerroUISlider",
                      [("parent", "int"), ("x", "int"), ("y", "int"),
                       ("width", "int"), ("height", "int"),
                       ("minimum", "int"), ("maximum", "int"),
                       ("value", "int"), ("onChanged", "closure")], "int"),
    "ferrouiProgressBar": ("swimFerroUIProgressBar",
                           [("parent", "int"), ("x", "int"), ("y", "int"),
                            ("width", "int"), ("height", "int"),
                            ("percent", "int")], "int"),
    "ferrouiSetFrame": ("swimFerroUISetFrame",
                        [("handle", "int"), ("x", "int"), ("y", "int"),
                         ("width", "int"), ("height", "int")], "void"),
    "ferrouiSetText": ("swimFerroUISetText",
                       [("handle", "int"), ("text", "string")], "void"),
    "ferrouiSetColor": ("swimFerroUISetColor",
                        [("handle", "int"), ("color", "int")], "void"),
    "ferrouiSetTextColor": ("swimFerroUISetTextColor",
                            [("handle", "int"), ("color", "int")], "void"),
    "ferrouiSetBorder": ("swimFerroUISetBorder",
                         [("handle", "int"), ("color", "int"),
                          ("width", "int")], "void"),
    "ferrouiSetHidden": ("swimFerroUISetHidden",
                         [("handle", "int"), ("hidden", "bool")], "void"),
    "ferrouiSetOpacity": ("swimFerroUISetOpacity",
                          [("handle", "int"), ("percent", "int")], "void"),
    "ferrouiSetRadius": ("swimFerroUISetRadius",
                         [("handle", "int"), ("radius", "int")], "void"),
    "ferrouiSetFontSize": ("swimFerroUISetFontSize",
                           [("handle", "int"), ("size", "int")], "void"),
    "ferrouiSetBold": ("swimFerroUISetBold",
                       [("handle", "int"), ("bold", "bool")], "void"),
    "ferrouiSetAlignment": ("swimFerroUISetAlignment",
                            [("handle", "int"), ("align", "int")], "void"),
    "ferrouiSetProgress": ("swimFerroUISetProgress",
                           [("handle", "int"), ("percent", "int")], "void"),
    "ferrouiSetValue": ("swimFerroUISetValue",
                        [("handle", "int"), ("value", "double")], "void"),
    "ferrouiSetChecked": ("swimFerroUISetChecked",
                          [("handle", "int"), ("checked", "bool")], "void"),
    "ferrouiSetSpacing": ("swimFerroUISetSpacing",
                          [("handle", "int"), ("spacing", "int")], "void"),
    "ferrouiGetValue": ("swimFerroUIGetValue", [("handle", "int")], "double"),
    "ferrouiGetText": ("swimFerroUIGetText", [("handle", "int")], "string"),
    "ferrouiGetVisible": ("swimFerroUIGetVisible", [("handle", "int")],
                          "bool"),
    "ferrouiGetChecked": ("swimFerroUIGetChecked", [("handle", "int")],
                          "bool"),
    "ferrouiOnTap": ("swimFerroUIOnTap",
                     [("handle", "int"), ("onTap", "closure")], "void"),
    "ferrouiOnTextChanged": ("swimFerroUIOnTextChanged",
                             [("handle", "int"),
                              ("onChanged", "closure")], "void"),
    "ferrouiOnCheckedChanged": ("swimFerroUIOnCheckedChanged",
                                [("handle", "int"),
                                 ("onChanged", "closure")], "void"),
    "ferrouiOnValueChanged": ("swimFerroUIOnValueChanged",
                              [("handle", "int"),
                               ("onChanged", "closure")], "void"),
    "ferrouiAfter": ("swimFerroUIAfter",
                     [("ms", "int"), ("action", "closure")], "void"),
    "ferrouiRaiseClick": ("swimFerroUIRaiseClick", [("handle", "int")], "void"),
    "ferrouiSnapshot": ("swimFerroUISnapshot",
                        [("delayMs", "int"), ("path", "string")], "void"),
    "ferrouiVersion": ("swimFerroUIVersion", [], "string"),
    "ferrouiImagePath": ("swimFerroUIImagePath", [], "string"),
    "ferrouiAutoQuitMs": ("swimFerroUIAutoQuitMs", [], "int"),
    "ferrouiBridgePath": ("swimFerroUIBridgePath", [], "string"),
    "ferrouiLog": ("swimFerroUILog", [("message", "string")], "void"),
    "ferrouiRelease": ("swimFerroUIRelease", [("handle", "int")], "void"),
}

NIMX_KINDS = {"int": INT, "string": STRING, "bool": BOOL}
FERROUI_KINDS = {"int": INT, "string": STRING, "bool": BOOL,
                 "double": FLOAT}
# The Swift types the native modules may return.
NATIVE_RESULT_TYPES = {"int": INT, "string": STRING, "bool": BOOL,
                       "double": FLOAT, "void": VOID}


RUNTIME_NAMES = {
    "swimStr", "swimPrint", "swimPrintNoNewline", "swimFatal", "swimAssert",
    "swimPreconditionFailure", "swimReadLine", "swimExit", "swimRandomInt",
    "swimRandomDouble", "swimOptFlatMap", "swimOptMap", "swimUnwrap",
    "swimToInt", "swimToInt64", "swimToDouble", "swimSortedByImpl",
    "swimSortedByIt", "swimMapIt", "swimFilterIt", "swimAllIt", "swimAnyIt",
    "swimStride", "swimStrideTo", "swimInRange", "swimInSet",
    "swimRemoveAllIt", "swimMergeSort", "swimAsOpt",
}

CONCEPT_MAP = {
    "Equatable": "Equatable",
    "Comparable": "Comparable",
    "Hashable": "Hashable",
    "CustomStringConvertible": "CustomStringConvertible",
    "CaseIterable": "CaseIterable",
    "Error": "CatchableError",
    "AnyObject": "RootObj",
    "AdditiveArithmetic": "AdditiveArithmetic",
    "Numeric": "Numeric",
    "SignedNumeric": "SignedNumeric",
    "BinaryInteger": "SomeNumber",
    "FloatingPoint": "SomeFloat",
    "StringProtocol": "string",
}

ASSIGN_OPS = {
    "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
}


def nim_ident(name: str) -> str:
    """Mangle a Swim identifier into a safe Nim identifier."""
    if name == "_":
        return "_"
    if name in NIM_RESERVED or name in RUNTIME_NAMES:
        return "sw_" + name
    if name.startswith("__"):
        return "sw" + name
    return name


def mangle_type_name(name: str) -> str:
    return nim_ident(name)


# ---------------------------------------------------------------------------
# Procedure job descriptors
# ---------------------------------------------------------------------------
@dataclass
class JobParam:
    name: str
    ty: Ty
    default: Any = None
    is_var: bool = False
    label: str | None = None
    orig_name: str | None = None
    is_variadic: bool = False


@dataclass
class ProcJob:
    kind: str = "func"
    name: str = ""
    params: list = field(default_factory=list)
    ret: Ty = VOID
    generics: list = field(default_factory=list)
    pragmas: str = ""
    body: list | None = None
    special: Callable[["CodeGen", "ProcJob"], None] | None = None
    custom: Callable[["CodeGen", "ProcJob"], None] | None = None
    owner: TypeInfo | None = None
    self_ty: Ty | None = None
    desc: str = ""
    raw_signature: str | None = None
    src_line: int = 0
    is_main: bool = False
    is_local: bool = False
    # for methods: the underlying implementation proc (class dynamic dispatch)
    impl_name: str | None = None


class VarSym:
    __slots__ = ("name", "nim", "ty", "mutable", "kind")

    def __init__(self, name: str, nim: str, ty: Ty, mutable: bool,
                 kind: str = "local") -> None:
        self.name = name
        self.nim = nim
        self.ty = ty
        self.mutable = mutable
        self.kind = kind

    def __repr__(self) -> str:  # pragma: no cover
        return f"VarSym({self.name}->{self.nim}: {ty_to_str(self.ty)})"


class Scope:
    __slots__ = ("vars", "kind")

    def __init__(self, kind: str = "block") -> None:
        self.vars: dict[str, VarSym] = {}
        self.kind = kind


class CodeGen:
    def __init__(self, module: A.Module, registry: Registry,
                 filename: str = "<input>",
                 native_modules: list | None = None) -> None:
        self.module = module
        self.reg = registry
        self.filename = filename
        self.native_modules = set(native_modules or ())

        self.out: list[str] = []
        self.indent_level = 0
        self.line_map: dict[int, int] = {}
        self.current_src_line = 0

        self.scopes: list[Scope] = []
        self.self_ty: Ty | None = None
        self.type_info: TypeInfo | None = None
        self.self_nim = "self"
        self.ret_ty: Ty = VOID
        self.current_func: FuncInfo | None = None
        self.current_proc_name: str = ""
        self.in_init = False
        self.in_failable_init = False
        self.generic_env: dict[str, Ty] = {}
        self.generic_constraints: dict[str, list] = {}
        self.static_owner: TypeInfo | None = None
        self.return_collector: list | None = None
        self.breakables: list[dict] = []
        self.switch_labels: list[str] = []
        self.continue_labels: dict[str, str] = {}

        self.temp_counter = 0
        self.switch_counter = 0

        self.jobs: list[ProcJob] = []
        self.impl_names: dict[int, str] = {}  # id(FuncInfo) -> impl proc name
        self.main_job: ProcJob | None = None
        self.static_var_nims: dict[tuple[str, str], str] = {}
        self.global_syms: dict[str, VarSym] = {}
        self.global_let_names: set[str] = set()
        self.used_builtin_helpers: set[str] = set()

        # generated helper declarations discovered lazily
        self.extra_decls: list[str] = []
        self.needs_as_opt = False
        self.local_func_decls: dict[str, A.FuncDecl] = {}
        self._forwarded_local: set = set()
        self._last_generic_map: dict[str, Ty] = {}

    # =================================================================== errors
    def error(self, msg: str, node: Any = None, hint: str | None = None):
        raise SwimError(
            msg,
            filename=self.filename,
            line=getattr(node, "line", None) or self.current_src_line or None,
            col=getattr(node, "col", None) or None,
            hint=hint,
        )

    def not_supported(self, what: str, node: Any = None):
        self.error(f"{what} is not supported by Swim yet", node)

    # ================================================================ emission
    def line(self, text: str = "") -> None:
        prefix = "  " * self.indent_level
        for raw in text.split("\n"):
            self.out.append((prefix + raw) if raw else "")
        self.line_map[len(self.out) - 1] = self.current_src_line

    def code(self, text: str) -> None:
        """Emit a (possibly multi line) code block at the current indentation."""
        prefix = "  " * self.indent_level
        lines = text.split("\n")
        for i, raw in enumerate(lines):
            self.out.append(prefix + raw if raw else "")
            self.line_map[len(self.out) - 1] = (
                self.current_src_line if i == 0 else self.current_src_line
            )

    def indent(self):
        self.indent_level += 1

    def dedent(self):
        self.indent_level -= 1

    def temp(self, hint: str = "t") -> str:
        self.temp_counter += 1
        return f"sw{hint.capitalize()}{self.temp_counter}"

    # ================================================================== scopes
    def push_scope(self, kind: str = "block") -> Scope:
        scope = Scope(kind)
        self.scopes.append(scope)
        return scope

    def pop_scope(self) -> None:
        self.scopes.pop()

    def declare(self, name: str, nim: str | None = None, ty: Ty = UNKNOWN,
                mutable: bool = True, kind: str = "local") -> VarSym:
        sym = VarSym(name, nim or nim_ident(name), ty, mutable, kind)
        self.scopes[-1].vars[name] = sym
        return sym

    def lookup(self, name: str) -> VarSym | None:
        for scope in reversed(self.scopes):
            sym = scope.vars.get(name)
            if sym is not None:
                return sym
        return None

    def lookup_global(self, name: str) -> VarSym | None:
        for sym in getattr(self, "global_syms", {}).values():
            if sym.name == name:
                return sym
        return None

    def var_ty(self, name: str) -> Ty | None:
        sym = self.lookup(name)
        if sym is not None:
            return sym.ty
        if name in self.static_var_nims:
            return None
        return None

    # ============================================================ type helpers
    def nim_type(self, ty: Ty, node: Any = None) -> str:
        if ty is None or ty.kind == "unknown":
            self.error("cannot infer type here; add an explicit type annotation",
                       node)
        k = ty.kind
        if k in NIM_PRIM:
            return NIM_PRIM[k]
        if k == "any":
            return "RootObj"
        if k == "array":
            return f"seq[{self.nim_type(ty.elem, node)}]"
        if k == "dict":
            return f"Table[{self.nim_type(ty.key, node)}, {self.nim_type(ty.value, node)}]"
        if k == "set":
            return f"HashSet[{self.nim_type(ty.elem, node)}]"
        if k == "optional":
            return f"Option[{self.nim_type(ty.inner, node)}]"
        if k == "tuple":
            if ty.labels and any(ty.labels):
                parts = []
                for i, t in enumerate(ty.args):
                    label = ty.labels[i] if i < len(ty.labels) and ty.labels[i] else f"f{i}"
                    parts.append(f"{nim_ident(label)}: {self.nim_type(t, node)}")
                return "tuple[" + ", ".join(parts) + "]"
            return "(" + ", ".join(self.nim_type(t, node) for t in ty.args) + ")"
        if k == "func":
            params = ", ".join(
                f"a{i}: {self.nim_type(p, node)}"
                for i, p in enumerate(ty.params)
            )
            if ty.ret.is_void:
                return f"proc ({params})"
            return f"proc ({params}): {self.nim_type(ty.ret, node)}"
        if k == "range":
            return f"Slice[{self.nim_type(ty.elem, node)}]"
        if k == "named":
            info = self.reg.type_info(ty)
            if info is not None:
                name = info.nim_name
            else:
                name = mangle_type_name(ty.name)
            if ty.args:
                return name + "[" + ", ".join(self.nim_type(a, node) for a in ty.args) + "]"
            return name
        if k == "generic":
            return nim_ident(ty.name)
        self.error(f"cannot translate type '{ty_to_str(ty)}' to Nim", node)
        raise AssertionError

    def nim_ret(self, ty: Ty, node: Any = None) -> str:
        if ty.is_void:
            return ""
        return ": " + self.nim_type(ty, node)

    def concept_nim(self, name: str) -> str | None:
        if name in CONCEPT_MAP:
            return CONCEPT_MAP[name]
        info = self.reg.types.get(name)
        if info is not None and info.kind == "protocol":
            return info.nim_name
        return None

    def generics_clause(self, generics: list, node: Any = None) -> str:
        parts: list[str] = []
        for name, constraints in generics:
            cons_parts = []
            for c in constraints:
                cn = self.concept_nim(c)
                if cn is not None:
                    cons_parts.append(cn)
                else:
                    self.error(f"unknown protocol constraint '{c}'; Swim "
                               "supports user protocols and Equatable, "
                               "Comparable, Hashable, "
                               "CustomStringConvertible, CaseIterable, Error")
            if cons_parts:
                parts.append(f"{nim_ident(name)}: {'|'.join(cons_parts)}")
            else:
                parts.append(nim_ident(name))
        return "[" + ", ".join(parts) + "]" if parts else ""

    # =========================================================== build jobs
    def build_jobs(self) -> None:
        jobs: list[ProcJob] = []

        # free functions (source order)
        for decl in self.module.decls:
            if isinstance(decl, A.FuncDecl):
                fi = None
                for cand in self.reg.global_funcs.get(decl.name, []):
                    if cand.decl is decl:
                        fi = cand
                        break
                if fi is None:
                    continue
                jobs.append(self.make_func_job(fi))

        # type members
        for info in self.reg.types.values():
            if info.kind == "protocol":
                continue
            self.add_type_jobs(info, jobs)

        # extensions
        for key, ext in self.reg.extensions.items():
            self.add_extension_jobs(key, ext, jobs)

        # @main
        if self.reg.main_type is not None:
            info = self.reg.types[self.reg.main_type]
            main_fis = info.static_funcs.get("main", [])
            if main_fis:
                want = self.static_proc_name(info, "main")
                for job in jobs:
                    if job.name == want:
                        job.is_main = True
                        self.main_job = job
                        break

        self.jobs = jobs

    def static_proc_name(self, info: TypeInfo, name: str) -> str:
        return f"{info.nim_name}_{nim_ident(name)}"

    def make_func_job(self, fi: FuncInfo) -> ProcJob:
        display_name = f"`{fi.name}`" if fi.is_operator else nim_ident(fi.name)
        params = []
        for i, p in enumerate(fi.params):
            ty = fi.param_types[i] if i < len(fi.param_types) else UNKNOWN
            is_var = isinstance(p.ty, A.InoutType)
            params.append(JobParam(name=nim_ident(p.name), ty=ty,
                                   default=p.default, is_var=is_var,
                                   label=p.label, orig_name=p.name,
                                   is_variadic=getattr(p, "is_variadic", False)))
        ret = fi.ret
        if isinstance(fi.decl, A.FuncDecl) and fi.decl.ret is None:
            # functions without a return type: infer Void
            ret = VOID
        job = ProcJob(kind="func", name=display_name, params=params,
                      ret=ret, generics=list(fi.generics), body=fi.body or [],
                      src_line=fi.line, desc=fi.name)
        return job

    def _type_generics(self, info: TypeInfo) -> list:
        return [(name, list(cons)) for name, cons in info.generic_params]

    def _combine_generics(self, info: TypeInfo, fi: FuncInfo | None) -> list:
        gens = self._type_generics(info)
        if fi is not None:
            gens = gens + [(n, list(c)) for n, c in fi.generics]
        return gens

    def method_impl_name(self, info: TypeInfo, name: str, idx: int,
                         overloads: int) -> str:
        base = f"{nim_ident(name)}_{info.nim_name}"
        if overloads > 1:
            return f"{base}_{idx}"
        return base

    def add_type_jobs(self, info: TypeInfo, jobs: list) -> None:
        impl_counter: dict[str, int] = {}
        # instance methods
        for name, fis in info.methods.items():
            for idx, fi in enumerate(fis):
                if fi.is_static:
                    job = self.make_static_job(info, fi)
                    jobs.append(job)
                    continue
                params = [JobParam(name="self", ty=self.self_type(info),
                                   is_var=(info.kind == "struct" and fi.is_mutating) or
                                          (info.kind == "enum" and fi.is_mutating),
                                   label=None)]
                for i, p in enumerate(fi.params):
                    ty = fi.param_types[i] if i < len(fi.param_types) else UNKNOWN
                    params.append(JobParam(name=nim_ident(p.name), ty=ty,
                                           default=p.default,
                                           is_var=isinstance(p.ty, A.InoutType),
                                           label=p.label, orig_name=p.name,
                                           is_variadic=getattr(p, "is_variadic",
                                                               False)))
                generics = self._combine_generics(info, fi)
                if info.kind == "class":
                    impl = self.method_impl_name(info, name, idx, len(fis))
                    self.impl_names[id(fi)] = impl
                    impl_job = ProcJob(
                        kind="method_impl", name=impl, params=params,
                        ret=fi.ret, generics=generics, body=fi.body or [],
                        owner=info, self_ty=self.self_type(info),
                        desc=name, src_line=fi.line,
                    )
                    jobs.append(impl_job)
                    base = not self._has_super_method(info, name)
                    wrapper = ProcJob(
                        kind="method_wrapper", name=nim_ident(name),
                        params=params, ret=fi.ret, generics=generics,
                        owner=info, self_ty=self.self_type(info),
                        desc=name, src_line=fi.line,
                        impl_name=impl,
                    )
                    if base:
                        wrapper.pragmas = " {.base.}"
                    jobs.append(wrapper)
                else:
                    job = ProcJob(kind="method", name=nim_ident(name),
                                  params=params, ret=fi.ret, generics=generics,
                                  body=fi.body or [], owner=info,
                                  self_ty=self.self_type(info), desc=name,
                                  src_line=fi.line)
                    jobs.append(job)
        # static methods
        for name, fis in info.static_funcs.items():
            for fi in fis:
                jobs.append(self.make_static_job(info, fi))
        # initializers / constructors
        if info.kind != "enum":
            self.add_init_jobs(info, jobs)
        # computed properties
        for name, cp in info.computed.items():
            self.add_computed_jobs(info, cp, jobs)
        # static computed properties (``static var x: T { get { ... } }``)
        for name, sv in info.static_vars.items():
            if isinstance(sv, ComputedProp):
                self.add_computed_jobs(info, sv, jobs)
        # observed stored properties (willSet / didSet)
        for f in info.fields:
            if f.observers:
                self.add_observed_jobs(info, f, jobs)
        # subscripts
        self.add_subscript_jobs(info, info.subscripts, jobs)
        # static vars are handled as globals
        # enum helpers
        if info.kind == "enum":
            self.add_enum_jobs(info, jobs)
        # synthesized protocol conformances
        self.add_conformance_jobs(info, jobs)

    def self_type(self, info: TypeInfo) -> Ty:
        if info.is_generic:
            return Ty.named(info.name, tuple(Ty.generic(n) for n, _ in info.generic_params))
        return Ty.named(info.name)

    def _has_super_method(self, info: TypeInfo, name: str) -> bool:
        cur = info.superclass
        while cur is not None:
            if name in cur.methods:
                return True
            cur = cur.superclass
        return False

    def make_static_job(self, info: TypeInfo, fi: FuncInfo) -> ProcJob:
        params = []
        for i, p in enumerate(fi.params):
            ty = fi.param_types[i] if i < len(fi.param_types) else UNKNOWN
            params.append(JobParam(name=nim_ident(p.name), ty=ty,
                                   default=p.default,
                                   is_var=isinstance(p.ty, A.InoutType),
                                   label=p.label, orig_name=p.name))
        name = (f"`{fi.name}`" if fi.is_operator
                else self.static_proc_name(info, fi.name))
        return ProcJob(kind="static", name=name,
                       params=params, ret=fi.ret,
                       generics=self._combine_generics(info, fi),
                       body=fi.body or [], owner=info, src_line=fi.line,
                       desc=fi.name)

    def add_init_jobs(self, info: TypeInfo, jobs: list) -> None:
        tname = info.nim_name
        if info.inits:
            for i, fi in enumerate(info.inits):
                suffix = "" if len(info.inits) == 1 else f"_{i + 1}"
                init_name = f"init{tname}{suffix}"
                new_name = f"new{tname}{suffix}"
                params = [JobParam(name="self", ty=self.self_type(info),
                                   is_var=(info.kind == "struct"))]
                for j, p in enumerate(fi.params):
                    ty = fi.param_types[j] if j < len(fi.param_types) else UNKNOWN
                    params.append(JobParam(name=nim_ident(p.name), ty=ty,
                                           default=p.default,
                                           is_var=isinstance(p.ty, A.InoutType),
                                           label=p.label, orig_name=p.name,
                                           is_variadic=getattr(p, "is_variadic",
                                                               False)))
                generics = self._type_generics(info)
                init_kind = "failable_init" if fi.failable else "init"
                jobs.append(ProcJob(kind=init_kind, name=init_name,
                                    params=params,
                                    ret=BOOL if fi.failable else VOID,
                                    generics=generics,
                                    body=fi.body or [], owner=info,
                                    self_ty=self.self_type(info),
                                    src_line=fi.line, desc="init"))
                ctor_params = [p for p in params[1:]]
                ctor_ret = self.self_type(info)
                if fi.failable:
                    ctor_ret = Ty.optional(ctor_ret)
                job = ProcJob(kind="ctor", name=new_name, params=ctor_params,
                              ret=ctor_ret, generics=generics,
                              owner=info, src_line=fi.line, desc="init")
                job.special = self._make_ctor_special(
                    info, init_name, is_struct=(info.kind == "struct"),
                    failable=fi.failable)
                jobs.append(job)
        else:
            # synthesize a default / memberwise initializer
            params: list[JobParam] = []
            if info.kind == "struct":
                for f in info.fields:
                    if f.is_static:
                        continue
                    params.append(JobParam(name=nim_ident(f.name),
                                           ty=self._field_ty_for_jobs(info, f),
                                           default=f.default, label=f.name))
            job = ProcJob(kind="ctor", name=f"new{tname}", params=params,
                          ret=self.self_type(info),
                          generics=self._type_generics(info), owner=info,
                          src_line=getattr(info.decl, "line", 0),
                          desc="init")
            job.special = self._make_ctor_special(info, None,
                                                  is_struct=(info.kind == "struct"))
            jobs.append(job)

    def _field_ty_for_jobs(self, info: TypeInfo, f: FieldInfo) -> Ty:
        """Best-effort field type inference available at job-building time."""
        if f.ty.kind == "unknown" and f.default is not None:
            ty = self._infer_expr_type_quiet(f.default)
            if ty is not None and ty.kind != "unknown":
                env = info.generic_env() if info.is_generic else {}
                f.ty = substitute(ty, env) if env else ty
        if f.ty.kind == "unknown":
            self.error(f"cannot infer the type of property '{f.name}'; "
                       "add a type annotation", info.decl)
        return f.ty

    def backing_field_name(self, name: str) -> str:
        return f"swimBk_{nim_ident(name)}"

    def _make_ctor_special(self, info: TypeInfo, init_name: str | None,
                           is_struct: bool, failable: bool = False) -> Callable:
        tname = info.nim_name

        def special(cg: "CodeGen", job: ProcJob) -> None:
            cg.current_src_line = job.src_line
            gpart = (f"[{', '.join(self._type_generic_names(info))}]"
                     if info.is_generic else "")
            if failable:
                if init_name is None:
                    raise AssertionError("failable synthetic initializer")
                if info.kind == "class":
                    cg.line(f"var swTmp: {tname}{gpart}")
                    cg.line("new(swTmp)")
                else:
                    cg.line(f"var swTmp: {tname}{gpart}")
                args = ", ".join(["swTmp"] + [p.name for p in job.params])
                cg.line(f"if {init_name}({args}):")
                cg.indent()
                cg.line("result = some(swTmp)")
                cg.dedent()
                cg.line("else:")
                cg.indent()
                cg.line(f"result = none({tname}{gpart})")
                cg.dedent()
                return
            if info.kind == "class":
                cg.line("new(result)")
            else:
                cg.line(f"var swTmp: {tname}{gpart}")
            if init_name is not None:
                args = ", ".join(["result" if info.kind == "class" else "swTmp"] +
                                 [p.name for p in job.params])
                cg.line(f"{init_name}({args})")
            else:
                by_nim = {nim_ident(f.name): f for f in info.fields
                          if not f.is_static}
                for p in job.params:
                    target = "result" if info.kind == "class" else "swTmp"
                    fld = by_nim.get(p.name)
                    fname = p.name
                    if fld is not None and fld.observers:
                        fname = self.backing_field_name(fld.name)
                    cg.line(f"{target}.{fname} = {p.name}")
                for f in info.fields:
                    if f.is_static or f.default is None:
                        continue
                    if any(p.name == nim_ident(f.name) for p in job.params):
                        continue
                    code, _ = cg.gen_expr(f.default, f.ty)
                    target = "result" if info.kind == "class" else "swTmp"
                    fname = (self.backing_field_name(f.name) if f.observers
                             else nim_ident(f.name))
                    cg.line(f"{target}.{fname} = {code}")
            if is_struct:
                cg.line("result = swTmp")
        return special

    def _type_generic_names(self, info: TypeInfo) -> list[str]:
        return [nim_ident(n) for n, _ in info.generic_params]

    def add_computed_jobs(self, info: TypeInfo, cp: ComputedProp,
                          jobs: list) -> None:
        getter_body: list = []
        setter_body: list = []
        has_setter = False
        for acc in cp.accessors:
            if acc.kind == "get":
                getter_body = acc.body
            elif acc.kind == "set":
                has_setter = True
                setter_body = acc.body
        if cp.is_static:
            if info.is_generic:
                self.error("static computed properties in generic types are "
                           "not supported", cp.decl)
            job = ProcJob(kind="static",
                          name=f"{info.nim_name}_{nim_ident(cp.name)}",
                          params=[], ret=cp.ty, body=getter_body,
                          owner=info,
                          src_line=cp.decl.line if cp.decl else 0,
                          desc=cp.name)
            jobs.append(job)
            if has_setter:
                jobs.append(ProcJob(
                    kind="static",
                    name=f"{info.nim_name}_{nim_ident(cp.name)}_set",
                    params=[JobParam(name="newValue", ty=cp.ty)], ret=VOID,
                    body=setter_body, owner=info,
                    src_line=cp.decl.line if cp.decl else 0, desc=cp.name))
            return
        generics = self._type_generics(info)
        params = [JobParam(name="self", ty=self.self_type(info),
                           is_var=False)]
        jobs.append(ProcJob(kind="computed_get", name=nim_ident(cp.name),
                            params=params, ret=cp.ty, generics=generics,
                            body=getter_body, owner=info,
                            self_ty=self.self_type(info), src_line=cp.decl.line if cp.decl else 0,
                            desc=cp.name))
        if has_setter:
            sparams = [JobParam(name="self", ty=self.self_type(info),
                                is_var=info.kind in ("struct", "enum")),
                       JobParam(name="value", ty=cp.ty)]
            jobs.append(ProcJob(kind="computed_set",
                                name=f"{nim_ident(cp.name)}=", params=sparams,
                                ret=VOID, generics=generics,
                                body=setter_body, owner=info,
                                self_ty=self.self_type(info),
                                src_line=cp.decl.line if cp.decl else 0,
                                desc=cp.name))

    def add_observed_jobs(self, info: TypeInfo, f: FieldInfo,
                          jobs: list) -> None:
        """Generate the getter/setter pair for a willSet/didSet property."""
        ty = self._field_ty_for_jobs(info, f)
        generics = self._type_generics(info)
        self_ty = self.self_type(info)
        getter = ProcJob(kind="computed_get", name=nim_ident(f.name),
                         params=[JobParam(name="self", ty=self_ty)],
                         ret=ty, generics=generics, owner=info,
                         self_ty=self_ty, src_line=f.line, desc=f.name)
        backing = self.backing_field_name(f.name)

        def getter_special(cg: "CodeGen", job: ProcJob) -> None:
            cg.line(f"return self.{backing}")

        getter.special = getter_special
        jobs.append(getter)
        setter = ProcJob(kind="computed_set", name=f"{nim_ident(f.name)}=",
                         params=[JobParam(name="self", ty=self_ty,
                                          is_var=info.kind in ("struct",
                                                               "enum")),
                                 JobParam(name="swNewValue", ty=ty)],
                         ret=VOID, generics=generics, owner=info,
                         self_ty=self_ty, src_line=f.line, desc=f.name)
        setter.custom = self._make_observer_setter(f, ty)
        jobs.append(setter)

    def _make_observer_setter(self, f: FieldInfo, ty: Ty) -> Callable:
        backing = self.backing_field_name(f.name)

        def custom(cg: "CodeGen", job: ProcJob) -> None:
            cg.line(f"let swOldValue = self.{backing}")
            cg.declare("newValue", "swNewValue", ty, mutable=False)
            cg.declare("oldValue", "swOldValue", ty, mutable=False)
            for acc in f.observers:
                if acc.kind == "willSet":
                    if acc.param:
                        cg.declare(acc.param, "swNewValue", ty, mutable=False)
                    cg.gen_block(acc.body, new_scope=True)
            cg.line(f"self.{backing} = swNewValue")
            for acc in f.observers:
                if acc.kind == "didSet":
                    if acc.param:
                        cg.declare(acc.param, "swOldValue", ty, mutable=False)
                    cg.gen_block(acc.body, new_scope=True)

        return custom

    def _add_static_subscript_jobs(self, info: TypeInfo | None,
                                   si, jobs: list) -> None:
        if info is None:
            self.error("static subscripts on primitive types are not supported",
                       si.decl)
        if info.is_generic:
            self.error("static subscripts in generic types are not supported",
                       si.decl)
        counter = self.temp("StaticSub")
        si.nim_get = f"swimStaticSubscriptGet{counter}"
        si.nim_set = f"swimStaticSubscriptSet{counter}"
        getter_body: list = []
        setter_body: list = []
        has_setter = False
        for acc in si.accessors:
            if acc.kind == "get":
                getter_body = acc.body
            elif acc.kind == "set":
                has_setter = True
                setter_body = acc.body
        params: list = []
        for j, p in enumerate(si.params):
            jty = si.param_types[j] if j < len(si.param_types) else UNKNOWN
            params.append(JobParam(name=nim_ident(p.name), ty=jty,
                                   default=p.default, label=p.label,
                                   orig_name=p.name,
                                   is_variadic=getattr(p, "is_variadic",
                                                       False)))
        jobs.append(ProcJob(kind="static", name=si.nim_get, params=params,
                            ret=si.ret, body=getter_body, owner=info,
                            src_line=getattr(si.decl, "line", 0),
                            desc="static subscript"))
        if has_setter:
            sparams = list(params) + [JobParam(name="newValue", ty=si.ret)]
            jobs.append(ProcJob(kind="static", name=si.nim_set,
                                params=sparams, ret=VOID, body=setter_body,
                                owner=info,
                                src_line=getattr(si.decl, "line", 0),
                                desc="static subscript"))

    def add_subscript_jobs(self, info: TypeInfo | None, subscripts: list,
                           jobs: list, *, self_ty: Ty | None = None,
                           generics: list | None = None) -> None:
        for si in subscripts:
            if si.is_static:
                self._add_static_subscript_jobs(info, si, jobs)
                continue
            if self_ty is None:
                if info is None:
                    continue
                self_generic = self.self_type(info)
            else:
                self_generic = self_ty
            gens = generics if generics is not None else (
                self._type_generics(info) if info is not None else [])
            params = [JobParam(name="self", ty=self_generic,
                               is_var=False)]
            for j, p in enumerate(si.params):
                jty = si.param_types[j] if j < len(si.param_types) else UNKNOWN
                params.append(JobParam(name=nim_ident(p.name), ty=jty,
                                       default=p.default, label=p.label,
                                       orig_name=p.name,
                                       is_variadic=getattr(p, "is_variadic",
                                                           False)))
            getter_body: list = []
            has_setter = False
            setter_body: list = []
            for acc in si.accessors:
                if acc.kind == "get":
                    getter_body = acc.body
                elif acc.kind == "set":
                    has_setter = True
                    setter_body = acc.body
            owner = info
            getter = ProcJob(kind="subscript_get", name="`[]`",
                             params=params, ret=si.ret, generics=gens,
                             body=getter_body, owner=owner,
                             self_ty=self_generic,
                             src_line=getattr(si.decl, "line", 0),
                             desc="subscript")
            jobs.append(getter)
            if has_setter:
                self_is_var = not (owner is not None and
                                   owner.kind == "class")
                sparams = [JobParam(name="self", ty=self_generic,
                                    is_var=self_is_var)]
                sparams.extend(params[1:])
                sparams.append(JobParam(name="value", ty=si.ret))
                setter = ProcJob(kind="subscript_set", name="`[]=`",
                                 params=sparams, ret=VOID, generics=gens,
                                 body=setter_body, owner=owner,
                                 self_ty=self_generic,
                                 src_line=getattr(si.decl, "line", 0),
                                 desc="subscript")
                jobs.append(setter)

    def add_enum_jobs(self, info: TypeInfo, jobs: list) -> None:
        generics = self._type_generics(info)
        if info.is_error:
            # error enums are represented as exception types; no jobs needed
            return
        has_payload = any(c.has_assoc for c in info.enum_cases)
        if has_payload:
            for case in info.enum_cases:
                params = [JobParam(name=nim_ident(fname), ty=fty,
                                   label=fname)
                          for fname, fty in case.assoc]
                job = ProcJob(kind="enum_ctor",
                              name=f"{info.nim_name}_{nim_ident(case.name)}",
                              params=params, ret=self.self_type(info),
                              generics=generics, owner=info,
                              src_line=case.decl.line if case.decl else 0,
                              desc=case.name)
                job.special = self._make_enum_ctor_special(info, case)
                jobs.append(job)
        # raw values
        if info.raw_type is not None:
            raw = info.raw_type
            job = ProcJob(kind="raw_value", name="rawValue",
                          params=[JobParam(name="self",
                                           ty=self.self_type(info))],
                          ret=raw, generics=generics, owner=info,
                          src_line=getattr(info.decl, "line", 0))
            job.special = self._make_raw_value_special(info)
            jobs.append(job)
            from_job = ProcJob(kind="from_raw", name="fromRaw", params=[],
                               ret=Ty.optional(self.self_type(info)),
                               generics=generics, owner=info,
                               src_line=getattr(info.decl, "line", 0))
            from_job.raw_signature = (
                f"proc fromRaw*(T: typedesc[{info.nim_name}], raw: "
                f"{self.nim_type(raw)}): Option[{info.nim_name}]"
            )
            from_job.special = self._make_from_raw_special(info)
            jobs.append(from_job)
        if "CaseIterable" in info.conformances:
            case_iter = ProcJob(kind="all_cases", name="allCases", params=[],
                                ret=Ty.array(self.self_type(info)),
                                generics=generics, owner=info)
            case_iter.raw_signature = (
                f"proc allCases*(T: typedesc[{info.nim_name}]): "
                f"seq[{info.nim_name}]"
            )
            case_iter.special = self._make_all_cases_special(info)
            jobs.append(case_iter)

    def _make_enum_ctor_special(self, info: TypeInfo,
                                case: EnumCaseInfo) -> Callable:
        kind_name = f"{info.nim_name}Kind"

        def special(cg: "CodeGen", job: ProcJob) -> None:
            tname = info.nim_name
            gnames = self._type_generic_names(info)
            ret = tname + (f"[{', '.join(gnames)}]" if gnames else "")
            parts = [f"kind: {kind_name}.{nim_ident(case.name)}"]
            for fname, _ in case.assoc:
                parts.append(f"{info.nim_name}_{nim_ident(case.name)}_"
                             f"{nim_ident(fname)}: {nim_ident(fname)}")
            cg.line(f"result = {ret}({', '.join(parts)})")
        return special

    def _make_raw_value_special(self, info: TypeInfo) -> Callable:
        def special(cg: "CodeGen", job: ProcJob) -> None:
            if info.raw_type is not None and info.raw_type.is_int:
                cg.line("result = ord(self)")
            elif info.raw_type is not None and info.raw_type.kind == "string":
                cg.line("case self")
                cg.indent()
                for case in info.enum_cases:
                    raw = case.raw_value
                    lit = cg.gen_expr(raw)[0] if isinstance(raw, A.Expr) else '""'
                    cg.line(f"of {info.nim_name}.{nim_ident(case.name)}: result = {lit}")
                cg.dedent()
            else:
                cg.line("result = ord(self)")
        return special

    def _make_from_raw_special(self, info: TypeInfo) -> Callable:
        def special(cg: "CodeGen", job: ProcJob) -> None:
            raw = info.raw_type
            if raw is not None and raw.is_int:
                cg.line(f"if ord(raw) >= ord(low({info.nim_name})) and "
                        f"ord(raw) <= ord(high({info.nim_name})):")
                cg.indent()
                cg.line(f"result = some({info.nim_name}(raw))")
                cg.dedent()
                cg.line("else:")
                cg.indent()
                cg.line(f"result = none({info.nim_name})")
                cg.dedent()
            else:
                cg.line(f"result = none({info.nim_name})")
                for case in info.enum_cases:
                    lit = case.raw_value
                    if isinstance(lit, str):
                        lit_code = cg.str_literal(lit)
                    elif isinstance(lit, A.Expr):
                        lit_code = cg.gen_expr(lit)[0]
                    else:
                        continue
                    cg.line(f"if raw == {lit_code}: "
                            f"result = some({info.nim_name}.{nim_ident(case.name)})")
        return special

    def _make_all_cases_special(self, info: TypeInfo) -> Callable:
        def special(cg: "CodeGen", job: ProcJob) -> None:
            items = ", ".join(f"{info.nim_name}.{nim_ident(c.name)}"
                              for c in info.enum_cases)
            cg.line(f"result = @[{items}]")
        return special

    def add_conformance_jobs(self, info: TypeInfo, jobs: list) -> None:
        if info.kind == "protocol":
            return
        confs = info.all_conformances()
        if "Error" in confs:
            return
        generics = self._type_generics(info)
        self_ty = self.self_type(info)
        simple_enum = info.kind == "enum" and not any(
            c.has_assoc for c in info.enum_cases)
        if simple_enum:
            return
        # description -> $
        dollar = ProcJob(kind="dollar", name="`$`",
                         params=[JobParam(name="self", ty=self_ty)],
                         ret=STRING, generics=generics, owner=info,
                         src_line=getattr(info.decl, "line", 0))
        dollar.special = self._make_dollar_special(info)
        jobs.append(dollar)
        if "Equatable" in confs:
            eq = ProcJob(kind="equatable", name="`==`",
                         params=[JobParam(name="a", ty=self_ty,
                                          default=None),
                                 JobParam(name="b", ty=self_ty)],
                         ret=BOOL, generics=generics, owner=info)
            eq.special = self._make_equatable_special(info)
            jobs.append(eq)
        if "Hashable" in confs:
            hjob = ProcJob(kind="hash", name="hash",
                           params=[JobParam(name="x", ty=self_ty)],
                           ret=Ty.prim("int"), generics=generics, owner=info)
            hjob.special = self._make_hash_special(info)
            jobs.append(hjob)

    def _make_dollar_special(self, info: TypeInfo) -> Callable:
        def special(cg: "CodeGen", job: ProcJob) -> None:
            # explicit description property wins
            if "description" in info.computed:
                cg.line("result = description(self)")
                return
            if info.kind == "class":
                cg.line(f'result = {cg.str_literal(info.name)}')
                return
            if info.kind == "enum":
                cg.line(f"case self.kind")
                cg.indent()
                for case in info.enum_cases:
                    cg.line(f"of {info.nim_name}Kind.{nim_ident(case.name)}:")
                    cg.indent()
                    if case.assoc:
                        pieces = [cg.str_literal(case.name + "(")]
                        for i, (fname, _) in enumerate(case.assoc):
                            if i > 0:
                                pieces.append(cg.str_literal(", "))
                            pieces.append(cg.str_literal(f"{fname}: "))
                            pieces.append(
                                f"swimStr(self.{info.nim_name}_{nim_ident(case.name)}_"
                                f"{nim_ident(fname)})")
                        pieces.append(cg.str_literal(")"))
                        cg.line("result = " + " & ".join(pieces))
                    else:
                        cg.line(f'result = {cg.str_literal(case.name)}')
                    cg.dedent()
                cg.dedent()
                return
            # struct: Type(field: value, ...)
            if not info.fields:
                cg.line(f'result = {cg.str_literal(info.name + "()")}')
                return
            pieces = [cg.str_literal(f"{info.name}(")]
            for i, f in enumerate(info.fields):
                if i > 0:
                    pieces.append(cg.str_literal(", "))
                pieces.append(cg.str_literal(f"{f.name}: "))
                pieces.append(f"swimStr(self.{nim_ident(f.name)})")
            pieces.append(cg.str_literal(")"))
            cg.line("result = " + " & ".join(pieces))
        return special

    def _make_equatable_special(self, info: TypeInfo) -> Callable:
        def special(cg: "CodeGen", job: ProcJob) -> None:
            if info.kind == "enum" and any(c.has_assoc for c in info.enum_cases):
                cg.line("if a.kind != b.kind: return false")
                cg.line("case a.kind")
                cg.indent()
                for case in info.enum_cases:
                    cg.line(f"of {info.nim_name}Kind.{nim_ident(case.name)}:")
                    cg.indent()
                    checks = []
                    for fname, _ in case.assoc:
                        prefix = f"{info.nim_name}_{nim_ident(case.name)}_{nim_ident(fname)}"
                        checks.append(f"a.{prefix} == b.{prefix}")
                    cg.line("return " + (" and ".join(checks) if checks else "true"))
                    cg.dedent()
                cg.dedent()
                return
            if info.kind == "enum":
                cg.line("result = a == b")
                return
            checks = " and ".join(
                f"a.{nim_ident(f.name)} == b.{nim_ident(f.name)}"
                for f in info.fields
            ) or "true"
            cg.line(f"result = {checks}")
        return special

    def _make_hash_special(self, info: TypeInfo) -> Callable:
        def special(cg: "CodeGen", job: ProcJob) -> None:
            if info.kind == "enum" and any(c.has_assoc for c in info.enum_cases):
                cg.line("result = hash(ord(x.kind))")
                for case in info.enum_cases:
                    for fname, _ in case.assoc:
                        prefix = f"{info.nim_name}_{nim_ident(case.name)}_{nim_ident(fname)}"
                        cg.line(f"if x.kind == {info.nim_name}Kind."
                                f"{nim_ident(case.name)}: result = result !& "
                                f"hash(x.{prefix})")
                cg.line("result = !$result")
                return
            if info.kind == "enum":
                cg.line("result = hash(ord(x))")
                return
            cg.line("result = 0")
            for f in info.fields:
                cg.line(f"result = result !& hash(x.{nim_ident(f.name)})")
            cg.line("result = !$result")
        return special

    def add_extension_jobs(self, key: str, ext, jobs: list) -> None:
        info = self.reg.types.get(key)
        protocol_info: TypeInfo | None = None
        if info is not None:
            self_ty = self.self_type(info)
            generics = self._type_generics(info)
            if info.kind == "protocol":
                protocol_info = info
                generics = [("T", [info.name])] + generics
                self_ty = Ty.generic("T")
        elif key == "String":
            self_ty = STRING
            generics = []
        elif key == "Int":
            self_ty = INT
            generics = []
        elif key == "Double":
            self_ty = FLOAT
            generics = []
        elif key == "Bool":
            self_ty = BOOL
            generics = []
        elif key == "Character":
            self_ty = CHAR
            generics = []
        elif key == "Array":
            self_ty = Ty.array(Ty.generic("T"))
            generics = [("T", [])]
        elif key == "Dictionary":
            self_ty = Ty.dict(Ty.generic("K"), Ty.generic("V"))
            generics = [("K", []), ("V", [])]
        else:
            self_ty = UNKNOWN
            generics = []
        for name, fis in ext.methods.items():
            for fi in fis:
                params = [JobParam(name="self", ty=self_ty,
                                   is_var=(fi.is_mutating and self_ty.kind in
                                           ("named", "string", "array", "dict")))]
                for i, p in enumerate(fi.params):
                    ty = fi.param_types[i] if i < len(fi.param_types) else UNKNOWN
                    params.append(JobParam(name=nim_ident(p.name), ty=ty,
                                           default=p.default,
                                           is_var=isinstance(p.ty, A.InoutType),
                                           label=p.label, orig_name=p.name,
                                           is_variadic=getattr(p, "is_variadic",
                                                               False)))
                job = ProcJob(kind="ext_method", name=nim_ident(name),
                              params=params, ret=fi.ret,
                              generics=generics + [(n, list(c))
                                                   for n, c in fi.generics],
                              body=fi.body or [], owner=protocol_info or info,
                              self_ty=self_ty, src_line=fi.line, desc=name)
                jobs.append(job)
        for name, fis in ext.static_funcs.items():
            for fi in fis:
                params = []
                for i, p in enumerate(fi.params):
                    ty = fi.param_types[i] if i < len(fi.param_types) else UNKNOWN
                    params.append(JobParam(name=nim_ident(p.name), ty=ty,
                                           default=p.default,
                                           is_var=isinstance(p.ty, A.InoutType),
                                           label=p.label, orig_name=p.name,
                                           is_variadic=getattr(p, "is_variadic",
                                                               False)))
                prefix = info.nim_name if info is not None else nim_ident(key)
                jname = (f"`{fi.name}`" if fi.is_operator
                         else f"{prefix}_{nim_ident(name)}")
                job = ProcJob(kind="static", name=jname,
                              params=params, ret=fi.ret,
                              generics=generics + [(n, list(c))
                                                   for n, c in fi.generics],
                              body=fi.body or [], owner=None,
                              src_line=fi.line, desc=name)
                jobs.append(job)
        for name, cp in ext.computed.items():
            getter_body = []
            for acc in cp.accessors:
                if acc.kind == "get":
                    getter_body = acc.body
            params = [JobParam(name="self", ty=self_ty)]
            jobs.append(ProcJob(kind="ext_method", name=nim_ident(name),
                                params=params, ret=cp.ty, generics=generics,
                                body=getter_body, owner=protocol_info or info,
                                self_ty=self_ty,
                                src_line=cp.decl.line if cp.decl else 0,
                                desc=name))
        if ext.subscripts:
            self.add_subscript_jobs(info, ext.subscripts, jobs,
                                    self_ty=self_ty, generics=generics)

    # ============================================================ type section
    def gen_type_section(self) -> None:
        self.current_src_line = 0
        self.line("# " + "=" * 74)
        self.line("# Type declarations")
        self.line("# " + "=" * 74)
        # All declarations live in one Nim ``type`` section so types may refer
        # to each other (including nested types) regardless of source order.
        type_names = {i.name for i in self.reg.types.values()}
        alias_items = [(name, alias) for name, alias in self.reg.aliases.items()
                       if name not in type_names and "." not in name]
        if not self.reg.types and not alias_items:
            self.line("")
            return
        self.line("type")
        self.indent()
        for info in self.reg.types.values():
            self.gen_type_decl(info)
        for name, alias in alias_items:
            self.current_src_line = alias.line
            ty = self.reg.resolve_type(alias.ty)
            generics = ""
            if alias.generic_params:
                generics = self.generics_clause(alias.generic_params)
            self.line(f"{mangle_type_name(name)}*{generics} = "
                      f"{self.nim_type(ty, alias)}")
        self.dedent()
        self.line("")

    def gen_type_decl(self, info: TypeInfo) -> None:
        self.current_src_line = getattr(info.decl, "line", 0)
        generics = self.generics_clause([(n, list(c))
                                          for n, c in info.generic_params])
        if info.kind == "protocol":
            self.gen_concept(info)
            return
        if info.kind == "enum" and info.is_error:
            self.gen_error_types(info)
            return
        if info.kind == "enum" and any(c.has_assoc for c in info.enum_cases):
            self.gen_payload_enum(info, generics)
            return
        if info.kind == "enum":
            self.gen_simple_enum(info, generics)
            return
        if info.kind == "class":
            self.gen_class_decl(info, generics)
            return
        self.gen_struct_decl(info, generics)

    def gen_concept(self, info: TypeInfo) -> None:
        required: list[str] = []
        # include inherited protocol requirements
        chain: list[TypeInfo] = []
        for inherited in getattr(info.decl, "inherits", []) or []:
            if isinstance(inherited, A.NamedType):
                parent = self.reg.types.get(inherited.name)
                if parent is not None and parent.kind == "protocol":
                    chain.append(parent)
        for parent in chain:
            required.extend(self.concept_requirements(parent))
        required.extend(self.concept_requirements(info))
        self.line(f"{info.nim_name}* = concept x")
        self.indent()
        if not required:
            required = ["x == x is bool"]
        for req in required:
            self.line(req)
        self.dedent()
        self.line("")

    def concept_requirements(self, info: TypeInfo) -> list[str]:
        reqs: list[str] = []
        if info.decl is None:
            return reqs
        for member in getattr(info.decl, "members", []):
            if isinstance(member, A.FuncDecl):
                params = []
                for p in member.params:
                    ty = self.reg.resolve_type(p.ty, {})
                    params.append(self.nim_type(ty, member))
                ret = self.reg.resolve_type(member.ret, {}) if member.ret else VOID
                call = f"x.{nim_ident(member.name)}({', '.join(params)})"
                if ret.is_void:
                    reqs.append(call)
                else:
                    reqs.append(f"{call} is {self.nim_type(ret, member)}")
            elif isinstance(member, A.VarDecl):
                ty = self.reg.resolve_type(member.ty, {}) if member.ty else UNKNOWN
                reqs.append(f"x.{nim_ident(member.name)} is "
                            f"{self.nim_type(ty, member)}")
        return reqs

    def gen_error_types(self, info: TypeInfo) -> None:
        base = info.nim_name
        self.line(f"{base}* = object of CatchableError")
        for case in info.enum_cases:
            cname = f"{base}_{nim_ident(case.name)}"
            if case.assoc:
                self.line(f"{cname}* = object of {base}")
                self.indent()
                for fname, fty in case.assoc:
                    self.line(f"{nim_ident(fname)}*: {self.nim_type(fty, info.decl)}")
                self.dedent()
            else:
                self.line(f"{cname}* = object of {base}")
        self.line("")

    def _infer_field_types(self, info: TypeInfo) -> None:
        env = info.generic_env()
        for f in info.fields:
            if f.ty.kind == "unknown" and f.default is not None:
                _, fty = self.gen_expr(f.default, None)
                if fty.kind != "unknown":
                    f.ty = substitute(fty, env) if env else fty
            if f.ty.kind == "unknown":
                self.error(f"cannot infer the type of property '{f.name}'; "
                           "add a type annotation", info.decl)

    def gen_struct_decl(self, info: TypeInfo, generics: str) -> None:
        self._infer_field_types(info)
        self.line(f"{info.nim_name}*{generics} = object")
        if info.fields:
            self.indent()
            for f in info.fields:
                if f.is_static:
                    continue
                name = (self.backing_field_name(f.name) if f.observers
                        else nim_ident(f.name))
                self.line(f"{name}*: {self.nim_type(f.ty, info.decl)}")
            self.dedent()
        else:
            self.indent()
            self.line("discard")
            self.dedent()
        self.line("")

    def gen_class_decl(self, info: TypeInfo, generics: str) -> None:
        self._infer_field_types(info)
        if info.superclass is not None:
            parent = info.superclass.nim_name
            base = f" of {parent}"
            if info.superclass.is_generic:
                base += f"[{', '.join(info.superclass.generic_params[i][0] for i in range(len(info.superclass.generic_params)))}]"
        else:
            base = " of RootObj"
        self.line(f"{info.nim_name}*{generics} = ref object{base}")
        if info.fields:
            self.indent()
            for f in info.fields:
                if f.is_static:
                    continue
                name = (self.backing_field_name(f.name) if f.observers
                        else nim_ident(f.name))
                self.line(f"{name}*: {self.nim_type(f.ty, info.decl)}")
            self.dedent()
        else:
            self.indent()
            self.line("discard")
            self.dedent()
        self.line("")

    def _enum_raw_ordinals(self, info: TypeInfo) -> list[int]:
        values: list[int] = []
        nxt = 0
        for case in info.enum_cases:
            raw = case.raw_value
            if isinstance(raw, A.IntLit):
                try:
                    nxt = int(raw.text.replace("_", ""), 0)
                except ValueError:
                    pass
            elif isinstance(raw, A.UnaryExpr) and raw.op == "-" and \
                    isinstance(raw.operand, A.IntLit):
                try:
                    nxt = -int(raw.operand.text.replace("_", ""), 0)
                except ValueError:
                    pass
            values.append(nxt)
            nxt += 1
        return values

    def gen_simple_enum(self, info: TypeInfo, generics: str) -> None:
        if generics:
            self.not_supported("generic enums without associated values",
                               info.decl)
        self.line(f"{info.nim_name}* {{.pure.}} = enum")
        self.indent()
        is_int_raw = info.raw_type is not None and info.raw_type.is_int
        if is_int_raw:
            ordinals = self._enum_raw_ordinals(info)
            for case, ordinal in zip(info.enum_cases, ordinals):
                self.line(f"{nim_ident(case.name)} = {ordinal}")
        else:
            for case in info.enum_cases:
                self.line(nim_ident(case.name))
        self.dedent()
        self.line("")

    def _recursive_enum(self, info: TypeInfo) -> bool:
        def mentions(ty: Ty) -> bool:
            if ty.kind == "named" and ty.name == info.name:
                return True
            if ty.kind in ("array", "optional", "set", "range"):
                return mentions(ty.elem)
            if ty.kind == "dict":
                return mentions(ty.key) or mentions(ty.value)
            if ty.kind == "tuple":
                return any(mentions(t) for t in ty.args)
            if ty.kind == "func":
                return any(mentions(t) for t in ty.params) or mentions(ty.ret)
            return False

        for case in info.enum_cases:
            for _, fty in case.assoc:
                if mentions(fty):
                    return True
        return False

    def gen_payload_enum(self, info: TypeInfo, generics: str) -> None:
        kind_name = f"{info.nim_name}Kind"
        self.line(f"{kind_name}* {{.pure.}} = enum")
        self.indent()
        for case in info.enum_cases:
            self.line(nim_ident(case.name))
        self.dedent()
        if self._recursive_enum(info):
            self.line(f"{info.nim_name}*{generics} = ref object of RootObj")
        else:
            self.line(f"{info.nim_name}*{generics} = object")
        self.indent()
        self.line(f"case kind*: {kind_name}")
        for case in info.enum_cases:
            self.line(f"of {kind_name}.{nim_ident(case.name)}:")
            self.indent()
            if case.assoc:
                for fname, fty in case.assoc:
                    field = (f"{info.nim_name}_{nim_ident(case.name)}_"
                             f"{nim_ident(fname)}")
                    self.line(f"{field}*: {self.nim_type(fty, info.decl)}")
            else:
                self.line("discard")
            self.dedent()
        self.dedent()
        self.line("")

    # ========================================================== global section
    def gen_global_section(self) -> None:
        self.current_src_line = 0
        self.line("# " + "=" * 74)
        self.line("# Global variables")
        self.line("# " + "=" * 74)
        self.global_syms: dict[str, VarSym] = {}
        for decl in self.module.decls:
            if isinstance(decl, A.VarDecl):
                self.global_syms[decl.name] = VarSym(
                    decl.name, nim_ident(decl.name), UNKNOWN,
                    not decl.is_let, "global")
        # reserve all static variable names first
        for info in self.reg.types.values():
            for name in info.static_vars:
                self.static_var_nim(info, name)
        for decl in self.module.decls:
            if not isinstance(decl, A.VarDecl):
                continue
            ty = self._infer_var_decl_type(decl)
            sym = self.global_syms[decl.name]
            sym.ty = ty
            self.line(f"var {sym.nim}: {self.nim_type(ty, decl)}")
            if decl.is_let:
                self.global_let_names.add(decl.name)
        for info in self.reg.types.values():
            for name, sv in info.static_vars.items():
                if isinstance(sv, ComputedProp):
                    continue
                nim = self.static_var_nim(info, name)
                ty = sv.ty
                if ty.kind == "unknown" and not isinstance(sv, ComputedProp) \
                        and sv.default is not None:
                    _, ty = self.gen_expr(sv.default, None)
                    sv.ty = ty
                self.line(f"var {nim}: {self.nim_type(ty, info.decl)}")
        self.line("")

    def static_var_nim(self, info: TypeInfo, name: str) -> str:
        key = (info.name, name)
        if key not in self.static_var_nims:
            self.static_var_nims[key] = f"{info.nim_name}_{nim_ident(name)}"
        return self.static_var_nims[key]

    def _infer_var_decl_type(self, decl: A.VarDecl) -> Ty:
        if decl.ty is not None:
            return self.reg.resolve_type(decl.ty)
        if decl.init is not None:
            _, ty = self.gen_expr(decl.init, None)
            if ty.kind == "unknown":
                self.error("cannot infer the type of global variable "
                           f"'{decl.name}'; add an explicit type annotation",
                           decl)
            return ty
        self.error(f"global variable '{decl.name}' needs a type or an "
                   "initializer", decl)
        raise AssertionError

    # ======================================================= forward + bodies
    def signature(self, job: ProcJob, with_defaults: bool,
                  with_body: bool) -> str:
        if job.raw_signature is not None:
            sig = job.raw_signature
            if with_body:
                sig += job.pragmas
            return sig
        gen = self.generics_clause(job.generics)
        params = []
        for p in job.params:
            if p.name == "_":
                continue
            prefix = "var " if p.is_var else ""
            piece = f"{p.name}: {prefix}{self.nim_type(p.ty)}"
            if with_defaults and p.default is not None:
                code, _ = self.gen_expr(p.default, p.ty)
                piece += f" = {code}"
            params.append(piece)
        ret = self.nim_ret(job.ret)
        if job.kind == "init":
            ret = ""
        elif job.kind == "failable_init":
            ret = ": bool"
        pragma = job.pragmas
        prefix = "method" if job.kind == "method_wrapper" else "proc"
        if job.name.startswith("`"):
            disp = job.name
        elif job.name.endswith("="):
            disp = f"`{job.name}`"
        else:
            disp = job.name
        export = "" if job.is_local else "*"
        return f"{prefix} {disp}{export}{gen}({', '.join(params)}){ret}{pragma}"

    def emit_forward_decls(self) -> None:
        self.current_src_line = 0
        self.line("# " + "=" * 74)
        self.line("# Forward declarations")
        self.line("# " + "=" * 74)
        for job in self.jobs:
            if job.kind in ("computed_set",):
                self.current_src_line = job.src_line
                sig = self.signature(job, True, False)
                self.line(sig)
                continue
            sig = self.signature(job, True, False)
            if sig.endswith(":"):
                sig = sig[:-1]
            self.line(sig)
        self.line("")
        self.line("# " + "=" * 74)
        self.line("# Procedure definitions")
        self.line("# " + "=" * 74)
        self.line("")

    def emit_proc(self, job: ProcJob) -> None:
        self.current_src_line = job.src_line
        sig = self.signature(job, False, True)
        self.line(sig + " =")
        self.indent()
        if job.kind == "method_wrapper":
            args = ", ".join(["self"] + [p.name for p in job.params[1:]])
            if job.ret.is_void:
                self.line(f"{job.impl_name}({args})")
            else:
                self.line(f"return {job.impl_name}({args})")
        elif job.special is not None:
            job.special(self, job)
        else:
            self.emit_proc_body(job)
        self.dedent()
        self.line("")

    def emit_proc_body(self, job: ProcJob) -> None:
        saved = self._save_ctx()
        self.push_scope("proc")
        self.self_ty = job.self_ty
        self.static_owner = job.owner if job.kind == "static" else None
        if job.kind == "static":
            self.type_info = None
        elif job.owner is not None and job.owner.kind == "protocol" and \
                job.kind != "ext_method":
            self.type_info = None
        else:
            self.type_info = job.owner
        self.self_nim = "self"
        self.ret_ty = job.ret
        self.in_init = job.kind in ("init", "failable_init")
        self.in_failable_init = job.kind == "failable_init"
        self.current_proc_name = job.desc or job.name
        self.generic_env = {}
        self.generic_constraints = {}
        for name, cons in job.generics:
            self.generic_env[name] = Ty.generic(name)
            self.generic_constraints[name] = list(cons)
        for p in job.params:
            self.declare(p.orig_name or p.name, p.name, p.ty, mutable=True,
                         kind="param")
        if job.kind == "computed_set" and job.params:
            self.declare("newValue", "value", job.params[-1].ty,
                         mutable=True, kind="param")
        if job.kind == "subscript_set" and job.params:
            self.declare("newValue", "value", job.params[-1].ty,
                         mutable=True, kind="param")
        body = job.body or []
        self.breakables = []
        self.switch_labels = []
        self.continue_labels = {}
        saved_locals = self.local_func_decls
        saved_forwarded = self._forwarded_local
        self.local_func_decls = {}
        self._forwarded_local = set()
        emitted_before = len(self.out)
        try:
            if job.kind in ("init", "failable_init") and job.owner is not None:
                for f in job.owner.fields:
                    if f.default is None or f.is_static:
                        continue
                    fty = substitute(f.ty, self.generic_env)
                    fcode, fgot = self.gen_expr(f.default, fty)
                    fcode = self.coerce(fcode, fgot, fty, f.default)
                    fname = (self.backing_field_name(f.name) if f.observers
                             else nim_ident(f.name))
                    self.line(f"self.{fname} = {fcode}")
            if job.custom is not None:
                job.custom(self, job)
            elif job.kind not in ("init", "failable_init", "ctor",
                                  "computed_set", "subscript_set") and \
                    len(body) == 1 and isinstance(body[0], A.ExprStmt) and \
                    not job.ret.is_void:
                code, got = self.gen_expr(body[0].expr, job.ret)
                code = self.coerce(code, got, job.ret, body[0].expr)
                self.line(f"return {code}")
            else:
                for stmt in body:
                    if isinstance(stmt, A.FuncDecl):
                        self.local_func_decls[stmt.name] = stmt
                        if id(stmt) not in self._forwarded_local:
                            self._forwarded_local.add(id(stmt))
                            self.emit_local_forward(stmt)
                for stmt in body:
                    self.gen_stmt(stmt)
            if job.kind == "failable_init":
                self.line("return true")
            if len(self.out) == emitted_before:
                self.line("discard")
        finally:
            self.local_func_decls = saved_locals
            self._forwarded_local = saved_forwarded
            self.pop_scope()
            self._restore_ctx(saved)

    def emit_local_forward(self, decl: A.FuncDecl) -> None:
        self.current_src_line = decl.line
        params = []
        for p in decl.params:
            ty = self.reg.resolve_type(p.ty, {})
            if getattr(p, "is_variadic", False):
                ty = Ty.array(ty)
            params.append(f"{nim_ident(p.name)}: "
                          f"{'var ' if isinstance(p.ty, A.InoutType) else ''}"
                          f"{self.nim_type(ty, decl)}")
        ret = self.nim_ret(self.reg.resolve_type(decl.ret, {})) if decl.ret else ""
        gen = self.generics_clause(decl.generic_params)
        self.line(f"proc {nim_ident(decl.name)}{gen}({', '.join(params)}){ret}")

    # ------------------------------------------------------------ ctx save
    def _save_ctx(self):
        return (self.self_ty, self.type_info, self.ret_ty, self.in_init,
                self.in_failable_init, self.current_proc_name,
                dict(self.generic_env), dict(self.generic_constraints),
                self.static_owner, self.return_collector,
                list(self.breakables), list(self.switch_labels),
                dict(self.continue_labels))

    def _restore_ctx(self, saved) -> None:
        (self.self_ty, self.type_info, self.ret_ty, self.in_init,
         self.in_failable_init, self.current_proc_name,
         genv, gcons, self.static_owner, self.return_collector,
         self.breakables, self.switch_labels, self.continue_labels) = saved
        self.generic_env = genv
        self.generic_constraints = gcons

    # ============================================================= statements
    def gen_block(self, stmts: list, new_scope: bool = True) -> None:
        if new_scope:
            self.push_scope()
        if not stmts:
            self.line("discard")
        saved_funcs = dict(self.local_func_decls)
        for stmt in stmts:
            if isinstance(stmt, A.FuncDecl):
                self.local_func_decls[stmt.name] = stmt
                if id(stmt) not in self._forwarded_local:
                    self._forwarded_local.add(id(stmt))
                    self.emit_local_forward(stmt)
        for stmt in stmts:
            self.gen_stmt(stmt)
        self.local_func_decls = saved_funcs
        if new_scope:
            self.pop_scope()

    def gen_stmt(self, stmt: Any) -> None:
        self.current_src_line = getattr(stmt, "line", self.current_src_line)
        if isinstance(stmt, A.VarStmt):
            self.gen_var_stmt(stmt)
        elif isinstance(stmt, A.ExprStmt):
            self.gen_expr_stmt(stmt)
        elif isinstance(stmt, A.IfStmt):
            self.gen_if(stmt)
        elif isinstance(stmt, A.GuardStmt):
            self.gen_guard(stmt)
        elif isinstance(stmt, A.WhileStmt):
            self.gen_while(stmt)
        elif isinstance(stmt, A.RepeatStmt):
            self.gen_repeat(stmt)
        elif isinstance(stmt, A.ForStmt):
            self.gen_for(stmt)
        elif isinstance(stmt, A.SwitchStmt):
            self.gen_switch(stmt, label=None)
        elif isinstance(stmt, A.ReturnStmt):
            self.gen_return(stmt)
        elif isinstance(stmt, A.BreakStmt):
            self.gen_break(stmt)
        elif isinstance(stmt, A.ContinueStmt):
            self.gen_continue(stmt)
        elif isinstance(stmt, A.FallthroughStmt):
            self.error("'fallthrough' is only supported as the last statement "
                       "of a switch case", stmt)
        elif isinstance(stmt, A.ThrowStmt):
            self.gen_throw(stmt)
        elif isinstance(stmt, A.DeferStmt):
            self.line("defer:")
            self.indent()
            self.gen_block(stmt.body)
            self.dedent()
        elif isinstance(stmt, A.DoStmt):
            self.gen_do(stmt)
        elif isinstance(stmt, A.LabeledStmt):
            self.gen_labeled(stmt)
        elif isinstance(stmt, A.FuncDecl):
            self.gen_local_func(stmt)
        elif isinstance(stmt, A.TypeAliasDecl):
            self.line(f"type {mangle_type_name(stmt.name)}* = "
                      f"{self.nim_type(self.reg.resolve_type(stmt.ty), stmt)}")
        else:
            self.error(f"unsupported statement: {type(stmt).__name__}", stmt)

    def gen_var_stmt(self, stmt: A.VarStmt) -> None:
        if stmt.names:
            self.gen_destructure_stmt(stmt)
            return
        if stmt.name == "_":
            code, ty = self.gen_expr(stmt.init, None)
            if ty.is_void:
                self.code(code)
            else:
                self.code(f"discard {code}")
            return
        declared = self.reg.resolve_type(stmt.ty) if stmt.ty is not None else None
        if stmt.init is None:
            if declared is None:
                self.error(f"variable '{stmt.name}' needs a type or an "
                           "initializer", stmt)
            if declared.is_optional:
                code = f"none({self.nim_type(declared.inner, stmt)})"
            else:
                code = f"default({self.nim_type(declared, stmt)})"
            self.line(f"{'let' if stmt.is_let else 'var'} {nim_ident(stmt.name)}"
                      f": {self.nim_type(declared, stmt)} = {code}")
            self.declare(stmt.name, nim_ident(stmt.name), declared,
                         not stmt.is_let)
            return
        code, got = self.gen_expr(stmt.init, declared)
        if declared is None:
            declared = got
            if declared.kind == "unknown":
                self.error(f"cannot infer the type of '{stmt.name}'; add a "
                           "type annotation", stmt)
        code = self.coerce(code, got, declared, stmt.init)
        self.line(f"{'let' if stmt.is_let else 'var'} {nim_ident(stmt.name)}"
                  f": {self.nim_type(declared, stmt)} = {code}")
        self.declare(stmt.name, nim_ident(stmt.name), declared, not stmt.is_let)

    def gen_destructure_stmt(self, stmt: A.VarStmt) -> None:
        declared = self.reg.resolve_type(stmt.ty) if stmt.ty is not None else None
        code, got = self.gen_expr(stmt.init, declared)
        elem_types: list[Ty] = []
        if declared is not None and declared.kind == "tuple":
            elem_types = list(declared.args)
        elif got.kind == "tuple":
            elem_types = list(got.args)
        if len(elem_types) != len(stmt.names):
            elem_types = [UNKNOWN] * len(stmt.names)
        names = ", ".join(nim_ident(n) if n != "_" else "_"
                          for n in stmt.names)
        self.line(f"{'let' if stmt.is_let else 'var'} ({names}) = {code}")
        for i, n in enumerate(stmt.names):
            if n == "_":
                continue
            self.declare(n, nim_ident(n), elem_types[i],
                         mutable=not stmt.is_let)

    def gen_local_func(self, decl: A.FuncDecl) -> None:
        # find the matching FuncInfo from the registry if it exists; nested
        # functions are re-parsed directly from the AST.
        fi = self._find_local_func(decl)
        if fi is not None:
            job = self.make_func_job(fi)
            self.emit_proc(job)
            return
        # fallback: build a job straight from the AST
        job = self._job_from_ast_func(decl)
        self.emit_proc(job)

    def _find_local_func(self, decl: A.FuncDecl) -> FuncInfo | None:
        for cand in self.reg.global_funcs.get(decl.name, []):
            if cand.decl is decl:
                return cand
        return None

    def _job_from_ast_func(self, decl: A.FuncDecl) -> ProcJob:
        params = []
        for p in decl.params:
            ty = self.reg.resolve_type(p.ty, self.generic_env)
            if getattr(p, "is_variadic", False):
                ty = Ty.array(ty)
            params.append(JobParam(name=nim_ident(p.name), ty=ty,
                                   default=p.default,
                                   is_var=isinstance(p.ty, A.InoutType),
                                   is_variadic=getattr(p, "is_variadic", False)))
        ret = self.reg.resolve_type(decl.ret, self.generic_env) if decl.ret else VOID
        return ProcJob(kind="func", name=nim_ident(decl.name), params=params,
                       ret=ret, generics=list(decl.generic_params),
                       body=decl.body, src_line=decl.line, is_local=True)

    MUTATING_VALUE_METHODS = {
        "append", "insert", "remove", "removeFirst", "removeLast",
        "removeAll", "popLast", "sort", "swapAt", "shuffle", "formUnion",
        "formIntersection", "formSymmetricDifference", "updateValue",
        "removeValue", "merge",
    }

    def _property_access_info(self, node: Any):
        """Resolve ``obj.prop`` / a bare property name to an assignable
        property.  Returns (base_expr|None, prop_name, prop_ty, field|None)."""
        if isinstance(node, A.MemberExpr) and not node.optional:
            base_ty = self._infer_expr_type_quiet(node.base)
            if base_ty is not None and base_ty.kind == "named":
                fld = self.reg.field_info(base_ty, node.name)
                if fld is not None and fld.is_observed:
                    return (node.base, node.name,
                            self.reg.field_type(base_ty, node.name) or UNKNOWN,
                            fld)
                cp = self.reg.computed_prop(base_ty, node.name)
                if cp is not None and any(a.kind == "set"
                                          for a in cp.accessors):
                    return node.base, node.name, cp.ty, None
            return None
        if isinstance(node, A.Ident) and self.type_info is not None:
            fld = self._find_field_recursive(self.type_info, node.name)
            if fld is not None and fld.is_observed:
                return None, node.name, fld.ty, fld
            cp = self.reg.computed_prop(Ty.named(self.type_info.name),
                                        node.name)
            if cp is not None and any(a.kind == "set" for a in cp.accessors):
                return None, node.name, cp.ty, None
        return None

    def _gen_mutating_property_stmt(self, call: A.CallExpr) -> bool:
        callee = call.callee
        if not isinstance(callee, A.MemberExpr) or callee.optional:
            return False
        info = self._property_access_info(callee.base)
        if info is None:
            return False
        base_expr, prop_name, prop_ty, fld = info
        name = callee.name
        mutating = name in self.MUTATING_VALUE_METHODS
        if not mutating:
            for fi in self.reg.find_methods(prop_ty, name):
                if fi.is_mutating:
                    mutating = True
                    break
        if not mutating:
            return False
        if base_expr is not None:
            base_code, _ = self.gen_expr(base_expr, None)
            read_code = f"{self._wrap(base_code)}.{prop_name}"
            assign_code = read_code
        else:
            read_code = f"self.{prop_name}"
            assign_code = read_code
        direct = (fld is not None and self.in_init and
                  (base_expr is None or isinstance(base_expr, A.SelfExpr)))
        if direct and fld is not None:
            read_code = f"self.{self.backing_field_name(fld.name)}"
            assign_code = read_code
        tmp = self.temp("prop")
        self.line(f"var {tmp}: {self.nim_type(prop_ty)} = {read_code}")
        code, ty = self.code_method_on(tmp, prop_ty, name, call.args,
                                       call.trailing_closure, call)
        if ty.is_void:
            self.code(code)
        else:
            self.code(f"discard {code}")
        self.code(f"{assign_code} = {tmp}")
        return True

    def gen_expr_stmt(self, stmt: A.ExprStmt) -> None:
        expr = stmt.expr
        if isinstance(expr, A.AssignExpr):
            self.gen_assign(expr)
            return
        if isinstance(expr, A.CallExpr) and \
                self._gen_mutating_property_stmt(expr):
            return
        if (isinstance(expr, A.CallExpr) and
                isinstance(expr.callee, A.MemberExpr) and
                isinstance(expr.callee.base, A.SelfExpr) and
                expr.callee.name == "init"):
            code, ty = self._gen_self_init(expr, expr)
            if ty.kind == "bool" and self.in_failable_init:
                self.line(f"if not ({code}):")
                self.indent()
                self.line("return false")
                self.dedent()
            else:
                self.code(code)
            return
        if (isinstance(expr, A.CallExpr) and
                isinstance(expr.callee, A.MemberExpr) and
                isinstance(expr.callee.base, A.SuperExpr) and
                expr.callee.name == "init"):
            code, ty = self.gen_expr(expr, None)
            if ty.kind == "bool" and self.in_failable_init:
                self.line(f"if not ({code}):")
                self.indent()
                self.line("return false")
                self.dedent()
            else:
                self.code(code)
            return
        if isinstance(expr, A.CallExpr) or isinstance(expr, A.TryExpr):
            code, ty = self.gen_expr(expr, None)
            if not ty.is_void:
                self.code(f"discard {code}")
            else:
                self.code(code)
            return
        if isinstance(expr, A.BinaryExpr) and expr.op in ASSIGN_OPS:
            self.gen_assign(A.AssignExpr(target=expr.left, op=expr.op,
                                         value=expr.right, line=expr.line,
                                         col=expr.col))
            return
        code, ty = self.gen_expr(expr, None)
        if not ty.is_void:
            self.code(f"discard {code}")
        else:
            self.code(code)

    def _target_is_property(self, node: Any) -> bool:
        """True when assigning to ``node`` goes through a property setter."""
        if isinstance(node, A.Ident):
            if self.lookup(node.name) is not None:
                return False
            if node.name in self.global_syms:
                return False
            if self.type_info is None:
                return False
            fld = self._find_field_recursive(self.type_info, node.name)
            if fld is not None:
                return fld.is_observed and not self.in_init
            cp = self.reg.computed_prop(Ty.named(self.type_info.name),
                                        node.name)
            return cp is not None
        if isinstance(node, A.MemberExpr):
            base_ty = self._infer_expr_type_quiet(node.base)
            if base_ty is None:
                return False
            if base_ty.kind == "type":
                info = self.reg.types.get(base_ty.name)
                if info is not None:
                    sv = info.static_vars.get(node.name)
                    return isinstance(sv, ComputedProp)
                return False
            if base_ty.kind == "named":
                fld = self.reg.field_info(base_ty, node.name)
                if fld is not None:
                    if fld.is_observed and not (
                            self.in_init and isinstance(node.base, A.SelfExpr)):
                        return True
                    return False
                return self.reg.computed_prop(base_ty, node.name) is not None
        if isinstance(node, A.SubscriptExpr):
            base_ty = self._infer_expr_type_quiet(node.base)
            if base_ty is None or base_ty.kind not in ("named", "generic"):
                return False
            subs = (self._generic_subscripts(base_ty)
                    if base_ty.kind == "generic"
                    else self.reg.find_subscripts(base_ty))
            for si in subs:
                if len(si.param_types) == len(node.args) and not si.is_static:
                    return si.has_setter()
        return False

    def _assign_static_property(self, info: TypeInfo, cp: ComputedProp,
                                expr: A.AssignExpr) -> bool:
        if not any(a.kind == "set" for a in cp.accessors):
            self.error(f"cannot assign to read-only static property "
                       f"'{cp.name}'", expr)
        get_code = f"{info.nim_name}_{nim_ident(cp.name)}()"
        set_code = f"{info.nim_name}_{nim_ident(cp.name)}_set"
        code, got = self.gen_expr(expr.value, cp.ty)
        code = self.coerce(code, got, cp.ty, expr.value)
        if expr.op == "=":
            self.code(f"{set_code}({code})")
            return True
        base_op = expr.op[:-1]
        if base_op in ("/", "%") and cp.ty.is_int:
            base_op = "div" if base_op == "/" else "mod"
        elif cp.ty.kind == "array" and base_op == "+":
            code = code if got is not None and got.kind == "array" \
                else f"@[{code}]"
            base_op = "&"
        elif cp.ty.kind == "string" and base_op == "+":
            base_op = "&"
        self.code(f"{set_code}({get_code} {base_op} {code})")
        return True

    def gen_assign(self, expr: A.AssignExpr) -> None:
        if isinstance(expr.target, A.Ident) and expr.target.name == "_" and \
                expr.op == "=":
            code, ty = self.gen_expr(expr.value, None)
            if ty.is_void:
                self.code(code)
            else:
                self.code(f"discard {code}")
            return
        if expr.op in ASSIGN_OPS and \
                self.reg.find_operators("infix", expr.op):
            self.error(f"custom assignment operator '{expr.op}' is not "
                       "supported by Swim", expr)
        if isinstance(expr.target, A.Ident) and self.static_owner is not None:
            sv = self.static_owner.static_vars.get(expr.target.name)
            if isinstance(sv, ComputedProp):
                if self._assign_static_property(self.static_owner, sv, expr):
                    return
        if isinstance(expr.target, A.MemberExpr) and \
                not expr.target.optional:
            target_base_ty = self._infer_expr_type_quiet(expr.target.base)
            if target_base_ty is not None and target_base_ty.kind == "type":
                target_info = self.reg.types.get(target_base_ty.name)
                if target_info is not None:
                    sv = target_info.static_vars.get(expr.target.name)
                    if isinstance(sv, ComputedProp):
                        if self._assign_static_property(target_info, sv,
                                                        expr):
                            return
        if isinstance(expr.target, A.SubscriptExpr):
            target_base_ty = self._infer_expr_type_quiet(expr.target.base)
            if target_base_ty is not None and target_base_ty.kind == "type":
                target_info = self.reg.types.get(target_base_ty.name)
                if target_info is not None and \
                        self._assign_static_subscript(target_info,
                                                      expr.target, expr):
                    return
        target, target_ty = self.gen_assign_target(expr.target, expr.value)
        value_ty_expected = target_ty
        code, got = self.gen_expr(expr.value, value_ty_expected)
        code = self.coerce(code, got, target_ty, expr.value)
        if expr.op == "=":
            self.code(f"{target} = {code}")
            return
        base_op = expr.op[:-1]
        if self._target_is_property(expr.target):
            # Compound assignment through a getter/setter pair: expand it so
            # the setter runs exactly once with the computed value.
            if base_op in ("/", "%") and target_ty is not None and \
                    target_ty.is_int:
                nim_op = "div" if base_op == "/" else "mod"
                self.code(f"{target} = {target} {nim_op} {code}")
            elif target_ty is not None and target_ty.kind == "string" and \
                    base_op == "+":
                self.code(f"{target} = {target} & {code}")
            elif target_ty is not None and target_ty.kind == "array" and \
                    base_op == "+":
                rhs = code if got is not None and got.kind == "array" \
                    else f"@[{code}]"
                self.code(f"{target} = {target} & {rhs}")
            else:
                self.code(f"{target} = {target} {base_op} {code}")
            return
        if base_op in ("/", "%") and target_ty is not None and target_ty.is_int:
            nim_op = "div" if base_op == "/" else "mod"
            self.code(f"{target} = {target} {nim_op} {code}")
            return
        if target_ty is not None and target_ty.kind == "string" and base_op == "+":
            self.code(f"{target} &= {code}")
            return
        if target_ty is not None and target_ty.kind == "array" and base_op == "+":
            self.code(f"{target}.add({code})")
            return
        self.code(f"{target} {expr.op} {code}")

    def gen_assign_target(self, node: Any, value_node: Any) -> tuple[str, Ty]:
        if isinstance(node, A.Ident):
            sym = self.lookup(node.name)
            if sym is None:
                sym = self.global_syms.get(node.name)
            if sym is None and self.static_owner is not None:
                sv = self.static_owner.static_vars.get(node.name)
                if sv is not None:
                    if isinstance(sv, ComputedProp):
                        self.error(f"cannot assign to static computed "
                                   f"property '{node.name}' here", node)
                    return (self.static_var_nim(self.static_owner, node.name),
                            sv.ty)
            if sym is None and self.type_info is not None:
                fld = self._find_field_recursive(self.type_info, node.name)
                if fld is not None:
                    if fld.is_let and not self.in_init:
                        self.error(f"cannot assign to let property "
                                   f"'{node.name}'", node)
                    if fld.observers:
                        if self.in_init:
                            return (f"self.{self.backing_field_name(fld.name)}",
                                    fld.ty)
                        return f"self.{nim_ident(node.name)}", fld.ty
                    return f"self.{nim_ident(node.name)}", fld.ty
                cp = self.reg.computed_prop(
                    Ty.named(self.type_info.name), node.name)
                if cp is not None:
                    return f"self.{nim_ident(node.name)}", cp.ty
            if sym is None:
                self.error(f"cannot assign to undefined variable "
                           f"'{node.name}'", node)
            if not sym.mutable:
                if sym.kind == "field":
                    self.error(f"cannot assign to let property '{node.name}'",
                               node)
                self.error(f"cannot assign to let constant '{node.name}'", node)
            return sym.nim, sym.ty
        if isinstance(node, A.MemberExpr):
            if node.optional:
                self.error("cannot assign through an optional chain", node)
            base_code, base_ty = self.gen_expr(node.base, None)
            if base_ty.kind == "type":
                info = self.reg.types.get(base_ty.name)
                if info is not None and node.name in info.static_vars:
                    sv = info.static_vars[node.name]
                    if isinstance(sv, ComputedProp):
                        has_set = any(a.kind == "set" for a in sv.accessors)
                        if not has_set:
                            self.error(f"cannot assign to read-only static "
                                       f"property '{node.name}'", node)
                        return (f"{info.nim_name}_{nim_ident(node.name)}",
                                sv.ty)
                    if isinstance(sv, FieldInfo) and sv.is_let:
                        self.error(f"cannot assign to static let property "
                                   f"'{node.name}'", node)
                    return (self.static_var_nim(info, node.name), sv.ty)
                self.error(f"type '{base_ty.name}' has no static property "
                           f"'{node.name}'", node)
            if base_ty.kind == "named":
                fld = self.reg.field_info(base_ty, node.name)
                if fld is not None:
                    if fld.is_let and not self.in_init:
                        self.error(f"cannot assign to let property "
                                   f"'{node.name}'", node)
                    fty = self.reg.field_type(base_ty, node.name) or UNKNOWN
                    if fld.observers and self.in_init and \
                            isinstance(node.base, A.SelfExpr):
                        return (f"{base_code}."
                                f"{self.backing_field_name(fld.name)}", fty)
                    return f"{base_code}.{nim_ident(node.name)}", fty
                cp = self.reg.computed_prop(base_ty, node.name)
                if cp is not None:
                    has_set = any(a.kind == "set" for a in cp.accessors)
                    if not has_set:
                        self.error(f"cannot assign to read-only property "
                                   f"'{node.name}'", node)
                    return f"{base_code}.{nim_ident(node.name)}", cp.ty
            self.error(f"cannot assign to '{node.name}'", node)
        if isinstance(node, A.SubscriptExpr):
            base_code, base_ty = self.gen_expr(node.base, None)
            if base_ty.kind == "array":
                idx, _ = self.gen_expr(node.args[0].expr, INT)
                return f"{base_code}[{idx}]", base_ty.elem
            if base_ty.kind == "dict":
                key_code, key_ty = self.gen_expr(node.args[0].expr, base_ty.key)
                return f"{base_code}[{key_code}]", base_ty.value
            if base_ty.kind == "string":
                idx, _ = self.gen_expr(node.args[0].expr, INT)
                return f"{base_code}[{idx}]", CHAR
            user = self._user_subscript(base_ty, node.args, node)
            if user is not None:
                si, codes = user
                if not si.has_setter():
                    self.error("cannot assign through a read-only subscript",
                               node)
                return (f"{self._wrap(base_code)}[{', '.join(codes)}]",
                        si.ret)
            self.error("invalid subscript assignment", node)
        self.error("invalid assignment target", node)
        raise AssertionError

    # ------------------------------------------------------------ if / guard
    def gen_if(self, stmt: A.IfStmt) -> None:
        self._gen_if_chain(stmt.conditions, stmt.then_body, stmt.else_body)

    def _gen_if_chain(self, conds: list, then_body: list,
                      else_body: list) -> None:
        if not conds:
            self.gen_block(then_body)
            return
        # combine leading boolean conditions
        codes: list[str] = []
        i = 0
        while i < len(conds) and isinstance(conds[i], A.CondExpr):
            code, _ = self.gen_expr(conds[i].expr, BOOL)
            codes.append(code)
            i += 1
        if codes:
            self.line("if " + " and ".join(codes) + ":")
            self.indent()
            if i < len(conds):
                self._gen_if_chain(conds[i:], then_body, else_body)
            else:
                self.gen_block(then_body)
            self.dedent()
            self._emit_else(else_body)
            return
        cond = conds[0]
        rest = conds[1:]
        if isinstance(cond, A.CondBinding):
            tmp = self.temp("opt")
            code, got = self.gen_expr(cond.expr, None)
            if got.kind != "unknown" and not got.is_optional:
                self.error("initializer for conditional binding must have "
                           "Optional type, not "
                           f"'{ty_to_str(got)}'", cond)
            self.line(f"let {tmp} = {code}")
            self.line(f"if {tmp}.isSome:")
            self.indent()
            self.push_scope()
            self.line(f"let {nim_ident(cond.name)} = {tmp}.get")
            self.declare(cond.name, nim_ident(cond.name),
                         unwrap_optional(got), mutable=(cond.kind == "var"),
                         kind="local")
            if rest:
                self._gen_if_chain(rest, then_body, else_body)
            else:
                self.gen_block(then_body, new_scope=False)
            self.pop_scope()
            self.dedent()
            self._emit_else(else_body)
            return
        if isinstance(cond, A.CaseCond):
            tmp = self.temp("case")
            code, got = self.gen_expr(cond.expr, None)
            self.line(f"let {tmp} = {code}")
            cond_code, bind_lines = self._pattern_condition(
                cond.pattern, tmp, got, bind_prefix="")
            self.push_scope()
            self.line(f"if {cond_code}:")
            self.indent()
            bind_lines()
            if rest:
                self._gen_if_chain(rest, then_body, else_body)
            else:
                self.gen_block(then_body, new_scope=False)
            self.dedent()
            self.pop_scope()
            self._emit_else(else_body)
            return
        self.error("invalid condition", cond)

    def _emit_else(self, else_body: list) -> None:
        if not else_body:
            return
        self.line("else:")
        self.indent()
        if len(else_body) == 1 and isinstance(else_body[0], A.IfStmt):
            self.gen_if(else_body[0])
        else:
            self.gen_block(else_body)
        self.dedent()

    def gen_guard(self, stmt: A.GuardStmt) -> None:
        self._validate_guard_exit(stmt)
        for cond in stmt.conditions:
            if isinstance(cond, A.CondExpr):
                code, _ = self.gen_expr(cond.expr, BOOL)
                self.line(f"if not ({code}):")
                self.indent()
                self.gen_block(stmt.else_body)
                self.dedent()
            elif isinstance(cond, A.CondBinding):
                tmp = self.temp("opt")
                code, got = self.gen_expr(cond.expr, None)
                if got.kind != "unknown" and not got.is_optional:
                    self.error("initializer for conditional binding must have "
                               "Optional type, not "
                               f"'{ty_to_str(got)}'", cond)
                self.line(f"let {tmp} = {code}")
                self.line(f"if {tmp}.isNone:")
                self.indent()
                self.gen_block(stmt.else_body)
                self.dedent()
                nim_name = nim_ident(cond.name)
                if self.lookup(cond.name) is not None or \
                        cond.name in self.global_syms:
                    # A guard binding may shadow an outer value; Nim forbids
                    # re-declaring the same name in one scope.
                    nim_name = f"{nim_name}_guarded"
                self.line(f"let {nim_name} = {tmp}.get")
                self.declare(cond.name, nim_name,
                             unwrap_optional(got),
                             mutable=(cond.kind == "var"), kind="local")
            elif isinstance(cond, A.CaseCond):
                tmp = self.temp("case")
                code, got = self.gen_expr(cond.expr, None)
                self.line(f"let {tmp} = {code}")
                cond_code, bind_lines = self._pattern_condition(
                    cond.pattern, tmp, got, bind_prefix="")
                self.line(f"if not ({cond_code}):")
                self.indent()
                self.gen_block(stmt.else_body)
                self.dedent()
                bind_lines()
            else:
                self.error("invalid guard condition", cond)

    def _validate_guard_exit(self, stmt: A.GuardStmt) -> None:
        if not stmt.else_body:
            self.error("guard body must not be empty", stmt)
        last = stmt.else_body[-1]
        ok = isinstance(last, (A.ReturnStmt, A.BreakStmt, A.ContinueStmt,
                               A.ThrowStmt))
        if isinstance(last, A.ExprStmt) and isinstance(last.expr, A.CallExpr):
            callee = last.expr.callee
            if isinstance(callee, A.Ident) and callee.name in (
                    "fatalError", "preconditionFailure"):
                ok = True
        if not ok:
            self.error("guard body must end with return, break, continue, "
                       "throw or fatalError", stmt)

    # ---------------------------------------------------------------- loops
    def gen_while(self, stmt: A.WhileStmt, body_block: str | None = None) -> None:
        all_expr = all(isinstance(c, A.CondExpr) for c in stmt.conditions)
        self.breakables.append({"kind": "loop", "label": None})
        if all_expr and stmt.conditions:
            codes = [self.gen_expr(c.expr, BOOL)[0] for c in stmt.conditions]
            self.line("while " + " and ".join(codes) + ":")
            self.indent()
            self.push_scope()
            if body_block:
                self.line(f"block {body_block}:")
                self.indent()
            self.gen_block(stmt.body, new_scope=False)
            if body_block:
                self.dedent()
            self.pop_scope()
            self.dedent()
        else:
            self.line("while true:")
            self.indent()
            self.push_scope()
            for cond in stmt.conditions:
                if isinstance(cond, A.CondExpr):
                    code, _ = self.gen_expr(cond.expr, BOOL)
                    self.line(f"if not ({code}): break")
                elif isinstance(cond, A.CondBinding):
                    tmp = self.temp("opt")
                    code, got = self.gen_expr(cond.expr, None)
                    self.line(f"let {tmp} = {code}")
                    self.line(f"if {tmp}.isNone: break")
                    self.line(f"let {nim_ident(cond.name)} = {tmp}.get")
                    self.declare(cond.name, nim_ident(cond.name),
                                 unwrap_optional(got), mutable=(cond.kind == "var"))
                else:
                    self.error("this condition is not supported in while loops",
                               cond)
            if body_block:
                self.line(f"block {body_block}:")
                self.indent()
            self.gen_block(stmt.body, new_scope=False)
            if body_block:
                self.dedent()
            self.pop_scope()
            self.dedent()
        self.breakables.pop()

    def gen_repeat(self, stmt: A.RepeatStmt, body_block: str | None = None) -> None:
        body_label = body_block or f"swRepeat{self.temp('body')}"
        self.line("while true:")
        self.indent()
        self.line(f"block {body_label}:")
        self.indent()
        self.push_scope()
        self.breakables.append({"kind": "repeat", "label": body_label})
        self.gen_block(stmt.body, new_scope=False)
        self.breakables.pop()
        self.pop_scope()
        self.dedent()
        cond_code, _ = self.gen_expr(stmt.condition, BOOL)
        self.line(f"if not ({cond_code}): break")
        self.dedent()

    def gen_for(self, stmt: A.ForStmt, body_block: str | None = None) -> None:
        if stmt.pattern is not None:
            self._gen_for_case(stmt, body_block)
            return
        self.push_scope()
        iterable = stmt.iterable
        self.breakables.append({"kind": "loop", "label": None})
        body = stmt.body

        def emit_body() -> None:
            if body_block:
                self.line(f"block {body_block}:")
                self.indent()
            if stmt.where_cond is not None:
                code, _ = self.gen_expr(stmt.where_cond, BOOL)
                self.line(f"if not ({code}): continue")
            self.gen_block(body, new_scope=False)
            if body_block:
                self.dedent()

        handled = False
        # for (k, v) in dict
        if isinstance(iterable, A.Ident):
            pass
        it_ty = self._infer_expr_type_quiet(iterable)
        if it_ty is not None and it_ty.kind == "dict":
            if len(stmt.names) == 2:
                base_code, _ = self.gen_expr(iterable, None)
                kname = nim_ident(stmt.names[0]) if stmt.names[0] != "_" else "_"
                vname = nim_ident(stmt.names[1]) if stmt.names[1] != "_" else "_"
                self.line(f"for {kname}, {vname} in {base_code}.pairs:")
                self.indent()
                if stmt.names[0] != "_":
                    self.declare(stmt.names[0], kname, it_ty.key, mutable=False)
                if stmt.names[1] != "_":
                    self.declare(stmt.names[1], vname, it_ty.value, mutable=False)
                emit_body()
                self.dedent()
                self.breakables.pop()
                self.pop_scope()
                return
            else:
                self.error("iterate over a dictionary with 'for (key, value) "
                           "in dict' or use 'dict.keys'", iterable)
        # dict.keys / dict.values
        if isinstance(iterable, A.MemberExpr) and not iterable.optional and \
                iterable.name in ("keys", "values"):
            base_code, base_ty = self.gen_expr(iterable.base, None)
            if base_ty.kind == "dict":
                nim_member = "keys" if iterable.name == "keys" else "values"
                elem_ty = base_ty.key if nim_member == "keys" else base_ty.value
                only = stmt.names[0]
                name = nim_ident(only) if only != "_" else "_"
                self.line(f"for {name} in {base_code}.{nim_member}:")
                self.indent()
                if only != "_":
                    self.declare(only, name, elem_ty, mutable=False)
                emit_body()
                self.dedent()
                self.breakables.pop()
                self.pop_scope()
                return
        # enumerated()
        if (isinstance(iterable, A.CallExpr) and not iterable.args and
                isinstance(iterable.callee, A.MemberExpr) and
                iterable.callee.name == "enumerated"):
            base_code, base_ty = self.gen_expr(iterable.callee.base, None)
            elem_ty = self._elem_type(base_ty, iterable)
            if len(stmt.names) == 2:
                iname = nim_ident(stmt.names[0]) if stmt.names[0] != "_" else "_"
                xname = nim_ident(stmt.names[1]) if stmt.names[1] != "_" else "_"
                self.line(f"for {iname}, {xname} in {base_code}.pairs:")
                self.indent()
                if stmt.names[0] != "_":
                    self.declare(stmt.names[0], iname, INT, mutable=False)
                if stmt.names[1] != "_":
                    self.declare(stmt.names[1], xname, elem_ty, mutable=False)
                emit_body()
                self.dedent()
                self.breakables.pop()
                self.pop_scope()
                return
            else:
                code = f"enumerated({base_code})"
                name = nim_ident(stmt.names[0])
                self.line(f"for {name} in {code}:")
                self.indent()
                self.declare(stmt.names[0], name,
                             Ty.tuple((INT, elem_ty), ("offset", "element")),
                             mutable=False)
                emit_body()
                self.dedent()
                self.breakables.pop()
                self.pop_scope()
                return
        # range.reversed()
        if (isinstance(iterable, A.CallExpr) and not iterable.args and
                isinstance(iterable.callee, A.MemberExpr) and
                iterable.callee.name == "reversed" and
                isinstance(iterable.callee.base, A.BinaryExpr) and
                iterable.callee.base.op in ("...", "..<")):
            rng = iterable.callee.base
            low_code, _ = self.gen_expr(rng.left, INT)
            high_code, _ = self.gen_expr(rng.right, INT)
            if rng.op == "...":
                start = high_code
            else:
                start = f"({high_code}) - 1"
            name = nim_ident(stmt.names[0]) if stmt.names[0] != "_" else "_"
            self.line(f"for {name} in countdown({start}, {low_code}):")
            self.indent()
            if stmt.names[0] != "_":
                self.declare(stmt.names[0], name, INT, mutable=False)
            emit_body()
            self.dedent()
            self.breakables.pop()
            self.pop_scope()
            return
        # stride(from:to:by:) / stride(from:through:by:)
        if (isinstance(iterable, A.CallExpr) and
                isinstance(iterable.callee, A.Ident) and
                iterable.callee.name == "stride"):
            labels = {a.label: a.expr for a in iterable.args}
            if "from" in labels and "by" in labels:
                frm, _ = self.gen_expr(labels["from"], INT)
                by, _ = self.gen_expr(labels["by"], INT)
                if "to" in labels:
                    to, _ = self.gen_expr(labels["to"], INT)
                    code = f"swimStrideTo({frm}, {to}, {by})"
                elif "through" in labels:
                    to, _ = self.gen_expr(labels["through"], INT)
                    code = f"swimStride({frm}, {to}, {by})"
                else:
                    self.error("stride needs 'to:' or 'through:'", iterable)
                name = nim_ident(stmt.names[0]) if stmt.names[0] != "_" else "_"
                self.line(f"for {name} in {code}:")
                self.indent()
                if stmt.names[0] != "_":
                    self.declare(stmt.names[0], name, INT, mutable=False)
                emit_body()
                self.dedent()
                self.breakables.pop()
                self.pop_scope()
                return
        # generic sequence / range / string
        code, got = self.gen_expr(iterable, None)
        elem_ty = self._iter_elem_type(got, iterable)
        if len(stmt.names) == 1:
            name = nim_ident(stmt.names[0]) if stmt.names[0] != "_" else "_"
            self.line(f"for {name} in {code}:")
            self.indent()
            if stmt.names[0] != "_":
                self.declare(stmt.names[0], name, elem_ty, mutable=False)
            emit_body()
            self.dedent()
        elif len(stmt.names) == 2:
            a = nim_ident(stmt.names[0]) if stmt.names[0] != "_" else "_"
            b = nim_ident(stmt.names[1]) if stmt.names[1] != "_" else "_"
            self.line(f"for ({a}, {b}) in {code}:")
            self.indent()
            ty_a, ty_b = UNKNOWN, UNKNOWN
            if elem_ty.kind == "tuple" and len(elem_ty.args) == 2:
                ty_a, ty_b = elem_ty.args
            if stmt.names[0] != "_":
                self.declare(stmt.names[0], a, ty_a, mutable=False)
            if stmt.names[1] != "_":
                self.declare(stmt.names[1], b, ty_b, mutable=False)
            emit_body()
            self.dedent()
        else:
            self.error("too many loop variables", stmt)
        self.breakables.pop()
        self.pop_scope()

    def _gen_for_case(self, stmt: A.ForStmt,
                      body_block: str | None = None) -> None:
        self.push_scope()
        self.breakables.append({"kind": "loop", "label": None})
        try:
            code, got = self.gen_expr(stmt.iterable, None)
            elem_ty = self._iter_elem_type(got, stmt.iterable)
            tmp = self.temp("case")
            self.line(f"for {tmp} in {code}:")
            self.indent()
            self.push_scope()
            cond, bindings = self._pattern_condition(stmt.pattern, tmp,
                                                     elem_ty, "")
            self.line(f"if not ({cond}): continue")
            bindings()
            if body_block:
                self.line(f"block {body_block}:")
                self.indent()
            if stmt.where_cond is not None:
                wcode, _ = self.gen_expr(stmt.where_cond, BOOL)
                self.line(f"if not ({wcode}): continue")
            self.gen_block(stmt.body, new_scope=False)
            if body_block:
                self.dedent()
            self.pop_scope()
            self.dedent()
        finally:
            self.breakables.pop()
            self.pop_scope()

    def _elem_type(self, ty: Ty, node: Any) -> Ty:
        if ty.kind == "array":
            return ty.elem
        if ty.kind == "string":
            return CHAR
        if ty.kind == "dict":
            return ty.key
        if ty.kind == "range":
            return ty.elem
        if ty.kind == "set":
            return ty.elem
        return UNKNOWN

    def _iter_elem_type(self, ty: Ty, node: Any) -> Ty:
        if ty.kind == "unknown":
            self.error("cannot infer the element type of this sequence; add "
                       "an explicit type annotation", node)
        return self._elem_type(ty, node)

    def _infer_expr_type_quiet(self, expr: Any) -> Ty | None:
        saved_out = self.out
        saved_map = dict(self.line_map)
        self.out = []
        try:
            _, ty = self.gen_expr(expr, None)
        except SwimError:
            ty = None
        finally:
            self.out = saved_out
            self.line_map = saved_map
        return ty

    # --------------------------------------------------------------- switch
    def gen_switch(self, stmt: A.SwitchStmt, label: str | None) -> None:
        subj_code, subj_ty = self.gen_expr(stmt.subject, None)
        label_name = nim_ident(label) if label else \
            f"swSwitch{self.switch_counter + 1}"
        if not label:
            self.switch_counter += 1
        self.line(f"block {label_name}:")
        self.indent()
        subj = self.temp("subj")
        matched = self.temp("matched")
        self.line(f"let {subj} = {subj_code}")
        self.line(f"var {matched} = false")
        self.breakables.append({"kind": "switch", "label": label_name})
        cases = stmt.cases
        for i, case in enumerate(cases):
            self.gen_switch_case(case, subj, subj_ty, matched, cases, i)
        self.breakables.pop()
        self.dedent()

    def gen_switch_case(self, case: A.CaseClause, subj: str, subj_ty: Ty,
                        matched: str, cases: list | None = None,
                        index: int = 0) -> None:
        self.current_src_line = case.line
        if cases is None:
            cases = [case]

        def emit_body() -> None:
            self._gen_case_body(case, cases, index)

        if case.is_default:
            self.line(f"if not {matched}:")
            self.indent()
            self.line(f"{matched} = true")
            emit_body()
            self.dedent()
            return
        for pat in case.patterns:
            self.line(f"if not {matched}:")
            self.indent()
            self.push_scope()
            self.line("block:")
            self.indent()
            cond, bindings = self._pattern_condition(pat, subj, subj_ty,
                                                     bind_prefix="")
            self.line(f"if {cond}:")
            self.indent()
            bindings()
            if case.where_cond is not None:
                where_code, _ = self.gen_expr(case.where_cond, BOOL)
                self.line(f"if {where_code}:")
                self.indent()
                self.line(f"{matched} = true")
                emit_body()
                self.dedent()
            else:
                self.line(f"{matched} = true")
                emit_body()
            self.dedent()
            self.dedent()
            self.pop_scope()
            self.dedent()

    def _gen_case_body(self, case: A.CaseClause, cases: list,
                       index: int) -> None:
        body = case.body
        if body and isinstance(body[-1], A.FallthroughStmt):
            if index + 1 >= len(cases):
                self.error("'fallthrough' cannot transfer control out of the "
                           "switch (no following case)", body[-1])
            self.gen_block(body[:-1])
            self._gen_fallthrough_body(cases, index + 1)
        else:
            self.gen_block(body)

    def _gen_fallthrough_body(self, cases: list, index: int) -> None:
        """Inline the body of the case control fell through into."""
        case = cases[index]
        self.current_src_line = case.line
        self.push_scope()
        body = case.body
        if body and isinstance(body[-1], A.FallthroughStmt):
            if index + 1 >= len(cases):
                self.error("'fallthrough' cannot transfer control out of the "
                           "switch (no following case)", body[-1])
            self.gen_block(body[:-1], new_scope=False)
            self._gen_fallthrough_body(cases, index + 1)
        else:
            self.gen_block(body, new_scope=False)
        self.pop_scope()

    def _capture(self, fn) -> list:
        saved_out = self.out
        saved_map = self.line_map
        saved_indent = self.indent_level
        self.out = []
        self.line_map = {}
        self.indent_level = 0
        try:
            fn()
            return list(self.out)
        finally:
            self.out = saved_out
            self.line_map = saved_map
            self.indent_level = saved_indent

    def _splice(self, lines: list, indent: int) -> None:
        prefix = "  " * indent
        for raw in lines:
            self.out.append((prefix + raw) if raw else "")
            self.line_map[len(self.out) - 1] = self.current_src_line

    def _pattern_condition(self, pat: A.Pattern, subj: str, subj_ty: Ty,
                           bind_prefix: str) -> tuple[str, Callable]:
        """Return (condition code, callable that emits bindings+declarations)."""
        emitted: list = []  # list[(code_line, name|None, Ty)]

        def bindings() -> None:
            for item in emitted:
                code, name, ty = item
                self.line(code)
                if name:
                    self.declare(name, nim_ident(name), ty, mutable=False,
                                 kind="pattern")

        if isinstance(pat, A.WildcardPattern):
            return "true", bindings
        if isinstance(pat, A.BindingPattern):
            if pat.optional_unwrap:
                inner = unwrap_optional(subj_ty)
                emitted.append((f"let {nim_ident(pat.name)} = ({subj}).get",
                                pat.name, inner))
                return f"({subj}).isSome", bindings
            emitted.append((f"let {nim_ident(pat.name)} = {subj}",
                            pat.name, subj_ty))
            return "true", bindings
        if isinstance(pat, A.LiteralPattern):
            code, _ = self.gen_expr(pat.expr, subj_ty)
            return f"{subj} == {code}", bindings
        if isinstance(pat, A.RangePattern):
            low, _ = self.gen_expr(pat.low, subj_ty)
            high, _ = self.gen_expr(pat.high, subj_ty)
            if subj_ty.kind == "string" or subj_ty.kind == "char":
                self.error("range patterns on strings are not supported", pat)
            op = "<=" if pat.closed else "<"
            return f"({subj} >= {low}) and ({subj} {op} {high})", bindings
        if isinstance(pat, A.IsPattern):
            ty = self.reg.resolve_type(pat.ty, self.generic_env)
            info = self.reg.type_info(ty)
            if info is None or info.kind != "class":
                self.error("'case is' currently supports class types only",
                           pat)
            return f"{subj} of {info.nim_name}", bindings
        if isinstance(pat, A.EnumCasePattern):
            return self._enum_pattern_condition(pat, subj, subj_ty, emitted)
        self.error("unsupported pattern", pat)
        raise AssertionError

    def _enum_pattern_condition(self, pat: A.EnumCasePattern, subj: str,
                                subj_ty: Ty, emitted: list) -> tuple[str, Callable]:
        base_ty = unwrap_optional(subj_ty)
        info = self.reg.type_info(base_ty)
        is_optional_subject = subj_ty.is_optional or pat.optional_unwrap
        case_name = pat.case_name

        def bindings() -> None:
            for item in emitted:
                code, name, ty = item
                self.line(code)
                if name:
                    self.declare(name, nim_ident(name), ty, mutable=False,
                                 kind="pattern")

        if case_name in ("some", "none") and (subj_ty.is_optional or
                                             pat.optional_unwrap):
            if case_name == "none":
                return f"({subj}).isNone", bindings
            if pat.bindings and pat.bindings[0][1]:
                emitted.append((f"let {nim_ident(pat.bindings[0][1])} = "
                                f"({subj}).get", pat.bindings[0][1],
                                unwrap_optional(subj_ty)))
            return f"({subj}).isSome", bindings
        if info is None:
            self.error(f"cannot pattern match '.{case_name}' on type "
                       f"'{ty_to_str(subj_ty)}'", pat)
        case = info.enum_case(case_name)
        if case is None:
            self.error(f"type '{info.name}' has no case '{case_name}'", pat)
        if info.kind == "enum" and self._enum_has_payload(info):
            kind_name = f"{info.nim_name}Kind"
            cond = f"({subj}).kind == {kind_name}.{nim_ident(case_name)}"
            for i, (label, bname, bkind) in enumerate(pat.bindings):
                if i >= len(case.assoc):
                    break
                if bname is None:
                    continue
                fname, fty = case.assoc[i]
                field = (f"{info.nim_name}_{nim_ident(case_name)}_"
                         f"{nim_ident(fname)}")
                emitted.append((f"let {nim_ident(bname)} = ({subj}).{field}",
                                bname, fty))
            return cond, bindings
        if is_optional_subject:
            return f"({subj}).get == {info.nim_name}.{nim_ident(case_name)}", \
                bindings
        return f"({subj}) == {info.nim_name}.{nim_ident(case_name)}", bindings

    def _enum_has_payload(self, info: TypeInfo) -> bool:
        return any(c.has_assoc for c in info.enum_cases)

    # --------------------------------------------------- return/break/continue
    def gen_return(self, stmt: A.ReturnStmt) -> None:
        if self.in_failable_init:
            if stmt.expr is None or isinstance(stmt.expr, A.NilLit):
                self.line("return true" if stmt.expr is None else "return false")
                return
            self.error("a failable initializer can only return nil or fall "
                       "through to the end of the body", stmt)
        if self.return_collector is not None and \
                (self.ret_ty.kind == "unknown" or self.ret_ty.is_void):
            if stmt.expr is not None:
                ty = self._infer_expr_type_quiet(stmt.expr)
                if ty is not None and ty.kind != "unknown":
                    self.return_collector.append(ty)
            else:
                self.return_collector.append(VOID)
            self.line("discard")
            return
        if stmt.expr is None:
            if not self.ret_ty.is_void:
                self.error("non-void function must return a value", stmt)
            self.line("return")
            return
        if self.ret_ty.is_void:
            self.error("cannot return a value from a Void function", stmt)
        code, got = self.gen_expr(stmt.expr, self.ret_ty)
        code = self.coerce(code, got, self.ret_ty, stmt.expr)
        self.line(f"return {code}")

    def gen_break(self, stmt: A.BreakStmt) -> None:
        if stmt.label is not None:
            self.line(f"break {nim_ident(stmt.label)}")
            return
        if not self.breakables:
            self.error("'break' outside of a loop or switch", stmt)
        inner = self.breakables[-1]
        if inner["kind"] == "switch":
            self.line(f"break {inner['label']}")
        else:
            self.line("break")

    def gen_continue(self, stmt: A.ContinueStmt) -> None:
        if stmt.label is not None:
            target = self.continue_labels.get(stmt.label)
            if target is None:
                self.error(f"cannot find loop labeled '{stmt.label}'", stmt)
            self.line(f"break {target}")
            return
        for entry in reversed(self.breakables):
            if entry["kind"] == "switch":
                continue
            if entry["kind"] == "repeat":
                self.line(f"break {entry['label']}")
                return
            self.line("continue")
            return
        self.error("'continue' outside of a loop", stmt)

    # -------------------------------------------------------------- throw/do
    def gen_throw(self, stmt: A.ThrowStmt) -> None:
        info, case, args = self._resolve_error_case(stmt.expr)
        if info is None or case is None:
            code, ty = self.gen_expr(stmt.expr, None)
            if ty.kind == "named" and self.reg.is_error_type(ty):
                self.line(f"raise {code}")
                return
            self.error("can only throw cases of an enum that conforms to "
                       "'Error'", stmt)
        exc_type = f"{info.nim_name}_{nim_ident(case.name)}"
        msg = f"{info.name}.{case.name}"
        if case.assoc:
            var = self.temp("err")
            self.line(f"var {var} = newException({exc_type}, "
                      f"{self.str_literal(msg)})")
            for i, (fname, fty) in enumerate(case.assoc):
                if i < len(args):
                    code, got = self.gen_expr(args[i], fty)
                    code = self.coerce(code, got, fty, args[i])
                else:
                    code = f"default({self.nim_type(fty)})"
                self.line(f"{var}.{nim_ident(fname)} = {code}")
            self.line(f"raise {var}")
        else:
            self.line(f"raise newException({exc_type}, {self.str_literal(msg)})")

    def _resolve_error_case(self, expr: A.Expr):
        """Return (TypeInfo, EnumCaseInfo, args) for throw targets."""
        if isinstance(expr, A.CallExpr) and isinstance(expr.callee, A.MemberExpr) \
                and isinstance(expr.callee.base, A.Ident):
            tname = expr.callee.base.name
            info = self.reg.types.get(tname)
            if info is not None and info.kind == "enum" and info.is_error:
                case = info.enum_case(expr.callee.name)
                if case is not None:
                    return info, case, [a.expr for a in expr.args]
        if isinstance(expr, A.MemberExpr) and isinstance(expr.base, A.Ident):
            tname = expr.base.name
            info = self.reg.types.get(tname)
            if info is not None and info.kind == "enum" and info.is_error:
                case = info.enum_case(expr.name)
                if case is not None:
                    return info, case, []
        if isinstance(expr, A.CallExpr) and isinstance(expr.callee, A.Ident):
            info = self.reg.types.get(expr.callee.name)
            if info is not None and info.kind == "enum" and info.is_error:
                cases = info.enum_cases
                if len(cases) == 1:
                    return info, cases[0], [a.expr for a in expr.args]
        return None, None, []

    def gen_do(self, stmt: A.DoStmt) -> None:
        if not stmt.catches:
            self.line("block:")
            self.indent()
            self.gen_block(stmt.body)
            self.dedent()
            return
        self.line("try:")
        self.indent()
        self.gen_block(stmt.body)
        self.dedent()
        err = self.temp("err")
        self.line(f"except CatchableError as {err}:")
        self.indent()
        # pre-bind named catches so ``where`` clauses can use them
        names_seen: list[str] = []
        for clause in stmt.catches:
            if clause.name and clause.name not in names_seen:
                names_seen.append(clause.name)
                self.line(f"let {nim_ident(clause.name)} = {err}")
                self.declare(clause.name, nim_ident(clause.name), UNKNOWN,
                             mutable=False, kind="error")
        first = True
        saw_default = False
        for clause in stmt.catches:
            if clause.is_default:
                cond = None
            else:
                cond = self._catch_condition(clause, err)
            if cond is None:
                saw_default = True
                self.line("else:" if not first else "if true:")
            else:
                self.line(("elif " if not first else "if ") + cond + ":")
            self.indent()
            self.push_scope()
            self._emit_catch_bindings(clause, err)
            self.gen_block(clause.body, new_scope=False)
            self.pop_scope()
            self.dedent()
            first = False
            if saw_default:
                break
        if not saw_default:
            self.line("else:")
            self.indent()
            self.line("raise")
            self.dedent()
        self.dedent()

    def _emit_catch_bindings(self, clause: A.CatchClause, err: str) -> None:
        for pat in clause.patterns:
            if not isinstance(pat, A.EnumCasePattern) or "." not in pat.case_name:
                continue
            tname, cname = pat.case_name.split(".", 1)
            info = self.reg.types.get(tname)
            if info is None or info.kind != "enum":
                continue
            case = info.enum_case(cname)
            if case is None:
                continue
            exc_type = f"{info.nim_name}_{nim_ident(cname)}"
            for i, (label, bname, bkind) in enumerate(pat.bindings):
                if i >= len(case.assoc) or not bname:
                    continue
                fname, fty = case.assoc[i]
                self.line(f"let {nim_ident(bname)} = "
                          f"(ref {exc_type})({err}).{nim_ident(fname)}")
                self.declare(bname, nim_ident(bname), fty, mutable=False,
                             kind="error")

    def _catch_condition(self, clause: A.CatchClause, err: str) -> str | None:
        conds: list[str] = []
        for pat in clause.patterns:
            if isinstance(pat, A.NamedType):
                if pat.name in ("Error", "any Error"):
                    return None
                info = self.reg.types.get(pat.name)
                if info is not None and info.kind == "enum" and info.is_error:
                    conds.append(f"{err} of {info.nim_name}")
                elif info is not None and info.kind == "protocol":
                    return None
                else:
                    conds.append(f"{err} of {mangle_type_name(pat.name)}")
            elif isinstance(pat, A.EnumCasePattern):
                if "." in pat.case_name:
                    tname, cname = pat.case_name.split(".", 1)
                    info = self.reg.types.get(tname)
                    if info is not None and info.kind == "enum" and info.is_error:
                        conds.append(f"{err} of {info.nim_name}_{nim_ident(cname)}")
                    else:
                        conds.append("false")
                else:
                    conds.append("false")
            else:
                conds.append("false")
        if not conds:
            return None
        if len(conds) == 1:
            return conds[0]
        return " or ".join(f"({c})" for c in conds)

    # ---------------------------------------------------------- labeled stmt
    def gen_labeled(self, stmt: A.LabeledStmt) -> None:
        label = stmt.label
        inner = stmt.stmt
        if isinstance(inner, A.SwitchStmt):
            self.gen_switch(inner, label=label)
            return
        if isinstance(inner, (A.ForStmt, A.WhileStmt, A.RepeatStmt)):
            has_cont = self._body_has_continue(inner, label)
            body_label = f"swCont{self.temp('body')}"
            self.line(f"block {nim_ident(label)}:")
            self.indent()
            if has_cont:
                self.continue_labels[label] = body_label
            try:
                if isinstance(inner, A.ForStmt):
                    self.gen_for(inner, body_block=body_label if has_cont else None)
                elif isinstance(inner, A.WhileStmt):
                    self.gen_while(inner, body_block=body_label if has_cont else None)
                else:
                    self.gen_repeat(inner, body_block=body_label if has_cont else None)
            finally:
                if has_cont:
                    self.continue_labels.pop(label, None)
            self.dedent()
            return
        # labeled plain statement: just a block label
        self.line(f"block {nim_ident(label)}:")
        self.indent()
        self.gen_block([inner])
        self.dedent()

    def _body_has_continue(self, node: Any, label: str) -> bool:
        found = False

        def walk(n: Any) -> None:
            nonlocal found
            if found or n is None:
                return
            if isinstance(n, A.ContinueStmt) and n.label == label:
                found = True
                return
            if isinstance(n, A.FuncDecl):
                return
            if isinstance(n, A.Node):
                for key, value in vars(n).items():
                    if key in ("line", "col"):
                        continue
                    walk(value)
            elif isinstance(n, list):
                for item in n:
                    walk(item)

        walk(node)
        return found

    # ============================================================ expressions
    def gen_expr(self, node: Any, expected: Ty | None = None):
        if isinstance(node, A.IntLit):
            if expected is not None and (expected.is_float or expected.is_int):
                return node.text, expected
            return node.text, INT
        if isinstance(node, A.FloatLit):
            if expected is not None and expected.is_float:
                return node.text, expected
            return node.text, FLOAT
        if isinstance(node, A.BoolLit):
            return ("true" if node.value else "false"), BOOL
        if isinstance(node, A.StringLit):
            return self.gen_string_literal(node, expected)
        if isinstance(node, A.NilLit):
            if expected is not None and expected.is_optional:
                inner = expected.inner
                if inner.kind == "unknown":
                    self.error("cannot infer the type of nil here", node)
                return f"none({self.nim_type(inner, node)})", expected
            if expected is not None and expected.kind == "unknown":
                return "nil", UNKNOWN
            self.error("cannot infer the type of 'nil'; add a type annotation",
                       node)
        if isinstance(node, A.MagicLit):
            if node.kind == "file":
                return self.str_literal(self.filename.rsplit("/", 1)[-1]), STRING
            if node.kind == "line":
                return str(node.line), INT
            if node.kind == "column":
                return str(node.col), INT
            fname = self.current_proc_name or "main"
            if fname != "main" and not fname.endswith(")"):
                fname += "()"
            return self.str_literal(fname), STRING
        if isinstance(node, A.Ident):
            return self.gen_ident(node)
        if isinstance(node, A.SelfExpr):
            if self.self_ty is None:
                self.error("'self' used outside of a type member", node)
            return "self", self.self_ty
        if isinstance(node, A.SuperExpr):
            self.error("'super' can only be used as 'super.method(...)'", node)
        if (isinstance(node, A.CallExpr) and
                isinstance(node.callee, A.MemberExpr) and
                isinstance(node.callee.base, A.SelfExpr) and
                node.callee.name == "init"):
            return self._gen_self_init(node, node)
        if isinstance(node, (A.MemberExpr, A.CallExpr, A.SubscriptExpr,
                             A.ForceExpr)):
            return self.gen_postfix_expr(node, expected)
        if isinstance(node, A.BinaryExpr):
            return self.gen_binary(node, expected)
        if isinstance(node, A.AssignExpr):
            self.error("assignment is not allowed in this position", node)
        if isinstance(node, A.PostfixExpr):
            return self.gen_postfix_unary(node)
        if isinstance(node, A.UnaryExpr):
            return self.gen_unary(node, expected)
        if isinstance(node, A.TernaryExpr):
            return self.gen_ternary(node, expected)
        if isinstance(node, A.ClosureExpr):
            return self.gen_closure(node, expected)
        if isinstance(node, A.ArrayLit):
            return self.gen_array_literal(node, expected)
        if isinstance(node, A.DictLit):
            return self.gen_dict_literal(node, expected)
        if isinstance(node, A.TupleLit):
            return self.gen_tuple_literal(node, expected)
        if isinstance(node, A.CastExpr):
            return self.gen_cast(node, expected)
        if isinstance(node, A.TypeCheckExpr):
            return self.gen_type_check(node, expected)
        if isinstance(node, A.TryExpr):
            return self.gen_try(node, expected)
        if isinstance(node, A.CaseRefExpr):
            return self.gen_case_ref(node, expected)
        if isinstance(node, A.GenericRefExpr):
            info = self.reg.types.get(node.name)
            resolved = tuple(self.reg.resolve_type(a, self.generic_env)
                             for a in node.args)
            code = info.nim_name if info is not None else \
                (NIM_PRIM.get(node.name, node.name))
            return code, Ty(kind="type", name=node.name, args=resolved)
        if isinstance(node, A.ExprStmt):
            return self.gen_expr(node.expr, expected)
        self.error(f"unsupported expression: {type(node).__name__}", node)
        raise AssertionError

    # -------------------------------------------------------------- literals
    def str_literal(self, text: str) -> str:
        out = ['"']
        for ch in text:
            if ch == "\\":
                out.append("\\\\")
            elif ch == '"':
                out.append('\\"')
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            elif ord(ch) < 32:
                out.append(f"\\x{ord(ch):02X}")
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)

    def char_literal(self, ch: str) -> str:
        if ch == "'":
            return "'\\''"
        if ch == "\\":
            return "'\\\\'"
        if ch == "\n":
            return "'\\n'"
        if ch == "\r":
            return "'\\r'"
        if ch == "\t":
            return "'\\t'"
        return f"'{ch}'"

    def gen_string_literal(self, node: A.StringLit, expected: Ty | None):
        if expected is not None and expected.kind == "char":
            if len(node.parts) == 1 and node.parts[0][0] == "text" and \
                    len(node.parts[0][1]) == 1:
                return self.char_literal(node.parts[0][1]), CHAR
            self.error("a Character must be a single-character string literal",
                       node)
        pieces: list[str] = []
        for part in node.parts:
            if part[0] == "text":
                if part[1]:
                    pieces.append(self.str_literal(part[1]))
            else:
                code, _ = self.gen_expr(part[1], None)
                pieces.append(f"swimStr({code})")
        if not pieces:
            return '""', STRING
        if len(pieces) == 1 and node.parts and node.parts[0][0] == "text":
            return pieces[0], STRING
        return " & ".join(pieces), STRING

    # ------------------------------------------------------------ identifiers
    def gen_ident(self, node: A.Ident):
        name = node.name
        sym = self.lookup(name)
        if sym is not None:
            return sym.nim, sym.ty
        if name in self.local_func_decls:
            decl = self.local_func_decls[name]
            ty = self._func_type_from_decl(decl)
            return nim_ident(name), ty
        # Type members (and nested types) shadow module-level declarations.
        scope_info: TypeInfo | None = self.type_info or self.static_owner
        if scope_info is not None:
            cur: TypeInfo | None = scope_info
            while cur is not None:
                nested = cur.nested.get(name)
                if nested is not None:
                    return nested.nim_name, Ty(kind="type", name=nested.name)
                cur = cur.parent
        if self.type_info is not None:
            fld = self._find_field_recursive(self.type_info, name)
            if fld is not None:
                return f"self.{nim_ident(name)}", fld.ty
            cp = self.reg.computed_prop(Ty.named(self.type_info.name), name)
            if cp is not None:
                return f"self.{nim_ident(name)}", cp.ty
            stat = self._find_static_var(self.type_info, name)
            if stat is not None:
                return self.static_var_nim(self.type_info, name), stat.ty
            if self.type_info.kind == "enum" and name == "rawValue" and \
                    self.type_info.raw_type is not None:
                return "rawValue(self)", self.type_info.raw_type
            if name in self.type_info.methods:
                self.error(f"method '{name}' can only be called; add '('", node)
        if self.static_owner is not None:
            if name == "allCases" and \
                    "CaseIterable" in self.static_owner.conformances:
                return (f"allCases({self.static_owner.nim_name})",
                        Ty.array(Ty.named(self.static_owner.name)))
            sv = self.static_owner.static_vars.get(name)
            if sv is not None:
                if isinstance(sv, ComputedProp):
                    return (f"{self.static_owner.nim_name}_"
                            f"{nim_ident(name)}()", sv.ty)
                return (self.static_var_nim(self.static_owner, name), sv.ty)
            sfis = self.static_owner.static_funcs.get(name)
            if sfis:
                return (self.static_proc_name(self.static_owner, name),
                        self._func_type_from_info(sfis[0]))
        if self.self_ty is not None:
            prop = self.code_builtin_property("self", self.self_ty, name, node)
            if prop is not None:
                return prop
            if self.self_ty.kind == "tuple" and name in self.self_ty.labels:
                idx = self.self_ty.labels.index(name)
                return f"self[{idx}]", self.self_ty.args[idx]
        if name in self.global_syms:
            sym = self.global_syms[name]
            return sym.nim, sym.ty
        from .types import PRIM_KINDS
        if name in PRIM_KINDS:
            return NIM_PRIM[PRIM_KINDS[name]], Ty(kind="type", name=name)
        if name in ("Array", "Dictionary", "Set", "Optional", "Any",
                    "AnyObject"):
            return name, Ty(kind="type", name=name)
        if (name in BUILTIN_FREE_NAMES or name in NIMX_FUNCS
                or name in ZETA_FUNCS or name in FERROUI_FUNCS):
            return name, Ty(kind="builtins", name=name)
        # enum case shorthand written without a dot (not valid Swift but helpful)
        info = self.reg.types.get(name)
        if info is not None:
            return info.nim_name, Ty(kind="type", name=name)
        if name in self.reg.global_funcs:
            fis = self.reg.global_funcs[name]
            ty = Ty(kind="func", name=name)
            if fis:
                ty = self._func_type_from_info(fis[0])
            return nim_ident(name), ty
        if name in ("true", "false"):
            return name, BOOL
        self.error(f"use of unresolved identifier '{name}'", node)
        raise AssertionError

    def _find_field_recursive(self, info: TypeInfo, name: str) -> FieldInfo | None:
        cur: TypeInfo | None = info
        while cur is not None:
            f = cur.field(name)
            if f is not None:
                return f
            cur = cur.superclass
        return None

    def _find_static_var(self, info: TypeInfo, name: str):
        cur: TypeInfo | None = info
        while cur is not None:
            if name in cur.static_vars:
                return cur.static_vars[name]
            cur = cur.superclass
        return None

    def _func_type_from_info(self, fi: FuncInfo) -> Ty:
        return Ty(kind="func", name=fi.name,
                  args=(tuple(fi.param_types), fi.ret))

    def _func_type_from_decl(self, decl: A.FuncDecl) -> Ty:
        params = []
        for p in decl.params:
            ty = self.reg.resolve_type(p.ty, self.generic_env)
            if getattr(p, "is_variadic", False):
                ty = Ty.array(ty)
            params.append(ty)
        ret = self.reg.resolve_type(decl.ret, self.generic_env) if decl.ret else VOID
        return Ty(kind="func", name=decl.name, args=(tuple(params), ret))

    # -------------------------------------------------------- postfix chains
    def flatten_postfix(self, node: Any):
        steps: list[dict] = []

        def walk(n: Any) -> Any:
            if isinstance(n, A.CallExpr):
                if isinstance(n.callee, A.MemberExpr) and not n.callee.optional:
                    base = walk(n.callee.base)
                    steps.append({"kind": "method", "name": n.callee.name,
                                  "optional": n.callee.optional, "call": n})
                    return base
                if isinstance(n.callee, A.MemberExpr) and n.callee.optional:
                    base = walk(n.callee.base)
                    steps.append({"kind": "method", "name": n.callee.name,
                                  "optional": True, "call": n})
                    return base
                base = walk(n.callee)
                steps.append({"kind": "func", "optional": getattr(n, "optional_call", False),
                              "call": n})
                return base
            if isinstance(n, A.MemberExpr):
                base = walk(n.base)
                steps.append({"kind": "member", "name": n.name,
                              "optional": n.optional, "node": n})
                return base
            if isinstance(n, A.SubscriptExpr):
                base = walk(n.base)
                steps.append({"kind": "sub", "optional": n.optional,
                              "node": n, "call": None})
                return base
            if isinstance(n, A.ForceExpr):
                base = walk(n.operand)
                steps.append({"kind": "force", "optional": False, "node": n})
                return base
            return n

        base = walk(node)
        return base, steps

    def gen_postfix_expr(self, node: Any, expected: Ty | None):
        base, steps = self.flatten_postfix(node)
        if isinstance(base, A.SuperExpr):
            return self.gen_super_chain(steps, node)
        if isinstance(base, A.Ident) and steps and \
                steps[0]["kind"] == "func" and \
                self._is_implicit_self_method(base.name):
            call = steps[0]["call"]
            code, ty = self.code_method_on("self", self.self_ty, base.name,
                                           call.args, call.trailing_closure,
                                           call)
            for step in steps[1:]:
                code, ty = self.apply_step(step, code, ty)
            return code, ty
        base_code, base_ty = self.gen_expr(base, None)
        opt_idx = None
        for i, step in enumerate(steps):
            if step.get("optional"):
                opt_idx = i
                break
        if opt_idx is None:
            code, ty = base_code, base_ty
            for step in steps:
                code, ty = self.apply_step(step, code, ty)
            return code, ty
        code, ty = base_code, base_ty
        for step in steps[:opt_idx]:
            code, ty = self.apply_step(step, code, ty)
        inner_code, inner_ty = self.gen_chain_from(steps, opt_idx, "it",
                                                   unwrap_optional(ty))
        final = f"swimOptFlatMap({code}, {inner_code})"
        return final, make_optional(unwrap_optional(inner_ty))

    def _is_implicit_self_method(self, name: str) -> bool:
        if self.type_info is None:
            if self.self_ty is not None and self.lookup(name) is None and \
                    name not in self.global_syms and \
                    name not in self.local_func_decls and \
                    name not in self.reg.global_funcs:
                return self._builtin_method_known(self.self_ty, name)
            return False
        if self.lookup(name) is not None:
            return False
        if name in self.global_syms or name in self.local_func_decls:
            return False
        if name in self.reg.global_funcs:
            return False
        cur: TypeInfo | None = self.type_info
        while cur is not None:
            if name in cur.methods:
                return True
            ext = self.reg.extensions.get(cur.name)
            if ext is not None and name in ext.methods:
                return True
            cur = cur.superclass
        return False

    def _builtin_method_known(self, ty: Ty, name: str) -> bool:
        k = ty.kind
        names = {
            "array": {"append", "insert", "remove", "removeFirst",
                      "removeLast", "removeAll", "popLast", "contains",
                      "allSatisfy", "swapAt", "sorted", "reversed",
                      "enumerated", "min", "max", "joined", "dropFirst",
                      "dropLast", "prefix", "suffix", "map", "filter",
                      "forEach", "firstIndex", "index", "reduce",
                      "first", "last"},
            "string": {"append", "insert", "remove", "removeFirst",
                       "removeLast", "removeAll", "uppercased", "lowercased",
                       "capitalized", "hasPrefix", "hasSuffix", "contains",
                       "split", "components", "replacingOccurrences",
                       "trimmingCharacters", "reversed", "dropFirst",
                       "dropLast", "prefix", "suffix", "index", "firstIndex",
                       "map", "filter", "forEach", "allSatisfy", "first",
                       "last", "reduce"},
            "dict": {"updateValue", "removeValue"},
            "set": {"contains", "insert", "remove"},
            "char": {"uppercased", "lowercased"},
            "int": {"isMultiple", "description"},
            "float": {"squareRoot", "rounded", "description"},
        }
        if k in names:
            return name in names[k]
        if k == "optional":
            return name in ("map", "flatMap")
        if k == "range":
            return name in ("map", "filter", "contains", "count",
                            "forEach", "reversed")
        if k in INT_KINDS:
            return name in names["int"]
        if k in FLOAT_KINDS:
            return name in names["float"]
        return False

    def _generic_subscripts(self, ty: Ty) -> list:
        out: list = []
        for proto in self._generic_protocols(ty):
            for pinfo in self._protocol_chain(proto):
                for member in getattr(pinfo.decl, "members", []):
                    if isinstance(member, A.SubscriptDecl):
                        out.append(SubscriptInfo(
                            params=member.params,
                            param_types=[self.reg.resolve_type(p.ty, {})
                                         for p in member.params],
                            ret=self.reg.resolve_type(member.ret, {}),
                            accessors=member.accessors, decl=member))
        return out

    def _user_subscript(self, base_ty: Ty, args: list, node: Any):
        """Return (SubscriptInfo, rendered argument codes) or None."""
        if base_ty.kind == "generic":
            subs = self._generic_subscripts(base_ty)
        else:
            subs = self.reg.find_subscripts(base_ty)
        if not subs:
            return None
        cands = [si for si in subs
                 if len(si.param_types) == len(args) and not si.is_static]
        if not cands:
            return None
        si = cands[0]
        codes: list[str] = []
        for i, arg in enumerate(args):
            exp = si.param_types[i] if i < len(si.param_types) else None
            code, got = self.gen_expr(arg.expr, exp)
            if exp is not None:
                code = self.coerce(code, got, exp, arg.expr)
            codes.append(code)
        return si, codes

    def _select_static_subscript(self, info: TypeInfo, args: list,
                                 node: Any):
        cands = [si for si in info.subscripts
                 if si.is_static and len(si.param_types) == len(args)]
        if not cands:
            return None
        arg_types = [self._infer_expr_type_quiet(a.expr) for a in args]
        best = None
        best_score = -1.0
        for si in cands:
            score = 0.0
            compatible = True
            for i, aty in enumerate(arg_types):
                pty = si.param_types[i]
                if aty is None or aty.kind == "unknown":
                    score += 0.5
                    continue
                match = self._overload_match(pty, aty)
                if match <= 0:
                    compatible = False
                    break
                score += match
            if compatible and score > best_score:
                best = si
                best_score = score
        if best is None:
            return None
        codes: list[str] = []
        for i, arg in enumerate(args):
            exp = best.param_types[i]
            code, got = self.gen_expr(arg.expr, exp)
            code = self.coerce(code, got, exp, arg.expr)
            codes.append(code)
        return best, codes

    def _static_subscript_on(self, info: TypeInfo, args: list, node: Any):
        selected = self._select_static_subscript(info, args, node)
        if selected is None:
            self.error(f"type '{info.name}' has no matching static subscript",
                       node)
        si, codes = selected
        if not si.nim_get:
            self.error(f"static subscript of '{info.name}' is not available",
                       node)
        return f"{si.nim_get}({', '.join(codes)})", si.ret

    def _assign_static_subscript(self, info: TypeInfo, target: Any,
                                 expr: A.AssignExpr) -> bool:
        selected = self._select_static_subscript(info, target.args, target)
        if selected is None:
            return False
        si, codes = selected
        if not si.has_setter() or not si.nim_set:
            self.error(f"cannot assign through a read-only static subscript "
                       f"of '{info.name}'", target)
        code, got = self.gen_expr(expr.value, si.ret)
        code = self.coerce(code, got, si.ret, expr.value)
        if expr.op == "=":
            self.code(f"{si.nim_set}({', '.join(codes + [code])})")
            return True
        get_code = f"{si.nim_get}({', '.join(codes)})"
        base_op = expr.op[:-1]
        if base_op in ("/", "%") and si.ret.is_int:
            base_op = "div" if base_op == "/" else "mod"
        elif si.ret.kind == "array" and base_op == "+":
            code = code if got is not None and got.kind == "array" \
                else f"@[{code}]"
            base_op = "&"
        call_args = ", ".join(codes + [f"{get_code} {base_op} {code}"])
        self.code(f"{si.nim_set}({call_args})")
        return True

    def code_subscript_on(self, base_code: str, base_ty: Ty, args: list,
                          node: Any):
        if not args:
            self.error("empty subscript", node)
        if base_ty.kind == "type":
            info = self.reg.types.get(base_ty.name)
            if info is not None:
                return self._static_subscript_on(info, args, node)
            self.error(f"type '{base_ty.name}' has no static subscript", node)
        if base_ty.kind in ("array", "string") and len(args) == 1:
            arg_ty = self._infer_expr_type_quiet(args[0].expr)
            if arg_ty is not None and arg_ty.kind == "range":
                return self._code_range_slice(base_code, base_ty,
                                              args[0].expr, node)
        if base_ty.kind == "array":
            idx, _ = self.gen_expr(args[0].expr, INT)
            return f"({base_code})[{idx}]", base_ty.elem
        if base_ty.kind == "dict":
            key, _ = self.gen_expr(args[0].expr, base_ty.key)
            return f"tableOpt({base_code}, {key})", \
                Ty.optional(base_ty.value)
        if base_ty.kind == "string":
            idx, _ = self.gen_expr(args[0].expr, INT)
            return f"({base_code})[{idx}]", CHAR
        user = self._user_subscript(base_ty, args, node)
        if user is not None:
            si, codes = user
            return f"{self._wrap(base_code)}[{', '.join(codes)}]", si.ret
        if base_ty.kind == "unknown":
            idx, _ = self.gen_expr(args[0].expr, None)
            return f"({base_code})[{idx}]", UNKNOWN
        self.error(f"value of type '{ty_to_str(base_ty)}' cannot be "
                   "subscripted", node)

    def _code_range_slice(self, base_code: str, base_ty: Ty, rng: Any,
                          node: Any):
        if not (isinstance(rng, A.BinaryExpr) and rng.op in ("...", "..<")):
            self.error("slicing with a range value is not supported yet; "
                       "write the range inline", node)
        low, _ = self.gen_expr(rng.left, INT)
        high, _ = self.gen_expr(rng.right, INT)
        fn = "swimSliceInclusive" if rng.op == "..." else "swimSlice"
        if base_ty.kind == "string":
            fn = "swimSliceStrInclusive" if rng.op == "..." else "swimSliceStr"
        return f"{fn}({base_code}, {low}, {high})", base_ty

    def gen_chain_from(self, steps: list, i: int, var: str, var_ty: Ty):
        cur_code, cur_ty = var, unwrap_optional(var_ty)
        j = i
        while j < len(steps):
            step = steps[j]
            if step.get("optional"):
                level_code, level_ty = self.apply_step(step, cur_code, cur_ty)
                if j + 1 < len(steps):
                    rest_code, rest_ty = self.gen_chain_from(steps, j + 1,
                                                             "it", level_ty)
                    inner = f"swimOptFlatMap({level_code}, {rest_code})"
                    return inner, make_optional(unwrap_optional(rest_ty))
                return level_code, level_ty
            cur_code, cur_ty = self.apply_step(step, cur_code, cur_ty)
            j += 1
        return cur_code, cur_ty

    def apply_step(self, step: dict, code: str, ty: Ty):
        kind = step["kind"]
        node = step.get("node") or step.get("call")
        if kind == "member":
            return self.code_member_on(code, ty, step["name"], node)
        if kind == "method":
            call = step["call"]
            return self.code_method_on(code, ty, step["name"],
                                       call.args, call.trailing_closure, call)
        if kind == "func":
            call = step["call"]
            return self.code_call_value(code, ty, call.args,
                                        call.trailing_closure, call)
        if kind == "sub":
            return self.code_subscript_on(code, ty, step["node"].args,
                                          step["node"])
        if kind == "force":
            if ty.is_optional:
                return f"({code}).get", ty.inner
            if ty.kind == "unknown":
                return f"({code}).get", UNKNOWN
            self.error("cannot force-unwrap a non-optional value", node)
        self.error(f"internal: unknown chain step {kind}", node)
        raise AssertionError

    # ------------------------------------------------------------- member access
    def code_member_on(self, base_code: str, base_ty: Ty, name: str,
                       node: Any):
        if base_ty.kind == "type":
            return self.code_type_member(base_ty.name, name, node,
                                         type_args=list(base_ty.args))
        if base_ty.kind == "unknown":
            self.error(f"cannot infer the type of the receiver when accessing "
                       f"'.{name}'", node)
        if base_ty.is_optional:
            self.error(f"optional value must be unwrapped before accessing "
                       f"'.{name}'", node)
        if base_ty.kind == "named":
            info = self.reg.type_info(base_ty)
            if info is None:
                self.error(f"unknown type '{base_ty.name}'", node)
            fld = self.reg.field_info(base_ty, name)
            if fld is not None:
                return f"{base_code}.{nim_ident(name)}", \
                    self.reg.field_type(base_ty, name) or fld.ty
            cp = self.reg.computed_prop(base_ty, name)
            if cp is not None:
                return f"{base_code}.{nim_ident(name)}", cp.ty
            if info.kind == "enum":
                case = info.enum_case(name)
                if case is not None and not case.has_assoc:
                    return f"{info.nim_name}.{nim_ident(name)}", base_ty
                if name == "rawValue" and info.raw_type is not None:
                    return f"rawValue({base_code})", info.raw_type
            if name == "description":
                return f"swimStr({base_code})", STRING
            if name in info.methods:
                self.error(f"method '{name}' can only be called; add '('", node)
            self.error(f"type '{info.name}' has no member '{name}'", node)
        if base_ty.kind == "tuple":
            if name.isdigit():
                idx = int(name)
                if idx < len(base_ty.args):
                    return f"({base_code})[{idx}]", base_ty.args[idx]
                self.error(f"tuple has no element {idx}", node)
            if name in base_ty.labels:
                idx = base_ty.labels.index(name)
                return f"({base_code}).{nim_ident(name)}", base_ty.args[idx]
            self.error(f"tuple has no member '{name}'", node)
        if base_ty.kind == "generic":
            member = self._generic_member(base_ty, name)
            if member is not None:
                ty, kind = member
                if kind == "method":
                    self.error(f"method '{name}' can only be called; add '('",
                               node)
                return f"({base_code}).{nim_ident(name)}", ty
        builtin = self.code_builtin_property(base_code, base_ty, name, node)
        if builtin is not None:
            return builtin
        self.error(f"value of type '{ty_to_str(base_ty)}' has no member "
                   f"'{name}'", node)

    def code_type_member(self, type_name: str, name: str, node: Any,
                         type_args: list | None = None):
        info = self.reg.types.get(type_name)
        prim = self.prim_type_name(type_name)
        if info is not None:
            nested = info.nested.get(name)
            if nested is not None:
                return nested.nim_name, Ty(kind="type", name=nested.name)
            if info.kind == "enum":
                case = info.enum_case(name)
                if case is not None:
                    if case.has_assoc:
                        self.error(f"enum case '{name}' needs arguments", node)
                    if any(c.has_assoc for c in info.enum_cases):
                        value = (f"{info.nim_name}(kind: {info.nim_name}Kind."
                                 f"{nim_ident(name)})")
                    else:
                        value = f"{info.nim_name}.{nim_ident(name)}"
                    return value, Ty.named(type_name)
                if name == "rawValue":
                    self.error("rawValue is an instance property", node)
            sv = info.static_vars.get(name)
            if sv is not None:
                if isinstance(sv, ComputedProp):
                    return (f"{info.nim_name}_{nim_ident(name)}()", sv.ty)
                return self.static_var_nim(info, name), sv.ty
            if name in info.static_funcs:
                fi = info.static_funcs[name][0]
                return self.static_proc_name(info, name), \
                    self._func_type_from_info(fi)
            if name == "allCases" and "CaseIterable" in info.conformances:
                return f"allCases({info.nim_name})", Ty.array(Ty.named(type_name))
            if info.kind == "enum":
                self.error(f"enum '{type_name}' has no case '{name}'", node)
            self.error(f"type '{type_name}' has no static member '{name}'", node)
        if prim is not None:
            return self.code_prim_static_member(prim, name, node)
        if type_name in ("Any", "AnyObject"):
            self.error(f"type '{type_name}' has no static member '{name}'", node)
        self.error(f"unknown type '{type_name}'", node)

    def prim_type_name(self, name: str) -> str | None:
        from .types import PRIM_KINDS
        if name in PRIM_KINDS:
            return PRIM_KINDS[name]
        return None

    # -------------------------------------------------------------- calls
    def code_method_on(self, recv_code: str, recv_ty: Ty, name: str, args: list,
                       trailing: Any, node: Any):
        if recv_ty.kind == "generic":
            req = self._generic_method(recv_ty, name)
            if req is not None:
                params, param_types, ret = req
                arg_codes = self._bind_call_args(params, param_types, args,
                                                 trailing, node, [])
                return (f"({recv_code}).{nim_ident(name)}"
                        f"({', '.join(arg_codes)})", ret)
            self.error(f"cannot find method '{name}' on generic type "
                       f"'{recv_ty.name}'", node)
        if recv_ty.kind == "type":
            return self.code_static_call(recv_ty.name, name, args, trailing,
                                         node, type_args=list(recv_ty.args))
        if recv_ty.kind == "unknown":
            # fall back: try a plain method call
            fn_args = []
            for a in args:
                c, _ = self.gen_expr(a.expr, None)
                fn_args.append((a.label, c, UNKNOWN))
            return f"{self._wrap(recv_code)}.{nim_ident(name)}" \
                   f"({self._render_args_simple(fn_args)})", UNKNOWN
        user = self._user_method_call(recv_code, recv_ty, name, args, trailing, node)
        if user is not None:
            return user
        builtin = self.code_builtin_method(recv_code, recv_ty, name, args,
                                           trailing, node)
        if builtin is not None:
            return builtin
        self.error(f"value of type '{ty_to_str(recv_ty)}' has no method "
                   f"'{name}'", node)

    def _user_method_call(self, recv_code: str, recv_ty: Ty, name: str,
                          args: list, trailing: Any, node: Any):
        methods = self.reg.find_methods(recv_ty, name)
        if not methods:
            return None
        fi = self._select_overload(methods, args, trailing, node)
        arg_codes = self._bind_call_args(fi.params, fi.param_types, args,
                                         trailing, node, fi.generics)
        ret = substitute(fi.ret, self._last_generic_map) if fi.generics else fi.ret
        return (f"{self._wrap(recv_code)}.{nim_ident(name)}"
                f"({', '.join(arg_codes)})", ret)

    def code_static_call(self, type_name: str, name: str, args: list,
                         trailing: Any, node: Any, type_args: list | None = None):
        info = self.reg.types.get(type_name)
        if info is not None:
            if name == "init":
                self.error("init cannot be called directly", node)
            fis = info.static_funcs.get(name, [])
            if fis:
                fi = self._select_overload(fis, args, trailing, node)
                arg_codes = self._bind_call_args(fi.params, fi.param_types,
                                                 args, trailing, node,
                                                 fi.generics)
                ret = substitute(fi.ret, self._last_generic_map) \
                    if fi.generics else fi.ret
                if type_args:
                    ret = substitute(ret, self._type_arg_map(info, type_args))
                return (f"{self.static_proc_name(info, name)}"
                        f"({', '.join(arg_codes)})", ret)
            nested = info.nested.get(name)
            if nested is not None:
                return self.code_constructor(
                    nested.name, args, trailing, node,
                    generic_args=getattr(node, "generic_args", []))
            sv = info.static_vars.get(name)
            if sv is not None:
                self.error(f"static property '{name}' is not callable", node)
            if info.kind == "enum":
                case = info.enum_case(name)
                if case is not None:
                    return self._enum_case_call(info, case, args, node,
                                                type_args=type_args)
            ext0 = self.reg.extensions.get(type_name)
            if ext0 is not None and name in ext0.static_funcs:
                fi = ext0.static_funcs[name][0]
                arg_codes = self._bind_call_args(fi.params, fi.param_types,
                                                 args, trailing, node,
                                                 fi.generics)
                return (f"{mangle_type_name(type_name)}_{nim_ident(name)}"
                        f"({', '.join(arg_codes)})", fi.ret)
            self.error(f"type '{type_name}' has no static method '{name}'",
                       node)
        ext = self.reg.extensions.get(type_name)
        if ext is not None and name in ext.static_funcs:
            fi = ext.static_funcs[name][0]
            arg_codes = self._bind_call_args(fi.params, fi.param_types, args,
                                             trailing, node, fi.generics)
            return (f"{mangle_type_name(type_name)}_{nim_ident(name)}"
                    f"({', '.join(arg_codes)})", fi.ret)
        prim = self.prim_type_name(type_name)
        if prim is not None:
            return self.code_prim_static_call(prim, type_name, name, args,
                                              trailing, node)
        self.error(f"unknown type '{type_name}'", node)
        raise AssertionError

    def _type_arg_map(self, info: TypeInfo, type_args: list) -> dict:
        mapping = {}
        for (gname, _), arg in zip(info.generic_params, type_args):
            mapping[gname] = arg
        return mapping

    def _enum_case_call(self, info: TypeInfo, case: EnumCaseInfo, args: list,
                        node: Any, type_args: list | None = None):
        if info.is_error:
            self.error("error enum cases are only used with 'throw'", node)
        ret_ty = Ty.named(info.name, tuple(type_args or ()))
        generic_suffix = ""
        if type_args:
            generic_suffix = "[" + ", ".join(self.nim_type(t)
                                             for t in type_args) + "]"
        if not case.has_assoc:
            if args:
                self.error(f"enum case '{case.name}' takes no arguments", node)
            return f"{info.nim_name}.{nim_ident(case.name)}", ret_ty
        param_types = [fty for _, fty in case.assoc]
        arg_codes: list[str] = []
        for i, (label, fty) in enumerate(case.assoc):
            if i < len(args):
                code, got = self.gen_expr(args[i].expr, fty)
                arg_codes.append(self.coerce(code, got, fty, args[i].expr))
            else:
                self.error(f"missing argument '{label}' for enum case "
                           f"'{case.name}'", node)
        return (f"{info.nim_name}_{nim_ident(case.name)}{generic_suffix}"
                f"({', '.join(arg_codes)})", ret_ty)

    def code_call_value(self, fn_code: str, fn_ty: Ty, args: list,
                        trailing: Any, node: Any):
        if fn_ty.kind == "builtins":
            return self.code_builtin_free_call(fn_ty.name, args, trailing, node)
        if fn_ty.kind == "type":
            return self.code_constructor(fn_ty.name, args, trailing, node,
                                         generic_args=getattr(node, "generic_args", []),
                                         type_args=list(fn_ty.args))
        if fn_ty.kind == "func":
            name = fn_ty.name
            if name and name in self.local_func_decls:
                decl = self.local_func_decls[name]
                return self._local_func_call(decl, args, trailing, node)
            if name and name in self.reg.global_funcs:
                return self._free_func_call(name, args, trailing, node)
            # plain function value
            codes = []
            for i, a in enumerate(args):
                exp = fn_ty.params[i] if i < len(fn_ty.params) else None
                code, got = self.gen_expr(a.expr, exp)
                if exp is not None:
                    code = self.coerce(code, got, exp, a.expr)
                codes.append(code)
            return f"{self._wrap(fn_code)}({', '.join(codes)})", fn_ty.ret
        if fn_ty.kind == "unknown":
            codes = []
            for a in args:
                code, _ = self.gen_expr(a.expr, None)
                codes.append(code)
            return f"{self._wrap(fn_code)}({', '.join(codes)})", UNKNOWN
        self.error(f"value of type '{ty_to_str(fn_ty)}' is not callable", node)

    def _local_func_call(self, decl: A.FuncDecl, args: list, trailing: Any,
                         node: Any):
        param_types = []
        for p in decl.params:
            ty = self.reg.resolve_type(p.ty, self.generic_env)
            if getattr(p, "is_variadic", False):
                ty = Ty.array(ty)
            param_types.append(ty)
        params = [A.Param(label=p.label, name=p.name, ty=p.ty, default=p.default,
                          is_variadic=getattr(p, "is_variadic", False))
                  for p in decl.params]
        arg_codes = self._bind_call_args(params, param_types, args, trailing,
                                         node, decl.generic_params)
        ret = self.reg.resolve_type(decl.ret, self.generic_env) if decl.ret else VOID
        return (f"{nim_ident(decl.name)}({', '.join(arg_codes)})", ret)

    def _free_func_call(self, name: str, args: list, trailing: Any, node: Any):
        fis = self.reg.global_funcs.get(name, [])
        fi = self._select_overload(fis, args, trailing, node)
        arg_codes = self._bind_call_args(fi.params, fi.param_types, args,
                                         trailing, node, fi.generics)
        ret = substitute(fi.ret, self._last_generic_map) if fi.generics else fi.ret
        return (f"{nim_ident(name)}({', '.join(arg_codes)})", ret)

    def _select_overload(self, fis: list, args: list, trailing: Any,
                         node: Any) -> FuncInfo:
        n = len(args) + (1 if trailing is not None else 0)
        candidates = []
        for fi in fis:
            has_variadic = any(getattr(p, "is_variadic", False)
                               for p in fi.params)
            required = sum(1 for p in fi.params if p.default is None and
                           not getattr(p, "is_variadic", False))
            total = len(fi.params)
            if has_variadic:
                if n >= required:
                    candidates.append(fi)
            elif required <= n <= total:
                candidates.append(fi)
        if not candidates:
            if fis:
                return fis[0]
            self.error("no matching function found", node)
        if len(candidates) == 1:
            return candidates[0]
        arg_types: list[Ty] = []
        for arg in args:
            ty = self._infer_expr_type_quiet(arg.expr)
            arg_types.append(ty if ty is not None else UNKNOWN)
        if trailing is not None:
            arg_types.append(UNKNOWN)

        def score(fi: FuncInfo) -> float:
            total = 0.0
            labels = {p.label for p in fi.params if p.label is not None}
            labels |= {p.name for p in fi.params}
            for arg in args:
                if arg.label is not None:
                    if arg.label not in labels:
                        return -1e9
                    total += 2.0
            for i, aty in enumerate(arg_types):
                if i >= len(fi.param_types):
                    continue
                pty = fi.param_types[i]
                total += self._overload_match(pty, aty)
            return total

        best = max(candidates, key=score)
        if score(best) < 0:
            self.error("no overload matches the argument labels", node)
        return best

    def _overload_match(self, pty: Ty, aty: Ty) -> float:
        if pty.kind == "unknown" or aty.kind == "unknown":
            return 0.5
        if pty.kind == "generic":
            return 0.8
        if pty == aty:
            return 1.0
        if pty.is_optional and pty.inner == aty:
            return 0.9
        if pty.is_numeric and aty.is_numeric:
            return 0.8 if pty.kind == aty.kind else 0.6
        if pty.kind == "named" and aty.kind == "named":
            info = self.reg.types.get(aty.name)
            cur = info
            while cur is not None:
                if cur.name == pty.name:
                    return 0.7
                cur = cur.superclass
        if pty.kind in ("array", "dict", "set") and pty.kind == aty.kind:
            return 0.7
        return 0.0

    def _bind_call_args(self, params: list, param_types: list, args: list,
                        trailing: Any, node: Any, generics: list) -> list[str]:
        arglist = list(args)
        variadic = None
        for i, p in enumerate(params):
            if getattr(p, "is_variadic", False):
                variadic = i
                break
        if trailing is not None:
            # A trailing closure always binds to the last declared parameter
            # (Swift semantics), even when earlier parameters are omitted by
            # their default values.  Using the explicit label/name keeps the
            # positional argument scanner from binding the closure to a
            # preceding defaulted parameter.
            last = params[-1]
            trailing_label = last.label if last.label is not None \
                else last.name
            arglist = arglist + [A.CallArg(label=trailing_label, expr=trailing,
                                           line=trailing.line,
                                           col=trailing.col)]
        variadic_elem: Ty = UNKNOWN
        if variadic is not None and variadic < len(param_types):
            pty = param_types[variadic]
            variadic_elem = pty.elem if pty is not None and \
                pty.kind == "array" else UNKNOWN
        assigned: dict[int, str] = {}
        got_types: list = []  # list[(idx, got)]
        used = [False] * len(params)
        variadic_codes: list[str] = []
        variadic_started = False
        next_pos = 0
        generics_map: dict[str, Ty] = {}
        for arg in arglist:
            idx = None
            if arg.label is not None:
                if variadic is not None and not variadic_started and \
                        arg.label in (params[variadic].label,
                                      params[variadic].name):
                    idx = variadic
                elif variadic is not None and variadic_started:
                    # Only labeled parameters declared after the variadic one
                    # can appear here.
                    for i in range(variadic + 1, len(params)):
                        p = params[i]
                        if used[i]:
                            continue
                        if p.label == arg.label or p.name == arg.label:
                            idx = i
                            break
                    if idx is None:
                        self.error("unexpected argument label "
                                   f"'{arg.label}' (it follows a variadic "
                                   "parameter)", node)
                else:
                    for i, p in enumerate(params):
                        if used[i] or (variadic is not None and i == variadic):
                            continue
                        if p.label == arg.label or p.name == arg.label:
                            idx = i
                            break
                    if idx is None:
                        self.error(f"unexpected argument label '{arg.label}'",
                                   node)
            else:
                if variadic is not None:
                    if variadic_started:
                        idx = variadic
                    else:
                        while next_pos < variadic and used[next_pos]:
                            next_pos += 1
                        if next_pos < variadic:
                            idx = next_pos
                        else:
                            idx = variadic
                else:
                    while next_pos < len(params) and used[next_pos]:
                        next_pos += 1
                    if next_pos < len(params):
                        idx = next_pos
                    else:
                        self.error("too many arguments", node)
            if idx == variadic:
                variadic_started = True
                expected = variadic_elem if variadic_elem.kind != "unknown" \
                    else None
                code, got = self.gen_expr(arg.expr, expected)
                if expected is not None and not expected.is_void:
                    code = self.coerce(code, got, expected, arg.expr)
                variadic_codes.append(code)
                if variadic_elem.kind != "unknown":
                    self._unify_generics(variadic_elem, got, generics_map)
                continue
            used[idx] = True
            expected = param_types[idx] if idx < len(param_types) else None
            code, got = self.gen_expr(arg.expr, expected)
            if expected is not None and not expected.is_void:
                code = self.coerce(code, got, expected, arg.expr)
            assigned[idx] = code
            got_types.append((idx, got))
        # render the variadic argument (possibly empty)
        if variadic is not None:
            if variadic_codes:
                assigned[variadic] = "@[" + ", ".join(variadic_codes) + "]"
            elif variadic_elem.kind != "unknown":
                assigned[variadic] = (f"newSeq[{self.nim_type(variadic_elem)}]"
                                      "()")
            else:
                assigned[variadic] = "@[]"
        for idx, got in got_types:
            if idx < len(param_types):
                self._unify_generics(param_types[idx], got, generics_map)
        self._last_generic_map = generics_map
        # fill in defaults
        result: list[str] = []
        prefix_len = 0
        while prefix_len < len(params) and prefix_len in assigned:
            prefix_len += 1
        for i in range(prefix_len):
            result.append(assigned[i])
        for i in range(prefix_len, len(params)):
            if i in assigned:
                result.append(f"{params[i].name} = {assigned[i]}")
            else:
                if params[i].default is None:
                    self.error(f"missing argument for parameter "
                               f"'{params[i].name}'", node)
                code, _ = self.gen_expr(params[i].default,
                                        param_types[i] if i < len(param_types) else None)
                result.append(f"{params[i].name} = {code}")
        return result

    def _unify_generics(self, expected: Ty, got: Ty, mapping: dict) -> None:
        if expected.kind == "generic":
            if expected.name not in mapping and got.kind != "unknown":
                mapping[expected.name] = got
            return
        if got.kind == "unknown":
            return
        if expected.kind in ("array", "optional", "set", "range") and got.kind == expected.kind:
            self._unify_generics(expected.elem, got.elem, mapping)
        elif expected.kind == "dict" and got.kind == "dict":
            self._unify_generics(expected.key, got.key, mapping)
            self._unify_generics(expected.value, got.value, mapping)
        elif expected.kind == "named" and got.kind == "named" and \
                expected.name == got.name and expected.args and got.args:
            for e, g in zip(expected.args, got.args):
                self._unify_generics(e, g, mapping)

    def _render_args_simple(self, args: list) -> str:
        return ", ".join(c for (_, c, _) in args)

    def _wrap(self, code: str) -> str:
        code = code.strip()
        if not code:
            return code
        if code.startswith("(") and code.endswith(")"):
            return code
        if all(c.isalnum() or c in "_." for c in code):
            return code
        return f"({code})"

    # ------------------------------------------------------- constructors
    def code_constructor(self, type_name: str, args: list, trailing: Any,
                         node: Any, generic_args: list | None = None,
                         type_args: list | None = None):
        from .types import PRIM_KINDS
        resolved_generics: list = []
        if generic_args:
            resolved_generics = [self.reg.resolve_type(t, self.generic_env)
                                 for t in generic_args]
        elif type_args:
            resolved_generics = list(type_args)
        if type_name in ("String", "Character"):
            return self.code_builtin_type_construct(type_name, args, trailing,
                                                    node,
                                                    type_args=resolved_generics)
        if type_name in PRIM_KINDS:
            return self.code_prim_conversion(type_name, args, node)
        if type_name in ("Bool", "Array", "Dictionary", "Set", "Optional"):
            return self.code_builtin_type_construct(type_name, args, trailing,
                                                    node,
                                                    type_args=resolved_generics)
        info = self.reg.types.get(type_name)
        if info is None:
            # perhaps a function call through a value
            self.error(f"unknown type or function '{type_name}'", node)
        if info.kind == "protocol":
            self.error(f"cannot instantiate protocol '{type_name}'", node)
        if info.kind == "enum":
            if info.raw_type is not None and len(args) == 1 and \
                    args[0].label in ("rawValue", "rawValue"):
                code, got = self.gen_expr(args[0].expr, info.raw_type)
                code = self.coerce(code, got, info.raw_type, args[0].expr)
                return (f"fromRaw({info.nim_name}, {code})",
                        Ty.optional(Ty.named(type_name)))
            self.error(f"enum '{type_name}' cannot be constructed with "
                       f"arguments", node)
        # user struct / class constructor

        def generic_parts(gens: list) -> tuple[str, Ty, dict]:
            code = ""
            if gens:
                code = "[" + ", ".join(self.nim_type(t) for t in gens) + "]"
            ret = Ty.named(type_name, tuple(gens))
            tmap = self._type_arg_map(info, gens) if gens else {}
            return code, ret, tmap

        def infer_generics(gens: list) -> list:
            if gens or not info.is_generic:
                return gens
            mp = self._last_generic_map
            out = [mp.get(gname, UNKNOWN) for gname, _ in info.generic_params]
            if all(t.kind != "unknown" for t in out):
                return out
            return gens

        generic_codes, ret_ty, type_map = generic_parts(resolved_generics)
        inits = self.reg.find_inits(Ty.named(type_name,
                                             tuple(resolved_generics)))
        if inits:
            fi = self._select_overload(inits, args, trailing, node)
            param_types = fi.param_types
            arg_codes = self._bind_call_args(fi.params, param_types, args,
                                             trailing, node, fi.generics)
            resolved_generics = infer_generics(resolved_generics)
            generic_codes, ret_ty, type_map = generic_parts(resolved_generics)
            idx = inits.index(fi)
            suffix = "" if len(inits) == 1 else f"_{idx + 1}"
            call = (f"new{info.nim_name}{suffix}{generic_codes}"
                    f"({', '.join(arg_codes)})")
            if fi.failable:
                if fi.failable_mode == "!":
                    return f"({call}).get", ret_ty
                return call, Ty.optional(ret_ty)
            return call, ret_ty
        # synthesized memberwise initializer
        if info.kind == "class":
            fields: list = []
        else:
            fields = [f for f in info.fields if not f.is_static]
        params = [A.Param(label=f.name, name=f.name, ty=None, default=f.default)
                  for f in fields]
        param_types = [substitute(f.ty, type_map) for f in fields]
        arg_codes = self._bind_call_args(params, param_types, args, trailing,
                                         node, info.generic_params)
        resolved_generics = infer_generics(resolved_generics)
        generic_codes, ret_ty, type_map = generic_parts(resolved_generics)
        return (f"new{info.nim_name}{generic_codes}"
                f"({', '.join(arg_codes)})", ret_ty)

    def code_prim_conversion(self, type_name: str, args: list, node: Any):
        from .types import PRIM_KINDS
        kind = PRIM_KINDS[type_name]
        if not args:
            self.error(f"{type_name} needs an argument", node)
        arg = args[0].expr
        arg_code, arg_ty = self.gen_expr(arg, None)
        # failable initializers from strings
        if arg_ty.kind == "string" and kind in ("int", "int64", "float"):
            target = {"int": "swimToInt", "int64": "swimToInt64",
                      "float": "swimToDouble"}[kind]
            opt_ty = Ty.optional(Ty.prim(kind))
            return f"{target}({arg_code})", opt_ty
        if kind == "string":
            return f"swimStr({arg_code})", STRING
        if kind == "bool":
            if arg_ty.is_numeric:
                return f"({arg_code} != 0)", BOOL
            self.error("Bool(...) conversion is not supported for this type",
                       node)
        return f"{NIM_PRIM[kind]}({arg_code})", Ty.prim(kind)

    # -------------------------------------------------------------- super
    def gen_super_chain(self, steps: list, node: Any):
        if self.type_info is None or self.type_info.superclass is None:
            self.error("'super' used outside of a class with a superclass",
                       node)
        if not steps:
            self.error("'super' must be followed by a method call", node)
        step = steps[0]
        if step["kind"] != "method":
            self.error("'super' must be followed by a method call", node)
        name = step["name"]
        call = step["call"]
        if name == "init":
            return self._gen_super_init(call, node)
        cur: TypeInfo | None = self.type_info.superclass
        while cur is not None:
            fis = cur.methods.get(name, [])
            if fis:
                fi = self._select_overload(fis, call.args, call.trailing_closure,
                                           node)
                arg_codes = self._bind_call_args(
                    fi.params, fi.param_types, call.args,
                    call.trailing_closure, node, fi.generics)
                impl = self.impl_names.get(id(fi))
                if impl is None:
                    impl = nim_ident(name)
                args = ", ".join(["self"] + arg_codes)
                return f"{impl}({args})", fi.ret
            cur = cur.superclass
        self.error(f"superclass has no method '{name}'", node)

    def _gen_self_init(self, call: Any, node: Any):
        """Delegate from one initializer to another via ``self.init(...)``."""
        if self.type_info is None or not self.in_init:
            self.error("'self.init' can only be used inside an initializer",
                       node)
        inits = self.type_info.inits
        if not inits:
            self.error("type has no initializer to delegate to", node)
        fi = self._select_overload(inits, call.args, call.trailing_closure, node)
        arg_codes = self._bind_call_args(fi.params, fi.param_types,
                                         call.args, call.trailing_closure,
                                         node, fi.generics)
        suffix = "" if len(inits) == 1 else f"_{inits.index(fi) + 1}"
        args = ", ".join(["self"] + arg_codes)
        name = f"init{self.type_info.nim_name}{suffix}"
        if fi.failable:
            if not self.in_failable_init:
                self.error("delegating to a failable initializer requires a "
                           "failable initializer (init?)", node)
            return f"{name}({args})", BOOL
        return f"{name}({args})", VOID

    def _gen_super_init(self, call: Any, node: Any):
        base = self.type_info.superclass
        inits = self.reg.find_inits(Ty.named(base.name))
        if not inits:
            self.error("superclass has no initializer", node)
        fi = self._select_overload(inits, call.args, call.trailing_closure, node)
        arg_codes = self._bind_call_args(fi.params, fi.param_types,
                                         call.args, call.trailing_closure,
                                         node, fi.generics)
        suffix = "" if len(inits) == 1 else f"_{inits.index(fi) + 1}"
        args = ", ".join(["self"] + arg_codes)
        if fi.failable:
            if not self.in_failable_init:
                self.error("calling a failable superclass initializer "
                           "requires a failable initializer (init?)", node)
            return f"init{base.nim_name}{suffix}({args})", BOOL
        return f"init{base.nim_name}{suffix}({args})", VOID

    # ------------------------------------------------------------- operators
    def _gen_user_operator(self, op: str, fixity: str, exprs: list,
                           node: Any):
        """Call a user-declared operator function, if one matches."""
        fis = self.reg.find_operators(fixity, op)
        if not fis:
            return None
        args = [A.CallArg(expr=e, line=getattr(e, "line", 0),
                          col=getattr(e, "col", 0)) for e in exprs]
        arg_types = [self._infer_expr_type_quiet(e) for e in exprs]
        best = None
        best_score = -1.0
        for fi in fis:
            if len(fi.params) != len(exprs):
                continue
            score = 0.0
            compatible = True
            for i, aty in enumerate(arg_types):
                pty = fi.param_types[i] if i < len(fi.param_types) else UNKNOWN
                if aty is None or aty.kind == "unknown":
                    score += 0.5
                    continue
                match = self._overload_match(pty, aty)
                if match <= 0:
                    compatible = False
                    break
                score += match
            if compatible and score > best_score:
                best = fi
                best_score = score
        if best is None:
            return None
        arg_codes = self._bind_call_args(best.params, best.param_types, args,
                                         None, node, best.generics)
        ret = substitute(best.ret, self._last_generic_map) \
            if best.generics else best.ret
        return f"`{op}`({', '.join(arg_codes)})", ret

    def gen_postfix_unary(self, node: A.PostfixExpr):
        user = self._gen_user_operator(node.op, "postfix", [node.operand], node)
        if user is not None:
            return user
        self.error(f"no operator function for postfix '{node.op}'", node)

    def gen_binary(self, node: A.BinaryExpr, expected: Ty | None):
        op = node.op
        if self.reg.operators and op not in ASSIGN_OPS and \
                op not in ("&&", "||", "??", "...", "..<", "===", "!==") and \
                not (op in ("==", "!=") and
                     (isinstance(node.left, A.NilLit) or
                      isinstance(node.right, A.NilLit))):
            user = self._gen_user_operator(op, "infix",
                                           [node.left, node.right], node)
            if user is not None:
                return user
        if op in ("==", "!="):
            if isinstance(node.left, A.NilLit) or isinstance(node.right, A.NilLit):
                other = node.right if isinstance(node.left, A.NilLit) else node.left
                code, ty = self.gen_expr(other, None)
                if ty.is_optional:
                    return (f"({code}).is{'None' if op == '==' else 'Some'}",
                            BOOL)
                return f"({code}) {'==' if op == '==' else '!='} nil", BOOL
        if op == "??":
            lcode, lty = self.gen_expr(node.left, None)
            if lty.is_optional:
                inner = lty.inner
                rcode, rgot = self.gen_expr(node.right, inner)
                rcode = self.coerce(rcode, rgot, inner, node.right)
                return f"({lcode}).get({rcode})", inner
            self.error("left side of '??' must be an Optional", node)
        if op in ("&&", "||"):
            lcode, _ = self.gen_expr(node.left, BOOL)
            rcode, _ = self.gen_expr(node.right, BOOL)
            return (f"({lcode}) {'and' if op == '&&' else 'or'} ({rcode})",
                    BOOL)
        if op in ("...", "..<"):
            lcode, lty = self.gen_expr(node.left, None)
            rcode, rty = self.gen_expr(node.right, None)
            elem = lty if lty.kind != "unknown" else rty
            if elem.kind == "unknown":
                elem = INT
            return f"({lcode} {'..' if op == '...' else '..<'} {rcode})", \
                Ty(kind="range", name="closed" if op == "..." else "half",
                   args=(elem,))
        if op in ("===", "!=="):
            lcode, _ = self.gen_expr(node.left, None)
            rcode, _ = self.gen_expr(node.right, None)
            eq = f"cast[pointer]({lcode}) == cast[pointer]({rcode})"
            return (eq if op == "===" else f"not ({eq})"), BOOL
        lcode, lty = self.gen_expr(node.left, None)
        right_expected = lty if lty.is_numeric else None
        if lty.kind == "char" and isinstance(node.right, A.StringLit):
            right_expected = CHAR
        rcode, rty = self.gen_expr(node.right, right_expected)
        if rty.kind == "char" and isinstance(node.left, A.StringLit):
            lcode, lty = self.gen_expr(node.left, CHAR)
        # literal promotion
        if lty.is_float and isinstance(node.right, A.IntLit):
            rcode, rty = self.gen_expr(node.right, FLOAT)
        if rty.is_float and isinstance(node.left, A.IntLit):
            lcode, lty = self.gen_expr(node.left, FLOAT)
        cmp_ops = {"<", "<=", ">", ">=", "==", "!="}
        if op in cmp_ops:
            return f"({lcode} {op} {rcode})", BOOL
        if op in ("+", "-", "*", "/", "%"):
            int_operands = (lty.is_int or lty.kind == "unknown") and \
                           (rty.is_int or rty.kind == "unknown")
            if op == "/" and int_operands and not (lty.is_float or rty.is_float):
                return f"({lcode} div {rcode})", lty if lty.is_int else (rty if rty.is_int else INT)
            if op == "%" and int_operands:
                return f"({lcode} mod {rcode})", lty if lty.is_int else (rty if rty.is_int else INT)
            numeric = lty.is_numeric or rty.is_numeric
            if numeric:
                result = FLOAT if (lty.is_float or rty.is_float) else (
                    lty if lty.is_int else (rty if rty.is_int else INT))
                return f"({lcode} {op} {rcode})", result
            if op == "+" and (lty.kind == "string" or rty.kind == "string"):
                return f"({lcode} & {rcode})", STRING
            if op == "+" and lty.kind == "array" and rty.kind == "array":
                return f"({lcode} & {rcode})", lty
            if op == "+" and lty.kind == "array":
                return f"({lcode} & @[{rcode}])", lty
            return f"({lcode} {op} {rcode})", lty if lty.kind != "unknown" else rty
        mapped = {
            "&+": "+", "&-": "-", "&*": "*", "&": "and", "|": "or",
            "^": "xor", "<<": "shl", ">>": "shr", "~=": "==",
        }
        if op in mapped:
            return f"({lcode} {mapped[op]} {rcode})", \
                BOOL if op == "~=" else (lty if lty.kind != "unknown" else rty)
        self.error(f"unsupported operator '{op}'", node)
        raise AssertionError

    def gen_unary(self, node: A.UnaryExpr, expected: Ty | None):
        if self.reg.operators and node.op not in ("!", "-", "+", "~", "&"):
            user = self._gen_user_operator(node.op, "prefix", [node.operand],
                                           node)
            if user is not None:
                return user
        if node.op == "&":
            return self.gen_expr(node.operand, expected)
        code, ty = self.gen_expr(node.operand,
                                 expected if expected is not None and
                                 expected.is_numeric else None)
        if node.op == "!":
            return f"not ({code})", BOOL
        if node.op == "-":
            return f"-({code})", ty if ty.kind != "unknown" else (
                expected if expected is not None else INT)
        if node.op == "+":
            return code, ty
        if node.op == "~":
            return f"not ({code})", ty
        self.error(f"unsupported unary operator '{node.op}'", node)
        raise AssertionError

    def gen_ternary(self, node: A.TernaryExpr, expected: Ty | None):
        cond, _ = self.gen_expr(node.cond, BOOL)
        if isinstance(node.else_expr, A.NilLit) or \
                isinstance(node.then_expr, A.NilLit):
            if not isinstance(node.then_expr, A.NilLit):
                tcode, tty = self.gen_expr(node.then_expr, expected)
                if tty.kind != "unknown" and not tty.is_optional:
                    opt = make_optional(tty)
                    tcode = self.coerce(tcode, tty, opt, node.then_expr)
                    return (f"(if {cond}: {tcode} else: "
                            f"none({self.nim_type(tty, node)}))", opt)
            elif not isinstance(node.else_expr, A.NilLit):
                ecode, ety = self.gen_expr(node.else_expr, expected)
                if ety.kind != "unknown" and not ety.is_optional:
                    opt = make_optional(ety)
                    ecode = self.coerce(ecode, ety, opt, node.else_expr)
                    return (f"(if {cond}: none({self.nim_type(ety, node)}) "
                            f"else: {ecode})", opt)
        if expected is not None and expected.is_optional:
            tcode, tty = self.gen_expr(node.then_expr, expected)
            ecode, ety = self.gen_expr(node.else_expr, expected)
            tcode = self.coerce(tcode, tty, expected, node.then_expr)
            ecode = self.coerce(ecode, ety, expected, node.else_expr)
            return f"(if {cond}: {tcode} else: {ecode})", expected
        tcode, tty = self.gen_expr(node.then_expr, expected)
        ecode, ety = self.gen_expr(node.else_expr,
                                   tty if tty.kind != "unknown" else expected)
        result = tty
        if tty.kind == "unknown":
            result = ety
        if tty.is_optional or ety.is_optional:
            inner = unwrap_optional(tty if tty.is_optional else ety)
            result = make_optional(inner)
            tcode = self.coerce(tcode, tty, result, node.then_expr)
            ecode = self.coerce(ecode, ety, result, node.else_expr)
        elif tty.is_float and ety.is_int:
            ecode, ety = self.gen_expr(node.else_expr, FLOAT)
            result = FLOAT
        elif ety.is_float and tty.is_int:
            tcode, tty = self.gen_expr(node.then_expr, FLOAT)
            result = FLOAT
        return f"(if {cond}: {tcode} else: {ecode})", result

    # --------------------------------------------------------------- closures
    def gen_closure(self, node: A.ClosureExpr, expected: Ty | None):
        exp_params: tuple = ()
        exp_ret: Ty = UNKNOWN
        exp_is_func = expected is not None and expected.kind == "func"
        if exp_is_func:
            exp_params = expected.params
            exp_ret = expected.ret
        param_tys: list[Ty] = []
        param_names: list[str] = []
        if node.params:
            for i, p in enumerate(node.params):
                ty = self.reg.resolve_type(p.ty, self.generic_env) if p.ty else None
                if ty is None:
                    ty = exp_params[i] if i < len(exp_params) else UNKNOWN
                if ty.kind == "unknown":
                    self.error("cannot infer the type of closure parameter "
                               f"'{p.name}'; add a type annotation", p)
                param_tys.append(ty)
                param_names.append(p.name)
        else:
            if node.has_signature:
                param_tys = []
                param_names = []
            elif not exp_is_func:
                self.error("cannot infer closure parameter types here; add "
                           "type annotations", node)
            else:
                param_tys = list(exp_params)
                param_names = [f"${i}" for i in range(len(param_tys))]
        ret = exp_ret
        if node.ret_type is not None:
            ret = self.reg.resolve_type(node.ret_type, self.generic_env)
        elif ret.kind in ("unknown", "generic"):
            ret = self._infer_closure_ret(node, param_names, param_tys)
        if ret.kind == "unknown":
            ret = VOID
        nim_names = [
            (f"swArg{i}" if name.startswith("$") else nim_ident(name))
            for i, name in enumerate(param_names)
        ]
        saved = self._save_ctx()
        self.push_scope()
        try:
            for name, nim_name, ty in zip(param_names, nim_names, param_tys):
                self.declare(name, nim_name, ty, mutable=True, kind="param")
            self.ret_ty = ret
            if node.implicit_return:
                expected_ret = None if ret.kind in ("unknown", "generic") else ret
                code, got = self.gen_expr(node.body[0].expr, expected_ret)
                if ret.kind in ("unknown", "generic"):
                    ret = got
                self.ret_ty = ret
                code = self.coerce(code, got, ret, node.body[0].expr)
                sig = self._closure_signature(nim_names, param_tys, ret)
                return f"{sig} = {code}", Ty.func(tuple(param_tys), ret)
            if ret.kind in ("unknown", "generic"):
                ret = VOID
            self.ret_ty = ret
            sig = self._closure_signature(nim_names, param_tys, ret)
            lines = self._capture(lambda: self.gen_block(node.body, new_scope=False))
            body = "\n".join(("  " + ln if ln else "") for ln in lines)
            code = f"{sig} =\n{body}" if body else sig + " = discard"
            return code, Ty.func(tuple(param_tys), ret)
        finally:
            self.pop_scope()
            self._restore_ctx(saved)

    def _closure_signature(self, names: list[str], param_tys: list[Ty],
                           ret: Ty) -> str:
        params = ", ".join(f"{nim_ident(n)}: {self.nim_type(t)}"
                           for n, t in zip(names, param_tys))
        if ret.is_void or ret.kind == "unknown":
            return f"proc ({params}) {{.closure.}}"
        return f"proc ({params}): {self.nim_type(ret)} {{.closure.}}"

    def _infer_closure_ret(self, node: A.ClosureExpr, names: list,
                           param_tys: list) -> Ty:
        if node.ret_type is not None:
            return self.reg.resolve_type(node.ret_type, self.generic_env)
        # dry-run the body with a return-type collector
        saved_ret = self.ret_ty
        saved_collector = self.return_collector
        self.push_scope()
        collected: list[Ty] = []
        try:
            for i, (name, pty) in enumerate(zip(names, param_tys)):
                nim_name = f"swArg{i}" if name.startswith("$") else nim_ident(name)
                self.declare(name, nim_name, pty, mutable=True, kind="param")
            self.ret_ty = UNKNOWN
            self.return_collector = collected
            try:
                self._capture(lambda: self.gen_block(node.body, new_scope=False))
            except SwimError:
                pass
        finally:
            self.pop_scope()
            self.ret_ty = saved_ret
            self.return_collector = saved_collector
        for ty in collected:
            if ty.kind != "unknown" and not ty.is_void:
                return ty
        # fall back to a shallow scan
        exprs = []
        for stmt in node.body:
            if isinstance(stmt, A.ReturnStmt) and stmt.expr is not None:
                exprs.append(stmt.expr)
        if node.implicit_return and node.body and \
                isinstance(node.body[0], A.ExprStmt):
            exprs.append(node.body[0].expr)
        self.push_scope()
        try:
            for i, (name, pty) in enumerate(zip(names, param_tys)):
                nim_name = f"swArg{i}" if name.startswith("$") else nim_ident(name)
                self.declare(name, nim_name, pty, mutable=True, kind="param")
            for expr in exprs:
                ty = self._infer_expr_type_quiet(expr)
                if ty is not None and ty.kind != "unknown":
                    return ty
        finally:
            self.pop_scope()
        return UNKNOWN

    def _has_explicit_return(self, node: A.ClosureExpr) -> bool:
        def walk(n: Any) -> bool:
            if isinstance(n, A.ReturnStmt):
                return True
            if isinstance(n, (A.ClosureExpr, A.FuncDecl)):
                return False
            if isinstance(n, A.Node):
                for key, value in vars(n).items():
                    if key in ("line", "col"):
                        continue
                    if walk(value):
                        return True
            elif isinstance(n, list):
                for item in n:
                    if walk(item):
                        return True
            return False

        return walk(node.body)

    # --------------------------------------------------------------- literals
    def gen_array_literal(self, node: A.ArrayLit, expected: Ty | None):
        exp_elem = None
        exp_ty = expected
        if exp_ty is not None and exp_ty.is_optional:
            exp_ty = exp_ty.inner
        set_mode = exp_ty is not None and exp_ty.kind == "set"
        if set_mode:
            elem_ty = exp_ty.elem
            if not node.items:
                return (f"initHashSet[{self.nim_type(elem_ty, node)}]()",
                        Ty.set(elem_ty))
            pieces = []
            for item in node.items:
                code, got = self.gen_expr(item, elem_ty)
                pieces.append(self.coerce(code, got, elem_ty, item))
            return (f"toHashSet(@[{', '.join(pieces)}])", Ty.set(elem_ty))
        if exp_ty is not None and exp_ty.kind == "array":
            exp_elem = exp_ty.elem
            if exp_elem.kind == "unknown":
                exp_elem = None
        if not node.items:
            if exp_elem is not None:
                return f"newSeq[{self.nim_type(exp_elem, node)}]()", \
                    Ty.array(exp_elem)
            self.error("cannot infer the element type of an empty array "
                       "literal; add a type annotation", node)
        if exp_elem is None:
            first_code, first_ty = self.gen_expr(node.items[0], None)
            if first_ty.kind == "unknown":
                self.error("cannot infer the element type of the array "
                           "literal; add a type annotation", node)
            exp_elem = first_ty
        pieces = []
        for item in node.items:
            code, got = self.gen_expr(item, exp_elem)
            code = self.coerce(code, got, exp_elem, item)
            pieces.append(code)
        return "@[" + ", ".join(pieces) + "]", Ty.array(exp_elem)

    def gen_dict_literal(self, node: A.DictLit, expected: Ty | None):
        exp_ty = expected
        if exp_ty is not None and exp_ty.is_optional:
            exp_ty = exp_ty.inner
        exp_key = exp_val = None
        if exp_ty is not None and exp_ty.kind == "dict":
            exp_key, exp_val = exp_ty.key, exp_ty.value
            if exp_key.kind == "unknown":
                exp_key = None
            if exp_val.kind == "unknown":
                exp_val = None
        if not node.pairs:
            if exp_key is None or exp_val is None:
                self.error("cannot infer the key/value types of an empty "
                           "dictionary literal; add a type annotation", node)
            return (f"initTable[{self.nim_type(exp_key, node)}, "
                    f"{self.nim_type(exp_val, node)}]()", Ty.dict(exp_key, exp_val))
        if exp_key is None or exp_val is None:
            kcode, kty = self.gen_expr(node.pairs[0][0], None)
            vcode, vty = self.gen_expr(node.pairs[0][1], None)
            if exp_key is None:
                exp_key = kty
            if exp_val is None:
                exp_val = vty
            if exp_key.kind == "unknown" or exp_val.kind == "unknown":
                self.error("cannot infer the dictionary literal type; add a "
                           "type annotation", node)
        pieces = []
        for k, v in node.pairs:
            kcode, kty = self.gen_expr(k, exp_key)
            kcode = self.coerce(kcode, kty, exp_key, k)
            vcode, vty = self.gen_expr(v, exp_val)
            vcode = self.coerce(vcode, vty, exp_val, v)
            pieces.append(f"{kcode}: {vcode}")
        return "{" + ", ".join(pieces) + "}.toTable", Ty.dict(exp_key, exp_val)

    def gen_tuple_literal(self, node: A.TupleLit, expected: Ty | None):
        exp_types: tuple = ()
        exp_labels: tuple = ()
        if expected is not None and expected.kind == "tuple" and \
                len(expected.args) == len(node.items):
            exp_types = expected.args
            exp_labels = expected.labels
        tys: list[Ty] = []
        codes: list[str] = []
        labels: list[str] = []
        for i, (label, expr) in enumerate(node.items):
            exp = exp_types[i] if i < len(exp_types) else None
            code, got = self.gen_expr(expr, exp)
            if exp is not None:
                code = self.coerce(code, got, exp, expr)
                tys.append(exp)
            else:
                tys.append(got)
            codes.append(code)
            labels.append(label or (exp_labels[i] if i < len(exp_labels)
                                    and exp_labels[i] else ""))
        if any(labels):
            pieces = ", ".join(
                f"{nim_ident(label)}: {code}" if label else code
                for label, code in zip(labels, codes)
            )
            return f"({pieces})", Ty.tuple(tuple(tys), tuple(labels))
        return "(" + ", ".join(codes) + ")", Ty.tuple(tuple(tys))

    # ------------------------------------------------------------ casts, try
    def gen_cast(self, node: A.CastExpr, expected: Ty | None):
        target = self.reg.resolve_type(node.ty, self.generic_env)
        code, got = self.gen_expr(node.expr, None)
        if node.mode == "as":
            if got.kind == "named" and got.name == target.name:
                return code, target
            if got.kind == "unknown" or target.kind == "unknown":
                return code, target
            if got.is_numeric and target.is_numeric:
                return f"{self.nim_type(target)}({code})", target
            if got.kind == "named" and target.kind == "named" and \
                    self._is_subclass(got, target):
                return code, target
            if got.kind == "named" and target.kind == "named":
                return code, target
            self.error(f"cannot convert '{ty_to_str(got)}' to "
                       f"'{ty_to_str(target)}' with 'as'", node)
        if node.mode == "as!":
            if target.kind == "named" and got.kind == "named":
                return f"{self.nim_type(target)}({code})", target
            if got.is_numeric and target.is_numeric:
                return f"{self.nim_type(target)}({code})", target
            self.error(f"cannot convert '{ty_to_str(got)}' to "
                       f"'{ty_to_str(target)}' with 'as!'", node)
        # as?
        if target.kind == "named" and got.kind == "named":
            if self._is_subclass(got, target) or self._is_subclass(target, got):
                return (f"swimAsOpt({self.nim_type(target)}, {code})",
                        Ty.optional(target))
            return f"none({self.nim_type(target)})", Ty.optional(target)
        if got.is_numeric and target.is_numeric:
            return f"some({self.nim_type(target)}({code}))", Ty.optional(target)
        if got.kind == "unknown":
            return f"swimAsOpt({self.nim_type(target)}, {code})", \
                Ty.optional(target)
        self.error(f"cannot convert '{ty_to_str(got)}' to "
                   f"'{ty_to_str(target)}' with 'as?'", node)
        raise AssertionError

    def _is_subclass(self, sub: Ty, base: Ty) -> bool:
        if sub.kind != "named" or base.kind != "named":
            return False
        if sub.name == base.name:
            return True
        info = self.reg.types.get(sub.name)
        while info is not None:
            if info.superclass is not None and info.superclass.name == base.name:
                return True
            info = info.superclass
        return False

    def gen_type_check(self, node: A.TypeCheckExpr, expected: Ty | None):
        target = self.reg.resolve_type(node.ty, self.generic_env)
        code, got = self.gen_expr(node.expr, None)
        if target.kind == "named" and got.kind == "named":
            return f"({code} of {self.nim_type(target)})", BOOL
        if target.kind == "named":
            return f"({code} of {self.nim_type(target)})", BOOL
        self.error("'is' checks are only supported for class types and "
                   "error types", node)

    def gen_try(self, node: A.TryExpr, expected: Ty | None):
        if node.mode == "try":
            return self.gen_expr(node.expr, expected)
        code, ty = self.gen_expr(node.expr, expected)
        if node.mode == "try!":
            return code, ty
        if ty.kind == "unknown":
            self.error("cannot infer the type of 'try?' expression", node)
        inner = self.nim_type(ty, node)
        return (f"(try: some({code}) except CatchableError: none({inner}))",
                Ty.optional(ty))

    def gen_case_ref(self, node: A.CaseRefExpr, expected: Ty | None):
        base_ty = expected
        if base_ty is not None and base_ty.is_optional:
            base_ty = base_ty.inner
        if base_ty is None or base_ty.kind != "named":
            self.error(f"cannot infer the enum type for '.{node.name}'; add "
                       "a type annotation", node)
        info = self.reg.type_info(base_ty)
        if info is None or info.kind != "enum":
            self.error(f"type '{ty_to_str(base_ty)}' is not an enum", node)
        case = info.enum_case(node.name)
        if case is None:
            self.error(f"enum '{info.name}' has no case '{node.name}'", node)
        if case.has_assoc:
            if not node.args:
                self.error(f"enum case '{node.name}' needs arguments", node)
            return self._enum_case_call(info, case, node.args, node)
        if node.args:
            self.error(f"enum case '{node.name}' takes no arguments", node)
        if any(c.has_assoc for c in info.enum_cases):
            value = f"{info.nim_name}(kind: {info.nim_name}Kind." \
                    f"{nim_ident(node.name)})"
        else:
            value = f"{info.nim_name}.{nim_ident(node.name)}"
        return value, Ty.named(info.name)

    # --------------------------------------------------------------- coercion
    def coerce(self, code: str, got: Ty | None, want: Ty | None,
               node: Any) -> str:
        if want is None or got is None:
            return code
        if want.kind == "unknown" or got.kind == "unknown":
            return code
        if want.is_void:
            return code
        if want.is_optional:
            if isinstance(node, A.NilLit):
                return f"none({self.nim_type(want.inner, node)})"
            want_levels = 0
            w: Ty = want
            while w.is_optional:
                want_levels += 1
                w = w.inner
            got_levels = 0
            g: Ty = got
            while g.is_optional:
                got_levels += 1
                g = g.inner
            extra = want_levels - got_levels
            if extra > 0:
                return ("some(" * extra) + code + (")" * extra)
            return code
        if not want.is_optional and got.is_optional:
            self.error("optional value used where a non-optional "
                       f"'{ty_to_str(want)}' is expected; force-unwrap with "
                       "'!' or unwrap with 'if let'/'guard let'", node)
        if want.kind == "char" and got.kind == "string":
            self.error("a String cannot be used as a Character", node)
        if got.kind == "string" and (want.is_numeric or want.kind == "bool"):
            self.error(f"cannot implicitly convert 'String' to "
                       f"'{ty_to_str(want)}'; use an explicit conversion "
                       f"such as {want.kind.capitalize()}(...)", node)
        if want.kind == "string" and (got.is_numeric or got.kind == "bool"):
            self.error("cannot implicitly convert '" + ty_to_str(got) +
                       "' to 'String'; use String(...)", node)
        if want.is_float and got.is_int:
            if isinstance(node, (A.IntLit, A.UnaryExpr)) or \
                    (isinstance(node, A.UnaryExpr) and isinstance(node.operand, A.IntLit)):
                return code
            self.error(f"cannot implicitly convert '{ty_to_str(got)}' to "
                       f"'{ty_to_str(want)}'; use "
                       f"'{want.kind.capitalize()}(...)'", node)
        return code

    # ===================================================== generic constraints
    def _generic_protocols(self, ty: Ty) -> list:
        out: list = []
        for c in self.generic_constraints.get(ty.name, []):
            info = self.reg.types.get(c)
            if info is not None and info.kind == "protocol":
                out.append(info)
        return out

    def _protocol_chain(self, info: TypeInfo) -> list:
        out = [info]
        for inherited in getattr(info.decl, "inherits", []) or []:
            if isinstance(inherited, A.NamedType):
                parent = self.reg.types.get(inherited.name)
                if parent is not None and parent.kind == "protocol":
                    out.extend(self._protocol_chain(parent))
        return out

    def _generic_member(self, ty: Ty, name: str):
        for proto in self._generic_protocols(ty):
            for pinfo in self._protocol_chain(proto):
                for member in getattr(pinfo.decl, "members", []):
                    if isinstance(member, A.VarDecl) and member.name == name:
                        mty = self.reg.resolve_type(member.ty, {})
                        return mty, "property"
                    if isinstance(member, A.FuncDecl) and member.name == name \
                            and not member.params:
                        ret = (self.reg.resolve_type(member.ret, {})
                               if member.ret else VOID)
                        return ret, "method"
        return None

    def _generic_method(self, ty: Ty, name: str):
        for proto in self._generic_protocols(ty):
            for pinfo in self._protocol_chain(proto):
                for member in getattr(pinfo.decl, "members", []):
                    if isinstance(member, A.FuncDecl) and member.name == name:
                        params = []
                        ptypes = []
                        for p in member.params:
                            pty = self.reg.resolve_type(p.ty, {})
                            ptypes.append(pty)
                            params.append(A.Param(label=p.label, name=p.name,
                                                  ty=p.ty, default=None))
                        ret = (self.reg.resolve_type(member.ret, {})
                               if member.ret else VOID)
                        return params, ptypes, ret
        return None

    # ============================================================ built-in API
    def _arg(self, args: list, index: int = 0, label: str | None = None):
        if label is not None:
            for a in args:
                if a.label == label:
                    return a.expr
        if index < len(args):
            return args[index].expr
        return None

    def _get_closure(self, args: list, trailing: Any):
        if trailing is not None:
            return trailing
        if args and isinstance(args[-1].expr, A.ClosureExpr):
            return args[-1].expr
        return None

    def _has_label(self, args: list, label: str) -> bool:
        return any(a.label == label for a in args)

    def code_builtin_property(self, base_code: str, base_ty: Ty, name: str,
                              node: Any):
        k = base_ty.kind
        if name == "description":
            return f"swimStr({base_code})", STRING
        if k == "array":
            if name == "count":
                return f"count({base_code})", INT
            if name == "isEmpty":
                return f"isEmpty({base_code})", BOOL
            if name == "first":
                return f"firstOpt({base_code})", Ty.optional(base_ty.elem)
            if name == "last":
                return f"lastOpt({base_code})", Ty.optional(base_ty.elem)
            if name == "indices":
                return f"(0 ..< count({base_code}))", Ty.range(INT)
        if k == "string":
            if name == "count":
                return f"count({base_code})", INT
            if name == "isEmpty":
                return f"isEmpty({base_code})", BOOL
            if name == "first":
                return f"firstOpt({base_code})", Ty.optional(CHAR)
            if name == "last":
                return f"lastOpt({base_code})", Ty.optional(CHAR)
            if name == "indices":
                return f"(0 ..< count({base_code}))", Ty.range(INT)
        if k == "dict":
            if name == "count":
                return f"count({base_code})", INT
            if name == "isEmpty":
                return f"isEmpty({base_code})", BOOL
            if name == "keys":
                return f"keysSeq({base_code})", Ty.array(base_ty.key)
            if name == "values":
                return f"valuesSeq({base_code})", Ty.array(base_ty.value)
        if k == "set":
            if name == "count":
                return f"count({base_code})", INT
            if name == "isEmpty":
                return f"isEmpty({base_code})", BOOL
        if k in INT_KINDS or k in FLOAT_KINDS:
            if name == "description":
                return f"swimStr({base_code})", STRING
            if name in ("isNaN", "isInfinite", "isFinite"):
                if base_ty.is_float:
                    return f"{name}({base_code})", BOOL
                return None
            if name == "signum":
                return f"signum({base_code})", base_ty
        if k == "char":
            if name in ("isNumber", "isLetter", "isWhitespace", "isUppercase",
                        "isLowercase"):
                return f"{name}({base_code})", BOOL
            if name == "wholeNumberValue":
                return f"wholeNumberValue({base_code})", Ty.optional(INT)
            if name == "asciiValue":
                return f"asciiValue({base_code})", Ty.optional(INT)
            if name == "description":
                return f"swimStr({base_code})", STRING
        return None

    def code_builtin_method(self, recv_code: str, recv_ty: Ty, name: str,
                            args: list, trailing: Any, node: Any):
        if recv_ty.kind == "range":
            elem = recv_ty.elem
            recv_ty = Ty.array(elem)
            recv_code = f"toSeq({recv_code})"
        hof = self._try_hof(recv_code, recv_ty, name, args, trailing, node)
        if hof is not None:
            return hof
        k = recv_ty.kind
        recv = self._wrap(recv_code)
        if k == "array":
            res = self._array_method(recv, recv_ty, name, args, trailing, node)
            if res is not None:
                return res
        if k == "string":
            res = self._string_method(recv, name, args, trailing, node)
            if res is not None:
                return res
        if k == "char":
            if name == "uppercased":
                return f"uppercased({recv})", STRING
            if name == "lowercased":
                return f"lowercased({recv})", STRING
            if name == "description":
                return f"swimStr({recv})", STRING
        if k == "dict":
            res = self._dict_method(recv, recv_ty, name, args, trailing, node)
            if res is not None:
                return res
        if k == "set":
            res = self._set_method(recv, recv_ty, name, args, node)
            if res is not None:
                return res
        if k in INT_KINDS or k in FLOAT_KINDS:
            res = self._numeric_method(recv, recv_ty, name, args, node)
            if res is not None:
                return res
        if k == "optional":
            res = self._optional_method(recv, recv_ty, name, args, trailing, node)
            if res is not None:
                return res
        return None

    # -------------------------------------------------------------- HOFs
    def _try_hof(self, recv_code: str, recv_ty: Ty, name: str, args: list,
                 trailing: Any, node: Any):
        recv = self._wrap(recv_code)
        elem_ty = None
        if recv_ty.kind in ("array", "string", "set", "range"):
            elem_ty = self._elem_type(recv_ty, node)
        closure = self._get_closure(args, trailing)
        if name == "map" and closure is not None and recv_ty.kind in ("array", "string"):
            return self._hof_simple(recv, recv_ty, elem_ty, closure, name, node)
        if name == "filter" and closure is not None and recv_ty.kind in ("array", "string"):
            return self._hof_simple(recv, recv_ty, elem_ty, closure, name, node)
        if name == "forEach" and closure is not None and recv_ty.kind in ("array", "string"):
            return self._hof_simple(recv, recv_ty, elem_ty, closure, name, node)
        if name == "allSatisfy" and closure is not None:
            return self._hof_simple(recv, recv_ty, elem_ty, closure, name, node)
        if name == "contains" and closure is not None:
            return self._hof_simple(recv, recv_ty, elem_ty, closure, "any", node)
        if name == "first" and closure is not None:
            return self._hof_simple(recv, recv_ty, elem_ty, closure, "firstWhere",
                                    node)
        if name == "last" and closure is not None:
            return self._hof_simple(recv, recv_ty, elem_ty, closure, "lastWhere",
                                    node)
        if name == "firstIndex" and closure is not None:
            return self._hof_simple(recv, recv_ty, elem_ty, closure,
                                    "firstIndexWhere", node)
        if name == "map" and closure is not None and \
                recv_ty.kind == "set":
            return self._hof_simple(f"toSeq({recv})",
                                    Ty.array(recv_ty.elem), recv_ty.elem,
                                    closure, name, node)
        if name == "filter" and closure is not None and \
                recv_ty.kind == "set":
            try:
                code, _, ok = self._gen_it_body(closure, ["it"],
                                                recv_ty.elem, BOOL)
            except _ClosureFallback:
                ok = False
            if ok:
                return f"{recv}.swimSetFilterIt({code})", recv_ty
            expr_ty = Ty.func((recv_ty.elem,), BOOL)
            proc_code, _ = self.gen_closure(closure, expr_ty)
            return f"swimSetFilter({recv}, {proc_code})", recv_ty
        if name == "sorted" and (closure is not None or
                                 self._has_label(args, "by")):
            if recv_ty.kind == "set":
                elem_ty = recv_ty.elem
                return self._hof_sorted(f"toSeq({recv})", Ty.array(elem_ty),
                                        elem_ty, closure, node)
            if recv_ty.kind == "dict":
                elem_ty = Ty.tuple((recv_ty.key, recv_ty.value),
                                   ("key", "value"))
                return self._hof_sorted(f"dictPairs({recv})",
                                        Ty.array(elem_ty), elem_ty, closure,
                                        node)
            return self._hof_sorted(recv, recv_ty, elem_ty, closure, node)
        if name == "reduce" and closure is not None:
            return self._hof_reduce(recv, recv_ty, elem_ty, args, closure, node)
        if name == "compactMap" and closure is not None:
            return self._hof_compact_map(recv, recv_ty, elem_ty, closure, node)
        if name == "flatMap" and closure is not None and \
                recv_ty.kind in ("array", "string"):
            return self._hof_flat_map(recv, recv_ty, elem_ty, closure, node)
        if name in ("min", "max") and closure is not None and \
                recv_ty.kind == "array":
            return self._hof_minmax(recv, recv_ty, elem_ty, closure, node,
                                    name)
        if name == "sort":
            if closure is None:
                return f"sort({recv})", VOID
            try:
                code, _, ok = self._gen_it_body(closure, ["a", "b"], elem_ty,
                                                BOOL,
                                                param_tys=[elem_ty, elem_ty])
            except _ClosureFallback:
                ok = False
            if ok:
                return f"swimSortByIt({recv}, {code})", VOID
            expr_ty = Ty.func((elem_ty, elem_ty), BOOL)
            proc_code, _ = self.gen_closure(closure, expr_ty)
            return f"swimSortByImpl({recv}, {proc_code})", VOID
        return None

    def _hof_simple(self, recv: str, recv_ty: Ty, elem_ty: Ty, closure: A.ClosureExpr,
                    kind: str, node: Any):
        body_expected = BOOL if kind in ("filter", "any", "allSatisfy",
                                         "firstWhere", "lastWhere",
                                         "firstIndexWhere") else None
        template_names = {
            "map": "mapIt", "filter": "filterIt", "forEach": "forEachIt",
            "allSatisfy": "allIt", "any": "anyIt",
            "firstWhere": "firstWhereIt", "lastWhere": "lastWhereIt",
            "firstIndexWhere": "firstIndexWhereIt",
        }
        try:
            code, body_ty, ok = self._gen_it_body(closure, ["it"], elem_ty,
                                                  body_expected)
        except _ClosureFallback:
            ok = False
        if ok:
            tmpl = template_names[kind]
            if kind == "map":
                return f"{recv}.{tmpl}({code})", Ty.array(body_ty)
            if kind == "filter":
                return f"{recv}.{tmpl}({code})", recv_ty
            if kind == "forEach":
                return f"{recv}.{tmpl}({code})", VOID
            if kind == "allSatisfy" or kind == "any":
                return f"{recv}.{tmpl}({code})", BOOL
            if kind in ("firstWhere", "lastWhere"):
                return f"{recv}.{tmpl}({code})", Ty.optional(elem_ty)
            if kind == "firstIndexWhere":
                return f"{recv}.{tmpl}({code})", Ty.optional(INT)
        # fallback: typed closure proc
        expr_ty = Ty.func((elem_ty,), UNKNOWN)
        proc_code, proc_ty = self.gen_closure(closure, expr_ty)
        if kind == "map":
            return f"map({recv}, {proc_code})", Ty.array(proc_ty.ret)
        if kind == "filter":
            return f"filter({recv}, {proc_code})", recv_ty
        if kind == "forEach":
            return f"map({recv}, {proc_code})", VOID
        if kind == "allSatisfy":
            return f"all({recv}, {proc_code})", BOOL
        if kind == "any":
            return f"any({recv}, {proc_code})", BOOL
        if kind == "firstWhere":
            return f"firstWhereIt({recv}, true)", Ty.optional(elem_ty)
        if kind == "firstIndexWhere":
            return f"firstIndexWhereIt({recv}, true)", Ty.optional(INT)
        return f"lastWhereIt({recv}, true)", Ty.optional(elem_ty)

    def _gen_it_body(self, closure: A.ClosureExpr, names: list,
                     param_ty: Ty | None = None,
                     body_expected: Ty | None = None,
                     param_tys: list | None = None):
        saved = self._save_ctx()
        self.push_scope()
        ptypes = list(param_tys) if param_tys is not None else [
            param_ty if i == 0 and param_ty is not None else UNKNOWN
            for i in range(len(names))
        ]
        try:
            if closure.params:
                for i, p in enumerate(closure.params):
                    nm = names[i] if i < len(names) else f"swArg{i}"
                    ty = self.reg.resolve_type(p.ty, self.generic_env) if p.ty else (
                        ptypes[i] if i < len(ptypes) else UNKNOWN)
                    self.declare(p.name, nm, ty, mutable=True, kind="param")
            else:
                for i, nm in enumerate(names):
                    self.declare(f"${i}", nm,
                                 ptypes[i] if i < len(ptypes) else UNKNOWN,
                                 mutable=True, kind="param")
            if self._has_explicit_return(closure):
                raise _ClosureFallback()
            if closure.implicit_return:
                code, ty = self.gen_expr(closure.body[0].expr, body_expected)
                if body_expected is not None:
                    code = self.coerce(code, ty, body_expected, closure.body[0].expr)
                    ty = body_expected
                return code, ty, True
            body = closure.body
            if not body:
                return "discard", VOID, True
            last = body[-1]
            if not isinstance(last, A.ExprStmt):
                raise _ClosureFallback()
            lines = self._capture(
                lambda: self.gen_block(body[:-1], new_scope=False))
            last_code, last_ty = self.gen_expr(last.expr, body_expected)
            if body_expected is not None:
                last_code = self.coerce(last_code, last_ty, body_expected,
                                        last.expr)
                last_ty = body_expected
            if not lines:
                return last_code, last_ty, True
            indent = "\n".join(("  " + ln if ln else "") for ln in lines)
            return f"block:\n{indent}\n  {last_code}", last_ty, True
        finally:
            self.pop_scope()
            self._restore_ctx(saved)

    def _hof_sorted(self, recv: str, recv_ty: Ty, elem_ty: Ty,
                    closure: A.ClosureExpr | None, node: Any):
        if closure is None:
            return f"sorted({recv})", recv_ty
        try:
            code, _, ok = self._gen_it_body(closure, ["a", "b"], elem_ty, BOOL,
                                            param_tys=[elem_ty, elem_ty])
        except _ClosureFallback:
            ok = False
        if ok:
            return f"swimSortedByIt({recv}, {code})", recv_ty
        expr_ty = Ty.func((elem_ty, elem_ty), UNKNOWN)
        proc_code, _ = self.gen_closure(closure, expr_ty)
        return f"swimSortedByImpl({recv}, {proc_code})", recv_ty

    def _hof_reduce(self, recv: str, recv_ty: Ty, elem_ty: Ty, args: list,
                    closure: A.ClosureExpr, node: Any):
        initial = self._arg(args, 0)
        if initial is None:
            self.error("reduce needs an initial value", node)
        init_expected = elem_ty if elem_ty.kind in FLOAT_KINDS else None
        icode, ity = self.gen_expr(initial, init_expected)
        if isinstance(initial, A.IntLit) and elem_ty.kind in FLOAT_KINDS:
            icode = icode + ".0" if "." not in icode else icode
            ity = elem_ty
        try:
            code, _, ok = self._gen_it_body(closure, ["a", "b"], elem_ty, None,
                                            param_tys=[ity, elem_ty])
        except _ClosureFallback:
            ok = False
        if ok:
            return f"foldl({recv}, {code}, {icode})", ity
        expr_ty = Ty.func((ity, elem_ty), UNKNOWN)
        proc_code, _ = self.gen_closure(closure, expr_ty)
        return f"foldl({recv}, {proc_code}, {icode})", ity

    def _hof_compact_map(self, recv: str, recv_ty: Ty, elem_ty: Ty,
                         closure: A.ClosureExpr, node: Any):
        seq_recv = recv
        if recv_ty.kind == "string":
            seq_recv = f"toSeq({recv})"
        try:
            code, body_ty, ok = self._gen_it_body(closure, ["it"], elem_ty,
                                                  None)
        except _ClosureFallback:
            ok = False
        if ok:
            inner = body_ty.inner if body_ty.kind == "optional" else UNKNOWN
            return (f"{seq_recv}.swimCompactMapIt({code})",
                    Ty.array(inner))
        expr_ty = Ty.func((elem_ty,), UNKNOWN)
        proc_code, proc_ty = self.gen_closure(closure, expr_ty)
        if proc_ty.ret.kind != "optional":
            self.error("compactMap expects a closure returning an Optional",
                       node)
        return (f"swimCompactMap({seq_recv}, {proc_code})",
                Ty.array(proc_ty.ret.inner))

    def _hof_flat_map(self, recv: str, recv_ty: Ty, elem_ty: Ty,
                      closure: A.ClosureExpr, node: Any):
        seq_recv = recv
        if recv_ty.kind == "string":
            seq_recv = f"toSeq({recv})"
        try:
            code, body_ty, ok = self._gen_it_body(closure, ["it"], elem_ty,
                                                  None)
        except _ClosureFallback:
            ok = False
        if ok:
            if body_ty.kind == "array":
                return (f"{seq_recv}.swimFlatMapIt({code})",
                        Ty.array(body_ty.elem))
            if body_ty.kind == "optional":
                return (f"{seq_recv}.swimCompactMapIt({code})",
                        Ty.array(body_ty.inner))
        expr_ty = Ty.func((elem_ty,), UNKNOWN)
        proc_code, proc_ty = self.gen_closure(closure, expr_ty)
        if proc_ty.ret.kind == "array":
            return (f"swimFlatMap({seq_recv}, {proc_code})",
                    Ty.array(proc_ty.ret.elem))
        if proc_ty.ret.kind == "optional":
            return (f"swimCompactMap({seq_recv}, {proc_code})",
                    Ty.array(proc_ty.ret.inner))
        self.error("flatMap expects a closure returning a sequence or an "
                   "Optional", node)

    def _hof_minmax(self, recv: str, recv_ty: Ty, elem_ty: Ty,
                    closure: A.ClosureExpr, node: Any, name: str):
        try:
            code, _, ok = self._gen_it_body(closure, ["a", "b"], elem_ty, BOOL,
                                            param_tys=[elem_ty, elem_ty])
        except _ClosureFallback:
            ok = False
        cap = "Min" if name == "min" else "Max"
        if ok:
            return (f"swim{cap}ByIt({recv}, {code})", Ty.optional(elem_ty))
        expr_ty = Ty.func((elem_ty, elem_ty), BOOL)
        proc_code, _ = self.gen_closure(closure, expr_ty)
        return (f"swim{cap}By({recv}, {proc_code})", Ty.optional(elem_ty))

    # ------------------------------------------------------------ arrays
    def _array_method(self, recv: str, recv_ty: Ty, name: str, args: list,
                      trailing: Any, node: Any):
        elem = recv_ty.elem
        if name == "append":
            arg = self._arg(args, 0)
            if arg is None:
                self.error("append needs an argument", node)
            code, got = self.gen_expr(arg, elem)
            code = self.coerce(code, got, elem, arg)
            return f"append({recv}, {code})", VOID
        if name == "insert":
            value = self._arg(args, 0, "at")
            value = self._arg(args, 0)
            idx = self._arg(args, 1, "at")
            if idx is None:
                self.error("insert needs 'at:'", node)
            vcode, vgot = self.gen_expr(value, elem)
            icode, _ = self.gen_expr(idx, INT)
            return f"insert({recv}, {vcode}, {icode})", VOID
        if name == "remove":
            idx = self._arg(args, 0, "at")
            if idx is None:
                self.error("remove needs 'at:'", node)
            icode, _ = self.gen_expr(idx, INT)
            return f"removeAt({recv}, {icode})", elem
        if name == "removeFirst":
            return f"removeFirst({recv})", elem
        if name == "removeLast":
            return f"removeLast({recv})", elem
        if name == "popLast":
            return f"popLastOpt({recv})", Ty.optional(elem)
        if name == "removeAll":
            if self._has_label(args, "where") or self._get_closure(args, trailing):
                closure = self._get_closure(args, trailing)
                try:
                    code, _, ok = self._gen_it_body(closure, ["it"], elem, BOOL)
                except _ClosureFallback:
                    ok = False
                if ok:
                    return f"swimRemoveAllIt({recv}, {code})", VOID
                return f"swimRemoveAllItems({recv})", VOID
            return f"swimRemoveAllItems({recv})", VOID
        if name == "contains":
            arg = self._arg(args, 0)
            if arg is None:
                self.error("contains needs an argument", node)
            code, got = self.gen_expr(arg, elem)
            code = self.coerce(code, got, elem, arg)
            return f"contains({recv}, {code})", BOOL
        if name == "allSatisfy":
            self.error("allSatisfy needs a closure", node)
        if name == "swapAt":
            i = self._arg(args, 0)
            j = self._arg(args, 1)
            icode, _ = self.gen_expr(i, INT)
            jcode, _ = self.gen_expr(j, INT)
            return f"swapAt({recv}, {icode}, {jcode})", VOID
        if name == "sorted":
            return f"sorted({recv})", recv_ty
        if name == "reversed":
            return f"reversed({recv})", recv_ty
        if name == "enumerated":
            return f"enumerated({recv})", Ty.array(Ty.tuple((INT, elem)))
        if name == "min":
            return f"minOpt({recv})", Ty.optional(elem)
        if name == "max":
            return f"maxOpt({recv})", Ty.optional(elem)
        if name == "joined":
            sep = self._arg(args, 0, "separator")
            sep_code = '""' if sep is None else self.gen_expr(sep, STRING)[0]
            return f"joinedSep({recv}, {sep_code})", STRING
        if name == "dropFirst":
            if args:
                code, _ = self.gen_expr(self._arg(args, 0), INT)
                return f"dropFirst({recv}, {code})", recv_ty
            return f"dropFirst({recv})", recv_ty
        if name == "dropLast":
            if args:
                code, _ = self.gen_expr(self._arg(args, 0), INT)
                return f"dropLast({recv}, {code})", recv_ty
            return f"dropLast({recv})", recv_ty
        if name == "prefix":
            code, _ = self.gen_expr(self._arg(args, 0), INT)
            return f"prefixLen({recv}, {code})", recv_ty
        if name == "suffix":
            code, _ = self.gen_expr(self._arg(args, 0), INT)
            return f"suffixLen({recv}, {code})", recv_ty
        if name == "map":
            arg = self._arg(args, 0)
            if arg is not None:
                code, got = self.gen_expr(arg, None)
                return f"map({recv}, {code})", Ty.array(UNKNOWN)
        if name == "filter":
            arg = self._arg(args, 0)
            if arg is not None:
                code, got = self.gen_expr(arg, None)
                return f"filter({recv}, {code})", recv_ty
        if name == "firstIndex" or name == "index":
            arg = self._arg(args, 0, "of")
            if arg is not None:
                code, got = self.gen_expr(arg, elem)
                fn = "firstIndex" if name == "firstIndex" else "indexOf"
                return f"{fn}({recv}, {code})", Ty.optional(INT)
        if name == "lastIndex":
            arg = self._arg(args, 0, "of")
            if arg is not None:
                code, got = self.gen_expr(arg, elem)
                code = self.coerce(code, got, elem, arg)
                return f"lastIndex({recv}, {code})", Ty.optional(INT)
        if name == "randomElement":
            return f"randomElement({recv})", Ty.optional(elem)
        if name == "shuffled":
            return f"shuffled({recv})", recv_ty
        if name == "shuffle":
            return f"shuffle({recv})", VOID
        if name == "elementsEqual":
            arg = self._arg(args, 0)
            if arg is None:
                self.error("elementsEqual needs an argument", node)
            code, got = self.gen_expr(arg, recv_ty)
            return f"elementsEqual({recv}, {code})", BOOL
        if name == "starts":
            arg = self._arg(args, 0, "with") or self._arg(args, 0)
            if arg is None:
                self.error("starts(with:) needs an argument", node)
            code, got = self.gen_expr(arg, recv_ty)
            return f"startsWith({recv}, {code})", BOOL
        return None

    # ------------------------------------------------------------ strings
    def _string_method(self, recv: str, name: str, args: list,
                       trailing: Any, node: Any):
        if name == "append":
            arg = self._arg(args, 0)
            code, got = self.gen_expr(arg, None)
            return f"append({recv}, {code})", VOID
        if name == "insert":
            value = self._arg(args, 0)
            idx = self._arg(args, 1, "at")
            vcode, _ = self.gen_expr(value, None)
            icode, _ = self.gen_expr(idx, INT)
            return f"insert({recv}, {vcode}, {icode})", VOID
        if name == "remove":
            idx = self._arg(args, 0, "at")
            icode, _ = self.gen_expr(idx, INT)
            return f"removeAt({recv}, {icode})", CHAR
        if name == "removeFirst":
            return f"removeFirst({recv})", CHAR
        if name == "removeLast":
            return f"removeLast({recv})", CHAR
        if name == "removeAll":
            return f"{recv}.setLen(0)", VOID
        if name == "uppercased":
            return f"toUpperAscii({recv})", STRING
        if name == "lowercased":
            return f"toLowerAscii({recv})", STRING
        if name == "capitalized":
            return f"capitalized({recv})", STRING
        if name == "hasPrefix":
            code, _ = self.gen_expr(self._arg(args, 0), STRING)
            return f"startsWith({recv}, {code})", BOOL
        if name == "hasSuffix":
            code, _ = self.gen_expr(self._arg(args, 0), STRING)
            return f"endsWith({recv}, {code})", BOOL
        if name == "contains":
            arg = self._arg(args, 0)
            code, got = self.gen_expr(arg, None)
            return f"contains({recv}, {code})", BOOL
        if name == "split":
            sep = self._arg(args, 0, "separator")
            if sep is None:
                return f"splitSep({recv})", Ty.array(STRING)
            scode, sty = self.gen_expr(sep, None)
            if isinstance(sep, A.StringLit) and len(sep.parts) == 1 and \
                    sep.parts[0][0] == "text" and len(sep.parts[0][1]) == 1:
                scode = self.char_literal(sep.parts[0][1])
            return f"splitSep({recv}, {scode})", Ty.array(STRING)
        if name == "components":
            sep = self._arg(args, 0, "separatedBy")
            scode, _ = self.gen_expr(sep, STRING)
            return f"components({recv}, {scode})", Ty.array(STRING)
        if name == "replacingOccurrences":
            of = self._arg(args, 0, "of")
            with_ = self._arg(args, 1, "with")
            ocode, _ = self.gen_expr(of, STRING)
            wcode, _ = self.gen_expr(with_, STRING)
            return f"replacedOccurrences({recv}, {ocode}, {wcode})", STRING
        if name == "trimmingCharacters":
            arg = self._arg(args, 0, "in")
            if isinstance(arg, A.CaseRefExpr) and "whitespace" in arg.name:
                return f"trimmingWhitespace({recv})", STRING
            return f"trimmingWhitespace({recv})", STRING
        if name == "trimmingCharactersIn":
            return f"trimmingWhitespace({recv})", STRING
        if name == "reversed":
            return f"reversedStr({recv})", STRING
        if name == "dropFirst":
            if args:
                code, _ = self.gen_expr(self._arg(args, 0), INT)
                return f"dropFirst({recv}, {code})", STRING
            return f"dropFirst({recv})", STRING
        if name == "dropLast":
            if args:
                code, _ = self.gen_expr(self._arg(args, 0), INT)
                return f"dropLast({recv}, {code})", STRING
            return f"dropLast({recv})", STRING
        if name == "prefix":
            code, _ = self.gen_expr(self._arg(args, 0), INT)
            return f"prefixLen({recv}, {code})", STRING
        if name == "suffix":
            code, _ = self.gen_expr(self._arg(args, 0), INT)
            return f"suffixLen({recv}, {code})", STRING
        if name == "index" or name == "firstIndex":
            sub = self._arg(args, 0, "of")
            scode, _ = self.gen_expr(sub, STRING)
            fn = "indexOf" if name == "index" else "firstIndex"
            return f"{fn}({recv}, {scode})", Ty.optional(INT)
        return None

    # ---------------------------------------------------------- dictionaries
    def _dict_method(self, recv: str, recv_ty: Ty, name: str, args: list,
                     trailing: Any, node: Any):
        if name == "updateValue":
            value = self._arg(args, 0, "value") or self._arg(args, 0)
            key = self._arg(args, 1, "forKey") or self._arg(args, 1)
            vcode, vgot = self.gen_expr(value, recv_ty.value)
            kcode, kgot = self.gen_expr(key, recv_ty.key)
            return f"updateValue({recv}, {vcode}, {kcode})", \
                Ty.optional(recv_ty.value)
        if name == "removeValue":
            key = self._arg(args, 0, "forKey") or self._arg(args, 0)
            kcode, _ = self.gen_expr(key, recv_ty.key)
            return f"removeValue({recv}, {kcode})", Ty.optional(recv_ty.value)
        closure = self._get_closure(args, trailing)
        if name == "mapValues" and closure is not None:
            expr_ty = Ty.func((recv_ty.value,), UNKNOWN)
            proc_code, proc_ty = self.gen_closure(closure, expr_ty)
            return (f"swimDictMapValues({recv}, {proc_code})",
                    Ty.dict(recv_ty.key, proc_ty.ret))
        if name == "filter" and closure is not None:
            pair_ty = Ty.tuple((recv_ty.key, recv_ty.value),
                               ("key", "value"))
            expr_ty = Ty.func((pair_ty,), BOOL)
            proc_code, _ = self.gen_closure(closure, expr_ty)
            return f"swimDictFilter({recv}, {proc_code})", recv_ty
        return None

    def _set_method(self, recv: str, recv_ty: Ty, name: str, args: list,
                    node: Any):
        if name == "contains":
            code, got = self.gen_expr(self._arg(args, 0), recv_ty.elem)
            return f"contains({recv}, {code})", BOOL
        if name == "insert":
            code, got = self.gen_expr(self._arg(args, 0), recv_ty.elem)
            return f"{recv}.incl({code})", VOID
        if name == "sorted":
            return f"sorted(toSeq({recv}))", Ty.array(recv_ty.elem)
        if name == "remove":
            code, got = self.gen_expr(self._arg(args, 0), recv_ty.elem)
            return f"{recv}.excl({code})", VOID
        set_ops = {
            "union": "swimUnion",
            "intersection": "swimIntersection",
            "subtracting": "swimSubtracting",
        }
        if name in set_ops:
            arg = self._arg(args, 0)
            if arg is None:
                self.error(f"{name} needs an argument", node)
            code, got = self.gen_expr(arg, recv_ty)
            return f"{set_ops[name]}({recv}, {code})", recv_ty
        set_preds = {
            "isSubset": "swimIsSubset",
            "isSuperset": "swimIsSuperset",
            "isDisjoint": "swimIsDisjoint",
        }
        if name in set_preds:
            arg = self._arg(args, 0, "of") or self._arg(args, 0, "with") or \
                self._arg(args, 0)
            if arg is None:
                self.error(f"{name} needs an argument", node)
            code, got = self.gen_expr(arg, recv_ty)
            return f"{set_preds[name]}({recv}, {code})", BOOL
        set_mut = {
            "formUnion": "swimFormUnion",
            "formIntersection": "swimFormIntersection",
            "formSymmetricDifference": "swimFormSymmetricDifference",
        }
        if name in set_mut:
            arg = self._arg(args, 0)
            if arg is None:
                self.error(f"{name} needs an argument", node)
            code, got = self.gen_expr(arg, recv_ty)
            return f"{set_mut[name]}({recv}, {code})", VOID
        return None

    def _numeric_method(self, recv: str, recv_ty: Ty, name: str, args: list,
                        node: Any):
        if name == "isMultiple":
            arg = self._arg(args, 0, "of")
            code, _ = self.gen_expr(arg, recv_ty)
            return f"intIsMultiple({recv}, {code})", BOOL
        if name == "squareRoot":
            return f"sqrt({recv})", FLOAT
        if name == "rounded":
            return f"round({recv})", recv_ty
        if name == "description":
            return f"swimStr({recv})", STRING
        if name in ("isNaN", "isInfinite", "isFinite"):
            if not recv_ty.is_float:
                self.error(f"'{name}' is only available on floating point "
                           "values", node)
            return f"{name}({recv})", BOOL
        if name == "truncatingRemainder":
            arg = self._arg(args, 0, "dividingBy") or self._arg(args, 0)
            if arg is None:
                self.error("truncatingRemainder needs 'dividingBy:'", node)
            code, got = self.gen_expr(arg, recv_ty)
            code = self.coerce(code, got, recv_ty, arg)
            return f"truncatingRemainder({recv}, {code})", recv_ty
        if name == "advanced":
            arg = self._arg(args, 0, "by") or self._arg(args, 0)
            if arg is None:
                self.error("advanced needs 'by:'", node)
            code, got = self.gen_expr(arg, recv_ty)
            code = self.coerce(code, got, recv_ty, arg)
            return f"advanced({recv}, {code})", recv_ty
        if name == "signum":
            return f"signum({recv})", recv_ty
        return None

    def _optional_method(self, recv: str, recv_ty: Ty, name: str, args: list,
                         trailing: Any, node: Any):
        closure = self._get_closure(args, trailing)
        if name == "map" and closure is not None:
            try:
                code, ty, ok = self._gen_it_body(closure, ["it"], recv_ty.inner, None)
            except _ClosureFallback:
                ok = False
            if ok:
                return f"swimOptMap({recv}, {code})", Ty.optional(ty)
        if name == "flatMap" and closure is not None:
            try:
                code, ty, ok = self._gen_it_body(closure, ["it"], recv_ty.inner, None)
            except _ClosureFallback:
                ok = False
            if ok:
                return (f"swimOptFlatMap({recv}, {code})",
                        make_optional(unwrap_optional(ty)))
        return None

    # ----------------------------------------------------------- static API
    def code_prim_static_member(self, prim: str, name: str, node: Any):
        if prim in INT_KINDS:
            if name == "max":
                return f"high({NIM_PRIM[prim]})", Ty.prim(prim)
            if name == "min":
                return f"low({NIM_PRIM[prim]})", Ty.prim(prim)
        if prim in FLOAT_KINDS:
            nim = NIM_PRIM[prim]
            if name == "pi":
                return f"{nim}(PI)", Ty.prim(prim)
            if name == "infinity":
                return f"{nim}(Inf)", Ty.prim(prim)
            if name == "nan":
                return f"{nim}(NaN)", Ty.prim(prim)
            if name == "greatestFiniteMagnitude":
                return f"{nim}(high({nim}))", Ty.prim(prim)
        self.error(f"'{name}' is not a static member of this type", node)

    def code_prim_static_call(self, prim: str, type_name: str, name: str,
                              args: list, trailing: Any, node: Any):
        if name == "random":
            rng = self._arg(args, 0, "in")
            if prim in FLOAT_KINDS:
                if isinstance(rng, A.BinaryExpr) and rng.op in ("...", "..<"):
                    low, _ = self.gen_expr(rng.left, Ty.prim(prim))
                    high, _ = self.gen_expr(rng.right, Ty.prim(prim))
                    return (f"swimRandomDoubleRange({low}, {high})",
                            Ty.prim(prim))
                return "swimRandomDouble()", Ty.prim(prim)
            if isinstance(rng, A.BinaryExpr) and rng.op in ("...", "..<"):
                low, _ = self.gen_expr(rng.left, INT)
                high, _ = self.gen_expr(rng.right, INT)
                if rng.op == "..<":
                    high = f"({high}) - 1"
                return f"swimRandomInt({low}, {high})", INT
            return "swimRandomInt(0, high(int))", INT
        self.error(f"'{name}' is not a static method of '{type_name}'", node)

    def code_builtin_type_construct(self, type_name: str, args: list,
                                    trailing: Any, node: Any,
                                    type_args: list | None = None):
        if type_name == "String":
            if self._has_label(args, "repeating") or (args and args[0].label == "repeating"):
                s = self._arg(args, 0, "repeating")
                n = self._arg(args, 1, "count")
                scode, _ = self.gen_expr(s, STRING)
                ncode, _ = self.gen_expr(n, INT)
                return f"stringRepeating({scode}, {ncode})", STRING
            if not args:
                return '""', STRING
            if len(args) > 1 and not self._has_label(args, "repeating"):
                labels = ", ".join(a.label or "?" for a in args)
                self.error("unsupported String initializer with arguments "
                           f"({labels}); file/data/encoding initializers are "
                           "not available in Swim", node)
            code, got = self.gen_expr(args[0].expr, None)
            if got.kind == "char":
                return f"${code}", STRING
            return f"swimStr({code})", STRING
        if type_name == "Character":
            if not args:
                self.error("Character needs an argument", node)
            code, got = self.gen_expr(args[0].expr, CHAR)
            if got.kind == "string" or isinstance(args[0].expr, A.StringLit):
                return self.coerce(code, got, CHAR, args[0].expr), CHAR
            return f"{code}", CHAR
        if type_name == "Array":
            if not args and type_args:
                elem = type_args[0]
                return (f"newSeq[{self.nim_type(elem, node)}]()",
                        Ty.array(elem))
            if not args and not type_args:
                self.error("Array() needs element type information", node)
            if self._has_label(args, "repeating"):
                v = self._arg(args, 0, "repeating")
                n = self._arg(args, 1, "count")
                vcode, vgot = self.gen_expr(v, None)
                ncode, _ = self.gen_expr(n, INT)
                if type_args:
                    return (f"arrayRepeating({vcode}, {ncode})",
                            Ty.array(type_args[0]))
                return f"arrayRepeating({vcode}, {ncode})", Ty.array(vgot)
            if args:
                code, got = self.gen_expr(args[0].expr, None)
                if got.kind == "array":
                    return code, got
                if got.kind in ("string", "range"):
                    return f"toSeq({code})", Ty.array(self._elem_type(got, node))
                self.error("Array(...) expects a sequence", node)
            self.error("empty Array() needs a contextual type; write '[]' with "
                       "an annotation instead", node)
        if type_name == "Set":
            if args:
                code, got = self.gen_expr(args[0].expr, None)
                if got.kind == "array":
                    return f"toHashSet({code})", Ty.set(got.elem)
                self.error("Set(...) expects an array", node)
            self.error("empty Set() needs a contextual type; write '[]' with "
                       "an annotation instead", node)
        if type_name == "Dictionary":
            if not args and type_args and len(type_args) >= 2:
                return (f"initTable[{self.nim_type(type_args[0], node)}, "
                        f"{self.nim_type(type_args[1], node)}]()",
                        Ty.dict(type_args[0], type_args[1]))
            self.error("empty Dictionary() needs a contextual type; write "
                       "'[:]' with an annotation instead", node)
        if type_name == "Bool":
            if args:
                code, got = self.gen_expr(args[0].expr, None)
                if got.is_numeric:
                    return f"({code} != 0)", BOOL
            self.error("Bool(...) is only supported for numeric values", node)
        if type_name == "Optional":
            if args:
                code, got = self.gen_expr(args[0].expr, None)
                return f"some({code})", Ty.optional(got)
            self.error("Optional(...) needs a value", node)
        self.error(f"unknown type '{type_name}'", node)

    # -------------------------------------------------------- free functions
    def code_native_call(self, module: str, table: dict, kinds: dict,
                         name: str, args: list, trailing: Any, node: Any):
        """Generate a call to a procedure of a native module.

        Arguments may be written with Swift argument labels; a trailing
        closure binds to the last (closure) parameter.
        """
        if module not in self.native_modules:
            self.error(f"'{name}' is provided by the {module} module; add "
                       f"'import {module}' to the file that uses it", node)
        nim_name, params, ret_kind = table[name]
        values: dict[int, Any] = {}

        def bind(index: int, expr: Any) -> None:
            if index in values:
                self.error(f"duplicate argument '{params[index][0]}' in call "
                           f"to '{name}'", expr)
            values[index] = expr

        for i, arg in enumerate(args):
            if arg.label is None:
                index = i
            else:
                labels = [label for label, _ in params]
                if arg.label not in labels:
                    self.error(f"unknown argument label '{arg.label}' in call "
                               f"to '{name}'", arg.expr)
                index = labels.index(arg.label)
            if index >= len(params):
                self.error(f"too many arguments in call to '{name}'", arg.expr)
            bind(index, arg.expr)
        if trailing is not None:
            if not params or params[-1][1] != "closure":
                self.error(f"'{name}' does not take a trailing closure", node)
            bind(len(params) - 1, trailing)

        codes: list[str] = []
        for index, (label, kind) in enumerate(params):
            if index not in values:
                self.error(f"missing argument '{label}' in call to '{name}'",
                           node)
            expr = values[index]
            if kind == "closure":
                expected = Ty.func((), VOID)
                code, got = self.gen_expr(expr, expected)
                if got.kind != "func":
                    self.error(f"argument '{label}' of '{name}' must be a "
                               "closure of type '() -> Void'", expr)
            else:
                expected = kinds[kind]
                code, got = self.gen_expr(expr, expected)
                code = self.coerce(code, got, expected, expr)
            codes.append(code)
        call = f"{nim_name}({', '.join(codes)})"
        result_ty = NATIVE_RESULT_TYPES[ret_kind]
        return call, result_ty

    def code_nimx_call(self, name: str, args: list, trailing: Any, node: Any):
        """Generate a call to a procedure of the `Nimx` native module."""
        return self.code_native_call("Nimx", NIMX_FUNCS, NIMX_KINDS,
                                     name, args, trailing, node)

    def code_zeta_call(self, name: str, args: list, trailing: Any, node: Any):
        """Generate a call to a procedure of the `Zeta` native module."""
        return self.code_native_call("Zeta", ZETA_FUNCS, NIMX_KINDS,
                                     name, args, trailing, node)

    def code_ferroui_call(self, name: str, args: list, trailing: Any,
                          node: Any):
        """Generate a call to a procedure of the `FerroUI` native module."""
        return self.code_native_call("FerroUI", FERROUI_FUNCS, FERROUI_KINDS,
                                     name, args, trailing, node)

    def code_builtin_free_call(self, name: str, args: list, trailing: Any,
                               node: Any):
        if name in NIMX_FUNCS:
            return self.code_nimx_call(name, args, trailing, node)
        if name in ZETA_FUNCS:
            return self.code_zeta_call(name, args, trailing, node)
        if name in FERROUI_FUNCS:
            return self.code_ferroui_call(name, args, trailing, node)
        if name in ("print", "debugPrint"):
            str_args: list[str] = []
            terminator = None
            separator = None
            for a in args:
                if a.label == "terminator":
                    terminator, _ = self.gen_expr(a.expr, STRING)
                    continue
                if a.label == "separator":
                    separator, _ = self.gen_expr(a.expr, STRING)
                    continue
                code, aty = self.gen_expr(a.expr, None)
                if aty.is_void:
                    self.error("cannot print an expression of type Void; "
                               "did you mean to call this as a statement?",
                               a.expr)
                str_args.append(f"swimStr({code})")
            args_code = ", ".join(str_args)
            if separator is not None and terminator is not None:
                return (f"swimPrintSepTo({args_code}, {separator}, "
                        f"{terminator})", VOID)
            if separator is not None:
                return f"swimPrintSep({args_code}, {separator})", VOID
            if terminator is not None:
                return f"swimPrintTo({args_code}, {terminator})", VOID
            return f"swimPrint({args_code})", VOID
        if name in ("fatalError",):
            code, _ = self.gen_expr(args[0].expr, STRING)
            return f"swimFatal({code})", VOID
        if name == "preconditionFailure":
            code, _ = self.gen_expr(args[0].expr, STRING)
            return f"swimPreconditionFailure({code})", VOID
        if name in ("assert", "precondition"):
            cond, _ = self.gen_expr(args[0].expr, BOOL)
            if len(args) > 1:
                msg, _ = self.gen_expr(args[1].expr, STRING)
                return f"swimAssert({cond}, {msg})", VOID
            return f"swimAssert({cond})", VOID
        if name == "zip":
            if len(args) != 2:
                self.error("zip needs exactly two arguments", node)
            acode, aty = self.gen_expr(args[0].expr, None)
            bcode, bty = self.gen_expr(args[1].expr, None)
            if aty.kind == "array" and bty.kind in ("array", "string"):
                a_elem = aty.elem
                b_elem = bty.elem if bty.kind == "array" else CHAR
                return (f"swimZip({acode}, {bcode})",
                        Ty.array(Ty.tuple((a_elem, b_elem))))
            if aty.kind == "string" and bty.kind == "string":
                return (f"swimZip({acode}, {bcode})",
                        Ty.array(Ty.tuple((CHAR, CHAR))))
            self.error("zip expects two sequences (arrays or strings)", node)
        if name == "readLine":
            return "swimReadLine()", Ty.optional(STRING)
        if name == "exit":
            code, _ = self.gen_expr(args[0].expr, INT)
            return f"swimExit({code})", VOID
        if name in ("abs",):
            code, got = self.gen_expr(args[0].expr, None)
            return f"abs({code})", got
        if name in ("min", "max"):
            if len(args) < 2:
                self.error(f"{name} needs at least two arguments", node)
            codes = []
            ty = None
            for a in args:
                code, got = self.gen_expr(a.expr, ty)
                codes.append(code)
                if ty is None:
                    ty = got
            result = ty or UNKNOWN
            acc = codes[0]
            for c in codes[1:]:
                acc = f"{name}({acc}, {c})"
            return acc, result
        math1 = {
            "sqrt": "sqrt", "floor": "floor", "ceil": "ceil", "round": "round",
            "trunc": "trunc", "sin": "sin", "cos": "cos", "tan": "tan",
            "asin": "arcsin", "acos": "arccos", "atan": "arctan",
            "log": "ln", "log2": "log2", "log10": "log10", "exp": "exp",
            "fabs": "abs",
        }
        if name in math1:
            code, got = self.gen_expr(args[0].expr, None)
            ret = FLOAT if not got.is_float else got
            return f"{math1[name]}({code})", ret
        if name == "pow":
            a, aty = self.gen_expr(args[0].expr, None)
            b, bty = self.gen_expr(args[1].expr, None)
            return f"pow({a}, {b})", FLOAT
        if name == "atan2":
            a, _ = self.gen_expr(args[0].expr, None)
            b, _ = self.gen_expr(args[1].expr, None)
            return f"arctan2({a}, {b})", FLOAT
        if name == "swap":
            a = args[0].expr
            b = args[1].expr
            acode, _ = self.gen_expr(a, None)
            bcode, _ = self.gen_expr(b, None)
            acode = acode + ".get" if False else acode
            return f"swap({acode}, {bcode})", VOID
        if name == "stride":
            self.error("stride can only be used directly in a for loop", node)
        if name == "type":
            self.error("type(of:) is not supported by Swim", node)
        if name == "dump":
            self.error("dump is not supported by Swim", node)
        if name == "withUnsafePointer":
            self.error("withUnsafePointer is not supported by Swim", node)
        self.error(f"unknown function '{name}'", node)

    # ============================================================== finalize
    def gen_header(self) -> None:
        from . import __version__
        src = self.filename.rsplit("/", 1)[-1]
        self.line(f"# Generated by Swim {__version__} from {src}")
        self.line("# This file is machine generated; edit the .sw source instead.")
        self.line("import swimrt")
        for name in sorted(self.native_modules):
            nim_module = NATIVE_MODULES.get(name)
            if nim_module:
                self.line(f"import {nim_module}")
        self.line("")

    def gen_global_inits(self) -> None:
        """Initialize top level declarations/statements in source order."""
        self.current_src_line = 0
        self.line("# " + "=" * 74)
        self.line("# Top level program (declarations initialized in source "
                  "order)")
        self.line("# " + "=" * 74)
        self.push_scope("global")
        first = True
        for item in getattr(self.module, "top_items", None) \
                or list(self.module.decls) + list(self.module.statements):
            self.current_src_line = getattr(item, "line", 0)
            if isinstance(item, A.VarDecl):
                if item.init is None:
                    continue
                sym = self.global_syms.get(item.name)
                if sym is None:
                    continue
                code, got = self.gen_expr(item.init, sym.ty)
                code = self.coerce(code, got, sym.ty, item.init)
                self.line(f"{sym.nim} = {code}")
            elif isinstance(item, (A.FuncDecl, A.ImportDecl,
                                   A.TypeAliasDecl, A.StructDecl,
                                   A.ClassDecl, A.EnumDecl, A.ProtocolDecl,
                                   A.ExtensionDecl, A.OperatorDecl,
                                   A.PrecedenceGroupDecl)):
                continue
            else:
                self.gen_stmt(item)
        self.pop_scope()
        self.line("")

    def gen_top_level(self) -> None:
        self.current_src_line = 0
        if self.main_job is not None:
            self.line("# " + "=" * 74)
            self.line("# @main entry point")
            self.line("# " + "=" * 74)
            self.line(f"{self.main_job.name}()")
        self.line("")

    def gen_static_inits(self) -> None:
        self.current_src_line = 0
        lines: list[str] = []
        self.push_scope("global")
        for info in self.reg.types.values():
            for name, sv in info.static_vars.items():
                nim = self.static_var_nim(info, name)
                if isinstance(sv, ComputedProp):
                    continue
                if sv.default is not None:
                    code, got = self.gen_expr(sv.default, sv.ty)
                    code = self.coerce(code, got, sv.ty, sv.default)
                    self.line(f"{nim} = {code}")
        self.pop_scope()

    def generate(self) -> tuple[str, dict]:
        self.build_jobs()
        self.gen_header()
        self.gen_type_section()
        self.gen_global_section()
        self.emit_forward_decls()
        for job in self.jobs:
            self.emit_proc(job)
        self.gen_static_inits()
        self.gen_global_inits()
        self.gen_top_level()
        text = "\n".join(self.out).rstrip() + "\n"
        return text, self.line_map


class _ClosureFallback(Exception):
    pass


def generate(module: A.Module, registry: Registry,
             filename: str = "<input>",
             native_modules: list | None = None) -> tuple[str, dict]:
    return CodeGen(module, registry, filename,
                   native_modules=native_modules).generate()
