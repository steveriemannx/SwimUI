// Assorted features: typealias, nested tuples, defer, access modifiers,
// overloading, string interpolation, optional maps, recursion.
typealias Pair = (Int, Int)
typealias IntTransform = (Int) -> Int

func applyTwice(_ transform: IntTransform, to value: Int) -> Int {
    return transform(transform(value))
}
print(applyTwice({ $0 + 1 }, to: 5))

let pair: Pair = (3, 4)
print(pair.0, pair.1)

func divide(_ a: Int, _ b: Int) -> Pair {
    return (a / b, a % b)
}
let (quotient, remainder) = divide(17, 5)
print(quotient, remainder)

public struct Widget {
    public var name: String
    private var hidden: Int = 7
    public init(name: String) {
        self.name = name
    }
    public func secret() -> Int { hidden }
    fileprivate func secretDouble() -> Int { hidden * 2 }
}
print(Widget(name: "w").name, Widget(name: "w").secret())

// overloads by parameter types
func show(_ value: Int) -> String { return "int \(value)" }
func show(_ value: String) -> String { return "string \(value)" }
func show(_ value: Double) -> String { return "double \(value)" }
print(show(1), show("x"), show(1.5))

// recursion with closures
var factorial: (Int) -> Int = { $0 }
factorial = { (n: Int) -> Int in
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}
print(factorial(5))

// defer with multiple scopes
func scopes() {
    defer { print("outer defer") }
    do {
        defer { print("inner defer") }
        print("inner body")
    }
    print("outer body")
}
scopes()

// optional map and flatMap
let number: Int? = 5
let doubled = number.map { $0 * 2 }
print(doubled!)
let nested = number.flatMap { value in Optional(value + 1) }
print(nested ?? 0)

// ternary chains and nil
let flag = number != nil ? "has" : "none"
print(flag)

// tuples with labels
func stats(_ values: [Int]) -> (min: Int, max: Int, sum: Int) {
    var lo = values[0]
    var hi = values[0]
    var total = 0
    for value in values {
        if value < lo { lo = value }
        if value > hi { hi = value }
        total += value
    }
    return (min: lo, max: hi, sum: total)
}
let result = stats([4, 1, 9])
print(result.min, result.max, result.sum)
