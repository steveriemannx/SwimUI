// Custom operators, nested types and conditional compilation.

infix operator **: MultiplicationPrecedence
func ** (base: Int, power: Int) -> Int {
    var result = 1
    var index = 0
    while index < power {
        result *= base
        index += 1
    }
    return result
}
print("2 ** 10 =", 2 ** 10)

prefix operator %%
prefix func %% (value: Int) -> Int { value * 100 }
print("%%7 =", %%7)

struct Vector {
    struct Component {
        var value: Double
    }

    enum Axis {
        case x
        case y
    }

    var x: Double
    var y: Double

    static func + (lhs: Vector, rhs: Vector) -> Vector {
        return Vector(x: lhs.x + rhs.x, y: lhs.y + rhs.y)
    }

    func along(_ axis: Axis) -> Double {
        switch axis {
        case .x: return x
        case .y: return y
        }
    }
}

let sum = Vector(x: 1, y: 2) + Vector(x: 3, y: 4)
print("sum =", sum.x, sum.y)
print("x component:", sum.along(Vector.Axis.x))

#if true
print("conditional compilation is on")
#endif

#if DEBUG
print("debug build")
#else
print("release build")
#endif
