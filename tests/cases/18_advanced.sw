import Foundation

// nested functions
func outer(_ value: Int) -> Int {
    func helper(_ x: Int) -> Int {
        return x * 2
    }
    return helper(value) + 1
}
print(outer(5))

// hashable struct used as dict key
struct Key: Hashable {
    var id: Int
    var name: String
}
var map: [Key: Int] = [:]
let key = Key(id: 1, name: "one")
map[key] = 42
print(map[key]!)

// type constructors with generic args
let emptyArray = Array<Int>()
let emptyDictionary = Dictionary<String, Int>()
let set = Set<Int>([1, 2, 2, 3])
print(emptyArray.count, emptyDictionary.count, set.count)

// extension with computed property and static function
struct Vector {
    var x: Int
    var y: Int
}
extension Vector {
    var lengthSquared: Int { x * x + y * y }
    static func unitX() -> Vector { return Vector(x: 1, y: 0) }
    func scaled(by factor: Int) -> Vector {
        return Vector(x: x * factor, y: y * factor)
    }
}
print(Vector(x: 3, y: 4).lengthSquared)
print(Vector.unitX())
print(Vector(x: 1, y: 2).scaled(by: 10))

// class statics
class Registry {
    static var items: [String] = []
    static func add(_ item: String) {
        items.append(item)
    }
    static func count() -> Int { return items.count }
}
Registry.add("a")
Registry.add("b")
print(Registry.count())

// random
let randomValue = Int.random(in: 5...5)
print(randomValue)

// array extras
var list = [1, 2, 3, 4, 5, 6]
list.removeAll(where: { $0 % 2 == 0 })
print(list)
print([10, 20, 30].firstIndex(where: { $0 == 20 })!)
print([10, 20, 30].last(where: { $0 > 10 })!)
var mutable = [1, 2, 3]
mutable.removeAll(where: { $0 < 3 })
print(mutable)

// custom description conformance
struct Temperature: CustomStringConvertible {
    var degrees: Int
    var description: String { return "\(degrees) deg" }
}
print(Temperature(degrees: 21))
print("temp: \(Temperature(degrees: 7))")

// optional map / flatMap
let maybeNumber: Int? = 10
print(maybeNumber.map { $0 + 1 }!)
print(maybeNumber.flatMap { $0 > 5 ? Optional($0 * 2) : nil }!)

// tuple labels through functions
func split(_ text: String) -> (head: String, tail: String) {
    return (head: text.prefix(1), tail: text.dropFirst())
}
let parts = split("swim")
print(parts.head, parts.tail)

// switch with where on enum associated values
enum Event {
    case click(x: Int, y: Int)
    case key(String)
}
func describe(_ event: Event) -> String {
    switch event {
    case .click(let x, let y) where x == y:
        return "diagonal \(x)"
    case .click(let x, let y):
        return "click \(x),\(y)"
    case .key(let stroke):
        return "key \(stroke)"
    }
}
print(describe(.click(x: 3, y: 3)), describe(.click(x: 1, y: 2)), describe(.key("a")))
