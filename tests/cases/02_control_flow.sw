// Conditionals and loops.
func sign(_ value: Int) -> String {
    if value > 0 {
        return "positive"
    } else if value < 0 {
        return "negative"
    } else {
        return "zero"
    }
}
print(sign(3), sign(-2), sign(0))

// guard
func positive(_ value: Int) -> Int {
    guard value > 0 else {
        return 0
    }
    return value
}
print(positive(5), positive(-5))

// while / repeat-while
var total = 0
var i = 1
while i <= 5 {
    total += i
    i += 1
}
print("sum \(total)")

var countdown = 3
repeat {
    print("tick \(countdown)")
    countdown -= 1
} while countdown > 0

// for loops
for n in 0..<4 {
    print(n, terminator: " ")
}
print("")

for n in 1...4 {
    print(n, terminator: " ")
}
print("")

for n in stride(from: 0, to: 10, by: 4) {
    print(n, terminator: " ")
}
print("")

// where clause
for n in 1...10 where n % 3 == 0 {
    print(n, terminator: " ")
}
print("")

// reversed range
for n in (0..<4).reversed() {
    print(n, terminator: " ")
}
print("")

// loops over strings and tuples
for (index, character) in "abc".enumerated() {
    print("\(index):\(character)", terminator: " ")
}
print("")

let pairs = [(1, "one"), (2, "two")]
for (number, name) in pairs {
    print("\(name)=\(number)", terminator: " ")
}
print("")

// labeled control flow
outer: for row in 0..<3 {
    for column in 0..<3 {
        if column == 1 {
            continue outer
        }
        if row == 2 {
            break outer
        }
        print("cell \(row) \(column)")
    }
}

// switch with ranges, multiple patterns, where and default
func classify(_ value: Int) -> String {
    switch value {
    case 0:
        return "zero"
    case 1...5:
        return "small"
    case 6...10 where value % 2 == 0:
        return "even medium"
    case 6...10:
        return "odd medium"
    default:
        return "large"
    }
}
print(classify(0), classify(3), classify(8), classify(7), classify(99))
