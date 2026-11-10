// Modern Swift features supported by Swim: property observers, failable
// initializers, variadic parameters, subscripts and pattern helpers.

struct Temperature {
    var celsius: Int = 0 {
        willSet { print("-> \(newValue)C") }
        didSet { print("was \(oldValue)C, now \(celsius)C") }
    }
}

var temperature = Temperature()
temperature.celsius = 21
temperature.celsius += 1

struct User {
    let name: String
    let age: Int

    init?(name: String, age: Int) {
        guard !name.isEmpty, age >= 0 else { return nil }
        self.name = name
        self.age = age
    }
}

if let user = User(name: "Ada", age: 36) {
    print("\(user.name) is \(user.age)")
}
print("invalid user rejected:", User(name: "", age: 1) == nil)

func average(_ values: Double...) -> Double {
    if values.isEmpty { return 0 }
    return values.reduce(0) { $0 + $1 } / Double(values.count)
}
print("average:", average(1.0, 2.0, 3.0, 4.0))

struct Matrix {
    var cells: [[Int]]

    subscript(row: Int, column: Int) -> Int {
        get { cells[row][column] }
        set { cells[row][column] = newValue }
    }
}

var matrix = Matrix(cells: [[1, 2], [3, 4]])
matrix[0, 0] = 9
print("matrix:", matrix)

enum Response {
    case ok(code: Int)
    case failure(message: String)
    case pending
}

let responses: [Response] = [.ok(code: 200), .failure(message: "boom"),
                             .pending]
for case .ok(let code) in responses {
    print("success:", code)
}
for case .failure(let message) in responses {
    print("failure:", message)
}
