// Unicode operator symbols (Swift-style operator characters) and their
// user-defined implementations.

prefix operator √
prefix func √ (value: Double) -> Double { sqrt(value) }
print(√16.0)

infix operator ≤: ComparisonPrecedence
func ≤ (lhs: Int, rhs: Int) -> Bool { lhs < rhs || lhs == rhs }
print(1 ≤ 2, 2 ≤ 1)

infix operator ≠: ComparisonPrecedence
func ≠ (lhs: Int, rhs: Int) -> Bool { lhs != rhs }
print(3 ≠ 4, 3 ≠ 3)

infix operator ×: MultiplicationPrecedence
func × (lhs: Int, rhs: Int) -> Int { lhs * rhs }
print(6 × 7)

infix operator →: AdditionPrecedence
func → (lhs: Int, rhs: Int) -> Int { lhs + rhs }
print(40 → 2)

// Unicode operators compose with built-ins according to their precedence
print(2 × 3 → 4)
print(2 × (3 → 4))

struct Celsius {
    var degrees: Double
    static func ± (lhs: Celsius, rhs: Double) -> Celsius {
        return Celsius(degrees: lhs.degrees + rhs)
    }
}
infix operator ±: AdditionPrecedence
print((Celsius(degrees: 20.0) ± 1.5).degrees)
