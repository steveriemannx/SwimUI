struct Config {
    static var value: Int = 0 {
        didSet { print("changed") }
    }
}
