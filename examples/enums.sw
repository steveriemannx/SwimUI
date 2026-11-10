// Enums: raw values, associated values, pattern matching, recursive enums
enum Direction: Int {
    case north = 1
    case south
    case east
    case west

    func symbol() -> String {
        switch self {
        case .north: return "N"
        case .south: return "S"
        case .east: return "E"
        case .west: return "W"
        }
    }
}
print(Direction.north.rawValue, Direction.west.rawValue, Direction.east.symbol())
if let direction = Direction(rawValue: 2) {
    print("rawValue 2 = \(direction)")
}

enum Shape {
    case circle(radius: Double)
    case rectangle(width: Double, height: Double)
    case point
}

func area(_ shape: Shape) -> Double {
    switch shape {
    case .circle(let radius):
        return 3.14159 * radius * radius
    case .rectangle(let width, let height):
        return width * height
    case .point:
        return 0
    }
}
print(area(.circle(radius: 2.0)))
print(area(.rectangle(width: 3.0, height: 4.0)))

// Recursive enums (represented with references to break the cycle)
enum Tree {
    case leaf(Int)
    case node(Tree, Tree)
}
func sum(_ tree: Tree) -> Int {
    switch tree {
    case .leaf(let value):
        return value
    case .node(let left, let right):
        return sum(left) + sum(right)
    }
}
print(sum(.node(.leaf(1), .node(.leaf(2), .leaf(3)))))

// if case / guard case
let shape = Shape.rectangle(width: 2.0, height: 5.0)
if case .rectangle(let width, let height) = shape {
    print("rectangle \(width)x\(height)")
}
