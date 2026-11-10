> **This is the README of the Swim language project**, kept in this repository
> with the language it describes.  SwimUI keeps Swim's compiler, runtime,
> examples and tests and adds two things on top: the `FerroUI` native module
> (a C-level binding of the FerroUI UI framework, [`docs/ferroui.md`](ferroui.md))
> and the SwiftUI-shaped view layer ([`docs/swiftui.md`](swiftui.md)).  The
> compiler in this checkout has a few fixes the UI needed; the root
> [`README.md`](../README.md) lists them and is the entry point of SwimUI.

# Swim

**Swim** is a programming language that uses **Swift syntax** and compiles
**directly to C**. Source files use the `.sw` extension.

> Design goal: **write Swift syntax, compile straight to C**. The compiler front
> end performs Swift-style semantic checking, then a dedicated C backend emits
> self-contained C source that is built with the system C compiler. There is no
> intermediate language. The generated C is readable and inspectable
> (`Swim emit`), but you never need to (and should not) edit it directly.

Memory management is **Swift-style ARC**: every heap object carries an
atomically updated reference count (`runtime/swimrt.c`), value types are copied
on store, and there is no tracing GC and no cycle collector.

```swift
// Every Swim program starts executing at its top-level statements.
let language = "Swim"
let backend = "C"

func greet(_ name: String) -> String {
    return "Hello, \(name)!"
}

print(greet(language))
print("Swift syntax, \(backend) backend.")
```

```console
$ Swim run examples/hello.sw
Hello, Swim!
Swift syntax, C backend.
```

Repository: <https://github.com/steveriemannx/Swim>

---

## Table of contents

- [Features](#features)
- [Independent implementation](#independent-implementation)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Language tour](#language-tour)
- [Swift types → C representation](#swift-types--c-representation)
- [Runtime API](#runtime-api)
- [Modules and library imports](#modules-and-library-imports)
- [How it works](#how-it-works)
- [Memory management (ARC)](#memory-management-arc)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Differences from Swift / limitations](#differences-from-swift--limitations)
- [Editor support](#editor-support)
- [License](#license)

---

## Features

- **Swift syntax**: `let`/`var`, `func`, `struct`/`class`/`enum`/`protocol`/
  `extension`, argument labels, default **and variadic** parameters, closures
  and trailing closures, `$0`, `if let`/`guard let` (including the
  Swift 5.7 `if let value { ... }` shorthand), optional chaining `?.`/`!`/`??`,
  `switch` pattern matching with `fallthrough`, `for case` pattern loops,
  `do`/`catch`, `defer`, `@main`, `#file`/`#line`/`#column`/`#function`,
  conditional compilation (`#if`/`#available`, `-D` flags), nested types,
  custom operators with `precedencegroup`s, and more.
- **Direct C backend**: the compiler emits portable C11 and invokes the system
  C compiler (`cc`/`clang`/`gcc`). No Nim toolchain and no intermediate
  language are involved. Generated programs link a small C runtime
  (`runtime/swimrt*.c`).
- **Swift-style atomic ARC**: reference counts are updated with C11 atomics, so
  objects can be shared between threads. Value types (strings, arrays,
  dictionaries, sets, tuples, structs, enums, optionals, ranges) are copied on
  store; reference types (classes, closures) are retained. `weak`/`unowned`
  references and class `deinit` are supported. There is no tracing garbage
  collector and no cycle collector, exactly like Swift ARC.
- **Native GUI modules (retired)**: the previous Nim backend exposed the
  [nimx](https://github.com/yglukhov/nimx) GUI toolkit through `import Nimx`.
  The direct C backend has no GUI module yet; the example app in
  `projects-main/` is kept for historical reference and does not build with
  the C backend.
- **Broader standard library**: array/string range slicing, `zip`,
  `compactMap`/`flatMap`, Set algebra (`union`, `intersection`,
  `subtracting`, `isSubset(of:)`, ...), `Dictionary.mapValues`/`filter`,
  `min(by:)`/`max(by:)`, `randomElement`/`shuffled`, `lastIndex(of:)`,
  `elementsEqual`, numeric helpers such as `isNaN`/`isFinite`/
  `truncatingRemainder(dividingBy:)`, and more.
- **Semantic parity**: structs are value types, classes are reference types;
  enums support associated values, raw values and recursion; protocols are
  checked structurally at compile time; generic functions and types are
  type-erased and dispatch dynamically at run time, including
  `where T: Protocol` generic constraints.
- **Property observers, failable initializers and subscripts**: `willSet` /
  `didSet` (with custom parameter names) compile to getter/setter pairs over a
  hidden backing field; `init?` / `init!` return optionals and support
  `guard`/`return nil` plus `super.init`/`self.init` delegation; `subscript`
  declarations (read-only and read-write, also in extensions) compile to
  runtime subscript helpers.
- **Static metaprogramming features**: nested type declarations with
  `Outer.Inner` access, user-declared operators (`infix`/`prefix`/`postfix`
  plus `precedencegroup`), static computed properties and static subscripts,
  and compile-time conditional compilation (`#if`/`#elseif`/`#else`/`#endif`,
  `#error`, `#available`) driven by `-D` flags and platform/version checks.
- **Readable compiler output**: `Swim emit` prints commented, indented C.
  Compile errors are mapped back to `.sw` source lines with a highlighted
  snippet.
- **Multi-file modules**: `import Foo` resolves `Foo.sw` next to the source or
  on `SWIM_PATH`; modules are compiled together into one executable.
  `Swim deps` shows the resolved import graph and execution order.
- **Zero-dependency compiler**: the compiler is pure Python 3 standard library;
  the runtime is a small, dependency-free C library.
- **Complete toolchain**: `run` / `build` / `check` / `emit` / `deps` / `new` /
  `test`; build caching makes repeated runs take about 0.1 s.
- **MIT licensed and fully original**: the compiler and runtime are independent
  implementations. No code is included, linked, or copied from the Swift
  repository (swiftlang/swift) or the Swift standard library.

## Independent implementation

Swim **does not use any code from the Swift repository (swiftlang/swift) or the
Swift standard library**:

- The compiler in `src/swimc/` is a brand-new Python implementation: lexer,
  recursive-descent/Pratt parser, type system and C code generator are all
  original. It does not depend on a Swift toolchain and does not copy Swift
  sources. The static checker and the C backend are pure-Python/C and do not
  depend on any other language toolchain.
- The runtime in `runtime/swimrt*.c` is an original C library; generated
  programs only depend on it and the C standard library.
- At the language-design level, Swim follows Swift's syntax conventions
  (keywords, operator precedence, optional semantics, ...). Those are syntax
  conventions, not Swift implementation code; the repository contains no source
  file, compiler code or standard-library code copied from the Swift project.
- The project is released under the MIT license (see [LICENSE](LICENSE)) and
  contains no Swift project copyright files or third-party Swift code.

The whole repository is: a Python compiler, a C runtime, examples, tests,
documentation and editor grammar definitions.

## Installation

Requirements:

1. **A C11 compiler**: `clang` or `gcc` (on macOS the `cc` that ships with the
   Command Line Tools is enough).
2. **Python 3.9+** (only for the compiler; standard library is enough)

Verify your environment:

```console
$ cc --version
Apple clang version 21.0.0
$ python3 --version
Python 3.14.4
```

Run directly from a checkout (no installation needed):

```console
$ ./bin/Swim run examples/hello.sw
```

Install into your `PATH` (creates a symlink in `PREFIX/bin`, default
`/usr/local`):

```console
$ ./install.sh                 # or: PREFIX=$HOME/.local ./install.sh
$ Swim version
```

## Quick start

```console
$ Swim new hello               # create hello.sw from a template
$ Swim run hello.sw            # compile and run
$ Swim build hello.sw -o hello # produce a native executable
$ Swim emit hello.sw           # inspect the generated C source
$ Swim check hello.sw          # compile without running
$ Swim deps app.sw             # show resolved imports and module order
```

`Swim run` passes arguments after `--` to the program (plain arguments after
the file name also work):

```console
$ Swim run app.sw one two
$ Swim run -D DEBUG app.sw     # define a #if DEBUG flag
$ Swim run app.sw --cc-arg:-O3   # extra C compiler flag
```

Memory management is always Swift-style atomic ARC (`--mm atomicArc` is
accepted for compatibility). `--cc-arg <flag>` (repeatable, also
`--cc-arg:<flag>`) passes extra flags to the C compiler, for example
optimisation or include paths.

## Language tour

### Variables and constants

```swift
let name = "Swim"        // constant
var count = 3            // variable
count += 1
let ratio: Double = 3.5  // explicit type annotation
```

### Functions

```swift
func greet(name: String, from city: String = "the world") -> String {
    return "Hi \(name) from \(city)"
}

print(greet(name: "Ada"))
print(greet(name: "Ada", from: "Paris"))

func swapValues(_ a: inout Int, _ b: inout Int) { ... }
swapValues(&count, &count)
```

### Structs, classes, enums

```swift
struct Point: Equatable {
    var x: Int
    var y: Int
    func lengthSquared() -> Int { x * x + y * y }
    mutating func move(dx: Int, dy: Int) { x += dx; y += dy }
    static func origin() -> Point { Point(x: 0, y: 0) }
}

class Animal {
    var name: String
    init(name: String) { self.name = name }
    func speak() -> String { "..." }
}
class Dog: Animal {
    override func speak() -> String { "Woof" }
}

enum Shape {
    case circle(radius: Double)
    case point
}
func area(_ shape: Shape) -> Double {
    switch shape {
    case .circle(let radius): return 3.14159 * radius * radius
    case .point: return 0
    }
}
```

### Optionals

```swift
let present: Int? = 5
let missing: Int? = nil
print(present!, present ?? 0)

if let value = present {
    print(value)
}
guard let value = Int("42") else { return }
print(present != nil)

struct Engine { var power: Int }
struct Car { var engine: Engine? }
let car = Car(engine: Engine(power: 300))
print(car.engine?.power ?? 0)
```

### Property observers, failable initializers and subscripts

```swift
struct Temperature {
    var celsius: Int = 0 {
        willSet { print("warming to \(newValue)") }
        didSet { print("was \(oldValue)") }
    }
}

struct User {
    let name: String
    init?(name: String) {
        guard !name.isEmpty else { return nil }
        self.name = name
    }
}

struct Matrix {
    var cells: [[Int]]
    subscript(row: Int, column: Int) -> Int {
        get { cells[row][column] }
        set { cells[row][column] = newValue }
    }
}
```

### Variadic parameters and initializer delegation

```swift
func sum(_ values: Int...) -> Int {
    var total = 0
    for value in values { total += value }
    return total
}
print(sum(), sum(1, 2, 3))

struct Point {
    var x: Int
    var y: Int
    init(x: Int, y: Int) { self.x = x; self.y = y }
    convenience init(origin: Int) { self.init(x: origin, y: origin) }
}
```

### Closures and higher-order functions

```swift
let double = { (value: Int) -> Int in value * 2 }
let numbers = [1, 2, 3, 4, 5]

print(numbers.map { $0 * $0 })
print(numbers.filter { $0 % 2 == 0 })
print(numbers.reduce(0) { $0 + $1 })
print(numbers.sorted { $0 > $1 })
print(numbers.first(where: { $0 > 2 })!)
```

### Error handling

```swift
enum ValidationError: Error {
    case empty
    case tooShort(minimum: Int)
}

func validate(_ password: String) throws -> String {
    if password.isEmpty { throw ValidationError.empty }
    if password.count < 6 {
        throw ValidationError.tooShort(minimum: 6)
    }
    return "ok"
}

do {
    print(try validate("abc123"))
} catch ValidationError.tooShort(let minimum) {
    print("need \(minimum) characters")
} catch {
    print("other error")
}
```

### Custom operators and nested types

```swift
infix operator **: MultiplicationPrecedence
func ** (base: Int, power: Int) -> Int { ... }

precedencegroup ForwardApplication {
    associativity: left
    lowerThan: AdditionPrecedence
}
infix operator |>: ForwardApplication
func |> (value: Int, transform: (Int) -> Int) -> Int { transform(value) }
print(5 |> { $0 * 3 })

struct Outer {
    struct Inner { var value: Int }
    enum State { case idle, running }
    var inner: Inner
    var state: State
}
let inner = Outer.Inner(value: 1)
```

### Conditional compilation

```swift
#if DEBUG
print("debug build")
#else
print("release build")
#endif

if #available(iOS 13, *) {
    print("modern API")
}
```

`-D DEBUG` on the command line defines custom flags. `SWIM`, `swift(>=5.0)`,
`canImport(...)`, `os(...)` and `arch(...)` are built-in conditions.
`#error` aborts compilation when its branch is active.

### Generics and protocols

```swift
protocol Shape {
    func area() -> Double
    var name: String { get }
}

extension Shape {
    func describe() -> String { "\(name): \(area())" }
}

struct Square: Shape {
    var side: Double
    var name: String { "square" }
    func area() -> Double { side * side }
}

func largest<T: Comparable>(_ values: [T]) -> T? { ... }

struct Stack<Element> {
    private var items: [Element] = []
    mutating func push(_ item: Element) { items.append(item) }
    mutating func pop() -> Element? { items.popLast() }
}
```

## Swift types → C representation

| Swim (Swift syntax) | C representation | notes |
| --- | --- | --- |
| `Int` / `Int8` … `Int64` | boxed `int64_t` (`SwimInt`) | signed integers |
| `UInt` … | boxed integers | unsigned integers |
| `Double` / `Float` | boxed `double` | floating point |
| `Bool` / `Character` | boxed `bool` / `char` | |
| `String` | refcounted immutable byte string (`SwimString`) | |
| `T?` | refcounted optional wrapper (`SwimOptional`) | `nil`, `!`, `??` all work |
| `[T]` | refcounted array of `SwimValue` | dynamic array |
| `[K: V]` | insertion-ordered hash table | subscript returns `V?` |
| `Set<T>` | refcounted hash set | |
| `(A, B)` / `(x: A, y: B)` | refcounted tuple with named slots | labels preserved |
| `(A) -> B` | refcounted closure (`fn` + captured frame) | |
| `struct` | refcounted box with value semantics (copied on store) | value type |
| `class` (with inheritance) | refcounted object with a type descriptor and parent link | dynamic dispatch |
| `enum` | tagged object (`tag` + payload slots) | associated values and raw values |
| `enum E: Error` | tagged enum/struct value thrown through the runtime | `throw` / `catch` |
| `protocol` | compile-time structural check; calls dispatch by name | generic constraints |
| `extension` | extra methods/properties/subscripts registered on the type | also extends `Int`/`String`/`Array` |
| `typealias` | resolved at compile time | zero cost |
| `willSet`/`didSet` | generated getter/setter registered as a property | observers |
| `subscript` | generated getter/setter helpers | read-only and read-write |
| `@main struct` | generated `main()` call | |

Type descriptors, enum case metadata, default-argument thunks and member
registration are all generated into the emitted C file; every object header
carries an atomically refcounted `_Atomic int64_t` and a pointer to its
`SwimType` descriptor.

## Runtime API

`runtime/swimrt.h` / `runtime/swimrt*.c` provide a Swift-style standard library
(generated programs link it directly):

- **Printing**: `print(_:)` (with `separator:` and `terminator:`),
  `debugPrint`, `fatalError`, `assert`, `precondition`, `readLine()`, `exit()`.
- **Strings**: `count`, `isEmpty`, `uppercased/lowercased/capitalized`,
  `hasPrefix/hasSuffix/contains`, `split(separator:)`,
  `components(separatedBy:)`, `joined(separator:)`,
  `replacingOccurrences(of:with:)`, `trimmingCharacters(in:)`,
  `prefix/suffix/dropFirst/dropLast`, `reversed()`, `index(of:)`,
  `firstIndex(of:)`, `first/last`, string repetition initializers.
- **Characters**: `isNumber/isLetter/isWhitespace/isUppercase/isLowercase`,
  `wholeNumberValue`, case conversion.
- **Arrays**: `count/isEmpty/first/last`, `append/insert/remove/removeFirst/
  removeLast/removeAll(where:)`, `map/compactMap/flatMap/filter/reduce/
  forEach/allSatisfy/contains(where:)/first(where:)`, `sorted/sorted(by:)/
  sort/shuffled/reversed`, `prefix/suffix/dropFirst/dropLast`, `min/max(by:)`,
  `randomElement`, `enumerated`, `index(of:)/firstIndex(of:)/lastIndex(of:)`,
  `joined(separator:)`, `elementsEqual`, `zip`.
- **Dictionaries**: `count/isEmpty/keys/values`, `updateValue(_:forKey:)`,
  `removeValue(forKey:)`, `mapValues`, `filter`, iteration pairs.
- **Sets**: `insert/remove/contains`, algebra (`union`, `intersection`,
  `subtracting`, `isSubset`, `isSuperset`, `isDisjoint`, `formUnion`, ...),
  `sorted`, general sequence helpers.
- **Optionals**: `map`, `flatMap`, `!`, `??`, `if let` / `guard let` lowering.
- **Numbers**: `isNaN/isFinite/isInfinite`, `truncatingRemainder(dividingBy:)`,
  `advanced(by:)`, `signum`, `rounded`, `isMultiple(of:)`, math helpers
  (`abs`, `sqrt`, `pow`, `floor`, `ceil`, `round`, `min`, `max`).
- **Pattern matching**: enum tag/payload helpers, optional-pattern helpers and
  type-check/cast helpers (`is`, `as?`, `as!`).
- **ARC**: `SwimRetain`, `SwimRelease`, `SwimCopy` (value semantics),
  `SwimStore`, plus frame/closures/defer/exception support.

## Modules and library imports

Imports come in two layers. **Only Swift syntax is ever used; no foreign code
is imported into `.sw` files.**

### 1. Built-in modules (zero cost, provided by the runtime)

The following module names are accepted and treated as no-ops (the C runtime
already provides the corresponding Swift-style API):

```swift
import Foundation
import Swift
import Glibc        // also Darwin / Dispatch / ObjectiveC
import Math         // also Strings / Collections / Random / Time
```

`Foundation` etc. exist for source compatibility with Swift; Swim does not
emulate the complete Foundation/Cocoa APIs (there is no `URLSession` or
`JSONDecoder`, for example).

### 2. Swim modules (the recommended way)

`import Foo` / `import Foo.Bar` resolves to a **`.sw` source file**:

```swift
// MathX.sw
func triple(_ value: Int) -> Int { value * 3 }

// Greeter.sw
import MathX

struct Greeter {
    var name: String
    func greet() -> String { "Hi \(name), triple=\(triple(name.count))" }
}

// main.sw
import Greeter
print(Greeter(name: "Swim").greet())
print(triple(7))
```

```console
$ Swim run main.sw
Hi Swim, triple=12
21
```

Resolution rules:

- `import Foo` → `Foo.sw` or `Foo/main.sw`
- `import Foo.Bar` → `Foo/Bar.sw` or `Foo/Bar/main.sw`
- Search order: **directory of the importing file → entry file directory →
  current working directory → `SWIM_PATH` (colon-separated list of
  directories)**
- A local `.sw` file takes precedence over a built-in module name (so you can
  shadow names like `Math`).
- There is no package manager or dependency download: modules are source files
  placed in one of the search locations.

Compilation model:

- All imported modules and the entry file are **merged into one program** and
  compiled together.
- Top-level statements of imported modules run **dependencies first** (each
  module runs at most once), then the entry file's top-level statements. Import
  cycles expand deterministically by first-load order.
- Declarations share one flat namespace; declaring the same type, global
  variable or function signature in two different files is a compile error.
  Same-name functions with different signatures are overloads.
- Only the entry file may declare `@main`.

Inspect the resolved graph and execution order:

```console
$ Swim deps main.sw
module import graph for main.sw (execution order, dependencies first):
  1. MathX.sw
  2. Greeter.sw
     imports: MathX -> MathX.sw
  3. main.sw  (entry)
     imports: Greeter -> Greeter.sw
```

### 3. Native modules (retired)

The Nim backend used to expose Nim libraries (most notably the nimx GUI
toolkit) as *native modules*. The direct C backend does not support that
mechanism: `import Nimx` is rejected, and every program is built from the
emitted C plus `runtime/swimrt*.c`. `projects-main/` keeps the retired GUI
demo for historical reference.

## How it works

```
 .sw source files (one or more; imports resolved first)
   │  modules.py   resolve imports, load dependencies, merge ASTs
   │  lexer.py     tokenize Swift syntax (including string interpolation)
   │  parser.py    recursive descent → AST
   │  types.py     collect types/functions/members, build symbol tables
   │  checker.py  : pure-Python static checking and diagnostics
   │  codegen_c.py : AST -> C source + runtime type/registration metadata
   ▼
 .c file ──► C compiler (cc/clang/gcc) ──► native executable (linked with swimrt)
```

- Generated programs always have the same structure: type declarations →
  global variables → forward declarations → procedure definitions → top-level
  statements in source order (including global initialization).
- Optional chaining lowers to runtime optional helpers; `if let` / `guard let`
  become runtime `is-some`/unwrap checks; enum pattern matching becomes guarded
  `if` chains with payload extraction; closures become `SwimMakeClosure` with a
  captured frame; `defer` becomes a runtime scope; `throw`/`catch` use
  `setjmp`/`longjmp` frames in the runtime.
- Programs are always linked with the atomic-ARC C runtime. C compiler errors are
  mapped back to `.sw` line numbers, for example:

```console
$ Swim run broken.sw
broken.sw:1:14: error: expected parameter name, found '->'

   1 | func broken( -> Int {
                    ^
```

Actual `Swim emit examples/hello.sw` output (excerpt):

```c
/* Generated by Swim 0.2.0 -- direct C backend. */
#include "swimrt.h"
...
int main(int argc, char** argv) {
    SWIM_FRAME_TEMP(__fr);
    __fr = SwimFrameNew(NULL, 8);
    SwimProgramStart(argc, argv);
    SwimGlobalsInit(2);
    __swim_register();
    SWIM_TEMP(t1);
    t1 = SwimCStr("Swim");
    SwimGlobalSet(0, t1);
    ...
    t4 = SwimConcat(3, SwimCStr("Hello, "), SwimStr(t5), SwimCStr("!"));
    t3 = SwimCallGlobal("print", "_", 1, (SwimValue[]){ t4 });
    return 0;
}
```

## Memory management (ARC)

Every Swim program uses **Swift-style automatic reference counting (ARC)**,
implemented entirely in the C runtime:

- Every heap object starts with an `_Atomic int64_t` reference count that is
  updated with C11 atomic operations (`relaxed` increments, acquire/release
  decrements). This is the same model as Swift's ARC; objects can be shared
  between threads.
- `class` instances and closures are reference types: assignment retains them.
  `struct`, `enum`, `String`, arrays, dictionaries, sets, tuples, optionals and
  ranges are value types: storing them copies the value (`SwimCopy`), so value
  semantics is preserved without copy-on-write tricks.
- There is **no tracing garbage collector**, no cycle collector and no runtime
  dependency on a GC.
- As with Swift ARC, **reference cycles are not collected automatically**. If
  two classes hold strong references to each other (for example
  `parent`/`children`), break the cycle manually.
- `weak var` and `unowned var` break reference cycles: weak references are
  zeroed automatically when the target is deallocated (they must be optional
  class properties), unowned references are non-owning and trap on access
  after the target was released. As in Swift they are only allowed on stored
  properties of classes.
- Classes may declare a `deinit` block; it runs when the last strong
  reference is released, derived deinitializers run before the superclass
  ones, and stored members are released after `deinit` completes. Weak
  references are zeroed before `deinit` runs.
- Variables live in heap-allocated activation frames; closures capture the
  frame pointer and retain it. `defer` blocks run on normal scope exit, on
  `return`, and while exceptions unwind.
- Frames and temporaries are released with `__attribute__((cleanup))` on
  normal control flow. (Unlike Swift, a `setjmp`/`longjmp` exception unwind
  cannot run C cleanup handlers; the runtime runs `defer` blocks explicitly,
  but temporaries in the unwound C frames are not released. Programs that
  throw very frequently in long-running loops should be aware of this.)

## Project layout

```
Swim/
├── bin/Swim                  # launcher (Python compiler entry point)
├── src/swimc/                # compiler (Python, standard library only)
│   ├── lexer.py              # lexer
│   ├── parser.py             # recursive-descent parser
│   ├── modules.py            # import resolution / multi-file merging
│   ├── ast_nodes.py          # AST nodes
│   ├── types.py              # type system / symbol tables / registry
│   ├── checker.py            # static semantic checks (pure Python)
│   ├── codegen_c.py          # direct C backend (AST -> C + type metadata)
│   ├── cli.py                # command line interface
│   └── errors.py             # diagnostics
├── runtime/                  # atomic-ARC C runtime + Swift-style library
│   ├── swimrt.h              #   public runtime ABI
│   ├── swimrt_core.c         #   objects/ARC/values/printing/operators
│   ├── swimrt_collections.c  #   arrays/dicts/sets/iteration/sorting
│   ├── swimrt_call.c         #   dispatch/members/subscripts/registration
│   ├── swimrt_builtin.c      #   Swift-style standard library
│   └── swimrt_error.c        #   exceptions and `defer` scopes
├── tests/                    # end-to-end tests (41 programs + 30 error cases)
│   ├── run_tests.py
│   ├── cases/                # single-file .sw programs
│   ├── projects/             # multi-file projects (main.sw + modules)
│   ├── expected/             # expected output
│   └── errors/               # expected compile failures
├── examples/                 # getting-started examples
├── docs/                     # language reference and implementation notes
├── editors/vscode/Swim/      # VS Code syntax highlighting extension
├── projects-main/            # legacy nimx GUI demo (not built by the C backend)
├── install.sh
├── LICENSE                   # MIT
└── README.md
```

## Testing

```console
$ python3 tests/run_tests.py            # run all end-to-end tests in parallel
$ python3 tests/run_tests.py -v         # more detail
$ python3 tests/run_tests.py --filter optional
$ python3 tests/run_tests.py --update   # regenerate expected output
$ Swim test                             # same, from the repository
```

Currently **71/71 tests pass**, covering: basic types and control flow,
functions and closures, optionals, collections, structs, classes and
inheritance, enums and pattern matching, protocols and generics, error
handling, string APIs, `@main`, multi-file module imports, weak/unowned
references and `deinit`, plus 30 compile error diagnostics.

## Differences from Swift / limitations

Swim is not a complete implementation of Swift, nor a Swift compiler. Explicit
limitations:

- **No native modules**: the direct C backend does not import Nim libraries or
  GUI toolkits; `import Nimx` (the old nimx bridge) is no longer supported.
- **Not supported** (they produce compile errors): `async`/`await`,
  `associatedtype` / generic protocols, dynamic protocol existentials (`any P`
  as a variable type), `Any` type erasure, property wrappers, and Nim
  ecosystem imports. `import Foundation` is accepted and ignored.
- **String subscripts use integers** (`text[0]` returns a `Character`) rather
  than Swift's `String.Index`.
- **Protocols** are checked structurally at compile time; generic functions and
  structs with `T: Protocol` work well, but heterogeneous protocol arrays
  (`[any Shape]`) are not supported.
- **Integer division**: `/` between integers truncates toward zero (C
  semantics); `%` is the C remainder operator.
- **Print formatting** is close to Swift but not identical: `Optional(5)`,
  arrays as `[1, 2]`, structs as `Point(x: 1, y: 2)`, classes print their name
  by default.
- Recursive enums are boxed, so recursive enums have reference-like
  representation (value semantics are still preserved by copying).
- ARC memory management: reference cycles are not collected automatically;
  break them with `weak`/`unowned` properties, and use `deinit` for cleanup.
- **No package manager**: modules are source files resolved from directories /
  `SWIM_PATH`; dependencies are never downloaded automatically.
- **No direct Nim ecosystem imports**: `.sw` files may not contain Nim code;
  native modules were retired together with the Nim backend.
- Declarations across modules share a flat namespace; duplicate same-name
  types/global variables/same-signature functions in different files are
  compile errors (same-name overloads with different signatures are allowed).

## Editor support

`editors/vscode/Swim/` contains a VS Code extension (syntax highlighting,
bracket matching, indentation rules):

```console
$ cd editors/vscode/Swim
$ code --extensionDevelopmentPath="$(pwd)"
```

`editors/vscode/Swim/syntaxes/Swim.tmLanguage.json` is a standard TextMate
grammar and also works with Sublime Text / TextMate / Zed and other editors.

## License

Swim is released under the **MIT License**, see [LICENSE](LICENSE).

Copyright (c) 2026 steveriemannx

This is an independent implementation: no code from the official Swift
repository (swiftlang/swift) or the Swift standard library is used.
