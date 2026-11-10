"""Lexer for the Swim language.

Swim uses Swift-style syntax.  This lexer produces a flat token stream that the
parser turns into an AST.  Newlines are not significant tokens (the parser only
uses line numbers for the few places where Swift is line sensitive, such as a
bare ``return``).
"""

from __future__ import annotations

import platform
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .errors import SwimError


# Compile-time conditional compilation flags.  ``SWIM`` is always defined;
# additional flags come from ``Swim run -D FLAG``.
CONDITIONAL_DEFINES: set[str] = {"SWIM"}


def set_defines(names) -> None:
    CONDITIONAL_DEFINES.clear()
    CONDITIONAL_DEFINES.add("SWIM")
    for name in names or []:
        if name:
            CONDITIONAL_DEFINES.add(str(name))


# Token kinds
IDENT = "ident"
KEYWORD = "keyword"
NUMBER = "number"
STRING = "string"
OP = "op"
PUNCT = "punct"
EOF = "eof"

# Characters that make up a Swift operator token.  Note that ``.`` is *not*
# included: in Swift the dot is punctuation, and ``...`` / ``..<`` are handled
# specially below.
OP_CHARS = set("/=-+!*%<>&|^~?")


def is_operator_char(ch: str) -> bool:
    """Swift-style operator character (ASCII set plus Unicode math symbols)."""
    if ch in OP_CHARS:
        return True
    if not ch or ord(ch) < 128:
        return False
    return unicodedata.category(ch) in ("Sm", "So", "Sk")

# Swift keywords (reserved words).  Contextual keywords are lexed as plain
# identifiers and matched by the parser when needed.
KEYWORDS = {
    "associatedtype", "class", "deinit", "enum", "extension", "fileprivate",
    "func", "import", "init", "inout", "internal", "let", "open", "operator",
    "private", "precedencegroup", "protocol", "public", "rethrows", "static",
    "struct", "subscript", "typealias", "var", "break", "case", "catch",
    "continue", "default", "defer", "do", "else", "fallthrough", "for",
    "guard", "if", "in", "repeat", "return", "throw", "switch", "where",
    "while", "as", "Any", "catch", "false", "is", "nil", "super", "self",
    "Self", "throw", "throws", "true", "try", "async", "await",
}


@dataclass
class Token:
    kind: str
    value: Any
    line: int
    col: int
    # For string literals: list of ("text", str) / ("expr", source, line, col)
    parts: list = field(default_factory=list)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.kind}, {self.value!r}, {self.line}:{self.col})"

    def is_(self, kind: str, value: str | None = None) -> bool:
        if self.kind != kind:
            return False
        return value is None or self.value == value


class Lexer:
    def __init__(self, src: str, filename: str = "<input>") -> None:
        self.src = src
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    # ------------------------------------------------------------------ utils
    def error(self, msg: str, line: int | None = None, col: int | None = None):
        raise SwimError(
            msg,
            filename=self.filename,
            line=self.line if line is None else line,
            col=self.col if col is None else col,
        )

    def peek(self, off: int = 0) -> str:
        i = self.pos + off
        return self.src[i] if i < len(self.src) else ""

    def advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def skip_whitespace(self) -> None:
        while self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch in " \t\r\n\v\f":
                self.advance()
            elif ch == "/" and self.peek(1) == "/":
                while self.pos < len(self.src) and self.src[self.pos] != "\n":
                    self.advance()
            elif ch == "/" and self.peek(1) == "*":
                start_line, start_col = self.line, self.col
                self.advance()
                self.advance()
                depth = 1
                while self.pos < len(self.src) and depth > 0:
                    if self.peek() == "/" and self.peek(1) == "*":
                        self.advance()
                        self.advance()
                        depth += 1
                    elif self.peek() == "*" and self.peek(1) == "/":
                        self.advance()
                        self.advance()
                        depth -= 1
                    else:
                        self.advance()
                if depth > 0:
                    self.error("unterminated block comment", start_line, start_col)
            else:
                return

    # ------------------------------------------------------------------- main
    def tokenize(self) -> list[Token]:
        while self.pos < len(self.src):
            self.skip_whitespace()
            if self.pos >= len(self.src):
                break
            line, col = self.line, self.col
            ch = self.src[self.pos]

            if ch == '"':
                self.lex_string()
                continue
            if ch.isdigit():
                self.lex_number()
                continue
            if ch == "_" or ch.isalpha() or ch == "$" or ch == "`":
                self.lex_ident()
                continue
            if is_operator_char(ch):
                self.lex_operator()
                continue
            if ch == ".":
                # ``...`` and ``..<`` are range operators, otherwise punctuation
                if self.peek(1) == "." and self.peek(2) == ".":
                    self.advance()
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(OP, "...", line, col))
                elif self.peek(1) == "." and self.peek(2) == "<":
                    self.advance()
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(OP, "..<", line, col))
                else:
                    self.advance()
                    self.tokens.append(Token(PUNCT, ".", line, col))
                continue
            if ch in "(){}[],:;@#\\":
                self.advance()
                self.tokens.append(Token(PUNCT, ch, line, col))
                continue
            self.error(f"unexpected character {ch!r}")

        self.tokens.append(Token(EOF, "", self.line, self.col))
        return self.tokens

    # ---------------------------------------------------------------- pieces
    def lex_ident(self) -> None:
        line, col = self.line, self.col
        if self.peek() == "`":
            self.advance()
            start = self.pos
            while self.pos < len(self.src) and self.src[self.pos] != "`":
                self.advance()
            if self.pos >= len(self.src):
                self.error("unterminated backtick identifier")
            name = self.src[start:self.pos]
            self.advance()  # closing backtick
            self.tokens.append(Token(IDENT, name, line, col))
            return
        if self.peek() == "$":
            # implicit closure parameter: $0, $1, ...
            self.advance()
            start = self.pos
            while self.pos < len(self.src) and self.src[self.pos].isdigit():
                self.advance()
            if start == self.pos:
                self.error("expected digit after '$'")
            self.tokens.append(Token(IDENT, "$" + self.src[start:self.pos], line, col))
            return
        start = self.pos
        while self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch == "_" or ch.isalnum():
                self.advance()
            else:
                break
        name = self.src[start:self.pos]
        kind = KEYWORD if name in KEYWORDS else IDENT
        self.tokens.append(Token(kind, name, line, col))

    def lex_operator(self) -> None:
        line, col = self.line, self.col
        start = self.pos
        while self.pos < len(self.src) and is_operator_char(self.src[self.pos]):
            # do not swallow a comment starter
            if self.src[self.pos] in "/" and self.peek(1) in "/*":
                if self.pos == start:
                    self.error("unexpected '/'")
                break
            self.advance()
        self.tokens.append(Token(OP, self.src[start:self.pos], line, col))

    def lex_number(self) -> None:
        line, col = self.line, self.col
        start = self.pos
        text = ""
        if self.peek() == "0" and self.peek(1) in "xXbBoO":
            self.advance()
            self.advance()
            while self.pos < len(self.src) and (
                self.src[self.pos].isalnum() or self.src[self.pos] == "_"
            ):
                self.advance()
            text = self.src[start:self.pos]
            self.tokens.append(Token(NUMBER, text, line, col))
            return
        while self.pos < len(self.src) and (
            self.src[self.pos].isdigit() or self.src[self.pos] == "_"
        ):
            self.advance()
        is_float = False
        if self.peek() == "." and self.peek(1).isdigit():
            is_float = True
            self.advance()
            while self.pos < len(self.src) and (
                self.src[self.pos].isdigit() or self.src[self.pos] == "_"
            ):
                self.advance()
        if self.peek() in "eE":
            nxt = self.peek(1)
            if nxt.isdigit() or (nxt in "+-" and self.peek(2).isdigit()):
                is_float = True
                self.advance()
                if self.peek() in "+-":
                    self.advance()
                while self.pos < len(self.src) and self.src[self.pos].isdigit():
                    self.advance()
        text = self.src[start:self.pos]
        self.tokens.append(Token(NUMBER, text, line, col))

    # ---------------------------------------------------------------- strings
    def lex_string(self) -> None:
        line, col = self.line, self.col
        multiline = False
        if self.peek(1) == '"' and self.peek(2) == '"':
            multiline = True
            self.advance()
            self.advance()
            self.advance()
        else:
            self.advance()

        parts: list = []
        buf: list[str] = []

        def flush_text() -> None:
            if buf:
                parts.append(("text", "".join(buf)))
                buf.clear()

        while True:
            if self.pos >= len(self.src):
                self.error("unterminated string literal", line, col)
            ch = self.src[self.pos]

            if ch == '"':
                if multiline:
                    if (
                        self.peek(1) == '"'
                        and self.peek(2) == '"'
                    ):
                        self.advance()
                        self.advance()
                        self.advance()
                        break
                    buf.append(self.advance())
                    continue
                self.advance()
                break

            if ch == "\\":
                nxt = self.peek(1)
                if nxt == "(":
                    flush_text()
                    self.advance()  # backslash
                    self.advance()  # opening paren
                    expr_src, expr_line, expr_col = self.scan_interpolation()
                    parts.append(("expr", expr_src, expr_line, expr_col))
                    continue
                self.advance()
                esc = self.advance() if self.pos < len(self.src) else ""
                mapping = {
                    "n": "\n", "t": "\t", "r": "\r", "0": "\0",
                    "\\": "\\", '"': '"', "'": "'",
                }
                if esc in mapping:
                    buf.append(mapping[esc])
                elif esc == "u":
                    # \u{1F600}
                    if self.peek() != "{":
                        self.error("expected '{' after \\u")
                    self.advance()
                    hexs: list[str] = []
                    while self.pos < len(self.src) and self.src[self.pos] != "}":
                        hexs.append(self.advance())
                    if self.pos >= len(self.src):
                        self.error("unterminated \\u escape")
                    self.advance()
                    try:
                        buf.append(chr(int("".join(hexs), 16)))
                    except ValueError:
                        self.error("invalid unicode escape")
                elif multiline and esc == "\n":
                    # line continuation inside a multiline string
                    pass
                else:
                    self.error(f"invalid escape sequence '\\{esc}'")
                continue

            buf.append(self.advance())

        flush_text()

        raw_text = None
        if multiline:
            parts = self.dedent_multiline(parts, line, col)

        self.tokens.append(
            Token(STRING, raw_text, line, col, parts=parts)
        )

    def scan_interpolation(self) -> tuple[str, int, int]:
        """Scan the balanced ``( ... )`` body of a string interpolation.

        Returns the source text and the approximate line/column of its start.
        """
        depth = 1
        start = self.pos
        start_line, start_col = self.line, self.col
        while self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch == "(":
                depth += 1
                self.advance()
            elif ch == ")":
                depth -= 1
                self.advance()
                if depth == 0:
                    return self.src[start:self.pos - 1], start_line, start_col
            elif ch == '"':
                # nested string literal: skip it (with interpolation aware scan)
                self.skip_string_in_interpolation()
            else:
                self.advance()
        self.error("unterminated string interpolation", start_line, start_col)

    def skip_string_in_interpolation(self) -> None:
        multiline = self.peek(1) == '"' and self.peek(2) == '"'
        for _ in range(3 if multiline else 1):
            self.advance()
        while self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch == "\\":
                self.advance()
                if self.pos < len(self.src) and self.src[self.pos] == "(":
                    self.advance()
                    self.scan_interpolation()
                elif self.pos < len(self.src):
                    self.advance()
                continue
            if ch == '"':
                if multiline:
                    if self.peek(1) == '"' and self.peek(2) == '"':
                        self.advance()
                        self.advance()
                        self.advance()
                        return
                    self.advance()
                else:
                    self.advance()
                    return
            else:
                self.advance()
        self.error("unterminated string literal in interpolation")

    def dedent_multiline(self, parts: list, line: int, col: int) -> list:
        """Approximate Swift's multiline string indentation stripping."""
        # Only text parts that begin the string / follow an interpolation are
        # dedented; Swift dedents according to the closing delimiter.  The
        # closing delimiter's indentation can be inferred from the last line.
        if not parts:
            return parts
        text = "".join(p[1] for p in parts if p[0] == "text")
        lines = text.split("\n")
        if lines and lines[0].strip() == "":
            lines = lines[1:]
        if lines and lines[-1].strip() == "":
            lines = lines[:-1]
        indent = min(
            (len(ln) - len(ln.lstrip(" \t")) for ln in lines if ln.strip()),
            default=0,
        )
        lines = [ln[indent:] if len(ln) >= indent else ln for ln in lines]
        joined = "\n".join(lines)
        # Rebuild parts: this loses fine-grained interleaving with
        # interpolations, so only do it when there are no interpolations.
        if all(p[0] == "text" for p in parts):
            return [("text", joined)]
        # With interpolations we do a simpler cleanup: strip leading newline.
        out = []
        first = True
        for p in parts:
            if p[0] == "text":
                t = p[1]
                if first and t.startswith("\n"):
                    t = t[1:]
                # dedent each line by ``indent``
                t = "\n".join(
                    ln[indent:] if len(ln) >= indent else ln for ln in t.split("\n")
                )
                out.append(("text", t))
            else:
                out.append(p)
            first = False
        return out


# ---------------------------------------------------------------------------
# Conditional compilation (#if / #elseif / #else / #endif / #error)
# ---------------------------------------------------------------------------
class _ConditionParser:
    """Tiny recursive-descent evaluator for ``#if`` conditions."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def evaluate(self) -> bool:
        try:
            value = self._or()
            self._skip_ws()
            if self.pos < len(self.text):
                return False
            return bool(value)
        except (ValueError, IndexError):
            return False

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _match(self, token: str) -> bool:
        self._skip_ws()
        if self.text.startswith(token, self.pos):
            self.pos += len(token)
            return True
        return False

    def _or(self) -> bool:
        value = self._and()
        while self._match("||"):
            rhs = self._and()
            value = value or rhs
        return value

    def _and(self) -> bool:
        value = self._unary()
        while self._match("&&"):
            rhs = self._unary()
            value = value and rhs
        return value

    def _unary(self) -> bool:
        if self._match("!"):
            return not self._unary()
        if self._match("("):
            value = self._or()
            if not self._match(")"):
                raise ValueError("expected ')'")
            return value
        return self._primary()

    def _read_ident(self) -> str:
        self._skip_ws()
        start = self.pos
        while self.pos < len(self.text) and (
                self.text[self.pos].isalnum() or self.text[self.pos] == "_"):
            self.pos += 1
        if start == self.pos:
            raise ValueError("expected identifier")
        return self.text[start:self.pos]

    def _read_args(self) -> str:
        if not self._match("("):
            raise ValueError("expected '('")
        depth = 1
        start = self.pos
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    args = self.text[start:self.pos]
                    self.pos += 1
                    return args
            self.pos += 1
        raise ValueError("expected ')'")

    def _primary(self) -> bool:
        name = self._read_ident()
        self._skip_ws()
        if name in ("true", "false"):
            return name == "true"
        if self.pos < len(self.text) and self.text[self.pos] == "(":
            args = self._read_args().strip()
            if name == "os":
                return _platform_os() == args.strip()
            if name == "arch":
                return _platform_arch() == args.strip()
            if name == "canImport":
                return args.strip() in {
                    "Foundation", "Swift", "Dispatch", "Darwin", "Glibc",
                    "ObjectiveC", "Math", "swimrt",
                }
            if name == "targetEnvironment":
                return args.strip() == "simulator" and False
            if name in ("swift", "compiler"):
                return _check_version(args)
            return False
        return name in CONDITIONAL_DEFINES


def _platform_os() -> str:
    system = platform.system()
    return {"Darwin": "macOS", "Linux": "Linux",
            "Windows": "Windows"}.get(system, system)


def _platform_arch() -> str:
    machine = platform.machine().lower()
    return {"arm64": "arm64", "aarch64": "arm64",
            "x86_64": "x86_64", "amd64": "x86_64"}.get(machine, machine)


def _check_version(args: str) -> bool:
    match = re.match(r"\s*(>=|<=|>|<|==)?\s*([\d.]+)\s*$", args)
    if not match:
        return False
    op = match.group(1) or ">="
    try:
        wanted = tuple(int(p) for p in match.group(2).split("."))
    except ValueError:
        return False
    current = (5, 9, 0)  # Swift language compatibility version
    while len(wanted) < len(current):
        wanted = wanted + (0,)
    def cmp(a, b):
        return (a > b) - (a < b)
    relation = cmp(current, wanted)
    return {">=": relation >= 0, "<=": relation <= 0, ">": relation > 0,
            "<": relation < 0, "==": relation == 0}[op]


def _replace_availability(text: str) -> str:
    """Replace ``#available(...)`` / ``#unavailable(...)`` with a boolean."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            out.append(ch)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if text.startswith("#available", i) or text.startswith("#unavailable", i):
            keyword = ("#unavailable" if text.startswith("#unavailable", i)
                       else "#available")
            j = text.find("(", i + len(keyword))
            if j == -1:
                out.append(ch)
                i += 1
                continue
            depth = 0
            k = j
            while k < n:
                if text[k] == "(":
                    depth += 1
                elif text[k] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            end = k + 1 if k < n else n
            value = "false" if keyword == "#unavailable" else "true"
            span = text[i:end]
            pad = max(0, len(span) - len(value))
            out.append(value + " " * pad)
            i = end
            continue
        out.append(ch)
        i += 1
    return "".join(out)


_DIRECTIVE_RE = re.compile(r"^#(if|elseif|else|endif|error|warning)\b(.*)$")


def preprocess(src: str, filename: str = "<input>") -> str:
    """Evaluate conditional compilation, preserving line numbers exactly."""
    lines = src.split("\n")
    out: list[str] = []
    stack: list[dict] = []
    active = True
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        match = _DIRECTIVE_RE.match(stripped)
        if match:
            keyword = match.group(1)
            rest = match.group(2).strip()
            if keyword == "if":
                if not active:
                    state = {"parent_active": False, "taken": False,
                             "current": False}
                    stack.append(state)
                    out.append("")
                    continue
                cond = _ConditionParser(rest).evaluate()
                state = {"parent_active": active, "taken": cond,
                         "current": active and cond}
                active = state["current"]
                stack.append(state)
            elif keyword == "elseif":
                if not stack:
                    raise SwimError("#elseif without #if", filename=filename,
                                    line=index + 1)
                state = stack[-1]
                if not state["parent_active"]:
                    state["current"] = False
                    active = False
                else:
                    cond = (False if state["taken"]
                            else _ConditionParser(rest).evaluate())
                    active = cond
                    if cond:
                        state["taken"] = True
                    state["current"] = active
            elif keyword == "else":
                if not stack:
                    raise SwimError("#else without #if", filename=filename,
                                    line=index + 1)
                state = stack[-1]
                active = state["parent_active"] and not state["taken"]
                state["taken"] = True
                state["current"] = active
            elif keyword == "endif":
                if not stack:
                    raise SwimError("#endif without #if", filename=filename,
                                    line=index + 1)
                state = stack.pop()
                active = state["parent_active"]
            elif keyword in ("error", "warning"):
                if active and keyword == "error":
                    message = rest.strip().strip('"')
                    raise SwimError(f"#error: {message}", filename=filename,
                                    line=index + 1)
            out.append("")
            continue
        if not active:
            out.append("")
        else:
            out.append(_replace_availability(line))
    if stack:
        raise SwimError("#if without #endif", filename=filename,
                        line=len(lines))
    return "\n".join(out)


def tokenize(src: str, filename: str = "<input>") -> list[Token]:
    src = preprocess(src, filename)
    return Lexer(src, filename).tokenize()
