// Error handling with do/catch, throws and error enums.
enum ValidationError: Error {
    case tooShort(minimum: Int)
    case wrongFormat
    case empty
}

func validate(_ password: String) throws -> String {
    if password.isEmpty {
        throw ValidationError.empty
    }
    if password.count < 6 {
        throw ValidationError.tooShort(minimum: 6)
    }
    if !password.contains(where: { $0.isNumber }) {
        throw ValidationError.wrongFormat
    }
    return "ok: \(password)"
}

for candidate in ["", "abc", "abcdef", "abc123"] {
    do {
        print(try validate(candidate))
    } catch ValidationError.empty {
        print("empty password")
    } catch ValidationError.tooShort(let minimum) {
        print("need at least \(minimum) characters")
    } catch {
        print("other error")
    }
}

// propagate errors with throws
func firstValid(_ values: [String]) throws -> String {
    for value in values {
        if let result = try? validate(value) {
            return result
        }
    }
    throw ValidationError.empty
}
print(try! firstValid(["abc123"]))
do {
    print(try firstValid(["short"]))
} catch {
    print("no valid value")
}

// defer runs on scope exit
func withCleanup() -> Int {
    defer { print("first defer") }
    defer { print("second defer") }
    print("body")
    return 42
}
print(withCleanup())

// fatalError-style guards are not triggered here
func safeDivide(_ a: Int, _ b: Int) -> Int? {
    guard b != 0 else {
        return nil
    }
    return a / b
}
print(safeDivide(10, 2)!, safeDivide(10, 0) ?? -1)
