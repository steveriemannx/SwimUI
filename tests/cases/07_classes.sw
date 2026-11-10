// Classes: reference semantics, inheritance, dynamic dispatch, super, casts.
class Animal {
    var name: String
    init(name: String) {
        self.name = name
    }
    func speak() -> String { return "..." }
    func introduce() -> String { return "I am \(name)" }
    var description: String { return "Animal(\(name))" }
}

class Dog: Animal {
    var breed: String
    init(name: String, breed: String) {
        self.breed = breed
        super.init(name: name)
    }
    override func speak() -> String { return "Woof" }
    override func introduce() -> String {
        return super.introduce() + " and I am a \(breed)"
    }
}

class Cat: Animal {
    init(name: String) {
        super.init(name: name)
    }
    override func speak() -> String { return "Meow" }
}

let animals: [Animal] = [Dog(name: "Rex", breed: "lab"), Cat(name: "Tom")]
for animal in animals {
    print(animal.introduce(), animal.speak())
}

// reference semantics
let first = Animal(name: "shared")
let second = first
second.name = "renamed"
print(first.name, second.name)

// downcasting
if let dog = animals[0] as? Dog {
    print("dog breed \(dog.breed)")
}
let forcedDog = animals[0] as! Dog
print(forcedDog.speak())
if animals[1] is Cat {
    print("second is a cat")
}

// upcasting with as
let upcast = forcedDog as Animal
print(upcast.name)

// initializer chains
class Counter {
    var value: Int
    init() {
        value = 0
    }
    init(start: Int) {
        value = start
    }
    func next() -> Int {
        value += 1
        return value
    }
}
let counterA = Counter()
let counterB = Counter(start: 10)
print(counterA.next(), counterB.next())

// class with default property value
class Config {
    var debug: Bool = false
}
print(Config().debug)
