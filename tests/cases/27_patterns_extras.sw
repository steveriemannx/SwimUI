// for-case pattern loops and Swift 5.7 shorthand conditional bindings.
let optionals: [Int?] = [1, nil, 3, nil, 8]
for case let value? in optionals {
    print(value)
}

for case let value? in optionals where value > 5 {
    print("big", value)
}

enum Shape {
    case circle(radius: Int)
    case square(side: Int)
    case point
}
let shapes: [Shape] = [.circle(radius: 2), .point, .square(side: 3),
                       .circle(radius: 5)]
for case .circle(let radius) in shapes {
    print("circle", radius)
}
for case .square(let side) in shapes where side > 2 {
    print("square", side)
}
for case .point in shapes {
    print("point")
}

let rows: [[Int]?] = [[1, 2], nil, [3]]
outer: for case let row? in rows {
    for value in row {
        if value == 2 {
            continue outer
        }
        print("row value", value)
    }
}

let text: String? = "swim"
if let text {
    print("unwrapped", text)
}
var maybeCount: Int? = 2
if let maybeCount {
    print("count", maybeCount)
}
guard let maybeCount else {
    fatalError("missing")
}
print("guarded", maybeCount)

func describe(_ value: Int?) -> String {
    guard let value else { return "none" }
    return "some \(value)"
}
print(describe(nil), describe(4))

class Animal {
    init() {}
}
class Dog: Animal {}
class Cat: Animal {}
class Bird: Animal {}

let animals: [Animal] = [Dog(), Cat(), Bird(), Dog()]
for animal in animals {
    switch animal {
    case is Dog:
        print("dog")
    case is Cat:
        print("cat")
    default:
        print("other animal")
    }
}
