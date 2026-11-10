// Functions, argument labels, defaults, overloading, inout and closures.
func add(_ a: Int, _ b: Int) -> Int { return a + b }
func add(_ a: String, _ b: String) -> String { return a + b }
print(add(2, 3), add("a", "b"))

func greet(name: String, from city: String = "the world") -> String {
    return "Hi \(name) from \(city)"
}
print(greet(name: "Ada"))
print(greet(name: "Ada", from: "Paris"))

func swapValues(_ a: inout Int, _ b: inout Int) {
    let temp = a
    a = b
    b = temp
}
var first = 1
var second = 2
swapValues(&first, &second)
print(first, second)

// closures
let double = { (value: Int) -> Int in value * 2 }
print(double(21))
let square: (Int) -> Int = { $0 * $0 }
print(square(9))

func apply(_ transform: (Int) -> Int, to value: Int) -> Int {
    return transform(value)
}
print(apply({ $0 + 100 }, to: 1))
print(apply(double, to: 5))

func makeCounter() -> () -> Int {
    var current = 0
    return {
        current += 1
        return current
    }
}
let counter = makeCounter()
print(counter(), counter(), counter())

// trailing closures / higher order
let values = [1, 2, 3, 4, 5]
print(values.map { $0 * $0 })
print(values.filter { $0 % 2 == 0 })
print(values.reduce(0) { $0 + $1 })
values.forEach { print($0, terminator: "-") }
print("")
print(values.allSatisfy { $0 > 0 }, values.contains(where: { $0 > 4 }))
print(values.first(where: { $0 > 2 })!)

// multiple trailing closures are not used; nested closures are
func compose(_ f: (Int) -> Int, _ g: (Int) -> Int) -> (Int) -> Int {
    return { (x: Int) -> Int in f(g(x)) }
}
print(compose(double, square)(2))
