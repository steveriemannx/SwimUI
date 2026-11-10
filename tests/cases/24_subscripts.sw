// Subscript declarations: read-only, read-write, multiple parameters,
// classes, extensions, generics and protocol requirements.
struct Matrix {
    var cells: [[Int]]

    subscript(row: Int, column: Int) -> Int {
        get { cells[row][column] }
        set { cells[row][column] = newValue }
    }
}

var matrix = Matrix(cells: [[1, 2], [3, 4]])
print(matrix[0, 1], matrix[1, 0])
matrix[1, 0] = 30
matrix[0, 0] += 5
print(matrix[0, 0], matrix[1, 0])
print(matrix)

struct ReadOnly {
    var values: [Int]
    subscript(index: Int) -> Int {
        get { values[index] }
    }
}
let readOnly = ReadOnly(values: [10, 20, 30])
print(readOnly[0], readOnly[2])

class Cache {
    var storage: [String: Int] = [:]
    init() {}
    subscript(key: String) -> Int {
        get { storage[key] ?? 0 }
        set { storage[key] = newValue }
    }
}
let cache = Cache()
cache["hits"] = 3
cache["hits"] += 2
print(cache["hits"], cache["misses"])

enum Direction: Int {
    case north = 0
    case east = 1
    case south = 2
    case west = 3

    subscript(turn: Int) -> Direction {
        return Direction(rawValue: (rawValue + turn) % 4)!
    }
}
print(Direction.north[1], Direction.north[3])

extension String {
    subscript(index: Int) -> String {
        get { String(self[index]) }
    }
}
print("swim"[0], "swim"[3])

extension Int {
    subscript(digit: Int) -> Int {
        var value = self
        var index = 0
        while index < digit {
            value /= 10
            index += 1
        }
        return value % 10
    }
}
print(12345[0], 12345[3])

struct Stack<Element> {
    private var items: [Element] = []
    mutating func push(_ item: Element) { items.append(item) }
    subscript(index: Int) -> Element {
        get { items[index] }
        set { items[index] = newValue }
    }
}
var stack = Stack<Int>()
stack.push(10)
stack.push(20)
print(stack[0], stack[1])
stack[1] = 99
print(stack)

protocol Indexable {
    subscript(index: Int) -> Int { get }
}
struct Numbers: Indexable {
    var values: [Int]
    subscript(index: Int) -> Int { get { values[index] } }
}
func firstOf<T: Indexable>(_ container: T) -> Int {
    return container[0]
}
print(firstOf(Numbers(values: [7, 8, 9])))
