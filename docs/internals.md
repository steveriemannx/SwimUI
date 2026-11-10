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
  ├─ checker.py   : pure-Python static semantic checks / diagnostics
  ├─ codegen_c.py : Registry + AST → C source + type metadata + line mapping
  └─ cc           : C source + runtime/swimrt*.c → native executable
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
  constraint list while parsing (the checker verifies them structurally);
  same-type constraints are parsed and ignored.
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
  (`Outer.Inner`) and mangled C names (`Outer_Inner`); `TypeInfo.parent` /
  `TypeInfo.nested` support unqualified lookup inside the enclosing type and
  `Outer.Inner` lookup outside. Nested `typealias` declarations are available
  in the type's generic/nested environment.
- Operator functions are collected in `Registry.operators` keyed by
  `(fixity, symbol)`; static operators declared in types/extensions are
  registered the same way.

### 4. Static checking (`checker.py`) and the C backend (`codegen_c.py`)

- `checker.py` performs the front-end's static semantics on the AST built by
  the parser and the symbol tables from `types.py`.  It is pure Python and
  emits nothing.  It reports mutability errors (assignment to `let` constants,
  `let` properties, static `let`s and read-only subscripts), unknown members on
  user types and built-in values, implicit conversion failures, missing
  arguments, invalid enum cases, misplaced `fallthrough`, `guard` blocks that
  do not exit, non-`nil` returns from failable initializers, user-defined
  assignment operators, retired native-module references and similar errors.
  Diagnostics carry composed line numbers so the CLI maps them back to the
  originating module file.
- `codegen_c.py` is the **direct C backend** and the only code generator.  It
  lowers the checked AST to C targeting `runtime/swimrt.h`.

The C backend is deliberately *dynamic* at run time so that it can support the
full language on top of a small static checker:

- All values are pointers to refcounted objects (`SwimValue = SwimObj*`). Each
  object has an `_Atomic int64_t` refcount and a `SwimType*` descriptor holding
  its kind, name, parent, fields, enum cases, methods, properties and raw
  values.
- **Value semantics**: storing a value scans its descriptor kind and
  deep-copies value types (`SwimCopy`), while reference types (classes,
  closures, frames) are retained.
- **Assignment/coercion**: stores are wrapped in `SwimCoerce`, and expression
  results are materialised into cleanup-managed temporaries.
- **Dispatch**: method calls become `SwimCallMethod(recv, "name", "labels",
  argc, argv)`; the runtime matches signature by name/labels/arity/argument
  types, fills defaults, binds inout cells and invokes a uniform
  `SwimValue (*)(SwimFrame*, int, SwimValue*)` function.
- **Type descriptors** are emitted with forward declarations, then one
  `__swim_register()` registers every method, initializer, property,
  subscript, operator, enum case and `deinit`.
- **Statements** lower to runtime iteration, pattern predicates, `setjmp`
  exception frames, `defer` scopes and `goto`-based break/continue.
- **ARC**: temporaries are released at statement boundaries; frames and
  closures own their references.  Weak/unowned holders register with their
  target's weak list; `deinit` runs derived-first after the refcount reaches
  zero.
- **Errors**: C compiler diagnostics are mapped back through `line_map`.

### 5. Compiler CLI (`cli.py`)

- Subcommands `run/build/check/emit/new/deps/test`; plain `Swim file.sw` is
  equivalent to `run`.
- Generated files and binaries are cached in the system temp directory under
  `Swim-build-cache/src-<hash>`. The cache key includes the paths and sources of
  **all** project modules (any change recompiles), the compiler version, the
  runtime source hash, C compiler flags and the memory-management mode.
- `deps` reuses `modules.Project` to print the import graph and dependency
  execution order.
- C compiler subprocess: `cc -std=c11 -O2 -w -I runtime <generated.c>
  runtime/swimrt_core.c runtime/swimrt_collections.c runtime/swimrt_call.c
  runtime/swimrt_builtin.c runtime/swimrt_error.c -o <binary> -lm`.
  `--mm:arc` is the fixed memory-management strategy (ARC, no tracing GC); the
  `NIM_MEMORY_MANAGEMENT` constant in `cli.py` also participates in the cache
  key.

## Memory management

- Every heap object (`SwimObj`) starts with an `_Atomic int64_t` reference
  count and a `SwimType*` descriptor. `SwimRetain`/`SwimRelease` use C11
  atomic operations (`memory_order_relaxed` increments, `acq_rel`
  decrements); the object is freed when the count reaches zero. This is the
  same model as Swift's ARC and makes objects safe to share between threads.
- Reference types (classes, closures, frames) are retained on store. Value
  types (String, Array, Dictionary, Set, Tuple, struct, enum, Optional, Range)
  are copied on store by `SwimCopy`, preserving Swift value semantics.
- There is no tracing GC and no cycle collector. As with Swift ARC, reference
  cycles leak unless broken manually with `weak`/`unowned` properties.
- `weak` storage keeps a refcounted holder object registered in the target's
  intrusive weak list. The holder never retains the target; when the target's
  reference count reaches zero the runtime zeroes every registered holder slot
  before running class deinitializers. `unowned` uses the same holder without
  optionality and traps if the target was released.
- Classes declare a `deinit`; the runtime walks the class chain most-derived
  first after the refcount hits zero (weak slots are zeroed first), then frees
  the stored members. Objects are marked as destroying while `deinit` runs so
  the temporary self reference used by the generated frame cannot trigger a
  second destruction.
- Each function activation allocates a `SwimFrame` (a refcounted slot array).
  Closures capture their creating frame and retain it. Frames and temporaries
  are released by `__attribute__((cleanup))` on normal control flow. Exception
  unwinding uses `setjmp`/`longjmp` (C cleanups cannot run during a longjmp);
  the runtime runs pending `defer` blocks explicitly while unwinding, but
  temporaries in unwound C frames are not released.
- The cache key includes the runtime sources' hash, so changes to the ARC
  runtime automatically rebuild cached programs.

## Runtime (`runtime/swimrt*.c`)

The runtime is a dependency-free C11 library (only libc + libm) implementing
the dynamic object model and the Swift-style standard library:

- `swimrt.h` — the public ABI. Every generated program includes it. It defines
  `SwimValue`/`SwimObj`, `SwimKind`, `SwimType`/`SwimFieldDesc`/`SwimCaseDesc`,
  `SwimMethodEntry`/`SwimPropDesc`, the primitive/collection constructors,
  ARC functions, frame access, dispatch, member/subscript access, operators,
  iterators, exceptions/`defer` and registration hooks.
- `swimrt_core.c` — allocation, atomic retain/release, value-semantics
  `SwimCopy`, frames/globals, strings, double formatting, description/printing,
  equality/ordering/hashing, operators, optionals, coercion/casts, pattern
  helpers and fatal errors.
- `swimrt_collections.c` — arrays, dictionaries, sets, tuples, ranges,
  iterators (lazy for ranges; insertion order for dictionaries), slicing,
  stable merge sort, `map`/`filter` helpers.
- `swimrt_call.c` — the dynamic dispatcher: membership tables, signature
  binding (labels/defaults/variadic/inout), method/static/global/closure
  invocation, property/subscript access (including observer proxies),
  initializer delegation, enum construction, binding method/function
  references as closures, and program start-up.
- `swimrt_builtin.c` — the Swift-style library: string/array/dictionary/set/
  optional/number/character methods, higher-order functions, conversions,
  free functions (`print`, `min`, `max`, `abs`, `sqrt`, `zip`, ...) and
  static constructors (`Int(...)`, `String(repeating:count:)`,
  `Array(repeating:count:)`, enum `allCases`/raw-value initializers).
- `swimrt_error.c` — `setjmp`/`longjmp` exception frames, per-scope `defer`
  lists, error value construction and the type-matching helpers used by
  `catch`.

Generated code never modifies the runtime; it only calls it. Changing the
runtime changes the cache key of generated programs, so they rebuild
automatically.

## How to extend

### Add a standard-library method

1. Implement the behaviour in `runtime/swimrt_builtin.c` (for methods that
   only inspect `argv`) or in `runtime/swimrt_core.c`/`swimrt_collections.c`
   (for values that need new object kinds).
2. Add a test in `tests/cases/*.sw` with expected output, then run
   `python3 tests/run_tests.py`.
3. If the method needs special *lowering* (new syntax or a renamed runtime
   entry point), handle it in `src/swimc/codegen_c.py` (for example the
   subscript/observer/optional-chaining paths).

### Add a built-in module

Built-in module names (`Foundation`, `Swift`, `Math`, ...) are no-ops:
`modules.BUILTIN_MODULES` accepts the import and the C runtime already
provides the corresponding API. To add one, implement the API in
`runtime/swimrt_builtin.c` and register the name in `modules.py`.

#### Add a native module (C backend)

A native module binds a C library behind Swift-syntax-only declarations.  The
`FerroUI` module of this fork is the reference:

1. **Register the name** in `modules.NATIVE_MODULES` and let `load_project`
   record it on the project (`Project.native_modules`).  Retired Nim-era names
   go in `RETIRED_NATIVE_MODULES` so that importing them explains itself.
2. **Describe the functions** in a table of their own (for `FerroUI`,
   `src/swimc/native_ferroui.py`): Swift name → (C function,
   `[(argument label, kind)]`, result kind).  The kinds are `int`, `double`,
   `string`, `bool` and `closure` (`() -> Void`, which also takes a trailing
   closure); results may also be `void`.
3. **Check the calls** in `checker.py`: the import must be present, labels must
   exist and appear once, and every argument must have the kind's type.  The
   checker reports errors at the `.sw` location.
4. **Emit the calls** in `codegen_c.py`: include the module's header when the
   import is present and turn each call into a direct C call with the arguments
   in the table's order.  `CodeGen.native_call_code` does the label matching.
5. **Compile and link** in `cli.py`: a program with the module compiles the
   module's C source (a *shim*, `runtime/swimferroui.c`) into itself, adds the
   include directory of the library's header and links the shared library
   (`-L … -l … -Wl,-rpath,…`).  Include the shim and its headers in the build
   cache signature.
6. **Write the C shim** in `runtime/`: it receives the dynamic `SwimValue`s of
   generated code, converts them to the C ABI of the library, calls it, and
   converts the results back.  Closures cross as a C callback plus an opaque
   `int64_t`: keep the `SwimValue` closure in a cell, pass a trampoline and the
   cell's address, and run the closure with `SwimCallValue`.
7. **Tests**: a compiler test that the module resolves and emits the expected C,
   a test that the missing import is an error, and an end-to-end test that a
   program builds against the library and runs.

#### Fixes of this fork needed by the binding

The `FerroUI` module and the view layer needed three code-generator fixes,
each with a regression test in `tests/cases/`:

- an unqualified **global read inside a method or a closure in a method**
  resolved to `self.<name>` (and read `nil`): `expr_code` now checks the globals
  before the `has_self` fallback (`42_global_in_method.sw`);
- an **enum-case shorthand passed as an argument** (`.leading`) was emitted as
  an untyped enum case, so the dynamic dispatcher could not bind the call and
  reported `unknown function`: `gen_call` now resolves the parameter types of a
  known free function and the arguments are generated with that expected type
  (`43_enum_case_argument.sw`);
- the **return-type walk** over a statement list walked into lists of non-node
  values and crashed on some closure bodies (`_collect_return_types` now walks
  only AST nodes).

### Add a language feature

1. AST: add nodes in `ast_nodes.py`.
2. Front end: produce the nodes in the parser; extend `types.py` for symbol
   tables / type resolution when needed.
3. Static checking: teach `checker.py` the feature (type checking and
   diagnostics).
4. Backend: lower it in `codegen_c.py` (`gen_stmt`/`gen_expr_into`/
   `expr_code`/declaration collection), calling into the runtime; add runtime
   helpers in `runtime/` when the feature needs new value kinds or dispatch.
5. Registration/metadata: if the feature adds members, register them through
   the existing `register_*` helpers so dynamic dispatch can find them.
6. Tests: cover at least the success path, the error path and interactions
   with existing features.

### Add a new kind of type member (example: subscripts)

Subscript declarations are collected in `TypeInfo.subscripts` /
`ExtensionInfo.subscripts` (see `types.py`); `codegen_c.collect_subscript`
emits a getter/setter pair and registers them as `__sub_get` / `__sub_set`.
Call sites resolve to `SwimSubscriptGet`/`SwimSubscriptSet`, which dispatch to
string/array/dictionary helpers or the registered user subscripts.

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

- **Dynamic runtime**: the C backend does not monomorphise generics or emit
  specialised struct layouts. Every value is a refcounted object, so generic
  functions/types work by type erasure and method dispatch by name+signature.
  This trades raw speed for a much smaller backend; the emitted C is stable and
  readable but allocates more than a static backend would.
- **Static analysis is intentionally conservative**: `checker.py` implements
  the checks required by the language and the test suite; deeply generic code
  and built-in library calls fall back to dynamic dispatch instead of being
  statically verified. The C backend is the final source of truth.
- **Exception unwinding and cleanup**: `setjmp`/`longjmp` cannot run C cleanup
  handlers, so `defer` blocks are executed by the runtime while unwinding, but
  temporaries in the unwound C frames are not released. Avoid using thrown
  errors as normal control flow in long-running loops.
- **copy-on-store**: value types are deep-copied on every store. This keeps
  Swift value semantics correct without COW bookkeeping, at the cost of copies
  when large arrays/structs are passed around by value.
- **Top-level variable types** must be inferable from their initializer,
  otherwise an explicit annotation is required.
- **Dict/set iteration order** is insertion order for dictionaries and
  insertion order for sets; the language does not guarantee an order (tests
  sort before printing when order matters).
- **Integer overflow** follows C semantics; `%` is the C remainder operator and
  integer `/` truncates toward zero.
- Multi-file modules are merged into a single translation unit, so
  declarations share one flat namespace (duplicate names across files are
  compile errors).

## License

This project is released under the MIT License (see `LICENSE`) and is an
independent implementation: it uses no code from the official Swift repository
or the Swift standard library.
