// Weak and unowned references: ARC without a cycle collector.
class Node {
    let name: String
    weak var parent: Node?
    init(name: String) { self.name = name }
}
var root: Node? = Node(name: "root")
let child = Node(name: "child")
child.parent = root
print(child.parent!.name)
root = nil
print(child.parent == nil)

// reassignment replaces the weak referent; temporaries are not kept alive
var first: Node? = Node(name: "first")
let holder = Node(name: "holder")
holder.parent = first
print(holder.parent!.name)
first = nil
print(holder.parent == nil)
holder.parent = Node(name: "temp")
print(holder.parent == nil)

// unowned references are non-owning
class Owner {
    let id: Int
    init(id: Int) { self.id = id }
}
class Item {
    unowned var owner: Owner
    init(owner: Owner) { self.owner = owner }
}
let owner = Owner(id: 7)
let item = Item(owner: owner)
print(item.owner.id)
