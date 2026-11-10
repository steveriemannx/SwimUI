// Arrays, dictionaries and sets
var fruits = ["apple", "banana"]
fruits.append("cherry")
fruits.insert("avocado", at: 0)
print(fruits, fruits.count, fruits.isEmpty)

print(fruits.first!, fruits.last!)
print(fruits.sorted())
print(fruits.filter { $0.count > 5 })
print(fruits.map { $0.uppercased() })
print(fruits.joined(separator: ", "))

var scores: [String: Int] = ["alice": 90]
scores["bob"] = 80
scores["alice"] = (scores["alice"] ?? 0) + 5
print(scores["alice"]!, scores["missing"] ?? -1)
print(scores.count, scores.keys.count, scores.values.count)

for name in scores.keys.sorted() {
    print("\(name): \(scores[name]!)")
}

var seen: Set<Int> = []
seen.insert(1)
seen.insert(2)
seen.insert(1)
print(seen.count, seen.contains(2), seen.contains(3))

// Dictionaries into arrays, sorting
let sortedPairs = scores.sorted(by: { $0.value > $1.value })
for pair in sortedPairs {
    print(pair.key, pair.value)
}
