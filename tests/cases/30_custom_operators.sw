// Custom operators: operator / precedencegroup declarations, infix,
// prefix and postfix functions, user types and extensions.

infix operator **: MultiplicationPrecedence
func ** (base: Int, power: Int) -> Int {
    var result = 1
    var index = 0
    while index < power {
        result *= base
        index += 1
    }
    return result
}
print(2 ** 10)
print(2 * 3 ** 2)

precedencegroup PowerPrecedence {
    associativity: right
    higherThan: MultiplicationPrecedence
}
infix operator ^^: PowerPrecedence
func ^^ (base: Double, power: Double) -> Double {
    return pow(base, power)
}
print(2.0 ^^ 3.0 ^^ 2.0)

precedencegroup ForwardApplication {
    associativity: left
    lowerThan: AdditionPrecedence
}
infix operator |>: ForwardApplication
func |> (value: Int, transform: (Int) -> Int) -> Int {
    return transform(value)
}
print(5 |> { $0 * 3 })
print(1 + 2 |> { $0 * 10 })

prefix operator %%
prefix func %% (value: Int) -> Int { value * 2 }
print(%%5)
print(%%(3 + 1))

postfix operator ++
postfix func ++ (value: Int) -> Int { value + 1 }
print(5++)
var count = 1
count = count++
print(count)

struct Vec {
    var x: Int
    var y: Int

    func describe() -> String { "(\(x), \(y))" }

    static func + (lhs: Vec, rhs: Vec) -> Vec {
        return Vec(x: lhs.x + rhs.x, y: lhs.y + rhs.y)
    }

    static func * (lhs: Vec, factor: Int) -> Vec {
        return Vec(x: lhs.x * factor, y: lhs.y * factor)
    }

    static func == (lhs: Vec, rhs: Vec) -> Bool {
        return lhs.x == rhs.x && lhs.y == rhs.y
    }
}
let sum = Vec(x: 1, y: 2) + Vec(x: 3, y: 4)
print(sum.describe())
print((Vec(x: 1, y: 1) * 3).describe())
print(Vec(x: 1, y: 2) == Vec(x: 1, y: 2))
print(Vec(x: 1, y: 2) == Vec(x: 3, y: 4))

// operator declared at file scope for an extension type
extension String {
    static func * (lhs: String, count: Int) -> String {
        return String(repeating: lhs, count: count)
    }
}
print("ab" * 3)

// custom operator with generics
infix operator <=> : ComparisonPrecedence
func <=> <T: Comparable>(lhs: T, rhs: T) -> Int {
    if lhs < rhs { return -1 }
    if lhs > rhs { return 1 }
    return 0
}
print(1 <=> 2, 3 <=> 2, 2 <=> 2)
