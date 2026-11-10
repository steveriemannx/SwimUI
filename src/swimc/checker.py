"""Static semantic checking for Swim programs.

This module replaces the retired Nim code generator.  It walks the parsed AST
and the symbol tables built by :mod:`swimc.types`, performing the static checks
that a dynamically-typed C backend cannot perform at run time: mutability,
member existence, assignment/argument type compatibility, guard exits,
``fallthrough`` placement, custom assignment operators, failable initializer
returns and the like.

Everything here is pure Python: the checker emits no code.  The direct C
backend (:mod:`swimc.codegen_c`) is the only code generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import ast_nodes as A
from .errors import SwimError
from .native_ferroui import FERROUI_FUNCS, MODULE_NAME as FERROUI_MODULE
from .types import (
    ANY,
    PRIM_KINDS,
    UNKNOWN,
    VOID,
    ComputedProp,
    FieldInfo,
    FuncInfo,
    Registry,
    SubscriptInfo,
    Ty,
    TypeInfo,
    ty_to_str,
)

INT = Ty.prim("int")
DOUBLE = Ty.prim("float")
BOOL = Ty.prim("bool")
STRING = Ty.prim("string")
CHAR = Ty.prim("char")


# Assignment operators: ``+=`` etc. only work as built-ins, user-defined
# assignment operators are rejected at the use site.
ASSIGN_OPS = {
    "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
}

COMPARISON_OPS = {"==", "!=", "<", "<=", ">", ">=", "===", "!=="}
LOGICAL_OPS = {"&&", "||"}
ARITH_OPS = {"+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>"}

# Free functions implemented by the C runtime.
BUILTIN_FUNCS = {
    "print", "debugPrint", "min", "max", "abs", "sqrt", "pow", "floor",
    "ceil", "round", "zip", "readLine", "exit", "fatalError",
    "preconditionFailure", "precondition", "assert", "stride", "random",
    "swap", "type", "isKnownUniquelyReferenced", "withUnsafePointer",
}

# Names of the retired native GUI module.  Using one of them is a compile
# error now that native modules are gone.
NIMX_FUNCS = {
    "nimxWindow", "nimxPanel", "nimxLabel", "nimxButton", "nimxProgressBar",
    "nimxOnTap", "nimxSetText", "nimxSetColor", "nimxSetFrame", "nimxRun",
    "nimxStack", "nimxImage", "nimxTextField", "nimxSlider", "nimxFree",
}

# Member names implemented by the C runtime standard library.  Generated from
# ``runtime/swimrt_builtin.c``; members outside this set on built-in values are
# reported as unknown (user-defined types are checked against their metadata).
BUILTIN_MEMBERS = {
    "String", "__convert__", "abs", "advanced", "allCases", "allSatisfy",
    "append", "asciiValue", "assert", "capitalized", "ceil", "compactMap",
    "components", "contains", "count", "debugPrint", "description",
    "dropFirst", "dropLast", "elementsEqual", "enumerated", "exit",
    "fatalError", "filter", "first", "firstIndex", "flatMap", "floor",
    "forEach", "formIntersection", "formSymmetricDifference", "formUnion",
    "fromRaw", "hasPrefix", "hasSuffix", "hashValue", "index", "init",
    "insert", "intersection", "isDisjoint", "isEmpty", "isFinite",
    "isInfinite", "isLetter", "isLowercase", "isMultiple", "isNaN",
    "isNumber", "isSubset", "isSuperset", "isUppercase", "isWhitespace",
    "joined", "keys", "last", "lastIndex", "lowerBound", "lowercased",
    "magnitude", "map", "mapValues", "max", "min", "pi", "popLast", "pow",
    "precondition", "preconditionFailure", "prefix", "print", "random",
    "randomElement", "rawValue", "readLine", "reduce", "remove", "removeAll",
    "removeFirst", "removeLast", "removeValue", "repeat",
    "replacingOccurrences", "reversed", "round", "rounded", "shuffle",
    "shuffled", "sign", "signum", "sort", "sorted", "split", "sqrt",
    "starts", "stride", "subtracting", "suffix", "swapAt",
    "symmetricDifference", "trimmingCharacters", "truncatingRemainder",
    "type", "union", "updateValue", "upperBound", "uppercased", "values",
    "wholeNumberValue", "zip",
}

PROTOCOL_NAMES = {
    "Comparable", "Equatable", "Hashable", "CustomStringConvertible",
    "CaseIterable", "Error", "AdditiveArithmetic", "Numeric",
    "BinaryInteger", "FloatingPoint", "StringProtocol", "AnyObject",
    "RootObj", "Any",
}


@dataclass
class Binding:
    ty: Ty
    mutable: bool = True
    kind: str = "local"  # local | global | field | static
    field_info: FieldInfo | None = None


@dataclass
class FuncCtx:
    type_info: TypeInfo | None = None
    self_ty: Ty | None = None
    ret_ty: Ty = UNKNOWN
    is_static: bool = False
    is_init: bool = False
    failable_init: bool = False
    is_deinit: bool = False
    loop_depth: int = 0
    switch_depth: int = 0
    labels: list = field(default_factory=list)


class Checker:
    def __init__(self, module: A.Module, registry: Registry,
                 filename: str = "<input>",
                 native_modules: list | None = None) -> None:
        self.module = module
        self.reg = registry
        self.filename = filename
        self.native_modules = set(native_modules or ())
        self.scopes: list[dict[str, Binding]] = [{}]
        self.ctx = FuncCtx()
        self.checked_funcs: set[int] = set()
        self.global_syms: dict[str, Binding] = {}
        self.diags: list[SwimError] = []

    # ------------------------------------------------------------------ util
    def error(self, msg: str, node: Any = None, hint: str | None = None):
        raise SwimError(
            msg,
            filename=self.filename,
            line=getattr(node, "line", None),
            col=getattr(node, "col", None),
            hint=hint,
        )

    def push_scope(self) -> None:
        self.scopes.append({})

    def pop_scope(self) -> None:
        self.scopes.pop()

    def declare(self, name: str, ty: Ty, mutable: bool = True,
                kind: str = "local", field_info: FieldInfo | None = None):
        self.scopes[-1][name] = Binding(ty, mutable, kind, field_info)

    def lookup(self, name: str) -> Binding | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return self.global_syms.get(name)

    def resolve_ty(self, node: Any, env: dict | None = None) -> Ty:
        if node is None:
            return UNKNOWN
        try:
            return self.reg.resolve_type(node, env or {})
        except SwimError:
            raise
        except Exception:
            return UNKNOWN

    def type_name_of(self, name: str) -> str | None:
        if name in PRIM_KINDS:
            return name
        if name in ("Any", "AnyObject", "Self"):
            return name
        info = self.reg.types.get(name)
        if info is not None:
            return info.name
        return None

    def _func_type(self, fi: FuncInfo) -> Ty:
        params = tuple(fi.param_types) if fi.param_types else ()
        return Ty.func(params, fi.ret)

    # ------------------------------------------------------------- entry point
    def run(self) -> None:
        self.predeclare_globals()
        self.check_all_types()
        for item in self.module.top_items:
            if isinstance(item, A.Decl):
                continue
            self.check_stmt(item)
        for decl in self.module.decls:
            if isinstance(decl, A.VarDecl):
                self.check_global_decl(decl)

    # ---------------------------------------------------------------- globals
    def predeclare_globals(self) -> None:
        for decl in self.module.decls:
            if not isinstance(decl, A.VarDecl):
                continue
            if getattr(decl, "owner", None) is not None:
                continue
            ty = self.resolve_ty(decl.ty) if decl.ty is not None else UNKNOWN
            if ty.kind == "unknown" and decl.init is not None:
                ty = self.safe_infer(decl.init)
            self.global_syms[decl.name] = Binding(
                ty, mutable=not decl.is_let, kind="global")

    def check_global_decl(self, decl: A.VarDecl) -> None:
        want = self.resolve_ty(decl.ty) if decl.ty is not None else UNKNOWN
        if decl.init is None:
            return
        got = self.infer(decl.init, want)
        if want.kind != "unknown":
            self.check_convert(decl.init, got, want)

    # ----------------------------------------------------- declarations/types
    def check_all_types(self) -> None:
        for info in self.reg.types.values():
            if info.decl is None:
                continue
            self.check_type_info(info)
        for target, ext in self.reg.extensions.items():
            info = self.reg.types.get(target)
            self.check_extension(ext, info)
        for funcs in self.reg.global_funcs.values():
            for fi in funcs:
                self.check_func(fi, None)

    def check_type_info(self, info: TypeInfo) -> None:
        self_ty = Ty.named(info.name)
        env = info.generic_env()
        for f in info.fields:
            if f.default is not None:
                save = self.ctx
                self.ctx = FuncCtx(type_info=info, self_ty=self_ty,
                                   is_static=f.is_static)
                try:
                    self.push_scope()
                    self.declare("self", self_ty, False, "field")
                    got = self.infer(f.default, f.ty)
                    if f.ty.kind != "unknown" and not f.is_static:
                        self.check_convert(f.default, got, f.ty)
                    self.pop_scope()
                finally:
                    self.ctx = save
            for acc in getattr(f, "observers", []) or []:
                self.check_observer(info, f, acc)
        for name, sv in info.static_vars.items():
            if isinstance(sv, ComputedProp):
                self.check_accessors(sv.accessors, info, sv.ty, is_static=True)
            elif isinstance(sv, FieldInfo) and sv.default is not None:
                self.check_default_expr(sv.default, sv.ty, info)
        for name, cp in info.computed.items():
            self.check_accessors(cp.accessors, info, cp.ty,
                                 is_static=cp.is_static)
        for funcs in info.methods.values():
            for fi in funcs:
                self.check_func(fi, info)
        for funcs in info.static_funcs.values():
            for fi in funcs:
                self.check_func(fi, info)
        for fi in info.inits:
            self.check_func(fi, info)
        if getattr(info, "deinit", None) is not None:
            self.check_deinit(info)
        for si in info.subscripts:
            self.check_subscript(si, info)

    def check_extension(self, ext, info: TypeInfo | None) -> None:
        for funcs in ext.methods.values():
            for fi in funcs:
                self.check_func(fi, info)
        for funcs in ext.static_funcs.values():
            for fi in funcs:
                self.check_func(fi, info)
        for name, cp in ext.computed.items():
            if info is not None:
                self.check_accessors(cp.accessors, info, cp.ty,
                                     is_static=cp.is_static)
        for fi in ext.inits:
            self.check_func(fi, info)
        for si in ext.subscripts:
            if info is not None:
                self.check_subscript(si, info)

    def check_default_expr(self, expr: Any, want: Ty,
                           info: TypeInfo | None) -> None:
        save = self.ctx
        self.ctx = FuncCtx(type_info=info,
                           self_ty=Ty.named(info.name) if info else None)
        try:
            self.push_scope()
            got = self.infer(expr, want)
            if want.kind != "unknown":
                self.check_convert(expr, got, want)
            self.pop_scope()
        finally:
            self.ctx = save

    def check_deinit(self, info: TypeInfo) -> None:
        decl = info.deinit
        save = self.ctx
        self.ctx = FuncCtx(type_info=info, self_ty=Ty.named(info.name),
                           is_deinit=True)
        try:
            self.push_scope()
            self.declare("self", Ty.named(info.name), False, "field")
            self.check_stmts(getattr(decl, "body", []) or [])
            self.pop_scope()
        finally:
            self.ctx = save

    def check_accessors(self, accessors: list, info: TypeInfo,
                        prop_ty: Ty, is_static: bool = False) -> None:
        self_ty = Ty.named(info.name)
        for acc in accessors:
            save = self.ctx
            self.ctx = FuncCtx(type_info=info, self_ty=self_ty,
                               ret_ty=prop_ty if acc.kind == "get" else VOID,
                               is_static=is_static,
                               failable_init=False)
            if acc.kind in ("willSet", "didSet"):
                self.ctx.ret_ty = VOID
            try:
                self.push_scope()
                if not is_static:
                    self.declare("self", self_ty, False, "field")
                if acc.kind == "set":
                    self.declare(acc.param or "newValue", prop_ty, True)
                elif acc.kind == "willSet":
                    self.declare(acc.param or "newValue", prop_ty, False)
                elif acc.kind == "didSet":
                    self.declare(acc.param or "oldValue", prop_ty, False)
                body = getattr(acc, "body", []) or []
                if acc.kind == "get" and len(body) == 1 and \
                        isinstance(body[0], A.ExprStmt):
                    got = self.infer(body[0].expr, prop_ty)
                    if prop_ty.kind != "unknown":
                        self.check_convert(body[0].expr, got, prop_ty)
                else:
                    self.check_stmts(body)
                self.pop_scope()
            finally:
                self.ctx = save

    def check_observer(self, info: TypeInfo, f: FieldInfo,
                       acc) -> None:
        save = self.ctx
        self.ctx = FuncCtx(type_info=info, self_ty=Ty.named(info.name))
        try:
            self.push_scope()
            self.declare("self", Ty.named(info.name), False, "field")
            if acc.kind == "didSet":
                self.declare(acc.param or "oldValue", f.ty, False)
            else:
                self.declare(acc.param or "newValue", f.ty, False)
            self.check_stmts(getattr(acc, "body", []) or [])
            self.pop_scope()
        finally:
            self.ctx = save

    def check_subscript(self, si: SubscriptInfo,
                        info: TypeInfo) -> None:
        save = self.ctx
        self.ctx = FuncCtx(type_info=info, self_ty=Ty.named(info.name),
                           ret_ty=si.ret, is_static=si.is_static)
        try:
            self.push_scope()
            if not si.is_static:
                self.declare("self", Ty.named(info.name), False, "field")
            for p, ty in zip(si.params, si.param_types):
                self.declare(p.name, ty, False)
            for acc in si.accessors:
                if acc.kind == "set":
                    self.declare(acc.param or "newValue", si.ret, True)
            for acc in si.accessors:
                body = getattr(acc, "body", []) or []
                if acc.kind == "get" and len(body) == 1 and \
                        isinstance(body[0], A.ExprStmt):
                    got = self.infer(body[0].expr, si.ret)
                    if si.ret.kind != "unknown":
                        self.check_convert(body[0].expr, got, si.ret)
                else:
                    self.check_stmts(body)
            self.pop_scope()
        finally:
            self.ctx = save

    def check_func(self, fi: FuncInfo, info: TypeInfo | None) -> None:
        if not fi.body:
            return
        key = id(fi)
        if key in self.checked_funcs:
            return
        self.checked_funcs.add(key)
        self_ty = Ty.named(info.name) if info is not None else None
        save = self.ctx
        self.ctx = FuncCtx(
            type_info=info,
            self_ty=self_ty,
            ret_ty=fi.ret if fi.ret is not None else UNKNOWN,
            is_static=fi.is_static,
            is_init=fi.is_init,
            failable_init=fi.failable,
        )
        if fi.ret is None or fi.ret.kind == "unknown":
            self.ctx.ret_ty = UNKNOWN
        try:
            self.push_scope()
            if info is not None and not fi.is_static:
                self.declare("self", self_ty, False, "field")
            for p, ty in zip(fi.params, fi.param_types):
                if p.is_variadic:
                    self.declare(p.name, Ty.array(ty), False)
                else:
                    self.declare(p.name, ty, bool(p.is_inout))
            for p, ty in zip(fi.params, fi.param_types):
                if p.default is not None:
                    got = self.infer(p.default, ty)
                    if ty.kind != "unknown":
                        self.check_convert(p.default, got, ty)
            ret = self.ctx.ret_ty
            if ret.kind == "unknown" and not fi.is_init:
                self.ctx.ret_ty = self.infer_return_type(fi.body, VOID)
            body = fi.body or []
            implicit = (not fi.is_init and len(body) == 1 and
                        isinstance(body[0], A.ExprStmt))
            if implicit and not self.ctx.ret_ty.is_void:
                got = self.infer(body[0].expr, self.ctx.ret_ty)
                if self.ctx.ret_ty.kind != "unknown":
                    self.check_convert(body[0].expr, got, self.ctx.ret_ty)
            else:
                self.check_stmts(body)
            self.pop_scope()
        finally:
            self.ctx = save

    def infer_return_type(self, body: list, default: Ty) -> Ty:
        types: list[Ty] = []
        self._collect_return_types(body, types)
        for ty in types:
            if ty is not None and ty.kind != "unknown":
                return ty
        return default

    def _collect_return_types(self, stmts: list, out: list) -> None:
        for stmt in stmts or []:
            # Statements of a body are AST nodes; a list field of a node can
            # hold plain values (labels, strings, types) too, so only nodes are
            # walked further.  Without this guard a list of strings crashed the
            # walk (``dataclasses.fields`` on a ``str``).
            if not isinstance(stmt, A.Node):
                continue
            if isinstance(stmt, A.ReturnStmt):
                if stmt.expr is None:
                    out.append(VOID)
                else:
                    out.append(self.safe_infer(stmt.expr))
                continue
            for val in vars(stmt).values():
                if isinstance(val, list):
                    self._collect_return_types(val, out)
                elif isinstance(val, A.Node):
                    self._collect_return_types([val], out)

    # ------------------------------------------------------------ statements
    def check_stmts(self, stmts: list) -> None:
        for stmt in stmts or []:
            self.check_stmt(stmt)

    def check_stmt(self, stmt: Any) -> None:
        if isinstance(stmt, A.VarStmt):
            want = self.resolve_ty(stmt.ty) if stmt.ty is not None else UNKNOWN
            got = self.infer(stmt.init, want) if stmt.init is not None else UNKNOWN
            if stmt.ty is not None and want.kind != "unknown" and \
                    stmt.init is not None:
                self.check_convert(stmt.init, got, want)
            ty = want if stmt.ty is not None else got
            if stmt.names:
                elem = self.tuple_elements(ty)
                for i, name in enumerate(stmt.names):
                    self.declare(name, elem[i] if i < len(elem) else UNKNOWN,
                                 mutable=not stmt.is_let)
            elif stmt.name:
                self.declare(stmt.name, ty, mutable=not stmt.is_let)
        elif isinstance(stmt, A.ExprStmt):
            self.infer(stmt.expr)
        elif isinstance(stmt, A.IfStmt):
            self.push_scope()
            self.check_conditions(stmt.conditions)
            self.check_stmts(stmt.then_body)
            self.pop_scope()
            if stmt.else_body:
                if len(stmt.else_body) == 1 and isinstance(
                        stmt.else_body[0], A.IfStmt):
                    self.check_stmt(stmt.else_body[0])
                else:
                    self.push_scope()
                    self.check_stmts(stmt.else_body)
                    self.pop_scope()
        elif isinstance(stmt, A.GuardStmt):
            self.check_conditions(stmt.conditions)
            self._validate_guard_exit(stmt)
            self.push_scope()
            self.check_stmts(stmt.else_body)
            self.pop_scope()
        elif isinstance(stmt, A.WhileStmt):
            save = self.ctx.loop_depth
            self.ctx.loop_depth += 1
            self.push_scope()
            self.check_conditions(stmt.conditions)
            self.check_stmts(stmt.body)
            self.pop_scope()
            self.ctx.loop_depth = save
        elif isinstance(stmt, A.RepeatStmt):
            save = self.ctx.loop_depth
            self.ctx.loop_depth += 1
            self.push_scope()
            self.check_stmts(stmt.body)
            self.pop_scope()
            if stmt.condition is not None:
                self.infer(stmt.condition)
            self.ctx.loop_depth = save
        elif isinstance(stmt, A.ForStmt):
            iter_ty = self.infer(stmt.iterable)
            elem = self.iter_element(iter_ty)
            save = self.ctx.loop_depth
            self.ctx.loop_depth += 1
            self.push_scope()
            names = getattr(stmt, "names", []) or []
            for i, name in enumerate(names):
                if not name:
                    continue
                if len(names) > 1:
                    parts = self.tuple_elements(elem)
                    self.declare(name, parts[i] if i < len(parts) else UNKNOWN)
                else:
                    self.declare(name, elem)
            if getattr(stmt, "pattern", None) is not None:
                self.check_pattern(stmt.pattern, elem)
            if stmt.where_cond is not None:
                self.infer(stmt.where_cond)
            self.check_stmts(stmt.body)
            self.pop_scope()
            self.ctx.loop_depth = save
        elif isinstance(stmt, A.SwitchStmt):
            subject = self.infer(stmt.subject)
            save = self.ctx.switch_depth
            self.ctx.switch_depth += 1
            cases = stmt.cases or []
            for idx, case in enumerate(cases):
                self.push_scope()
                self.ctx.switch_depth += 0
                for pat in case.patterns or []:
                    self.check_pattern(pat, subject)
                if case.where_cond is not None:
                    self.infer(case.where_cond)
                self.check_stmts(case.body)
                if case.body and isinstance(case.body[-1], A.FallthroughStmt):
                    if idx + 1 >= len(cases):
                        self.error(
                            "'fallthrough' cannot transfer control out of the "
                            "switch (no following case)", case.body[-1])
                self.pop_scope()
            self.ctx.switch_depth = save
        elif isinstance(stmt, A.DoStmt):
            self.push_scope()
            self.check_stmts(stmt.body)
            self.pop_scope()
            for clause in stmt.catches or []:
                self.push_scope()
                if clause.name:
                    self.declare(clause.name, UNKNOWN, False)
                for pat in getattr(clause, "patterns", []) or []:
                    self.check_pattern(pat, Ty.named("Error"))
                self.check_stmts(clause.body)
                self.pop_scope()
        elif isinstance(stmt, A.DeferStmt):
            self.push_scope()
            self.check_stmts(stmt.body)
            self.pop_scope()
        elif isinstance(stmt, A.ReturnStmt):
            self.check_return(stmt)
        elif isinstance(stmt, A.ThrowStmt):
            self.infer(stmt.expr)
        elif isinstance(stmt, (A.BreakStmt, A.ContinueStmt)):
            pass
        elif isinstance(stmt, A.FallthroughStmt):
            if self.ctx.switch_depth == 0:
                self.error("'fallthrough' cannot transfer control out of the "
                           "switch (no following case)", stmt)
        elif isinstance(stmt, A.LabeledStmt):
            self.check_stmt(stmt.stmt)
        elif isinstance(stmt, A.Decl):
            return
        else:
            self.walk_unknown(stmt)

    def check_return(self, stmt: A.ReturnStmt) -> None:
        if self.ctx.failable_init:
            if stmt.expr is None or isinstance(stmt.expr, A.NilLit):
                return
            self.error("a failable initializer can only return nil or fall "
                       "through to the end of the body", stmt)
        ret = self.ctx.ret_ty
        if stmt.expr is None:
            if ret is not None and not ret.is_void and ret.kind != "unknown":
                self.error("non-void function must return a value", stmt)
            return
        got = self.infer(stmt.expr, ret)
        if ret is not None and ret.kind != "unknown" and not ret.is_void:
            self.check_convert(stmt.expr, got, ret)

    def _validate_guard_exit(self, stmt: A.GuardStmt) -> None:
        body = stmt.else_body or []
        if not body:
            self.error("guard body must not be empty", stmt)
        last = body[-1]
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

    def check_conditions(self, conditions: list) -> None:
        for cond in conditions or []:
            if isinstance(cond, A.CondExpr):
                self.infer(cond.expr)
            elif isinstance(cond, A.CondBinding):
                ty = self.infer(cond.expr)
                inner = ty.inner if ty.is_optional else ty
                self.declare(cond.name, inner,
                             mutable=(cond.kind == "var"))
            elif isinstance(cond, A.CaseCond):
                ty = self.infer(cond.expr)
                self.check_pattern(cond.pattern, ty)
            elif cond is not None:
                self.infer(cond)

    # --------------------------------------------------------------- patterns
    def check_pattern(self, pat: Any, subject: Ty) -> None:
        if isinstance(pat, A.WildcardPattern):
            return
        if isinstance(pat, A.LiteralPattern):
            self.infer(pat.expr)
            return
        if isinstance(pat, A.BindingPattern):
            if pat.name and pat.name != "_":
                ty = subject.inner if pat.optional_unwrap else subject
                self.declare(pat.name, ty, mutable=(pat.kind == "var"))
            return
        if isinstance(pat, A.IsPattern):
            self.resolve_ty(pat.ty)
            return
        if isinstance(pat, A.RangePattern):
            self.infer(pat.low)
            self.infer(pat.high)
            return
        if isinstance(pat, A.EnumCasePattern):
            info = self.reg.type_info(subject)
            if info is not None and info.kind == "enum":
                case = info.enum_case(pat.case_name)
                if case is None:
                    self.error(f"type '{info.name}' has no case "
                               f"'{pat.case_name}'", pat)
                for binding in getattr(pat, "bindings", []) or []:
                    name = binding[1] if isinstance(binding, tuple) and \
                        len(binding) > 1 else None
                    if name and name != "_":
                        self.declare(name, UNKNOWN)
            else:
                for binding in getattr(pat, "bindings", []) or []:
                    name = binding[1] if isinstance(binding, tuple) and \
                        len(binding) > 1 else None
                    if name and name != "_":
                        self.declare(name, UNKNOWN)
            return
        self.walk_unknown(pat)

    # ------------------------------------------------------------ expressions
    def safe_infer(self, node: Any) -> Ty:
        try:
            return self.infer(node)
        except SwimError:
            return UNKNOWN

    def infer(self, node: Any, expected: Ty | None = None) -> Ty:
        if node is None:
            return UNKNOWN
        if isinstance(node, A.IntLit):
            return INT
        if isinstance(node, A.FloatLit):
            return DOUBLE
        if isinstance(node, A.BoolLit):
            return BOOL
        if isinstance(node, A.StringLit):
            self.infer_string_parts(node)
            return STRING
        if isinstance(node, A.NilLit):
            return Ty.optional(UNKNOWN)
        if isinstance(node, A.MagicLit):
            if getattr(node, "kind", "") in ("line", "column"):
                return INT
            return STRING
        if isinstance(node, A.Ident):
            return self.infer_ident(node)
        if isinstance(node, A.SelfExpr):
            return self.ctx.self_ty or UNKNOWN
        if isinstance(node, A.SuperExpr):
            info = self.ctx.type_info
            if info is not None and info.superclass is not None:
                return Ty.named(info.superclass.name)
            return self.ctx.self_ty or UNKNOWN
        if isinstance(node, A.MemberExpr):
            return self.infer_member(node, expected)
        if isinstance(node, A.CallExpr):
            return self.infer_call(node, expected)
        if isinstance(node, A.SubscriptExpr):
            return self.infer_subscript(node)
        if isinstance(node, A.BinaryExpr):
            return self.infer_binary(node)
        if isinstance(node, A.UnaryExpr):
            self.infer(node.operand)
            if node.op == "!":
                return BOOL
            return self.safe_infer(node.operand)
        if isinstance(node, A.PostfixExpr):
            self.infer(node.operand)
            return self.safe_infer(node.operand)
        if isinstance(node, A.TernaryExpr):
            self.infer(node.cond)
            then_ty = self.infer(node.then_expr, expected)
            else_ty = self.infer(node.else_expr, expected)
            if then_ty.kind != "unknown":
                return then_ty
            return else_ty
        if isinstance(node, A.ForceExpr):
            ty = self.infer(node.operand)
            if ty.is_optional:
                return ty.inner
            return ty
        if isinstance(node, A.CastExpr):
            ty = self.resolve_ty(node.ty)
            self.infer(node.expr)
            if node.mode == "as?":
                return Ty.optional(ty)
            return ty
        if isinstance(node, A.TypeCheckExpr):
            self.infer(node.expr)
            self.resolve_ty(node.ty)
            return BOOL
        if isinstance(node, A.TryExpr):
            ty = self.infer(node.expr)
            if node.mode == "try?":
                return Ty.optional(ty)
            return ty
        if isinstance(node, A.ClosureExpr):
            return self.infer_closure(node)
        if isinstance(node, A.ArrayLit):
            elem = UNKNOWN
            for item in node.items:
                ty = self.infer(item, expected.elem if expected and
                              expected.kind == "array" else None)
                if ty.kind != "unknown":
                    elem = ty
            return Ty.array(elem)
        if isinstance(node, A.DictLit):
            key_ty, val_ty = UNKNOWN, UNKNOWN
            for key, val in node.pairs:
                kt = self.infer(key)
                vt = self.infer(val)
                if kt.kind != "unknown":
                    key_ty = kt
                if vt.kind != "unknown":
                    val_ty = vt
            return Ty.dict(key_ty, val_ty)
        if isinstance(node, A.TupleLit):
            types: list[Ty] = []
            labels: list[str] = []
            for item in node.items:
                if isinstance(item, tuple):
                    label, expr = item
                else:
                    label, expr = getattr(item, "label", None), item
                labels.append(label or "")
                types.append(self.infer(expr))
            return Ty.tuple(tuple(types),
                            tuple(labels) if any(labels) else ())
        if isinstance(node, A.CaseRefExpr):
            return self.infer_case_ref(node, expected)
        if isinstance(node, A.GenericRefExpr):
            return Ty(kind="type", name=node.name)
        if isinstance(node, A.AssignExpr):
            self.check_assign(node)
            return VOID
        self.walk_unknown(node)
        return UNKNOWN

    def infer_string_parts(self, node: A.StringLit) -> None:
        for part in getattr(node, "parts", []) or []:
            if isinstance(part, A.Node):
                self.infer(part)
            elif isinstance(part, tuple):
                for item in part:
                    if isinstance(item, A.Node):
                        self.infer(item)

    def infer_ident(self, node: A.Ident) -> Ty:
        name = node.name
        binding = self.lookup(name)
        if binding is not None:
            return binding.ty
        info = self.ctx.type_info
        if info is not None:
            self_ty = Ty.named(info.name)
            if not self.ctx.is_static:
                fld = self.reg.field_info(self_ty, name)
                if fld is not None:
                    fty = self.reg.field_type(self_ty, name) or fld.ty
                    return fty
                cp = self.reg.computed_prop(self_ty, name)
                if cp is not None:
                    return cp.ty
                methods = self.reg.find_methods(self_ty, name)
                if methods:
                    return self._func_type(methods[0])
            else:
                sv = info.static_vars.get(name)
                if sv is not None:
                    return sv.ty
                funcs = info.static_funcs.get(name)
                if funcs:
                    return self._func_type(funcs[0])
        tname = self.type_name_of(name)
        if tname is not None:
            return Ty(kind="type", name=tname)
        funcs = self.reg.find_functions(name)
        if funcs:
            return self._func_type(funcs[0])
        if name in BUILTIN_FUNCS or name in BUILTIN_MEMBERS:
            return UNKNOWN
        return UNKNOWN

    def infer_member(self, node: A.MemberExpr, expected: Ty | None) -> Ty:
        base = node.base
        name = node.name
        # Static access through a type name / generic reference.
        type_base: str | None = None
        if isinstance(base, A.Ident) and self.lookup(base.name) is None:
            type_base = self.type_name_of(base.name)
        elif isinstance(base, A.GenericRefExpr):
            type_base = base.name
        elif isinstance(base, A.SelfExpr):
            type_base = None
        if type_base is not None:
            return self.static_member(type_base, name, node)
        bty = self.infer(base, expected)
        if bty is None:
            return UNKNOWN
        if bty.kind == "type":
            return self.static_member(bty.name, name, node)
        if bty.is_optional and not node.optional:
            bty = bty.inner
        result = self.instance_member(bty, name, node)
        if node.optional:
            return Ty.optional(result)
        return result

    def static_member(self, type_name: str, name: str, node: Any) -> Ty:
        info = self.reg.types.get(type_name)
        if info is not None:
            nested = info.nested.get(name)
            if nested is not None:
                return Ty(kind="type", name=nested.name)
            sv = info.static_vars.get(name)
            if sv is not None:
                return sv.ty
            funcs = info.static_funcs.get(name)
            if funcs:
                return self._func_type(funcs[0])
            if name == "allCases":
                return Ty.array(Ty.named(info.name))
            if name in ("rawValue", "fromRaw"):
                return UNKNOWN
            if info.kind == "enum":
                case = info.enum_case(name)
                if case is not None:
                    if case.has_assoc:
                        return Ty.func(tuple(t for _, t in case.assoc),
                                       Ty.named(info.name))
                    return Ty.named(info.name)
                self.error(f"enum '{info.name}' has no case '{name}'", node)
            self.error(f"type '{info.name}' has no static member '{name}'",
                       node)
        if type_name in PRIM_KINDS or type_name in ("Any", "AnyObject"):
            return UNKNOWN
        return UNKNOWN

    def instance_member(self, ty: Ty, name: str, node: Any) -> Ty:
        if ty.kind == "named":
            info = self.reg.type_info(ty)
            if info is not None:
                if info.kind == "protocol":
                    return self.protocol_member(info, name)
                fld = self.reg.field_info(ty, name)
                if fld is not None:
                    fty = self.reg.field_type(ty, name) or fld.ty
                    return fty
                cp = self.reg.computed_prop(ty, name)
                if cp is not None:
                    return cp.ty
                if info.kind == "enum":
                    case = info.enum_case(name)
                    if case is not None and not case.has_assoc:
                        return Ty.named(info.name)
                    if name == "rawValue" and info.raw_type is not None:
                        return info.raw_type
                methods = self.reg.find_methods(ty, name)
                if methods:
                    return self._func_type(methods[0])
                if name in ("description", "hashValue", "debugDescription"):
                    return STRING if name != "hashValue" else INT
                if name in PROTOCOL_NAMES:
                    return UNKNOWN
                self.error(f"type '{info.name}' has no member '{name}'", node)
            if name in PROTOCOL_NAMES:
                return UNKNOWN
            return UNKNOWN
        if ty.kind == "tuple":
            if name.isdigit():
                idx = int(name)
                if idx < len(ty.args):
                    return ty.args[idx]
                self.error(f"tuple has no element {idx}", node)
            if name in getattr(ty, "labels", ()) or ():
                idx = ty.labels.index(name)
                return ty.args[idx]
            self.error(f"tuple has no member '{name}'", node)
        if ty.kind in ("unknown", "any", "generic", "type", "func"):
            return UNKNOWN
        if ty.kind == "optional":
            return self.instance_member(ty.inner, name, node)
        if name in BUILTIN_MEMBERS:
            return UNKNOWN
        self.error(f"value of type '{ty_to_str(ty)}' has no member '{name}'",
                   node)

    def protocol_member(self, info: TypeInfo, name: str) -> Ty:
        fld = info.field(name)
        if fld is not None:
            return fld.ty
        cp = info.computed.get(name)
        if cp is not None:
            return cp.ty
        funcs = info.methods.get(name)
        if funcs:
            return self._func_type(funcs[0])
        return UNKNOWN

    def infer_subscript(self, node: A.SubscriptExpr) -> Ty:
        base_ty = self.infer(node.base)
        args = node.args or []
        for arg in args:
            self.infer(arg.expr if hasattr(arg, "expr") else arg)
        user = self.reg.find_subscripts(base_ty)
        if user:
            si = self.pick_overload(user, args)
            if si is not None:
                return si.ret
        if base_ty.kind == "array":
            return base_ty.elem
        if base_ty.kind == "dict":
            return Ty.optional(base_ty.value)
        if base_ty.kind == "string":
            return CHAR
        return UNKNOWN

    def infer_case_ref(self, node: A.CaseRefExpr, expected: Ty | None) -> Ty:
        for arg in node.args or []:
            self.infer(arg.expr if hasattr(arg, "expr") else arg)
        if expected is not None:
            ty = expected.inner if expected.is_optional else expected
            info = self.reg.type_info(ty)
            if info is not None and info.kind == "enum":
                case = info.enum_case(node.name)
                if case is None:
                    self.error(f"type '{info.name}' has no case "
                               f"'{node.name}'", node)
                return ty
        return UNKNOWN

    def infer_binary(self, node: A.BinaryExpr) -> Ty:
        op = node.op
        left = self.infer(node.left)
        right = self.infer(node.right)
        if op in COMPARISON_OPS or op in LOGICAL_OPS:
            return BOOL
        if op == "??":
            if left.is_optional:
                return left.inner if right.kind == "unknown" else right
            return right
        if op in ("...", "..<"):
            return Ty.range(left if left.kind != "unknown" else INT)
        user = self.reg.find_operators("infix", op)
        if user:
            return user[0].ret
        if op == "+" and (left.kind == "string" or right.kind == "string"):
            return STRING
        if op == "+" and left.kind == "array":
            return left
        if op in ARITH_OPS:
            if left.kind in ("float", "float32", "float64") or \
                    right.kind in ("float", "float32", "float64"):
                return DOUBLE
            if left.is_numeric and right.is_numeric:
                return INT
            return UNKNOWN
        return UNKNOWN

    def infer_closure(self, node: A.ClosureExpr) -> Ty:
        save = self.ctx
        self.push_scope()
        try:
            params: list[Ty] = []
            for p in node.params or []:
                ty = self.resolve_ty(p.ty) if p.ty is not None else UNKNOWN
                params.append(ty)
                name = p.name or f"$0"
                self.declare(name, ty, False)
            if getattr(node, "uses_implicit_params", False):
                for i in range(10):
                    self.declare(f"${i}", UNKNOWN, False)
            ret = self.resolve_ty(node.ret_type) if node.ret_type is not None \
                else UNKNOWN
            self.ctx = FuncCtx(
                type_info=self.ctx.type_info,
                self_ty=self.ctx.self_ty,
                ret_ty=ret if ret.kind != "unknown" else UNKNOWN,
            )
            body = node.body or []
            implicit = getattr(node, "implicit_return", False) and \
                len(body) == 1 and isinstance(body[0], A.ExprStmt)
            if implicit:
                got = self.infer(body[0].expr, ret if ret.kind != "unknown"
                                 else None)
                if ret.kind == "unknown":
                    ret = got
            else:
                self.check_stmts(body)
                if ret.kind == "unknown":
                    ret = self.infer_return_type(body, VOID)
            return Ty.func(tuple(params), ret)
        finally:
            self.ctx = save
            self.pop_scope()

    # ----------------------------------------------------------------- calls
    def infer_call(self, node: A.CallExpr, expected: Ty | None) -> Ty:
        callee = node.callee
        args = list(node.args or [])
        if node.trailing_closure is not None:
            args.append(A.CallArg(label="__trailing__",
                                  expr=node.trailing_closure))
        if isinstance(callee, A.Ident):
            name = callee.name
            if name in FERROUI_FUNCS:
                return self.infer_native_call(name, node, args)
            if name in NIMX_FUNCS:
                self.error(f"'{name}' was provided by the retired Nimx native "
                           "module; use 'import FerroUI' (the C GUI binding of "
                           "SwimUI) instead", node)
            tname = self.type_name_of(name)
            if tname is not None and name not in ("Any", "AnyObject"):
                return self.construct(tname, node, args)
            funcs = self.reg.find_functions(name)
            if funcs:
                return self.call_overloads(funcs, node, args)
            if name in BUILTIN_FUNCS:
                for arg in args:
                    self.infer(arg.expr)
                return UNKNOWN
            for arg in args:
                self.infer(arg.expr)
            return UNKNOWN
        if isinstance(callee, A.MemberExpr):
            return self.infer_method_call(callee, node, args)
        if isinstance(callee, A.SubscriptExpr):
            for arg in args:
                self.infer(arg.expr)
            return UNKNOWN
        if isinstance(callee, A.GenericRefExpr):
            for arg in args:
                self.infer(arg.expr)
            return UNKNOWN
        callee_ty = self.infer(callee)
        for arg in args:
            self.infer(arg.expr)
        if callee_ty.kind == "func":
            return callee_ty.ret
        return UNKNOWN

    # ------------------------------------------------------- native modules
    NATIVE_KINDS = {"int": INT, "double": DOUBLE, "string": STRING,
                    "bool": BOOL}
    NATIVE_RESULTS = {"int": INT, "double": DOUBLE, "string": STRING,
                      "bool": BOOL, "void": VOID}

    def infer_native_call(self, name: str, node: A.CallExpr,
                          args: list) -> Ty:
        """Type-check a call of a free function of a native module."""
        c_name, params, ret = FERROUI_FUNCS[name]
        if FERROUI_MODULE not in self.native_modules:
            self.error(f"'{name}' is provided by the {FERROUI_MODULE} module; "
                       f"add 'import {FERROUI_MODULE}' to the file that uses "
                       "it", node)
        labels = [label for label, _ in params]
        slots: list = [None] * len(params)
        for index, arg in enumerate(args):
            if arg.label in ("__trailing__", "*"):
                where = len(params) - 1
                if where < 0 or params[where][1] != "closure":
                    self.error(f"'{name}' does not take a trailing closure",
                               arg.expr)
            elif arg.label is None:
                where = index
            elif arg.label in labels:
                where = labels.index(arg.label)
            else:
                self.error(f"unknown argument label '{arg.label}' in call to "
                           f"'{name}'", arg.expr)
            if where >= len(params):
                self.error(f"too many arguments in call to '{name}'",
                           arg.expr)
            if slots[where] is not None:
                self.error(f"duplicate argument '{labels[where]}' in call to "
                           f"'{name}'", arg.expr)
            slots[where] = arg.expr
        for where, (label, kind) in enumerate(params):
            if slots[where] is None:
                self.error(f"missing argument '{label}' in call to '{name}'",
                           node)
            expr = slots[where]
            got = self.infer(expr)
            if kind == "closure":
                expected = Ty.func((), VOID)
                if got.kind not in ("func", "unknown"):
                    self.error(f"argument '{label}' of '{name}' must be a "
                               "closure of type '() -> Void'", expr)
                if got.kind == "func" and got.args and got.args[0]:
                    self.error(f"argument '{label}' of '{name}' must be a "
                               "closure of type '() -> Void'", expr)
                continue
            expected = self.NATIVE_KINDS[kind]
            if got.kind in ("unknown", "never"):
                continue
            if kind == "int":
                ok = got.is_int
            elif kind == "double":
                ok = got.is_float
            elif kind == "string":
                ok = got.kind == "string"
            else:
                ok = got.kind == "bool"
            if not ok:
                self.error(f"argument '{label}' of '{name}' has type "
                           f"'{ty_to_str(got)}', expected "
                           f"'{ty_to_str(expected)}'", expr)
        return self.NATIVE_RESULTS[ret]

    def infer_method_call(self, callee: A.MemberExpr, node: A.CallExpr,
                          args: list) -> Ty:
        base = callee.base
        name = callee.name
        if isinstance(base, A.Ident) and self.lookup(base.name) is None:
            tname = self.type_name_of(base.name)
            if tname is not None:
                return self.static_call(tname, name, node, args)
        bty = self.infer(base)
        if bty.kind == "type":
            return self.static_call(bty.name, name, node, args)
        if bty.is_optional:
            bty = bty.inner
        info = self.reg.type_info(bty)
        if info is not None and info.kind == "enum":
            case = info.enum_case(name)
            if case is not None and case.has_assoc:
                self.bind_payload(case, node, args)
                ret = Ty.named(info.name)
                return Ty.optional(ret) if callee.optional else ret
        methods = self.reg.find_methods(bty, name)
        if methods:
            self.validate_defaults(methods)
            ret = self.call_overloads(methods, node, args)
            return Ty.optional(ret) if callee.optional else ret
        if info is not None:
            fld = self.reg.field_info(bty, name)
            if fld is not None:
                fty = self.reg.field_type(bty, name) or fld.ty
                for arg in args:
                    self.infer(arg.expr)
                return fty.ret if fty.kind == "func" else UNKNOWN
            cp = self.reg.computed_prop(bty, name)
            if cp is not None:
                for arg in args:
                    self.infer(arg.expr)
                return UNKNOWN
        for arg in args:
            self.infer(arg.expr)
        if name in BUILTIN_MEMBERS:
            return UNKNOWN
        # Method that does not exist: report the same message as a member read.
        return self.instance_member(bty, name, callee)

    def static_call(self, type_name: str, name: str, node: A.CallExpr,
                    args: list) -> Ty:
        info = self.reg.types.get(type_name)
        if info is not None and info.kind == "enum":
            case = info.enum_case(name)
            if case is not None and case.has_assoc:
                self.bind_payload(case, node, args)
                return Ty.named(info.name)
        if info is not None:
            funcs = info.static_funcs.get(name)
            if funcs:
                self.validate_defaults(funcs)
                return self.call_overloads(funcs, node, args)
            sv = info.static_vars.get(name)
            if sv is not None:
                for arg in args:
                    self.infer(arg.expr)
                return sv.ty
        for arg in args:
            self.infer(arg.expr)
        return UNKNOWN

    def construct(self, name: str, node: A.CallExpr, args: list) -> Ty:
        info = self.reg.types.get(name)
        if info is not None:
            ty = Ty.named(name)
            if info.kind == "struct" and self.reg.has_synthesized_memberwise_init(info):
                self.check_memberwise_init(info, node, args)
                return ty
            inits = self.reg.find_inits(ty)
            if inits:
                self.validate_defaults(inits)
                self.call_overloads(inits, node, args, is_init=True)
            else:
                for arg in args:
                    self.infer(arg.expr)
            return ty
        if name in PRIM_KINDS:
            for arg in args:
                self.infer(arg.expr)
            return UNKNOWN
        for arg in args:
            self.infer(arg.expr)
        return UNKNOWN

    def check_memberwise_init(self, info: TypeInfo, node: A.CallExpr,
                              args: list) -> None:
        params: list = []
        for f in info.fields:
            if f.is_static:
                continue
            params.append(A.Param(label=f.name, name=f.name, ty=None,
                                  default=f.default,
                                  line=getattr(f, "line", None)))
        self._bind_and_check(params, [f.ty for f in info.fields
                                      if not f.is_static],
                             node, args)

    def validate_defaults(self, funcs: list) -> None:
        return

    def call_overloads(self, funcs: list, node: A.CallExpr, args: list,
                       is_init: bool = False) -> Ty:
        errors: list[SwimError] = []
        for fi in funcs:
            try:
                self._bind_and_check(fi.params, fi.param_types, node, args)
                return fi.ret if not is_init else Ty.named(
                    fi.owner.name if isinstance(fi.owner, TypeInfo)
                    else "Self")
            except SwimError as err:
                errors.append(err)
        # Prefer an arity diagnostic over a "no overload" message.
        for err in errors:
            if "missing argument" in err.message:
                raise err
        if errors:
            raise errors[0]
        for arg in args:
            self.infer(arg.expr)
        return UNKNOWN

    def bind_payload(self, case, node: A.CallExpr, args: list) -> None:
        expected = [ty for _, ty in case.assoc]
        if len(args) < len(expected):
            label = case.assoc[len(args)][0] if len(args) < len(case.assoc) \
                else "value"
            self.error(f"missing argument '{label}' for enum case "
                       f"'{case.name}'", node)
        for i, arg in enumerate(args):
            ty = expected[i] if i < len(expected) else UNKNOWN
            got = self.infer(arg.expr, ty)
            if ty.kind != "unknown":
                self.check_convert(arg.expr, got, ty)

    def _bind_and_check(self, params: list, param_types: list,
                        node: A.CallExpr, args: list) -> None:
        assigned: dict[int, Any] = {}
        variadic_values: list = []
        variadic = None
        for i, p in enumerate(params):
            if p.is_variadic:
                variadic = i
        trailing_idx = variadic
        if trailing_idx is None and params:
            trailing_idx = len(params) - 1
        free = [i for i, p in enumerate(params) if not p.is_variadic]
        variadic_filled = False
        sure = True
        for arg in args:
            label = getattr(arg, "label", None)
            if label == "__trailing__":
                if trailing_idx is not None:
                    if variadic is not None and trailing_idx == variadic:
                        variadic_values.append(arg)
                        variadic_filled = True
                    assigned[trailing_idx] = arg
                continue
            if label is None:
                if variadic is not None and variadic_filled:
                    variadic_values.append(arg)
                elif free:
                    assigned[free.pop(0)] = arg
                elif variadic is not None:
                    variadic_values.append(arg)
                    variadic_filled = True
                else:
                    sure = False
                continue
            idx = None
            for i, p in enumerate(params):
                ext = p.label if p.label is not None else p.name
                if ext == label and i not in assigned:
                    idx = i
                    break
            if idx is None:
                sure = False
                continue
            assigned[idx] = arg
            if idx == variadic:
                variadic_filled = True
        for i, p in enumerate(params):
            if i == variadic:
                break
            if i not in assigned and p.default is None and sure:
                self.error(f"missing argument for parameter '{p.name}'", node)
        for i, p in enumerate(params):
            if i == variadic:
                elem = param_types[i].elem if (
                    i < len(param_types) and param_types[i].kind == "array"
                ) else (param_types[i] if i < len(param_types) else UNKNOWN)
                for a in variadic_values:
                    got = self.infer(a.expr, elem)
                    if elem.kind != "unknown":
                        self.check_convert(a.expr, got, elem)
                continue
            if i not in assigned:
                continue
            ty = param_types[i] if i < len(param_types) else UNKNOWN
            arg = assigned[i]
            got = self.infer(getattr(arg, "expr", arg), ty)
            if ty.kind != "unknown":
                self.check_convert(getattr(arg, "expr", arg), got, ty)

    def _variadic_args(self, params: list, args: list, variadic_param) -> list:
        out = []
        seen = False
        for arg in args:
            if isinstance(arg, A.CallArg) and arg.label is None:
                if seen:
                    out.append(arg)
                else:
                    seen = True
            elif out is not None and not isinstance(arg, A.CallArg):
                if seen:
                    out.append(A.CallArg(label=None, expr=arg))
        return out

    # ------------------------------------------------------------ assignment
    def check_assign(self, node: A.AssignExpr) -> None:
        op = node.op
        if op in ASSIGN_OPS and op != "=" and \
                self.reg.find_operators("infix", op):
            self.error(f"custom assignment operator '{op}' is not supported "
                       "by Swim", node)
        want = self.assign_target(node.target, op)
        got = self.infer(node.value, want if want is not None else None)
        if want is not None and want.kind != "unknown":
            self.check_convert(node.value, got, want)

    def assign_target(self, target: Any, op: str) -> Ty | None:
        if isinstance(target, A.Ident):
            name = target.name
            if name == "_":
                return None
            binding = self.lookup(name)
            if binding is not None:
                if not binding.mutable:
                    if binding.kind == "field":
                        self.error(f"cannot assign to let property '{name}'",
                                   target)
                    self.error(f"cannot assign to let constant '{name}'",
                               target)
                return binding.ty
            info = self.ctx.type_info
            if info is not None:
                self_ty = Ty.named(info.name)
                fld = self.reg.field_info(self_ty, name)
                if fld is not None:
                    if fld.is_let and not self.ctx.is_init:
                        self.error(f"cannot assign to let property '{name}'",
                                   target)
                    return self.reg.field_type(self_ty, name) or fld.ty
                cp = self.reg.computed_prop(self_ty, name)
                if cp is not None:
                    return cp.ty
                sv = info.static_vars.get(name)
                if sv is not None:
                    if isinstance(sv, FieldInfo) and sv.is_let:
                        self.error(f"cannot assign to static let property "
                                   f"'{name}'", target)
                    return sv.ty
            return None
        if isinstance(target, A.MemberExpr):
            if target.optional:
                self.error("cannot assign through an optional chain", target)
            base = target.base
            type_base: str | None = None
            if isinstance(base, A.Ident) and self.lookup(base.name) is None:
                type_base = self.type_name_of(base.name)
            elif isinstance(base, A.GenericRefExpr):
                type_base = base.name
            if type_base is not None:
                info = self.reg.types.get(type_base)
                if info is not None:
                    sv = info.static_vars.get(target.name)
                    if sv is None:
                        self.error(f"type '{info.name}' has no static member "
                                   f"'{target.name}'", target)
                    if isinstance(sv, FieldInfo) and sv.is_let:
                        self.error(f"cannot assign to static let property "
                                   f"'{target.name}'", target)
                    if isinstance(sv, ComputedProp) and not any(
                            a.kind == "set" for a in sv.accessors):
                        self.error(f"cannot assign to read-only static "
                                   f"property '{target.name}'", target)
                    return sv.ty
                return None
            bty = self.infer(base)
            info = self.reg.type_info(bty)
            if info is not None:
                fld = self.reg.field_info(bty, target.name)
                if fld is not None:
                    if fld.is_let and not self.ctx.is_init:
                        self.error(f"cannot assign to let property "
                                   f"'{target.name}'", target)
                    return self.reg.field_type(bty, target.name) or fld.ty
                cp = self.reg.computed_prop(bty, target.name)
                if cp is not None:
                    if not any(a.kind == "set" for a in cp.accessors):
                        self.error(f"cannot assign to read-only property "
                                   f"'{target.name}'", target)
                    return cp.ty
                self.error(f"cannot assign to '{target.name}'", target)
            return None
        if isinstance(target, A.SubscriptExpr):
            base_ty = self.infer(target.base)
            args = target.args or []
            for arg in args:
                self.infer(arg.expr if hasattr(arg, "expr") else arg)
            user = self.reg.find_subscripts(base_ty)
            if user:
                si = self.pick_overload(user, args)
                if si is not None:
                    if not si.has_setter():
                        self.error("cannot assign through a read-only "
                                   "subscript", target)
                    return si.ret
            if base_ty.kind == "array":
                return base_ty.elem
            if base_ty.kind == "dict":
                return base_ty.value
            if base_ty.kind == "string":
                return CHAR
            return None
        self.infer(target)
        return None

    def pick_overload(self, items: list, args: list):
        for item in items:
            nparams = len(getattr(item, "params", []))
            if nparams == len(args):
                return item
        if items:
            return items[0]
        return None

    # ------------------------------------------------------ type conversion
    def check_convert(self, node: Any, got: Ty | None, want: Ty | None) -> None:
        if got is None or want is None:
            return
        if got.kind in ("unknown", "any", "generic", "type") or \
                want.kind in ("unknown", "any", "generic", "type", "void"):
            return
        if want.is_optional:
            if got.is_optional:
                self.check_convert(node, got.inner, want.inner)
                return
            if want.inner.kind != "unknown":
                self.check_convert(node, got, want.inner)
            return
        if got.is_optional:
            self.error("optional value used where a non-optional "
                       f"'{ty_to_str(want)}' is expected; force-unwrap with "
                       "'!' or unwrap with 'if let'/'guard let'", node)
        if want.kind == "char" and got.kind == "string":
            if isinstance(node, A.StringLit) and self._single_char_literal(node):
                return
            self.error("a String cannot be used as a Character", node)
        if got.kind == "string" and (want.is_numeric or want.kind == "bool"):
            self.error(f"cannot implicitly convert 'String' to "
                       f"'{ty_to_str(want)}'; use an explicit conversion "
                       f"such as {want.kind.capitalize()}(...)", node)
        if want.kind == "string" and (got.is_numeric or got.kind == "bool"):
            self.error("cannot implicitly convert '" + ty_to_str(got) +
                       "' to 'String'; use String(...)", node)
        if want.is_float and got.is_int:
            if isinstance(node, A.IntLit) or (
                    isinstance(node, A.UnaryExpr) and
                    isinstance(node.operand, A.IntLit)):
                return
            self.error(f"cannot implicitly convert '{ty_to_str(got)}' to "
                       f"'{ty_to_str(want)}'; use "
                       f"'{want.kind.capitalize()}(...)'", node)
        if want.kind == "named" and got.kind == "named":
            if want.name == got.name:
                return
            if want.name in PROTOCOL_NAMES or got.name in PROTOCOL_NAMES:
                return
            want_info = self.reg.types.get(want.name)
            got_info = self.reg.types.get(got.name)
            if want_info is None or got_info is None:
                return
            if want_info.kind == "protocol" or got_info.kind == "protocol":
                return
            for anc in got_info.ancestors():
                if anc.name == want.name:
                    return
            self.error(f"cannot implicitly convert '{ty_to_str(got)}' to "
                       f"'{ty_to_str(want)}'", node)

    # ----------------------------------------------------------------- misc
    def _single_char_literal(self, node: Any) -> bool:
        parts = getattr(node, "parts", None) or []
        if len(parts) != 1:
            return False
        part = parts[0]
        if isinstance(part, tuple) and len(part) == 2:
            return part[0] == "text" and isinstance(part[1], str) and \
                len(part[1]) == 1
        return isinstance(part, str) and len(part) == 1

    def tuple_elements(self, ty: Ty) -> list[Ty]:
        if ty is not None and ty.kind == "tuple":
            return list(ty.args)
        if ty is not None and ty.kind == "array":
            return [ty.elem]
        return []

    def iter_element(self, ty: Ty) -> Ty:
        if ty is None:
            return UNKNOWN
        if ty.kind in ("array", "set"):
            return ty.elem
        if ty.kind == "dict":
            return Ty.tuple((ty.key, ty.value), ("key", "value"))
        if ty.kind == "string":
            return CHAR
        if ty.kind == "range":
            return ty.elem
        if ty.kind == "optional":
            return self.iter_element(ty.inner)
        return UNKNOWN

    def walk_unknown(self, node: Any) -> None:
        """Best-effort traversal of nodes the checker has no special case for."""
        from dataclasses import fields as dc_fields
        if not isinstance(node, A.Node):
            return
        for f in dc_fields(node):
            val = getattr(node, f.name)
            if isinstance(val, A.Stmt):
                self.check_stmt(val)
            elif isinstance(val, A.Expr):
                self.safe_infer(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, A.Stmt):
                        self.check_stmt(item)
                    elif isinstance(item, A.Expr):
                        self.safe_infer(item)


def check(module: A.Module, registry: Registry, filename: str = "<input>",
          native_modules: list | None = None) -> None:
    """Run all static checks for *module*; raises :class:`SwimError`."""
    Checker(module, registry, filename, native_modules).run()
