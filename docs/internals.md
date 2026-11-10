# Swim implementation notes

This document is for developers who want to modify the Swim compiler or
runtime.

## Compilation pipeline

```
swimc/cli.py
  ├─ modules.py   : import resolution → multi-file project (dependency order,
  │                 merged AST, line offsets)
  ├─ lexer.py     : source → token stream (with string interpolation parts)
  ├─ parser.py    : token stream → AST (ast_nodes.py)
  ├─ types.py     : AST → Registry (types/members/functions/aliases/extensions)
  ├─ codegen.py   : Registry + AST → Nim source + line mapping
  └─ nim compiler : Nim source + runtime/swimrt.nim → native executable
```

Entry point: `bin/Swim` → `src/swimc/main.py` → `swimc.cli:main`.

### 1. Lexer (`lexer.py`)

- Emits `Token(kind, value, line, col)` with kinds
  `ident/keyword/number/string/op/punct/eof`.
- String literals are split into `parts`: `("text", str)` or
  `("expr", source, line, col)`; interpolation expressions are parsed
  recursively by the parser.
- Comments (`//`, nested `/* */`) and multiline-string dedenting are handled in
  the lexer.
- No newline tokens are produced; the few line-sensitive places (such as a bare
  `return`) use the token's `line`.
- Operator tokens use Swift's ASCII operator characters plus Unicode characters
  in the math/symbol categories (`Sm`, `So`, `Sk`), so operators such as `≤`
  or `√` tokenize naturally.
- `lexer.preprocess` evaluates `#if`/`#elseif`/`#else`/`#endif` before
  tokenizing and replaces `#available(...)`/`#unavailable(...)` with a boolean.
  Inactive lines are replaced with empty lines so line numbers (and error
  mapping) are unchanged. Compile-time flags are set with
  `lexer.set_defines([...])` from the CLI `-D` options; built-in conditions are
  `SWIM`, `swift(...)`, `compiler(...)`, `os(...)`, `arch(...)` and
  `canImport(...)`.

### 1.5 Module loading (`modules.py`)

- `load_project(entry)` starts at the entry file and resolves every `import`:
  - built-in module names (`Foundation`, `Swift`, `Math`, ...) → no-op;
  - otherwise search for `<Name>.sw` or `<Name>/main.sw` in "importing file
    directory → entry file directory → cwd → `SWIM_PATH`";
  - report an error listing the search locations when not found.
- Dependencies are collected in post-order (dependencies before dependents);
  each file is loaded once. Import cycles are safely cut by first-visit order.
- Merging concatenates each file's `top_items` and rewrites every AST node's
  `line` with the file's line offset. A `line_owner` table (composed line →
  real file + line) is built for diagnostics.
- Validation: duplicate types/global variables/same-signature functions across
  files are errors; only the entry file may declare `@main`.
- `Project` stores file order, the merged AST, `line_owner`, per-file source
  text and the import graph. `Swim deps` uses this information directly.

### 2. Parser (`parser.py`)

- Recursive descent plus Pratt expression parsing (Swift precedence table in
  `PREC`).
- Dedicated functions for type parsing, generic parameters/constraints,
  closure signatures and patterns (`switch` cases, `catch`).
- A token pre-pass (`_scan_operator_declarations`) collects
  `operator`/`precedencegroup` declarations first: it extends the Pratt
  precedence table, records right-associative operators and knows which
  symbols are prefix/postfix. Operator functions (`func ** (...)` and
  `prefix/postfix func ...`) are parsed with the operator token as their name.
- Type names may be dotted (`Outer.Inner`); nested type declarations are
  parsed as ordinary members of their enclosing type.
- `where T: Protocol` clauses are merged into the generic parameter's
  constraint list while parsing (so codegen emits them as Nim concept
  constraints); same-type constraints are parsed and ignored.
- Declarations and statements have separate entry points; type members
  (`struct/class/enum/protocol/extension`) each have their own member loop.
- Backtracking (`Backtrack` exception) implements generic inference for
  `Box<Int>(...)` and `Box<Int>.case(...)`.
- Top-level declarations/statements are kept in source order in
  `Module.top_items` (execution order depends on it).

### 3. Type system and symbol tables (`types.py`)

- `Ty`: an immutable type representation (`kind` + `name` + `args` + `labels`)
  covering integers/floats/strings/arrays/dictionaries/optionals/tuples/
  closures/named types/generic parameters/ranges/types.
- `Registry`:
  - Two passes over the module build `TypeInfo` (struct/class/enum/protocol),
    `FuncInfo`, `EnumCaseInfo`, `ComputedProp` and `ExtensionInfo`.
  - Resolves inheritance, protocol constraints, type aliases and extension
    members.
  - Provides queries such as `find_methods` / `find_functions` / `field_type` /
    `resolve_type`, and performs generic substitution (`substitute`).
- Error enums (`enum E: Error`) are recorded with `is_error`; codegen emits the
  exception type hierarchy.
- Nested types are registered recursively with qualified names
  (`Outer.Inner`) and mangled Nim names (`Outer_Inner`); `TypeInfo.parent` /
  `TypeInfo.nested` support unqualified lookup inside the enclosing type and
  `Outer.Inner` lookup outside. Nested `typealias` declarations are available
  in the type's generic/nested environment.
- Operator functions are collected in `Registry.operators` keyed by
  `(fixity, symbol)`; static operators declared in types/extensions are
  registered the same way.

### 4. Code generation (`codegen.py`)

Emission order is fixed:

1. header (version, `import swimrt`)
2. type declarations (structs/classes/enums/protocol concepts/error types/
   aliases) — all in a single Nim `type` section so types may reference each
   other (including nested types) regardless of source order
3. global variable declarations (without initializers)
4. forward declarations for all procedures
5. procedure definitions (free functions, methods, initializers, computed
   properties, static members, extensions, enum helpers, synthesized
   `$`/`==`/`hash`/`allCases`, ...)
6. static variable initialization
7. top-level code (global initialization and top-level statements in source
   order)
8. `@main` entry call

Key designs:

- **Forward declarations**: Nim requires declaration before use, so every proc
  gets a signature first and its body later. Default parameter values are
  emitted on the declaration and omitted on the definition.
- **Naming**: `nim_ident()` handles Nim keyword/runtime symbol collisions with
  a `sw_` prefix. User type names that collide with Nim names get a `Swim`
  prefix. Static methods, constructors and enum constructors use names such as
  `Type_method`, `newType`, `Type_case` to avoid collisions.
- **Structs**: `object`; `mutating` methods take `self: var T`.
- **Classes**: `ref object of RootObj`. Covered methods with inheritance
  generate an "impl proc + method wrapper" pair to support dynamic dispatch and
  static `super.method()` calls.
- **Enums**: no associated values → `{.pure.} enum`; associated values → kind
  enum + variant object; recursive enums automatically use
  `ref object of RootObj`; string raw values generate `rawValue`/`fromRaw`.
- **Protocols**: generate Nim concepts (method/property requirements); protocol
  extensions generate generic procs constrained by the concept.
- **Optional chaining**: `a?.b?.c` compiles to nested `swimOptFlatMap` template
  calls (defined by the runtime).
- **`if let` / `guard let`**: generate a temporary plus `isSome` checks and
  `get`.
- **Pattern matching**: `switch` compiles to an `if` chain guarded by a
  `swMatched` flag; enum associated values are only read after the condition
  succeeds, avoiding variant-object field access errors.
- **Top-level order**: global variables are declared first (so procs can
  reference them); initialization and top-level statements execute in
  `top_items` order, matching Swift's top-level execution order.
- **Error mapping**: `CodeGen.line_map` records generated Nim line → composed
  line; `Project.line_owner` maps composed lines back to (module file, local
  line), and `cli.translate_nim_errors` /
  `Project.normalize_codegen_error` print the correct module snippet.
- **Closures**: single-expression closures generate `{.closure.}` proc
  literals; multi-statement closures generate proc literals with bodies.
  Higher-order trailing closures prefer the It-template path (`mapIt`, etc.).
- **Property observers**: a `var` with `willSet`/`didSet` becomes a hidden
  backing field (`swimBk_<name>`) plus a getter proc and a `` `<name>=` ``
  setter proc. The setter saves the old value, runs `willSet`, stores, then
  runs `didSet`. Initializers and the synthesized memberwise initializer write
  the backing field directly so observers do not fire during initialization.
  Compound assignments through a setter are expanded to
  `prop = prop <op> value`, and mutating collection/string method calls on an
  observed property are rewritten to a read-modify-write (`var tmp = ...`,
  mutate, `obj.prop = tmp`) so the observer runs once.
- **Failable initializers**: `init?` lowers to an `initT(...): bool` proc
  (calls return `true`/`false`; `return nil` becomes `return false`, falling off
  the end returns `true`) plus a `newT(...): Option[T]` constructor. `init!`
  uses the same pair and unwraps at the call site. `super.init`/`self.init`
  delegation propagates the bool (a failed delegated initializer returns
  `false`).
- **Subscripts**: a `subscript` compiles to Nim `` `[]` `` (getter) and
  `` `[]=` `` (setter, if a `set` accessor exists) proc overloads. Reads and
  writes on user types resolve through `Registry.find_subscripts`, which
  includes extension subscripts. Getter `self` is a plain parameter, setter
  `self` is `var` for value types.
- **Variadic parameters**: `func f(_ xs: Int...)` declares `xs: seq[int]`;
  call sites collect the matching trailing arguments into `@[...]` (or
  `newSeq[T]()` when empty). Parameters after the variadic one must be labeled
  at the call site.
- **`fallthrough`**: the switch `if` chain inlines the next case's body when a
  case body ends with `fallthrough`; no pattern test or payload binding happens
  for the fallen-into case. Nested cases are generated in their own scope and
  `break` still exits the whole switch via its block label.
- **`for case`**: parses the case pattern and inlines
  `if not (<pattern condition>): continue` plus the pattern bindings at the top
  of the loop body.
- **Compiler literals**: `#file`, `#line`, `#column`, `#function` are parsed as
  `A.MagicLit` and emitted as literals; `#function` uses the current procedure
  description (`main` at top level, otherwise `name()`).
- **Conditional compilation**: `lexer.preprocess` blanks inactive branches
  before parsing; the parser is unaware of `#if`.
- **Custom operators**: operator functions are emitted as Nim backtick procs
  (`` proc `**`*(...) ``), including static operators of a type/extension.
  `gen_binary`/`gen_unary`/`gen_postfix_unary` first look up a user operator
  function with matching operand types and emit an explicit call (so operator
  precedence from the Swim parser is preserved regardless of Nim's own
  operator precedence).
- **Nested types** are emitted as flattened Nim types (`Outer_Inner`). Member
  lookup understands `Outer.Inner` type references and unqualified nested
  names inside the enclosing type (including static contexts).
- **Static computed properties** generate `Type_name()` getter procs and
  `Type_name_set(value)` setter procs (no `self` parameter); reads/writes on
  `Type.name` call them explicitly.
- **Static subscripts** generate dedicated accessor procs
  (`swimStaticSubscriptGet...` / `...Set...`) because Nim's `[]` syntax cannot
  be used on types; `Type[index]` expression/assignment codegen calls them
  directly.

### 5. Compiler CLI (`cli.py`)

- Subcommands `run/build/check/emit/new/deps/test`; plain `Swim file.sw` is
  equivalent to `run`.
- Generated files and binaries are cached in the system temp directory under
  `Swim-build-cache/src-<hash>`. The cache key includes the paths and sources of
  **all** project modules (any change recompiles), the compiler version, the
  runtime source hash, Nim flags and the memory-management mode.
- `deps` reuses `modules.Project` to print the import graph and dependency
  execution order.
- Nim subprocess: `nim c --mm:arc --hints:off --warnings:off --path:<runtime>`.
  `--mm:arc` is the fixed memory-management strategy (ARC, no tracing GC); the
  `NIM_MEMORY_MANAGEMENT` constant in `cli.py` also participates in the cache
  key.

## Memory management

- Generated programs are always compiled with `--mm:arc`: class instances use
  reference counting and are released immediately when the count reaches zero.
- Nim ref-object cycles are not collected (ARC has no cycle collector), which
  matches Swift ARC. The runtime does not introduce a GC.
- Value types (`struct`/`enum`) do not involve reference counting; recursive
  enums are represented with `ref`, so they are ARC-managed.

## Runtime (`runtime/swimrt.nim`)

- Re-exports `options`, `tables`, `sequtils`, `strutils`, `math`, `algorithm`,
  `sets`, `hashes`, `os`, etc.
- Defines the Swift-style API: `swimStr` (print formatting), `print`, array/
  string/dictionary helpers, optional helpers, `swimOptFlatMap`, sort
  templates, stride iterators, protocol concepts, character classification,
  hash/exception helpers, etc.
- Changing the runtime changes the cache key of generated programs, so they
  recompile automatically.

## How to extend

### Add a standard-library method

1. Add a `proc`/`template` to `runtime/swimrt.nim` (avoid name collisions with
   existing symbols).
2. Register it in the corresponding place in `codegen.py`:
   - collection/string methods → `_array_method`, `_string_method`,
     `_dict_method`, `_set_method`, `_numeric_method`, `_optional_method`;
   - properties → `code_builtin_property`;
   - static members/constructors → `code_prim_static_member`,
     `code_prim_static_call`, `code_builtin_type_construct`;
   - global functions → `code_builtin_free_call`.
3. Add `tests/cases/*.sw` plus expected output, then run
   `python3 tests/run_tests.py`.

### Add a built-in module

Two kinds of built-in modules exist:

1. **No-op modules** (`Foundation`, `Swift`, `Math`, ...): the name is
   registered in `modules.BUILTIN_MODULES` and importing it does nothing,
   because `runtime/swimrt.nim` already provides the Swift-style API.  To add
   one of these, implement the API in `swimrt.nim` and register the name.
2. **Native modules**: a separate Nim module in `runtime/` is linked into the
   generated program, which is how a whole Nim library is exposed to Swim.
   `Nimx` (`runtime/swimnimx.nim`) is the oldest one; `FerroUI`
   (`runtime/swimferroui.nim`, the binding of SwimUI) is the reference for a
   binding of a library that is not written in Nim:
   - register the Swim name and its Nim module in `modules.NATIVE_MODULES`
     (`{"FerroUI": "swimferroui"}`); `gen_header` then emits
     `import swimferroui` into the generated Nim, and `load_project` records
     the import in `Project.native_modules`;
   - register the Swim-facing functions in the module's own table
     (`codegen.FERROUI_FUNCS`): `name -> (nim proc, [(argument label, kind)],
     return kind)`, where kind is `int`, `double`, `string`, `bool` or
     `closure` (`() -> Void`; supports the trailing closure syntax).  The
     kinds of the module are its own map (`FERROUI_KINDS`); the return kinds
     are in `NATIVE_RESULT_TYPES`.  `CodeGen.code_native_call` (reached through
     `code_nimx_call`, `code_zeta_call` or `code_ferroui_call`) generates the
     call, matches argument labels and type-checks the arguments;
   - keep the Nim wrapper's signature identical (positional order) to the
     table entry;
   - build programs with `--nim-arg:--path:<library>` so the Nim compiler can
     find the wrapped library.  `FerroUI` instead builds a shared library
     (`ffi/`, a Rust `cdylib`) once with `scripts/build-ffi.sh`; the Nim module
     declares its C ABI with `{.importc, cdecl, dynlib.}` and finds it in
     `build/` (override: `-d:swimFerroUILibDir=<dir>`), so a program build
     needs no C compiler arguments at all.  Everything native stays on the
     other side of a flat ABI of integers, doubles, strings and C callbacks.
3. For compiler-only behaviour (special static members, operators, ...) of a
   built-in name, implement it in `codegen.py`.
4. Add a test that imports the module name and compiles.

### Add a language feature

1. AST: add nodes in `ast_nodes.py`.
2. Parsing: produce the nodes in the appropriate parser functions.
3. Types/symbols (if needed): extend `types.py`.
4. Generation: implement in `codegen.py`'s `gen_expr`/`gen_stmt` or the
   specific declaration generator.
5. Forward declarations/naming: check whether a new `ProcJob` or helper
   procedure is needed.
6. Tests: cover at least the success path, the error path and interactions
   with existing features.

### Add a new kind of type member (example: subscripts)

Subscript declarations are collected in `TypeInfo.subscripts` /
`ExtensionInfo.subscripts` (see `types.py`) and generated by
`CodeGen.add_subscript_jobs`. Call sites resolve them through
`Registry.find_subscripts`; generic receivers use the protocol subscripts
found by `CodeGen._generic_subscripts`.

## Test framework

`tests/run_tests.py`:

- `tests/cases/*.sw`: single-file success programs; stdout is compared with
  `tests/expected/<name>.out`.
- `tests/projects/<name>/main.sw`: multi-file projects; expected output is
  `tests/expected/<name>.out`.
- `tests/errors/*.sw` and `tests/errors/<name>/main.sw`: expected compile
  failures; the first line of `tests/errors/<name>.err` must appear in the
  compiler output.
- Runs in parallel (`--jobs`); `--filter` filters and `--update` regenerates
  expected output.
- Tests use `bin/Swim run` (the full compile + run pipeline).
- An optional `tests/cases/<name>.flags` file supplies extra compiler flags
  (for example ``-D FANCY``) to that test program.

## Known implementation trade-offs

- Nim's `method` dynamic dispatch and `super` are implemented with impl procs
  plus wrappers, so `Swim emit` contains method pairs for class methods.
- The `swimOptFlatMap` template evaluates the outer expression once (saved in a
  temporary); pure expressions are unaffected. If the base of an optional chain
  has side effects, store it in a variable first.
- Multi-line closures in argument position generate multi-line Nim; Nim's
  parenthesis indentation rules are covered by tests.
- Top-level variable types must be inferable from their initializer, otherwise
  an explicit annotation is required.
- Recursive enums use `ref` representation and therefore have reference
  semantics (Swift recursive enums usually use `indirect`), and are managed by
  ARC.
- Reference cycles are not collected automatically (matching Swift ARC).
- Multi-file modules merge into a single Nim module: declarations share one
  flat namespace, and duplicate types/global variables across files are errors;
  functions are de-duplicated by signature. Imported modules' top-level
  statements run before the entry file.
- Module resolution is path-based (no package manager/download): it searches
  the importing file's directory, entry directory, cwd and `SWIM_PATH`; local
  `.sw` files take precedence over built-in module names.
- Observed properties cannot be `static` or declared in an extension (stored
  properties are not allowed there). Their backing field is a normal Nim field,
  so it appears in `Swim emit` and in the synthesized `$`/`==`/`hash` output
  through the getter.
- Failable initializers rely on the internal `bool`-returning init proc; the
  generated Nim signature differs from the `.sw` signature (`Swim emit` shows
  it). `init!` crashes on `nil` at the call site (like Swift's implicit unwrap).
- Subscript declarations are supported for concrete types and extensions; the
  concept generated for a protocol does not spell out subscript requirements,
  they are checked when a generic body is instantiated.
- Protocol/existential limitations still apply: `[any P]` and `Any` erasure
  are not supported.
- `#file`/`#line` are resolved from the composed source, so in multi-file
  projects they report the entry file and composed line numbers.

## License

This project is released under the MIT License (see `LICENSE`) and is an
independent implementation: it uses no code from the official Swift repository
or the Swift standard library.
