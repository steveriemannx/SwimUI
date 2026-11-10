// Initializer delegation with self.init(...), convenience initializers,
// overloaded initializer labels and failable delegation chains.
struct Temperature {
    var celsius: Int

    init(celsius: Int) {
        self.celsius = celsius
    }

    convenience init(fahrenheit: Int) {
        self.init(celsius: (fahrenheit - 32) * 5 / 9)
    }

    convenience init(kelvin: Int) {
        self.init(celsius: kelvin - 273)
    }
}

print(Temperature(celsius: 100).celsius)
print(Temperature(fahrenheit: 212).celsius)
print(Temperature(kelvin: 273).celsius)

class Rectangle {
    var width: Int
    var height: Int

    init(width: Int, height: Int) {
        self.width = width
        self.height = height
    }

    convenience init(square side: Int) {
        self.init(width: side, height: side)
    }
}
let square = Rectangle(square: 4)
print(square.width, square.height)

struct Parsed {
    let value: Int

    init?(value: Int) {
        if value < 0 { return nil }
        self.value = value
    }

    init?(text: String) {
        guard let number = Int(text) else { return nil }
        if !self.init(value: number) { return nil }
    }
}
print(Parsed(value: 3)!.value)
print(Parsed(text: "12")!.value)
print(Parsed(text: "-3") == nil)
print(Parsed(text: "abc") == nil)

// observers do not run while an initializer (or a delegated initializer)
// writes the property
struct Observed {
    var value: Int {
        didSet { print("observed", oldValue, "->", value) }
    }

    init(value: Int) {
        self.value = value
    }

    convenience init(doubleOf other: Observed) {
        self.init(value: other.value * 2)
    }
}
var observed = Observed(value: 5)
var doubled = Observed(doubleOf: observed)
print(doubled.value)
doubled.value = 30
