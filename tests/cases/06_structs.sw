// Structs: stored/computed properties, methods, mutating, static, init.
struct Point: Equatable {
    var x: Int
    var y: Int

    init(x: Int, y: Int) {
        self.x = x
        self.y = y
    }

    func lengthSquared() -> Int { x * x + y * y }

    mutating func translate(dx: Int, dy: Int) {
        x += dx
        y += dy
    }

    var description: String {
        return "Point(\(x), \(y))"
    }

    static func origin() -> Point {
        return Point(x: 0, y: 0)
    }
}
var point = Point(x: 3, y: 4)
print(point.lengthSquared())
point.translate(dx: 1, dy: 1)
print(point)
print(Point.origin())
print(point == Point(x: 4, y: 5))

// value semantics
var copy = point
copy.x = 100
print(point.x, copy.x)

// default property values and memberwise initializer
struct Rectangle {
    var width: Double = 1.0
    var height: Double = 2.0
    var area: Double { width * height }
    var perimeter: Double { 2 * (width + height) }
}
let unit = Rectangle()
let rect = Rectangle(width: 3.0, height: 4.0)
print(unit.area, rect.area, rect.perimeter)

// computed property with setter
struct Temperature {
    var celsius: Double
    var fahrenheit: Double {
        get { celsius * 9.0 / 5.0 + 32.0 }
        set { celsius = (newValue - 32.0) * 5.0 / 9.0 }
    }
}
var temperature = Temperature(celsius: 100.0)
print(temperature.fahrenheit)
temperature.fahrenheit = 32.0
print(temperature.celsius)

// methods on structs called from other methods
struct Counter {
    var value: Int = 0
    mutating func increment() { value += 1 }
    mutating func increment(by amount: Int) { value += amount }
    func doubled() -> Int { value * 2 }
}
var counter = Counter()
counter.increment()
counter.increment(by: 4)
print(counter.value, counter.doubled())
