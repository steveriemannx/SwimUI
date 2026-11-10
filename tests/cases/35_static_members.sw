// Static computed properties (get/set and read-only), plus static stored and
// static subscript members used together.
struct Config {
    static var stored: Int = 1

    static var doubled: Int {
        get { stored * 2 }
        set { stored = newValue / 2 }
    }

    static var description: String {
        return "Config(stored: \(stored))"
    }
}

print(Config.doubled, Config.description)
Config.doubled = 10
print(Config.stored)
Config.doubled += 2
print(Config.doubled, Config.stored)

enum Planet: Int, CaseIterable {
    case mercury = 1
    case earth = 3
    case mars = 4

    static var names: [String] {
        return allCases.map { $0.description }
    }

    static subscript(index: Int) -> Planet {
        get { allCases[index] }
    }
}
print(Planet.names)
print(Planet[1], Planet[2])

// assigning static computed properties from inside static members
struct Counter {
    static var stored: Int = 0
    static var doubled: Int {
        get { stored * 2 }
        set { stored = newValue / 2 }
    }
    static func reset(to value: Int) {
        doubled = value
    }
    static func bump(by amount: Int) {
        doubled += amount
    }
}
Counter.reset(to: 7)
print(Counter.stored, Counter.doubled)
Counter.bump(by: 2)
print(Counter.stored, Counter.doubled)
