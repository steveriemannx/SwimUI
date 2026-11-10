// Closures in more detail.
let add = { (a: Int, b: Int) -> Int in a + b }
print(add(1, 2))

let noArgs = { () -> String in "constant" }
print(noArgs())

var total = 0
let accumulate = { (value: Int) in total += value }
accumulate(5)
accumulate(7)
print(total)

// closures returning closures
func multiply(by factor: Int) -> (Int) -> Int {
    return { (value: Int) -> Int in value * factor }
}
let triple = multiply(by: 3)
print(triple(4))

// closures capturing mutable state
func makeAccumulator(start: Int) -> (Int) -> Int {
    var current = start
    return {
        current += $0
        return current
    }
}
let accumulator = makeAccumulator(start: 100)
print(accumulator(1), accumulator(2), accumulator(3))

// sorting with comparators
var names = ["charlie", "alice", "bob"]
print(names.sorted())
print(names.sorted(by: { $0 > $1 }))
print(names.sorted { $0.count < $1.count })
names.sort()
print(names)

// closures stored in arrays
let operations: [(Int) -> Int] = [
    { $0 + 1 },
    { $0 * 2 },
    { $0 - 3 }
]
for operation in operations {
    print(operation(10))
}

// filter/map/reduce chains
let numbers = [1, 2, 3, 4, 5, 6]
let result = numbers
    .filter { $0 % 2 == 0 }
    .map { $0 * $0 }
    .reduce(0) { $0 + $1 }
print(result)

// allSatisfy / contains / first(where:)
print(numbers.allSatisfy { $0 > 0 })
print(numbers.contains { $0 > 5 })
print(numbers.first { $0 % 3 == 0 }!)

// dictionary map / iteration over sorted keys
let ages = ["bob": 20, "alice": 30]
var lines: [String] = []
for name in ages.keys.sorted() {
    lines.append("\(name)=\(ages[name]!)")
}
print(lines.joined(separator: ","))
