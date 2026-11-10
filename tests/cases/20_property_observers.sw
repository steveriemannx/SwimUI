// Property observers: willSet / didSet with default and custom parameter
// names, in initializers, through mutating methods and computed properties.
struct Temperature {
    var celsius: Int = 0 {
        willSet { print("willSet", celsius, "->", newValue) }
        didSet { print("didSet", oldValue, "->", celsius) }
    }
    var fahrenheit: Int {
        get { celsius * 9 / 5 + 32 }
        set { celsius = (newValue - 32) * 5 / 9 }
    }
}

var temperature = Temperature()
temperature.celsius = 100
temperature.celsius += 1
temperature.fahrenheit = 212
print(temperature.celsius, temperature.fahrenheit)

struct Countdown {
    var value: Int = 3 {
        didSet(old) { print("was", old) }
        willSet(new) { print("now", new) }
    }
}
var countdown = Countdown()
countdown.value = 2
countdown.value = 1

// observers on a class property, including mutation through a method
class Logger {
    var entries: [String] = [] {
        didSet { print("entries:", entries.count) }
    }
    init() {}
}
let log = Logger()
log.entries.append("a")
log.entries.append("b")
log.entries = log.entries + ["c"]

// observers on a struct property mutated from a mutating method
struct Inventory {
    var items: [Int] = [] {
        didSet { print("inventory", items) }
    }
    mutating func add(_ item: Int) {
        items.append(item)
    }
}
var inventory = Inventory()
inventory.add(1)
inventory.add(2)
inventory.items.removeLast()
print(inventory.items)

// custom initializer assigns the backing storage directly: no observers run
struct Account {
    var balance: Int {
        didSet { print("balance changed") }
    }
    init(balance: Int) {
        self.balance = balance
    }
}
var account = Account(balance: 10)
print(account.balance)
account.balance = 20

// observers with an inferred type
struct Tally {
    var count = 0 {
        didSet { print("tally", oldValue, "->", count) }
    }
}
var tally = Tally()
tally.count += 5

// inherited observed property (class setter must accept subclass instances)
class Base {
    var value: Int = 0 {
        didSet { print("base", oldValue, "->", value) }
    }
    init() {}
}
class Derived: Base {
    var label: String = ""
}
let derived = Derived()
derived.value = 3
derived.value += 2
print(derived.value)

// A stored property whose initializer is a call may be followed by observers
// (the observer brace must not be parsed as a trailing closure).
struct ComputedInit {
    var total = max(1, 2) {
        didSet { print("computed", oldValue, "->", total) }
    }
}
var computedInit = ComputedInit()
print(computedInit.total)
computedInit.total = 10

// Trailing closures still work in stored-property initializers
struct Sorted {
    var values = [3, 1, 2].sorted { $0 < $1 }
}
let sorted = Sorted()
print(sorted.values)
