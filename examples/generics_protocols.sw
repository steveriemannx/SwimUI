// Generics and protocols (compiled to Nim concepts, checked statically)
protocol Shape {
    func area() -> Double
    var name: String { get }
}

struct Circle: Shape {
    var radius: Double
    var name: String { "circle" }
    func area() -> Double { 3.14159 * radius * radius }
}

struct Square: Shape {
    var side: Double
    var name: String { "square" }
    func area() -> Double { side * side }
}

func describe<T: Shape>(_ shape: T) -> String {
    return "\(shape.name): \(shape.area())"
}
print(describe(Circle(radius: 1.0)))
print(describe(Square(side: 3.0)))

// Protocol extensions provide default implementations
protocol Greeter {
    func greeting() -> String
}
extension Greeter {
    func greet() -> String { greeting() + "!" }
}
struct English: Greeter {
    func greeting() -> String { "Hello" }
}
struct French: Greeter {
    func greeting() -> String { "Bonjour" }
}
print(English().greet(), French().greet())

// Generic functions
func largest<T: Comparable>(_ values: [T]) -> T? {
    guard let firstValue = values.first else {
        return nil
    }
    var best = firstValue
    for value in values where value > best {
        best = value
    }
    return best
}
print(largest([3, 9, 2])!, largest(["apple", "pear"])!)

// Generic containers
struct Stack<Element> {
    private var items: [Element] = []
    mutating func push(_ item: Element) { items.append(item) }
    mutating func pop() -> Element? { items.popLast() }
    var count: Int { items.count }
    var isEmpty: Bool { items.isEmpty }
}
var stack = Stack<Int>()
stack.push(1)
stack.push(2)
print(stack.count, stack.pop()!, stack.isEmpty)

// Generic enums
enum Result<Value> {
    case success(Value)
    case failure(String)
}
func unwrap<Value>(_ result: Result<Value>) -> Value? {
    switch result {
    case .success(let value):
        return value
    case .failure(let message):
        print("error: \(message)")
        return nil
    }
}
print(unwrap(Result<Int>.success(42))!)
print(unwrap(Result<Int>.failure("boom")) ?? 0)

// Extending built-in types
extension Int {
    func squared() -> Int { self * self }
}
print(5.squared())
