// Variables, literals, arithmetic and printing.
let answer = 42
var count = 3
count += 2
print(answer, count)
print(answer - count, answer * count, answer / count, answer % count)

let ratio = 7.0 / 2.0
print(ratio)
print(1.5 + 2.5, 3 * 1.5)

let sword = "swim"
let exclamation = "!"
print(sword + exclamation)
print("interpolated: \(answer) and \(count * 2) and \(sword.uppercased())")

let isReady = answer > 40 && count < 10
print(isReady, !isReady, answer == 42 ? "yes" : "no")

// integer and float types
let big: Int64 = 9_000_000_000
print(big)
let small: Int8 = 12
print(small)
let single: Double = 2
print(single)

// character-ish strings
let initial = "S"
print(initial.count, initial)

// booleans
let yes = true
let no = false
print(yes && !no, yes || no)

// numeric conversions
print(Int(3.99), Double(7), String(123), Int("77")!)
print(abs(-9), min(3, 8), max(3, 8), pow(2.0, 8.0), sqrt(81.0))
