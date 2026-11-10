// Protocols (structural concepts), extensions and generics.
protocol Shape {
    func area() -> Double
    var name: String { get }
}

struct Circle: Shape {
    var radius: Double
    var name: String { return "circle" }
    func area() -> Double { return 3.14159 * radius * radius }
}

struct Square: Shape {
    var side: Double
    var name: String { return "square" }
    func area() -> Double { return side * side }
}

func describe<T: Shape>(_ shape: T) -> String {
    return "\(shape.name) -> \(shape.area())"
}
print(describe(Circle(radius: 2.0)))
print(describe(Square(side: 3.0)))

// protocol extension provides a default implementation
protocol Greeter {
    func greeting() -> String
}
extension Greeter {
    func greet() -> String { return greeting() + "!" }
}
struct English: Greeter {
    func greeting() -> String { return "Hello" }
}
struct French: Greeter {
    func greeting() -> String { return "Bonjour" }
}
print(English().greet(), French().greet())

// generic function with multiple constraints
func largest<T: Comparable>(_ values: [T]) -> T? {
    guard let firstValue = values.first else {
        return nil
    }
    var best = firstValue
    for value in values {
        if value > best {
            best = value
        }
    }
    return best
}
print(largest([4, 9, 2])!, largest(["apple", "pear"])!)

// generic struct
struct Stack<T> {
    var items: [T] = []
    mutating func push(_ item: T) {
        items.append(item)
    }
    mutating func pop() -> T? {
        return items.popLast()
    }
    var count: Int { items.count }
    var isEmpty: Bool { items.isEmpty }
}
var stack = Stack<Int>()
stack.push(1)
stack.push(2)
stack.push(3)
print(stack.count, stack.pop()!, stack.count, stack.isEmpty)

// generic class
class Box<T> {
    var value: T
    init(value: T) { self.value = value }
    func get() -> T { return value }
    func map<U>(_ transform: (T) -> U) -> Box<U> {
        return Box<U>(value: transform(value))
    }
}
let box = Box<Int>(value: 21)
print(box.get())
print(box.map { $0 * 2 }.get())

// generic enum with associated values
enum Result<Value> {
    case success(Value)
    case failure(String)
}
func unwrap<Value>(_ result: Result<Value>) -> Value? {
    switch result {
    case .success(let value):
        return value
    case .failure(let message):
        print("failure: \(message)")
        return nil
    }
}
print(unwrap(Result<Int>.success(42))!)
print(unwrap(Result<Int>.failure("nope")) ?? 0)

// typealias
typealias Callback = (Int) -> Void
let printNumber: Callback = { (value: Int) in print("number \(value)") }
printNumber(5)

// extensions on builtin types
extension Int {
    func cubed() -> Int { return self * self * self }
}
extension String {
    func shouted() -> String { return self.uppercased() + "!" }
}
print(3.cubed(), "hey".shouted())

// generic extension on arrays
extension Array {
    func secondOrNil() -> Element? {
        return count >= 2 ? self[1] : nil
    }
}
print([10, 20, 30].secondOrNil()!, [1].secondOrNil() ?? -1)
