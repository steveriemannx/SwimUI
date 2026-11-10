// Optionals: ?, !, ??, if let, guard let, optional chaining.
let present: Int? = 5
let missing: Int? = nil
print(present!, present ?? 0, missing ?? 0)
print(present == nil, missing == nil, present != nil)

if let value = present {
    print("present \(value)")
} else {
    print("absent")
}
if let value = missing {
    print("unexpected \(value)")
} else {
    print("absent as expected")
}

var maybeName: String? = nil
maybeName = "swim"
if let name = maybeName {
    print(name.count)
}

func parsePositive(_ text: String) -> Int? {
    guard let value = Int(text), value > 0 else {
        return nil
    }
    return value
}
print(parsePositive("12")!, parsePositive("-3") ?? 0)

// optional chaining through structs
struct Engine { var power: Int }
struct Car { var engine: Engine? }
struct Owner { var car: Car? }
let owner = Owner(car: Car(engine: Engine(power: 250)))
print(owner.car?.engine?.power ?? 0)
let emptyOwner = Owner(car: nil)
print(emptyOwner.car?.engine?.power ?? -1)

// while let
var stack = [1, 2, 3]
while let top = stack.last {
    print("top \(top)")
    stack.removeLast()
}

// nested optionals
let outer: Int?? = 7
if let inner = outer, let value = inner {
    print("nested \(value)")
}

// optional map
let length = maybeName.map { $0.count }
print(length!)
