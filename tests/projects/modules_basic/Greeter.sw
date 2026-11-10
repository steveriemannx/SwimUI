import MathX
import Foundation

struct Greeter {
    var name: String
    func greet() -> String {
        return "Hi \(name), triple=\(triple(name.count))"
    }
}

print("Greeter loaded")
