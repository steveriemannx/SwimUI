"""Direct C code generator: Swim AST -> C source (no Nim intermediate).

The generated C targets the Swim runtime in ``runtime/swimrt.h``, a dynamic
object model with Swift-style atomic ARC and value semantics for value types.
Function/method dispatch, coercion, operators, collection algorithms and
pattern helpers all live in the runtime; this module lowers the AST to calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import ast_nodes as A
from .errors import SwimError
from .native_ferroui import FERROUI_FUNCS, MODULE_NAME as FERROUI_MODULE
from . import __version__
from .types import (
    ANY, BOOL, CHAR, FLOAT, INT, STRING, UNKNOWN, VOID, ComputedProp,
    INT_KINDS, FLOAT_KINDS, PRIM_KINDS, Ty, Registry, substitute, ty_to_str,
)

BUILTIN_FUNCS = {
    "print", "debugPrint", "min", "max", "abs", "sqrt", "pow", "floor",
    "ceil", "round", "zip", "readLine", "exit", "fatalError",
    "preconditionFailure", "precondition", "assert", "stride", "random",
    "swap", "type", "isKnownUniquelyReferenced", "withUnsafePointer",
}

C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "inline",
    "int", "long", "register", "restrict", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned",
    "void", "volatile", "while", "bool", "true", "false", "NULL",
}

KIND_TO_PRIMDESC = {
    "int": "SwimType_Int", "int8": "SwimType_Int8", "int16": "SwimType_Int16",
    "int32": "SwimType_Int32", "int64": "SwimType_Int64", "uint": "SwimType_UInt",
    "uint8": "SwimType_UInt8", "uint16": "SwimType_UInt16",
    "uint32": "SwimType_UInt32", "uint64": "SwimType_UInt64",
    "float": "SwimType_Double", "float32": "SwimType_Float32",
    "float64": "SwimType_Double", "bool": "SwimType_Bool",
    "string": "SwimType_String", "char": "SwimType_Char", "void": "SwimType_Void",
}


def c_ident(name: str) -> str:
    out = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    text = "".join(out) or "_"
    if text[0].isdigit():
        text = "_" + text
    if text in C_KEYWORDS:
        text = "sw_" + text
    return text


def c_string(text: str) -> str:
    """A C string literal for arbitrary UTF-8 source text."""
    out = ['"']
    for ch in text:
        o = ord(ch)
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
        elif o < 32:
            out.append("\\x%02x" % o)
        elif o < 128:
            out.append(ch)
        else:
            for b in ch.encode("utf8"):
                out.append("\\x%02x" % b)
    out.append('"')
    return "".join(out)


class Emitter:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.indent = 1

    def line(self, text: str = "") -> None:
        if text:
            self.lines.append("    " * self.indent + text)
        else:
            self.lines.append("")

    def raw(self, text: str) -> None:
        for ln in text.rstrip("\n").split("\n"):
            self.line(ln)

    def push(self) -> None:
        self.indent += 1

    def pop(self) -> None:
        self.indent -= 1


@dataclass
class JobParam:
    name: str
    ty: Ty = UNKNOWN
    label: str | None = None
    is_inout: bool = False
    is_variadic: bool = False
    default: object = None


class VarRef:
    __slots__ = ("kind", "slot", "depth", "ty", "decl", "cname", "type_info")

    def __init__(self, kind="frame", slot=-1, depth=0, ty=UNKNOWN, decl=None,
                 cname="", type_info=None):
        self.kind = kind          # frame | global | inout | static | localfn
        self.slot = slot
        self.depth = depth
        self.ty = ty
        self.decl = decl
        self.cname = cname
        self.type_info = type_info


@dataclass
class Job:
    cname: str
    kind: str                    # func | method | static | init | prop_get |
                                 # prop_set | sub_get | sub_set | defaults |
                                 # closure | defer | op
    params: list = field(default_factory=list)
    body: list = field(default_factory=list)
    ret_ty: Ty = VOID
    has_self: bool = False
    self_ty: Ty | None = None
    type_info: object = None
    mutating: bool = False
    failable: bool = False
    defaults_cname: str = ""
    label: str = ""
    decl: object = None
    parent_ctx: object = None
    is_init: bool = False
    is_static: bool = False
    is_operator: bool = False
    fixity: str | None = None
    op_symbol: str = ""
    owner_name: str = ""


class Ctx:
    def __init__(self, cg: "CGen", cname: str, kind: str, parent=None,
                 ret_ty: Ty = VOID, self_ty: Ty | None = None,
                 type_info=None, is_init: bool = False, failable: bool = False,
                 is_static: bool = False):
        self.cg = cg
        self.cname = cname
        self.kind = kind
        self.parent = parent
        self.ret_ty = ret_ty
        self.self_ty = self_ty
        self.type_info = type_info
        self.is_init = is_init
        self.failable = failable
        self.is_static = is_static
        self.has_self = False
        self.em = Emitter()
        self.scopes: list[dict[str, VarRef]] = [{}]
        self.nslots = 0
        self.temp = 0
        self.label_n = 0
        self.breaks: list[tuple[str, str | None]] = []   # (break, continue)
        self.node_slots: dict[int, int] = {}
        self.temps: list[str] = []
        self.block_depth = 0
        self.captured: list = []  # unused, frame pointer model
        self.defer_scopes: list[str] = []
        self.is_main = kind == "main"

    # -- scopes ---------------------------------------------------------
    def push_scope(self) -> None:
        self.scopes.append({})

    def pop_scope(self) -> None:
        self.scopes.pop()

    def bind(self, name: str, ref: VarRef) -> None:
        self.scopes[-1][name] = ref

    def lookup(self, name: str) -> VarRef | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def new_slot(self) -> int:
        idx = self.nslots
        self.nslots += 1
        return idx

    def slot_for_node(self, node, key=None) -> int:
        if key is None:
            key = id(node)
        if key not in self.node_slots:
            self.node_slots[key] = self.new_slot()
        return self.node_slots[key]

    def new_temp(self) -> str:
        self.temp += 1
        name = f"t{self.temp}"
        self.em.line(f"SWIM_TEMP({name});")
        self.temps.append((name, self.em.indent))
        return name

    def new_label(self, prefix: str) -> str:
        self.label_n += 1
        return f"{prefix}{self.label_n}"

    def line(self, text: str = "") -> None:
        self.em.line(text)

    def push_indent(self) -> None:
        self.em.push()

    def pop_indent(self) -> None:
        self.em.pop()


class CGen:
    def __init__(self, module: A.Module, registry: Registry,
                 filename: str = "<input>",
                 native_modules: list | None = None) -> None:
        self.module = module
        self.reg = registry
        self.filename = filename
        self.native_modules = set(native_modules or ())
        self.ctx: Ctx | None = None
        self.jobs: list[Job] = []
        self.job_by_key: dict = {}
        self.fn_counter = 0
        self.tmp_counter = 0
        self.closure_counter = 0
        # emitted pieces
        self.prologues: list[str] = []
        self.data_defs: list[str] = []
        self.data_names: list[str] = []
        self.type_defs: dict[str, str] = {}      # swim type desc name -> definition
        self.ty_desc_names: dict[str, str] = {}  # key -> desc name
        self.fn_protos: list[str] = []
        self.fn_defs: list[str] = []
        self.registrations: list[str] = []
        self.global_count = 0
        self.global_slots: dict[str, int] = {}
        self.static_slots: dict[tuple, int] = {}
        self.static_inits: list[str] = []
        self.main_ctx: Ctx | None = None
        self.main_type_info = None
        self.user_desc: dict[str, str] = {}
        self.type_infos: list = []
        self.raw_regs: list[str] = []
        self.registration_needed = False
        self.string_literals: dict[str, str] = {}
        self.main_stmts = []
        self.main_stmts_decls = []
        self.init_jobs = {}
        self.globals_ty = {}

    # ================================================================ utils
    def error(self, msg: str, node=None) -> None:
        raise SwimError(msg, filename=self.filename,
                        line=getattr(node, "line", None),
                        col=getattr(node, "col", None))

    def new_cname(self, hint: str) -> str:
        self.fn_counter += 1
        return f"swf_{c_ident(hint)}_{self.fn_counter}"

    def new_data_name(self, hint: str) -> str:
        self.fn_counter += 1
        return f"swd_{c_ident(hint)}_{self.fn_counter}"

    def resolve_ty(self, node, env: dict | None = None) -> Ty:
        try:
            return self.reg.resolve_type(node, env or {})
        except SwimError:
            return UNKNOWN

    def type_label(self, ty: Ty) -> str:
        return ty_to_str(ty)

    # ---------------- type descriptors --------------------------------
    def ty_desc(self, ty: Ty | None) -> str:
        if ty is None:
            return "&SwimType_Generic"
        if ty.kind in ("unknown", "any", "generic"):
            return "&SwimType_Generic" if ty.kind == "generic" else "&SwimType_Any"
        if ty.kind in KIND_TO_PRIMDESC:
            return "&" + KIND_TO_PRIMDESC[ty.kind]
        if ty.kind == "named":
            info = self.reg.types.get(ty.name)
            if info is None or info.kind == "protocol":
                return "&SwimType_Any"
            return "&" + self.user_desc[info.name]
        key = ty_to_str(ty)
        if key in self.ty_desc_names:
            return "&" + self.ty_desc_names[key]
        name = self.new_data_name("ty")
        self.ty_desc_names[key] = name
        self.data_names.append(name)
        if ty.kind == "array":
            self.type_defs[name] = (
                '{ .name = %s, .kind = SWIM_KIND_ARRAY, .elem = %s }' %
                (c_string(key), self.ty_desc(ty.elem)))
        elif ty.kind == "set":
            self.type_defs[name] = (
                '{ .name = %s, .kind = SWIM_KIND_SET, .elem = %s }' %
                (c_string(key), self.ty_desc(ty.elem)))
        elif ty.kind == "dict":
            self.type_defs[name] = (
                '{ .name = %s, .kind = SWIM_KIND_DICT, .key = %s, '
                '.value = %s }' %
                (c_string(key), self.ty_desc(ty.key), self.ty_desc(ty.value)))
        elif ty.kind == "optional":
            self.type_defs[name] = (
                '{ .name = %s, .kind = SWIM_KIND_OPTIONAL, .elem = %s }' %
                (c_string(key), self.ty_desc(ty.inner)))
        elif ty.kind == "tuple":
            fdefs = []
            for i, item in enumerate(ty.args):
                label = ty.labels[i] if i < len(ty.labels) else str(i)
                fdefs.append("{ .name = %s, .type = %s }" %
                             (c_string(label), self.ty_desc(item)))
            if fdefs:
                arr = self.new_data_name("tupf")
                self.data_defs.append(
                    "static const SwimFieldDesc %s[] = { %s };" %
                    (arr, ", ".join(fdefs)))
            else:
                arr = "NULL"
            self.type_defs[name] = (
                '{ .name = %s, .kind = SWIM_KIND_TUPLE, .field_count = %d, '
                '.fields = %s }' % (c_string(key), len(ty.args), arr))
        elif ty.kind == "func":
            self.type_defs[name] = (
                '{ .name = %s, .kind = SWIM_KIND_CLOSURE }' % c_string(key))
        elif ty.kind == "range":
            self.type_defs[name] = (
                '{ .name = %s, .kind = SWIM_KIND_RANGE, .elem = %s }' %
                (c_string(key), self.ty_desc(ty.elem)))
        else:
            return "&SwimType_Any"
        return "&" + name

    def add_data(self, text: str) -> str:
        name = self.new_data_name("d")
        self.data_defs.append(f"static const SwimType* const {name}[] = {{ {text} }};")
        return name

    def params_array(self, param_tys: list[Ty]) -> str:
        if not param_tys:
            return "NULL"
        return self.add_data(", ".join(self.ty_desc(t) for t in param_tys))

    # ============================================================ collect
    def collect(self) -> None:
        # 1. user type descriptors
        for info in self.reg.types.values():
            if info.kind == "protocol":
                continue
            cname = "T_" + c_ident(info.name)
            self.user_desc[info.name] = cname
            self.data_names.append(cname)
            self.type_infos.append(info)
        # 2. global slots: top-level vars, then static vars
        for decl in self.module.decls:
            if isinstance(decl, A.VarDecl) and decl.name not in self.global_slots:
                self.global_slots[decl.name] = self.global_count
                self.global_count += 1
        for info in self.reg.types.values():
            if info.kind == "protocol":
                continue
            for name in info.static_vars:
                key = (info.name, name)
                if key not in self.static_slots:
                    self.static_slots[key] = self.global_count
                    self.global_count += 1
        # 3. type metadata + member jobs
        for info in self.type_infos:
            self.collect_type(info)
        # 4. extensions
        for key, ext in self.reg.extensions.items():
            self.collect_extension(key, ext)
        # 5. top-level items
        for item in self.module.top_items:
            if isinstance(item, A.VarDecl):
                self.main_stmts_decls.append(item)
            elif isinstance(item, A.FuncDecl):
                self.collect_free_func(item)
            elif isinstance(item, (A.StructDecl, A.ClassDecl, A.EnumDecl,
                                   A.ProtocolDecl, A.TypeAliasDecl,
                                   A.OperatorDecl, A.PrecedenceGroupDecl,
                                   A.ImportDecl)):
                continue
            else:
                self.main_stmts.append(item)
        # 6. static var initialisation
        for info in self.reg.types.values():
            if info.kind == "protocol":
                continue
            for name, sv in info.static_vars.items():
                if isinstance(sv, ComputedProp):
                    continue
                self.static_inits.append((info, name, sv))
        if self.reg.main_type is not None:
            self.main_type_info = self.reg.types.get(self.reg.main_type)


    # ---------------- member collection -------------------------------
    def param_types_of(self, fi) -> list[Ty]:
        out = []
        for i, p in enumerate(fi.params):
            ty = fi.param_types[i] if i < len(fi.param_types) else UNKNOWN
            out.append(ty)
        return out

    def job_params(self, fi) -> list[JobParam]:
        tys = self.param_types_of(fi)
        out = []
        for i, p in enumerate(fi.params):
            out.append(JobParam(name=p.name, ty=tys[i], label=p.label,
                                is_inout=isinstance(p.ty, A.InoutType),
                                is_variadic=getattr(p, "is_variadic", False),
                                default=p.default))
        return out

    def make_job(self, kind: str, hint: str, params: list, body: list,
                 ret_ty: Ty, has_self: bool = False, self_ty: Ty | None = None,
                 type_info=None, mutating: bool = False, failable: bool = False,
                 decl=None, is_init: bool = False, is_static: bool = False,
                 is_operator: bool = False, fixity: str | None = None,
                 op_symbol: str = "", display_name: str = "") -> Job:
        job = Job(cname=self.new_cname(hint), kind=kind, params=params,
                  body=body or [], ret_ty=ret_ty, has_self=has_self,
                  self_ty=self_ty, type_info=type_info, mutating=mutating,
                  failable=failable, decl=decl, is_init=is_init,
                  is_static=is_static, is_operator=is_operator, fixity=fixity,
                  op_symbol=op_symbol)
        job.display_name = display_name or hint
        if any(p.default is not None for p in job.params):
            djob = Job(cname=job.cname + "_def", kind="defaults",
                       params=[JobParam(name=p.name, ty=p.ty, label=p.label,
                                        is_inout=p.is_inout,
                                        default=p.default) for p in job.params],
                       body=[], ret_ty=VOID, has_self=has_self,
                       self_ty=self_ty, type_info=type_info)
            job.defaults_cname = djob.cname
            self.jobs.append(djob)
        self.jobs.append(job)
        return job

    def labels_for(self, params: list) -> str:
        return ",".join(p.label if (p.label is not None) else "_"
                        for p in params)

    def collect_type(self, info) -> None:
        self_ty = self.self_type(info)
        env = self.type_env(info)
        # instance methods
        for name, fis in info.methods.items():
            for fi in fis:
                params = self.job_params(fi)
                job = self.make_job(
                    "method", name, params, fi.body, fi.ret, has_self=True,
                    self_ty=self_ty, type_info=info,
                    mutating=fi.is_mutating, decl=fi.decl)
                job.owner_name = info.name
                self.register_method(info, job, name, fi)
        # static methods
        for name, fis in info.static_funcs.items():
            for fi in fis:
                params = self.job_params(fi)
                job = self.make_job(
                    "static", name, params, fi.body, fi.ret, type_info=info,
                    decl=fi.decl, is_static=True,
                    is_operator=fi.is_operator,
                    fixity=fi.operator_fixity, op_symbol=fi.name)
                job.owner_name = info.name
                if fi.is_operator:
                    self.register_operator(job)
                else:
                    self.register_static(info, job, name)
        # initializers
        if info.kind != "enum":
            self.collect_inits(info, env)
        # computed properties
        for name, cp in info.computed.items():
            self.collect_computed(info, cp, name)
        # static computed / stored variables
        for name, sv in info.static_vars.items():
            if isinstance(sv, ComputedProp):
                self.collect_static_computed(info, sv, name)
            else:
                self.collect_static_stored(info, name, sv)
        # observed stored properties
        for f in info.fields:
            if f.observers:
                self.collect_observed(info, f, env)
        # subscripts
        for si in info.subscripts:
            self.collect_subscript(info, si, env)
        # deinitializers (classes only, inherited ones run from the runtime)
        decl_deinit = getattr(info, "deinit", None)
        if decl_deinit is not None:
            job = self.make_job("deinit", "deinit", [], decl_deinit.body,
                                VOID, has_self=True, self_ty=self_ty,
                                type_info=info, decl=decl_deinit)
            self.register_deinit(info, job)
        # enum raw values
        if info.kind == "enum":
            self.collect_enum_raws(info, env)

    def self_type(self, info) -> Ty:
        if info.is_generic:
            return Ty.named(info.name,
                            tuple(Ty.generic(n) for n, _ in info.generic_params))
        return Ty.named(info.name)

    def type_env(self, info) -> dict:
        env = {n: Ty.generic(n) for n, _ in info.generic_params}
        cur = info.parent
        return env

    def collect_free_func(self, decl: A.FuncDecl) -> None:
        fi = None
        for cand in self.reg.global_funcs.get(decl.name, []):
            if cand.decl is decl:
                fi = cand
                break
        if fi is None:
            return
        params = self.job_params(fi)
        job = self.make_job("func", decl.name, params, fi.body, fi.ret,
                            decl=decl, is_operator=fi.is_operator,
                            fixity=fi.operator_fixity, op_symbol=fi.name)
        if fi.is_operator:
            self.register_operator(job)
        else:
            self.register_global(job)

    def collect_inits(self, info, env) -> None:
        self_ty = self.self_type(info)
        if info.inits:
            for fi in info.inits:
                params = self.job_params(fi)
                job = self.make_job(
                    "init", "init", params, fi.body, BOOL if fi.failable else VOID,
                    has_self=True, self_ty=self_ty, type_info=info,
                    failable=fi.failable, decl=fi.decl, is_init=True)
                self.register_init(info, job)
        else:
            # synthesized memberwise initializer for structs, default for classes
            params: list[JobParam] = []
            if info.kind == "struct":
                for f in info.fields:
                    if f.is_static:
                        continue
                    params.append(JobParam(name=f.name,
                                           ty=substitute(f.ty, env),
                                           label=f.name, default=f.default))
            body = [A.VarStmt(name="", init=None)]  # unused placeholder
            job = self.make_job("init", "new", params, [], VOID, has_self=True,
                                self_ty=self_ty, type_info=info, is_init=True)
            job.synth_init = True
            self.register_init(info, job)

    def collect_computed(self, info, cp, name: str) -> None:
        self_ty = self.self_type(info)
        getter_body = []
        setter_body = []
        setter_param = "newValue"
        has_setter = False
        for acc in cp.accessors:
            if acc.kind == "get":
                getter_body = acc.body
            elif acc.kind == "set":
                has_setter = True
                setter_body = acc.body
                if acc.param:
                    setter_param = acc.param
        if cp.is_static:
            g = self.make_job("prop_get", name, [], getter_body, cp.ty,
                              has_self=True, type_info=info)
            s = None
            if has_setter:
                sp = [JobParam(name=setter_param, ty=cp.ty, label=None)]
                s = self.make_job("prop_set", name, sp, setter_body, VOID,
                                  has_self=True, type_info=info)
            self.register_static_prop(info, name, g, s)
            return
        g = self.make_job("prop_get", name, [], getter_body, cp.ty,
                          has_self=True, self_ty=self_ty, type_info=info)
        setter = None
        if has_setter:
            sp = [JobParam(name=setter_param, ty=cp.ty)]
            setter = self.make_job("prop_set", name, sp, setter_body, VOID,
                                   has_self=True, self_ty=self_ty,
                                   type_info=info)
        self.register_prop(info, name, g, setter)

    def collect_static_computed(self, info, sv, name) -> None:
        getter_body = []
        setter_body = []
        has_setter = False
        for acc in sv.accessors:
            if acc.kind == "get":
                getter_body = acc.body
            elif acc.kind == "set":
                has_setter = True
                setter_body = acc.body
        g = self.make_job("prop_get", name, [], getter_body, sv.ty,
                          has_self=True, type_info=info)
        s = None
        if has_setter:
            sp = [JobParam(name="newValue", ty=sv.ty)]
            s = self.make_job("prop_set", name, sp, setter_body, VOID,
                              has_self=True, type_info=info)
        self.register_static_prop(info, name, g, s)

    def collect_static_stored(self, info, name, decl) -> None:
        ty = decl.ty if decl.ty is not None else UNKNOWN
        default = getattr(decl, "init", None)
        if default is None:
            default = getattr(decl, "default", None)
        if ty.kind == "unknown" and default is not None:
            ty = self.infer_literal_ty(default)
        g = self.make_job("prop_get", name, [], [], ty, has_self=True,
                          type_info=info)
        g.static_slot = self.static_slots[(info.name, name)]
        s = None
        if not getattr(decl, "is_let", False):
            s = self.make_job("prop_set", name,
                              [JobParam(name="newValue", ty=ty)], [], VOID,
                              has_self=True, type_info=info)
            s.static_slot = self.static_slots[(info.name, name)]
        self.register_static_prop(info, name, g, s)

    def collect_observed(self, info, f, env) -> None:
        ty = f.ty
        if ty.kind == "unknown" and f.default is not None:
            ty = self.infer_literal_ty(f.default)
        self_ty = self.self_type(info)
        g = self.make_job("prop_get", f.name, [], [], ty, has_self=True,
                          self_ty=self_ty, type_info=info)
        g.observed_field = f.name
        s = self.make_job("prop_set", f.name,
                          [JobParam(name="newValue", ty=ty)], [], VOID,
                          has_self=True, self_ty=self_ty, type_info=info)
        s.observed_field = f.name
        s.observers = f.observers
        self.register_prop(info, f.name, g, s)

    def infer_literal_ty(self, expr) -> Ty:
        if isinstance(expr, A.IntLit):
            return INT
        if isinstance(expr, A.FloatLit):
            return FLOAT
        if isinstance(expr, A.BoolLit):
            return BOOL
        if isinstance(expr, A.StringLit):
            return STRING
        return UNKNOWN

    def collect_subscript(self, info, si, env, self_ty=None,
                          ext_key=None) -> None:
        if self_ty is None:
            self_ty = self.self_type(info) if info is not None else UNKNOWN
        params = []
        for i, p in enumerate(si.params):
            ty = si.param_types[i] if i < len(si.param_types) else UNKNOWN
            params.append(JobParam(name=p.name, ty=ty, label=p.label,
                                   is_inout=isinstance(p.ty, A.InoutType),
                                   is_variadic=getattr(p, "is_variadic", False)))
        getter_body = []
        setter_body = []
        has_setter = False
        for acc in si.accessors:
            if acc.kind == "get":
                getter_body = acc.body
            elif acc.kind == "set":
                has_setter = True
                setter_body = acc.body
        g = self.make_job("sub_get", "sub", params, getter_body, si.ret,
                          has_self=not si.is_static, self_ty=self_ty,
                          type_info=info)
        self.register_subscript(info, g, "__sub_get", si.is_static, ext_key)
        if has_setter:
            sp = list(params) + [JobParam(name="newValue", ty=si.ret)]
            s = self.make_job("sub_set", "sub", sp, setter_body, VOID,
                              has_self=not si.is_static, self_ty=self_ty,
                              type_info=info)
            self.register_subscript(info, s, "__sub_set", si.is_static,
                                    ext_key)

    def collect_enum_raws(self, info, env) -> None:
        running = 0
        raw_kind = info.raw_type.kind if info.raw_type is not None else ""
        for case in info.enum_cases:
            if case.has_assoc:
                continue
            if case.raw_value is not None:
                self.raw_regs.append((info, case.name, case.raw_value))
                if raw_kind in INT_KINDS and isinstance(case.raw_value, A.IntLit):
                    try:
                        running = int(case.raw_value.text.replace("_", ""))
                    except ValueError:
                        pass
                running += 1
            elif raw_kind in INT_KINDS:
                self.raw_regs.append((info, case.name, A.IntLit(text=str(running))))
                running += 1
            elif raw_kind == "string":
                self.raw_regs.append((info, case.name,
                                      A.StringLit(parts=[("text", case.name)])))

    # ---------------- extensions --------------------------------------
    def extension_self_ty(self, key: str) -> Ty:
        info = self.reg.types.get(key)
        if info is not None:
            return self.self_type(info)
        mapping = {
            "String": STRING, "Int": INT, "Double": FLOAT, "Bool": BOOL,
            "Character": CHAR,
            "Array": Ty.array(Ty.generic("T")),
            "Dictionary": Ty.dict(Ty.generic("K"), Ty.generic("V")),
            "Set": Ty.set(Ty.generic("T")),
        }
        return mapping.get(key, UNKNOWN)

    def collect_extension(self, key: str, ext) -> None:
        info = self.reg.types.get(key)
        if info is not None and info.kind == "protocol":
            conformers = [ty for ty in self.reg.types.values()
                          if ty.kind != "protocol" and
                          key in ty.all_conformances()]
            for target in conformers:
                self.collect_extension_members(ext, target, key)
            return
        self.collect_extension_members(ext, info, key)

    def collect_extension_members(self, ext, info, key: str) -> None:
        self_ty = self.extension_self_ty(key) if info is None else \
            self.self_type(info)
        for name, fis in ext.methods.items():
            for fi in fis:
                params = self.job_params(fi)
                job = self.make_job("method", name, params, fi.body, fi.ret,
                                    has_self=True, self_ty=self_ty,
                                    type_info=info, mutating=fi.is_mutating,
                                    decl=fi.decl)
                self.register_method(info, job, name, fi, ext_key=key)
        for name, fis in ext.static_funcs.items():
            for fi in fis:
                params = self.job_params(fi)
                job = self.make_job("static", name, params, fi.body, fi.ret,
                                    type_info=info, is_static=True,
                                    is_operator=fi.is_operator,
                                    fixity=fi.operator_fixity,
                                    op_symbol=fi.name)
                if fi.is_operator:
                    self.register_operator(job)
                else:
                    self.register_static(info, job, name, ext_key=key)
        for name, cp in ext.computed.items():
            getter_body = []
            for acc in cp.accessors:
                if acc.kind == "get":
                    getter_body = acc.body
            g = self.make_job("prop_get", name, [], getter_body, cp.ty,
                              has_self=True, self_ty=self_ty, type_info=info)
            self.register_prop(info, name, g, None, ext_key=key)
        for si in ext.subscripts:
            self.collect_subscript(info, si, {}, self_ty=self_ty,
                                   ext_key=key)
        for fi in ext.inits:
            params = self.job_params(fi)
            job = self.make_job("init", "init", params, fi.body,
                                BOOL if fi.failable else VOID, has_self=True,
                                self_ty=self_ty, type_info=info,
                                failable=fi.failable, decl=fi.decl,
                                is_init=True)
            self.register_init(info, job)

    # ============================================================ register
    def target_desc(self, info, ext_key: str | None = None) -> str:
        if info is not None:
            return "&" + self.user_desc[info.name]
        mapping = {
            "String": "&SwimType_String", "Int": "&SwimType_Int",
            "Double": "&SwimType_Double", "Bool": "&SwimType_Bool",
            "Character": "&SwimType_Char", "Array": "&SwimType_Array",
            "Dictionary": "&SwimType_Dict", "Set": "&SwimType_Set",
        }
        return mapping.get(ext_key or "", "&SwimType_Any")

    def variadic_index(self, params: list) -> int:
        for i, p in enumerate(params):
            if p.is_variadic:
                return i
        return -1

    def param_tys(self, params: list) -> list:
        return [p.ty for p in params]

    def defaults_ref(self, job: Job) -> str:
        return job.defaults_cname if job.defaults_cname else "NULL"

    def register_method(self, info, job: Job, name: str, fi,
                        ext_key: str | None = None) -> None:
        target = self.target_desc(info, ext_key)
        labels = self.labels_for(job.params)
        arr = self.params_array(self.param_tys(job.params))
        self.registrations.append(
            "SwimRegisterMethod(%s, %s, %s, %s, %d, %s, %s, %d, %d, 0, 1);" % (
                target, c_string(name), c_string(labels), arr,
                len(job.params), job.cname, self.defaults_ref(job),
                self.variadic_index(job.params),
                1 if getattr(fi, "is_mutating", False) else 0))

    def register_static(self, info, job: Job, name: str,
                        ext_key: str | None = None) -> None:
        target = self.target_desc(info, ext_key)
        labels = self.labels_for(job.params)
        arr = self.params_array(self.param_tys(job.params))
        self.registrations.append(
            "SwimRegisterMethod(%s, %s, %s, %s, %d, %s, %s, %d, 0, 1, 0);" % (
                target, c_string(name), c_string(labels), arr,
                len(job.params), job.cname, self.defaults_ref(job),
                self.variadic_index(job.params)))

    def register_global(self, job: Job) -> None:
        labels = self.labels_for(job.params)
        arr = self.params_array(self.param_tys(job.params))
        gname = job.decl.name if job.decl is not None else job.cname
        self.registrations.append(
            "SwimRegisterGlobal(%s, %s, %s, %d, %s, %s, %d);" % (
                c_string(gname), c_string(labels), arr, len(job.params),
                job.cname, self.defaults_ref(job),
                self.variadic_index(job.params)))
        self.registration_needed = True

    def register_init(self, info, job: Job) -> None:
        labels = self.labels_for(job.params)
        self.init_jobs.setdefault(info.name, []).append(
            (labels, job.cname, job.failable,
             [p.ty for p in job.params]))
        target = self.target_desc(info)
        labels = self.labels_for(job.params)
        arr = self.params_array(self.param_tys(job.params))
        self.registrations.append(
            "SwimRegisterInit(%s, %s, %s, %d, %s, %s, %d, %d);" % (
                target, c_string(labels), arr, len(job.params), job.cname,
                self.defaults_ref(job), self.variadic_index(job.params),
                1 if job.failable else 0))

    def register_operator(self, job: Job) -> None:
        arr = self.params_array(self.param_tys(job.params))
        self.registrations.append(
            "SwimRegisterOperator(%s, %s, %s, %d, %s);" % (
                c_string(job.fixity or "infix"), c_string(job.op_symbol),
                arr, len(job.params), job.cname))
        self.registration_needed = True

    def register_prop(self, info, name: str, getter: Job | None,
                      setter: Job | None, ext_key: str | None = None) -> None:
        target = self.target_desc(info, ext_key)
        self.registrations.append(
            "SwimRegisterProp(%s, %s, %s, %s);" % (
                target, c_string(name),
                getter.cname if getter else "NULL",
                setter.cname if setter else "NULL"))

    def register_static_prop(self, info, name: str, getter: Job | None,
                             setter: Job | None) -> None:
        target = self.target_desc(info)
        self.registrations.append(
            "SwimRegisterStaticProp(%s, %s, %s, %s);" % (
                target, c_string(name),
                getter.cname if getter else "NULL",
                setter.cname if setter else "NULL"))

    def register_deinit(self, info, job: Job) -> None:
        target = self.target_desc(info)
        self.registrations.append(
            "SwimRegisterDeinit(%s, %s);" % (target, job.cname))

    def register_subscript(self, info, job: Job, name: str,
                           is_static: bool, ext_key=None) -> None:
        target = self.target_desc(info, ext_key)
        labels = ",".join("_" for _ in job.params)
        arr = self.params_array(self.param_tys(job.params))
        self.registrations.append(
            "SwimRegisterMethod(%s, %s, %s, %s, %d, %s, %s, %d, 0, %d, %d);" % (
                target, c_string(name), c_string(labels), arr,
                len(job.params), job.cname, self.defaults_ref(job),
                self.variadic_index(job.params), 1 if is_static else 0,
                0 if is_static else 1))

    # ============================================================ emission
    def emit(self) -> str:
        self.emit_user_types()
        self.emit_registration_function()
        self.emit_main()
        self.emit_functions()
        parts: list[str] = []
        parts.append("/* Generated by Swim %s -- direct C backend. */"
                     % __version__)
        parts.append('#include "swimrt.h"')
        if FERROUI_MODULE in self.native_modules:
            parts.append('#include "swimferroui.h"')
        parts.append("")
        for name in self.data_names:
            parts.append("static SwimType %s;" % name)
        parts.append("")
        for line in self.data_defs:
            parts.append(line)
        for name, definition in self.type_defs.items():
            parts.append("static SwimType %s = %s;" % (name, definition))
        parts.append("")
        for proto in self.fn_protos:
            parts.append(proto)
        parts.append("")
        parts.append(self.registration_code)
        parts.append("")
        for fn in self.fn_defs:
            parts.append(fn)
        parts.append("")
        parts.append(self.main_code)
        return "\n".join(parts) + "\n"

    def emit_user_types(self) -> None:
        for info in self.type_infos:
            cname = self.user_desc[info.name]
            fields = self.all_fields(info)
            field_defs = []
            for f, fty in fields:
                flags = ""
                if getattr(f, "weak", False):
                    flags = ", .weak = 1, .optional = %d" % (
                        1 if fty.is_optional else 0)
                elif getattr(f, "unowned", False):
                    flags = ", .unowned = 1, .optional = %d" % (
                        1 if fty.is_optional else 0)
                field_defs.append("{ .name = %s, .type = %s%s }" %
                                  (c_string(f.name), self.ty_desc(fty), flags))
            if field_defs:
                arr_name = self.new_data_name("fields")
                self.data_defs.append(
                    "static const SwimFieldDesc %s[] = { %s };" %
                    (arr_name, ", ".join(field_defs)))
                fields_ref = arr_name
            else:
                fields_ref = "NULL"
            cases_ref = "NULL"
            if info.kind == "enum":
                case_defs = []
                for ci, case in enumerate(info.enum_cases):
                    payload_defs = []
                    payload_names = []
                    for fname, fty in case.assoc:
                        payload_defs.append(
                            "{ .name = %s, .type = %s }" %
                            (c_string(fname), self.ty_desc(fty)))
                    payload_ref = "NULL"
                    if payload_defs:
                        pname = self.new_data_name("payload")
                        self.data_defs.append(
                            "static const SwimFieldDesc %s[] = { %s };" %
                            (pname, ", ".join(payload_defs)))
                        payload_ref = pname
                    case_defs.append(
                        "{ .name = %s, .payload_count = %d, .payload = %s }" %
                        (c_string(case.name), len(case.assoc), payload_ref))
                if case_defs:
                    carr = self.new_data_name("cases")
                    self.data_defs.append(
                        "static const SwimCaseDesc %s[] = { %s };" %
                        (carr, ", ".join(case_defs)))
                    cases_ref = carr
            parent = "NULL"
            if info.kind == "class" and info.superclass is not None:
                parent = "&" + self.user_desc[info.superclass.name]
            kind = {"struct": "SWIM_KIND_STRUCT", "class": "SWIM_KIND_CLASS",
                    "enum": "SWIM_KIND_ENUM"}[info.kind]
            self.type_defs[cname] = (
                '{ .name = %s, .kind = %s, .parent = %s, .field_count = %d, '
                '.fields = %s, .case_count = %d, .cases = %s, .is_error = %d, '
                '.is_generic = %d }' % (
                    c_string(info.name), kind, parent, len(fields), fields_ref,
                    len(info.enum_cases) if info.kind == "enum" else 0,
                    cases_ref, 1 if info.is_error else 0,
                    1 if info.is_generic else 0))

    def all_fields(self, info):
        """Flattened stored fields (base class fields first)."""
        chain = []
        cur = info
        while cur is not None:
            chain.append(cur)
            cur = cur.superclass
        chain.reverse()
        out = []
        for t in chain:
            env = {n: Ty.generic(n) for n, _ in t.generic_params}
            for f in t.fields:
                if f.is_static:
                    continue
                ty = substitute(f.ty, env) if env else f.ty
                if ty.kind == "unknown" and f.default is not None:
                    ty = self.infer_literal_ty(f.default)
                out.append((f, ty))
        return out

    def emit_registration_function(self) -> None:
        regs = list(self.registrations)
        for info in self.type_infos:
            regs.insert(0, "SwimRegisterType(&%s);" % self.user_desc[info.name])
        for info, case_name, raw_expr in self.raw_regs:
            regs.append("SwimRegisterEnumRaw(&%s, %s, %s);" % (
                self.user_desc[info.name], c_string(case_name),
                self.raw_value_code(raw_expr)))
        body = "\n".join("    " + r for r in regs)
        self.registration_code = (
            "static void __swim_register(void) {\n" + body + "\n}")

    def raw_value_code(self, expr) -> str:
        if isinstance(expr, bool):
            return "SwimBool(%s)" % ("1" if expr else "0")
        if isinstance(expr, int):
            return "SwimInt(%d)" % expr
        if isinstance(expr, str):
            return "SwimCStr(%s)" % c_string(expr)
        if isinstance(expr, A.IntLit):
            return "SwimInt(%s)" % expr.text.replace("_", "")
        if isinstance(expr, A.StringLit):
            text = "".join(p[1] for p in expr.parts if p[0] == "text")
            return "SwimCStr(%s)" % c_string(text)
        if isinstance(expr, A.BoolLit):
            return "SwimBool(%s)" % ("1" if expr.value else "0")
        return "SwimNone()"

    def emit_main(self) -> None:
        ctx = Ctx(self, "main", "main")
        self.ctx = ctx
        ctx.line("SWIM_FRAME_TEMP(__fr);")
        ctx.line("__fr = SwimFrameNew(NULL, 8);")
        ctx.line("SwimProgramStart(argc, argv);")
        ctx.line("SwimGlobalsInit(%d);" % self.global_count)
        ctx.line("__swim_register();")
        # static variable initialization (before top-level statements)
        for info, name, sv in self.static_inits:
            idx = self.static_slots[(info.name, name)]
            ctx.line("{")
            ctx.push_indent()
            if isinstance(sv, A.VarDecl):
                init = sv.init
                ty = self.resolve_ty(sv.ty) if sv.ty is not None else UNKNOWN
                if ty.kind == "unknown" and init is not None:
                    ty = self.infer_literal_ty(init)
            else:
                init = getattr(sv, "default", None)
                ty = sv.ty
                if ty.kind == "unknown" and init is not None:
                    ty = self.infer_literal_ty(init)
            if init is not None:
                value = self.gen_expr(init)
                value = self.coerce_temp(value, ty)
                ctx.line("SwimGlobalSet(%d, %s);" % (idx, value))
            ctx.pop_indent()
            ctx.line("}")
        # top-level items in source order
        for item in self.module.top_items:
            if isinstance(item, A.VarDecl):
                mark = len(ctx.temps)
                base = ctx.em.indent
                self.emit_top_var(item)
                for name, depth in ctx.temps[mark:]:
                    if depth == base:
                        ctx.line("SwimReleasePtr(&%s);" % name)
                del ctx.temps[mark:]
            elif isinstance(item, A.FuncDecl):
                continue
            elif isinstance(item, (A.StructDecl, A.ClassDecl, A.EnumDecl,
                                   A.ProtocolDecl, A.TypeAliasDecl,
                                   A.OperatorDecl, A.PrecedenceGroupDecl,
                                   A.ImportDecl, A.ExtensionDecl,
                                   A.InitDecl, A.DeinitDecl, A.VarDecl)):
                continue
            else:
                self.gen_stmt(item)
        if self.main_type_info is not None:
            ctx.line("SwimCallStatic(&%s, \"main\", \"\", 0, NULL);" %
                     self.user_desc[self.main_type_info.name])
        ctx.line("return 0;")
        body = "\n".join(ctx.em.lines)
        self.main_code = "int main(int argc, char** argv) {\n" + body + "\n}"

    def emit_top_var(self, decl: A.VarDecl) -> None:
        ctx = self.ctx
        idx = self.global_slots[decl.name]
        ty = self.resolve_ty(decl.ty) if decl.ty is not None else UNKNOWN
        if decl.init is not None:
            value = self.gen_expr(decl.init)
            if ty.kind != "unknown":
                value = self.coerce_temp(value, ty)
            ctx.line("SwimGlobalSet(%d, %s);" % (idx, value))
        elif decl.ty is not None:
            if ty.is_optional:
                ctx.line("SwimGlobalSet(%d, SwimNone());" % idx)
            else:
                ctx.line("SwimGlobalSet(%d, SwimVoid());" % idx)
        self.globals_ty = getattr(self, "globals_ty", {})
        self.globals_ty[decl.name] = ty

    # ---------------------------------------------------------- functions
    def emit_functions(self) -> None:
        i = 0
        while i < len(self.jobs):
            job = self.jobs[i]
            i += 1
            self.emit_job(job)

    def emit_job(self, job: Job) -> None:
        if job.kind == "defaults":
            self.emit_defaults(job)
            return
        ctx = Ctx(self, job.cname, job.kind, parent=job.parent_ctx,
                  ret_ty=job.ret_ty, self_ty=job.self_ty,
                  type_info=job.type_info, is_init=job.is_init,
                  failable=job.failable, is_static=job.is_static)
        ctx.proc_name = getattr(job, "display_name", None) or "main"
        if job.kind == "closure" and job.parent_ctx is not None:
            ctx.proc_name = getattr(job.parent_ctx, "proc_name", "main")
            ctx.type_info = job.parent_ctx.type_info
            ctx.has_self = job.parent_ctx.has_self
            ctx.self_ty = job.parent_ctx.self_ty
        self.ctx = ctx
        offset = 0
        if job.has_self:
            ctx.has_self = True
            ctx.bind("self", VarRef("frame", 0, 0, job.self_ty or ANY))
            ctx.nslots = 1
            offset = 1
        for i, p in enumerate(job.params):
            slot = ctx.new_slot()
            ref = VarRef("frame", slot, 0, p.ty, p)
            if p.is_inout:
                ref.kind = "inout"
            ctx.bind(p.name, ref)
        # write prologue
        ctx.line("SWIM_FRAME_TEMP(__fr);")
        ctx.line("__fr = SwimFrameNew(up, 8);")
        if job.has_self:
            ctx.line("SwimFrameSetRef(__fr, 0, argv[0]);")
        for i, p in enumerate(job.params):
            idx = i + offset
            if p.is_inout:
                ctx.line("SwimFrameSetRef(__fr, %d, argv[%d]);" %
                         (offset + i, idx))
            else:
                ctx.line("SwimFrameSet(__fr, %d, argv[%d]);" %
                         (offset + i, idx))
        # special bodies
        if getattr(job, "static_slot", None) is not None:
            if job.kind == "prop_get":
                ctx.line("return SwimRetainResult(SwimGlobalGet(%d));" %
                         job.static_slot)
            else:
                ref = ctx.lookup("newValue")
                value = self.read_var(ref) if ref is not None else "NULL"
                ctx.line("SwimGlobalSet(%d, %s);" % (job.static_slot, value))
                ctx.line("return SwimVoid();")
            self._append_fn(job, ctx)
            return
        if job.kind == "prop_get" and getattr(job, "observed_field", None):
            ctx.line("return SwimRetainResult(SwimGetFieldRaw(%s, %s));" % (
                self.read_self(), c_string(job.observed_field)))
        elif job.kind == "prop_set" and getattr(job, "observed_field", None):
            self.gen_observed_setter(job, ctx)
        elif job.kind == "init" and getattr(job, "synth_init", False):
            self.gen_synth_init(job, ctx)
        else:
            if job.is_init:
                for f, fty in self.all_fields(job.type_info):
                    if f.default is None:
                        continue
                    val = self.gen_expr(f.default)
                    val = self.coerce_temp(val, fty)
                    ctx.line("SwimInitField(%s, %s, %s);" %
                             (self.read_self(), c_string(f.name), val))
            body = job.body or []
            implicit = (job.ret_ty is not None and
                        not job.ret_ty.is_void and len(body) == 1 and
                        isinstance(body[0], A.ExprStmt) and
                        not isinstance(body[0].expr, A.AssignExpr) and
                        not getattr(job, "closure_has_return", False))
            if implicit:
                value = self.gen_expr(body[0].expr)
                value = self.coerce_temp(value, job.ret_ty)
                ctx.line("return SwimRetainResult(%s);" % value)
            else:
                self.gen_stmts(body, ctx)
                if job.is_init and job.failable:
                    ctx.line("return SwimBool(true);")
                elif job.ret_ty is not None and not job.ret_ty.is_void:
                    ctx.line("return SwimVoid();")
                else:
                    ctx.line("return SwimVoid();")
        self._append_fn(job, ctx)

    def _append_fn(self, job: Job, ctx: Ctx) -> None:
        text = ("static SwimValue %s(SwimFrame* up, int argc, SwimValue* argv) {\n"
                % job.cname) + "\n".join(ctx.em.lines) + "\n}"
        self.fn_protos.append(
            "static SwimValue %s(SwimFrame* up, int argc, SwimValue* argv);"
            % job.cname)
        self.fn_defs.append(text)

    def emit_defaults(self, job: Job) -> None:
        ctx = Ctx(self, job.cname, "defaults", type_info=job.type_info)
        self.ctx = ctx
        ctx.line("SWIM_FRAME_TEMP(__fr);")
        ctx.line("__fr = SwimFrameNew(up, 8);")
        for i, p in enumerate(job.params):
            ctx.bind(p.name, VarRef("frame", i, 0, p.ty, p))
            ctx.line("if (provided[%d] >= 0) {" % i)
            ctx.push_indent()
            ctx.line("SwimFrameSet(__fr, %d, argv[provided[%d]]);" % (i, i))
            ctx.pop_indent()
            ctx.line("} else {")
            ctx.push_indent()
            if p.default is not None:
                val = self.gen_expr(p.default)
                val = self.coerce_temp(val, p.ty)
                ctx.line("SwimFrameSet(__fr, %d, %s);" % (i, val))
            else:
                ctx.line("SwimFrameSet(__fr, %d, SwimNone());" % i)
            ctx.pop_indent()
            ctx.line("}")
            ctx.line("out[%d] = SwimRetainResult(SwimFrameGet(__fr, %d));" %
                     (i, i))
        text = ("static void %s(SwimFrame* up, int argc, SwimValue* argv, "
                "const int* provided, SwimValue* out) {\n" % job.cname) + \
               "\n".join(ctx.em.lines) + "\n}"
        self.fn_protos.append(
            "static void %s(SwimFrame* up, int argc, SwimValue* argv, "
            "const int* provided, SwimValue* out);" % job.cname)
        self.fn_defs.append(text)

    def gen_synth_init(self, job: Job, ctx: Ctx) -> None:
        info = job.type_info
        fields = self.all_fields(info)
        memberwise = info.kind == "struct" and not info.inits
        for f, fty in fields:
            value = None
            if memberwise:
                for p in job.params:
                    if p.name == f.name:
                        ref = ctx.lookup(p.name)
                        if ref is not None:
                            value = self.read_var(ref)
                        break
            if value is None:
                if f.default is None:
                    continue
                value = self.gen_expr(f.default)
            value = self.coerce_temp(value, fty)
            ctx.line("SwimInitField(%s, %s, %s);" % (
                self.read_self(), c_string(f.name), value))
        ctx.line("return SwimVoid();")

    def gen_observed_setter(self, job: Job, ctx: Ctx) -> None:
        fname = job.observed_field
        fty = job.params[0].ty if job.params else UNKNOWN
        old_slot = ctx.new_slot()
        if old_slot == 1:
            old_slot = ctx.new_slot()
        ctx.line("SwimFrameSet(__fr, %d, SwimGetFieldRaw(%s, %s));" %
                 (old_slot, self.read_self(), c_string(fname)))
        ctx.bind("oldValue", VarRef("frame", old_slot, 0, fty))
        setter_param = job.params[0] if job.params else JobParam(name="newValue")
        slot = 1
        if slot >= ctx.nslots:
            ctx.nslots = slot + 1
        ctx.bind("newValue", VarRef("frame", slot, 0, fty))
        ctx.bind(setter_param.name, VarRef("frame", slot, 0, fty))
        observers = getattr(job, "observers", [])
        for acc in observers:
            if acc.kind == "willSet":
                if acc.param:
                    ctx.bind(acc.param, VarRef("frame", slot, 0, fty))
                self.gen_stmts(acc.body, ctx)
        new_ref = ctx.lookup("newValue")
        cname = self.read_var(new_ref) if new_ref is not None else "NULL"
        ctx.line("SwimInitField(%s, %s, %s);" % (
            self.read_self(), c_string(fname), cname))
        for acc in observers:
            if acc.kind == "didSet":
                if acc.param:
                    ctx.bind(acc.param, VarRef("frame", old_slot, 0, fty))
                self.gen_stmts(acc.body, ctx)
        ctx.line("return SwimVoid();")

    # =========================================================== statements
    def gen_stmts(self, stmts: list, ctx: Ctx) -> None:
        self.ctx = ctx
        ctx.push_scope()
        has_defer = any(isinstance(s, A.DeferStmt) for s in stmts)
        scope_name = None
        if has_defer:
            scope_name = ctx.new_label("__d")
            ctx.line("SWIM_DEFFERRUN(%s);" % scope_name)
            ctx.line("SwimDeferBegin(&%s);" % scope_name)
            ctx.defer_scopes.append(scope_name)
        for stmt in stmts:
            if isinstance(stmt, A.FuncDecl):
                self.gen_local_func(stmt)
        for stmt in stmts:
            if isinstance(stmt, A.FuncDecl):
                continue
            self.gen_stmt(stmt)
        if scope_name is not None:
            ctx.defer_scopes.pop()
        ctx.pop_scope()

    def gen_block(self, stmts: list, ctx: Ctx) -> None:
        ctx.line("{")
        ctx.push_indent()
        self.gen_stmts(stmts, ctx)
        ctx.pop_indent()
        ctx.line("}")

    def gen_stmt(self, stmt) -> None:
        ctx = self.ctx
        mark = len(ctx.temps)
        base = ctx.em.indent
        self.gen_stmt_inner(stmt)
        block_scoped = (A.WhileStmt, A.RepeatStmt, A.ForStmt, A.SwitchStmt,
                        A.DoStmt, A.LabeledStmt)
        if not isinstance(stmt, block_scoped) and not isinstance(
                stmt, (A.ReturnStmt, A.BreakStmt, A.ContinueStmt, A.ThrowStmt)):
            for name, depth in ctx.temps[mark:]:
                if depth == base:
                    ctx.line("SwimReleasePtr(&%s);" % name)
        del ctx.temps[mark:]

    def gen_stmt_inner(self, stmt) -> None:
        ctx = self.ctx
        if isinstance(stmt, A.VarStmt):
            self.gen_var_stmt(stmt)
        elif isinstance(stmt, A.ExprStmt):
            expr = stmt.expr
            if isinstance(expr, A.AssignExpr):
                self.gen_assign(expr.target, expr.op, expr.value)
            else:
                self.gen_expr(expr)
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
            self.gen_switch(stmt, None)
        elif isinstance(stmt, A.ReturnStmt):
            self.gen_return(stmt)
        elif isinstance(stmt, A.BreakStmt):
            self.gen_break(stmt)
        elif isinstance(stmt, A.ContinueStmt):
            self.gen_continue(stmt)
        elif isinstance(stmt, A.ThrowStmt):
            val = self.gen_expr(stmt.expr)
            ctx.line("SwimThrow(%s);" % val)
        elif isinstance(stmt, A.DoStmt):
            self.gen_do(stmt)
        elif isinstance(stmt, A.DeferStmt):
            self.gen_defer(stmt)
        elif isinstance(stmt, A.LabeledStmt):
            self.gen_stmt_labeled(stmt)
        elif isinstance(stmt, A.FallthroughStmt):
            pass
        elif isinstance(stmt, (A.FuncDecl, A.VarDecl, A.ImportDecl)):
            pass
        else:
            self.error("unsupported statement: %r" % type(stmt).__name__, stmt)

    def declare_var(self, name: str, ty: Ty, node, key=None) -> VarRef:
        ctx = self.ctx
        if ctx.is_main and ctx.block_depth == 0 and name in self.global_slots:
            ref = VarRef("global", self.global_slots[name], 0, ty, node)
            ctx.bind(name, ref)
            return ref
        slot = ctx.slot_for_node(node, key)
        ref = VarRef("frame", slot, 0, ty, node)
        ctx.bind(name, ref)
        return ref

    def store_var(self, ref: VarRef, value: str) -> None:
        ctx = self.ctx
        if ref.kind == "global":
            ctx.line("SwimGlobalSet(%d, %s);" % (ref.slot, value))
        elif ref.kind == "inout":
            if ref.depth == 0:
                cell = "SwimFrameGet(__fr, %d)" % ref.slot
            else:
                cell = "SwimFrameGet(SwimFrameUp(__fr, %d), %d)" % (
                    ref.depth, ref.slot)
            ctx.line("SwimFrameSet((SwimFrame*)%s, 0, %s);" % (cell, value))
        elif ref.kind == "static":
            ctx.line("SwimSetStatic(&%s, %s, %s);" % (
                self.user_desc[ref.type_info.name], c_string(ref.decl), value))
        else:
            frame = "__fr" if ref.depth == 0 else \
                "SwimFrameUp(__fr, %d)" % ref.depth
            ctx.line("SwimFrameSet(%s, %d, %s);" % (frame, ref.slot, value))

    def read_var(self, ref: VarRef) -> str:
        if ref.kind == "global":
            return "SwimGlobalGet(%d)" % ref.slot
        if ref.kind == "temp":
            return ref.cname
        if ref.kind == "static":
            return "SwimGetStatic(&%s, %s)" % (
                self.user_desc[ref.type_info.name], c_string(ref.decl))
        if ref.kind == "inout":
            if ref.depth == 0:
                cell = "SwimFrameGet(__fr, %d)" % ref.slot
            else:
                cell = "SwimFrameGet(SwimFrameUp(__fr, %d), %d)" % (
                    ref.depth, ref.slot)
            return "SwimFrameGet((SwimFrame*)%s, 0)" % cell
        if ref.depth == 0:
            return "SwimFrameGet(__fr, %d)" % ref.slot
        return "SwimFrameGet(SwimFrameUp(__fr, %d), %d)" % (ref.depth, ref.slot)

    def lookup_var(self, name: str) -> VarRef | None:
        ctx = self.ctx
        depth = 0
        cur = ctx
        while cur is not None:
            ref = cur.lookup(name)
            if ref is not None:
                if ref.kind == "frame":
                    return VarRef("frame", ref.slot, ref.depth + depth, ref.ty,
                                  ref.decl)
                return ref
            cur = cur.parent
            depth += 1
        return None

    def lookup_global(self, name: str) -> VarRef | None:
        if name in self.global_slots:
            ty = getattr(self, "globals_ty", {}).get(name, UNKNOWN)
            return VarRef("global", self.global_slots[name], 0, ty)
        return None

    def gen_var_stmt(self, stmt: A.VarStmt) -> None:
        ctx = self.ctx
        if stmt.names:
            val = self.gen_expr(stmt.init)
            for i, name in enumerate(stmt.names):
                if name == "_":
                    continue
                elem = ctx.new_temp()
                ctx.line("%s = SwimTupleGet(%s, %d);" % (elem, val, i))
                ref = self.declare_var(name, UNKNOWN, stmt,
                                       key=(id(stmt), i))
                self.store_var(ref, elem)
            return
        if stmt.name == "_":
            self.gen_expr(stmt.init)
            return
        ty = self.resolve_ty(stmt.ty) if stmt.ty is not None else UNKNOWN
        if stmt.init is None:
            value = "SwimNone()" if ty.is_optional else "SwimVoid()"
            ref = self.declare_var(stmt.name, ty, stmt)
            self.store_var(ref, value)
            return
        value = self.gen_expr(stmt.init, ty)
        if ty.kind not in ("unknown", "any", "generic"):
            value = self.coerce_temp(value, ty)
        ref = self.declare_var(stmt.name, ty, stmt)
        self.store_var(ref, value)

    # ------------------------------------------------------------ control
    def gen_if(self, stmt: A.IfStmt) -> None:
        ctx = self.ctx
        self.emit_cond_chain(list(stmt.conditions),
                             lambda: self.gen_block(stmt.then_body, ctx),
                             lambda: (self.gen_block(stmt.else_body, ctx)
                                      if stmt.else_body else None))

    def gen_guard(self, stmt: A.GuardStmt) -> None:
        ctx = self.ctx
        for cond in stmt.conditions:
            if isinstance(cond, A.CondExpr):
                val = self.gen_expr(cond.expr)
                ctx.line("if (!SwimTruthy(%s)) {" % val)
                ctx.push_indent()
                self.gen_block(stmt.else_body, ctx)
                ctx.pop_indent()
                ctx.line("}")
            elif isinstance(cond, A.CondBinding):
                val = self.gen_expr(cond.expr)
                ctx.line("if (!SwimIsSome(%s)) {" % val)
                ctx.push_indent()
                self.gen_block(stmt.else_body, ctx)
                ctx.pop_indent()
                ctx.line("}")
                slot = ctx.slot_for_node(cond)
                ctx.line("SwimFrameSet(__fr, %d, SwimOptionalGet(%s));" %
                         (slot, val))
                if cond.name != "_":
                    ctx.bind(cond.name, VarRef("frame", slot, 0, UNKNOWN))
            elif isinstance(cond, A.CaseCond):
                subj = self.gen_expr(cond.expr)
                cond_code, bindings = self.pattern_condition(cond.pattern, subj)
                ctx.line("if (!(%s)) {" % cond_code)
                ctx.push_indent()
                self.gen_block(stmt.else_body, ctx)
                ctx.pop_indent()
                ctx.line("}")
                for name, slot in bindings:
                    ctx.line("SwimFrameSet(__fr, %d, %s);" % (
                        slot, self.binding_expr(cond.pattern, name, subj)))
                    ctx.bind(name, VarRef("frame", slot, 0, UNKNOWN))
            else:
                self.error("unsupported guard condition", cond)

    def emit_cond_chain(self, conds: list, on_success, on_fail) -> None:
        ctx = self.ctx
        if not conds:
            on_success()
            return
        cond = conds[0]
        rest = conds[1:]
        if isinstance(cond, A.CondExpr):
            val = self.gen_expr(cond.expr)
            ctx.line("if (SwimTruthy(%s)) {" % val)
            ctx.push_indent()
            self.emit_cond_chain(rest, on_success, on_fail)
            ctx.pop_indent()
            ctx.line("} else {")
            ctx.push_indent()
            on_fail()
            ctx.pop_indent()
            ctx.line("}")
            return
        if isinstance(cond, A.CondBinding):
            val = self.gen_expr(cond.expr)
            ctx.line("if (SwimIsSome(%s)) {" % val)
            ctx.push_indent()
            ctx.push_scope()
            slot = ctx.slot_for_node(cond)
            if cond.name != "_":
                ctx.bind(cond.name, VarRef("frame", slot, 0, UNKNOWN, cond))
            ctx.line("SwimFrameSet(__fr, %d, SwimOptionalGet(%s));" %
                     (slot, val))
            self.emit_cond_chain(rest, on_success, on_fail)
            ctx.pop_scope()
            ctx.pop_indent()
            ctx.line("} else {")
            ctx.push_indent()
            on_fail()
            ctx.pop_indent()
            ctx.line("}")
            return
        if isinstance(cond, A.CaseCond):
            self.emit_case_condition(cond, rest, on_success, on_fail)
            return
        self.error("unsupported condition", cond)

    def emit_case_condition(self, cond: A.CaseCond, rest: list, on_success,
                            on_fail) -> None:
        ctx = self.ctx
        subj = self.gen_expr(cond.expr)
        cond_code, bindings = self.pattern_condition(cond.pattern, subj)
        ctx.push_scope()
        for name, value_slot in bindings:
            ctx.bind(name, VarRef("frame", value_slot, 0, UNKNOWN))
        ctx.line("if (%s) {" % cond_code)
        ctx.push_indent()
        for name, value_slot in bindings:
            ctx.line("SwimFrameSet(__fr, %d, %s);" %
                     (value_slot, self.binding_expr(cond.pattern, name, subj)))
        self.emit_cond_chain(rest, on_success, on_fail)
        ctx.pop_indent()
        ctx.line("} else {")
        ctx.push_indent()
        on_fail()
        ctx.pop_indent()
        ctx.line("}")
        ctx.pop_scope()

    def binding_expr(self, pattern, name: str, subj: str) -> str:
        if isinstance(pattern, A.BindingPattern):
            if pattern.optional_unwrap:
                return "SwimOptionalGet(%s)" % subj
            return subj
        if isinstance(pattern, A.EnumCasePattern):
            for i, (label, bname, kind) in enumerate(pattern.bindings):
                if bname == name:
                    return "SwimEnumPayload(%s, %s, %d)" % (
                        subj, c_string(self.case_leaf(pattern.case_name)), i)
        return subj

    def pattern_condition(self, pattern, subj: str):
        ctx = self.ctx
        bindings = []
        if isinstance(pattern, A.WildcardPattern):
            return "1", bindings
        if isinstance(pattern, A.LiteralPattern):
            val = self.gen_expr(pattern.expr)
            return "SwimTruthy(SwimEqualsValue(%s, %s))" % (subj, val), bindings
        if isinstance(pattern, A.RangePattern):
            lo = self.gen_expr(pattern.low)
            hi = self.gen_expr(pattern.high)
            cmp_lo = "SwimCompareValues(%s, %s) >= 0" % (subj, lo)
            cmp_hi = ("SwimCompareValues(%s, %s) <= 0" if pattern.closed
                      else "SwimCompareValues(%s, %s) < 0")
            return "(%s && %s)" % (cmp_lo, cmp_hi % (subj, hi)), bindings
        if isinstance(pattern, A.IsPattern):
            ty = self.resolve_ty(pattern.ty)
            return "SwimTruthy(SwimCast(%s, %s, 0))" % (
                subj, self.ty_desc(ty)), bindings
        if isinstance(pattern, A.BindingPattern):
            if pattern.name != "_":
                slot = ctx.new_slot()
                bindings.append((pattern.name, slot))
            if pattern.optional_unwrap:
                return "SwimIsSome(%s)" % subj, bindings
            return "1", bindings
        if isinstance(pattern, A.EnumCasePattern):
            cond = "SwimTruthy(SwimEnumIs(%s, %s))" % (
                subj, c_string(self.case_leaf(pattern.case_name)))
            for i, (label, bname, kind) in enumerate(pattern.bindings):
                if bname and bname != "_":
                    slot = ctx.new_slot()
                    bindings.append((bname, slot))
            if pattern.optional_unwrap:
                cond = "(%s && SwimIsSome(%s))" % (cond, subj)
            return cond, bindings
        return "1", bindings

    def gen_while(self, stmt: A.WhileStmt, label: str | None = None) -> None:
        ctx = self.ctx
        brk = ctx.new_label("__brk")
        cont = ctx.new_label("__cont")
        ctx.breaks.append((brk, cont, label))
        ctx.line("for (;;) {")
        ctx.push_indent()
        self.emit_cond_chain(list(stmt.conditions),
                             lambda: (self.gen_block(stmt.body, ctx),
                                      ctx.line("%s: ;" % cont)),
                             lambda: ctx.line("break;"))
        ctx.pop_indent()
        ctx.line("}")
        ctx.line("%s: ;" % brk)
        ctx.breaks.pop()

    def gen_repeat(self, stmt: A.RepeatStmt, label: str | None = None) -> None:
        ctx = self.ctx
        brk = ctx.new_label("__brk")
        cont = ctx.new_label("__cont")
        ctx.breaks.append((brk, cont, label))
        ctx.line("for (;;) {")
        ctx.push_indent()
        self.gen_block(stmt.body, ctx)
        ctx.line("%s: ;" % cont)
        cond = self.gen_expr(stmt.condition)
        ctx.line("if (!SwimTruthy(%s)) break;" % cond)
        ctx.pop_indent()
        ctx.line("}")
        ctx.line("%s: ;" % brk)
        ctx.breaks.pop()

    def gen_for(self, stmt: A.ForStmt, label: str | None = None) -> None:
        ctx = self.ctx
        brk = ctx.new_label("__brk")
        cont = ctx.new_label("__cont")
        ctx.line("{")
        ctx.push_indent()
        ctx.push_scope()
        seq = self.gen_expr(stmt.iterable)
        it = ctx.new_label("__it")
        ctx.line("SWIM_ITER_TEMP(%s);" % it)
        ctx.line("%s = SwimIterate(%s);" % (it, seq))
        elem = ctx.new_temp()
        ctx.line("while (SwimIterNext(%s, &%s)) {" % (it, elem))
        ctx.push_indent()
        ctx.breaks.append((brk, cont, label))
        names = list(stmt.names)
        slots = []
        for i, name in enumerate(names):
            slot = ctx.slot_for_node(stmt, key=(id(stmt), i))
            slots.append(slot)
            if name != "_":
                ctx.bind(name, VarRef("frame", slot, 0, UNKNOWN))
        if len(names) == 1:
            ctx.line("SwimFrameSet(__fr, %d, %s);" % (slots[0], elem))
        else:
            for i, slot in enumerate(slots):
                ctx.line("SwimFrameSet(__fr, %d, SwimTupleGet(%s, %d));" %
                         (slot, elem, i))
        if stmt.pattern is not None:
            cond_code, bindings = self.pattern_condition(stmt.pattern, elem)
            for name, slot in bindings:
                ctx.bind(name, VarRef("frame", slot, 0, UNKNOWN))
            ctx.line("if (%s) {" % cond_code)
            ctx.push_indent()
            for name, slot in bindings:
                ctx.line("SwimFrameSet(__fr, %d, %s);" % (
                    slot, self.binding_expr(stmt.pattern, name, elem)))
            if stmt.where_cond is not None:
                cond = self.gen_expr(stmt.where_cond)
                ctx.line("if (SwimTruthy(%s)) {" % cond)
                ctx.push_indent()
                self.gen_block(stmt.body, ctx)
                ctx.pop_indent()
                ctx.line("}")
            else:
                self.gen_block(stmt.body, ctx)
            ctx.pop_indent()
            ctx.line("}")
        elif stmt.where_cond is not None:
            cond = self.gen_expr(stmt.where_cond)
            ctx.line("if (SwimTruthy(%s)) {" % cond)
            ctx.push_indent()
            self.gen_block(stmt.body, ctx)
            ctx.pop_indent()
            ctx.line("}")
        else:
            self.gen_block(stmt.body, ctx)
        ctx.line("%s: ;" % cont)
        ctx.pop_indent()
        ctx.line("}")
        ctx.breaks.pop()
        ctx.pop_scope()
        ctx.pop_indent()
        ctx.line("%s: ;" % brk)
        ctx.line("}")

    def gen_return(self, stmt: A.ReturnStmt) -> None:
        ctx = self.ctx
        if ctx.failable and isinstance(stmt.expr, A.NilLit):
            ctx.line("return SwimBool(false);")
            return
        if ctx.failable and stmt.expr is None:
            ctx.line("return SwimBool(true);")
            return
        if stmt.expr is None:
            ctx.line("return SwimVoid();")
            return
        value = self.gen_expr(stmt.expr, ctx.ret_ty)
        ret = ctx.ret_ty
        if ret is not None and not ret.is_void and not ctx.failable:
            value = self.coerce_temp(value, ret)
        ctx.line("return SwimRetainResult(%s);" % value)

    def gen_break(self, stmt: A.BreakStmt) -> None:
        ctx = self.ctx
        for brk, cont, label in reversed(ctx.breaks):
            if stmt.label is None or label == stmt.label:
                ctx.line("goto %s;" % brk)
                return
        self.error("'break' outside of a loop or switch", stmt)

    def gen_continue(self, stmt: A.ContinueStmt) -> None:
        ctx = self.ctx
        for brk, cont, label in reversed(ctx.breaks):
            if cont is None:
                continue
            if stmt.label is None or label == stmt.label:
                ctx.line("goto %s;" % cont)
                return
        self.error("'continue' outside of a loop", stmt)

    def gen_stmt_labeled(self, stmt: A.LabeledStmt) -> None:
        inner = stmt.stmt
        if isinstance(inner, A.WhileStmt):
            self.gen_while(inner, stmt.label)
        elif isinstance(inner, A.RepeatStmt):
            self.gen_repeat(inner, stmt.label)
        elif isinstance(inner, A.ForStmt):
            self.gen_for(inner, stmt.label)
        elif isinstance(inner, A.SwitchStmt):
            self.gen_switch(inner, stmt.label)
        else:
            self.gen_stmt(inner)

    def gen_defer(self, stmt: A.DeferStmt) -> None:
        ctx = self.ctx
        job = self.make_closure_job(stmt.body, [], VOID, None)
        if not ctx.defer_scopes:
            scope = ctx.new_label("__d")
            ctx.line("SWIM_DEFFERRUN(%s);" % scope)
            ctx.line("SwimDeferBegin(&%s);" % scope)
            ctx.defer_scopes.append(scope)
        ctx.line("SwimDeferAdd(&%s, SwimMakeClosure(%s, __fr));" %
                 (ctx.defer_scopes[-1], job.cname))

    def make_closure_job(self, body: list, params: list, ret_ty: Ty,
                         node, implicit: bool = False) -> Job:
        job = Job(cname=self.new_cname("closure"), kind="closure",
                  params=list(params), body=body or [], ret_ty=ret_ty or VOID,
                  parent_ctx=self.ctx)
        job.closure_has_return = not implicit
        saved = self.ctx
        self.emit_job(job)
        self.ctx = saved
        return job

    def max_implicit_param(self, body: list) -> int:
        highest = -1

        def walk(node):
            nonlocal highest
            if isinstance(node, A.Ident):
                if node.name.startswith("$") and node.name[1:].isdigit():
                    highest = max(highest, int(node.name[1:]))
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)
            elif hasattr(node, "__dataclass_fields__"):
                for fname in node.__dataclass_fields__:
                    walk(getattr(node, fname, None))

        walk(body)
        return highest + 1

    def gen_do(self, stmt: A.DoStmt) -> None:
        ctx = self.ctx
        tf = ctx.new_label("__tf")
        ctx.line("{")
        ctx.push_indent()
        ctx.line("SwimTryFrame %s; SwimTryBegin(&%s);" % (tf, tf))
        ctx.line("if (setjmp(%s.buf) == 0) {" % tf)
        ctx.push_indent()
        self.gen_block(stmt.body, ctx)
        ctx.line("SwimTryEnd(&%s);" % tf)
        ctx.pop_indent()
        ctx.line("} else {")
        ctx.push_indent()
        err = ctx.new_temp()
        ctx.line("%s = %s.error;" % (err, tf))
        emitted = False
        has_default = False
        for clause in stmt.catches:
            cond = self.catch_condition(clause, err)
            bind_specs = []
            for pat in clause.patterns:
                if isinstance(pat, A.EnumCasePattern):
                    code, binds = self.pattern_condition(pat, err)
                    bind_specs.extend((pat, name, slot)
                                      for name, slot in binds)
            if cond is None:
                has_default = True
                if emitted:
                    ctx.line("else {")
                else:
                    ctx.line("if (1) {")
            else:
                ctx.line("%s (%s) {" % ("if" if not emitted else "else if",
                                        cond))
            ctx.push_indent()
            ctx.push_scope()
            if clause.name:
                slot = ctx.slot_for_node(clause)
                ctx.bind(clause.name, VarRef("frame", slot, 0, UNKNOWN))
                ctx.line("SwimFrameSet(__fr, %d, %s);" % (slot, err))
            for pat, name, slot in bind_specs:
                ctx.bind(name, VarRef("frame", slot, 0, UNKNOWN))
                ctx.line("SwimFrameSet(__fr, %d, %s);" % (
                    slot, self.binding_expr(pat, name, err)))
            self.gen_block(clause.body, ctx)
            ctx.pop_scope()
            ctx.pop_indent()
            ctx.line("}")
            emitted = True
            if cond is None:
                break
        if not has_default:
            ctx.line("SwimThrow(%s);" % err)
        ctx.pop_indent()
        ctx.line("}")
        ctx.pop_indent()
        ctx.line("}")

    def case_leaf(self, name: str) -> str:
        return name.rsplit(".", 1)[-1]

    def catch_condition(self, clause: A.CatchClause, err: str) -> str | None:
        if clause.is_default or not clause.patterns:
            return None
        parts = []
        for pat in clause.patterns:
            if isinstance(pat, A.EnumCasePattern):
                parts.append("SwimTruthy(SwimEnumIs(%s, %s))" %
                             (err, c_string(self.case_leaf(pat.case_name))))
            elif isinstance(pat, A.TypeNode):
                ty = self.resolve_ty(pat)
                parts.append("SwimTruthy(SwimCast(%s, %s, 0))" %
                             (err, self.ty_desc(ty)))
            else:
                parts.append("1")
        return " || ".join(parts) if parts else None

    # ------------------------------------------------------------- switch
    def gen_switch(self, stmt: A.SwitchStmt, label: str | None) -> None:
        ctx = self.ctx
        brk = ctx.new_label("__swbrk")
        ctx.line("{")
        ctx.push_indent()
        subj = self.gen_expr(stmt.subject)
        matched = ctx.new_label("__matched")
        ctx.line("int %s = 0;" % matched)
        ctx.breaks.append((brk, None, label))
        cases = stmt.cases
        for idx, case in enumerate(cases):
            if case.is_default:
                ctx.line("if (!%s) {" % matched)
                ctx.push_indent()
                self.gen_case_body(cases, idx)
                ctx.pop_indent()
                ctx.line("}")
                continue
            ctx.line("if (!%s) {" % matched)
            ctx.push_indent()
            ctx.push_scope()
            evaluated = [(pat, self.pattern_condition(pat, subj))
                         for pat in case.patterns]
            for pat, (cond_code, bindings) in evaluated:
                for name, slot in bindings:
                    if ctx.lookup(name) is None:
                        ctx.bind(name, VarRef("frame", slot, 0, UNKNOWN))
            first = True
            for pat, (cond_code, bindings) in evaluated:
                ctx.line("%s (!%s && (%s)) {" % (
                    "if" if first else "else if", matched, cond_code))
                first = False
                ctx.push_indent()
                for name, slot in bindings:
                    ctx.line("SwimFrameSet(__fr, %d, %s);" % (
                        slot, self.binding_expr(pat, name, subj)))
                ctx.line("%s = 1;" % matched)
                ctx.pop_indent()
                ctx.line("}")
            if case.where_cond is not None:
                ctx.line("if (%s) {" % matched)
                ctx.push_indent()
                where = self.gen_expr(case.where_cond)
                ctx.line("if (!SwimTruthy(%s)) %s = 0;" % (where, matched))
                ctx.pop_indent()
                ctx.line("}")
            ctx.line("if (%s) {" % matched)
            ctx.push_indent()
            self.gen_case_body(cases, idx)
            ctx.pop_indent()
            ctx.line("}")
            ctx.pop_scope()
            ctx.pop_indent()
            ctx.line("}")
        ctx.line("%s: ;" % brk)
        ctx.breaks.pop()
        ctx.pop_indent()
        ctx.line("}")

    def gen_case_body(self, cases: list, idx: int) -> None:
        if idx >= len(cases):
            return
        case = cases[idx]
        body = list(case.body)
        fallthrough = False
        if body and isinstance(body[-1], A.FallthroughStmt):
            body = body[:-1]
            fallthrough = True
        self.gen_stmts(body, self.ctx)
        if fallthrough:
            self.gen_case_body(cases, idx + 1)

    # ========================================================== expressions
    def gen_expr(self, node, expected: Ty | None = None) -> str:
        ctx = self.ctx
        t = ctx.new_temp()
        self.gen_expr_into(node, t, expected)
        return t

    def gen_expr_into(self, node, dst: str, expected: Ty | None = None) -> None:
        ctx = self.ctx
        if isinstance(node, A.BinaryExpr) and node.op in ("&&", "||"):
            left = self.gen_expr(node.left)
            ctx.line("if (SwimTruthy(%s)) {" % left)
            ctx.push_indent()
            if node.op == "&&":
                right = self.gen_expr(node.right)
                ctx.line("%s = SwimBool(SwimUnboxBool(%s));" % (dst, right))
            else:
                ctx.line("%s = SwimBool(true);" % dst)
            ctx.pop_indent()
            ctx.line("} else {")
            ctx.push_indent()
            if node.op == "&&":
                ctx.line("%s = SwimBool(false);" % dst)
            else:
                right = self.gen_expr(node.right)
                ctx.line("%s = SwimBool(SwimUnboxBool(%s));" % (dst, right))
            ctx.pop_indent()
            ctx.line("}")
            return
        if isinstance(node, A.TernaryExpr):
            cond = self.gen_expr(node.cond)
            ctx.line("if (SwimTruthy(%s)) {" % cond)
            ctx.push_indent()
            self.gen_expr_into(node.then_expr, dst, expected)
            ctx.pop_indent()
            ctx.line("} else {")
            ctx.push_indent()
            self.gen_expr_into(node.else_expr, dst, expected)
            ctx.pop_indent()
            ctx.line("}")
            return
        if isinstance(node, A.TryExpr):
            if node.mode == "try":
                self.gen_expr_into(node.expr, dst, expected)
                return
            self.gen_try_expr(node, dst)
            return
        if isinstance(node, A.CallExpr):
            self.gen_call(node, dst, expected)
            return
        if isinstance(node, A.ClosureExpr):
            self.gen_closure_into(node, dst)
            return
        code = self.expr_code(node, expected)
        ctx.line("%s = %s;" % (dst, code))

    def gen_try_expr(self, node: A.TryExpr, dst: str) -> None:
        ctx = self.ctx
        tf = ctx.new_label("__tf")
        ctx.line("{")
        ctx.push_indent()
        ctx.line("SwimTryFrame %s; SwimTryBegin(&%s);" % (tf, tf))
        ctx.line("if (setjmp(%s.buf) == 0) {" % tf)
        ctx.push_indent()
        inner = self.gen_expr(node.expr)
        ctx.line("SwimTryEnd(&%s);" % tf)
        if node.mode == "try?":
            ctx.line("%s = SwimSome(%s);" % (dst, inner))
        else:
            ctx.line("%s = SwimRetainResult(%s);" % (dst, inner))
        ctx.pop_indent()
        ctx.line("} else {")
        ctx.push_indent()
        if node.mode == "try?":
            ctx.line("%s = SwimNone();" % dst)
        else:
            ctx.line("SwimFatal(\"error thrown by 'try!'\");")
        ctx.pop_indent()
        ctx.line("}")
        ctx.pop_indent()
        ctx.line("}")

    def expected_arg_type(self, expectations, label: str, index: int):
        if not expectations:
            return None
        for position, (param_label, ty, variadic) in enumerate(expectations):
            if label != "_" and param_label == label:
                return ty
        if index < len(expectations):
            ty = expectations[index][1]
            return ty
        return None

    def gen_call_args(self, args: list, trailing, expectations=None):
        ctx = self.ctx
        labels: list[str] = []
        vals: list[str] = []
        posts = []
        for index, arg in enumerate(args):
            label = arg.label if arg.label is not None else "_"
            expr = arg.expr
            if isinstance(expr, A.UnaryExpr) and expr.op == "&":
                target = expr.operand
                cell = ctx.new_temp()
                ctx.line("%s = SwimFrameNew(NULL, 1);" % cell)
                cur = self.read_lvalue(target)
                ctx.line("SwimFrameSet((SwimFrame*)%s, 0, %s);" % (cell, cur))
                vals.append(cell)
                labels.append(label)
                posts.append(self.make_writeback(target, cell))
            else:
                expected_ty = self.expected_arg_type(expectations, label, index)
                if expected_ty is not None and expected_ty.kind == "func":
                    # A closure types its own parameters; leave it alone.
                    expected_ty = None
                vals.append(self.gen_expr(expr, expected_ty))
                labels.append(label)
        if trailing is not None:
            vals.append(self.gen_closure(trailing))
            labels.append("*")
        return labels, vals, posts

    def make_writeback(self, target, cell: str):
        ctx = self.ctx

        def writeback() -> None:
            value = "SwimFrameGet((SwimFrame*)%s, 0)" % cell
            if isinstance(target, A.Ident):
                ref = self.lookup_var(target.name)
                if ref is None:
                    ref = self.lookup_global(target.name)
                if ref is None:
                    self.error("cannot pass '%s' as inout" % target.name,
                               target)
                self.store_var(ref, value)
            elif isinstance(target, A.MemberExpr):
                recv = self.gen_expr(target.base)
                ctx.line("SwimSetMember(%s, %s, %s);" %
                         (recv, c_string(target.name), value))
            elif isinstance(target, A.SubscriptExpr):
                base = self.gen_expr(target.base)
                argvals = [self.gen_expr(a.expr) for a in target.args]
                ctx.line("SwimSubscriptSet(%s, %d, %s, %s);" % (
                    base, len(argvals), self.argv(argvals), value))
            else:
                self.error("unsupported inout argument", target)

        return writeback

    def argv(self, vals: list[str]) -> str:
        if not vals:
            return "NULL"
        return "(SwimValue[]){ %s }" % ", ".join(vals)

    def call_code(self, node: A.CallExpr, labels: list[str], vals: list[str],
                  posts) -> str:
        lbl = ",".join(labels)
        argc = len(vals)
        argv = self.argv(vals)
        callee = node.callee
        if isinstance(callee, A.MemberExpr):
            base = callee.base
            if not isinstance(base, (A.SelfExpr, A.SuperExpr)) and \
                    not (isinstance(base, A.Ident) and
                         self.lookup_var(base.name) is not None):
                ty = self.type_name_of_expr(base)
                if ty is not None and ty.kind == "named":
                    nested_name = f"{ty.name}.{callee.name}"
                    nested = self.reg.types.get(nested_name)
                    if nested is not None:
                        return self.construct_code(
                            self.self_type(nested), nested.name, lbl, argc,
                            argv)
                if ty is not None:
                    desc = self.ty_desc(ty)
                    if ty.kind == "named":
                        info = self.reg.types.get(ty.name)
                        if info is not None and info.kind == "enum" and \
                                info.enum_case(callee.name) is not None:
                            return "SwimEnumCase(%s, %s, %d, %s);" % (
                                desc, c_string(callee.name), argc, argv)
                    return "SwimCallStatic(%s, %s, %s, %d, %s);" % (
                        desc, c_string(callee.name), c_string(lbl), argc, argv)
            if isinstance(base, A.SuperExpr):
                return self.super_call(node, labels, vals)
            if callee.optional:
                recv = self.gen_expr(base)
                return "SwimOptionalCall(%s, %s, %s, %d, %s);" % (
                    recv, c_string(callee.name), c_string(lbl), argc, argv)
            recv = self.gen_expr(base)
            return "SwimCallMethod(%s, %s, %s, %d, %s);" % (
                recv, c_string(callee.name), c_string(lbl), argc, argv)
        if isinstance(callee, A.CaseRefExpr):
            return "SwimEnumCaseAny(%s, %d, %s);" % (
                c_string(callee.name), argc, argv)
        if isinstance(callee, A.Ident):
            name = callee.name
            if name in FERROUI_FUNCS:
                return self.native_call_code(name, labels, vals, callee)
            ref = self.lookup_var(name)
            if ref is not None:
                if ref.kind == "localfn" and ref.decl is not None:
                    ordered = self.reorder_local_args(ref.decl, node, vals,
                                                      labels)
                    return "SwimCallValue(%s, %d, %s);" % (
                        self.read_var(ref), len(ordered),
                        self.argv(ordered))
                return "SwimCallValue(%s, %d, %s);" % (
                    self.read_var(ref), argc, argv)
            ty = self.ty_of_name(name)
            if ty is not None:
                return self.construct_code(ty, name, lbl, argc, argv)
            inst = self.instance_member_owner(name)
            if inst is not None and inst.methods.get(name):
                return "SwimCallMethod(%s, %s, %s, %d, %s);" % (
                    self.read_self(), c_string(name), c_string(lbl), argc,
                    argv)
            static_ty = self.static_func_owner(name)
            if static_ty is not None:
                return "SwimCallStatic(&%s, %s, %s, %d, %s);" % (
                    self.user_desc[static_ty.name], c_string(name),
                    c_string(lbl), argc, argv)
            if self.reg.find_functions(name) or name in BUILTIN_FUNCS:
                return "SwimCallGlobal(%s, %s, %d, %s);" % (
                    c_string(name), c_string(lbl), argc, argv)
            if self.ctx.has_self:
                return "SwimCallMethod(%s, %s, %s, %d, %s);" % (
                    self.read_self(), c_string(name), c_string(lbl), argc,
                    argv)
            gref = self.lookup_global(name)
            if gref is not None:
                return "SwimCallValue(%s, %d, %s);" % (
                    self.read_var(gref), argc, argv)
            return "SwimCallGlobal(%s, %s, %d, %s);" % (
                c_string(name), c_string(lbl), argc, argv)
        if isinstance(callee, A.SubscriptExpr) and not callee.args:
            elem_ty = self.type_name_of_expr(callee.base)
            if elem_ty is not None:
                return "SwimArrayInit(%s, %s, %d, %s);" % (
                    self.ty_desc(elem_ty), c_string(lbl), argc, argv)
        if isinstance(callee, A.GenericRefExpr):
            ty = self.ty_of_name(callee.name)
            if ty is None:
                ty = self.resolve_ty(A.NamedType(name=callee.name,
                                                 args=callee.args))
            return self.construct_code(ty, callee.name, lbl, argc, argv)
        if isinstance(callee, A.ClosureExpr):
            fn = self.gen_closure(callee)
            return "SwimCallValue(%s, %d, %s);" % (fn, argc, argv)
        fn = self.gen_expr(callee)
        return "SwimCallValue(%s, %d, %s);" % (fn, argc, argv)

    def construct_code(self, ty: Ty, name: str, lbl: str, argc: int,
                       argv: str) -> str:
        if ty.kind == "optional" or name in ("Optional", "Swift.Optional"):
            if argc >= 1:
                return "SwimSome((%s)[0]);" % argv if argv != "NULL" else "SwimNone();"
            return "SwimNone();"
        if ty.kind == "named":
            info = self.reg.types.get(ty.name)
            if info is not None and info.kind == "enum":
                return "SwimEnumRaw(%s, %s, %d, %s);" % (
                    self.ty_desc(ty), c_string(lbl), argc, argv)
            if info is not None:
                return "SwimConstruct(%s, %s, %d, %s);" % (
                    self.ty_desc(ty), c_string(lbl), argc, argv)
        if ty.kind in KIND_TO_PRIMDESC or ty.kind in ("array", "dict", "set"):
            return "SwimBuiltinStatic(%s, \"init\", %s, %d, %s);" % (
                self.ty_desc(ty), c_string(lbl), argc, argv)
        return "SwimConstruct(&SwimType_Any, %s, %d, %s);" % (
            c_string(lbl), argc, argv)

    def reorder_local_args(self, decl: A.FuncDecl, node: A.CallExpr,
                           vals: list[str], labels: list[str]) -> list[str]:
        params = decl.params
        ordered: list = [None] * len(params)
        used = [False] * len(vals)
        for i, p in enumerate(params):
            if p.label is None:
                continue
            for j, lab in enumerate(labels):
                if not used[j] and lab == p.label:
                    ordered[i] = vals[j]
                    used[j] = True
                    break
        k = 0
        for i, p in enumerate(params):
            if ordered[i] is None and k < len(vals):
                while k < len(vals) and used[k]:
                    k += 1
                if k < len(vals):
                    ordered[i] = vals[k]
                    used[k] = True
                    k += 1
        return [v for v in ordered if v is not None]

    def super_call(self, node: A.CallExpr, labels: list[str],
                   vals: list[str]) -> str:
        ctx = self.ctx
        info = ctx.type_info
        parent = info.superclass if info is not None else None
        if parent is None:
            self.error("'super' used without a superclass", node)
        if node.callee.name == "init":
            cname, failable = self.find_init_cname(parent, labels, len(vals))
            if failable:
                out = ctx.new_temp()
                ctx.line("%s = %s(NULL, %d, %s);" % (
                    out, cname, len(vals) + 1,
                    self.argv([self.read_self()] + vals)))
                return out
            ctx.line("%s(NULL, %d, %s);" % (
                cname, len(vals) + 1,
                self.argv([self.read_self()] + vals)))
            return "SwimVoid();"
        return "SwimCallMethodFrom(%s, &%s, %s, %s, %d, %s);" % (
            self.read_self(), self.user_desc[parent.name],
            c_string(node.callee.name), c_string(",".join(labels)), len(vals),
            self.argv(vals))

    def self_init_call(self, node: A.CallExpr, labels: list[str],
                       vals: list[str]) -> str:
        ctx = self.ctx
        info = ctx.type_info
        cname, failable = self.find_init_cname(info, labels, len(vals))
        if failable:
            out = ctx.new_temp()
            ctx.line("%s = %s(NULL, %d, %s);" % (
                out, cname, len(vals) + 1,
                self.argv([self.read_self()] + vals)))
            return out
        ctx.line("%s(NULL, %d, %s);" % (
            cname, len(vals) + 1, self.argv([self.read_self()] + vals)))
        return "SwimVoid();"

    def find_init_cname(self, info, labels: list[str], argc: int):
        jobs = self.init_jobs.get(info.name, [])
        want = ",".join(labels)
        for jlabels, cname, failable, params in jobs:
            if jlabels == want and len(params) == argc:
                return cname, failable
        if jobs:
            for jlabels, cname, failable, params in jobs:
                if len(params) == argc:
                    return cname, failable
        self.error("no matching initializer for '%s'" % info.name)
        raise AssertionError

    def gen_init_delegation(self, node: A.CallExpr, dst: str,
                            labels: list[str], vals: list[str]) -> None:
        ctx = self.ctx
        callee = node.callee
        info = ctx.type_info
        if isinstance(callee.base, A.SuperExpr):
            target = info.superclass if info is not None else None
        else:
            target = info
        if target is None:
            self.error("initializer delegation outside of a type", node)
        cname, failable = self.find_init_cname(target, labels, len(vals))
        call = "%s(NULL, %d, %s)" % (
            cname, len(vals) + 1, self.argv([self.read_self()] + vals))
        if failable:
            ctx.line("%s = %s;" % (dst, call))
        else:
            ctx.line("%s;" % call)
            ctx.line("%s = SwimVoid();" % dst)

    def read_self(self) -> str:
        """A borrowed reference to ``self`` (safe as a call receiver)."""
        ref = self.lookup_var("self")
        if ref is None or ref.kind != "frame":
            return "SwimFramePeek(__fr, 0)"
        if ref.depth == 0:
            return "SwimFramePeek(__fr, %d)" % ref.slot
        return "SwimFramePeek(SwimFrameUp(__fr, %d), %d)" % (
            ref.depth, ref.slot)

    # -------------------------------------------------------- native modules
    def native_call_code(self, name: str, labels: list[str], vals: list[str],
                         node) -> str:
        """The C call of a free function of the `FerroUI` native module."""
        if FERROUI_MODULE not in self.native_modules:
            self.error(f"'{name}' is provided by the {FERROUI_MODULE} module; "
                       f"add 'import {FERROUI_MODULE}' to the file that uses "
                       "it", node)
        c_name, params, _ret = FERROUI_FUNCS[name]
        param_labels = [label for label, _ in params]
        ordered: list = [None] * len(params)
        for index, label in enumerate(labels):
            if label in ("__trailing__", "*"):
                # A trailing closure: the parser records it apart from the
                # arguments and the call generator labels it "*".
                where = len(params) - 1
            elif label is None:
                where = index
            elif label in param_labels:
                where = param_labels.index(label)
            else:
                self.error(f"unknown argument label '{label}' in call to "
                           f"'{name}'", node)
            if where >= len(params):
                self.error(f"too many arguments in call to '{name}'", node)
            if ordered[where] is not None:
                self.error(f"duplicate argument '{param_labels[where]}' in "
                           f"call to '{name}'", node)
            ordered[where] = vals[index]
        for where, value in enumerate(ordered):
            if value is None:
                self.error(f"missing argument '{param_labels[where]}' in call "
                           f"to '{name}'", node)
        return "%s(%s);" % (c_name, ", ".join(ordered))

    def arg_expectations(self, node: A.CallExpr):
        """The (label, type) of the parameters of a known free function call.

        Used to give the arguments an expected type, which is what types an
        enum case written as a shorthand (``VStack(alignment: .leading)``):
        without it the runtime has to guess among the enums that have a case
        of that name.  ``None`` when the callee is not a single free function.
        """
        callee = node.callee
        if not isinstance(callee, A.Ident):
            return None
        funcs = self.reg.find_functions(callee.name)
        if not funcs or len(funcs) != 1:
            return None
        info = funcs[0]
        result = []
        index = 0
        while index < len(info.params):
            param = info.params[index]
            ty = info.param_types[index] if index < len(info.param_types) \
                else UNKNOWN
            label = param.label if param.label is not None else "_"
            result.append((label, ty, getattr(param, "is_variadic", False)))
            index += 1
        return result

    def gen_call(self, node: A.CallExpr, dst: str,
                 expected: Ty | None = None) -> None:
        ctx = self.ctx
        labels, vals, posts = self.gen_call_args(node.args,
                                                 node.trailing_closure,
                                                 self.arg_expectations(node))
        callee = node.callee
        if isinstance(callee, A.MemberExpr) and callee.name == "init" and \
                isinstance(callee.base, (A.SelfExpr, A.SuperExpr)):
            self.gen_init_delegation(node, dst, labels, vals)
            for post in posts:
                post()
            return
        code = self.call_code(node, labels, vals, posts)
        if code.endswith(";"):
            ctx.line("%s = %s" % (dst, code))
        else:
            ctx.line("%s = %s;" % (dst, code))
        for post in posts:
            post()

    def gen_closure_into(self, node: A.ClosureExpr, dst: str) -> None:
        ctx = self.ctx
        params = []
        for p in node.params:
            ty = self.resolve_ty(p.ty) if p.ty is not None else UNKNOWN
            params.append(JobParam(name=p.name, ty=ty))
        if not params:
            count = self.max_implicit_param(node.body)
            for i in range(count):
                params.append(JobParam(name="$%d" % i, ty=UNKNOWN))
        ret_ty = self.resolve_ty(node.ret_type) if node.ret_type is not None \
            else UNKNOWN
        job = self.make_closure_job(node.body, params, ret_ty, node,
                                    implicit=node.implicit_return)
        ctx.line("%s = SwimMakeClosure(%s, __fr);" % (dst, job.cname))

    def gen_closure(self, node: A.ClosureExpr,
                    expected: Ty | None = None) -> str:
        ctx = self.ctx
        params = []
        for p in node.params:
            ty = self.resolve_ty(p.ty) if p.ty is not None else UNKNOWN
            params.append(JobParam(name=p.name, ty=ty))
        if not params:
            count = self.max_implicit_param(node.body)
            for i in range(count):
                params.append(JobParam(name="$%d" % i, ty=UNKNOWN))
        ret_ty = self.resolve_ty(node.ret_type) if node.ret_type is not None \
            else UNKNOWN
        job = self.make_closure_job(node.body, params, ret_ty, node,
                                    implicit=node.implicit_return)
        t = ctx.new_temp()
        ctx.line("%s = SwimMakeClosure(%s, __fr);" % (t, job.cname))
        return t

    def read_lvalue(self, node) -> str:
        if isinstance(node, A.Ident):
            ref = self.lookup_var(node.name)
            if ref is None:
                ref = self.lookup_global(node.name)
            if ref is None:
                self.error("use of unresolved identifier '%s'" % node.name,
                           node)
            return self.read_var(ref)
        if isinstance(node, A.MemberExpr):
            recv = self.gen_expr(node.base)
            return "SwimGetMember(%s, %s)" % (recv, c_string(node.name))
        if isinstance(node, A.SubscriptExpr):
            base = self.gen_expr(node.base)
            argvals = [self.gen_expr(a.expr) for a in node.args]
            return "SwimSubscriptGet(%s, %d, %s)" % (
                base, len(argvals), self.argv(argvals))
        if isinstance(node, A.SelfExpr):
            ref = self.lookup_var("self")
            if ref is None:
                return "SwimFrameGet(__fr, 0)"
            return self.read_var(ref)
        self.error("invalid assignment target", node)

    def gen_assign(self, target, op: str, value_node) -> None:
        ctx = self.ctx
        if isinstance(target, A.Ident) and target.name == "_":
            self.gen_expr(value_node)
            return
        if isinstance(target, A.Ident):
            ref = self.lookup_var(target.name)
            if ref is None:
                ref = self.lookup_global(target.name)
            if ref is None:
                static_ty = self.static_var_owner(target.name)
                if static_ty is not None:
                    value = self.gen_expr(value_node)
                    if op != "=":
                        cur = "SwimGetStatic(&%s, %s)" % (
                            self.user_desc[static_ty.name],
                            c_string(target.name))
                        value = "SwimBinary(%s, %s, %s)" % (
                            c_string(op[:-1]), cur, value)
                    ctx.line("SwimSetStatic(&%s, %s, %s);" % (
                        self.user_desc[static_ty.name], c_string(target.name),
                        value))
                    return
                inst = self.instance_member_owner(target.name)
                if inst is not None:
                    value = self.gen_expr(value_node)
                    if op != "=":
                        cur = "SwimGetMember(%s, %s)" % (
                            self.read_self(), c_string(target.name))
                        value = "SwimBinary(%s, %s, %s)" % (
                            c_string(op[:-1]), cur, value)
                    if self.ctx.is_init and self.is_stored_field(target.name):
                        ctx.line("SwimInitField(%s, %s, %s);" % (
                            self.read_self(), c_string(target.name), value))
                    else:
                        ctx.line("SwimSetMember(%s, %s, %s);" % (
                            self.read_self(), c_string(target.name), value))
                    return
                self.error("use of unresolved identifier '%s'" % target.name,
                           target)
            value = self.gen_expr(value_node)
            if op != "=":
                cur = self.read_var(ref)
                value = "SwimBinary(%s, %s, %s)" % (c_string(op[:-1]), cur,
                                                    value)
            value = self.maybe_coerce(value, ref.ty)
            self.store_var(ref, value)
            return
        if isinstance(target, A.MemberExpr):
            recv = self.gen_expr(target.base)
            value = self.gen_expr(value_node)
            if op != "=":
                cur = "SwimGetMember(%s, %s)" % (recv, c_string(target.name))
                value = "SwimBinary(%s, %s, %s)" % (c_string(op[:-1]), cur,
                                                    value)
            if (self.ctx.is_init and isinstance(target.base, A.SelfExpr) and
                    self.is_stored_field(target.name)):
                ctx.line("SwimInitField(%s, %s, %s);" % (
                    self.read_self(), c_string(target.name), value))
                return
            ctx.line("SwimSetMember(%s, %s, %s);" %
                     (recv, c_string(target.name), value))
            return
        if isinstance(target, A.SubscriptExpr):
            base = self.gen_expr(target.base)
            argvals = [self.gen_expr(a.expr) for a in target.args]
            value = self.gen_expr(value_node)
            if op != "=":
                cur = "SwimSubscriptGet(%s, %d, %s)" % (
                    base, len(argvals), self.argv(argvals))
                value = "SwimBinary(%s, %s, %s)" % (c_string(op[:-1]), cur,
                                                    value)
            ctx.line("SwimSubscriptSet(%s, %d, %s, %s);" % (
                base, len(argvals), self.argv(argvals), value))
            return
        self.error("invalid assignment target", target)

    def coerce_temp(self, value: str, ty: Ty | None) -> str:
        if ty is None or ty.kind in ("unknown", "any", "generic", "void"):
            return value
        t = self.ctx.new_temp()
        self.ctx.line("%s = SwimCoerceOwned(%s, %s);" % (
            t, value, self.ty_desc(ty)))
        return t

    def maybe_coerce(self, value: str, ty: Ty | None) -> str:
        return self.coerce_temp(value, ty)

    def is_stored_field(self, name: str) -> bool:
        info = self.ctx.type_info
        if info is None:
            return False
        if name in info.computed:
            return False
        cur = info
        while cur is not None:
            for f in cur.fields:
                if f.name == name:
                    return True
            cur = cur.superclass
        return False

    def field_ty(self, info, name: str) -> Ty:
        cur = info
        while cur is not None:
            env = {n: Ty.generic(n) for n, _ in cur.generic_params}
            for f in cur.fields:
                if f.name == name:
                    return substitute(f.ty, env) if env else f.ty
            cur = cur.superclass
        return UNKNOWN

    # ---------------------------------------------------- types / names
    def ty_of_name(self, name: str) -> Ty | None:
        info = getattr(self.ctx, "type_info", None) if self.ctx else None
        cur = info
        while cur is not None:
            candidate = f"{cur.name}.{name}"
            if candidate in self.reg.types:
                return self.self_type(self.reg.types[candidate])
            cur = cur.parent
        if name in self.reg.types:
            return self.self_type(self.reg.types[name])
        if name in self.reg.aliases:
            return self.resolve_ty(self.reg.aliases[name].ty)
        if name in PRIM_KINDS:
            return Ty.prim(PRIM_KINDS[name])
        if name == "Array":
            return Ty.array(Ty.generic("T"))
        if name == "Dictionary":
            return Ty.dict(Ty.generic("K"), Ty.generic("V"))
        if name == "Set":
            return Ty.set(Ty.generic("T"))
        if name in ("Optional", "Swift.Optional"):
            return Ty.optional(UNKNOWN)
        return None

    def type_name_of_expr(self, node) -> Ty | None:
        if isinstance(node, A.Ident):
            return self.ty_of_name(node.name)
        if isinstance(node, A.GenericRefExpr):
            base = self.ty_of_name(node.name)
            if base is not None and base.kind == "named":
                args = tuple(self.resolve_ty(a) for a in node.args)
                return Ty.named(base.name, args)
            return base
        if isinstance(node, A.MemberExpr):
            base = self.type_name_of_expr(node.base)
            if base is not None and base.kind == "named":
                nested = f"{base.name}.{node.name}"
                if nested in self.reg.types:
                    return self.self_type(self.reg.types[nested])
        return None

    def static_var_owner(self, name: str):
        info = self.ctx.type_info
        cur = info
        while cur is not None:
            if name in cur.static_vars:
                return cur
            cp = cur.computed.get(name)
            if cp is not None and getattr(cp, "is_static", False):
                return cur
            cur = cur.superclass
        return None

    def instance_member_owner(self, name: str):
        info = self.ctx.type_info
        if info is None or not self.ctx.has_self:
            return None
        cur = info
        while cur is not None:
            if cur.field(name) is not None:
                return cur
            if name in cur.computed:
                return cur
            if cur.methods.get(name):
                return cur
            cur = cur.superclass
        return None

    def static_func_owner(self, name: str):
        info = self.ctx.type_info
        cur = info
        while cur is not None:
            if name in cur.static_funcs:
                return cur
            cur = cur.superclass
        return None

    # ------------------------------------------------------------ codegen
    def expr_code(self, node, expected: Ty | None = None) -> str:
        ctx = self.ctx
        if isinstance(node, A.IntLit):
            return "SwimInt(%s)" % node.text.replace("_", "")
        if isinstance(node, A.FloatLit):
            return "SwimDouble(%s)" % node.text.replace("_", "")
        if isinstance(node, A.BoolLit):
            return "SwimBool(%s)" % ("1" if node.value else "0")
        if isinstance(node, A.StringLit):
            return self.string_literal(node, expected)
        if isinstance(node, A.NilLit):
            return "SwimNone()"
        if isinstance(node, A.MagicLit):
            return self.magic_literal(node)
        if isinstance(node, A.Ident):
            ref = self.lookup_var(node.name)
            if ref is not None:
                return self.read_var(ref)
            ty = self.ty_of_name(node.name)
            if ty is not None:
                return "SwimTypeValue(%s)" % self.ty_desc(ty)
            owner = self.static_var_owner(node.name)
            if owner is None and node.name in ("allCases", "fromRaw"):
                cur = self.ctx.type_info
                while cur is not None:
                    if cur.kind == "enum":
                        return "SwimGetStatic(&%s, %s)" % (
                            self.user_desc[cur.name], c_string(node.name))
                    cur = cur.superclass
            if owner is not None:
                return "SwimGetStatic(&%s, %s)" % (
                    self.user_desc[owner.name], c_string(node.name))
            if self.ctx.has_self and node.name in ("rawValue", "hashValue"):
                ti = self.ctx.type_info
                if ti is not None and ti.kind == "enum":
                    return "SwimGetMember(%s, %s)" % (
                        self.read_self(), c_string(node.name))
            inst = self.instance_member_owner(node.name)
            if inst is not None:
                if inst.methods.get(node.name):
                    return "SwimBindMethod(%s, %s, \"\")" % (
                        self.read_self(), c_string(node.name))
                return "SwimGetMember(%s, %s)" % (
                    self.read_self(), c_string(node.name))
            # A global is a global even inside a method: without this lookup
            # first, an unqualified global name in a method became a member
            # access on `self` and read nil (the member does not exist).
            gref = self.lookup_global(node.name)
            if gref is not None:
                return self.read_var(gref)
            if self.reg.find_functions(node.name) or \
                    node.name in BUILTIN_FUNCS:
                return "SwimBindGlobalFn(%s, \"\")" % c_string(node.name)
            if self.static_func_owner(node.name) is not None:
                return "SwimBindGlobalFn(%s, \"\")" % c_string(node.name)
            if self.ctx.has_self:
                return "SwimGetMember(%s, %s)" % (
                    self.read_self(), c_string(node.name))
            self.error("use of unresolved identifier '%s'" % node.name, node)
        if isinstance(node, A.SelfExpr):
            ref = self.lookup_var("self")
            if ref is None:
                return "SwimFrameGet(__fr, 0)"
            return self.read_var(ref)
        if isinstance(node, A.MemberExpr):
            if isinstance(node.base, A.Ident) and \
                    self.lookup_var(node.base.name) is not None:
                if node.optional:
                    return "SwimOptionalMember(%s, %s)" % (
                        self.gen_expr(node.base), c_string(node.name))
                return "SwimGetMember(%s, %s)" % (
                    self.gen_expr(node.base), c_string(node.name))
            ty = self.type_name_of_expr(node.base)
            if ty is not None:
                info = self.reg.types.get(ty.name) if ty.kind == "named" else None
                if info is not None and info.kind == "enum" and \
                        info.enum_case(node.name) is not None:
                    return "SwimEnumCase(%s, %s, 0, NULL)" % (
                        self.ty_desc(ty), c_string(node.name))
                if ty.kind == "named" and ty.name in ("Array", "Dictionary",
                                                      "Set", "Optional"):
                    return "SwimGetStatic(%s, %s)" % (
                        self.ty_desc(ty), c_string(node.name))
                return "SwimGetStatic(%s, %s)" % (
                    self.ty_desc(ty), c_string(node.name))
            if node.optional:
                return "SwimOptionalMember(%s, %s)" % (
                    self.gen_expr(node.base), c_string(node.name))
            return "SwimGetMember(%s, %s)" % (
                self.gen_expr(node.base), c_string(node.name))
        if isinstance(node, A.SubscriptExpr):
            base = self.gen_expr(node.base)
            argvals = [self.gen_expr(a.expr) for a in node.args]
            if node.optional:
                return "SwimOptionalSubscript(%s, %d, %s)" % (
                    base, len(argvals), self.argv(argvals))
            return "SwimSubscriptGet(%s, %d, %s)" % (
                base, len(argvals), self.argv(argvals))
        if isinstance(node, A.ForceExpr):
            return "SwimUnwrap(%s)" % self.gen_expr(node.operand)
        if isinstance(node, A.UnaryExpr):
            return "SwimUnary(%s, %s)" % (c_string(node.op),
                                          self.gen_expr(node.operand))
        if isinstance(node, A.PostfixExpr):
            return "SwimUnary(%s, %s)" % (c_string(node.op),
                                          self.gen_expr(node.operand))
        if isinstance(node, A.BinaryExpr):
            if node.op in ("...", "..<"):
                lo = self.gen_expr(node.left)
                hi = self.gen_expr(node.right)
                return "SwimRangeFrom(%s, %s, %d)" % (
                    lo, hi, 1 if node.op == "..." else 0)
            if node.op == "??":
                left = self.gen_expr(node.left)
                right = self.gen_expr(node.right)
                return "SwimCoalesce(%s, %s)" % (left, right)
            left = self.gen_expr(node.left)
            right = self.gen_expr(node.right)
            return "SwimBinary(%s, %s, %s)" % (c_string(node.op), left, right)
        if isinstance(node, A.CastExpr):
            mode = {"as": 2, "as?": 1, "as!": 2}.get(node.mode, 2)
            return "SwimCast(%s, %s, %d)" % (
                self.gen_expr(node.expr), self.ty_desc(self.resolve_ty(node.ty)),
                mode)
        if isinstance(node, A.TypeCheckExpr):
            return "SwimCast(%s, %s, 0)" % (
                self.gen_expr(node.expr), self.ty_desc(self.resolve_ty(node.ty)))
        if isinstance(node, A.ClosureExpr):
            return self.gen_closure(node, expected)
        if isinstance(node, A.ArrayLit):
            items = [self.gen_expr(i) for i in node.items]
            elem_desc = "NULL"
            if expected is not None and expected.kind == "array":
                elem_desc = self.ty_desc(expected.elem)
            return "SwimArrayFrom(%d, %s, %s)" % (
                len(items), self.argv(items), elem_desc)
        if isinstance(node, A.DictLit):
            keys = [self.gen_expr(k) for k, _ in node.pairs]
            values = [self.gen_expr(v) for _, v in node.pairs]
            return "SwimDictFrom(%d, %s, %s, %s, %s)" % (
                len(keys), self.argv(keys), self.argv(values),
                self.ty_desc(expected.key) if expected is not None and
                expected.kind == "dict" else "NULL",
                self.ty_desc(expected.value) if expected is not None and
                expected.kind == "dict" else "NULL")
        if isinstance(node, A.TupleLit):
            items = [self.gen_expr(e) for _, e in node.items]
            labels = tuple((l if l is not None else str(i))
                           for i, (l, _) in enumerate(node.items))
            types = tuple(UNKNOWN for _ in node.items)
            desc = self.ty_desc(Ty(kind="tuple", args=types, labels=labels))
            return "SwimTupleFrom(%d, %s)" % (len(items), self.argv(items)) \
                if False else "SwimCoerce(SwimTupleFrom(%d, %s), %s)" % (
                    len(items), self.argv(items), desc)
        if isinstance(node, A.CaseRefExpr):
            vals: list[str] = []
            for arg in node.args:
                vals.append(self.gen_expr(arg.expr))
            target = expected
            if target is not None and target.kind == "optional":
                target = unwrap_optional(target)
            if target is not None and target.kind == "named":
                info = self.reg.types.get(target.name)
                if info is not None and info.kind == "enum" and \
                        info.enum_case(node.name) is not None:
                    return "SwimEnumCase(%s, %s, %d, %s)" % (
                        self.ty_desc(target), c_string(node.name),
                        len(vals), self.argv(vals))
            return "SwimEnumCaseAny(%s, %d, %s)" % (
                c_string(node.name), len(vals), self.argv(vals))
        if isinstance(node, A.GenericRefExpr):
            ty = self.ty_of_name(node.name)
            if ty is not None:
                return "SwimTypeValue(%s)" % self.ty_desc(ty)
            self.error("unknown type '%s'" % node.name, node)
        if isinstance(node, A.AssignExpr):
            self.gen_assign(node.target, node.op, node.value)
            return "SwimVoid()"
        self.error("unsupported expression: %s" % type(node).__name__, node)
        raise AssertionError

    def string_literal(self, node: A.StringLit, expected: Ty | None) -> str:
        if expected is not None and expected.kind == "char":
            if len(node.parts) == 1 and node.parts[0][0] == "text":
                text = node.parts[0][1]
                if len(text) == 1:
                    return "SwimChar(%d)" % (ord(text) & 0xFF)
        parts: list[str] = []
        for part in node.parts:
            if part[0] == "text":
                if part[1]:
                    parts.append("SwimCStr(%s)" % c_string(part[1]))
            else:
                parts.append("SwimStr(%s)" % self.gen_expr(part[1]))
        if not parts:
            return "SwimCStr(\"\")"
        if len(parts) == 1:
            return parts[0]
        return "SwimConcat(%d, %s)" % (len(parts), ", ".join(parts))

    def magic_literal(self, node: A.MagicLit) -> str:
        if node.kind == "file":
            return "SwimCStr(%s)" % c_string(
                str(self.filename).rsplit("/", 1)[-1])
        if node.kind == "line":
            return "SwimInt(%d)" % node.line
        if node.kind == "column":
            return "SwimInt(%d)" % node.col
        name = getattr(self.ctx, "proc_name", None) or "main"
        if name != "main" and not name.endswith("()"):
            name += "()"
        return "SwimCStr(%s)" % c_string(name)

    def gen_local_func(self, decl: A.FuncDecl) -> None:
        ctx = self.ctx
        params = []
        for p in decl.params:
            ty = self.resolve_ty(p.ty) if p.ty is not None else UNKNOWN
            if getattr(p, "is_variadic", False):
                ty = Ty.array(ty)
            params.append(JobParam(name=p.name, ty=ty, label=p.label,
                                   is_inout=isinstance(p.ty, A.InoutType),
                                   is_variadic=getattr(p, "is_variadic", False),
                                   default=p.default))
        ret_ty = self.resolve_ty(decl.ret) if decl.ret is not None else VOID
        job = Job(cname=self.new_cname(decl.name), kind="closure",
                  params=params, body=decl.body or [], ret_ty=ret_ty,
                  parent_ctx=ctx)
        job.closure_has_return = True
        saved = self.ctx
        self.emit_job(job)
        self.ctx = saved
        ctx = self.ctx
        slot = ctx.slot_for_node(decl)
        ref = VarRef("localfn", slot, 0, UNKNOWN, decl)
        ctx.bind(decl.name, ref)
        ctx.line("SwimFrameSet(__fr, %d, SwimMakeClosure(%s, __fr));" %
                 (slot, job.cname))


def generate(module: A.Module, registry: Registry,
             filename: str = "<input>",
             native_modules: list | None = None) -> str:
    """Generate C source for the given module."""
    gen = CGen(module, registry, filename, native_modules=native_modules)
    gen.collect()
    return gen.emit()