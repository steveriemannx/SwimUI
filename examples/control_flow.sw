// Conditionals, loops and switch
func grade(_ score: Int) -> String {
    if score >= 90 {
        return "A"
    } else if score >= 80 {
        return "B"
    } else if score >= 60 {
        return "C"
    }
    return "F"
}
print(grade(95), grade(83), grade(42))

// guard for early exit
func safeDivide(_ a: Int, _ b: Int) -> Int? {
    guard b != 0 else {
        return nil
    }
    return a / b
}
print(safeDivide(10, 3)!, safeDivide(1, 0) ?? -1)

// while / repeat-while
var countdown = 3
while countdown > 0 {
    print("countdown  \(countdown)")
    countdown -= 1
}

repeat {
    print("runs at least once")
} while false

// for-in, ranges, stride, where, enumerated
for i in 0..<3 {
    print(i, terminator: " ")
}
print("")

for i in stride(from: 0, to: 10, by: 5) {
    print(i, terminator: " ")
}
print("")

for n in 1...10 where n % 2 == 0 {
    print(n, terminator: " ")
}
print("")

for (index, letter) in "abc".enumerated() {
    print("\(index)=\(letter)", terminator: " ")
}
print("")

// switch: ranges, where clauses, multiple patterns, default branch
func classify(_ n: Int) -> String {
    switch n {
    case 0:
        return "zero"
    case 1...9 where n % 2 == 0:
        return "small even"
    case 1...9:
        return "small odd"
    default:
        return "large"
    }
}
print(classify(0), classify(4), classify(5), classify(100))

// Labeled loops
outer: for row in 0..<3 {
    for column in 0..<3 {
        if column == 1 {
            continue outer
        }
        print("cell \(row)-\(column)")
    }
}
