// Argument labels, default parameters, inout, closures
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
var x = 1
var y = 2
swapValues(&x, &y)
print(x, y)

// Closures with explicit parameters
let double = { (value: Int) -> Int in value * 2 }
print(double(21))

// Shorthand parameter $0
let squared = [1, 2, 3, 4].map { $0 * $0 }
print(squared)

// Higher-order functions
let numbers = [1, 2, 3, 4, 5, 6]
print(numbers.filter { $0 % 2 == 0 })
print(numbers.reduce(0) { $0 + $1 })
print(numbers.allSatisfy { $0 > 0 })

// Returning a closure that captures state
func makeCounter() -> () -> Int {
    var current = 0
    return {
        current += 1
        return current
    }
}
let counter = makeCounter()
print(counter(), counter(), counter())

// Functions as parameters
func applyTwice(_ f: (Int) -> Int, to value: Int) -> Int {
    return f(f(value))
}
print(applyTwice({ $0 + 10 }, to: 1))
