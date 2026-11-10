// Error handling: Error enums, throw, do/catch, try?/try!
enum ValidationError: Error {
    case empty
    case tooShort(minimum: Int)
    case noDigit
}

func validate(_ password: String) throws -> String {
    if password.isEmpty {
        throw ValidationError.empty
    }
    if password.count < 6 {
        throw ValidationError.tooShort(minimum: 6)
    }
    var hasDigit = false
    for character in password where character.isNumber {
        hasDigit = true
    }
    if !hasDigit {
        throw ValidationError.noDigit
    }
    return "accepted: \(password)"
}

for attempt in ["", "abc", "abcdef", "abc123"] {
    do {
        print(try validate(attempt))
    } catch ValidationError.empty {
        print("password is empty")
    } catch ValidationError.tooShort(let minimum) {
        print("needs at least \(minimum) characters")
    } catch {
        print("other error")
    }
}

// try? turns errors into Optional; try! asserts it cannot throw
let maybe = try? validate("abc123")
print(maybe != nil)
print(try! validate("good123"))

// Error propagation
func firstValid(_ values: [String]) throws -> String {
    for value in values {
        if let result = try? validate(value) {
            return result
        }
    }
    throw ValidationError.empty
}
do {
    print(try firstValid(["bad", "better123"]))
} catch {
    print("no valid input")
}

// defer: runs in reverse order on scope exit
func cleanupDemo() {
    defer { print("cleanup 1") }
    defer { print("cleanup 2") }
    print("work done")
}
cleanupDemo()
