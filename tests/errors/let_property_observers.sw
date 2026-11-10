struct Counter {
    let value: Int = 0 {
        didSet { print("changed") }
    }
}
