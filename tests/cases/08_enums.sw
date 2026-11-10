// Enums: plain, raw values, associated values, pattern matching, recursion.
enum Direction: Int {
    case north = 1
    case south
    case east
    case west
}
print(Direction.north.rawValue, Direction.south.rawValue, Direction.west.rawValue)
print(Direction.east)
let direction = Direction.south
switch direction {
case .north:
    print("up")
case .south, .east:
    print("down or right")
case .west:
    print("left")
}
if let parsed = Direction(rawValue: 3) {
    print("parsed \(parsed)")
}

// methods and computed properties on enums
enum Planet: Int {
    case mercury = 1
    case earth = 3
    func gravity() -> Double {
        switch self {
        case .mercury:
            return 3.7
        case .earth:
            return 9.8
        default:
            return 0.0
        }
    }
}
print(Planet.earth.rawValue, Planet.earth.gravity())
if Planet.earth == Planet.earth {
    print("equal")
}

// string raw values
enum Suit: String {
    case hearts = "h"
    case spades = "s"
    case clubs = "c"
}
print(Suit.hearts.rawValue)
if let suit = Suit(rawValue: "s") {
    print("found \(suit)")
}
if Suit(rawValue: "x") == nil {
    print("missing")
}

// associated values
enum Shape {
    case circle(radius: Double)
    case rectangle(width: Double, height: Double)
    case point
}
func area(_ shape: Shape) -> Double {
    switch shape {
    case .circle(let radius):
        return 3.14 * radius * radius
    case .rectangle(let width, let height):
        return width * height
    case .point:
        return 0.0
    }
}
print(area(.circle(radius: 2.0)))
print(area(.rectangle(width: 3.0, height: 4.0)))
print(area(.point))
let shape = Shape.circle(radius: 1.0)
if case .circle(let radius) = shape {
    print("radius \(radius)")
}

// recursive enum
enum Tree {
    case leaf(Int)
    case node(Tree, Tree)
}
func sumTree(_ tree: Tree) -> Int {
    switch tree {
    case .leaf(let value):
        return value
    case .node(let left, let right):
        return sumTree(left) + sumTree(right)
    }
}
let tree = Tree.node(Tree.leaf(1), Tree.node(Tree.leaf(2), Tree.leaf(3)))
print(sumTree(tree))

// patterns with where and multiple values
for value in [1, 2, 3, 4] {
    switch value {
    case 1:
        print("one")
    case let other where other % 2 == 0:
        print("even \(other)")
    default:
        print("other \(value)")
    }
}
