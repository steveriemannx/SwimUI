> **This is the README of the Swim language project**, kept in this repository
> with the language it describes.  SwimUI keeps Swim's compiler, runtime,
> examples and tests unchanged and adds the `FerroUI` native module:
> [`docs/ferroui.md`](ferroui.md) is the binding reference and the root
> [`README.md`](../README.md) is the entry point of SwimUI.

# Swim

**Swim** is a programming language that uses **Swift syntax** and compiles to
**Nim** for execution. Source files use the `.sw` extension.

> Design goal: **write Swift syntax only — never mix in Nim**. Every token in a
> `.sw` file is Swift-style; Nim is only the invisible execution backend. The
> generated Nim is readable and inspectable (`Swim emit`), but you never need
> to (and should not) edit it directly.

```swift
// Every Swim program starts executing at its top-level statements.
let language = "Swim"
let backend = "Nim"

func greet(_ name: String) -> String {
    return "Hello, \(name)!"
}

print(greet(language))
print("Swift syntax, \(backend) backend.")
```

```console
$ Swim run examples/hello.sw
Hello, Swim!
Swift syntax, Nim backend.
```

Repository: <https://github.com/steveriemannx/Swim>

---

## Table of contents

- [Features](#features)
- [Independent implementation](#independent-implementation)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Language tour](#language-tour)
- [Swift types → Nim types](#swift-types--nim-types)
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
- **Nim backend**: compiles to native executables with Nim/C-class speed, using
  Nim's **ARC** (automatic reference counting) memory management — no tracing
  GC, no cycle collector. `--mm atomicArc` switches to Swift-style atomically
  refcounted ARC.
- **Native GUI modules**: `import Nimx` exposes the [nimx](https://github.com/yglukhov/nimx)
  GUI toolkit behind Swift-style functions, so a complete GUI app can be
  written in pure Swim. See [`projects-main/`](projects-main/) for a
  phone-sized (390 × 844) example.
- **Broader standard library**: array/string range slicing, `zip`,
  `compactMap`/`flatMap`, Set algebra (`union`, `intersection`,
  `subtracting`, `isSubset(of:)`, ...), `Dictionary.mapValues`/`filter`,
  `min(by:)`/`max(by:)`, `randomElement`/`shuffled`, `lastIndex(of:)`,
  `elementsEqual`, numeric helpers such as `isNaN`/`isFinite`/
  `truncatingRemainder(dividingBy:)`, and more.
- **Semantic parity**: structs are value types, classes are reference types;
  enums support associated values, raw values and recursion; protocols map to
  Nim concepts (statically checked); generics are zero-cost, including
  `where T: Protocol` generic constraints.
- **Property observers, failable initializers and subscripts**: `willSet` /
  `didSet` (with custom parameter names) compile to getter/setter pairs over a
  hidden backing field; `init?` / `init!` return optionals and support
  `guard`/`return nil` plus `super.init`/`self.init` delegation; `subscript`
  declarations (read-only and read-write, also in extensions) compile to Nim
  `[]`/`[]=` operators.
- **Static metaprogramming features**: nested type declarations with
  `Outer.Inner` access, user-declared operators (`infix`/`prefix`/`postfix`
  plus `precedencegroup`), static computed properties and static subscripts,
  and compile-time conditional compilation (`#if`/`#elseif`/`#else`/`#endif`,
  `#error`, `#available`) driven by `-D` flags and platform/version checks.
- **Readable compiler output**: `Swim emit` prints commented, indented Nim.
  Compile errors are mapped back to `.sw` source lines with a highlighted
  snippet.
- **Multi-file modules**: `import Foo` resolves `Foo.sw` next to the source or
  on `SWIM_PATH`; modules are compiled together into one executable.
  `Swim deps` shows the resolved import graph and execution order.
- **Zero-dependency compiler**: the compiler is pure Python 3 standard library;
  the runtime is a single Nim module.
- **Complete toolchain**: `run` / `build` / `check` / `emit` / `deps` / `new` /
  `test`; build caching makes repeated runs take about 0.1 s.
- **MIT licensed and fully original**: the compiler and runtime are independent
  implementations. No code is included, linked, or copied from the Swift
  repository (swiftlang/swift) or the Swift standard library.

## Independent implementation

Swim **does not use any code from the Swift repository (swiftlang/swift) or the
Swift standard library**:

- The compiler in `src/swimc/` is a brand-new Python implementation: lexer,
  recursive-descent/Pratt parser, type system and Nim code generator are all
  original. It does not depend on a Swift toolchain and does not copy Swift
  sources.
- The runtime in `runtime/swimrt.nim` is an original Nim module; generated
  programs only depend on it and the Nim standard library.
- At the language-design level, Swim follows Swift's syntax conventions
  (keywords, operator precedence, optional semantics, ...). Those are syntax
  conventions, not Swift implementation code; the repository contains no source
  file, compiler code or standard-library code copied from the Swift project.
- The project is released under the MIT license (see [LICENSE](LICENSE)) and
  contains no Swift project copyright files or third-party Swift code.

The whole repository is: a Python compiler, a Nim runtime, examples, tests,
documentation and editor grammar definitions.

## Installation

Requirements:

1. **Nim 2.x** (including the Nim compiler): <https://nim-lang.org/install.html>
2. **Python 3.9+** (only for the compiler; standard library is enough)

Verify your environment:

```console
$ nim --version
Nim Compiler Version 2.2.12
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
$ Swim emit hello.sw           # inspect the generated Nim source
$ Swim check hello.sw          # compile without running
$ Swim deps app.sw             # show resolved imports and module order
```

`Swim run` passes arguments after `--` to the program (plain arguments after
the file name also work):

```console
$ Swim run app.sw one two
$ Swim run -D DEBUG app.sw     # define a #if DEBUG flag
$ Swim run --mm atomicArc app.sw   # Swift-style atomically refcounted ARC
$ Swim run app.sw --nim-arg:--path:/opt/nimx   # extra Nim compiler flag
```

`--mm <arc|atomicArc|orc|refc>` selects the memory management mode (`arc` is
the default) and `--nim-arg <flag>` (repeatable, also `--nim-arg:<flag>`) passes
extra flags to the Nim compiler — needed by native modules such as `Nimx`,
which build against a Nim library.

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

## Swift types → Nim types

| Swim (Swift syntax) | generated Nim type | notes |
| --- | --- | --- |
| `Int` / `Int8` … `Int64` | `int` / `int8` … `int64` | signed integers |
| `UInt` … | `uint` … | unsigned integers |
| `Double` / `Float` | `float` / `float32` | floating point |
| `Bool` | `bool` | |
| `String` | `string` | |
| `Character` | `char` | |
| `T?` / `T!` | `Option[T]` | `nil`, `!`, `??` all work |
| `[T]` | `seq[T]` | dynamic array |
| `[K: V]` | `Table[K, V]` | hash table; subscript returns `V?` |
| `Set<T>` | `HashSet[T]` | |
| `(A, B)` / `(x: A, y: B)` | `(A, B)` / `tuple[x: A, y: B]` | |
| `(A) -> B` | `proc (a: A): B {.closure.}` | closure |
| `struct` | `object` (value type) | value semantics |
| `class` (with inheritance) | `ref object of RootObj` (reference type) | dynamic dispatch via Nim `method` |
| `enum` (no associated values) | `{.pure.} enum` | |
| `enum` (associated values) | kind enum + variant object | recursive enums automatically use `ref` |
| `enum E: Error` | exception type hierarchy (`CatchableError`) | `throw` / `catch` |
| `protocol` | Nim `concept` constraint + structural checks | generic constraints |
| `extension` | top-level `proc` (with a `self` parameter) | also extends `Int`/`String`/`Array` |
| `typealias` | `type` alias | |
| `willSet`/`didSet` | getter/setter over a hidden backing field | observers |
| `subscript` | `[]` / `[]=` proc overloads | read-only and read-write |
| `@main struct` | generated `main()` call | |

Enum kind/raw values, exception types, `$`, `==`, `hash` and `allCases` helpers
are generated by the compiler.

## Runtime API

`runtime/swimrt.nim` provides a Swift-style standard library (generated code
automatically imports it):

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
  removeLast/removeAll(where:)/popLast`, `contains`, `first(where:)`,
  `firstIndex(where:)/(of:)`, `map/filter/reduce/forEach/allSatisfy`,
  `sorted/sorted(by:)/sort`, `reversed/enumerated/min/max/swapAt`,
  `prefix/suffix/dropFirst/dropLast`, `joined`.
- **Dictionaries**: `count/isEmpty/keys/values`, `updateValue(_:forKey:)`,
  `removeValue(forKey:)`, `sorted(by:)`, `mapValues`, `filter`.
- **Sets**: `count/isEmpty/insert/remove/contains`, `union`, `intersection`,
  `subtracting`, `isSubset(of:)`, `isSuperset(of:)`, `isDisjoint(with:)`,
  `formUnion`, `formIntersection`, `formSymmetricDifference`, `sorted()`,
  `map`, `filter`.
- **Numbers**: `description`, `isMultiple(of:)`, `squareRoot()`, `rounded()`,
  `isNaN/isInfinite/isFinite`, `signum`, `advanced(by:)`,
  `truncatingRemainder(dividingBy:)`, `asciiValue` (Character),
  `Int.max/min`, `Double.pi/infinity/nan`, `Int.random(in:)`,
  `Double.random(in:)`,
  `abs/min/max/pow/sqrt/floor/ceil/round/sin/cos/...`.
- **Optionals**: `!`, `??`, `if let`, `guard let`, `?.`, `map`, `flatMap`.
- **Ranges**: `a..<b`, `a...b`, `stride(from:to:by:)`,
  `stride(from:through:by:)`, slicing with `array[1..<3]` / `text[1...3]`.
- **Sequences**: `zip(_:_:)`, `compactMap`, `flatMap`, `firstIndex(of:)`,
  `lastIndex(of:)`, `elementsEqual`, `starts(with:)`, `randomElement`,
  `shuffled`, `shuffle`, `min(by:)`, `max(by:)`.

## Modules and library imports

Imports come in three layers. **Only Swift syntax is ever used; no Nim code is
imported into `.sw` files.**

### 1. Built-in modules (zero cost, provided by the runtime)

The following module names are accepted and treated as no-ops (the `swimrt`
runtime already provides the corresponding Swift-style API):

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

### 3. Nim ecosystem libraries (through native modules)

Because Swim's hard constraint is "**Swift syntax only, no mixing with Nim**",
a `.sw` file **cannot** contain `import std/xxx`, `importcpp`, pragmas, or any
other Nim code, so it cannot import a Nim library directly. Instead a bundled
library can be exposed as a **native module**:

1. Write a Nim wrapper in `runtime/` (for example
   [`runtime/swimnimx.nim`](runtime/swimnimx.nim), which wraps nimx). It
   exposes a flat, Swift-friendly API: `Int` handles, `Int`/`String`/`Bool`
   parameters and `proc()` callbacks.
2. Register the module name and its Nim implementation in
   `NATIVE_MODULES` (`src/swimc/modules.py`). Importing the name makes the
   generated Nim emit `import <nim module>`.
3. Register the Swim-facing functions — name, argument labels, parameter kinds
   and return type — in a codegen dispatch table (for `Nimx` that is
   `NIMX_FUNCS` in `src/swimc/codegen.py`), or add a built-in method as
   described in [docs/internals.md](docs/internals.md).
4. Pass the library's Nim `--path` flags to the compiler with `--nim-arg`.

`Nimx` is the reference implementation of this mechanism:

```swift
import Nimx

let screen = nimxWindow(width: 390, height: 844, title: "Swim", background: 0x0B0C10)
let title = nimxLabel(parent: screen, x: 24, y: 54, width: 260, height: 42,
                      size: 30, color: 0xF2F3F7, align: 0, bold: true,
                      text: "Library")
nimxOnTap(handle: title) {
    print("tapped")
}
nimxRun()
```

A `.sw` file still contains only Swift syntax, and the bridge lives entirely in
Nim. See [`projects-main/`](projects-main/) for a full phone-sized GUI app, its
`NimxUI.sw` Swift-style wrapper and the `run.sh` build script.

## How it works

```
 .sw source files (one or more; imports resolved first)
   │  modules.py   resolve imports, load dependencies, merge ASTs
   │  lexer.py     tokenize Swift syntax (including string interpolation)
   │  parser.py    recursive descent → AST
   │  types.py     collect types/functions/members, build symbol tables
   │  codegen.py   emit Nim (with line mapping and helper procedures)
   ▼
 .nim file ──► Nim compiler ──► native executable (linked with swimrt)
```

- Generated programs always have the same structure: type declarations →
  global variables → forward declarations → procedure definitions → top-level
  statements in source order (including global initialization).
- Swift's optional chaining `a?.b?.c` becomes `swimOptFlatMap`; `if let` /
  `guard let` become `Option` `isSome`/`get` checks; enum pattern matching
  becomes guarded `if` chains.
- Programs are always compiled with `--mm:arc` (ARC). Nim compile errors are
  mapped back to `.sw` line numbers, for example:

```console
$ Swim run broken.sw
broken.sw:1:14: error: expected parameter name, found '->'

   1 | func broken( -> Int {
                    ^
```

Actual `Swim emit examples/hello.sw` output (excerpt):

```nim
import swimrt

var language: string
var backend: string

language = "Swim"
backend = "Nim"
swimPrint(swimStr("Hello, " & swimStr(language) & "!"))
swimPrint(swimStr("Swift syntax, " & swimStr(backend) & " backend."))
```

## Memory management (ARC)

Every Swim program uses **ARC (Automatic Reference Counting)**:

- The compiler invokes Nim with `--mm:arc` by default (see `DEFAULT_MEMORY_MANAGEMENT`
  in `src/swimc/cli.py`); `Swim run/build/check --mm atomicArc` selects
  Swift-style atomically refcounted ARC (reference counts are updated
  atomically, so objects can be shared between threads). Generated binaries
  contain **no** tracing garbage collector and no Nim ORC cycle collector.
- `class` instances are ARC-managed references; `struct`/`enum` are value types
  and are copied by value.
- As with Swift ARC, **reference cycles are not collected automatically**. If
  two classes hold strong references to each other (for example
  `parent`/`children`), break the cycle manually (set one side to `nil` or
  redesign).
- `weak` / `unowned` are not supported (they are rejected at compile time);
  avoid reference cycles instead.
- Values captured by closures are also ARC-managed.

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
│   ├── codegen.py            # Nim code generation
│   ├── cli.py                # command line interface
│   └── errors.py             # diagnostics
├── runtime/swimrt.nim        # Swim runtime + Swift-style standard library
├── runtime/swimnimx.nim      # native module: nimx GUI bridge for `import Nimx`
├── projects-main/            # phone-sized Swim + nimx GUI demo (run.sh, README)
├── tests/                    # end-to-end tests (programs, projects, error cases)
│   ├── run_tests.py
│   ├── cases/                # single-file .sw programs
│   ├── projects/             # multi-file projects (main.sw + modules)
│   ├── expected/             # expected output
│   └── errors/               # expected compile failures
├── examples/                 # getting-started examples
├── docs/                     # language reference and implementation notes
├── editors/vscode/Swim/      # VS Code syntax highlighting extension
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
functions and closures, optionals, collections, structs (including property
observers and subscripts), classes and inheritance, failable/convenience
initializers, enums and pattern matching (`fallthrough`, `for case`,
`case is`), variadic parameters, protocols and generics, nested types, custom
operators, conditional compilation, error handling, string APIs, the extended
standard library, `@main`, multi-file module imports, plus 29 compile-error
diagnostics.

## Differences from Swift / limitations

Swim is not a complete implementation of Swift, nor a Swift compiler. Explicit
limitations:

- **No mixing with Nim**: you cannot write Nim inside `.sw` files (no
  `importcpp`, no `{.pragma.}`, ...). To add capabilities, extend the runtime or
  the compiler instead of inlining Nim.
- **Not supported** (they produce compile errors or are ignored):
  `associatedtype` / generic protocols, `async`/`await`, property wrappers,
  `lazy`, `weak`/`unowned`, `deinit`, dynamic protocol existentials
  (`any P` as a variable type), `Any` type erasure, custom *assignment*
  operators, and Cocoa/Foundation APIs (`import Foundation` is accepted and ignored).
- **String subscripts use integers** (`text[0]` returns a `Character`) rather
  than Swift's `String.Index`.
- **Protocols** are checked statically via Nim concepts; generic functions and
  structs with `T: Protocol` work well, but heterogeneous protocol arrays
  (`[any Shape]`) are not supported.
- **Integer division**: `/` between integers generates `div` (truncating
  toward zero) and `%` generates `mod`.
- **Print formatting** is close to Swift but not identical: `Optional(5)`,
  arrays as `[1, 2]`, structs as `Point(x: 1, y: 2)`, classes print their name
  by default.
- Recursive enums use reference representation automatically (Nim cannot inline
  recursive objects), so recursive enums have reference semantics.
- `willSet`/`didSet` keep the stored value in a hidden backing field; they are
  supported for instance properties of structs/classes, not for `static`
  properties or extension (stored) properties. `didSet`/`willSet` do not run
  while an initializer writes the property, and mutating method calls on an
  observed collection property are rewritten to read-modify-write it.
- `init?` compiles to a constructor returning `Option<T>` (`init!` unwraps at
  the call site); `super.init`/`self.init` delegation works, including for
  failable initializers.
- Subscript declarations compile to Nim `[]`/`[]=` operators. Protocol
  subscript requirements are accepted, but protocol generics are still checked
  structurally and the concept does not spell out the subscript requirement.
- `#file`/`#line` refer to the entry file in multi-file projects (diagnostics
  still map every module line correctly).
- All type declarations are emitted into one Nim `type` section, so nested
  types and source-order-independent type references work; nested types are
  addressed as `Outer.Inner` and mangled to `Outer_Inner` in the Nim output.
- Static subscripts and static computed properties are supported; static
  property observers (`static var x { didSet }`) are not.
- Custom operators support both ASCII operator characters and Unicode math/
  symbol characters (for example `≤`, `×`, `√`); `Swim emit` shows them as
  backtick Nim procs. Custom *assignment* operators (`+=`, ...) are rejected;
  `operator`/`precedencegroup` declarations themselves do not produce runtime
  code.
- `#if` conditions are evaluated at compile time. Built-in conditions are
  `SWIM`, `true`/`false`, `swift(...)`, `compiler(...)`, `os(...)`,
  `arch(...)`, `canImport(...)`; add project flags with `-D NAME`.
  `#available` is treated as satisfied (Swim does not model OS availability).
- ARC memory management: reference cycles are not collected automatically and
  `weak`/`unowned` are rejected; break cycles manually.
- **No package manager**: modules are source files resolved from directories /
  `SWIM_PATH`; dependencies are never downloaded automatically.
- **No direct Nim ecosystem imports**: `.sw` files may not contain Nim code
  (see the extension paths above).
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
