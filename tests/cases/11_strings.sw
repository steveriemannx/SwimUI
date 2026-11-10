// String and Character utilities.
let text = "Hello, swim"
print(text.count, text.isEmpty, text.contains("swim"))
print(text.hasPrefix("Hello"), text.hasSuffix("swim"))
print(text.uppercased(), text.lowercased(), text.capitalized())
print(text.replacingOccurrences(of: "swim", with: "nim"))
print(text.split(separator: " ").count)
print(text.components(separatedBy: ", "))
print("  padded  ".trimmingCharacters(in: .whitespaces))
print(String(repeating: "-", count: 10))

// indexing and slicing
let word = "swift"
print(word[0], word[4], word.first!, word.last!)
print(word.prefix(2), word.suffix(2))
print(word.dropFirst(), word.dropLast(), word.dropFirst(3), word.dropLast(3))
print(word.reversed())

// characters
let character: Character = "x"
print(character.isLetter, "7".first!.isNumber, " ".first!.isWhitespace)
print("a".first!.uppercased(), "Z".first!.lowercased())
print("7".first!.wholeNumberValue!)

// multiline strings
let poem = """
    first line
    second line
    """
print(poem.count)
print(poem.contains("second"))

// escapes
print("tab\there, newline\\n, quote\" done")
print("unicode escape length: \(("\u{00E9}").count)")

// interpolation with expressions
let values = [1, 2, 3]
print("sum=\(values.reduce(0) { $0 + $1 }), count=\(values.count), upper=\(text.uppercased())")

// joining strings
let parts = ["a", "b", "c"]
print(parts.joined(separator: "-"))
print(parts.joined(separator: ""))

// string comparison
print("abc" == "abc", "abc" < "abd", "z" > "a")

// splitting into characters
var letters: [Character] = []
for character in "abc" {
    letters.append(character)
}
print(letters.count)

// searching
print(text.index(of: "swim")!, text.firstIndex(of: "s")!)
