// Structs: value types, properties, methods, mutating, computed properties, static members
struct Point: Equatable {
    var x: Int
    var y: Int

    init(x: Int, y: Int) {
        self.x = x
        self.y = y
    }

    func lengthSquared() -> Int { x * x + y * y }

    mutating func move(dx: Int, dy: Int) {
        x += dx
        y += dy
    }

    var description: String { "Point(\(x), \(y))" }

    static func origin() -> Point { Point(x: 0, y: 0) }
}

var point = Point(x: 3, y: 4)
print(point.lengthSquared(), point)
point.move(dx: 1, dy: 1)
print(point)
print(Point.origin(), point == Point(x: 4, y: 5))

// Value semantics: copies are independent
var copy = point
copy.x = 100
print(point.x, copy.x)

// Default values and the memberwise initializer
struct Rectangle {
    var width: Double = 1.0
    var height: Double = 2.0
    var area: Double { width * height }
}
print(Rectangle().area, Rectangle(width: 3.0, height: 4.0).area)

// Property setter
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
