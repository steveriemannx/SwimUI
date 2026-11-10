// Classes: reference semantics, inheritance, dynamic dispatch, super, casts
class Animal {
    var name: String

    init(name: String) {
        self.name = name
    }

    func speak() -> String { "..." }

    func introduce() -> String { "I am \(name)" }

    var description: String { "Animal(\(name))" }
}

class Dog: Animal {
    var breed: String

    init(name: String, breed: String) {
        self.breed = breed
        super.init(name: name)
    }

    override func speak() -> String { "Woof" }

    override func introduce() -> String {
        return super.introduce() + ", a \(breed)"
    }
}

class Cat: Animal {
    init(name: String) {
        super.init(name: name)
    }

    override func speak() -> String { "Meow" }
}

let animals: [Animal] = [Dog(name: "Rex", breed: "lab"), Cat(name: "Tom")]
for animal in animals {
    print(animal.introduce(), animal.speak())
}

// Reference semantics
let shared = Animal(name: "shared")
let alias = shared
alias.name = "renamed"
print(shared.name, alias.name)

// Downcasting
if let dog = animals[0] as? Dog {
    print("breed:", dog.breed)
}
let cat = animals[1] as! Cat
print(cat.speak())
print(animals[1] is Cat)

// Static members and computed properties in a class
class Counter {
    static var created = 0
    var value = 0

    init() {
        Counter.created += 1
    }

    func next() -> Int {
        value += 1
        return value
    }
}
let first = Counter()
let second = Counter()
print(first.next(), second.next(), Counter.created)
