// Pattern matching: switch, if case, guard case, optional patterns.
enum Status {
    case ok(code: Int)
    case redirect(to: String)
    case failed
}

func describe(_ status: Status) -> String {
    switch status {
    case .ok(let code):
        return "ok \(code)"
    case .redirect(let target):
        return "redirect to \(target)"
    case .failed:
        return "failed"
    }
}
print(describe(.ok(code: 200)))
print(describe(.redirect(to: "/home")))
print(describe(.failed))

func codeOrZero(_ status: Status) -> Int {
    guard case .ok(let code) = status else {
        return 0
    }
    return code
}
print(codeOrZero(.ok(code: 7)), codeOrZero(.failed))

let status = Status.redirect(to: "/next")
if case .redirect(let target) = status {
    print("redirecting to \(target)")
}

// switch over optionals
func unwrapOr(_ value: Int?, _ fallback: Int) -> Int {
    switch value {
    case .some(let inner):
        return inner
    case .none:
        return fallback
    }
}
print(unwrapOr(5, 0), unwrapOr(nil, -1))

// pattern bindings with where
for value in 0...6 {
    switch value {
    case 0:
        print("zero", terminator: " ")
    case let even where even % 2 == 0:
        print("even \(even)", terminator: " ")
    default:
        print("odd \(value)", terminator: " ")
    }
}
print("")

// nested enum patterns
enum Token {
    case number(Int)
    case word(String)
    case end
}
func tokenName(_ token: Token) -> String {
    switch token {
    case .number(_):
        return "number"
    case .word(let text) where text.isEmpty:
        return "empty word"
    case .word(let text):
        return "word \(text)"
    case .end:
        return "end"
    }
}
print(tokenName(.number(1)), tokenName(.word("hi")), tokenName(.end))

// tuple patterns are not supported; use destructuring instead
let pair = (10, 20)
let (left, right) = pair
print(left + right)
