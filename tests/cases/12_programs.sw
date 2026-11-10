// Small complete programs.

// fizzbuzz
func fizzbuzz(_ n: Int) -> String {
    if n % 15 == 0 { return "FizzBuzz" }
    if n % 3 == 0 { return "Fizz" }
    if n % 5 == 0 { return "Buzz" }
    return "\(n)"
}
var fizz: [String] = []
for n in 1...15 {
    fizz.append(fizzbuzz(n))
}
print(fizz.joined(separator: ","))

// fibonacci (iterative)
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
print((0..<10).map { fib($0) })

// recursive factorial
func factorial(_ n: Int) -> Int {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}
print(factorial(6))

// bubble sort on an array of structs
struct Person {
    var name: String
    var age: Int
}
var people = [
    Person(name: "Ada", age: 36),
    Person(name: "Bob", age: 25),
    Person(name: "Cara", age: 41)
]
for i in 0..<people.count {
    for j in 0..<(people.count - i - 1) {
        if people[j].age > people[j + 1].age {
            let temp = people[j]
            people[j] = people[j + 1]
            people[j + 1] = temp
        }
    }
}
for person in people {
    print(person.name, person.age)
}

// binary search
func binarySearch(_ values: [Int], _ target: Int) -> Int? {
    var low = 0
    var high = values.count - 1
    while low <= high {
        let mid = (low + high) / 2
        if values[mid] == target {
            return mid
        }
        if values[mid] < target {
            low = mid + 1
        } else {
            high = mid - 1
        }
    }
    return nil
}
let sortedValues = [1, 3, 5, 7, 9, 11]
print(binarySearch(sortedValues, 7)!, binarySearch(sortedValues, 4) ?? -1)

// word frequencies
func wordCount(_ sentence: String) -> [String: Int] {
    var counts: [String: Int] = [:]
    for word in sentence.split(separator: " ") {
        let key = word.lowercased()
        counts[key] = (counts[key] ?? 0) + 1
    }
    return counts
}
let counts = wordCount("the cat and the dog and the bird")
var report: [String] = []
for key in counts.keys.sorted() {
    report.append("\(key):\(counts[key]!)")
}
print(report.joined(separator: " "))

// matrix sum
let matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
var diagonal = 0
for i in 0..<matrix.count {
    diagonal += matrix[i][i]
}
print(diagonal)

// prime sieve
func primes(upTo limit: Int) -> [Int] {
    var isPrime = [Bool](repeating: true, count: limit + 1)
    isPrime[0] = false
    isPrime[1] = false
    var p = 2
    while p * p <= limit {
        if isPrime[p] {
            var multiple = p * p
            while multiple <= limit {
                isPrime[multiple] = false
                multiple += p
            }
        }
        p += 1
    }
    var result: [Int] = []
    for n in 0...limit {
        if isPrime[n] {
            result.append(n)
        }
    }
    return result
}
print(primes(upTo: 30))
