"""Swim type representation and the type registry.

The registry collects all user declared types and free functions from a parsed
module and answers questions about them (fields, methods, enum cases, ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import ast_nodes as A
from .errors import SwimError


# ---------------------------------------------------------------------------
# Primitive mapping: Swift name -> internal kind
# ---------------------------------------------------------------------------
PRIM_KINDS = {
    "Int": "int", "Int8": "int8", "Int16": "int16", "Int32": "int32",
    "Int64": "int64",
    "UInt": "uint", "UInt8": "uint8", "UInt16": "uint16",
    "UInt32": "uint32", "UInt64": "uint64",
    "Double": "float", "Float": "float32", "Float80": "float64",
    "Bool": "bool", "String": "string", "Character": "char", "Void": "void",
}

NIM_PRIM = {
    "int": "int", "int8": "int8", "int16": "int16", "int32": "int32",
    "int64": "int64", "uint": "uint", "uint8": "uint8", "uint16": "uint16",
    "uint32": "uint32", "uint64": "uint64", "float": "float",
    "float32": "float32", "float64": "float64", "bool": "bool",
    "string": "string", "char": "char", "void": "void",
}

INT_KINDS = {"int", "int8", "int16", "int32", "int64",
             "uint", "uint8", "uint16", "uint32", "uint64"}
FLOAT_KINDS = {"float", "float32", "float64"}

# Names that must be mangled because they collide with Nim / runtime symbols.
# Protocol names that Swim implements natively even though they are not declared
# in the project (mapped to Nim concepts or synthesized members).
# Attributes that are either harmless or implemented by Swim.
ALLOWED_ATTRIBUTES = {
    "main", "discardableResult", "inlinable", "inline", "usableFromInline",
    "nonobjc", "objc", "available", "escaping", "autoclosure", "testable",
    "frozen",
}

UNSUPPORTED_PROPERTY_MODIFIERS = {"weak", "unowned", "lazy"}

BUILTIN_CONFORMANCES = {
    "Equatable", "Comparable", "Hashable", "CustomStringConvertible",
    "CaseIterable", "Error", "AnyObject",
}

RESERVED_TYPE_NAMES = {
    "Option", "Table", "TableRef", "HashSet", "HashSetRef", "seq", "array",
    "string", "int", "float", "bool", "char", "Result", "SomeInteger",
    "SomeFloat", "RootObj", "CatchableError", "Defect", "SortOrder", "Slice",
    "OpenArray", "untyped", "typed",
}


@dataclass(frozen=True)
class Ty:
    kind: str = "unknown"
    name: str = ""
    args: tuple = ()
    labels: tuple = ()

    # -- constructors ------------------------------------------------------
    @staticmethod
    def prim(kind: str) -> "Ty":
        return Ty(kind)

    @staticmethod
    def named(name: str, args: tuple = ()) -> "Ty":
        return Ty(kind="named", name=name, args=tuple(args))

    @staticmethod
    def generic(name: str) -> "Ty":
        return Ty(kind="generic", name=name)

    @staticmethod
    def array(elem: "Ty") -> "Ty":
        return Ty(kind="array", args=(elem,))

    @staticmethod
    def dict(key: "Ty", value: "Ty") -> "Ty":
        return Ty(kind="dict", args=(key, value))

    @staticmethod
    def set(elem: "Ty") -> "Ty":
        return Ty(kind="set", args=(elem,))

    @staticmethod
    def optional(inner: "Ty") -> "Ty":
        return Ty(kind="optional", args=(inner,))

    @staticmethod
    def tuple(types: tuple, labels: tuple = ()) -> "Ty":
        return Ty(kind="tuple", args=tuple(types), labels=tuple(labels))

    @staticmethod
    def func(params: tuple, ret: "Ty") -> "Ty":
        return Ty(kind="func", args=(tuple(params), ret))

    @staticmethod
    def range(elem: "Ty") -> "Ty":
        return Ty(kind="range", args=(elem,))

    # -- predicates --------------------------------------------------------
    @property
    def elem(self) -> "Ty":
        return self.args[0]

    @property
    def key(self) -> "Ty":
        return self.args[0]

    @property
    def value(self) -> "Ty":
        return self.args[1]

    @property
    def inner(self) -> "Ty":
        return self.args[0]

    @property
    def ret(self) -> "Ty":
        return self.args[1]  # type: ignore[return-value]

    @property
    def params(self) -> tuple:
        return self.args[0]  # type: ignore[return-value]

    @property
    def is_optional(self) -> bool:
        return self.kind == "optional"

    @property
    def is_void(self) -> bool:
        return self.kind == "void"

    @property
    def is_int(self) -> bool:
        return self.kind in INT_KINDS

    @property
    def is_float(self) -> bool:
        return self.kind in FLOAT_KINDS

    @property
    def is_numeric(self) -> bool:
        return self.is_int or self.is_float

    @property
    def is_named(self) -> bool:
        return self.kind == "named"

    def __repr__(self) -> str:  # pragma: no cover
        return ty_to_str(self)


UNKNOWN = Ty(kind="unknown")
VOID = Ty.prim("void")
INT = Ty.prim("int")
FLOAT = Ty.prim("float")
BOOL = Ty.prim("bool")
STRING = Ty.prim("string")
CHAR = Ty.prim("char")
ANY = Ty(kind="any")


def ty_to_str(ty: Ty) -> str:
    if ty.kind in NIM_PRIM:
        return ty.kind
    if ty.kind == "array":
        return f"[{ty_to_str(ty.elem)}]"
    if ty.kind == "dict":
        return f"[{ty_to_str(ty.key)}: {ty_to_str(ty.value)}]"
    if ty.kind == "set":
        return f"Set<{ty_to_str(ty.elem)}>"
    if ty.kind == "optional":
        return f"{ty_to_str(ty.inner)}?"
    if ty.kind == "tuple":
        if ty.labels:
            return "(" + ", ".join(
                f"{l}: {ty_to_str(t)}" for l, t in zip(ty.labels, ty.args)
            ) + ")"
        return "(" + ", ".join(ty_to_str(t) for t in ty.args) + ")"
    if ty.kind == "func":
        return "(" + ", ".join(ty_to_str(t) for t in ty.params) + f") -> {ty_to_str(ty.ret)}"
    if ty.kind == "named":
        if ty.args:
            return ty.name + "<" + ", ".join(ty_to_str(t) for t in ty.args) + ">"
        return ty.name
    if ty.kind == "generic":
        return ty.name
    if ty.kind == "range":
        return f"Range<{ty_to_str(ty.elem)}>"
    return ty.kind


def unwrap_optional(ty: Ty) -> Ty:
    return ty.inner if ty.is_optional else ty


def make_optional(ty: Ty) -> Ty:
    return ty if ty.is_optional else Ty.optional(ty)


def substitute(ty: Ty, mapping: dict[str, Ty]) -> Ty:
    if ty.kind == "generic":
        return mapping.get(ty.name, ty)
    if ty.kind in ("array", "optional", "set", "range"):
        return Ty(kind=ty.kind, args=(substitute(ty.elem, mapping),),
                  labels=ty.labels)
    if ty.kind == "dict":
        return Ty.dict(substitute(ty.key, mapping), substitute(ty.value, mapping))
    if ty.kind == "named":
        if not ty.args:
            return ty
        return Ty.named(ty.name, tuple(substitute(a, mapping) for a in ty.args))
    if ty.kind == "tuple":
        return Ty(kind="tuple",
                  args=tuple(substitute(t, mapping) for t in ty.args),
                  labels=ty.labels)
    if ty.kind == "func":
        params = tuple(substitute(p, mapping) for p in ty.params)
        return Ty.func(params, substitute(ty.ret, mapping))
    return ty


def types_equal(a: Ty | None, b: Ty | None) -> bool:
    if a is None or b is None:
        return False
    if a.kind == "unknown" or b.kind == "unknown":
        return True
    return a == b


# ---------------------------------------------------------------------------
# Type info
# ---------------------------------------------------------------------------
@dataclass
class FieldInfo:
    name: str
    ty: Ty
    is_let: bool = False
    default: Any = None
    owner: Any = None
    order: int = 0
    is_static: bool = False
    line: int = 0
    # Property observers (willSet/didSet).  When non-empty the stored value
    # lives in a mangled backing field and access goes through generated
    # getter/setter procs.
    observers: list = field(default_factory=list)

    @property
    def is_observed(self) -> bool:
        return bool(self.observers)


@dataclass
class SubscriptInfo:
    params: list = field(default_factory=list)  # list[A.Param]
    param_types: list = field(default_factory=list)  # list[Ty]
    ret: Ty = UNKNOWN
    accessors: list = field(default_factory=list)  # list[A.AccessorDecl]
    owner: Any = None
    is_static: bool = False
    decl: Any = None
    nim_get: str = ""  # generated proc names for static subscripts
    nim_set: str = ""

    def has_setter(self) -> bool:
        return any(a.kind == "set" for a in self.accessors)


@dataclass
class FuncInfo:
    name: str
    params: list = field(default_factory=list)  # list[A.Param]
    param_types: list = field(default_factory=list)  # list[Ty]
    ret: Ty = VOID
    generics: list = field(default_factory=list)  # list[(name, constraints)]
    body: list = field(default_factory=list)
    owner: Any = None  # TypeInfo or None for free functions
    is_method: bool = False
    is_static: bool = False
    is_mutating: bool = False
    is_init: bool = False
    failable: bool = False
    failable_mode: str | None = None
    is_operator: bool = False
    operator_fixity: str | None = None
    throws: bool = False
    decl: Any = None
    generic_env: dict = field(default_factory=dict)
    line: int = 0


@dataclass
class ComputedProp:
    name: str
    ty: Ty
    accessors: list = field(default_factory=list)
    owner: Any = None
    is_static: bool = False
    decl: Any = None


@dataclass
class EnumCaseInfo:
    name: str
    assoc: list = field(default_factory=list)  # list[(field_name, Ty)]
    raw_value: Any = None
    ordinal: int = 0
    has_assoc: bool = False
    decl: Any = None
    owner: Any = None


@dataclass
class TypeInfo:
    kind: str = "struct"  # 'struct' | 'class' | 'enum' | 'protocol'
    name: str = ""
    nim_name: str = ""
    generic_params: list = field(default_factory=list)
    fields: list = field(default_factory=list)
    methods: dict = field(default_factory=dict)  # name -> list[FuncInfo]
    inits: list = field(default_factory=list)
    computed: dict = field(default_factory=dict)  # name -> ComputedProp
    subscripts: list = field(default_factory=list)  # list[SubscriptInfo]
    static_funcs: dict = field(default_factory=dict)
    static_vars: dict = field(default_factory=dict)
    conformances: list = field(default_factory=list)
    superclass: Any = None
    raw_type: Ty | None = None
    enum_cases: list = field(default_factory=list)
    is_error: bool = False
    decl: Any = None
    is_builtin: bool = False
    parent: Any = None  # enclosing type for nested declarations
    nested: dict = field(default_factory=dict)  # leaf name -> TypeInfo

    # -- helpers -----------------------------------------------------------
    @property
    def is_generic(self) -> bool:
        return bool(self.generic_params)

    def generic_env(self) -> dict:
        return {name: Ty.generic(name) for name, _ in self.generic_params}

    def field(self, name: str) -> FieldInfo | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def method(self, name: str) -> list:
        return self.methods.get(name, [])

    def enum_case(self, name: str) -> EnumCaseInfo | None:
        for c in self.enum_cases:
            if c.name == name:
                return c
        return None

    def all_conformances(self) -> set:
        out = set(self.conformances)
        if self.superclass is not None:
            out |= self.superclass.all_conformances()
        return out

    def ancestors(self):
        t = self
        while t is not None:
            yield t
            t = t.superclass


@dataclass
class ExtensionInfo:
    target_name: str
    methods: dict = field(default_factory=dict)
    static_funcs: dict = field(default_factory=dict)
    computed: dict = field(default_factory=dict)
    inits: list = field(default_factory=list)
    subscripts: list = field(default_factory=list)


class Registry:
    """Collects declarations from a module and resolves type references."""

    def __init__(self, module: A.Module, filename: str = "<input>") -> None:
        self.module = module
        self.filename = filename
        self.types: dict[str, TypeInfo] = {}
        self.aliases: dict[str, A.TypeAliasDecl] = {}
        self.global_funcs: dict[str, list[FuncInfo]] = {}
        self.operators: dict[tuple[str, str], list[FuncInfo]] = {}
        self.global_vars: dict[str, A.VarDecl] = {}
        self.extensions: dict[str, ExtensionInfo] = {}
        self.protocols: dict[str, TypeInfo] = {}
        self.main_type: str | None = None
        self._build()

    # ------------------------------------------------------------- diagnostics
    def error(self, msg: str, node: Any = None, hint: str | None = None):
        raise SwimError(msg, filename=self.filename,
                        line=getattr(node, "line", None),
                        col=getattr(node, "col", None), hint=hint)

    def validate_attributes(self, node: Any) -> None:
        for attr in getattr(node, "attributes", []) or []:
            base = attr.split(".")[0]
            if base not in ALLOWED_ATTRIBUTES:
                self.error(
                    f"attribute '@{attr}' is not supported by Swim "
                    "(property wrappers and custom attributes have no "
                    "semantics)", node)

    def _validate_conformance(self, name: str, node: Any) -> None:
        if name in self.types:
            info = self.types[name]
            if info.kind != "protocol":
                self.error(f"'{name}' is a {info.kind}, not a protocol", node)
            return
        if name in BUILTIN_CONFORMANCES:
            return
        self.error(
            f"unknown protocol '{name}'; Swim supports user-declared protocols "
            "and Equatable, Comparable, Hashable, "
            "CustomStringConvertible, CaseIterable, Error",
            node,
        )

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        # Pass 0: reject attributes that would be silently ignored
        for decl in self.module.decls:
            self.validate_attributes(decl)
        # Pass 1: create TypeInfos (recursively for nested types) and aliases
        self._register_type_decls(self.module.decls, parent=None)
        # Pass 2: fill in members
        for info in list(self.types.values()):
            if info.kind in ("struct", "class", "enum", "protocol"):
                self._fill_type(info, info.decl)
        for decl in self.module.decls:
            if isinstance(decl, A.ExtensionDecl):
                self._add_extension(decl)
            elif isinstance(decl, A.FuncDecl):
                fi = self._func_info(decl, owner=None)
                self.global_funcs.setdefault(fi.name, []).append(fi)
                if fi.is_operator:
                    self.operators.setdefault(
                        (fi.operator_fixity or "infix", fi.name),
                        []).append(fi)
            elif isinstance(decl, A.VarDecl):
                self.global_vars[decl.name] = decl
        # Pass 3: resolve superclass / conformances / extensions superclass
        for info in self.types.values():
            self._resolve_inheritance(info)
        # detect @main (top level only)
        for decl in self.module.decls:
            if isinstance(decl, A.StructDecl) and "main" in decl.attributes:
                self.main_type = decl.name

    def _register_type_decls(self, decls: list, parent: Any) -> None:
        for decl in decls:
            kind = None
            if isinstance(decl, A.StructDecl):
                kind = "struct"
            elif isinstance(decl, A.ClassDecl):
                kind = "class"
            elif isinstance(decl, A.EnumDecl):
                kind = "enum"
            elif isinstance(decl, A.ProtocolDecl):
                kind = "protocol"
            if kind is not None:
                name = decl.name if parent is None else \
                    f"{parent.name}.{decl.name}"
                info = self._add_type(name, kind, decl, parent=parent)
                if kind == "protocol":
                    self.protocols[name] = info
                self._register_type_decls(getattr(decl, "members", []), info)
            elif isinstance(decl, A.TypeAliasDecl) and parent is None:
                self.aliases[decl.name] = decl

    def _add_type(self, name: str, kind: str, decl: Any,
                  parent: Any = None) -> "TypeInfo":
        leaf = name.rsplit(".", 1)[-1]
        if parent is not None:
            nim_name = f"{parent.nim_name}_{leaf}"
        else:
            nim_name = leaf
            if leaf in RESERVED_TYPE_NAMES:
                nim_name = "Swim" + leaf
        info = TypeInfo(kind=kind, name=name, nim_name=nim_name,
                        generic_params=list(
                            getattr(decl, "generic_params", [])),
                        decl=decl, parent=parent)
        self.types[name] = info
        if parent is not None:
            parent.nested[leaf] = info
        return info

    def _fill_type(self, info: TypeInfo, decl: Any) -> None:
        env = info.generic_env()
        env.update(self._nested_type_env(info, env))
        members = getattr(decl, "members", [])
        self._collect_member_aliases(members, env)
        if isinstance(decl, A.EnumDecl):
            self._fill_enum(info, decl, env)
        if isinstance(decl, A.ClassDecl):
            if decl.superclass is not None:
                # Heuristic: if the name is a protocol, treat as conformance
                if decl.superclass.name in self.protocols:
                    info.conformances.append(decl.superclass.name)
                else:
                    info._superclass_name = decl.superclass.name  # type: ignore
            info.conformances.extend(
                t.name for t in decl.conformances if isinstance(t, A.NamedType)
            )
        else:
            info.conformances.extend(
                t.name for t in getattr(decl, "conformances", [])
                if isinstance(t, A.NamedType)
            )
        info.conformances = [self._relative_type_name(c, info)
                             for c in info.conformances]
        for conformance in info.conformances:
            self._validate_conformance(conformance, decl)
        if info.kind == "protocol":
            for inherited in getattr(decl, "inherits", []) or []:
                if isinstance(inherited, A.NamedType):
                    self._validate_conformance(inherited.name, decl)
        for member in members:
            self._add_member(info, member, env)

    def _add_member(self, info: TypeInfo, member: Any, env: dict) -> None:
        self.validate_attributes(member)
        mods = set(getattr(member, "modifiers", []))
        if isinstance(member, A.DeinitDecl):
            self.error("deinit is not supported by Swim: ARC releases "
                       "objects automatically and there are no cleanup hooks",
                       member)
        if isinstance(member, (A.VarDecl, A.SubscriptDecl)):
            bad = mods & UNSUPPORTED_PROPERTY_MODIFIERS
            if bad:
                self.error(f"'{sorted(bad)[0]}' properties are not supported "
                           "by Swim yet", member)
        is_static = "static" in mods or "class" in mods
        if isinstance(member, A.VarDecl):
            observers = [a for a in member.accessors
                         if a.kind in ("willSet", "didSet")]
            accessors = [a for a in member.accessors
                         if a.kind in ("get", "set")]
            if observers:
                if member.is_let:
                    self.error("a 'let' constant cannot have property "
                               "observers (willSet/didSet)", member)
                if accessors:
                    self.error("a property cannot have both get/set "
                               "accessors and willSet/didSet observers", member)
                if is_static:
                    self.error("property observers on static properties are "
                               "not supported by Swim yet", member)
                ty = self.resolve_type(member.ty, env) if member.ty else UNKNOWN
                fi = FieldInfo(name=member.name, ty=ty,
                               is_let=member.is_let, default=member.init,
                               owner=info, order=len(info.fields),
                               is_static=False, line=member.line,
                               observers=observers)
                info.fields.append(fi)
            elif member.accessors:
                cp = ComputedProp(name=member.name, ty=UNKNOWN, owner=info,
                                  accessors=member.accessors,
                                  is_static=is_static, decl=member)
                cp.ty = self.resolve_type(member.ty, env) if member.ty else UNKNOWN
                if is_static:
                    info.static_vars[member.name] = cp
                else:
                    info.computed[member.name] = cp
            else:
                ty = self.resolve_type(member.ty, env) if member.ty else UNKNOWN
                fi = FieldInfo(name=member.name, ty=ty,
                               is_let=member.is_let, default=member.init,
                               owner=info, order=len(info.fields),
                               is_static=is_static, line=member.line)
                if is_static:
                    info.static_vars[member.name] = fi
                else:
                    info.fields.append(fi)
        elif isinstance(member, A.SubscriptDecl):
            if not member.accessors:
                self.error("expected subscript accessors", member)
            info.subscripts.append(SubscriptInfo(
                params=member.params,
                param_types=self._param_types(member.params, env),
                ret=self.resolve_type(member.ret, env),
                accessors=member.accessors, owner=info, is_static=is_static,
                decl=member))
        elif isinstance(member, A.FuncDecl):
            fi = self._func_info(member, owner=info, env=env)
            if fi.is_operator:
                is_static = True
                self.operators.setdefault(
                    (fi.operator_fixity or "infix", fi.name), []).append(fi)
            fi.is_static = is_static
            is_mutating = "mutating" in mods
            fi.is_mutating = is_mutating
            if info.kind == "protocol":
                fi.is_method = False
            else:
                fi.is_method = not is_static
            if is_static:
                info.static_funcs.setdefault(fi.name, []).append(fi)
            else:
                info.methods.setdefault(fi.name, []).append(fi)
        elif isinstance(member, A.InitDecl):
            fi = FuncInfo(name="init", params=member.params,
                          param_types=self._param_types(member.params, env),
                          ret=Ty.named(info.name,
                                       tuple(env[p] for p in env)
                                       if info.is_generic else ()),
                          body=member.body, owner=info, is_init=True,
                          failable=member.failable,
                          failable_mode=member.failable_mode, decl=member,
                          generic_env=env, line=member.line)
            info.inits.append(fi)
        elif isinstance(member, A.EnumCase):
            pass
        elif isinstance(member, A.DeinitDecl):
            pass
        elif isinstance(member, A.TypeAliasDecl):
            key = member.name if info is None else f"{info.name}.{member.name}"
            self.aliases[key] = member

    def _fill_enum(self, info: TypeInfo, decl: A.EnumDecl, env: dict) -> None:
        if decl.raw_type is not None:
            info.raw_type = self.resolve_type(decl.raw_type, env)
        info.conformances.extend(
            t.name for t in decl.conformances if isinstance(t, A.NamedType)
        )
        info.conformances = [self._relative_type_name(c, info)
                             for c in info.conformances]
        info.is_error = "Error" in info.conformances
        ordinal = 0
        for case in decl.cases:
            assoc: list = []
            for i, p in enumerate(case.assoc_params):
                fname = p.label if p.label else (
                    p.name if p.name and not p.name.startswith("arg") else f"value{i}")
                # Swift enum case parameters: ``case foo(Int)`` has no label,
                # ``case foo(x: Int)`` uses x.
                fname = p.label if p.label else f"arg{i}"
                assoc.append((fname, self.resolve_type(p.ty, env)))
            raw = case.raw_value
            if info.raw_type is not None and raw is None:
                if info.raw_type.is_int:
                    raw_val: Any = ordinal
                elif info.raw_type.kind == "string":
                    raw_val = case.name
                else:
                    raw_val = None
                ci = EnumCaseInfo(name=case.name, assoc=assoc, raw_value=raw_val,
                                  ordinal=ordinal, has_assoc=bool(assoc),
                                  decl=case, owner=info)
                ordinal += 1
            else:
                raw_val = raw
                ci = EnumCaseInfo(name=case.name, assoc=assoc, raw_value=raw_val,
                                  ordinal=ordinal, has_assoc=bool(assoc),
                                  decl=case, owner=info)
                if isinstance(raw, A.IntLit):
                    try:
                        ordinal = int(raw.text.replace("_", ""), 0) + 1
                    except ValueError:
                        ordinal += 1
                elif raw is None:
                    ordinal += 1
            info.enum_cases.append(ci)

    def _collect_member_aliases(self, members: list, env: dict) -> None:
        """Make nested ``typealias`` declarations usable inside the type."""
        for member in members:
            if isinstance(member, A.TypeAliasDecl):
                env[member.name] = self.resolve_type(member.ty, env)

    def _relative_type_name(self, name: str, info: TypeInfo) -> str:
        """Resolve a nested type/protocol name relative to its enclosing type."""
        if name in self.types or name in self.protocols:
            return name
        cur = info.parent
        while cur is not None:
            candidate = f"{cur.name}.{name}"
            if candidate in self.types or candidate in self.protocols:
                return candidate
            cur = cur.parent
        return name

    def _nested_type_env(self, info: TypeInfo, env: dict) -> dict:
        """Map unqualified sibling/nested type names to qualified Ty names."""
        out: dict = {}
        chain: list = []
        cur = info
        while cur is not None:
            chain.append(cur)
            cur = cur.parent
        for anc in reversed(chain):
            for leaf, child in anc.nested.items():
                out[leaf] = Ty.named(child.name)
            anc_env = anc.generic_env()
            for member in getattr(anc.decl, "members", []):
                if isinstance(member, A.TypeAliasDecl):
                    if member.name not in out:
                        out[member.name] = self.resolve_type(member.ty, anc_env)
        generic_names = {n for n, _ in info.generic_params}
        return {k: v for k, v in out.items() if k not in generic_names}

    def _param_types(self, params: list, env: dict) -> list:
        """Resolve parameter types; variadic parameters become arrays."""
        out: list = []
        for p in params:
            ty = self.resolve_type(p.ty, env)
            if getattr(p, "is_variadic", False):
                ty = Ty.array(ty)
            out.append(ty)
        return out

    def _func_info(self, decl: A.FuncDecl, owner: Any,
                   env: dict | None = None) -> FuncInfo:
        if env is None:
            env = {}
        gen_env = dict(env)
        for name, cons in decl.generic_params:
            gen_env[name] = Ty.generic(name)
        ret = self.resolve_type(decl.ret, gen_env) if decl.ret else VOID
        fi = FuncInfo(
            name=decl.name,
            params=decl.params,
            param_types=self._param_types(decl.params, gen_env),
            ret=ret,
            generics=decl.generic_params,
            body=decl.body,
            owner=owner,
            decl=decl,
            generic_env=gen_env,
            line=decl.line,
            is_operator=getattr(decl, "is_operator", False),
            operator_fixity=getattr(decl, "fixity", None),
        )
        return fi

    def _resolve_inheritance(self, info: TypeInfo) -> None:
        sup_name = getattr(info, "_superclass_name", None)
        if sup_name is not None:
            if sup_name not in self.types and info.parent is not None:
                cur = info.parent
                while cur is not None:
                    candidate = f"{cur.name}.{sup_name}"
                    if candidate in self.types:
                        sup_name = candidate
                        break
                    cur = cur.parent
            cur = info.parent
            while cur is not None:
                candidate = f"{cur.name}.{sup_name}"
                if candidate in self.protocols:
                    sup_name = candidate
                    break
                cur = cur.parent
            if sup_name in self.protocols:
                info.conformances.append(sup_name)
            elif sup_name in self.types:
                target_info = self.types[sup_name]
                if target_info.kind != "class":
                    self.error(f"'{sup_name}' is a {target_info.kind}, not a "
                               "class", info.decl)
                info.superclass = target_info
            else:
                self.error(f"unknown superclass or protocol '{sup_name}'",
                           info.decl)
        # remove protocol names that were resolved as superclass already
        info.conformances = [c for c in info.conformances
                             if c not in self.types
                             or self.types[c].kind == "protocol"]
        info.is_error = info.is_error or "Error" in info.conformances

    def _add_extension(self, decl: A.ExtensionDecl) -> None:
        target = decl.target
        name = None
        if isinstance(target, A.NamedType):
            name = target.name
        elif isinstance(target, A.ArrayType):
            name = "Array"
        elif isinstance(target, A.DictType):
            name = "Dictionary"
        if name is None:
            self.error("unsupported extension target", decl)
        for conformance in getattr(decl, "conformances", []) or []:
            if isinstance(conformance, A.NamedType):
                self._validate_conformance(conformance.name, decl)
        ext = self.extensions.setdefault(name, ExtensionInfo(target_name=name))
        env: dict = {}
        if isinstance(target, A.NamedType):
            info = self.types.get(name)
            if info is not None:
                env = info.generic_env()
            elif name == "Array":
                env = {"Element": Ty.generic("T")}
            elif name == "Dictionary":
                env = {"Key": Ty.generic("K"), "Value": Ty.generic("V")}
            elif name == "Set":
                env = {"Element": Ty.generic("T")}
        for member in decl.members:
            self.validate_attributes(member)
            mods = set(getattr(member, "modifiers", []))
            if isinstance(member, (A.VarDecl, A.SubscriptDecl)):
                bad = mods & UNSUPPORTED_PROPERTY_MODIFIERS
                if bad:
                    self.error(f"'{sorted(bad)[0]}' properties are not "
                               "supported by Swim yet", member)
            if isinstance(member, A.VarDecl):
                for accessor in member.accessors:
                    if accessor.kind in ("willSet", "didSet"):
                        self.error("property observers are not allowed in "
                                   "extensions (stored properties cannot be "
                                   "added by an extension)", member)
            if isinstance(member, A.DeinitDecl):
                self.error("deinit is not supported by Swim yet", member)
            is_static = "static" in mods or "class" in mods
            if isinstance(member, A.FuncDecl):
                fi = self._func_info(member, owner=None, env=env)
                if fi.is_operator:
                    is_static = True
                    self.operators.setdefault(
                        (fi.operator_fixity or "infix", fi.name),
                        []).append(fi)
                fi.is_static = is_static
                fi.is_mutating = "mutating" in mods
                fi.is_method = not is_static
                if is_static:
                    ext.static_funcs.setdefault(fi.name, []).append(fi)
                else:
                    ext.methods.setdefault(fi.name, []).append(fi)
            elif isinstance(member, A.VarDecl):
                ty = self.resolve_type(member.ty, env) if member.ty else UNKNOWN
                if member.accessors:
                    cp = ComputedProp(name=member.name, ty=ty, owner=None,
                                      accessors=member.accessors,
                                      is_static=is_static, decl=member)
                    ext.computed[member.name] = cp
                else:
                    # stored properties in extensions are not allowed in Swift
                    self.error("stored properties are not allowed in "
                               "extensions", member)
            elif isinstance(member, A.SubscriptDecl):
                if not member.accessors:
                    self.error("expected subscript accessors", member)
                ext.subscripts.append(SubscriptInfo(
                    params=member.params,
                    param_types=self._param_types(member.params, env),
                    ret=self.resolve_type(member.ret, env),
                    accessors=member.accessors, is_static=is_static,
                    decl=member))
            elif isinstance(member, A.InitDecl):
                fi = FuncInfo(name="init", params=member.params,
                              param_types=self._param_types(member.params, env),
                              ret=UNKNOWN, body=member.body, is_init=True,
                              failable=member.failable,
                              failable_mode=member.failable_mode, decl=member,
                              generic_env=env, line=member.line)
                ext.inits.append(fi)

    # ------------------------------------------------------- type resolution
    def resolve_type(self, node: A.TypeNode | None, env: dict | None = None) -> Ty:
        if node is None:
            return UNKNOWN
        env = env or {}
        if isinstance(node, A.NamedType):
            name = node.name
            if name in env:
                return env[name]
            if name in PRIM_KINDS:
                kind = PRIM_KINDS[name]
                return Ty.prim(kind)
            if name == "Optional" or name == "ImplicitlyUnwrappedOptional":
                if node.args:
                    return Ty.optional(self.resolve_type(node.args[0], env))
                return Ty.optional(UNKNOWN)
            if name == "Array":
                if node.args:
                    return Ty.array(self.resolve_type(node.args[0], env))
                return Ty.array(UNKNOWN)
            if name == "Dictionary":
                if len(node.args) >= 2:
                    return Ty.dict(self.resolve_type(node.args[0], env),
                                   self.resolve_type(node.args[1], env))
                return Ty.dict(UNKNOWN, UNKNOWN)
            if name == "Set":
                if node.args:
                    return Ty.set(self.resolve_type(node.args[0], env))
                return Ty.set(UNKNOWN)
            if name == "Any":
                return ANY
            if name == "AnyObject":
                return Ty.named("RootObj")
            if name == "Never":
                return VOID
            if name == "Self":
                return UNKNOWN
            if name in self.aliases:
                alias = self.aliases[name]
                if alias.generic_params and node.args:
                    alias_env = {}
                    for (gname, _), arg in zip(alias.generic_params, node.args):
                        alias_env[gname] = self.resolve_type(arg, env)
                    return self.resolve_type(alias.ty, alias_env)
                alias_ty = self.resolve_type(alias.ty, env)
                if alias.generic_params:
                    return alias_ty
                return alias_ty
            args = tuple(self.resolve_type(a, env) for a in node.args)
            if name in {"Comparable", "Equatable", "Hashable",
                        "CustomStringConvertible", "CaseIterable", "Error",
                        "AdditiveArithmetic", "Numeric", "BinaryInteger",
                        "FloatingPoint", "StringProtocol"}:
                return Ty.named(name, args)
            return Ty.named(name, args)
        if isinstance(node, A.OptionalType):
            return Ty.optional(self.resolve_type(node.inner, env))
        if isinstance(node, A.ArrayType):
            return Ty.array(self.resolve_type(node.elem, env))
        if isinstance(node, A.DictType):
            return Ty.dict(self.resolve_type(node.key, env),
                           self.resolve_type(node.value, env))
        if isinstance(node, A.TupleType):
            types = tuple(self.resolve_type(t, env) for _, t in node.elements)
            labels = tuple(lbl or "" for lbl, _ in node.elements)
            return Ty.tuple(types, labels if any(labels) else ())
        if isinstance(node, A.FuncType):
            params = tuple(self.resolve_type(p, env) for p in node.params)
            ret = self.resolve_type(node.ret, env)
            return Ty.func(params, ret)
        if isinstance(node, A.InoutType):
            return self.resolve_type(node.inner, env)
        return UNKNOWN

    # ------------------------------------------------------------- lookups
    def type_info(self, ty: Ty | None) -> TypeInfo | None:
        if ty is None or ty.kind != "named":
            return None
        return self.types.get(ty.name)

    def type_args_env(self, ty: Ty) -> dict:
        info = self.type_info(ty)
        if info is None or not info.is_generic:
            return {}
        mapping = {}
        for (name, _), arg in zip(info.generic_params, ty.args):
            mapping[name] = arg
        return mapping

    def field_type(self, ty: Ty, name: str) -> Ty | None:
        info = self.type_info(ty)
        if info is None:
            return None
        env = self.type_args_env(ty)
        cur: TypeInfo | None = info
        while cur is not None:
            for f in cur.fields:
                if f.name == name:
                    return substitute(f.ty, env)
            cur = cur.superclass
        return None

    def field_info(self, ty: Ty, name: str) -> FieldInfo | None:
        info = self.type_info(ty)
        if info is None:
            return None
        cur: TypeInfo | None = info
        while cur is not None:
            for f in cur.fields:
                if f.name == name:
                    return f
            cur = cur.superclass
        return None

    def computed_prop(self, ty: Ty, name: str) -> ComputedProp | None:
        info = self.type_info(ty)
        if info is None:
            return None
        env = self.type_args_env(ty)
        cur: TypeInfo | None = info
        while cur is not None:
            cp = cur.computed.get(name)
            if cp is not None:
                return ComputedProp(name=cp.name, ty=substitute(cp.ty, env),
                                    accessors=cp.accessors, owner=cur,
                                    is_static=cp.is_static, decl=cp.decl)
            for ext_key in (cur.name,):
                ext = self.extensions.get(ext_key)
                if ext and name in ext.computed:
                    cp = ext.computed[name]
                    return ComputedProp(name=cp.name, ty=cp.ty,
                                        accessors=cp.accessors, owner=cur,
                                        is_static=cp.is_static, decl=cp.decl)
            cur = cur.superclass
        return None

    def find_methods(self, ty: Ty, name: str) -> list[FuncInfo]:
        info = self.type_info(ty)
        out: list[FuncInfo] = []
        if info is not None:
            env = self.type_args_env(ty)
            cur: TypeInfo | None = info
            while cur is not None:
                for fi in cur.methods.get(name, []):
                    out.append(self._specialize(fi, env))
                cur = cur.superclass
        ext = self.extensions.get(ty.name if ty.kind == "named" else ty.kind)
        if ext is not None:
            for fi in ext.methods.get(name, []):
                out.append(self._specialize(fi, {}))
        # builtin pseudo-types for primitive extensions are keyed by Swift name
        prim_key = self._prim_key(ty)
        if prim_key and prim_key != (ty.name if ty.kind == "named" else None):
            ext2 = self.extensions.get(prim_key)
            if ext2 is not None:
                for fi in ext2.methods.get(name, []):
                    out.append(fi)
        # methods provided by protocol extensions
        if info is not None:
            for conf in info.all_conformances():
                ext3 = self.extensions.get(conf)
                if ext3 is not None:
                    for fi in ext3.methods.get(name, []):
                        out.append(fi)
        return out

    def _prim_key(self, ty: Ty) -> str | None:
        if ty.kind == "string":
            return "String"
        if ty.kind == "int":
            return "Int"
        if ty.kind == "float":
            return "Double"
        if ty.kind == "bool":
            return "Bool"
        if ty.kind == "char":
            return "Character"
        if ty.kind == "array":
            return "Array"
        if ty.kind == "dict":
            return "Dictionary"
        return None

    def _specialize(self, fi: FuncInfo, env: dict) -> FuncInfo:
        if not env:
            return fi
        return FuncInfo(
            name=fi.name,
            params=fi.params,
            param_types=[substitute(p, env) for p in fi.param_types],
            ret=substitute(fi.ret, env),
            generics=fi.generics,
            body=fi.body,
            owner=fi.owner,
            is_method=fi.is_method,
            is_static=fi.is_static,
            is_mutating=fi.is_mutating,
            is_init=fi.is_init,
            failable=fi.failable,
            failable_mode=fi.failable_mode,
            is_operator=fi.is_operator,
            operator_fixity=fi.operator_fixity,
            throws=fi.throws,
            decl=fi.decl,
            generic_env=fi.generic_env,
            line=fi.line,
        )

    def find_static_methods(self, ty: Ty, name: str) -> list[FuncInfo]:
        info = self.type_info(ty)
        out: list[FuncInfo] = []
        if info is not None:
            env = self.type_args_env(ty)
            for fi in info.static_funcs.get(name, []):
                out.append(self._specialize(fi, env))
        ext_key = ty.name if ty.kind == "named" else self._prim_key(ty)
        if ext_key:
            ext = self.extensions.get(ext_key)
            if ext is not None:
                for fi in ext.static_funcs.get(name, []):
                    out.append(fi)
        return out

    def find_operators(self, fixity: str, symbol: str) -> list[FuncInfo]:
        return self.operators.get((fixity, symbol), [])

    def find_functions(self, name: str) -> list[FuncInfo]:
        return self.global_funcs.get(name, [])

    def find_inits(self, ty: Ty) -> list[FuncInfo]:
        info = self.type_info(ty)
        if info is None:
            return []
        env = self.type_args_env(ty)
        out = [self._specialize(fi, env) for fi in info.inits]
        ext = self.extensions.get(info.name)
        if ext:
            out.extend(ext.inits)
        return out

    def has_synthesized_memberwise_init(self, info: TypeInfo) -> bool:
        return info.kind == "struct" and not info.inits

    def find_subscripts(self, ty: Ty) -> list:
        """All subscript declarations available on ``ty`` (own + extension)."""
        out: list = []
        info = self.type_info(ty)
        env: dict = {}
        if info is not None:
            env = self.type_args_env(ty)
            for si in info.subscripts:
                out.append(self._specialize_subscript(si, env))
        ext_key = info.name if info is not None else self._prim_key(ty)
        if ext_key:
            ext = self.extensions.get(ext_key)
            if ext is not None:
                for si in ext.subscripts:
                    out.append(self._specialize_subscript(si, env))
        return out

    def _specialize_subscript(self, si: SubscriptInfo, env: dict) -> SubscriptInfo:
        if not env:
            return si
        return SubscriptInfo(
            params=si.params,
            param_types=[substitute(t, env) for t in si.param_types],
            ret=substitute(si.ret, env),
            accessors=si.accessors,
            owner=si.owner,
            is_static=si.is_static,
            decl=si.decl,
            nim_get=si.nim_get,
            nim_set=si.nim_set,
        )

    # ---------------------------------------------------------- misc queries
    def is_error_type(self, ty: Ty | None) -> bool:
        info = self.type_info(ty)
        if info is None:
            return False
        return info.is_error or "Error" in info.conformances

    def resolve_type_str(self, name: str, env: dict | None = None) -> Ty:
        """Resolve a bare type name (used for superclass resolution)."""
        return self.resolve_type(A.NamedType(name=name), env or {})


def build_registry(module: A.Module, filename: str = "<input>") -> Registry:
    return Registry(module, filename)
