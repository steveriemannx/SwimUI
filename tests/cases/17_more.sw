// More realistic combinations.
struct Money: Equatable {
    var cents: Int
    var description: String {
        let dollars = cents / 100
        let rest = cents % 100
        return "\(dollars).\(rest < 10 ? "0" : "")\(rest)"
    }
}
let price = Money(cents: 1234)
print(price)
print(price == Money(cents: 1234), price == Money(cents: 1))

class Account {
    let owner: String
    var balance: Money
    private var history: [String] = []

    init(owner: String, opening: Money) {
        self.owner = owner
        self.balance = opening
        history.append("open \(opening)")
    }

    func deposit(_ amount: Money) {
        balance = Money(cents: balance.cents + amount.cents)
        history.append("deposit \(amount)")
    }

    func withdraw(_ amount: Money) -> Bool {
        if amount.cents > balance.cents {
            history.append("rejected \(amount)")
            return false
        }
        balance = Money(cents: balance.cents - amount.cents)
        history.append("withdraw \(amount)")
        return true
    }

    func statement() -> [String] {
        return history
    }
}
let account = Account(owner: "Ada", opening: Money(cents: 10000))
account.deposit(Money(cents: 250))
print(account.withdraw(Money(cents: 5000)), account.withdraw(Money(cents: 99999)))
print(account.owner, account.balance)
for line in account.statement() {
    print(line)
}

// generic queue
struct Queue<Element> {
    private var items: [Element] = []
    mutating func enqueue(_ item: Element) {
        items.append(item)
    }
    mutating func dequeue() -> Element? {
        if items.isEmpty {
            return nil
        }
        return items.remove(at: 0)
    }
    var count: Int { items.count }
}
var queue = Queue<String>()
queue.enqueue("first")
queue.enqueue("second")
print(queue.count, queue.dequeue()!, queue.dequeue()!, queue.dequeue() ?? "empty")

// protocol with default implementation used through generic function
protocol Summary {
    func summary() -> String
}
extension Summary {
    func describeTwice() -> String {
        return summary() + " / " + summary()
    }
}
struct NumberSummary: Summary {
    var number: Int
    func summary() -> String { return "number \(number)" }
}
print(NumberSummary(number: 3).describeTwice())

// higher order functions over structs
let transactions = [Money(cents: 500), Money(cents: 1250), Money(cents: 99)]
let total = transactions.reduce(0) { $0 + $1.cents }
print(total)
print(transactions.map { $0.cents }.max()!)
print(transactions.sorted { $0.cents > $1.cents }.map { $0.cents })
