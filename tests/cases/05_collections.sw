// Arrays, dictionaries and sets.
var numbers = [3, 1, 4, 1, 5]
print(numbers.count, numbers.isEmpty, numbers.contains(4))
numbers.append(9)
numbers.append(contentsOf: [2, 6])
print(numbers)
print(numbers.first!, numbers.last!)
print(numbers.min()!, numbers.max()!)
print(numbers.firstIndex(of: 4)!)
print(numbers.index(of: 1)!)
print(numbers.filter { $0 > 3 })
print(numbers.map { $0 * 2 })
print(numbers.sorted())
print(numbers.sorted { $0 > $1 })
print(numbers.prefix(3), numbers.suffix(2))
print(numbers.dropFirst(2))
numbers.insert(0, at: 0)
print(numbers.remove(at: 0))
print(numbers.contains(where: { $0 == 5 }))
numbers.removeAll(where: { $0 == 1 })
print(numbers)

// dictionaries
var ages = ["alice": 30]
ages["bob"] = 25
print(ages.count, ages.isEmpty)
print(ages["alice"]!, ages["missing"] ?? -1)
let removed = ages.updateValue(31, forKey: "alice")
print(removed!, ages["alice"]!)
print(ages.removeValue(forKey: "bob")!)
print(ages.keys.count, ages.values.count)

// dictionary iteration (order independent)
var pairs: [String] = []
for (key, value) in ages {
    pairs.append("\(key)=\(value)")
}
print(pairs.sorted().joined(separator: ","))

// sets
var unique: Set<Int> = []
unique.insert(3)
unique.insert(1)
unique.insert(3)
print(unique.count, unique.contains(1), unique.contains(2))
unique.remove(1)
print(unique.count)

// literal inference and nested collections
let matrix = [[1, 2], [3, 4]]
print(matrix.count, matrix[1][0])
let groups = ["a": [1, 2], "b": [3]]
print(groups["a"]!.count)

// range as a value
let range = 1...5
print(range.contains(3), range.contains(6))
