"""Recursive descent parser for the Swim language (Swift-style syntax)."""

from __future__ import annotations

from . import ast_nodes as A
from .errors import SwimError
from .lexer import (
    EOF,
    IDENT,
    KEYWORD,
    NUMBER,
    OP,
    PUNCT,
    STRING,
    Token,
    tokenize,
)


class Backtrack(Exception):
    """Internal exception used for speculative parsing."""


# Assignment operators
ASSIGN_OPS = {
    "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "??=",
}
RIGHT_ASSOC = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
               "??=", "??"}

# Swift operator precedence (higher binds tighter)
PREC = {
    "=": 1, "+=": 1, "-=": 1, "*=": 1, "/=": 1, "%=": 1, "&=": 1, "|=": 1,
    "^=": 1, "<<=": 1, ">>=": 1, "??=": 1,
    "?": 2,  # ternary
    "??": 3,
    "||": 4,
    "&&": 5,
    "==": 6, "!=": 6, "<": 6, "<=": 6, ">": 6, ">=": 6, "===": 6, "!==": 6,
    "~=": 6,
    "...": 8, "..<": 8,
    "+": 9, "-": 9, "|": 9, "^": 9, "&+": 9, "&-": 9,
    "*": 10, "/": 10, "%": 10, "&": 10, "&*": 10,
    "<<": 11, ">>": 11,
}
CAST_PREC = 7

# Swift's built-in precedence groups (highest to lowest precedence groups are
# assigned higher numeric values, matching the PREC table above).
STANDARD_PRECEDENCE_GROUPS = {
    "AssignmentPrecedence": 1,
    "TernaryPrecedence": 2,
    "DefaultPrecedence": 2.5,
    "LogicalDisjunctionPrecedence": 4,
    "LogicalConjunctionPrecedence": 5,
    "ComparisonPrecedence": 6,
    "CastingPrecedence": 7,
    "RangeFormationPrecedence": 8,
    "AdditionPrecedence": 9,
    "MultiplicationPrecedence": 10,
    "BitwiseShiftPrecedence": 11,
}

MODIFIER_WORDS = {
    "public", "private", "internal", "fileprivate", "open", "final", "static",
    "mutating", "nonmutating", "override", "required", "convenience", "lazy",
    "weak", "unowned", "indirect", "dynamic", "optional", "prefix", "postfix",
    "infix", "nonisolated", "class", "__consuming", "borrowing", "consuming",
}

MEMBER_CONTEXTUAL = {
    "get", "set", "willSet", "didSet", "init", "self", "Type", "none", "some",
}

RAW_TYPES = {
    "Int", "Int8", "Int16", "Int32", "Int64", "UInt", "UInt8", "UInt16",
    "UInt32", "UInt64", "String", "Character", "Double", "Float", "Bool",
}

CONTROL_KEYWORDS = {"for", "while", "repeat", "switch", "do", "if"}


class Parser:
    def __init__(self, src: str, filename: str = "<input>") -> None:
        self.src = src
        self.filename = filename
        self.tokens: list[Token] = tokenize(src, filename)
        self.pos = 0
        self.no_trailing = 0
        self.prefix_ops: set[str] = set()
        self.postfix_ops: set[str] = set()
        self.operator_fixities: dict[str, set] = {}
        self.op_groups: dict[str, str] = {}
        self.group_assoc: dict[str, str] = {}
        self.group_precedence: dict[str, float] = \
            dict(STANDARD_PRECEDENCE_GROUPS)
        self.prec: dict[str, float] = dict(PREC)
        self.right_assoc: set[str] = set(RIGHT_ASSOC)
        self._scan_operator_declarations()

    # ------------------------------------------------------------------ tokens
    def peek(self, off: int = 0) -> Token:
        idx = self.pos + off
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind != EOF:
            self.pos += 1
        return tok

    def at(self, kind: str, value: str | None = None) -> bool:
        tok = self.peek()
        return tok.kind == kind and (value is None or tok.value == value)

    def at_op(self, value: str) -> bool:
        return self.at(OP, value)

    def at_punct(self, value: str) -> bool:
        return self.at(PUNCT, value)

    def at_kw(self, value: str) -> bool:
        return self.at(KEYWORD, value)

    def at_ident(self, value: str | None = None) -> bool:
        return self.at(IDENT, value)

    def consume_op(self, value: str) -> bool:
        if self.at_op(value):
            self.advance()
            return True
        return False

    def consume_punct(self, value: str) -> bool:
        if self.at_punct(value):
            self.advance()
            return True
        return False

    def consume_kw(self, value: str) -> bool:
        if self.at_kw(value):
            self.advance()
            return True
        return False

    def expect_op(self, value: str) -> Token:
        if not self.at_op(value):
            self.error(f"expected '{value}'")
        return self.advance()

    def expect_punct(self, value: str) -> Token:
        if not self.at_punct(value):
            self.error(f"expected '{value}'")
        return self.advance()

    def expect_kw(self, value: str) -> Token:
        if not self.at_kw(value):
            self.error(f"expected '{value}'")
        return self.advance()

    def expect_ident(self, what: str = "identifier") -> Token:
        tok = self.peek()
        if tok.kind == IDENT or (tok.kind == KEYWORD and tok.value in MEMBER_CONTEXTUAL):
            return self.advance()
        self.error(f"expected {what}, found {tok.value!r}")
        raise AssertionError

    def error(self, msg: str, tok: Token | None = None):
        tok = tok or self.peek()
        raise SwimError(
            msg,
            filename=self.filename,
            line=tok.line,
            col=tok.col,
        )

    # ------------------------------------------------------------ generic args
    def consume_generic_close(self) -> None:
        """Consume a single '>' even when the lexer produced '>>' or '>>>'."""
        tok = self.peek()
        if tok.kind != OP or not tok.value.startswith(">"):
            self.error("expected '>'")
        rest = tok.value[1:]
        if rest:
            # Replace the token with the leftover operators.
            self.tokens[self.pos] = Token(OP, rest, tok.line, tok.col + 1)
        else:
            self.advance()

    # --------------------------------------------------- operator declarations
    def _scan_operator_declarations(self) -> None:
        """Collect operator and precedencegroup declarations before parsing.

        Prefix/postfix operator symbols and custom infix precedence must be
        known while tokenizing the expression grammar, so a lightweight token
        pre-pass handles the declarations first.
        """
        toks = self.tokens
        n = len(toks)
        group_defs: dict[str, tuple] = {}
        i = 0
        while i < n - 1:
            tok = toks[i]
            val = tok.value if isinstance(tok.value, str) else ""
            if tok.kind == KEYWORD and val == "precedencegroup":
                j = i + 1
                if j < n and toks[j].kind == IDENT:
                    name = toks[j].value
                    j += 1
                    if j < n and toks[j].kind == PUNCT and \
                            toks[j].value == "{":
                        j += 1
                        assoc = "none"
                        higher: list = []
                        lower: list = []
                        while j < n and not (toks[j].kind == PUNCT and
                                             toks[j].value == "}"):
                            key = toks[j]
                            if key.kind == IDENT:
                                j += 1
                                if j < n and toks[j].kind == PUNCT and \
                                        toks[j].value == ":":
                                    j += 1
                                if key.value == "associativity" and j < n:
                                    assoc = toks[j].value
                                    j += 1
                                elif key.value in ("higherThan",
                                                   "lowerThan") and j < n:
                                    target = toks[j].value
                                    j += 1
                                    if key.value == "higherThan":
                                        higher.append(target)
                                    else:
                                        lower.append(target)
                                # other properties (assignment, ...) ignored
                            else:
                                j += 1
                        group_defs[name] = (assoc, higher, lower)
                        i = j + 1
                        continue
            if val in ("prefix", "postfix", "infix") and i + 1 < n:
                nxt = toks[i + 1]
                if nxt.kind == KEYWORD and nxt.value == "operator":
                    j = i + 2
                    if j < n and toks[j].kind == OP:
                        symbol = toks[j].value
                        j += 1
                        group = None
                        if j < n and toks[j].kind == PUNCT and \
                                toks[j].value == ":":
                            j += 1
                            if j < n and toks[j].kind in (IDENT, KEYWORD):
                                group = toks[j].value
                                j += 1
                        self.operator_fixities.setdefault(
                            symbol, set()).add(val)
                        if group is not None:
                            self.op_groups[symbol] = group
                        i = j
                        continue
            i += 1
        # Resolve custom precedence groups from higherThan/lowerThan relations
        values = dict(STANDARD_PRECEDENCE_GROUPS)
        pending = dict(group_defs)
        for _ in range(50):
            progress = False
            for name, (assoc, higher, lower) in list(pending.items()):
                highs = [values[h] for h in higher if h in values]
                lows = [values[l] for l in lower if l in values]
                if not highs and not lows:
                    continue
                value = (max(highs) + 0.1) if highs else (min(lows) - 0.1)
                if lows:
                    value = min(value, min(lows) - 0.1)
                values[name] = value
                pending.pop(name)
                progress = True
            if not pending or not progress:
                break
        for name in pending:
            values[name] = values["DefaultPrecedence"]
        self.group_precedence = values
        self.group_assoc = {name: definition[0]
                            for name, definition in group_defs.items()}
        for symbol, fixities in self.operator_fixities.items():
            if "infix" in fixities:
                group = self.op_groups.get(symbol)
                if group in values:
                    self.prec[symbol] = values[group]
                elif symbol not in self.prec:
                    self.prec[symbol] = values["DefaultPrecedence"]
                assoc = self.group_assoc.get(group, "none") if group else \
                    ("right" if symbol in RIGHT_ASSOC else "left")
                if assoc == "right":
                    self.right_assoc.add(symbol)
            if "prefix" in fixities:
                self.prefix_ops.add(symbol)
            if "postfix" in fixities:
                self.postfix_ops.add(symbol)

    # ----------------------------------------------------------------- module
    def parse_module(self) -> A.Module:
        decls: list = []
        stmts: list = []
        top_items: list = []
        while not self.at(EOF):
            while self.consume_punct(";"):
                pass
            if self.at(EOF):
                break
            if self.at_punct("}"):
                self.error("unexpected '}'")
            attrs, mods = self.parse_attrs_mods()
            top_let_tuple = (
                (self.at_kw("let") or self.at_kw("var")) and
                self.peek(1).kind == PUNCT and self.peek(1).value == "(")
            top_let_discard = (
                (self.at_kw("let") or self.at_kw("var")) and
                self.peek(1).kind == IDENT and self.peek(1).value == "_")
            if self.starts_decl() and not top_let_tuple and \
                    not top_let_discard:
                decl = self.parse_decl(attrs, mods)
                decls.append(decl)
                top_items.append(decl)
            else:
                if attrs or mods:
                    self.error("attributes/modifiers are only allowed on declarations")
                stmt = self.parse_statement()
                stmts.append(stmt)
                top_items.append(stmt)
        return A.Module(decls=decls, statements=stmts, top_items=top_items,
                        filename=self.filename, line=1, col=1)

    def starts_decl(self) -> bool:
        tok = self.peek()
        if tok.kind == KEYWORD and tok.value in {
            "import", "func", "struct", "class", "enum", "protocol",
            "extension", "typealias", "var", "let", "init", "deinit",
            "subscript", "operator", "precedencegroup",
        }:
            return True
        return False

    # ----------------------------------------------------- attributes/modifiers
    def parse_attrs_mods(self) -> tuple[list, list]:
        attrs: list = []
        mods: list = []
        while True:
            if self.at_punct("@"):
                self.advance()
                name = self.expect_ident("attribute name").value
                while self.at_punct("."):
                    self.advance()
                    name += "." + self.expect_ident("attribute name").value
                if self.at_punct("("):
                    self.skip_balanced("(", ")")
                attrs.append(name)
                continue
            tok = self.peek()
            val = tok.value if isinstance(tok.value, str) else ""
            if val in MODIFIER_WORDS and (tok.kind in (IDENT, KEYWORD)):
                if val == "class":
                    nxt = self.peek(1)
                    if not (nxt.kind == KEYWORD and nxt.value in
                            {"func", "var", "let", "subscript", "init"}):
                        break
                if val == "optional" and not self._in_protocol():
                    break
                self.advance()
                mods.append(val)
                continue
            break
        return attrs, mods

    def _in_protocol(self) -> bool:
        return False

    def skip_balanced(self, open_ch: str, close_ch: str) -> None:
        self.expect_punct(open_ch)
        depth = 1
        while depth > 0:
            if self.at(EOF):
                self.error(f"expected '{close_ch}'")
            tok = self.advance()
            if tok.kind == PUNCT and tok.value == open_ch:
                depth += 1
            elif tok.kind == PUNCT and tok.value == close_ch:
                depth -= 1

    # ------------------------------------------------------------- declarations
    def parse_decl(self, attrs: list, mods: list):
        tok = self.peek()
        if tok.kind == KEYWORD:
            if tok.value == "import":
                return self.parse_import(attrs, mods)
            if tok.value == "func":
                return self.parse_func(attrs, mods)
            if tok.value == "struct":
                return self.parse_struct(attrs, mods)
            if tok.value == "class":
                return self.parse_class(attrs, mods)
            if tok.value == "enum":
                return self.parse_enum(attrs, mods)
            if tok.value == "protocol":
                return self.parse_protocol(attrs, mods)
            if tok.value == "extension":
                return self.parse_extension(attrs, mods)
            if tok.value == "typealias":
                return self.parse_typealias(attrs, mods)
            if tok.value == "init":
                return self.parse_init(attrs, mods)
            if tok.value == "deinit":
                return self.parse_deinit(attrs, mods)
            if tok.value in ("var", "let"):
                return self.parse_var_decl(attrs, mods)
            if tok.value == "subscript":
                self.error("subscript declarations are only allowed inside a "
                           "type")
            if tok.value == "operator":
                return self.parse_operator_decl(attrs, mods)
            if tok.value == "precedencegroup":
                return self.parse_precedencegroup(attrs, mods)
        self.error("expected a declaration")

    def parse_operator_decl(self, attrs: list, mods: list):
        tok = self.expect_kw("operator")
        if self.peek().kind != OP:
            self.error("expected an operator symbol")
        symbol = self.advance().value
        group = None
        if self.consume_punct(":"):
            group = self.expect_ident("precedence group name").value
        fixity = ("prefix" if "prefix" in mods else
                  "postfix" if "postfix" in mods else "infix")
        return A.OperatorDecl(fixity=fixity, symbol=symbol,
                              precedence_group=group, attributes=attrs,
                              modifiers=mods, line=tok.line, col=tok.col)

    def parse_precedencegroup(self, attrs: list, mods: list):
        tok = self.expect_kw("precedencegroup")
        name = self.expect_ident("precedence group name").value
        self.expect_punct("{")
        associativity = "none"
        higher: list = []
        lower: list = []
        assignment = False
        while not self.at_punct("}"):
            key_tok = self.expect_ident("precedence group property")
            self.expect_punct(":")
            key = key_tok.value
            if key == "associativity":
                value_tok = self.expect_ident("associativity")
                if value_tok.value not in ("left", "right", "none"):
                    self.error("associativity must be left, right or none",
                               value_tok)
                associativity = value_tok.value
            elif key in ("higherThan", "lowerThan"):
                while True:
                    target = self.expect_ident("precedence group name").value
                    if key == "higherThan":
                        higher.append(target)
                    else:
                        lower.append(target)
                    if not self.consume_punct(","):
                        break
            elif key == "assignment":
                value_tok = self.expect_ident("boolean")
                assignment = value_tok.value == "true"
            else:
                self.error(f"unknown precedence group property '{key}'")
            while self.consume_punct(";"):
                pass
        self.expect_punct("}")
        return A.PrecedenceGroupDecl(name=name, associativity=associativity,
                                     higher_than=higher, lower_than=lower,
                                     assignment=assignment, attributes=attrs,
                                     modifiers=mods, line=tok.line,
                                     col=tok.col)

    def parse_import(self, attrs: list, mods: list):
        tok = self.expect_kw("import")
        if self.at_kw("typealias") or self.at_kw("struct") or self.at_kw("class"):
            self.advance()
        elif self.at_kw("enum") or self.at_kw("protocol") or self.at_kw("func"):
            self.advance()
        elif self.at_kw("let") or self.at_kw("var"):
            self.advance()
        parts = [self.expect_ident("module name").value]
        while self.consume_punct("."):
            parts.append(self.expect_ident("module name").value)
        return A.ImportDecl(path=".".join(parts), attributes=attrs,
                            modifiers=mods, line=tok.line, col=tok.col)

    def parse_typealias(self, attrs: list, mods: list):
        tok = self.expect_kw("typealias")
        name = self.expect_ident("type alias name").value
        generics = self.parse_generic_params_opt()
        self.expect_op("=")
        ty = self.parse_type()
        return A.TypeAliasDecl(name=name, generic_params=generics, ty=ty,
                               attributes=attrs, modifiers=mods,
                               line=tok.line, col=tok.col)

    def parse_func(self, attrs: list, mods: list, body_required: bool = True):
        tok = self.expect_kw("func")
        nt = self.peek()
        is_operator = False
        fixity: str | None = None
        if nt.kind == OP:
            name = self.advance().value
            is_operator = True
            fixity = ("prefix" if "prefix" in mods else
                      "postfix" if "postfix" in mods else "infix")
            if name not in self.operator_fixities:
                # Existing Swift operators can be overloaded without a
                # separate ``operator`` declaration.
                self.operator_fixities.setdefault(name, set()).add(fixity)
                if fixity == "infix" and name not in self.prec:
                    self.prec[name] = self.group_precedence[
                        "DefaultPrecedence"]
        else:
            name = self.expect_ident("function name").value
        generics = self.parse_generic_params_opt()
        params = self.parse_params()
        while True:
            if self.at_kw("async"):
                self.error("async functions are not supported by Swim yet")
            if self.at_kw("throws") or self.at_kw("rethrows"):
                self.advance()
            else:
                break
        ret = None
        if self.consume_op("->"):
            ret = self.parse_type()
        while True:
            if self.at_kw("async"):
                self.error("async functions are not supported by Swim yet")
            if self.at_kw("throws") or self.at_kw("rethrows"):
                self.advance()
            elif self.at_kw("where"):
                self.parse_where_constraints(generics)
            else:
                break
        body: list = []
        if self.at_punct("{"):
            body = self.parse_block()
        elif body_required:
            self.error("expected function body")
        return A.FuncDecl(name=name, generic_params=generics, params=params,
                          ret=ret, body=body, attributes=attrs, modifiers=mods,
                          is_operator=is_operator,
                          fixity=fixity if is_operator else None,
                          line=tok.line, col=tok.col)

    def parse_init(self, attrs: list, mods: list, body_required: bool = True):
        tok = self.expect_kw("init")
        failable = False
        failable_mode = None
        if self.at_op("?") or self.at_op("!"):
            failable_mode = self.advance().value
            failable = True
        params = self.parse_params()
        while self.at_kw("throws") or self.at_kw("rethrows"):
            self.advance()
        if self.at_kw("async"):
            self.error("async initializers are not supported by Swim yet")
        body: list = []
        if self.at_punct("{"):
            body = self.parse_block()
        elif body_required:
            self.error("expected initializer body")
        return A.InitDecl(params=params, body=body, failable=failable,
                          failable_mode=failable_mode,
                          attributes=attrs, modifiers=mods,
                          line=tok.line, col=tok.col)

    def parse_deinit(self, attrs: list, mods: list):
        tok = self.expect_kw("deinit")
        body = self.parse_block() if self.at_punct("{") else []
        return A.DeinitDecl(body=body, attributes=attrs, modifiers=mods,
                            line=tok.line, col=tok.col)

    def parse_subscript_decl(self, attrs: list, mods: list,
                             body_required: bool = True):
        tok = self.expect_kw("subscript")
        params = self.parse_params()
        self.expect_op("->")
        ret = self.parse_type()
        accessors: list = []
        if self.at_punct("{"):
            accessors = self.parse_accessors()
        elif body_required:
            self.error("expected subscript accessors")
        return A.SubscriptDecl(params=params, ret=ret, accessors=accessors,
                               attributes=attrs, modifiers=mods,
                               line=tok.line, col=tok.col)

    def parse_var_decl(self, attrs: list, mods: list):
        tok = self.peek()
        is_let = self.at_kw("let")
        self.advance()
        name = self.expect_ident("variable name").value
        ty = None
        if self.consume_punct(":"):
            ty = self.parse_type()
        init = None
        if self.consume_op("="):
            init = self.parse_expression()
        accessors: list = []
        if self.at_punct("{"):
            accessors = self.parse_accessors()
        return A.VarDecl(name=name, is_let=is_let, ty=ty, init=init,
                         accessors=accessors, attributes=attrs, modifiers=mods,
                         line=tok.line, col=tok.col)

    def parse_accessors(self) -> list:
        accessors: list = []
        self.expect_punct("{")
        while not self.at_punct("}"):
            while self.consume_punct(";"):
                pass
            if self.at_punct("}"):
                break
            tok = self.peek()
            if tok.kind == IDENT and tok.value in ("get", "set", "willSet", "didSet"):
                kind = self.advance().value
                param: str | None = None
                if self.at_punct("("):
                    # ``willSet(newValue)`` / ``didSet(oldValue)`` name the
                    # observer parameter; ``get async``/``set`` may contain
                    # other modifiers that are ignored.
                    self.advance()
                    if self.at(IDENT) or self.at(KEYWORD):
                        param = self.advance().value
                    while not self.at_punct(")"):
                        if self.at(EOF):
                            self.error("expected ')'")
                        self.advance()
                    self.expect_punct(")")
                body: list = []
                if self.at_punct("{"):
                    body = self.parse_block()
                accessors.append(A.AccessorDecl(kind=kind, body=body, param=param,
                                                line=tok.line, col=tok.col))
                if body and kind in ("get", "set"):
                    # ``get { ... }`` style: after set there may be no more braces
                    pass
                continue
            # Shorthand getter: ``var x: Int { expr }`` or a multi statement
            # getter body without an explicit ``get`` keyword.
            body = self.parse_statements_until("}")
            accessors.append(A.AccessorDecl(kind="get", body=body,
                                            line=tok.line, col=tok.col))
            break
        self.expect_punct("}")
        return accessors

    # ------------------------------------------------------------ type decls
    def parse_struct(self, attrs: list, mods: list):
        tok = self.expect_kw("struct")
        name = self.expect_ident("struct name").value
        generics = self.parse_generic_params_opt()
        inherits: list = []
        if self.consume_punct(":"):
            inherits = self.parse_inheritance_list()
        if self.at_kw("where"):
            self.parse_where_constraints(generics)
        members = self.parse_type_members("struct")
        return A.StructDecl(name=name, generic_params=generics,
                            conformances=inherits, members=members,
                            attributes=attrs, modifiers=mods,
                            line=tok.line, col=tok.col)

    def parse_class(self, attrs: list, mods: list):
        tok = self.expect_kw("class")
        name = self.expect_ident("class name").value
        generics = self.parse_generic_params_opt()
        superclass = None
        conformances: list = []
        if self.consume_punct(":"):
            inherits = self.parse_inheritance_list()
            if inherits:
                superclass = inherits[0]
                conformances = inherits[1:]
        if self.at_kw("where"):
            self.parse_where_constraints(generics)
        members = self.parse_type_members("class")
        return A.ClassDecl(name=name, generic_params=generics,
                           superclass=superclass, conformances=conformances,
                           members=members, attributes=attrs, modifiers=mods,
                           line=tok.line, col=tok.col)

    def parse_enum(self, attrs: list, mods: list):
        tok = self.expect_kw("enum")
        name = self.expect_ident("enum name").value
        generics = self.parse_generic_params_opt()
        raw_type = None
        conformances: list = []
        if self.consume_punct(":"):
            inherits = self.parse_inheritance_list()
            if (inherits and isinstance(inherits[0], A.NamedType)
                    and inherits[0].name in RAW_TYPES):
                raw_type = inherits[0]
                conformances = inherits[1:]
            else:
                conformances = inherits
        if self.at_kw("where"):
            self.parse_where_constraints(generics)
        cases, members = self.parse_enum_members()
        return A.EnumDecl(name=name, generic_params=generics, raw_type=raw_type,
                          conformances=conformances, cases=cases,
                          members=members, attributes=attrs, modifiers=mods,
                          line=tok.line, col=tok.col)

    def parse_protocol(self, attrs: list, mods: list):
        tok = self.expect_kw("protocol")
        name = self.expect_ident("protocol name").value
        generics = self.parse_generic_params_opt()
        inherits: list = []
        if self.consume_punct(":"):
            inherits = self.parse_inheritance_list()
        if self.at_kw("where"):
            self.parse_where_constraints(generics)
        members = self.parse_type_members("protocol")
        return A.ProtocolDecl(name=name, inherits=inherits, members=members,
                              attributes=attrs, modifiers=mods,
                              line=tok.line, col=tok.col)

    def parse_extension(self, attrs: list, mods: list):
        tok = self.expect_kw("extension")
        target = self.parse_type()
        conformances: list = []
        if self.consume_punct(":"):
            conformances = self.parse_inheritance_list()
        if self.at_kw("where"):
            self.parse_where_constraints([])
        members = self.parse_type_members("extension")
        return A.ExtensionDecl(target=target, conformances=conformances,
                               members=members, attributes=attrs,
                               modifiers=mods, line=tok.line, col=tok.col)

    def parse_inheritance_list(self) -> list:
        items: list = []
        while True:
            items.append(self.parse_type())
            if self.consume_punct(","):
                continue
            break
        return items

    def parse_generic_params_opt(self) -> list:
        params: list = []
        if not self.at_op("<"):
            return params
        self.advance()
        while True:
            name = self.expect_ident("generic parameter").value
            cons: list = []
            if self.consume_punct(":"):
                cons.append(self.expect_ident("protocol name").value)
                while self.consume_op("&"):
                    cons.append(self.expect_ident("protocol name").value)
            params.append((name, cons))
            if self.consume_punct(","):
                continue
            break
        self.consume_generic_close()
        return params

    def parse_where_constraints(self, generics: list) -> None:
        self.expect_kw("where")
        while True:
            if self.at(IDENT):
                name = self.advance().value
                if self.consume_punct(":"):
                    ty = self.parse_type()
                    # ``where T: SomeProtocol`` becomes an extra constraint on
                    # generic parameter T (same-type constraints are parsed
                    # but not enforced).
                    if isinstance(ty, A.NamedType):
                        for gname, constraints in generics:
                            if gname == name and ty.name not in constraints:
                                constraints.append(ty.name)
                elif self.consume_op("=="):
                    self.parse_type()
                else:
                    self.error("invalid where clause")
            else:
                self.error("invalid where clause")
            if self.consume_punct(","):
                continue
            break

    # ------------------------------------------------------------ members
    def parse_type_members(self, kind: str):
        members: list = []
        self.expect_punct("{")
        while not self.at_punct("}"):
            while self.consume_punct(";"):
                pass
            if self.at_punct("}"):
                break
            attrs, mods = self.parse_attrs_mods()
            if kind == "enum" and self.at_kw("case"):
                members.extend(self.parse_enum_cases(attrs, mods))
                continue
            if kind == "enum" and self.peek().kind == IDENT and self.peek().value == "indirect":
                self.advance()
                if self.at_kw("case"):
                    members.extend(self.parse_enum_cases(attrs, mods))
                    continue
            if self.at_kw("func"):
                members.append(self.parse_func(attrs, mods,
                                               body_required=(kind != "protocol")))
            elif self.at_kw("init"):
                members.append(self.parse_init(attrs, mods,
                                               body_required=(kind != "protocol")))
            elif self.at_kw("deinit"):
                members.append(self.parse_deinit(attrs, mods))
            elif self.at_kw("var") or self.at_kw("let"):
                members.append(self.parse_var_decl(attrs, mods))
            elif self.at_kw("typealias"):
                members.append(self.parse_typealias(attrs, mods))
            elif self.at_kw("subscript"):
                members.append(self.parse_subscript_decl(
                    attrs, mods, body_required=(kind != "protocol")))
            elif self.at_kw("struct"):
                members.append(self.parse_struct(attrs, mods))
            elif self.at_kw("class"):
                members.append(self.parse_class(attrs, mods))
            elif self.at_kw("enum"):
                members.append(self.parse_enum(attrs, mods))
            elif self.at_kw("protocol"):
                members.append(self.parse_protocol(attrs, mods))
            else:
                self.error("expected a member declaration")
        self.expect_punct("}")
        return members

    def parse_enum_members(self):
        cases: list = []
        members: list = []
        self.expect_punct("{")
        while not self.at_punct("}"):
            while self.consume_punct(";"):
                pass
            if self.at_punct("}"):
                break
            attrs, mods = self.parse_attrs_mods()
            if self.at_kw("case"):
                cases.extend(self.parse_enum_cases(attrs, mods))
                continue
            if self.peek().kind == IDENT and self.peek().value == "indirect":
                self.advance()
                if self.at_kw("case"):
                    cases.extend(self.parse_enum_cases(attrs, mods))
                    continue
            if self.at_kw("func"):
                members.append(self.parse_func(attrs, mods))
            elif self.at_kw("init"):
                members.append(self.parse_init(attrs, mods))
            elif self.at_kw("var") or self.at_kw("let"):
                members.append(self.parse_var_decl(attrs, mods))
            elif self.at_kw("subscript"):
                members.append(self.parse_subscript_decl(attrs, mods))
            elif self.at_kw("deinit"):
                members.append(self.parse_deinit(attrs, mods))
            elif self.at_kw("struct"):
                members.append(self.parse_struct(attrs, mods))
            elif self.at_kw("class"):
                members.append(self.parse_class(attrs, mods))
            elif self.at_kw("enum"):
                members.append(self.parse_enum(attrs, mods))
            elif self.at_kw("protocol"):
                members.append(self.parse_protocol(attrs, mods))
            else:
                self.error("expected enum member")
        self.expect_punct("}")
        return cases, members

    def parse_enum_cases(self, attrs: list, mods: list) -> list:
        self.expect_kw("case")
        cases: list = []
        while True:
            tok = self.peek()
            name = self.expect_ident("enum case name").value
            assoc: list = []
            if self.at_punct("("):
                assoc = self.parse_enum_assoc_params()
            raw = None
            if self.consume_op("="):
                raw = self.parse_expression()
            cases.append(A.EnumCase(name=name, assoc_params=assoc, raw_value=raw,
                                    attributes=attrs, modifiers=mods,
                                    line=tok.line, col=tok.col))
            if self.consume_punct(","):
                continue
            break
        return cases

    # ------------------------------------------------------------ parameters
    def parse_enum_assoc_params(self) -> list:
        self.expect_punct("(")
        params: list = []
        if self.at_punct(")"):
            self.advance()
            return params
        index = 0
        while True:
            label = None
            if self.at(IDENT) and self.peek(1).kind == PUNCT and \
                    self.peek(1).value == ":":
                label = self.advance().value
                self.advance()
            ty = self.parse_type()
            name = label if label else f"arg{index}"
            params.append(A.Param(label=label, name=name, ty=ty, default=None,
                                  line=self.peek().line, col=self.peek().col))
            index += 1
            if self.consume_punct(","):
                continue
            break
        self.expect_punct(")")
        return params

    def parse_params(self, allow_defaults: bool = True) -> list:
        self.expect_punct("(")
        params: list = []
        if self.at_punct(")"):
            self.advance()
            return params
        while True:
            label: str | None = None
            name: str = ""
            if self.at_ident("_"):
                self.advance()
                name = self.expect_ident("parameter name").value
                label = None
            else:
                first = self.expect_ident("parameter name").value
                if (self.at(IDENT) or self.at_kw("inout")) and not self.at_kw("inout"):
                    second = self.expect_ident("parameter name").value
                    label = first
                    name = second
                elif self.at(IDENT) and self.peek(1).kind == PUNCT and self.peek(1).value == ":":
                    second = self.expect_ident("parameter name").value
                    label = first
                    name = second
                else:
                    label = first
                    name = first
            self.expect_punct(":")
            ty = self.parse_type()
            is_variadic = self.consume_op("...")
            default = None
            if allow_defaults and not is_variadic and self.consume_op("="):
                default = self.parse_expression()
            is_inout = isinstance(ty, A.InoutType)
            if is_variadic and is_inout:
                self.error("a variadic parameter cannot be inout")
            params.append(A.Param(label=label, name=name, ty=ty, default=default,
                                  is_inout=is_inout, is_variadic=is_variadic,
                                  line=self.peek().line, col=self.peek().col))
            if self.consume_punct(","):
                continue
            break
        self.expect_punct(")")
        return params

    # ------------------------------------------------------------- statements
    def parse_block(self) -> list:
        self.expect_punct("{")
        body = self.parse_statements_until("}")
        self.expect_punct("}")
        return body

    def parse_statements_until(self, close: str) -> list:
        stmts: list = []
        while not self.at_punct(close):
            if self.at(EOF):
                self.error(f"expected '{close}'")
            while self.consume_punct(";"):
                pass
            if self.at_punct(close):
                break
            stmts.append(self.parse_statement())
        return stmts

    def parse_statement(self):
        tok = self.peek()
        if tok.kind == KEYWORD:
            v = tok.value
            if v in ("let", "var"):
                return self.parse_local_var()
            if v == "if":
                return self.parse_if()
            if v == "guard":
                return self.parse_guard()
            if v == "while":
                return self.parse_while()
            if v == "repeat":
                return self.parse_repeat()
            if v == "for":
                return self.parse_for()
            if v == "switch":
                return self.parse_switch()
            if v == "return":
                return self.parse_return()
            if v == "break":
                self.advance()
                label = None
                if self.at(IDENT):
                    label = self.advance().value
                return A.BreakStmt(label=label, line=tok.line, col=tok.col)
            if v == "continue":
                self.advance()
                label = None
                if self.at(IDENT):
                    label = self.advance().value
                return A.ContinueStmt(label=label, line=tok.line, col=tok.col)
            if v == "fallthrough":
                self.advance()
                return A.FallthroughStmt(line=tok.line, col=tok.col)
            if v == "throw":
                self.advance()
                return A.ThrowStmt(expr=self.parse_expression(),
                                   line=tok.line, col=tok.col)
            if v == "defer":
                self.advance()
                return A.DeferStmt(body=self.parse_block(),
                                   line=tok.line, col=tok.col)
            if v == "do":
                return self.parse_do()
            if v == "func":
                return self.parse_func([], [])
            if v == "typealias":
                return self.parse_typealias([], [])
            if v == "import":
                return self.parse_import([], [])
        # labeled statements: ``label: for`` / ``label: while`` ...
        if (tok.kind == IDENT and self.peek(1).kind == PUNCT
                and self.peek(1).value == ":" and self.peek(2).kind == KEYWORD
                and self.peek(2).value in CONTROL_KEYWORDS):
            self.advance()
            self.advance()
            inner = self.parse_statement()
            return A.LabeledStmt(label=tok.value, stmt=inner,
                                 line=tok.line, col=tok.col)
        expr = self.parse_expression()
        return A.ExprStmt(expr=expr, line=tok.line, col=tok.col)

    def parse_local_var(self) -> A.VarStmt:
        tok = self.peek()
        is_let = self.at_kw("let")
        self.advance()
        names: list = []
        if self.at_punct("("):
            self.advance()
            while True:
                if self.at_ident("_"):
                    self.advance()
                    names.append("_")
                else:
                    names.append(self.expect_ident("variable name").value)
                if self.consume_punct(","):
                    continue
                break
            self.expect_punct(")")
        name = self.expect_ident("variable name").value if not names else ""
        ty = None
        if self.consume_punct(":"):
            ty = self.parse_type()
        init = None
        if self.consume_op("="):
            init = self.parse_expression()
        return A.VarStmt(name=name, is_let=is_let, ty=ty, init=init,
                         names=names, line=tok.line, col=tok.col)

    def parse_conditions(self) -> list:
        items: list = []
        self.no_trailing += 1
        try:
            while True:
                tok = self.peek()
                if self.at_kw("let") or self.at_kw("var"):
                    kind = self.advance().value
                    name_tok = self.expect_ident("binding name")
                    name = name_tok.value
                    if self.consume_op("="):
                        expr = self.parse_expression()
                    else:
                        # Swift 5.7 shorthand: ``if let value { ... }``
                        expr = A.Ident(name=name, line=name_tok.line,
                                       col=name_tok.col)
                    items.append(A.CondBinding(kind=kind, name=name, expr=expr,
                                               line=tok.line, col=tok.col))
                elif self.at_kw("case"):
                    self.advance()
                    pat = self.parse_case_pattern()
                    self.expect_op("=")
                    expr = self.parse_expression()
                    items.append(A.CaseCond(pattern=pat, expr=expr,
                                            line=tok.line, col=tok.col))
                else:
                    expr = self.parse_expression()
                    items.append(A.CondExpr(expr=expr, line=tok.line,
                                            col=tok.col))
                if self.consume_punct(","):
                    continue
                break
        finally:
            self.no_trailing -= 1
        return items

    def parse_if(self) -> A.IfStmt:
        tok = self.expect_kw("if")
        conds = self.parse_conditions()
        body = self.parse_block()
        else_body: list = []
        if self.consume_kw("else"):
            if self.at_kw("if"):
                else_body = [self.parse_if()]
            else:
                else_body = self.parse_block()
        return A.IfStmt(conditions=conds, then_body=body, else_body=else_body,
                        line=tok.line, col=tok.col)

    def parse_guard(self) -> A.GuardStmt:
        tok = self.expect_kw("guard")
        conds = self.parse_conditions()
        self.expect_kw("else")
        body = self.parse_block()
        return A.GuardStmt(conditions=conds, else_body=body,
                           line=tok.line, col=tok.col)

    def parse_while(self) -> A.WhileStmt:
        tok = self.expect_kw("while")
        conds = self.parse_conditions()
        body = self.parse_block()
        return A.WhileStmt(conditions=conds, body=body, line=tok.line,
                           col=tok.col)

    def parse_repeat(self) -> A.RepeatStmt:
        tok = self.expect_kw("repeat")
        body = self.parse_block()
        self.expect_kw("while")
        self.no_trailing += 1
        try:
            cond = self.parse_expression()
        finally:
            self.no_trailing -= 1
        return A.RepeatStmt(body=body, condition=cond, line=tok.line,
                            col=tok.col)

    def parse_for(self) -> A.ForStmt:
        tok = self.expect_kw("for")
        names: list = []
        pattern = None
        if self.at_kw("case"):
            self.advance()
            pattern = self.parse_case_pattern()
        elif self.at_ident("_"):
            self.advance()
            names = ["_"]
        elif self.at_punct("("):
            self.advance()
            while True:
                if self.at_ident("_"):
                    self.advance()
                    names.append("_")
                else:
                    names.append(self.expect_ident("loop variable").value)
                if self.consume_punct(","):
                    continue
                break
            self.expect_punct(")")
        else:
            names = [self.expect_ident("loop variable").value]
        self.expect_kw("in")
        self.no_trailing += 1
        try:
            iterable = self.parse_expression()
            where_cond = None
            if self.at_kw("where"):
                self.advance()
                where_cond = self.parse_expression()
        finally:
            self.no_trailing -= 1
        body = self.parse_block()
        return A.ForStmt(names=names, iterable=iterable, where_cond=where_cond,
                         body=body, pattern=pattern, line=tok.line, col=tok.col)

    def parse_switch(self) -> A.SwitchStmt:
        tok = self.expect_kw("switch")
        self.no_trailing += 1
        try:
            subject = self.parse_expression()
        finally:
            self.no_trailing -= 1
        self.expect_punct("{")
        cases: list = []
        while not self.at_punct("}"):
            while self.consume_punct(";"):
                pass
            if self.at_punct("}"):
                break
            ctok = self.peek()
            if self.at_kw("case"):
                self.advance()
                patterns = self.parse_case_patterns()
                where_cond = None
                if self.at_kw("where"):
                    self.advance()
                    self.no_trailing += 1
                    try:
                        where_cond = self.parse_expression()
                    finally:
                        self.no_trailing -= 1
                self.expect_punct(":")
                body = self.parse_case_body()
                cases.append(A.CaseClause(patterns=patterns,
                                          where_cond=where_cond, body=body,
                                          line=ctok.line, col=ctok.col))
            elif self.at_kw("default"):
                self.advance()
                if self.at_kw("where"):
                    self.error("'default where' is not valid Swift")
                self.expect_punct(":")
                body = self.parse_case_body()
                cases.append(A.CaseClause(patterns=[], is_default=True,
                                          body=body, line=ctok.line,
                                          col=ctok.col))
            else:
                self.error("expected 'case' or 'default' in switch")
        self.expect_punct("}")
        return A.SwitchStmt(subject=subject, cases=cases, line=tok.line,
                            col=tok.col)

    def parse_case_body(self) -> list:
        stmts: list = []
        while not self.at_punct("}") and not self.at_kw("case") and \
                not self.at_kw("default"):
            if self.at(EOF):
                self.error("expected '}'")
            while self.consume_punct(";"):
                pass
            if self.at_punct("}") or self.at_kw("case") or self.at_kw("default"):
                break
            stmts.append(self.parse_statement())
        return stmts

    def parse_case_patterns(self) -> list:
        pats = [self.parse_case_pattern()]
        while self.consume_punct(","):
            pats.append(self.parse_case_pattern())
        return pats

    def parse_case_pattern(self) -> A.Pattern:
        tok = self.peek()
        declared_kind: str | None = None
        if self.at_kw("let") or self.at_kw("var"):
            declared_kind = self.advance().value
        if self.at_punct("."):
            self.advance()
            name = self.expect_ident("enum case name").value
            bindings: list = []
            has_parens = False
            if self.at_punct("("):
                has_parens = True
                self.advance()
                if not self.at_punct(")"):
                    while True:
                        label = None
                        bkind = declared_kind or "let"
                        bname = None
                        # optional label: ``label: let x``
                        if (self.at(IDENT) and self.peek(1).kind == PUNCT
                                and self.peek(1).value == ":"):
                            label = self.advance().value
                            self.advance()
                        if self.at_kw("let") or self.at_kw("var"):
                            bkind = self.advance().value
                        if self.at_ident("_"):
                            self.advance()
                            bname = None
                        else:
                            bname = self.expect_ident("binding name").value
                        bindings.append((label, bname, bkind))
                        if self.consume_punct(","):
                            continue
                        break
                self.expect_punct(")")
            pat = A.EnumCasePattern(case_name=name, bindings=bindings,
                                    has_parens=has_parens, line=tok.line,
                                    col=tok.col)
            if self.at_op("?"):
                self.advance()
                pat.optional_unwrap = True
            return pat
        if declared_kind is not None:
            if self.at_ident("_"):
                self.advance()
                return A.WildcardPattern(line=tok.line, col=tok.col)
            name = self.expect_ident("binding name").value
            pat = A.BindingPattern(kind=declared_kind, name=name, line=tok.line,
                                   col=tok.col)
            if self.at_op("?"):
                self.advance()
                pat.optional_unwrap = True
            return pat
        if self.at_ident("_"):
            self.advance()
            return A.WildcardPattern(line=tok.line, col=tok.col)
        if self.at_kw("is"):
            self.advance()
            ty = self.parse_type()
            return A.IsPattern(ty=ty, line=tok.line, col=tok.col)
        expr = self.parse_expression()
        if isinstance(expr, A.BinaryExpr) and expr.op in ("...", "..<"):
            return A.RangePattern(low=expr.left, high=expr.right,
                                  closed=(expr.op == "..."), line=tok.line,
                                  col=tok.col)
        if isinstance(expr, A.Ident) and expr.name == "_":
            return A.WildcardPattern(line=tok.line, col=tok.col)
        return A.LiteralPattern(expr=expr, line=tok.line, col=tok.col)

    def parse_return(self) -> A.ReturnStmt:
        tok = self.expect_kw("return")
        nxt = self.peek()
        expr = None
        if not (nxt.kind == EOF or (nxt.kind == PUNCT and nxt.value == "}")
                or nxt.line > tok.line):
            expr = self.parse_expression()
        return A.ReturnStmt(expr=expr, line=tok.line, col=tok.col)

    def parse_do(self) -> A.DoStmt:
        tok = self.expect_kw("do")
        body = self.parse_block()
        catches: list = []
        while self.at_kw("catch"):
            catches.append(self.parse_catch())
        if not catches:
            return A.DoStmt(body=body, catches=[], line=tok.line, col=tok.col)
        return A.DoStmt(body=body, catches=catches, line=tok.line, col=tok.col)

    def parse_catch(self) -> A.CatchClause:
        tok = self.expect_kw("catch")
        patterns: list = []
        name: str | None = None
        is_default = False
        where_cond = None
        if not self.at_punct("{"):
            if self.at_kw("let") or self.at_kw("var"):
                self.advance()
                name = self.expect_ident("error binding").value
                if self.at_kw("as"):
                    self.advance()
                    patterns.append(self.parse_type())
            else:
                parts: list = [self.expect_ident("error type").value]
                while self.consume_punct("."):
                    parts.append(self.expect_ident("error case").value)
                if len(parts) == 1:
                    patterns.append(A.NamedType(name=parts[0],
                                                line=tok.line, col=tok.col))
                elif len(parts) == 2:
                    bindings: list = []
                    if self.at_punct("("):
                        self.advance()
                        if not self.at_punct(")"):
                            while True:
                                bkind = "let"
                                if self.at_kw("let") or self.at_kw("var"):
                                    bkind = self.advance().value
                                if self.at_ident("_"):
                                    self.advance()
                                    bindings.append((None, None, bkind))
                                else:
                                    bname = self.expect_ident("binding name").value
                                    bindings.append((None, bname, bkind))
                                if self.consume_punct(","):
                                    continue
                                break
                        self.expect_punct(")")
                    patterns.append(A.EnumCasePattern(
                        case_name=parts[0] + "." + parts[1], bindings=bindings,
                        has_parens=bool(bindings), line=tok.line, col=tok.col))
                else:
                    self.error("invalid catch pattern")
            if self.at_kw("where"):
                self.advance()
                self.no_trailing += 1
                try:
                    where_cond = self.parse_expression()
                finally:
                    self.no_trailing -= 1
        else:
            is_default = True
        body = self.parse_block()
        return A.CatchClause(patterns=patterns, name=name, body=body,
                             is_default=is_default, line=tok.line, col=tok.col)

    # ------------------------------------------------------------ expressions
    def parse_expression(self) -> A.Expr:
        return self.parse_binary(1)

    def parse_binary(self, min_prec: int) -> A.Expr:
        left = self.parse_unary()
        while True:
            tok = self.peek()
            if tok.kind == KEYWORD and tok.value in ("as", "is"):
                if CAST_PREC < min_prec:
                    break
                self.advance()
                if tok.value == "as":
                    mode = "as"
                    if self.at_op("?"):
                        self.advance()
                        mode = "as?"
                    elif self.at_op("!"):
                        self.advance()
                        mode = "as!"
                    ty = self.parse_type()
                    left = A.CastExpr(expr=left, ty=ty, mode=mode,
                                      line=tok.line, col=tok.col)
                else:
                    ty = self.parse_type()
                    left = A.TypeCheckExpr(expr=left, ty=ty, line=tok.line,
                                           col=tok.col)
                continue
            if tok.kind != OP:
                break
            op = tok.value
            if op == "?":
                nxt = self.peek(1)
                if nxt.kind == PUNCT and nxt.value in (".", "[", "("):
                    break
            if op not in self.prec:
                break
            prec = self.prec[op]
            if prec < min_prec:
                break
            if op == "?":
                # ternary conditional
                self.advance()
                then_expr = self.parse_binary(3)
                self.expect_punct(":")
                else_expr = self.parse_binary(2)
                left = A.TernaryExpr(cond=left, then_expr=then_expr,
                                     else_expr=else_expr, line=tok.line,
                                     col=tok.col)
                continue
            self.advance()
            right = self.parse_binary(
                prec if op in self.right_assoc else prec + 1e-6
            )
            if op in ASSIGN_OPS:
                left = A.AssignExpr(target=left, op=op, value=right,
                                    line=tok.line, col=tok.col)
            else:
                left = A.BinaryExpr(op=op, left=left, right=right,
                                    line=tok.line, col=tok.col)
        return left

    def parse_unary(self) -> A.Expr:
        tok = self.peek()
        if tok.kind == OP and tok.value in self.prefix_ops and \
                tok.value not in ("!", "-", "+", "~", "&", "&+"):
            self.advance()
            operand = self.parse_unary()
            return A.UnaryExpr(op=tok.value, operand=operand,
                               line=tok.line, col=tok.col)
        if tok.kind == OP and tok.value in ("!", "-", "+", "~", "&", "&+"):
            self.advance()
            operand = self.parse_unary()
            return A.UnaryExpr(op=tok.value, operand=operand,
                               line=tok.line, col=tok.col)
        if tok.kind == KEYWORD and tok.value == "try":
            self.advance()
            mode = "try"
            if self.at_op("?"):
                self.advance()
                mode = "try?"
            elif self.at_op("!"):
                self.advance()
                mode = "try!"
            operand = self.parse_unary()
            return A.TryExpr(mode=mode, expr=operand, line=tok.line,
                             col=tok.col)
        if tok.kind == KEYWORD and tok.value == "await":
            self.error("'await' is not supported: Swim has no concurrency yet")
        return self.parse_postfix()

    def parse_postfix(self) -> A.Expr:
        expr = self.parse_primary()
        while True:
            tok = self.peek()
            if tok.kind == PUNCT and tok.value == ".":
                self.advance()
                name = self.parse_member_name()
                expr = A.MemberExpr(base=expr, name=name, optional=False,
                                    line=tok.line, col=tok.col)
                continue
            if tok.kind == OP and tok.value == "?" and self.peek(1).kind == PUNCT:
                nxt = self.peek(1).value
                if nxt == ".":
                    self.advance()
                    self.advance()
                    name = self.parse_member_name()
                    expr = A.MemberExpr(base=expr, name=name, optional=True,
                                        line=tok.line, col=tok.col)
                    continue
                if nxt == "[":
                    self.advance()
                    sub = self.parse_subscript()
                    sub.optional = True
                    sub.base = expr
                    expr = sub
                    continue
                if nxt == "(":
                    self.advance()
                    call = self.parse_call_args(expr)
                    call.line = tok.line
                    call.col = tok.col
                    expr = call
                    # optional call: mark callee's optional; handled in codegen
                    expr.optional_call = True  # type: ignore[attr-defined]
                    continue
            if tok.kind == PUNCT and tok.value == "(":
                expr = self.parse_call_args(expr)
                continue
            if tok.kind == PUNCT and tok.value == "[":
                sub = self.parse_subscript()
                sub.base = expr
                expr = sub
                continue
            if tok.kind == OP and tok.value in self.postfix_ops:
                self.advance()
                expr = A.PostfixExpr(op=tok.value, operand=expr,
                                     line=tok.line, col=tok.col)
                continue
            if tok.kind == OP and tok.value == "!":
                # postfix force unwrap (``a!``); ``a!=b`` lexes as a single token
                self.advance()
                expr = A.ForceExpr(operand=expr, line=tok.line, col=tok.col)
                continue
            if tok.kind == PUNCT and tok.value == "{" and self.no_trailing == 0 \
                    and not self._starts_accessor_block() \
                    and isinstance(expr, (A.CallExpr, A.MemberExpr, A.Ident,
                                          A.SubscriptExpr, A.TryExpr,
                                          A.ForceExpr)):
                closure = self.parse_closure()
                if isinstance(expr, A.CallExpr) and expr.trailing_closure is None:
                    expr.trailing_closure = closure
                else:
                    expr = A.CallExpr(callee=expr, args=[], trailing_closure=closure,
                                      line=tok.line, col=tok.col)
                continue
            if tok.kind == OP and tok.value == "<" and \
                    isinstance(expr, A.Ident):
                generic_args = self.try_parse_explicit_generic_call()
                if generic_args is not None:
                    call = self.parse_call_args(expr)
                    call.generic_args = generic_args
                    expr = call
                    continue
                type_args = self.try_parse_type_args_then_member()
                if type_args is not None:
                    expr = A.GenericRefExpr(name=expr.name, args=type_args,
                                            line=tok.line, col=tok.col)
                    continue
            break
        return expr

    def try_parse_type_args_then_member(self) -> list | None:
        save = self.pos
        try:
            if not self.at_op("<"):
                return None
            self.advance()
            args: list = []
            if not self.at_op(">"):
                while True:
                    args.append(self.parse_type())
                    if self.consume_punct(","):
                        continue
                    break
            self.consume_generic_close()
            nxt = self.peek()
            if not (nxt.kind == PUNCT and nxt.value in (".", "(")):
                raise Backtrack()
            return args
        except (Backtrack, SwimError):
            self.pos = save
            return None

    ACCESSOR_NAMES = ("get", "set", "willSet", "didSet")

    def _starts_accessor_block(self) -> bool:
        """True for a ``{ get/set/willSet/didSet ... }`` brace.

        Used to keep ``var x = makeValue() { didSet { ... } }`` from treating
        the observer block as a trailing closure.
        """
        if not self.at_punct("{"):
            return False
        nxt = self.peek(1)
        if nxt.kind != IDENT or nxt.value not in self.ACCESSOR_NAMES:
            return False
        after = self.peek(2)
        if after.kind == PUNCT and after.value == "{":
            return True
        if nxt.value in ("willSet", "didSet") and after.kind == PUNCT and \
                after.value == "(":
            return True
        return False

    def parse_member_name(self) -> str:
        tok = self.peek()
        if tok.kind == IDENT:
            return self.advance().value
        if tok.kind == NUMBER:
            return self.advance().value
        if tok.kind == KEYWORD and tok.value in MEMBER_CONTEXTUAL:
            return self.advance().value
        if tok.kind == KEYWORD and tok.value in ("init", "self"):
            return self.advance().value
        self.error("expected member name")

    def try_parse_explicit_generic_call(self) -> list | None:
        """Speculatively parse ``<T, U>`` followed by ``(`` for ``Foo<T>(...)``."""
        save = self.pos
        try:
            if not self.at_op("<"):
                return None
            self.advance()
            args: list = []
            if self.at_op(">"):
                self.consume_generic_close()
            else:
                while True:
                    args.append(self.parse_type())
                    if self.consume_punct(","):
                        continue
                    break
                self.consume_generic_close()
            if not self.at_punct("("):
                raise Backtrack()
            return args
        except (Backtrack, SwimError):
            self.pos = save
            return None

    def parse_subscript(self) -> A.SubscriptExpr:
        tok = self.expect_punct("[")
        args: list = []
        if not self.at_punct("]"):
            while True:
                label = None
                if (self.at(IDENT) or self.at(KEYWORD)) and \
                        self.peek(1).kind == PUNCT and self.peek(1).value == ":":
                    label = self.advance().value
                    self.advance()
                args.append(A.CallArg(label=label, expr=self.parse_expression(),
                                      line=self.peek().line, col=self.peek().col))
                if self.consume_punct(","):
                    continue
                break
        self.expect_punct("]")
        return A.SubscriptExpr(args=args, line=tok.line, col=tok.col)

    def parse_call_args(self, callee: A.Expr | None = None) -> A.CallExpr:
        tok = self.expect_punct("(")
        args: list = []
        if not self.at_punct(")"):
            while True:
                label = None
                # label detection (identifier or keyword followed by ':')
                if (self.at(IDENT) or self.at(KEYWORD)) and \
                        self.peek(1).kind == PUNCT and self.peek(1).value == ":":
                    label = self.advance().value
                    self.advance()
                expr = self.parse_expression()
                args.append(A.CallArg(label=label, expr=expr,
                                      line=expr.line, col=expr.col))
                if self.consume_punct(","):
                    continue
                break
        self.expect_punct(")")
        return A.CallExpr(callee=callee, args=args, line=tok.line, col=tok.col)

    def parse_primary(self) -> A.Expr:
        tok = self.peek()
        if tok.kind == NUMBER:
            self.advance()
            text = tok.value
            is_float = ("." in text) or ("e" in text.lower()) and not text.lower().startswith("0x")
            if is_float:
                return A.FloatLit(text=text, line=tok.line, col=tok.col)
            return A.IntLit(text=text, line=tok.line, col=tok.col)
        if tok.kind == STRING:
            self.advance()
            parts: list = []
            for part in tok.parts:
                if part[0] == "text":
                    parts.append(("text", part[1]))
                else:
                    _, src, line, col = part
                    sub = Parser(src, self.filename)
                    sub.pos = 0
                    try:
                        expr = sub.parse_expression()
                    except SwimError as exc:
                        exc.line = line
                        exc.col = col
                        raise
                    if not sub.at(EOF):
                        raise SwimError("invalid expression in string "
                                        "interpolation",
                                        filename=self.filename, line=line,
                                        col=col)
                    parts.append(("expr", expr))
            return A.StringLit(parts=parts, line=tok.line, col=tok.col)
        if tok.kind == KEYWORD:
            v = tok.value
            if v == "true" or v == "false":
                self.advance()
                return A.BoolLit(value=(v == "true"), line=tok.line,
                                 col=tok.col)
            if v == "nil":
                self.advance()
                return A.NilLit(line=tok.line, col=tok.col)
            if v == "self":
                self.advance()
                return A.SelfExpr(line=tok.line, col=tok.col)
            if v == "super":
                self.advance()
                return A.SuperExpr(line=tok.line, col=tok.col)
            if v in ("await",):
                self.advance()
                return self.parse_primary()
        if tok.kind == IDENT:
            self.advance()
            return A.Ident(name=tok.value, line=tok.line, col=tok.col)
        if tok.kind == PUNCT:
            v = tok.value
            if v == "#":
                self.advance()
                name_tok = self.peek()
                if name_tok.kind not in (IDENT, KEYWORD):
                    self.error("expected a compiler literal after '#'")
                self.advance()
                literal = name_tok.value
                if literal not in ("file", "line", "column", "function"):
                    self.error(f"unsupported compiler literal '#{literal}'; "
                               "Swim supports #file, #line, #column and "
                               "#function")
                return A.MagicLit(kind=literal, line=tok.line, col=tok.col)
            if v == "[":
                type_ctor = self.try_parse_collection_type_constructor()
                if type_ctor is not None:
                    return type_ctor
                return self.parse_collection_literal()
            if v == "(":
                return self.parse_tuple_or_paren()
            if v == "{":
                return self.parse_closure()
            if v == ".":
                self.advance()
                name = self.expect_ident("case name").value
                args: list = []
                if self.at_punct("("):
                    call = self.parse_call_args(A.Ident(name=name, line=tok.line,
                                                        col=tok.col))
                    args = call.args
                return A.CaseRefExpr(name=name, args=args, line=tok.line,
                                     col=tok.col)
        self.error(f"unexpected token {tok.value!r} in expression")

    def try_parse_collection_type_constructor(self) -> A.Expr | None:
        save = self.pos
        try:
            self.expect_punct("[")
            first = self.parse_type()
            args: list = [first]
            if self.consume_punct(":"):
                args.append(self.parse_type())
            self.expect_punct("]")
            if not self.at_punct("("):
                raise Backtrack()
            if len(args) == 1:
                ident = A.Ident(name="Array", line=self.peek().line,
                                col=self.peek().col)
            else:
                ident = A.Ident(name="Dictionary", line=self.peek().line,
                                col=self.peek().col)
            call = self.parse_call_args(ident)
            call.generic_args = args
            return call
        except (Backtrack, SwimError):
            self.pos = save
            return None

    def parse_collection_literal(self) -> A.Expr:
        tok = self.expect_punct("[")
        if self.at_punct("]"):
            self.advance()
            return A.ArrayLit(items=[], line=tok.line, col=tok.col)
        if self.at_punct(":"):
            self.advance()
            self.expect_punct("]")
            return A.DictLit(pairs=[], line=tok.line, col=tok.col)
        first = self.parse_expression()
        if self.consume_punct(":"):
            value = self.parse_expression()
            pairs = [(first, value)]
            while self.consume_punct(","):
                if self.at_punct("]"):
                    break
                k = self.parse_expression()
                self.expect_punct(":")
                v = self.parse_expression()
                pairs.append((k, v))
            self.expect_punct("]")
            return A.DictLit(pairs=pairs, line=tok.line, col=tok.col)
        items = [first]
        while self.consume_punct(","):
            if self.at_punct("]"):
                break
            items.append(self.parse_expression())
        self.expect_punct("]")
        return A.ArrayLit(items=items, line=tok.line, col=tok.col)

    def parse_tuple_or_paren(self) -> A.Expr:
        tok = self.expect_punct("(")
        if self.at_punct(")"):
            self.advance()
            return A.TupleLit(items=[], line=tok.line, col=tok.col)
        items: list = []
        while True:
            label = None
            if (self.at(IDENT) and self.peek(1).kind == PUNCT
                    and self.peek(1).value == ":"):
                label = self.advance().value
                self.advance()
            expr = self.parse_expression()
            items.append((label, expr))
            if self.consume_punct(","):
                if self.at_punct(")"):
                    break
                continue
            break
        self.expect_punct(")")
        if len(items) == 1 and items[0][0] is None:
            return items[0][1]
        return A.TupleLit(items=items, line=tok.line, col=tok.col)

    # --------------------------------------------------------------- closures
    def parse_closure(self) -> A.ClosureExpr:
        tok = self.expect_punct("{")
        params: list = []
        ret_type = None
        has_signature = False
        # capture list
        if self.at_punct("["):
            save = self.pos
            try:
                self.skip_balanced("[", "]")
                sig = self.try_closure_signature()
                if sig is None:
                    self.pos = save
                else:
                    params, ret_type = sig
                    has_signature = True
            except SwimError:
                self.pos = save
        if not has_signature:
            sig = self.try_closure_signature()
            if sig is not None:
                params, ret_type = sig
                has_signature = True

        body = self.parse_statements_until("}")
        self.expect_punct("}")
        implicit_return = False
        if (ret_type is None or not isinstance(ret_type, A.NamedType)
                or ret_type.name != "Void"):
            if (len(body) == 1 and isinstance(body[0], A.ExprStmt)
                    and not isinstance(body[0].expr, A.AssignExpr)):
                implicit_return = True
        return A.ClosureExpr(params=params, ret_type=ret_type, body=body,
                             implicit_return=implicit_return,
                             has_signature=has_signature,
                             uses_implicit_params=any(
                                 isinstance(p, A.ClosureParam) and
                                 p.name.startswith("$") for p in params),
                             line=tok.line, col=tok.col)

    def try_closure_signature(self):
        save = self.pos
        try:
            params: list = []
            ret_type = None
            if self.at_punct("("):
                self.advance()
                if not self.at_punct(")"):
                    while True:
                        name = self.expect_ident("closure parameter").value
                        ty = None
                        if self.consume_punct(":"):
                            ty = self.parse_type()
                        params.append(A.ClosureParam(name=name, ty=ty,
                                                     line=self.peek().line,
                                                     col=self.peek().col))
                        if self.consume_punct(","):
                            continue
                        break
                self.expect_punct(")")
                if self.at_op("->"):
                    self.advance()
                    ret_type = self.parse_type()
                if not self.at_kw("in"):
                    raise Backtrack()
                self.advance()
                return params, ret_type
            if self.at(IDENT):
                if not (self.peek(1).kind == PUNCT and
                        self.peek(1).value in (",", ":")) and \
                        not self.at_kw("in"):
                    # single ident followed by ``in``
                    if self.peek(1).kind != KEYWORD or self.peek(1).value != "in":
                        raise Backtrack()
                while True:
                    name = self.expect_ident("closure parameter").value
                    ty = None
                    if self.consume_punct(":"):
                        ty = self.parse_type()
                    params.append(A.ClosureParam(name=name, ty=ty,
                                                 line=self.peek().line,
                                                 col=self.peek().col))
                    if self.consume_punct(","):
                        continue
                    break
                if self.at_op("->"):
                    self.advance()
                    ret_type = self.parse_type()
                if not self.at_kw("in"):
                    raise Backtrack()
                self.advance()
                return params, ret_type
            raise Backtrack()
        except (Backtrack, SwimError):
            self.pos = save
            return None

    # ------------------------------------------------------------------ types
    def parse_type(self) -> A.TypeNode:
        tok = self.peek()
        while self.at_punct("@"):
            self.advance()
            self.expect_ident("attribute")
            if self.at_punct("("):
                self.skip_balanced("(", ")")
        if self.at_kw("inout"):
            self.advance()
            inner = self.parse_type()
            return A.InoutType(inner=inner, line=tok.line, col=tok.col)
        ty = self.parse_type_primary()
        while True:
            nxt = self.peek()
            if nxt.kind == OP and nxt.value and \
                    set(nxt.value) <= {"?", "!"}:
                self.advance()
                for _ in nxt.value:
                    ty = A.OptionalType(inner=ty, line=tok.line, col=tok.col)
                continue
            break
        return ty

    def parse_type_primary(self) -> A.TypeNode:
        tok = self.peek()
        if tok.kind == IDENT or tok.kind == KEYWORD:
            if tok.value in ("some", "any"):
                self.advance()
                return self.parse_type_primary()
            if tok.value in ("inout",):
                self.advance()
                return A.InoutType(inner=self.parse_type(), line=tok.line,
                                   col=tok.col)
            name = self.expect_ident("type name").value
            while self.at_punct(".") and self.peek(1).kind in (IDENT, KEYWORD):
                self.advance()
                name += "." + self.expect_ident("type name").value
            args: list = []
            if self.at_op("<"):
                self.advance()
                if self.at_op(">"):
                    self.consume_generic_close()
                else:
                    while True:
                        args.append(self.parse_type())
                        if self.consume_punct(","):
                            continue
                        break
                    self.consume_generic_close()
            return A.NamedType(name=name, args=args, line=tok.line, col=tok.col)
        if tok.kind == PUNCT and tok.value == "[":
            self.advance()
            first = self.parse_type()
            if self.consume_punct(":"):
                value = self.parse_type()
                self.expect_punct("]")
                return A.DictType(key=first, value=value, line=tok.line,
                                  col=tok.col)
            self.expect_punct("]")
            return A.ArrayType(elem=first, line=tok.line, col=tok.col)
        if tok.kind == PUNCT and tok.value == "(":
            self.advance()
            if self.at_punct(")"):
                self.advance()
                if self.consume_op("->"):
                    ret = self.parse_type()
                    return A.FuncType(params=[], ret=ret, line=tok.line,
                                      col=tok.col)
                return A.NamedType(name="Void", line=tok.line, col=tok.col)
            elements: list = []
            while True:
                label = None
                if (self.at(IDENT) and self.peek(1).kind == PUNCT
                        and self.peek(1).value == ":"):
                    label = self.advance().value
                    self.advance()
                elements.append((label, self.parse_type()))
                if self.consume_punct(","):
                    continue
                break
            self.expect_punct(")")
            if self.consume_op("->"):
                ret = self.parse_type()
                return A.FuncType(params=[e[1] for e in elements], ret=ret,
                                  line=tok.line, col=tok.col)
            if len(elements) == 1 and elements[0][0] is None:
                return elements[0][1]
            return A.TupleType(elements=elements, line=tok.line, col=tok.col)
        self.error("expected a type")

    # ------------------------------------------------------------------ entry
    def parse(self) -> A.Module:
        return self.parse_module()


def parse_source(src: str, filename: str = "<input>") -> A.Module:
    return Parser(src, filename).parse()
