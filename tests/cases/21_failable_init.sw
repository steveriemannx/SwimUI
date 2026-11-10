// Failable initializers: init? / init!, guard + return nil, subclass
// initializer chaining and use in conditional bindings.
struct User {
    let name: String
    let age: Int

    init?(name: String, age: Int) {
        guard !name.isEmpty, age >= 0 else { return nil }
        self.name = name
        self.age = age
    }
}

if let user = User(name: "Ada", age: 36) {
    print(user.name, user.age)
}
print(User(name: "", age: 1) == nil)
print(User(name: "Bob", age: -1) == nil)

let optionalUser: User? = User(name: "Carol", age: 20)
print(optionalUser?.name ?? "none")
print(optionalUser!.age)

class Connection {
    let host: String
    init?(host: String) {
        if host.isEmpty { return nil }
        self.host = host
    }
}

class SecureConnection: Connection {
    let port: Int
    init?(host: String, port: Int) {
        if port <= 0 { return nil }
        self.port = port
        if !super.init(host: host) { return nil }
    }
}

print(SecureConnection(host: "example.com", port: 443)!.port)
print(SecureConnection(host: "example.com", port: 0) == nil)
print(SecureConnection(host: "", port: 443) == nil)

// init! behaves like an implicitly unwrapped optional
struct Strict {
    let value: Int
    init!(value: Int) {
        if value < 0 { return nil }
        self.value = value
    }
}
print(Strict(value: 3).value)

// failable initializer for a generic type
struct Box<T> {
    let value: T
    init?(value: T, valid: Bool) {
        if !valid { return nil }
        self.value = value
    }
}
print(Box(value: 42, valid: true)!.value)
print(Box(value: 42, valid: false) == nil)
