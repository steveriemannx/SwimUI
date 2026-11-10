# The Swim language reference

This document describes the complete syntax and semantics of Swim.
Swim = **Swift syntax** compiled **directly to C**. Files use the `.sw`
extension and each file is a complete program. Programs are built with the
system C compiler and linked with the atomic-ARC C runtime.

## Table of contents

1. [Lexical structure](#1-lexical-structure)
2. [Types](#2-types)
3. [Declarations](#3-declarations)
4. [Statements](#4-statements)
5. [Expressions and operators](#5-expressions-and-operators)
6. [Optionals](#6-optionals)
7. [Closures](#7-closures)
8. [Pattern matching](#8-pattern-matching)
9. [Error handling](#9-error-handling)
10. [Protocols and generics](#10-protocols-and-generics)
11. [Extensions](#11-extensions)
12. [Runtime standard library](#12-runtime-standard-library)
13. [Top-level code and @main](#13-top-level-code-and-main)
14. [Memory management and ARC](#14-memory-management-and-arc)
15. [License and independent implementation](#15-license-and-independent-implementation)
16. [Unsupported features](#16-unsupported-features)

---

## 1. Lexical structure

### Comments

```swift
// line comment
/* block comment; /* nesting works */ like this */
```

### Identifiers

Unicode letters, digits and underscores are supported. Reserved words can be
escaped with backticks:

```swift
let `class` = 1   // legal
```

### Numeric literals

```swift
42
1_000_000
0xFF
0b1010
0o755
3.14
1.5e-3
```

### Strings

```swift
let single = "hello"
let escaped = "tab\tnewline\nquote\"done"
let unicode = "\u{1F600}"
let interpolated = "sum = \(1 + 2), name = \(person.name)"
```

Multiline strings use `"""` and are dedented relative to the closing delimiter:

```swift
let poem = """
    first line
    second line
    """
```

Expressions inside interpolation `\(...)` can be arbitrary expressions
(including nested strings). They are printed using Swift's `description`
semantics (arrays as `[1, 2]`, optionals as `Optional(1)` / `nil`).

### Compiler literals

```swift
print(#file)      // "main.sw"
print(#line)      // the current source line (Int)
print(#column)    // the current source column (Int)
print(#function)  // "main" at top level, otherwise "name()"
```

### Conditional compilation

```swift
#if DEBUG
print("debug build")
#elseif os(Linux)
print("linux release")
#else
print("release build")
#endif

#if swift(>=5.0) && canImport(Foundation)
print("modern toolchain")
#endif

#if false
#error "this branch never compiles"
#endif

let modern = #available(iOS 13, macOS 10.15, *)
if #available(iOS 13, *) { ... }
```

- Conditions are evaluated by the compiler; inactive branches are removed
  while line numbers are preserved for diagnostics.
- Built-in conditions: `true`/`false`, `SWIM` (always defined),
  `swift(>=x.y)` / `compiler(>=x.y)`, `os(macOS)` / `os(Linux)` /
  `os(Windows)`, `arch(arm64)` / `arch(x86_64)`, `canImport(Foundation)`.
- Custom flags are defined with `Swim run -D NAME file.sw` (also `-DNAME`).
- `#error "message"` fails compilation in an active branch; `#warning` is
  accepted and ignored. `#available` is treated as satisfied (no OS
  availability modelling).

### Operator tokens

Swift's operator character set is used: `/ - + ! * % < > & | ^ ~ ?`, plus
`...` and `..<`. Assignment operators, `??`, `&&`, `||` and the like are
built in; **custom operators** can be declared with `operator` /
`precedencegroup` declarations (see "Custom operators" below), including
Unicode math/symbol operators such as `≤`, `×` and `√`.

## 2. Types

### Primitive types

| Swim | runtime representation | notes |
| --- | --- | --- |
| `Int`, `Int8`, `Int16`, `Int32`, `Int64` | boxed integer (`SwimInt`) | signed |
| `UInt`, `UInt8`, … | boxed integer | unsigned |
| `Double`, `Float` | boxed `double` | |
| `Bool` | boxed `bool` | `true` / `false` |
| `String` | refcounted byte string | UTF-8 |
| `Character` | boxed byte (`char`) | single character |
| `Void` | — | no return value |

### Composite types

```swift
let a: [Int] = [1, 2, 3]              // refcounted array
let b: [String: Int] = ["a": 1]       // insertion-ordered hash table
let c: Set<Int> = [1, 2]              // refcounted hash set
let d: (Int, String) = (1, "a")       // refcounted tuple
let e: (x: Int, y: Int) = (x: 1, y: 2)
let f: Int? = nil                     // Option[int]
let g: (Int) -> String = { "\($0)" }  // closure type
```

### Type conversions

```swift
Int(3.9)          // 3 (truncates)
Double(2)         // 2.0
String(42)        // "42"
Int("42")         // Int? (can fail)
Double("3.5")     // Double?
```

### Type checks and casts

```swift
if let dog = animal as? Dog { ... }   // downcast, returns Optional
let dog = animal as! Dog              // forced downcast
let animal: Animal = dog as Animal    // upcast
if animal is Cat { ... }              // type check
```

## 3. Declarations

### Constants and variables

```swift
let answer = 42          // constant (cannot be reassigned; struct
                         // properties of a let value cannot be mutated)
var count = 0            // variable
var name: String = "Swim"
var items: [Int] = []    // empty arrays need a type annotation
```

Tuple destructuring is also supported:

```swift
let (minValue, maxValue) = minMax([1, 5, 3])
```

### Functions

```swift
// Argument labels: a leading _ removes the label at call sites; otherwise the
// parameter name is the label.
func add(_ a: Int, _ b: Int) -> Int { return a + b }
func greet(name: String, from city: String = "the world") -> String {
    return "Hi \(name) from \(city)"
}
add(1, 2)
greet(name: "Ada")                 // default parameter used
greet(name: "Ada", from: "Paris")  // labels are matched, not positional

// inout parameters
func bump(_ value: inout Int) { value += 1 }
var x = 1
bump(&x)

// Single-expression functions may omit `return`
func square(_ x: Int) -> Int { x * x }

// Overloads are resolved by parameter types
func show(_ x: Int) -> String { "int" }
func show(_ x: String) -> String { "string" }

// Generic functions and constraints
func largest<T: Comparable>(_ values: [T]) -> T? { ... }
func first<T, U>(_ a: T, _ b: U) -> T { a }

// ``where`` clauses add protocol constraints to generic parameters
func sortedValues<T>(_ values: [T]) -> [T] where T: Comparable {
    values.sorted()
}

// throws declarations (errors propagate; `try` is optional at call sites)
func risky() throws -> Int { ... }

// Variadic parameters collect the trailing arguments into an array
func sum(_ values: Int...) -> Int { ... }
sum()
sum(1, 2, 3)

// Parameters after a variadic parameter must be labeled
func describe(prefix: String = "values", values: Int...) -> String { ... }
describe(values: 4, 5)
describe(prefix: "sum", values: 6)
```

Modifiers such as `func`, `mutating func`, `static func`, `class func`,
`override`, `final` and `@discardableResult` are accepted; modifiers without
semantic impact are ignored.

### Custom operators

```swift
// Existing precedence groups: AssignmentPrecedence, TernaryPrecedence,
// DefaultPrecedence, LogicalDisjunction/ConjunctionPrecedence,
// ComparisonPrecedence, CastingPrecedence, RangeFormationPrecedence,
// AdditionPrecedence, MultiplicationPrecedence, BitwiseShiftPrecedence.
infix operator **: MultiplicationPrecedence
func ** (base: Int, power: Int) -> Int { ... }

precedencegroup ForwardApplication {
    associativity: left          // left | right | none
    higherThan: AdditionPrecedence
    // or: lowerThan: MultiplicationPrecedence
}
infix operator |>: ForwardApplication
func |> (value: Int, transform: (Int) -> Int) -> Int { transform(value) }

prefix operator %%
prefix func %% (value: Int) -> Int { value * 2 }

postfix operator ++
postfix func ++ (value: Int) -> Int { value + 1 }

// operator functions may be static members of a type or extension
struct Vec {
    var x: Int
    var y: Int
    static func + (lhs: Vec, rhs: Vec) -> Vec { ... }
}
```

- `precedencegroup` properties: `associativity`, `higherThan`, `lowerThan`,
  `assignment`.
- Operator functions take one (prefix/postfix) or two (infix) parameters and
  are resolved by argument type, like ordinary overloads.
- Custom *assignment* operators (`+=`, ...) are not supported.

### Nested types

```swift
struct Outer {
    typealias ID = Int
    struct Inner { var id: ID }
    enum State { case idle, running(progress: Int) }
    var inner: Inner
    var state: State
}

let inner = Outer.Inner(id: 1)
let state: Outer.State = .running(progress: 50)
```

Nested types are declared inside `struct`/`class`/`enum`/`protocol` bodies,
referenced as `Outer.Inner`, and can be extended with
`extension Outer.Inner { ... }`. Inside the enclosing type the short name
(`Inner`, `State`) works; a nested type can also refer back to its enclosing
class. The C backend emits type descriptors with forward declarations, so type
declaration order does not matter.

### Structs

```swift
struct Point: Equatable {
    var x: Int
    let id: Int
    var y: Int = 0                        // default value

    init(x: Int, id: Int) {               // custom initializer
        self.x = x
        self.id = id
    }

    func lengthSquared() -> Int { x * x + y * y }   // non-mutating self

    mutating func move(dx: Int, dy: Int) {           // mutating self
        x += dx
        y += dy
    }

    var description: String { "Point(\(x), \(y))" }  // computed property

    var doubled: Int {
        get { x * 2 }
        set { x = newValue / 2 }                     // writable computed property
    }

    static func origin() -> Point { Point(x: 0, id: 0) }
    static let zero = Point(x: 0, id: 0)
}
```

Property observers run on every assignment outside initialization:

```swift
struct Counter {
    var value: Int = 0 {
        willSet { print("will become \(newValue)") }
        didSet { print("was \(oldValue)") }
    }
    var labelled: Int {
        didSet(old) { print("old labelled", old) }   // custom parameter name
    }
}
```

- `willSet` runs before the new value is stored and `didSet` after; both can
  use `oldValue`/`newValue` or the custom names from `willSet(name)` /
  `didSet(name)`.
- Observers run for assignment, compound assignment and mutating method calls
  on the property, but not while an initializer writes the property.
- The stored value lives in a hidden backing field (visible in `Swim emit`).

Subscript declarations define `value[index]` access:

```swift
struct Matrix {
    var cells: [[Int]]
    subscript(row: Int, column: Int) -> Int {
        get { cells[row][column] }
        set { cells[row][column] = newValue }
    }
}

var matrix = Matrix(cells: [[1, 2], [3, 4]])
print(matrix[0, 1])
matrix[1, 0] = 30
```

- A getter-only subscript is read-only; assignment through it is a compile
  error. Subscripts also work in `extension`s and on `class`es/enums.
- `static subscript` declares type-level indexing; overloads may differ by
  argument type:

```swift
struct Settings {
    static var values: [Int] = [1, 2, 3]
    static subscript(index: Int) -> Int {
        get { values[index] }
        set { values[index] = newValue }
    }
}
print(Settings[1])
Settings[1] = 20
```

Static stored properties and static computed properties are supported:

```swift
struct Config {
    static var stored: Int = 1
    static var doubled: Int {
        get { stored * 2 }
        set { stored = newValue / 2 }
    }
    static var summary: String { "stored=\(stored)" }
}
print(Config.doubled)
Config.doubled = 10
```

- `struct` is a **value type**: assignment and argument passing copy it.
- Without an `init`, a memberwise initializer is generated (defaults allowed).
- Conforming to `Equatable` synthesizes `==`; conforming to `Hashable`
  synthesizes `hash` (usable as dictionary keys).
- Conforming to `CustomStringConvertible`, or providing `description`, is used
  for printing and interpolation.

### Classes

```swift
class Animal {
    var name: String
    init(name: String) { self.name = name }
    func speak() -> String { "..." }
    deinit { print("bye", name) }   // runs when the last reference goes away
}

class Dog: Animal {
    var breed: String
    init(name: String, breed: String) {
        self.breed = breed
        super.init(name: name)
    }
    override func speak() -> String { "Woof" }
}
```

- `class` is a **reference type**: assigning shares the same instance.
- Single inheritance; `override` methods dispatch dynamically through the
  runtime
  `method`.
- `super.init(...)` and `super.method(...)` work.
- `as?` / `as!` downcast; `is` tests the runtime type.
- `let` properties of a class can only be assigned in its initializers.

Initializers can be failable and can delegate:

```swift
struct User {
    let name: String
    init?(name: String) {
        guard !name.isEmpty else { return nil }
        self.name = name
    }
}

class View {
    var width: Int
    init(width: Int) { self.width = width }
    convenience init(square side: Int) { self.init(width: side) }
}
```

- `init?` returns `T?`; `return nil` fails, falling off the end succeeds.
  `init!` is an implicitly unwrapped failable initializer.
- `self.init(...)` delegates to another initializer (used by `convenience
  init`); `super.init(...)` calls the superclass initializer. Delegation
  propagates failure in failable initializers.

### Enums

```swift
// Plain enum (optionally with raw values)
enum Direction: Int {
    case north = 1
    case south
    case east
    case west
}
print(Direction.north.rawValue)   // 1
if let d = Direction(rawValue: 2) { ... }

// String raw values
enum Suit: String {
    case hearts = "h"
    case spades = "s"
}
print(Suit.hearts.rawValue)       // "h"
if let s = Suit(rawValue: "s") { ... }

// Associated values
enum Shape {
    case circle(radius: Double)
    case rectangle(width: Double, height: Double)
    case point
}
let shape = Shape.circle(radius: 2.0)
print(shape)                       // circle(radius: 2.0)

// Recursive enums (automatically represented with references)
enum Tree {
    case leaf(Int)
    case node(Tree, Tree)
}

// Enums can have methods, computed properties and initializers
enum Planet: Int {
    case earth = 3
    func gravity() -> Double {
        switch self {
        case .earth: return 9.8
        default: return 0
        }
    }
}

// CaseIterable
enum Compass: CaseIterable {
    case north, south
}
for c in Compass.allCases { print(c) }
```

Enum values print as the case name (with payloads as
`case(label: value)`). With `Equatable`, `==` is synthesized. `rawValue`,
`Enum(rawValue:)` (returns an Optional) and `allCases` (with `CaseIterable`)
are supported.

### Protocols

```swift
protocol Shape {
    func area() -> Double
    var name: String { get }
    subscript(index: Int) -> Int { get }   // subscript requirements are allowed
}

struct Circle: Shape {
    var radius: Double
    var name: String { "circle" }
    func area() -> Double { 3.14159 * radius * radius }
}

func describe<T: Shape>(_ shape: T) -> String {
    return "\(shape.name): \(shape.area())"
}
```

Protocols are checked structurally at compile time and constrain generic
parameters. A protocol name can also be used directly as a function parameter
type (statically dispatched).

### Extensions

```swift
extension Int {
    func squared() -> Int { self * self }
}

extension String {
    func shouted() -> String { self.uppercased() + "!" }
}

extension Array {
    func second() -> Element? { count >= 2 ? self[1] : nil }
}

extension Stack {
    func peek() -> Element? { ... }
}

// Provide default implementations for a protocol
extension Shape {
    func describe() -> String { "\(name): \(area())" }
}
```

Inside extensions, `self` is directly accessible; `mutating func` can mutate
value types. In `Array` extensions `Element` refers to the element type
(`Key`/`Value` for `Dictionary`).

### Type aliases

```swift
typealias Callback = (Int) -> Void
typealias Pair = (Int, Int)
```

### Imports

Swim imports come in three layers (see "Modules and library imports" in the
README):

**1) Built-in modules** (provided by `swimrt`, treated as no-ops):

```swift
import Foundation
import Swift
import Glibc        // or Darwin / Dispatch / ObjectiveC
import Math         // or Strings / Collections / Random / Time
```

**2) Swim modules** (`.sw` source files; the recommended way):

```swift
import MathX          // resolves MathX.sw or MathX/main.sw
import lib.Utils      // resolves lib/Utils.sw or lib/Utils/main.sw
import Greeter
```

- Search order: importing file's directory → entry file's directory → current
  working directory → `SWIM_PATH` (colon-separated).
- A local `.sw` file takes precedence over a built-in module name.
- All modules are merged with the entry file into one program; imported modules'
  top-level statements run dependencies-first, exactly once, then the entry
  file runs.
- Declarations share one flat namespace: duplicate types/global
  variables/same-signature functions across files are compile errors;
  same-name functions with different signatures are overloads.
- Import cycles compile fine; they expand deterministically by first-load
  order.
- Only the entry file may declare `@main`.
- `Swim deps main.sw` shows the resolved import graph and execution order.

**3) Native modules (retired)**: the Nim backend used to wrap Nim libraries
as *native modules* (`import Nimx`). The direct C backend does not support
that mechanism; `import Nimx` is rejected. Extend the C runtime
(`runtime/swimrt*.c`) and the builtin dispatch instead.

## 4. Statements

### if / else

```swift
if value > 0 {
    ...
} else if value < 0 {
    ...
} else {
    ...
}

// Conditional bindings; multiple conditions are separated by commas
if let x = optionalX, let y = optionalY, x > y {
    ...
}

// Swift 5.7 shorthand (also works in guard/while)
if let optionalX {
    print(optionalX)
}
```

### guard

```swift
guard let value = Int(text), value > 0 else {
    return
}
```

A `guard` else branch must end with `return`, `break`, `continue`, `throw`,
`fatalError(...)` or `preconditionFailure(...)`.

### while / repeat-while

```swift
while condition { ... }
while let top = stack.last {
    stack.removeLast()
}

repeat {
    ...
} while condition
```

### for-in

```swift
for i in 0..<10 { }                     // half-open range
for i in 1...10 { }                     // closed range
for (index, value) in array.enumerated() { }
for (key, value) in dictionary { }
for key in dictionary.keys { }
for value in dictionary.values { }
for character in "abc" { }
for n in stride(from: 0, to: 100, by: 10) { }
for n in stride(from: 100, through: 0, by: -10) { }
for n in 1...10 where n % 2 == 0 { }    // where filter
for n in (0..<10).reversed() { }

// Pattern loops
for case let value? in optionalValues { }        // unwrap every non-nil value
for case .circle(let radius) in shapes { }       // match enum payloads
for case let value? in values where value > 0 { }
```

### switch

```swift
switch value {
case 0:
    ...
case 1...9:
    ...
case let x where x % 2 == 0:
    ...
case .circle(let radius):
    ...
case .rectangle(let width, let height) where width > height:
    ...
case "literal":
    ...
default:
    ...
}
```

- Integers, strings, enums and booleans can all be matched.
- Patterns: literals, `...`/`..<` ranges, `_`, `let x`, `let x where cond`,
  enum cases (including associated-value bindings).
- `fallthrough` continues execution in the next case body without testing its
  pattern; it is supported as the last statement of a case (it must not be the
  last case of the switch).
- Each branch does **not** need `break` (there is no implicit fallthrough).
- `break` inside a `switch` exits the switch (as in Swift).
- `case is SomeClass` matches class instances by runtime type.

### Labeled statements

```swift
outer: for i in 0..<10 {
    for j in 0..<10 {
        if j == threshold { continue outer }
        if i > limit { break outer }
    }
}
label: switch value { ... }
```

### defer

```swift
func work() {
    defer { print("cleanup") }
    print("doing")
}
```

Deferred blocks run in **last-in, first-out** order on scope exit.

### do / catch

```swift
do {
    try risky()
} catch ValidationError.empty {
    ...
} catch ValidationError.tooShort(let minimum) {
    ...
} catch {
    ...
}
```

A `do { ... }` without `catch` is just a scope block (`block:`).
Both `catch let e as SomeError` and `catch SomeError` are supported.
`where` clauses work too (`catch SomeError where cond { ... }`; if the
condition is false the error is rethrown).

## 5. Expressions and operators

### Precedence (highest to lowest)

| precedence | operators |
| --- | --- |
| prefix | `!` (logical not), `-`, `+`, `~`, `&` (inout argument marker) |
| multiplication | `*` `/` `%` `&` `&*` |
| addition | `+` `-` `\|` `^` `&+` `&-` |
| shift | `<<` `>>` |
| range | `...` `..<` |
| casting | `is` `as` `as?` `as!` |
| nil-coalescing | `??` (right associative) |
| comparison | `==` `!=` `<` `<=` `>` `>=` `===` `!==` |
| logical | `&&`, then `\|\|` |
| ternary | `cond ? a : b` (right associative) |
| assignment | `=` `+=` `-=` `*=` `/=` `%=` `&=` `\|=` `^=` `<<=` `>>=` (right associative) |

### Integers and floats

- Integer `/` truncates toward zero (C semantics); `%` is the C remainder.
- Float `/` is normal division; literal integers are promoted when mixed with
  floats.
- Integer overflow follows C semantics (no traps).

### Ternary and nil-coalescing

```swift
let label = count > 0 ? "some" : "none"
let value = optionalInt ?? 0
let chained = a ?? b ?? 0
```

### Custom operators

User-declared operators use the precedence from their `precedencegroup`;
prefix operators bind tighter than any infix operator and postfix operators
bind tighter than infix operators. See "Custom operators" in the declarations
section.

### Identity comparison

```swift
if a === b { }     // reference identity
```

### Optionals in ternary expressions

```swift
let x: Int? = condition ? 5 : nil
```

## 6. Optionals

```swift
let maybe: Int? = 5
let none: Int? = nil

maybe!                      // force unwrap (a runtime error if nil)
maybe ?? 0                  // default value
if let v = maybe { }        // if-let unwrapping
if let v = maybe, v > 0 { }
guard let v = maybe else { return }

var x: Int? = nil
x = 5                       // automatically wraps as .some(5)
x = nil

// Optional chaining: arbitrary depth, short-circuits on nil
print(person?.address?.city ?? "unknown")
print(object?.method(arg) ?? default)
```

- The type `T?` compiles to `Option[T]`.
- Passing an optional where a non-optional is expected is a clear compile
  error (use `!` or unwrap it).
- Nested optionals such as `Int??` are supported (multi-level `some` wrapping).
- Optional values can be used in `if` / `guard` / `while` / `switch`
  (`.some` / `.none`).

## 7. Closures

```swift
// Explicit parameters and return type
let add = { (a: Int, b: Int) -> Int in a + b }

// Single-expression closures may omit `return`
let square = { (x: Int) -> Int in x * x }

// Shorthand parameters
let doubled = [1, 2, 3].map { $0 * 2 }
let sum = [1, 2, 3].reduce(0) { $0 + $1 }

// Zero-parameter closures
let constant = { () -> String in "value" }

// Trailing closures
array.sorted { $0 < $1 }
array.filter { $0 > 0 }
array.forEach { print($0) }

// Capturing outer variables
var total = 0
let addToTotal = { (x: Int) in total += x }

// Returning closures
func multiplier(_ factor: Int) -> (Int) -> Int {
    return { (x: Int) -> Int in x * factor }
}
```

Closures work with `map`, `filter`, `reduce`, `forEach`, `allSatisfy`,
`contains(where:)`, `first(where:)`, `last(where:)`, `firstIndex(where:)`,
`sorted(by:)`, `sort(by:)` and more. Single-expression closures generate
efficient template calls; multi-statement closures generate procs.

## 8. Pattern matching

`switch`, `if case` and `guard case` all support patterns:

```swift
if case .circle(let radius) = shape {
    print(radius)
}

guard case .ok = status else { return }

switch optionalValue {
case .some(let v):
    ...
case .none:
    ...
}

for value in 0...10 {
    switch value {
    case 0: ...
    case let x where x % 2 == 0: ...
    default: ...
    }
}
```

## 9. Error handling

```swift
enum NetworkError: Error {
    case timeout
    case badResponse(code: Int)
}

func fetch(_ url: String) throws -> Data {
    if url.isEmpty { throw NetworkError.timeout }
    ...
}

do {
    let data = try fetch(url)
    print(data)
} catch NetworkError.timeout {
    print("timeout")
} catch NetworkError.badResponse(let code) {
    print("bad response \(code)")
} catch {
    print("other error")
}

// try? -> Optional (the error is swallowed)
if let data = try? fetch(url) { ... }

// try! -> a runtime crash if it throws
let data = try! fetch(url)
```

- `enum E: Error` and `struct E: Error` values are thrown through the
  runtime's exception frames and matched by `catch` patterns.
- Errors propagate across functions and are not caught by unrelated `catch`
  clauses.
- `defer` also runs when an error propagates.

## 10. Protocols and generics

```swift
protocol Container {
    func count() -> Int
    var isEmpty: Bool { get }
}

// Generic function with a protocol constraint
func report<T: Container>(_ c: T) -> String {
    return "count=\(c.count()), empty=\(c.isEmpty)"
}

// Multiple constraints and built-in protocols
func maximum<T: Comparable>(_ a: T, _ b: T) -> T { a > b ? a : b }

// Generic struct
struct Box<T> {
    var value: T
    func map<U>(_ transform: (T) -> U) -> Box<U> {
        return Box<U>(value: transform(value))
    }
}
let box = Box<Int>(value: 21)
print(box.map { $0 * 2 }.value)

// Generic enum
enum Result<Value> {
    case success(Value)
    case failure(String)
}
let result = Result<Int>.success(42)
```

- Generic types/functions are type-erased; dispatch happens at run time.
- `where T: Protocol` clauses (on functions, types and extensions) are folded
  into the generic parameter's protocol constraints. Same-type constraints
  (`where T == Int`) are parsed but not enforced.
- Protocols support property and method requirements; protocol extensions can
  provide default implementations.
- Built-in concepts: `Equatable`, `Comparable`, `Hashable`,
  `CustomStringConvertible`, `CaseIterable`, `Numeric`, `SignedNumeric`, etc.
- Generic instantiation uses `Type<Arg>(...)` and `Type<Arg>.case(...)` syntax.

## 11. Extensions

```swift
extension Int {
    func squared() -> Int { self * self }
}
extension String {
    var initials: String { ... }
}
extension Array {
    func secondOrNil() -> Element? { count >= 2 ? self[1] : nil }
}
extension Stack {
    static func empty() -> Stack<Element> { Stack<Element>() }
}
```

- Extend user types and `Int`/`Double`/`Bool`/`Character`/`String`/`Array`/
  `Dictionary`.
- Instance methods, `mutating` methods, computed properties and static methods
  are supported.
- Stored properties cannot be added in extensions (compile error).
- Methods from protocol extensions apply to all conforming types.

## 12. Runtime standard library

Every program links `runtime/swimrt*.c`, which provides:

### Printing

```swift
print("value:", 42)                       // space-separated, trailing newline
print("no newline", terminator: "")
print("a", "b", separator: "-")
debugPrint(value)                          // same as print
fatalError("message")                      // abort with an error
assert(condition, "message")
precondition(condition)
readLine()                                 // -> String?
exit(1)
```

### Optionals

`!`, `??`, `if let`, `guard let`, `?.`, `.map { }`, `.flatMap { }`.

### String / Character

See the runtime API list in the README.

### Array / Dictionary / Set

See the runtime API list in the README. Highlights added beyond the basics:

```swift
print(numbers[1..<3])             // slicing (arrays and strings)
for (a, b) in zip(xs, ys) { }     // zip
print(values.compactMap { Int($0) })
print([[1], [2, 3]].flatMap { $0 })
print(set.union(other).sorted())
print(set.isSubset(of: other))
print(scores.mapValues { $0 * 2 })
print(values.min(by: { $0 < $1 })!)
```

### Math

`abs`, `min`, `max`, `pow`, `sqrt`, `floor`, `ceil`, `round`, `trunc`,
`sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log2`, `log10`,
`exp`; constants `Double.pi`, `Double.infinity`, `Double.nan`, `Int.max`,
`Int.min`; `Int.random(in: 1...10)`.

### Ranges / stride

`a..<b`, `a...b`, `stride(from:to:by:)`, `stride(from:through:by:)`,
`range.contains(x)`.

## 13. Top-level code and @main

Like Swift's `main.swift`, a `.sw` file can contain top-level statements that
run in source order (global variable initialization also runs there, in order):

```swift
let greeting = "hello"
print(greeting)
```

Alternatively, use `@main`:

```swift
@main
struct App {
    static func main() {
        print("main ran")
    }
}
```

## 14. Memory management and ARC

Swim uses **ARC (Automatic Reference Counting)**:

- Heap objects carry an `_Atomic int64_t` reference count updated with C11
  atomics (Swift-style atomic ARC); no tracing GC or cycle collector exists.
- `struct`, `enum`, `String`, arrays, dictionaries, sets, tuples and optionals
  are value types: they are copied on store.
- `class` is a reference type; ARC releases instances immediately when the
  reference count reaches zero.
- As with Swift ARC, **reference cycles are not collected automatically**. If
  two classes hold strong references to each other, break the cycle manually
  (set one side to `nil`).
- `weak var` (optional class property) and `unowned var` (class property)
  break reference cycles: weak references are zeroed when the target is
  deallocated, unowned references trap if used after the target is released.
- Classes can declare `deinit`, which runs when the last strong reference is
  released; derived deinitializers run before superclass ones and weak
  references are zeroed first. Stored members are released after `deinit`.
- Recursive enums are represented with references, so they are also managed by
  ARC; large recursive values can still form cycles.
- References captured by closures are ARC-managed.

## 15. License and independent implementation

Swim is released under the **MIT License** (see `LICENSE` in the repository
root).

This is an independent implementation: **no code from the official Swift
repository (swiftlang/swift) or the Swift standard library is used**. The
compiler (Python), C runtime, tests and documentation are all original.
The syntax design follows Swift's language conventions (keywords, precedence,
optional semantics, etc.), but no files were copied from the Swift repository.

## 16. Unsupported features

The following features are not implemented yet (most produce a clear error;
a few are only ignored):

- `associatedtype`, generic protocols, protocol composition types, `any P` as a
  variable type.
- `async`/`await` (keywords are ignored; code is compiled synchronously).
- Custom assignment operators.
- Property wrappers, `lazy`, attribute semantics beyond `@escaping`.
- `weak`/`unowned` on locals, globals, static properties or with observers;
  weak properties must be optional class types, and `deinit` is only allowed
  in classes.
- `willSet`/`didSet` on `static` properties and in extensions (stored
  properties cannot be added by extensions).
- Foundation / Cocoa / SwiftUI library APIs (`import Foundation` is only
  accepted).
- Multi-file modules are supported, but there is no package manager and
  dependencies are not downloaded.
- Direct imports of foreign libraries (only Swift syntax is allowed in
  `.sw` files; see the extension paths above).
- `Any` type erasure, C interop, macros.
- Heterogeneous protocol arrays (`[any Shape]`) and dynamic dispatch through
  protocol existentials.

Implemented in the meantime (previously listed here): `subscript`
declarations, `fallthrough`, property observers `willSet`/`didSet`, failable
initializers `init?`/`init!`, variadic parameters, `for case` pattern loops,
initializer delegation via `self.init`, custom operators, nested types and
`#if`/`#available` conditional compilation.

If you need these capabilities, extend the Swim compiler/runtime instead of
mixing in another language — Swim source files accept Swift syntax only.
