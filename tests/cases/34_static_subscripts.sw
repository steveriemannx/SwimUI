// Static subscripts (type-level `Type[index]` access), including overloads by
// argument type and read/write/compound assignment.
struct Settings {
    static var values: [Int] = [1, 2, 3]

    static subscript(index: Int) -> Int {
        get { values[index] }
        set { values[index] = newValue }
    }

    static subscript(label: String) -> Int {
        get { label.count }
    }
}

print(Settings[1])
Settings[1] = 20
print(Settings[1])
Settings[0] += 5
print(Settings[0])
print(Settings["swim"])

class Registry {
    static var entries: [String] = ["alpha", "beta"]

    static subscript(index: Int) -> String {
        get { entries[index] }
        set { entries[index] = newValue }
    }
}
print(Registry[0])
Registry[1] = "zulu"
print(Registry[1])
print(Registry.entries)
