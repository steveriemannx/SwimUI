// Fibonacci: iterative and memoized recursive versions
func fib(_ n: Int) -> Int {
    var a = 0
    var b = 1
    for _ in 0..<n {
        let next = a + b
        a = b
        b = next
    }
    return a
}

var memo: [Int: Int] = [:]
func fibMemo(_ n: Int) -> Int {
    if n < 2 {
        return n
    }
    if let cached = memo[n] {
        return cached
    }
    let value = fibMemo(n - 1) + fibMemo(n - 2)
    memo[n] = value
    return value
}

print((0..<15).map { fib($0) })
print((0..<15).map { fibMemo($0) })
print(fib(50))
