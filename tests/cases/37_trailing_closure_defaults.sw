// A trailing closure binds to the last parameter even when earlier parameters
// are omitted through their default values.
func schedule(name: String, priority: Int = 1, action: () -> Void) {
    print("schedule \(name) priority \(priority)")
    action()
}

schedule(name: "refresh") {
    print("running refresh")
}

func makeGreeter(greeting: String = "Hello", name: String, then: (String) -> Void) -> String {
    then(greeting)
    return "\(greeting), \(name)!"
}

let text = makeGreeter(name: "swim") { line in
    print(line)
}
print(text)
