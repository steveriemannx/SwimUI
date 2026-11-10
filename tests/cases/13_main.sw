// @main entry point with static helpers.
@main
struct Demo {
    static let title = "swim demo"

    static func square(_ value: Int) -> Int {
        return value * value
    }

    static func greet(_ name: String) -> String {
        return "Hello, \(name)!"
    }

    static func main() {
        print(title)
        print(greet("world"))
        let values = [1, 2, 3]
        let squares = values.map { square($0) }
        print(squares)
        print("done")
    }
}
