// Generic where clauses become extra generic constraints (protocol
// constraints are enforced through Nim concepts).
func sortedValues<T>(_ values: [T]) -> [T] where T: Comparable {
    return values.sorted()
}
print(sortedValues([3, 1, 2]))
print(sortedValues(["b", "a", "c"]))

func maximum<T: Comparable>(_ a: T, _ b: T) -> T where T: Hashable {
    return a > b ? a : b
}
print(maximum(3, 5))
print(maximum("pear", "apple"))

struct Holder<T> where T: Comparable {
    var value: T
    func isSmaller(than other: T) -> Bool { value < other }
}
print(Holder(value: 1).isSmaller(than: 2))
print(Holder(value: "z").isSmaller(than: "a"))

extension Holder where T: Comparable {
    func clamped(to limit: T) -> T {
        return value < limit ? value : limit
    }
}
print(Holder(value: 9).clamped(to: 5))
