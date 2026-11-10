// Variables, constants and basic types
let name = "Swim"          // constant (immutable)
var version = 1            // variable (mutable)
version += 1

let pi = 3.14159
let answer: Int = 42
let ready: Bool = true

print(name, version, pi, answer, ready)

// String interpolation
print("\(name) v\(version) ready: \(ready)")

// Arithmetic and comparison
print(7 / 2, 7 % 2, 7.0 / 2.0)
print(answer > 40 && !ready == false)

// Conversions (failable conversions return Optionals)
if let number = Int("123") {
    print("parsed: \(number * 2)")
} else {
    print("not a number")
}
print(Int(3.99), Double(2), String(42))
