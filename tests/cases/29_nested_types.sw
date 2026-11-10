// Nested type declarations: structs, classes, enums, typealiases,
// extensions, static members and mutual references via the Nim type block.
struct Outer {
    typealias ID = Int

    struct Inner {
        var id: ID
        func doubled() -> Int { id * 2 }
    }

    enum State: Int {
        case idle = 0
        case running = 1
        case done = 2
    }

    var inner: Inner
    var state: State

    func summary() -> String {
        switch state {
        case .idle:
            return "idle \(inner.doubled())"
        case .running:
            return "running \(inner.doubled())"
        case .done:
            return "done"
        }
    }
}

let inner = Outer.Inner(id: 21)
print(inner.doubled())
let outer = Outer(inner: inner, state: .running)
print(outer.summary())
print(Outer.Inner(id: 3).doubled())
print(Outer.State.idle.rawValue, Outer.State.done.rawValue)
let state: Outer.State = .done
print(state == Outer.State.done)
let id: Outer.ID = 7
print(id)

extension Outer.Inner {
    func tripled() -> Int { id * 3 }
}
print(inner.tripled())

class Zoo {
    struct Animal {
        var name: String
    }

    enum Kind: Int {
        case cat = 1
        case dog = 2
    }

    static func makeAnimal() -> Animal {
        return Animal(name: "kitten")
    }
}
print(Zoo.makeAnimal().name)
print(Zoo.Kind.cat.rawValue)
print(Zoo.Animal(name: "pup").name)

// a nested type may refer back to its enclosing class
class Node {
    struct Snapshot {
        var owner: Node?
        var label: String
    }

    var label: String
    init(label: String) { self.label = label }
}
let node = Node(label: "root")
let snapshot = Node.Snapshot(owner: node, label: "snap")
print(snapshot.owner!.label, snapshot.label)

// nested generic type
struct PairBox {
    struct Pair<A, B> {
        var first: A
        var second: B
    }
}
let pair = PairBox.Pair(first: 1, second: "one")
print(pair.first, pair.second)
