// Classic FizzBuzz
func fizzbuzz(_ n: Int) -> String {
    if n % 15 == 0 { return "FizzBuzz" }
    if n % 3 == 0 { return "Fizz" }
    if n % 5 == 0 { return "Buzz" }
    return "\(n)"
}

for n in 1...20 {
    print(fizzbuzz(n), terminator: n % 5 == 0 ? "\n" : " ")
}
