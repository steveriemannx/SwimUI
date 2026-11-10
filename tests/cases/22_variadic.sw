// Variadic parameters: free functions, methods, argument labels, default
// parameters before the variadic parameter and empty calls.
func sum(_ values: Int...) -> Int {
    var total = 0
    for value in values {
        total += value
    }
    return total
}
print(sum(), sum(1), sum(1, 2, 3), sum(10, 20))

func describe(prefix: String = "values", values: Int...) -> String {
    return "\(prefix): \(values)"
}
print(describe())
print(describe(values: 4, 5))
print(describe(prefix: "sum", values: 6))
print(describe("count", 7, 8, 9))

func first(_ first: Int, rest: String...) -> String {
    return "\(first): \(rest.joined(separator: ","))"
}
print(first(1))
print(first(1, rest: "a", "b"))

struct Accumulator {
    var total: Int = 0
    mutating func add(_ values: Int...) {
        for value in values {
            total += value
        }
    }
    func joined(with separator: String, parts: String...) -> String {
        return parts.joined(separator: separator)
    }
}
var accumulator = Accumulator()
accumulator.add()
accumulator.add(1, 2, 3)
print(accumulator.total)
print(accumulator.joined(with: "-", parts: "swift", "syntax"))

func multiply(_ factor: Int, values: Int...) -> [Int] {
    return values.map { $0 * factor }
}
print(multiply(2, values: 1, 2, 3))

// a trailing closure binds to the final labeled parameter, past the variadic one
func apply(_ values: Int..., transform: (Int) -> Int) -> [Int] {
    return values.map(transform)
}
print(apply(1, 2, 3) { $0 * 2 })
print(apply(values: 4, 5, transform: { $0 + 1 }))
