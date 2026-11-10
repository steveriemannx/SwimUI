// Sorting algorithms and closure comparators
func bubbleSorted(_ input: [Int]) -> [Int] {
    var values = input
    for i in 0..<values.count {
        for j in 0..<(values.count - i - 1) {
            if values[j] > values[j + 1] {
                let temp = values[j]
                values[j] = values[j + 1]
                values[j + 1] = temp
            }
        }
    }
    return values
}

let data = [5, 2, 9, 1, 5, 6]
print(bubbleSorted(data))
print(data.sorted())
print(data.sorted { $0 > $1 })

struct Person {
    var name: String
    var age: Int
}
let people = [
    Person(name: "Ada", age: 36),
    Person(name: "Bob", age: 25),
    Person(name: "Cara", age: 41)
]
print(people.sorted { $0.age < $1.age }.map { $0.name })
