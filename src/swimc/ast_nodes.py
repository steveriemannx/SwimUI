"""AST node definitions for the Swim language."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
@dataclass
class Node:
    line: int = 0
    col: int = 0


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
@dataclass
class TypeNode(Node):
    pass


@dataclass
class NamedType(TypeNode):
    name: str = ""
    args: list = field(default_factory=list)


@dataclass
class ArrayType(TypeNode):
    elem: Any = None


@dataclass
class DictType(TypeNode):
    key: Any = None
    value: Any = None


@dataclass
class OptionalType(TypeNode):
    inner: Any = None


@dataclass
class TupleType(TypeNode):
    elements: list = field(default_factory=list)  # list[(label|None, TypeNode)]


@dataclass
class FuncType(TypeNode):
    params: list = field(default_factory=list)  # list[TypeNode]
    ret: Any = None


@dataclass
class InoutType(TypeNode):
    inner: Any = None


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------
@dataclass
class Expr(Node):
    pass


@dataclass
class IntLit(Expr):
    text: str = ""


@dataclass
class FloatLit(Expr):
    text: str = ""


@dataclass
class BoolLit(Expr):
    value: bool = True


@dataclass
class StringLit(Expr):
    parts: list = field(default_factory=list)  # list[("text", str) | ("expr", Expr)]


@dataclass
class NilLit(Expr):
    pass


@dataclass
class MagicLit(Expr):
    """A compile-time literal such as ``#file``, ``#line`` or ``#function``."""

    kind: str = "file"  # 'file' | 'line' | 'column' | 'function'


@dataclass
class Ident(Expr):
    name: str = ""


@dataclass
class SelfExpr(Expr):
    pass


@dataclass
class SuperExpr(Expr):
    pass


@dataclass
class MemberExpr(Expr):
    base: Any = None
    name: str = ""
    optional: bool = False  # True when written as ``base?.member``


@dataclass
class CallArg(Node):
    label: str | None = None
    expr: Any = None


@dataclass
class CallExpr(Expr):
    callee: Any = None
    args: list = field(default_factory=list)  # list[CallArg]
    trailing_closure: Any = None
    generic_args: list = field(default_factory=list)  # explicit ``foo<T>(...)``


@dataclass
class SubscriptExpr(Expr):
    base: Any = None
    args: list = field(default_factory=list)  # list[CallArg]
    optional: bool = False


@dataclass
class BinaryExpr(Expr):
    op: str = ""
    left: Any = None
    right: Any = None


@dataclass
class UnaryExpr(Expr):
    op: str = ""
    operand: Any = None


@dataclass
class TernaryExpr(Expr):
    cond: Any = None
    then_expr: Any = None
    else_expr: Any = None


@dataclass
class ForceExpr(Expr):
    operand: Any = None


@dataclass
class ClosureParam(Node):
    name: str = ""
    ty: Any = None


@dataclass
class ClosureExpr(Expr):
    params: list = field(default_factory=list)  # list[ClosureParam]
    ret_type: Any = None
    body: list = field(default_factory=list)  # list[Stmt]
    # True when the closure body is a single expression and no ``return`` was
    # written (Swift allows implicit return for single expression closures).
    implicit_return: bool = False
    uses_implicit_params: bool = False
    has_signature: bool = False


@dataclass
class ArrayLit(Expr):
    items: list = field(default_factory=list)


@dataclass
class DictLit(Expr):
    pairs: list = field(default_factory=list)  # list[(key Expr, value Expr)]


@dataclass
class TupleLit(Expr):
    items: list = field(default_factory=list)  # list of (label|None, Expr)


@dataclass
class CastExpr(Expr):
    expr: Any = None
    ty: Any = None
    mode: str = "as"  # 'as' | 'as?' | 'as!'


@dataclass
class TypeCheckExpr(Expr):
    expr: Any = None
    ty: Any = None


@dataclass
class TryExpr(Expr):
    mode: str = "try"  # 'try' | 'try?' | 'try!'
    expr: Any = None


@dataclass
class GenericRefExpr(Expr):
    name: str = ""
    args: list = field(default_factory=list)


@dataclass
class CaseRefExpr(Expr):
    """Shorthand enum case reference such as ``.north``."""

    name: str = ""
    args: list = field(default_factory=list)  # list[CallArg]


@dataclass
class AssignExpr(Expr):
    target: Any = None
    op: str = "="  # '=', '+=', ...
    value: Any = None


# ---------------------------------------------------------------------------
# Patterns (switch / if case)
# ---------------------------------------------------------------------------
@dataclass
class Pattern(Node):
    pass


@dataclass
class WildcardPattern(Pattern):
    pass


@dataclass
class LiteralPattern(Pattern):
    expr: Any = None


@dataclass
class RangePattern(Pattern):
    low: Any = None
    high: Any = None
    closed: bool = True


@dataclass
class IsPattern(Pattern):
    """``case is SomeClass`` type test."""

    ty: Any = None


@dataclass
class BindingPattern(Pattern):
    kind: str = "let"  # 'let' | 'var'
    name: str = ""
    optional_unwrap: bool = False


@dataclass
class EnumCasePattern(Pattern):
    case_name: str = ""
    # list of (field label or None, binding name or None or '_', kind)
    bindings: list = field(default_factory=list)
    has_parens: bool = False
    optional_unwrap: bool = False


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------
@dataclass
class CondBinding(Node):
    kind: str = "let"  # 'let' | 'var'
    name: str = ""
    expr: Any = None


@dataclass
class CondExpr(Node):
    expr: Any = None


@dataclass
class CaseCond(Node):
    pattern: Any = None
    expr: Any = None


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------
@dataclass
class Stmt(Node):
    pass


@dataclass
class ExprStmt(Stmt):
    expr: Any = None


@dataclass
class VarStmt(Stmt):
    name: str = ""
    is_let: bool = False
    ty: Any = None
    init: Any = None
    names: list = field(default_factory=list)  # tuple destructuring


@dataclass
class IfStmt(Stmt):
    conditions: list = field(default_factory=list)  # list[CondBinding|CondExpr]
    then_body: list = field(default_factory=list)
    else_body: list = field(default_factory=list)  # may be [] or contain single IfStmt


@dataclass
class GuardStmt(Stmt):
    conditions: list = field(default_factory=list)
    else_body: list = field(default_factory=list)


@dataclass
class WhileStmt(Stmt):
    conditions: list = field(default_factory=list)
    body: list = field(default_factory=list)


@dataclass
class RepeatStmt(Stmt):
    body: list = field(default_factory=list)
    condition: Any = None


@dataclass
class ForStmt(Stmt):
    names: list = field(default_factory=list)  # list[str] (single or tuple pattern)
    iterable: Any = None
    where_cond: Any = None
    body: list = field(default_factory=list)
    pattern: Any = None  # ``for case <pattern> in ...``


@dataclass
class CaseClause(Node):
    patterns: list = field(default_factory=list)  # list[Pattern]
    where_cond: Any = None
    body: list = field(default_factory=list)
    is_default: bool = False


@dataclass
class SwitchStmt(Stmt):
    subject: Any = None
    cases: list = field(default_factory=list)


@dataclass
class ReturnStmt(Stmt):
    expr: Any = None


@dataclass
class BreakStmt(Stmt):
    label: str | None = None


@dataclass
class ContinueStmt(Stmt):
    label: str | None = None


@dataclass
class FallthroughStmt(Stmt):
    pass


@dataclass
class ThrowStmt(Stmt):
    expr: Any = None


@dataclass
class DeferStmt(Stmt):
    body: list = field(default_factory=list)


@dataclass
class DoStmt(Stmt):
    body: list = field(default_factory=list)
    catches: list = field(default_factory=list)  # list[CatchClause]


@dataclass
class CatchClause(Node):
    patterns: list = field(default_factory=list)  # list[TypeNode|EnumCasePattern|None]
    name: str | None = None
    body: list = field(default_factory=list)
    is_default: bool = False


@dataclass
class LabeledStmt(Stmt):
    label: str = ""
    stmt: Any = None


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------
@dataclass
class Decl(Node):
    modifiers: list = field(default_factory=list)
    attributes: list = field(default_factory=list)


@dataclass
class Param(Node):
    label: str | None = None  # external label; None means "_"
    name: str = ""
    ty: Any = None
    default: Any = None
    is_inout: bool = False
    is_variadic: bool = False


@dataclass
class ImportDecl(Decl):
    path: str = ""


@dataclass
class TypeAliasDecl(Decl):
    name: str = ""
    generic_params: list = field(default_factory=list)
    ty: Any = None


@dataclass
class FuncDecl(Decl):
    name: str = ""
    generic_params: list = field(default_factory=list)  # list[(name, constraints)]
    params: list = field(default_factory=list)
    ret: Any = None
    body: list = field(default_factory=list)
    owner: Any = None  # TypeInfo assigned during registration
    is_operator: bool = False
    fixity: str | None = None  # 'infix' | 'prefix' | 'postfix' for operators


@dataclass
class OperatorDecl(Decl):
    fixity: str = "infix"
    symbol: str = ""
    precedence_group: str | None = None


@dataclass
class PrecedenceGroupDecl(Decl):
    name: str = ""
    associativity: str = "none"  # 'left' | 'right' | 'none'
    higher_than: list = field(default_factory=list)
    lower_than: list = field(default_factory=list)
    assignment: bool = False


@dataclass
class PostfixExpr(Expr):
    op: str = ""
    operand: Any = None


@dataclass
class InitDecl(Decl):
    params: list = field(default_factory=list)
    body: list = field(default_factory=list)
    failable: bool = False
    failable_mode: str | None = None  # '?' or '!' for failable initializers
    owner: Any = None


@dataclass
class DeinitDecl(Decl):
    body: list = field(default_factory=list)
    owner: Any = None


@dataclass
class AccessorDecl(Node):
    kind: str = "get"  # 'get' | 'set' | 'willSet' | 'didSet'
    body: list = field(default_factory=list)
    param: str | None = None  # explicit observer parameter name


@dataclass
class VarDecl(Decl):
    name: str = ""
    is_let: bool = False
    ty: Any = None
    init: Any = None
    accessors: list = field(default_factory=list)  # list[AccessorDecl]
    property_observers: list = field(default_factory=list)
    owner: Any = None


@dataclass
class SubscriptDecl(Decl):
    params: list = field(default_factory=list)
    ret: Any = None
    accessors: list = field(default_factory=list)
    owner: Any = None


@dataclass
class EnumCase(Decl):
    name: str = ""
    assoc_params: list = field(default_factory=list)  # list[Param]
    raw_value: Any = None


@dataclass
class StructDecl(Decl):
    name: str = ""
    generic_params: list = field(default_factory=list)
    conformances: list = field(default_factory=list)  # list[str]
    members: list = field(default_factory=list)
    is_extension: bool = False


@dataclass
class ClassDecl(Decl):
    name: str = ""
    generic_params: list = field(default_factory=list)
    superclass: str | None = None
    conformances: list = field(default_factory=list)
    members: list = field(default_factory=list)


@dataclass
class EnumDecl(Decl):
    name: str = ""
    generic_params: list = field(default_factory=list)
    raw_type: Any = None
    conformances: list = field(default_factory=list)
    cases: list = field(default_factory=list)
    members: list = field(default_factory=list)


@dataclass
class ProtocolDecl(Decl):
    name: str = ""
    inherits: list = field(default_factory=list)
    members: list = field(default_factory=list)


@dataclass
class ExtensionDecl(Decl):
    target: Any = None  # TypeNode
    conformances: list = field(default_factory=list)
    members: list = field(default_factory=list)


@dataclass
class Module(Node):
    decls: list = field(default_factory=list)
    statements: list = field(default_factory=list)
    top_items: list = field(default_factory=list)
    filename: str = ""
