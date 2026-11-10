// Class deinitializers run when ARC releases the last reference.
class Resource {
    let name: String
    let size: Int
    init(name: String, size: Int) {
        self.name = name
        self.size = size
    }
    deinit { print("release", name, size) }
}
var a: Resource? = Resource(name: "a", size: 1)
print("made a")
a = nil
var list: [Resource] = []
list.append(Resource(name: "b", size: 2))
print("made b")
list.removeLast()
print("removed b")

// inherited deinitializers run derived-first
class Base {
    init() {}
    deinit { print("base") }
}
class Sub: Base {
    let tag: String
    init(tag: String) {
        self.tag = tag
        super.init()
    }
    deinit { print("sub", tag) }
}
var s: Sub? = Sub(tag: "s")
s = nil

// stored members are released after the owner's deinit
class Outer {
    let inner: Resource
    init() {
        inner = Resource(name: "inner", size: 3)
    }
    deinit { print("outer deinit") }
}
var o: Outer? = Outer()
o = nil
print("done")
