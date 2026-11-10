// Common Swift idioms: empty bodies, discard bindings, Character comparisons,
// stride in a for loop and discarded call results.
func noop() {}
class EmptyClass {
    init() {}
}
struct EmptyStruct {
    init() {}
}

noop()
print(EmptyClass() is EmptyClass)
print(EmptyStruct())

var value = 0
_ = value
let _ = value + 1
print("value:", value)

func firstCharacter(_ text: String) -> Character? {
    return text.first
}
func isVowel(_ character: Character) -> Bool {
    switch character {
    case "a", "e", "i", "o", "u":
        return true
    default:
        return false
    }
}
if let character = firstCharacter("apple") {
    print(character, isVowel(character), character == "a")
}

for n in stride(from: 0, to: 6, by: 2) {
    print(n, terminator: " ")
}
print("")

var total = 0
func bump() -> Int {
    total += 1
    return total
}
_ = bump()
bump()
print("total:", total)
